"""Live commander: plan economy, production/research, defense, and observed events."""
import math
import time

from .agent_engine import Outcome
from .commander_queue import TERMINAL, cost_for, drain, reconcile
from .commander_state import (Budget, locations, armies, item_costs, resource_lines,
                              queue_entries, busy_construction, snapshot)
from .protocol import collection, commands, army_status, same_point


def defensive_moves(session):
    catalog, pid = session.ctrl.catalog, session.player_id
    locs = locations(session.raw)
    cities = {k: p for k, p in locs.items() if p.get('o') == pid and p.get('plv', 0) >= 4}
    land = {}
    for aid, army in armies(session.raw, pid).items():
        units = collection(army.get('u'))
        if army.get('a') or not units or not all(isinstance(u, dict) and
                catalog.domain(u.get('t', 0)) == 'land' and u.get('hp', 0) > 0 for u in units):
            continue
        # A moving army's location can point to the next route province; it is not a garrison.
        if army_status(army) == 'IDLE':
            land[aid] = army
    garrisons = {cid: sum(a.get('l') == cid for a in land.values()) for cid in cities}
    incoming = set()
    for a in armies(session.raw, pid).values():
        units = collection(a.get('u'))
        if a.get('a') or not units or not all(catalog.domain(u.get('t', 0)) == 'land' for u in units):
            continue
        orders = commands(a)
        if orders and all(c.get('@c') == 'gc' for c in orders):
            incoming.update(cid for cid, city in cities.items() if same_point(orders[-1].get('tp'), city.get('c')))
    targets = sorted((p for cid, p in cities.items() if not garrisons[cid] and cid not in incoming),
                     key=lambda p: (p.get('m', 100), -p.get('plv', 0), p['id']))
    used = set()
    result = []
    for target in targets:
        options = []
        for aid, army in land.items():
            origin = locs.get(army.get('l'), {})
            if aid in used or origin.get('o') != pid or origin.get('m') is None or origin['m'] < 40:
                continue
            if origin.get('id') in cities and garrisons.get(origin['id'], 0) <= 1:
                continue
            source_pos, target_pos = army.get('p'), target.get('c')
            if not isinstance(source_pos, dict) or not isinstance(target_pos, dict) or not all(
                    k in source_pos and k in target_pos for k in ('x', 'y')):
                continue
            distance = math.hypot(source_pos['x'] - target_pos['x'], source_pos['y'] - target_pos['y'])
            if distance <= 1000:
                options.append((distance, aid, army))
        if not options:
            continue
        _, aid, army = min(options)
        used.add(aid)
        origin_id = army.get('l')
        if origin_id in garrisons:
            garrisons[origin_id] -= 1
        garrisons[target['id']] += 1
        result.append({'army_id': int(aid), 'target_province': target['id']})
    return result


def military_plan(session):
    from .tactics import visible_contacts
    pid, catalog = session.player_id, session.ctrl.catalog
    mine = armies(session.raw, pid)
    city_ids = {cid for cid, c in locations(session.raw).items() if c.get('o') == pid and c.get('plv', 0) >= 4}
    garrisons = {cid: [] for cid in city_ids}
    domains = {}
    for aid, army in mine.items():
        for u in collection(army.get('u')):
            if isinstance(u, dict):
                domain = catalog.domain(u.get('t', 0))
                domains[domain] = domains.get(domain, 0) + u.get('s', 1)
        if army_status(army) == 'IDLE' and army.get('l') in garrisons and not army.get('a') and any(
                catalog.domain(u.get('t', 0)) == 'land' for u in collection(army.get('u')) if isinstance(u, dict)):
            garrisons[army['l']].append(aid)
    return {'domains': domains, 'idle_armies': [aid for aid, a in mine.items() if army_status(a) == 'IDLE'],
            'unguarded_cities': sorted(cid for cid, ids in garrisons.items() if not ids),
            'defensive_moves': defensive_moves(session),
            'visible_contacts': visible_contacts(session),
            'intel_note': 'Kontak langsung dan akses militer dipisahkan dari spy. Fog dan stealth yang tidak terlihat tetap unknown.'}


