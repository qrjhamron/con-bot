"""State and command mapping checked against the public v374.p game client."""
import base64
import binascii
import math


def collection(value):
    if isinstance(value, list):
        if len(value) == 2 and isinstance(value[0], str):
            # Java [tag, items] wrapper: malformed items fail closed, never
            # leak the wrapper itself to callers expecting entry dicts.
            return value[1] if isinstance(value[1], list) else []
        return value
    return []


def resource_amount(entry, server_time):
    """Official client amount0 + rate * elapsed seconds, using game server time."""
    try:
        base = float(entry.get('amount0', 0))
    except (TypeError, ValueError):
        base = 0.0
    try:
        elapsed = max(0, float(server_time) - float(entry['time0'])) / 1000
        change = float(entry.get('rate', 0)) * elapsed
    except (KeyError, TypeError, ValueError):
        change = 0
    limit = float(entry.get('maxAmount', -1))
    if limit > 0 and base + change > limit:
        change = 0 if base >= limit else limit - base
    return math.floor(max(0, base + change))


def commands(army):
    return [c for c in collection(army.get('c')) if isinstance(c, dict)]


def order_summary(army):
    orders = commands(army)
    return {'count': len(orders), 'next': orders[0] if orders else None,
            'destination': orders[-1] if orders else None}


def army_status(army):
    """s is stack size. Orders and fs determine activity; never infer it from s."""
    orders = commands(army)
    first = orders[0] if orders else {}
    if first.get('@c') == 'gc' and first.get('at', 0):
        return 'MOVING'
    fight = army.get('fs', 0)
    if isinstance(fight, bool) or not isinstance(fight, int):
        # Malformed fight status never implies activity; fall through to orders.
        fight = 0
    if fight in (3, 4):
        return 'PATROL'
    if fight == 2:
        return 'BOMBARDING'
    if fight in (1, 7) or army.get('b'):
        return 'ATTACKING'
    if first.get('@c') == 'wc':
        return 'WAITING'
    if orders:
        return 'ORDERED'
    return 'IDLE'


def same_point(a, b, tolerance=1):
    if not isinstance(a, dict) or not isinstance(b, dict):
        return False
    if not all(k in a and k in b for k in ('x', 'y')):
        return False
    try:
        return math.hypot(float(a['x']) - float(b['x']), float(a['y']) - float(b['y'])) <= tolerance
    except (TypeError, ValueError):
        # Non-numeric coordinates never count as a match; callers treat
        # a non-match as unverified, never as verified.
        return False


def action_result(response, request_id=None):
    body = response.get('result', response) if isinstance(response, dict) else {}
    results = body.get('actionResults', {}) if isinstance(body, dict) else {}
    if not isinstance(results, dict):
        return None
    if request_id:
        value = results.get(request_id)
        return value if type(value) is int else None
    values = [v for k, v in results.items() if k != '@c']
    return values[0] if len(values) == 1 and type(values[0]) is int else None


