"""Public map geography and conservative, current, non-spy military contacts.

Protocol: official v374.p client decodes province coreIDs from ci, sight widths
from vw/dvw, STEALTH=13 and UNITFEATURE_CANNOT_CONQUER=48. Widths are rendered
as billboard diameters; use half the decoded width as a conservative radius.
Never treat the presence of an enemy army in raw state as proof of visibility.
"""
from .presentation import province_name
import math
import re

from .commander_state import locations, armies
from .protocol import collection, commands, army_status


def features(item):
    value = item.get('unitFeatures', '')
    if not isinstance(value, str) or (value and not re.fullmatch(r'a\d+=-?\d+(?:\.\d+)?(?:,a\d+=-?\d+(?:\.\d+)?)*', value)):
        return None
    return {int(k): float(v) for k, v in re.findall(r'a(\d+)=(-?\d+(?:\.\d+)?)', value)}


def can_capture(session, army):
    if army.get('a'):
        return False
    for unit in collection(army.get('u')):
        if not isinstance(unit, dict) or unit.get('cru') or unit.get('hp', 0) <= 0:
            continue
        item = session.ctrl.catalog.units.get(unit.get('t'))
        flags = features(item) if item is not None else None
        if flags is not None and session.ctrl.catalog.domain(unit.get('t')) == 'land' and not flags.get(48, 0):
            return True
    return False


def relation(raw, viewer, other):
    # Direction matters: the OTHER player grants access/intel to the viewer.
    rows = raw.get('states', {}).get('5', {}).get('relations', {}).get('neighborRelations', {})
    theirs = rows.get(str(other), rows.get(other, {}))
    return theirs.get(str(viewer), theirs.get(viewer, 1)) if isinstance(theirs, dict) else 1


def at_war(raw, viewer, other):
    return relation(raw, viewer, other) == -2 or relation(raw, other, viewer) == -2


def core_ids(province):
    value = province.get('ci')
    if not isinstance(value, list):
        return None
    return [n for n in collection(value) if type(n) is int and n > 0]


def geography(session, player_id=None, homeland_only=False, cities_only=False):
    players = session.raw.get('states', {}).get('1', {}).get('players', {})
    result = []
    for province in locations(session.raw).values():
        cores = core_ids(province)
        city = province.get('plv', 0) >= 4
        if cities_only and not city:
            continue
        if player_id is not None and ((not cores or player_id not in cores) if homeland_only else province.get('o') != player_id):
            continue
        if homeland_only and player_id is None and not cores:
            continue
        owner = province.get('o')
        player = players.get(str(owner), players.get(owner, {}))
        result.append({'province_id': province['id'], 'name': province_name(session.raw, province['id']),
                       'owner_id': owner, 'country': player.get('nationName'), 'is_city': city,
                       'core_owner_ids': cores, 'is_owner_homeland': owner in cores if cores is not None else None,
                       'is_our_homeland': session.player_id in cores if cores is not None else None})
    return {'provinces': sorted(result, key=lambda p: (not p['is_city'], p['province_id'])),
            'homeland_source': 'ci / coreIDs dari peta game; data yang tidak tersedia tetap unknown'}


def point(value):
    if not isinstance(value, dict) or not all(type(value.get(k)) in (int, float) and math.isfinite(value[k]) for k in ('x', 'y')):
        return None
    return value


def visible_contacts(session):
    """Return only current visual contacts or military access; no spy snapshots."""
    raw, pid = session.raw, session.player_id
    ours = armies(raw, pid)
    combat_ids = {str(order.get('targetUnitID')) for a in ours.values() if a.get('fs') in (1, 7) for order in commands(a)
                  if order.get('@c') == 'ac' and order.get('targetUnitID')}
    observers = []
    for army in ours.values():
        # Flying positions require interpolation; do not use their stale ground p.
        if army.get('a'):
            continue
        pos = point(army.get('p'))
        width = army.get('dvw', army.get('vw', 0))
        if pos and type(width) in (int, float) and math.isfinite(width) and width > 0:
            observers.append((pos, width / 2))
    contacts = []
    all_armies = raw.get('states', {}).get('6', {}).get('armies', {})
    for aid, enemy in all_armies.items() if isinstance(all_armies, dict) else []:
        if not isinstance(enemy, dict) or enemy.get('o') in (None, pid) or enemy.get('rm') or enemy.get('st', 0):
            continue
        pos = point(enemy.get('p'))
        if not pos or enemy.get('a'):
            continue
        shared = relation(raw, pid, enemy['o']) >= 4
        combat = str(aid) in combat_ids
        in_sight = any(math.hypot(pos['x'] - p['x'], pos['y'] - p['y']) <= radius for p, radius in observers)
        if not (shared or combat or in_sight):
            continue
        units = [u for u in collection(enemy.get('u')) if isinstance(u, dict)]
        flags = [features(session.ctrl.catalog.units.get(u.get('t'), {})) if u.get('t') in session.ctrl.catalog.units else None for u in units]
        # Concealed/unknown types cannot be revealed solely by geometric proximity.
        if not shared and not combat and (not units or any(f is None or f.get(13, 0) for f in flags)):
            continue
        details = [{'type_id': u.get('t'), 'name': session.ctrl.catalog.name(u['t']), 'count': u.get('s', 1)}
                   for u in units if not u.get('cru') and u.get('t') in session.ctrl.catalog.units]
        contacts.append({'army_id': str(aid), 'owner_id': enemy['o'], 'province_id': enemy.get('l'),
                         'position': dict(pos), 'units': details, 'identity_unknown': not details or any(u.get('cru') for u in units),
                         'source': 'shared_military' if shared else 'combat' if combat else 'own_sight',
                         'game_time': raw.get('timeStamp'), 'is_hostile': at_war(raw, pid, enemy['o'])})
    return contacts