def economy_plan(session, nodes):
    resources = resource_lines(session.raw, session.player_id)
    budget = Budget(resources)
    planned, unknown, fundable, upkeep = {}, [], [], {}
    for node in nodes:
        if node['kind'] in ('produce', 'build') and node['state'] not in TERMINAL:
            daily = session.ctrl.catalog.items.get(node['args']['item_id'], {}).get('dailyCosts', '')
            parsed = item_costs({'costs': daily}) if daily else {}
            if parsed is not None:
                for name, amount in parsed.items():
                    upkeep[name] = upkeep.get(name, 0) + amount
        if node['state'] in TERMINAL or node['state'] in ('accepted', 'dispatching', 'outcome_unknown'):
            continue
        costs = cost_for(session, node)
        if costs is None:
            unknown.append(node['id'])
            continue
        for name, value in costs.items():
            planned[name] = planned.get(name, 0) + value * 1.25
        if budget.reserve(costs):
            fundable.append(node['id'])
    scale = session.raw.get('states', {}).get('12', {}).get('timeScale')
    forecast = {}
    for name, line in resources.items():
        net = line['net_per_day'] - upkeep.get(name, 0)
        available = line['amount'] - budget.reserves[name]
        forecast[name] = {'amount': line['amount'], 'reserve': budget.reserves[name],
                          'planned_cost_with_margin': round(planned.get(name, 0), 2),
                          'planned_daily_upkeep': round(upkeep.get(name, 0), 2),
                          'after_entire_plan': round(available - planned.get(name, 0), 2),
                          'depletion_real_hours': round(max(0, available) / -net * 24 * scale, 2)
                              if net < 0 and isinstance(scale, (int, float)) and scale > 0 else None}
    return {'resources': forecast, 'fundable_nodes': fundable, 'unknown_cost_nodes': unknown,
            'note': 'Biaya node yang sudah diterima server tidak dipotong dua kali. Margin biaya 25% ditambah cadangan.'}


def migrate_legacy(session, store, game_id):
    """Adopt explicit old build queues; ambiguous names remain held, not guessed."""
    from .catalog import ALIASES, normalize
    previous = {}
    for old in store.builds(game_id, limit=200)[::-1]:
        adopted = store.preference(f'legacy_commander:{old["id"]}')
        if adopted:
            previous[old['city_id']] = adopted
            continue
        if old['status'] not in ('queued', 'unknown'):
            continue
        query = normalize(old['building'])
        query = ALIASES.get(query, query)
        props = session.raw.get('states', {}).get('3', {}).get('properties', {}).get(str(old['city_id']), {})
        ids = [b.get('id') for b in collection(props.get('queueableUpgrades')) if isinstance(b, dict)]
        matches = [iid for iid in ids if query == str(iid) or query == normalize(session.ctrl.catalog.name(iid))]
        if len(matches) != 1:
            continue
        deps = [previous[old['city_id']]] if old['city_id'] in previous else []
        node = store.enqueue_commander(game_id, session.player_id, 'build',
                                       {'city_id': old['city_id'], 'item_id': matches[0]}, deps)
        if old['status'] == 'unknown':
            store.set_commander_node(node['id'], 'outcome_unknown', 'Hasil pengiriman queue lama belum diketahui.')
        store.set_preference(f'legacy_commander:{old["id"]}', node['id'])
        store.set_build_status(old['id'], 'migrated', {'commander_node_id': node['id']})
        previous[old['city_id']] = node['id']