def verification(sub, raw, player_id):
    """Return observed evidence, or None if the requested effect is not visible."""
    states = raw.get('states', {})
    kind = sub.get('@c', '').rsplit('.', 1)[-1]
    if kind == 'UltArmyAction':
        observed = states.get('6', {}).get('armies', {})
        evidence = []
        for expected in collection(sub.get('armies')):
            army = observed.get(str(expected.get('id')), observed.get(expected.get('id')))
            if not isinstance(army, dict) or army.get('o') != player_id:
                # Arrival can merge selected armies. Prove original unit membership
                # at the destination instead of guessing a replacement army ID.
                wanted = commands(expected)
                unit_ids = {u.get('id') for u in collection(expected.get('u')) if isinstance(u, dict)}
                if not wanted or wanted[-1].get('@c') != 'gc' or not unit_ids or None in unit_ids:
                    return None
                matched_ids, merged_armies = set(), []
                for a in observed.values():
                    if not isinstance(a, dict) or a.get('o') != player_id:
                        continue
                    units = {u.get('id') for u in collection(a.get('u')) if isinstance(u, dict) and u.get('hp', 0) > 0}
                    route = [c for c in commands(a) if c.get('@c') == 'gc']
                    arrived = same_point(a.get('p'), wanted[-1].get('tp')) and not commands(a)
                    moving = bool(route) and same_point(route[-1].get('tp'), wanted[-1].get('tp'))
                    if units.intersection(unit_ids) and (arrived or moving):
                        matched_ids.update(units)
                        merged_armies.append(a.get('id'))
                if not unit_ids.issubset(matched_ids):
                    return None
                evidence.append({'army_id': expected['id'], 'status': 'ORDER_VERIFIED_AFTER_MERGE',
                                 'unit_ids_verified': sorted(unit_ids), 'current_army_ids': merged_armies})
                continue
            want, actual = commands(expected), commands(army)
            if not want:
                if actual:
                    return None
            else:
                last = want[-1]
                if last.get('@c') == 'gc':
                    route = [c for c in actual if c.get('@c') == 'gc']
                    reached = same_point(army.get('p'), last.get('tp')) and not actual
                    if not reached and (not route or not same_point(route[-1].get('tp'), last.get('tp'))):
                        return None
                elif last.get('@c') == 'ac':
                    matched = any(c.get('@c') == 'ac' and
                                  c.get('targetUnitID', 0) == last.get('targetUnitID', 0) and
                                  same_point(c.get('targetPos'), last.get('targetPos')) for c in actual)
                    if not matched:
                        return None
                elif last.get('@c') == 'pc':
                    matched = any(c.get('@c') == 'pc' and c.get('type') == last.get('type') and
                                  same_point(c.get('targetPos'), last.get('targetPos')) and
                                  (last.get('type') != 'Guard' or not last.get('airField') or
                                   army.get('aip', {}).get('airField') == last.get('airField')) for c in actual)
                    reached = (last.get('type') == 'AirplaneRelocation' and not actual and
                               same_point(army.get('p'), last.get('targetPos')) and
                               army.get('aip', {}).get('airField') == last.get('airField'))
                    if not matched and not reached:
                        return None
                else:
                    return None
            evidence.append({'army_id': expected['id'], 'status': army_status(army), 'orders': order_summary(army)})
        return {'armies': evidence} if evidence else None
    if kind == 'UltChangeRelationAction':
        targets = sub.get('playerB')
        targets = targets if isinstance(targets, list) else [targets]
        try:
            raw_relation = base64.b64decode(sub.get('relationType', ''))
        except (ValueError, TypeError, binascii.Error):
            return None
        if not raw_relation:
            return None
        byte = raw_relation[0]
        relation = byte - 256 if byte >= 128 else byte
        rows = states.get('5', {}).get('relations', {}).get('neighborRelations', {})
        ours = rows.get(str(player_id), rows.get(player_id, {}))
        if all(ours.get(str(t), ours.get(t, 1)) == relation for t in targets):
            return {'targets': targets, 'relation': relation}
    if kind == 'UltResearchAction' and not sub.get('cancel'):
        research = states.get('23', {})
        rid = sub.get('researchID')
        if rid is None:
            return None
        active = collection(research.get('currentResearches'))
        done = research.get('completedResearches', {})
        if any(r.get('researchTypeID', r.get('researchID')) == rid for r in active) or str(rid) in done:
            return {'research_id': rid, 'observed': True}
    if kind == 'UltUpdateProvinceAction' and sub.get('mode') in (1, 2):
        locations = {p['id']: p for p in collection(states.get('3', {}).get('map', {}).get('locations'))
                     if isinstance(p, dict) and 'id' in p}
        upgrade = sub.get('upgrade', {})
        mode = sub['mode']
        target_id = upgrade.get('id') if mode == 1 else upgrade.get('unit', {}).get('t')
        if target_id is None:
            return None
        provinces = collection(sub.get('provinceIDs'))
        completed = True
        for pid in provinces:
            province = locations.get(pid, {})
            if province.get('o') != player_id:
                return None
            if mode == 1:
                built = [e.get('id') for e in collection(province.get('us')) if isinstance(e, dict)]
                constructing = [p.get('u', {}).get('id') if isinstance(p.get('u'), dict) else None
                                for p in collection(province.get('cos')) if isinstance(p, dict)]
                if target_id not in built and target_id not in constructing:
                    return None
                completed = completed and target_id not in constructing and any(
                    e.get('id') == target_id and e.get('built') is not False and not e.get('cn')
                    for e in collection(province.get('us')) if isinstance(e, dict))
            else:
                entries = collection(province.get('prs'))
                pi = province.get('pi')
                if isinstance(pi, dict):
                    entries.append(pi)
                found = any(e.get('u', {}).get('unit', {}).get('t') == target_id
                            for e in entries if isinstance(e, dict))
                if not found:
                    return None
        if not provinces:
            return None
        evidence = {'province_ids': provinces, 'item_id': target_id, 'observed': True}
        if mode == 1:
            # A finished building sits in 'us'; an entry only in 'cos' is still under construction.
            evidence['completed'] = completed
        return evidence
    if kind == 'UltUpdateProvinceAction' and sub.get('mode') in (3, 4):
        # Cancel building (3) or production (4): the slot must read free (None).
        # Missing queue data never verifies; an occupied slot is not a cancellation.
        locations = {p['id']: p for p in collection(states.get('3', {}).get('map', {}).get('locations'))
                     if isinstance(p, dict) and 'id' in p}
        field = 'cos' if sub.get('mode') == 3 else 'prs'
        slot = sub.get('slot', 0)
        provinces = collection(sub.get('provinceIDs'))
        for pid in provinces:
            province = locations.get(pid, {})
            if province.get('o') != player_id:
                return None
            queue = province.get(field)
            if not isinstance(queue, list) or len(queue) < 2:
                return None
            entries = collection(province.get(field))
            if isinstance(slot, bool) or not isinstance(slot, int) or slot >= len(entries) or entries[slot] is not None:
                return None
        return {'province_ids': provinces, 'cancelled': True, 'observed': True} if provinces else None
    return None


def action_key(sub):
    """Stable intent identity, ignoring clocks, position interpolation and HP."""
    def pos_items(command):
        pos = command.get('targetPos') or command.get('tp') or {}
        if not isinstance(pos, dict):
            return ()
        try:
            return tuple(sorted(pos.items(), key=repr))
        except (TypeError, ValueError):
            return ()

    kind = sub.get('@c', '')
    if kind.endswith('UltArmyAction'):
        return (kind, tuple((a.get('id'), tuple((c.get('@c'), c.get('targetUnitID'),
                     pos_items(c)) for c in commands(a)))
                    for a in collection(sub.get('armies'))))
    if kind.endswith('UltChangeRelationAction'):
        targets = sub.get('playerB', [])
        return (kind, tuple(targets if isinstance(targets, list) else [targets]), sub.get('relationType'))
    if kind.endswith('UltResearchAction'):
        return (kind, sub.get('researchID'), sub.get('cancel', False))
    if kind.endswith('UltUpdateProvinceAction'):
        item = sub.get('upgrade', {})
        if not isinstance(item, dict):
            return None
        unit = item.get('unit', {})
        return (kind, sub.get('mode'), tuple(collection(sub.get('provinceIDs'))),
                item.get('id'), unit.get('t') if isinstance(unit, dict) else None)
    return None
