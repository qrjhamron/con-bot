"""Observed own-game state, resource budgets, and durable change detection."""
import math
import re

from .protocol import collection, army_status, resource_amount, commands
from .overnight import RESERVES, RESOURCE_NAMES


def locations(raw):
    return {p['id']: p for p in collection(raw.get('states', {}).get('3', {}).get('map', {}).get('locations'))
            if isinstance(p, dict) and 'id' in p}


def armies(raw, player_id):
    return {str(k): a for k, a in raw.get('states', {}).get('6', {}).get('armies', {}).items()
            if isinstance(a, dict) and a.get('o') == player_id}


def resource_lines(raw, player_id):
    state = raw.get('states', {}).get('4', {})
    profile = state.get('resourceProfs', {}).get(str(player_id), {})
    result = {}
    for category in profile.get('categories', {}).values():
        if not isinstance(category, dict):
            continue
        for rid, entry in category.get('resourceEntries', {}).items():
            if not isinstance(entry, dict) or not str(rid).isdigit() or int(rid) not in RESOURCE_NAMES:
                continue
            consumed = sum(entry.get(k, 0) for k in
                           ('dailyUnitConsumption', 'dailyUpgradeConsumption', 'dailyPopulationConsumption'))
            result[RESOURCE_NAMES[int(rid)]] = {
                'amount': resource_amount(entry, raw.get('timeStamp', state.get('timeStamp'))),
                'net_per_day': entry.get('production', 0) - consumed}
    return result


def item_costs(item):
    value = item.get('costs')
    if not isinstance(value, str) or not value or item.get('costsFunction'):
        return None
    costs = {}
    for part in value.split(','):
        match = re.fullmatch(r'a(\d+)=(\d+(?:\.\d+)?)', part.strip())
        if not match or int(match[1]) not in RESOURCE_NAMES:
            return None
        name = RESOURCE_NAMES[int(match[1])]
        costs[name] = costs.get(name, 0) + float(match[2])
    return costs


class Budget:
    def __init__(self, resources, reserves=None):
        self.resources = resources
        self.reserves = dict(RESERVES if reserves is None else reserves)
        self.committed = {}

    def shortages(self, costs):
        if costs is None:
            return {'unknown_cost': True}
        shortage = {}
        for name, amount in costs.items():
            balance = self.resources.get(name, {}).get('amount')
            if not isinstance(balance, (int, float)) or not math.isfinite(balance):
                shortage[name] = 'unknown_balance'
            else:
                needed = amount * 1.25 + self.reserves.get(name, 0) + self.committed.get(name, 0)
                if balance < needed:
                    shortage[name] = math.ceil(needed - balance)
        return shortage

    def reserve(self, costs):
        if self.shortages(costs):
            return False
        for name, amount in costs.items():
            self.committed[name] = self.committed.get(name, 0) + amount * 1.25
        return True


def queue_entries(city, kind):
    key = 'cos' if kind == 'build' else 'prs'
    result = [p for p in collection(city.get(key)) if isinstance(p, dict)]
    if kind == 'produce' and isinstance(city.get('pi'), dict) and city['pi'].get('u'):
        result.append(city['pi'])
    return result


def busy_construction(city, catalog):
    def real_upgrade(b):
        return not catalog.name(b.get('id', 0)).casefold().startswith('population level')
    return (any(real_upgrade(p.get('u', {})) for p in queue_entries(city, 'build')) or
            any(b.get('built') is False and b.get('cn') and real_upgrade(b)
                for b in collection(city.get('us')) if isinstance(b, dict)))


def finished_building(city, item_id):
    if any(p.get('u', {}).get('id') == item_id for p in queue_entries(city, 'build')):
        return False
    return any(b.get('id') == item_id and b.get('built') is not False and not b.get('cn')
               for b in collection(city.get('us')) if isinstance(b, dict))


def unit_totals(raw, player_id):
    totals = {}
    for army in armies(raw, player_id).values():
        for unit in collection(army.get('u')):
            if isinstance(unit, dict) and 't' in unit:
                key = str(unit['t'])
                totals[key] = totals.get(key, 0) + unit.get('s', 1)
    return totals


def unit_inventory(raw, player_id):
    result = {}
    for army in armies(raw, player_id).values():
        for unit in collection(army.get('u')):
            if isinstance(unit, dict) and 'id' in unit and 't' in unit:
                result[str(unit['id'])] = {'item_id': unit['t'], 'count': unit.get('s', 1),
                                          'province_id': army.get('l'), 'stationary': not commands(army)}
    return result