def plan(session, store, config):
    """Small live plans; never enqueue another active goal for the same slot."""
    gid, pid, raw = config['game_id'], session.player_id, session.raw
    catalog = session.ctrl.catalog
    source = f"auto:{config['started_at']}"
    nodes = store.commander_nodes(gid)
    planned = []

    def add(kind, args, priority):
        for n in nodes:
            if kind == 'move' and n['kind'].startswith('group_') and n['state'] not in TERMINAL:
                tracked = set(n['args'].get('unit_ids', []))
                own_unit_ids = {u.get('id') for u in collection(armies(raw, pid).get(str(args['army_id']), {}).get('u')) if isinstance(u, dict)}
                if args['army_id'] in n['args'].get('army_ids', []) or tracked.intersection(own_unit_ids):
                    return
            if kind == 'move' and n['kind'] in ('move', 'conquer') and n['args'].get('army_id') == args.get('army_id') and n['state'] not in TERMINAL:
                return
            same = n['kind'] == kind and (n['args'].get('city_id') == args.get('city_id') if kind in ('build', 'produce')
                                         else n['args'].get('army_id') == args.get('army_id') if kind == 'move'
                                         else n['args'].get('item_id') == args.get('item_id'))
            if same and (n['state'] not in TERMINAL or (n['source'] == source and n['state'] == 'failed')):
                return
        node = store.enqueue_commander(gid, pid, kind, args, source=source, priority=priority)
        nodes.append(node)
        planned.append(node['id'])

    props = raw.get('states', {}).get('3', {}).get('properties', {})
    for city in locations(raw).values():
        if city.get('o') != pid or city.get('plv', 0) < 4:
            continue
        available = props.get(str(city['id']), {})
        existing = {catalog.name(b.get('id', 0)).casefold() for b in collection(city.get('us')) if isinstance(b, dict)}
        if 'arms industry' not in existing:
            for entry in collection(available.get('queueableUpgrades')):
                if isinstance(entry, dict) and catalog.name(entry.get('id', 0)).casefold() == 'arms industry':
                    add('build', {'city_id': city['id'], 'item_id': entry['id']}, 3)
                    break
        if not queue_entries(city, 'produce'):
            choices = []
            for entry in collection(available.get('queueableProductions')):
                if not isinstance(entry, dict) or entry.get('enabled') is False:
                    continue
                iid = entry.get('unit', {}).get('t')
                if iid is None or catalog.domain(iid) != 'land':
                    continue
                name = catalog.name(iid).casefold()
                if name not in ('motorized infantry', 'national guard') or item_costs(catalog.items.get(iid, {})) is None:
                    continue
                choices.append((name != 'motorized infantry', iid))
            if choices:
                add('produce', {'city_id': city['id'], 'item_id': min(choices)[1]}, 2)
    relevant_names = {catalog.name(u.get('t', 0)).casefold() for a in armies(raw, pid).values()
                      for u in collection(a.get('u')) if isinstance(u, dict)}
    relevant_research = set()
    for unit in catalog.units.values():
        if catalog.name(unit['itemID']).casefold() in relevant_names:
            import re
            relevant_research.update(int(r) for r in re.findall(r'a(\d+)', unit.get('requiredResearches', '')))
    available = [r['id'] for r in catalog.available_research(raw, pid) if r['id'] in relevant_research
                 and item_costs(catalog.items.get(r['id'], {})) is not None]
    if available and not any(n['kind'] == 'research' and n['state'] not in TERMINAL for n in nodes):
        rid = min(available, key=lambda r: sum(item_costs(catalog.items[r]).values()))
        add('research', {'item_id': rid}, 4)
    for movement in defensive_moves(session):
        add('move', movement, 1)
    return planned


async def cycle(executor, store, runtime, config=None):
    config = dict(config or {})
    game_id = config.get('game_id') or store.task(runtime.task_id)['game_id']
    automatic = bool(config.get('enabled') and config.get('mode') == 'commander' and
                     time.time() < config.get('deadline', 0))
    if automatic:
        runtime.deadline = config['deadline']
    runtime.checkpoint()
    read = await executor.execute(game_id, 'get_status', {}, runtime)
    if not read.ok:
        session = executor.session(game_id)
        if session.ctrl:
            session.ctrl.client.session.close()
        session.ctrl = session.ge = session.raw = None
        return Outcome('Pembacaan game gagal; semua aksi baru ditahan.', 'failed')
    session = executor.session(game_id)
    if automatic and session.player_id != config.get('player_id'):
        current = store.preference('overnight_control', {})
        current.update(enabled=False, reason='player_changed')
        store.set_preference('overnight_control', current)
        return Outcome('Identitas pemain berubah; commander berhenti.', 'failed')
    data = snapshot(session)
    events = store.observe_commander(game_id, data)
    migrate_legacy(session, store, game_id)
    reconcile(session, store, game_id)
    planned = plan(session, store, config) if automatic and not config.get('observe_only') and not store.preference(f'commander_paused:{game_id}', False) else []
    actions = [] if config.get('observe_only') else await drain(executor, store, game_id, runtime, config if automatic else {})
    # Read again after actions, so events/completion remain observation based.
    if actions:
        refresh = await executor.execute(game_id, 'get_status', {}, runtime)
        if refresh.ok:
            events += store.observe_commander(game_id, snapshot(session))
            reconcile(session, store, game_id)
    result = {'events': len(events), 'alerts': [kind for kind, _ in events if kind in
              ('city_lost', 'province_lost', 'war_started', 'resource_low', 'enemy_contact_seen')], 'planned': planned, 'actions': actions,
              'queue_pending': sum(n['state'] not in TERMINAL for n in store.commander_nodes(game_id))}
    store.set_preference(f'commander_last:{game_id}', {'checked_at': time.time(), **result})
    if automatic:
        current = store.preference('overnight_control', {})
        if current.get('started_at') == config.get('started_at'):
            if any(a['state'] in ('outcome_unknown', 'failed') for a in actions):
                current.update(enabled=False, reason='action_failed_or_unverified')
            current.update(last_checked=time.time())
            store.set_preference('overnight_control', current)
    text = (f"Commander: {len(actions)} perintah diproses, {len(events)} perubahan game, "
            f"{result['queue_pending']} item belum selesai. Penyelesaian mengikuti state game.")
    return Outcome(text, 'failed' if any(a['state'] in ('outcome_unknown', 'failed') for a in actions) else 'completed')