def snapshot(session):
    raw, pid = session.raw, session.player_id
    locs = locations(raw)
    catalog = session.ctrl.catalog
    cities = {}
    for city in locs.values():
        if city.get('o') != pid or city.get('plv', 0) < 4:
            continue
        cities[str(city['id'])] = {
            'morale': city.get('m'),
            'built': sorted(b['id'] for b in collection(city.get('us'))
                            if isinstance(b, dict) and 'id' in b and finished_building(city, b['id'])),
            'construction': sorted(p.get('u', {}).get('id', 0) for p in queue_entries(city, 'build')),
            'production': sorted(p.get('u', {}).get('unit', {}).get('t', 0)
                                 for p in queue_entries(city, 'produce'))}
    research = raw.get('states', {}).get('23', {})
    mine = armies(raw, pid)
    relations = raw.get('states', {}).get('5', {}).get('relations', {}).get('neighborRelations', {})
    ours = relations.get(str(pid), relations.get(pid, {}))
    wars = sorted(int(k) for k, v in ours.items() if str(k).isdigit() and v == -2)
    report = raw.get('states', {}).get('7', {}).get('spyReport', {})
    intel = {}
    if isinstance(report, dict):
        day = report.get('currentDay')
        for daily in collection(report.get('dailyStates')):
            if not isinstance(daily, dict) or daily.get('day') != day:
                continue
            for detail in collection(daily.get('detailedStates')):
                if not isinstance(detail, dict) or not detail.get('@c', '').endswith('UltDetailedSpyState'):
                    continue
                owner = detail.get('playerID')
                if owner is None or owner == pid:
                    continue
                intel[str(owner)] = {'day': day, 'source': 'spy_report_snapshot'}
    from .tactics import visible_contacts
    return {'visible_contacts': visible_contacts(session), 'player_id': pid, 'cities': cities,
            'owned_provinces': sorted(p['id'] for p in locs.values() if p.get('o') == pid),
            'armies': {aid: {'province_id': a.get('l'), 'status': army_status(a)} for aid, a in mine.items()},
            'unit_totals': unit_totals(raw, pid), 'resources': resource_lines(raw, pid),
            'wars': wars, 'intel_reports': intel,
            'research_done': sorted(int(k) for k in research.get('completedResearches', {}) if str(k).isdigit()),
            'research_active': sorted(r.get('researchTypeID', r.get('researchID', 0))
                                      for r in collection(research.get('currentResearches')) if isinstance(r, dict)),
            'army_names': sorted({catalog.name(u.get('t', 0)) for a in mine.values()
                                  for u in collection(a.get('u')) if isinstance(u, dict)})}


def changes(before, after):
    if not before or before.get('player_id') != after['player_id']:
        return []
    events = []
    old_contacts = {c['army_id']: c for c in before.get('visible_contacts', [])}
    new_contacts = {c['army_id']: c for c in after.get('visible_contacts', [])}
    for aid, contact in new_contacts.items():
        if aid not in old_contacts or (contact.get('is_hostile') and not old_contacts[aid].get('is_hostile')):
            events.append(('enemy_contact_seen' if contact.get('is_hostile') else 'military_contact_seen', contact))
        elif old_contacts[aid].get('position') != contact.get('position'):
            events.append(('enemy_contact_moved', contact))
    for aid in old_contacts.keys() - new_contacts.keys():
        events.append(('enemy_contact_lost', {'army_id': aid, 'last_seen': old_contacts[aid],
                      'note': 'Tidak lagi terlihat; posisi sekarang dan nasib pasukan belum diketahui.'}))
    for city_id in set(before['cities']) - set(after['cities']):
        events.append(('city_lost', {'city_id': int(city_id)}))
    for city_id in set(after['cities']) - set(before['cities']):
        events.append(('city_gained', {'city_id': int(city_id)}))
    for province_id in set(before['owned_provinces']) - set(after['owned_provinces']):
        events.append(('province_lost', {'province_id': province_id}))
    for province_id in set(after['owned_provinces']) - set(before['owned_provinces']):
        events.append(('province_gained', {'province_id': province_id}))
    for pid in set(after.get('wars', [])) - set(before.get('wars', [])):
        events.append(('war_started', {'player_id': pid}))
    for pid, intel in after.get('intel_reports', {}).items():
        if before.get('intel_reports', {}).get(pid) != intel:
            events.append(('intel_report_available', {'player_id': pid, **intel}))
    for aid in set(before['armies']) - set(after['armies']):
        events.append(('army_no_longer_observed', {'army_id': aid, 'note': 'Bisa hilang atau bergabung; bukan bukti kehancuran.'}))
    for city_id, city in after['cities'].items():
        old = before['cities'].get(city_id, {})
        for bid in set(city['built']) - set(old.get('built', [])):
            if old:
                events.append(('building_completed', {'city_id': int(city_id), 'item_id': bid}))
        if old.get('production') and not city['production']:
            events.append(('production_slot_free', {'city_id': int(city_id)}))
        if city.get('morale') is not None and city['morale'] < 35 and old.get('morale', 100) >= 35:
            events.append(('low_morale', {'city_id': int(city_id), 'morale': city['morale']}))
    for rid in set(after['research_done']) - set(before['research_done']):
        events.append(('research_completed', {'research_id': rid}))
    for aid, army in after['armies'].items():
        old = before['armies'].get(aid)
        if old and old['status'] != 'IDLE' and army['status'] == 'IDLE':
            events.append(('army_idle', {'army_id': aid, 'province_id': army['province_id']}))
    for name, data in after['resources'].items():
        old = before['resources'].get(name, {})
        if data['amount'] < RESERVES[name] and old.get('amount', 0) >= RESERVES[name]:
            events.append(('resource_low', {'resource': name, 'amount': data['amount']}))
    for tid, count in after['unit_totals'].items():
        gain = count - before['unit_totals'].get(tid, 0)
        if gain > 0:
            events.append(('units_observed', {'item_id': int(tid), 'increase': gain}))
    return events
