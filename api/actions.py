#!/usr/bin/env python3
"""Action registry for game agent tool calls."""

import sys, os, time, math
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from _conn import (connect, get_locations, get_armies, get_players,
                    get_properties, army_units, army_hp, army_status_str,
                    unit_name, building_name, UNIT_NAMES, BUILDING_NAMES)

_ctrl = _ge = _raw = None

def _connect():
    global _ctrl, _ge, _raw
    _ctrl, _ge, _raw = connect()
    return _ctrl, _ge, _raw

def _ensure():
    if _ctrl is None:
        _connect()
    return _ctrl, _ge, _raw

def refresh():
    """Force refresh game state from server."""
    global _raw
    ctrl, ge, raw = _ensure()
    ctrl.refresh_state()
    _raw = ctrl.state
    return ctrl, ge, _raw


def get_status() -> dict:
    ctrl, ge, raw = refresh()
    locs = get_locations(raw)
    armies_data = get_armies(raw)
    players = get_players(raw)
    now_ms = time.time() * 1000

    s12 = raw.get('states', {}).get('12', {})
    day = s12.get('dayOfGame', '?')

    p88 = players.get(88, {})
    vp = p88.get('vps', 0)
    our_provs = sum(1 for l in locs if isinstance(l, dict) and l.get('o') == 88)

    res = ge.get_resources()
    resources = {}
    for k in ['Money', 'Supplies', 'Manpower', 'Metal', 'Oil', 'Fuel', 'Electronics']:
        r = res.get(k, {})
        resources[k] = {
            'amount': round(r.get('amount', 0)),
            'net_per_day': round(r.get('production', 0) - r.get('consumption', 0)),
        }

    our_armies = []
    for aid, a in armies_data.items():
        if isinstance(a, dict) and a.get('o') == 88:
            units = []
            for u in army_units(a):
                if isinstance(u, dict):
                    units.append({'type': unit_name(u.get('t', 0)), 'hp': u.get('hp', 0)})
            our_armies.append({
                'id': int(aid), 'status': army_status_str(a.get('s', 0)),
                'hp': round(army_hp(a)), 'units': units,
            })

    cities = []
    for loc in locs:
        if not isinstance(loc, dict) or loc.get('o') != 88 or loc.get('plv', 0) < 4:
            continue
        pid = loc.get('id', 0)
        pi = loc.get('pi')
        status = 'idle'
        producing = None
        if pi and isinstance(pi, dict) and pi.get('u'):
            su = pi['u']
            ut = su.get('unit', {}).get('t', su.get('t', 0))
            comp = pi.get('t', 0)
            rem = (comp - now_ms) / 3600000
            status = 'producing'
            producing = f"{unit_name(ut)} ({rem:.1f}h)"
        cities.append({'id': pid, 'status': status, 'producing': producing})

    # Wars
    nr = raw.get('states', {}).get('5', {}).get('relations', {}).get('neighborRelations', {})
    our_rels = nr.get('88', nr.get(88, {}))
    war_pids = set()
    for pk, rel in our_rels.items():
        if isinstance(rel, (int, float)) and rel == -2:
            war_pids.add(int(pk))
    wars = []
    for pid in sorted(war_pids):
        nation = players.get(pid, {}).get('nationName', f'P{pid}')
        ep = sum(1 for l in locs if isinstance(l, dict) and l.get('o') == pid)
        wars.append({'player_id': pid, 'nation': nation, 'provinces': ep})

    return {
        'day': day, 'vp': vp, 'provinces': our_provs, 'speed': '4x',
        'resources': resources, 'armies': our_armies, 'cities': cities,
        'wars': wars, 'goldmark': ge.get_goldmark(),
    }


def get_armies_detail() -> dict:
    """Get all our armies with unit details, position, status."""
    ctrl, ge, raw = refresh()
    locs = get_locations(raw)
    armies_data = get_armies(raw)
    players = get_players(raw)

    loc_list = [l for l in locs if isinstance(l, dict) and 'c' in l]

    def find_province(pos):
        if not isinstance(pos, dict):
            return None
        ax, ay = pos.get('x', 0), pos.get('y', 0)
        best, best_d = None, float('inf')
        for loc in loc_list:
            c = loc.get('c', {})
            if not isinstance(c, dict):
                continue
            d = math.hypot(c.get('x', 0) - ax, c.get('y', 0) - ay)
            if d < best_d:
                best_d, best = d, loc
        return best

    result = []
    for aid, a in armies_data.items():
        if not isinstance(a, dict) or a.get('o') != 88:
            continue
        loc = find_province(a.get('p'))
        owner_name = ''
        prov_id = None
        if loc:
            prov_id = loc.get('id')
            ow = loc.get('o')
            if ow and ow != 88:
                owner_name = players.get(ow, {}).get('nationName', f'P{ow}')
            else:
                owner_name = 'ours'

        units = []
        for u in army_units(a):
            if isinstance(u, dict):
                units.append({
                    'type': unit_name(u.get('t', 0)),
                    'type_id': u.get('t', 0),
                    'hp': round(u.get('hp', 0), 1),
                    'morale': round(u.get('ml', 1.0) * 100, 1),
                })
        result.append({
            'army_id': int(aid),
            'status': army_status_str(a.get('s', 0)),
            'province_id': prov_id,
            'territory': owner_name,
            'total_hp': round(army_hp(a), 1),
            'units': units,
        })
    return {'armies': result, 'count': len(result)}


def get_cities_detail() -> dict:
    """Get all our cities with buildings, production, available units."""
    ctrl, ge, raw = refresh()
    locs = get_locations(raw)
    props = get_properties(raw)
    now_ms = time.time() * 1000

    result = []
    for loc in locs:
        if not isinstance(loc, dict) or loc.get('o') != 88 or loc.get('plv', 0) < 4:
            continue
        pid = loc.get('id', 0)

        # Buildings
        buildings = []
        us = loc.get('us', [])
        if isinstance(us, list) and len(us) > 1:
            for b in us[1]:
                if isinstance(b, dict):
                    bid = b.get('id')
                    built = b.get('built')
                    cn = b.get('cn')
                    status = 'built'
                    if built is False and cn:
                        status = 'building'
                    buildings.append({
                        'id': bid, 'name': building_name(bid), 'status': status,
                    })

        # Production
        pi = loc.get('pi')
        prod_status = 'idle'
        producing = None
        if pi and isinstance(pi, dict) and pi.get('u'):
            su = pi['u']
            ut = su.get('unit', {}).get('t', su.get('t', 0))
            comp = pi.get('t', 0)
            rem = (comp - now_ms) / 3600000
            prod_status = 'producing'
            producing = {'unit': unit_name(ut), 'hours_remaining': round(rem, 1)}

        # Available productions
        p = props.get(str(pid), {})
        qp = p.get('queueableProductions', [])
        items = qp[1] if isinstance(qp, list) and len(qp) > 1 else []
        available_units = []
        for item in (items if isinstance(items, list) else []):
            if isinstance(item, dict):
                t = item.get('unit', {}).get('t')
                if t:
                    available_units.append({'type_id': t, 'name': unit_name(t)})

        # Available buildings
        qu = p.get('queueableUpgrades') or p.get('possibleUpgrades') or []
        items_b = qu[1] if isinstance(qu, list) and len(qu) > 1 else (list(qu.values()) if isinstance(qu, dict) else [])
        available_buildings = []
        for item in (items_b if isinstance(items_b, list) else []):
            if isinstance(item, dict):
                bid = item.get('id')
                if bid:
                    available_buildings.append({'id': bid, 'name': building_name(bid)})

        result.append({
            'city_id': pid, 'level': loc.get('plv', 0),
            'morale': loc.get('m', 0),
            'buildings': buildings, 'production': prod_status,
            'producing': producing, 'available_units': available_units,
            'available_buildings': available_buildings[:10],
        })
    return {'cities': result, 'count': len(result)}


def get_resources_detail() -> dict:
    """Get detailed resource breakdown."""
    ctrl, ge, raw = refresh()
    res = ge.get_resources()
    result = {}
    for k in ['Money', 'Supplies', 'Manpower', 'Metal', 'Oil', 'Fuel', 'Electronics']:
        r = res.get(k, {})
        result[k] = {
            'amount': round(r.get('amount', 0)),
            'production': round(r.get('production', 0)),
            'consumption': round(r.get('consumption', 0)),
            'net': round(r.get('production', 0) - r.get('consumption', 0)),
        }
    result['Goldmark'] = ge.get_goldmark()
    return result


def get_players_info() -> dict:
    """Get all players with VP, provinces, relations."""
    ctrl, ge, raw = refresh()
    locs = get_locations(raw)
    players = get_players(raw)

    owners = {}
    for loc in locs:
        if isinstance(loc, dict):
            ow = loc.get('o')
            if ow:
                owners[ow] = owners.get(ow, 0) + 1

    nr = raw.get('states', {}).get('5', {}).get('relations', {}).get('neighborRelations', {})
    our_rels = nr.get('88', {})
    rel_names = {-2: 'WAR', 6: 'SHARED_INTEL', 99: 'SELF'}

    result = []
    for pid, p in sorted(players.items(), key=lambda x: -x[1].get('vps', 0)):
        provs = owners.get(pid, 0)
        rel = our_rels.get(str(pid))
        rel_str = rel_names.get(rel, '') if rel else ''
        result.append({
            'player_id': pid,
            'nation': p.get('nationName', ''),
            'name': p.get('name', ''),
            'vp': p.get('vps', 0),
            'provinces': provs,
            'is_bot': p.get('computerPlayer', False),
            'relation': rel_str,
        })
    return {'players': result[:50]}


def get_research_info() -> dict:
    """Get research status: active, completed, slots."""
    ctrl, ge, raw = refresh()
    s23 = raw.get('states', {}).get('23', {})
    now_ms = time.time() * 1000

    current = []
    cr = s23.get('currentResearches', [])
    if isinstance(cr, list) and len(cr) > 1:
        for r in cr[1]:
            if isinstance(r, dict):
                rid = r.get('researchTypeID')
                end = r.get('endTime', 0)
                rem = (end - now_ms) / 3600000
                current.append({'id': rid, 'hours_remaining': round(rem, 1)})

    completed = [int(k) for k in s23.get('completedResearches', {}).keys() if k != '@c']
    slots = s23.get('researchSlots', 0)

    return {
        'active': current,
        'completed': completed,
        'slots_total': slots,
        'slots_used': len(current),
    }


def get_enemy_provinces() -> dict:
    """Get all provinces owned by players we're at war with or AI bots near us."""
    ctrl, ge, raw = refresh()
    locs = get_locations(raw)
    players = get_players(raw)

    nr = raw.get('states', {}).get('5', {}).get('relations', {}).get('neighborRelations', {})
    our_rels = nr.get('88', {})
    war_pids = set()
    for pk, rel in our_rels.items():
        if isinstance(rel, (int, float)) and rel == -2:
            war_pids.add(int(pk))

    # Also include weak AI bots in Africa
    for pid, p in players.items():
        if p.get('computerPlayer') and pid not in war_pids:
            provs = sum(1 for l in locs if isinstance(l, dict) and l.get('o') == pid)
            if 0 < provs <= 15:
                war_pids.add(pid)

    result = {}
    for loc in locs:
        if isinstance(loc, dict) and loc.get('o') in war_pids:
            ow = loc.get('o')
            nation = players.get(ow, {}).get('nationName', f'P{ow}')
            if nation not in result:
                result[nation] = {'player_id': ow, 'provinces': []}
            result[nation]['provinces'].append(loc.get('id'))

    return result


def _resolve_player(name_or_id) -> int:
    try:
        return int(name_or_id)
    except (ValueError, TypeError):
        pass
    ctrl, ge, raw = _ensure()
    players = get_players(raw)
    name_lower = str(name_or_id).lower().strip()
    # Exact match first
    for pid, p in players.items():
        nn = p.get('nationName', '').lower()
        dn = p.get('defaultNationName', '').lower()
        un = p.get('name', '').lower()
        if name_lower == nn or name_lower == dn or name_lower == un:
            return pid
    # Substring match requiring >75% length overlap to prevent "Niger" matching "Nigeria"
    for pid, p in players.items():
        nn = p.get('nationName', '').lower()
        dn = p.get('defaultNationName', '').lower()
        if (name_lower in nn and len(name_lower) > len(nn) * 0.75) or \
           (name_lower in dn and len(name_lower) > len(dn) * 0.75):
            return pid
    return -1

def move_army(army_id: int, target_province: int) -> dict:
    """Move an army to a target province."""
    ctrl, ge, raw = _ensure()
    try:
        r = ctrl.move_army(int(army_id), int(target_province))
        ar = _extract_ar(r)
        return {'success': ar == 1, 'army_id': army_id, 'target': target_province}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def produce_unit(city_id: int, unit_type: str) -> dict:
    """Produce a unit in a city. unit_type: 'infantry', 'motorized_infantry', 'attack_helicopter', 'mbt', 'sam', 'recon', 'artillery', 'mlrs', 'strike_fighter'."""
    ctrl, ge, raw = _ensure()
    type_map = {
        'infantry': 10141, 'motorized_infantry': 3294, 'mot': 3294,
        'attack_helicopter': 3308, 'heli': 3308, 'mbt': 3322, 'tank': 3322,
        'sam': 3373, 'recon': 3229, 'artillery': 3336, 'mlrs': 3350,
        'strike_fighter': 3387, 'fighter': 3387, 'bomber': 3401,
    }
    uid = type_map.get(unit_type.lower().replace(' ', '_'), None)
    if uid is None:
        try:
            uid = int(unit_type)
        except ValueError:
            return {'success': False, 'error': f'Unknown unit type: {unit_type}. Available: {list(type_map.keys())}'}

    try:
        r = ctrl.produce_unit(city_id, uid)
        ar = _extract_ar(r)
        return {'success': ar == 1, 'city_id': city_id, 'unit': unit_name(uid)}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def build_building(city_id: int, building_type: str) -> dict:
    """Build a building in a city. building_type: 'army_base', 'recruiting_office', 'local_industry', 'arms_industry', 'airbase', 'naval_base', 'barracks', 'propaganda', 'research_lab', 'radar', 'bunker', 'hospital'."""
    ctrl, ge, raw = _ensure()
    type_map = {
        'army_base': 2271, 'army_base_lv2': 2244, 'army_base_lv3': 2272,
        'recruiting_office': 2245, 'recruiting_office_lv2': 2246,
        'local_industry': 2250, 'local_industry_lv2': 2251,
        'arms_industry': 2016, 'airbase': 2260, 'airbase_lv2': 2261,
        'naval_base': 2255, 'naval_base_lv2': 2256, 'barracks': 2270,
        'propaganda': 2275, 'propaganda_lv2': 2276, 'research_lab': 2280,
        'radar': 2295, 'bunker': 2265, 'hospital': 2290,
        'secret_weapons_lab': 2285, 'combat_outpost': 2240,
    }
    bid = type_map.get(building_type.lower().replace(' ', '_'), None)
    if bid is None:
        try:
            bid = int(building_type)
        except ValueError:
            return {'success': False, 'error': f'Unknown building: {building_type}. Available: {list(type_map.keys())}'}

    try:
        r = ctrl.build_building(city_id, bid)
        ar = _extract_ar(r)
        return {'success': ar == 1, 'city_id': city_id, 'building': building_name(bid)}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def declare_war(player_id: int) -> dict:
    """Declare war on a player. Can use player ID or nation name (e.g. 'Ghana', 'Mali')."""
    ctrl, ge, raw = _ensure()
    pid = _resolve_player(player_id)
    if pid == -1:
        return {'success': False, 'error': f'Player not found: {player_id}'}
    r = ctrl.declare_war(pid)
    ar = _extract_ar(r)
    players = get_players(raw)
    name = players.get(pid, {}).get('nationName', f'P{pid}')
    return {'success': ar == 1, 'target': name, 'player_id': pid}


def offer_peace(player_id) -> dict:
    """Offer peace to a player. Can use player ID or nation name."""
    ctrl, ge, raw = _ensure()
    pid = _resolve_player(player_id)
    if pid == -1:
        return {'success': False, 'error': f'Player not found: {player_id}'}
    try:
        r = ctrl.offer_peace(pid)
        ar = _extract_ar(r)
        return {'success': ar == 1, 'player_id': pid}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def auto_conquer() -> dict:
    """Auto-send all idle armies to nearest enemy provinces."""
    ctrl, ge, raw = refresh()
    locs = get_locations(raw)
    armies_data = get_armies(raw)
    players = get_players(raw)

    nr = raw.get('states', {}).get('5', {}).get('relations', {}).get('neighborRelations', {})
    our_rels = nr.get('88', {})
    war_pids = set()
    for pk, rel in our_rels.items():
        if isinstance(rel, (int, float)) and rel == -2:
            war_pids.add(int(pk))

    idle = []
    loc_list = [l for l in locs if isinstance(l, dict) and 'c' in l]

    def find_pos(pos):
        if not isinstance(pos, dict):
            return 0, 0
        return pos.get('x', 0), pos.get('y', 0)

    for aid, a in armies_data.items():
        if isinstance(a, dict) and a.get('o') == 88 and a.get('s') == 1:
            idle.append((int(aid), a))

    targets = []
    for loc in locs:
        if isinstance(loc, dict) and loc.get('o') in war_pids:
            targets.append(loc)

    assigned = set()
    moves = []
    for aid, a in sorted(idle, key=lambda x: -army_hp(x[1])):
        ax, ay = find_pos(a.get('p'))
        best_t, best_d = None, float('inf')
        for loc in targets:
            lid = loc.get('id')
            if lid in assigned:
                continue
            c = loc.get('c', {})
            if not isinstance(c, dict):
                continue
            d = math.hypot(c.get('x', 0) - ax, c.get('y', 0) - ay)
            if d < best_d:
                best_d, best_t = d, loc
        if best_t:
            assigned.add(best_t['id'])
            r = ctrl.move_army(aid, best_t['id'])
            ar = _extract_ar(r)
            owner = best_t.get('o')
            nation = players.get(owner, {}).get('nationName', '?')
            moves.append({
                'army_id': aid, 'target': best_t['id'],
                'nation': nation, 'success': ar == 1,
            })

    successful = sum(1 for m in moves if m['success'])
    return {'deployed': successful, 'idle_remaining': len(idle) - successful, 'moves': moves}


def auto_produce() -> dict:
    """Auto-produce units in all idle cities."""
    ctrl, ge, raw = refresh()
    locs = get_locations(raw)
    props = get_properties(raw)

    results = []
    for loc in locs:
        if not isinstance(loc, dict) or loc.get('o') != 88 or loc.get('plv', 0) < 4:
            continue
        pid = loc.get('id', 0)
        if loc.get('pi'):
            continue  # already producing

        p = props.get(str(pid), {})
        qp = p.get('queueableProductions', [])
        items = qp[1] if isinstance(qp, list) and len(qp) > 1 else []

        priority = [10141, 3294, 3308, 3322, 3373]
        produced = False
        for uid in priority:
            avail = any(isinstance(it, dict) and it.get('unit', {}).get('t') == uid for it in (items if isinstance(items, list) else []))
            if not avail:
                continue
            try:
                r = ctrl.produce_unit(pid, uid)
                ar = _extract_ar(r)
                if ar == 1:
                    results.append({'city_id': pid, 'unit': unit_name(uid), 'success': True})
                    produced = True
                    break
            except Exception:
                continue
        if not produced:
            results.append({'city_id': pid, 'unit': None, 'success': False})

    return {'results': results}


def build_in_all_cities(building_type: str) -> dict:
    """Build a specific building in ALL cities that can build it."""
    ctrl, ge, raw = refresh()
    locs = get_locations(raw)

    type_map = {
        'army_base': 2271, 'army_base_lv2': 2244, 'army_base_lv3': 2272,
        'recruiting_office': 2245, 'local_industry': 2250,
        'arms_industry': 2016, 'airbase': 2260, 'barracks': 2270,
        'propaganda': 2275, 'research_lab': 2280, 'radar': 2295,
        'bunker': 2265, 'hospital': 2290,
    }
    bid = type_map.get(building_type.lower().replace(' ', '_'))
    if bid is None:
        try:
            bid = int(building_type)
        except ValueError:
            return {'success': False, 'error': f'Unknown building: {building_type}'}

    results = []
    for loc in locs:
        if not isinstance(loc, dict) or loc.get('o') != 88 or loc.get('plv', 0) < 4:
            continue
        pid = loc.get('id', 0)
        us = loc.get('us', [])
        existing = set()
        if isinstance(us, list) and len(us) > 1:
            for b in us[1]:
                if isinstance(b, dict):
                    existing.add(b.get('id'))
        if bid in existing:
            results.append({'city_id': pid, 'success': True, 'skipped': 'already_built'})
            continue
        try:
            r = ctrl.build_building(pid, bid)
            ar = _extract_ar(r)
            results.append({'city_id': pid, 'success': ar == 1})
        except Exception:
            results.append({'city_id': pid, 'success': False})

    built = sum(1 for r in results if r['success'])
    return {'building': building_name(bid), 'attempted': len(results), 'success': built, 'details': results}


def declare_war_on_all_bots() -> dict:
    """Declare war on all weak AI bot nations nearby."""
    ctrl, ge, raw = refresh()
    locs = get_locations(raw)
    players = get_players(raw)

    results = []
    for pid, p in players.items():
        if not p.get('computerPlayer'):
            continue
        provs = sum(1 for l in locs if isinstance(l, dict) and l.get('o') == pid)
        if provs <= 0 or provs > 15:
            continue
        try:
            r = ctrl.declare_war(pid)
            ar = _extract_ar(r)
            results.append({
                'player_id': pid, 'nation': p.get('nationName', ''),
                'provinces': provs, 'success': ar == 1,
            })
        except Exception:
            pass

    return {'wars_declared': sum(1 for r in results if r['success']), 'details': results}


def send_message(player_id, message: str) -> dict:
    """Send an in-game message to a player. Accepts ID or name."""
    ctrl, ge, raw = _ensure()
    pid = _resolve_player(player_id)
    if pid == -1:
        return {'success': False, 'error': f'Player not found: {player_id}'}
    try:
        r = ge.send_message(pid, message)
        return {'success': True, 'player_id': pid}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def start_research(research_id: int) -> dict:
    """Start a research by ID."""
    ctrl, ge, raw = _ensure()
    try:
        r = ctrl.research(research_id)
        ar = _extract_ar(r)
        return {'success': ar == 1, 'research_id': research_id}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def deploy_spy(province_id: int, mission_type: int = 0) -> dict:
    """Recruit and deploy a spy to a province. mission_type: 0=economy, 1=military, 2=sabotage."""
    ctrl, ge, raw = _ensure()
    try:
        r = ge.recruit_and_deploy_spy(province_id, mission_type)
        return {'success': r, 'province_id': province_id}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def full_conquest_cycle() -> dict:
    """Run a full conquest cycle: re-declare wars, auto-conquer, auto-produce, auto-build."""
    results = {}
    results['wars'] = declare_war_on_all_bots()
    results['conquest'] = auto_conquer()
    results['production'] = auto_produce()
    results['buildings'] = auto_build_infrastructure()
    return results


def auto_build_infrastructure() -> dict:
    """Auto-build essential buildings in cities that need them."""
    ctrl, ge, raw = refresh()
    locs = get_locations(raw)
    essential = [2245, 2250, 2271, 2016]
    results = []
    for loc in locs:
        if not isinstance(loc, dict) or loc.get('o') != 88 or loc.get('plv', 0) < 4:
            continue
        pid = loc.get('id', 0)
        us = loc.get('us', [])
        existing = set()
        under_construction = False
        if isinstance(us, list) and len(us) > 1:
            for b in us[1]:
                if isinstance(b, dict):
                    existing.add(b.get('id'))
                    if b.get('built') is False and b.get('cn'):
                        under_construction = True
        if loc.get('cos'):
            under_construction = True
        if under_construction:
            continue
        for bid in essential:
            if bid not in existing:
                try:
                    r = ctrl.build_building(pid, bid)
                    ar = _extract_ar(r)
                    if ar == 1:
                        results.append({'city_id': pid, 'building': building_name(bid), 'success': True})
                        break
                except Exception:
                    continue
    return {'built': len(results), 'details': results}


def buy_market_resource(resource: str, amount: int) -> dict:
    """Buy resources from market. resource: 'metal', 'oil', 'manpower', 'electronics', 'supplies', 'fuel'."""
    ctrl, ge, raw = _ensure()
    res_map = {'supplies': 1, 'oil': 2, 'manpower': 3, 'electronics': 4, 'metal': 5, 'fuel': 6}
    res_id = res_map.get(resource.lower())
    if not res_id:
        return {'success': False, 'error': f'Unknown resource: {resource}. Available: {list(res_map.keys())}'}
    try:
        r = ctrl.buy_resource(res_id, amount, 99.0)
        ar = _extract_ar(r)
        return {'success': ar == 1, 'resource': resource, 'amount': amount}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def sell_market_resource(resource: str, amount: int) -> dict:
    """Sell resources on market. resource: 'metal', 'oil', 'manpower', 'electronics', 'supplies', 'fuel'."""
    ctrl, ge, raw = _ensure()
    res_map = {'supplies': 1, 'oil': 2, 'manpower': 3, 'electronics': 4, 'metal': 5, 'fuel': 6}
    res_id = res_map.get(resource.lower())
    if not res_id:
        return {'success': False, 'error': f'Unknown resource: {resource}'}
    try:
        r = ctrl.sell_resource(res_id, amount, 1.0)
        ar = _extract_ar(r)
        return {'success': ar == 1, 'resource': resource, 'amount': amount}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def get_spy_info() -> dict:
    """Get all our spy units with their missions and locations."""
    ctrl, ge, raw = refresh()
    spies = ge.get_spies()
    return {'spies': spies, 'count': len(spies)}


def offer_shared_intel(player_id) -> dict:
    """Offer shared intelligence to a player (alliance building). Accepts ID or name."""
    ctrl, ge, raw = _ensure()
    pid = _resolve_player(player_id)
    if pid == -1:
        return {'success': False, 'error': f'Player not found: {player_id}'}
    try:
        r = ge.offer_shared_intel(pid)
        return {'success': r, 'player_id': pid}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def offer_right_of_way(player_id) -> dict:
    """Offer right of way to a player. Accepts ID or name."""
    ctrl, ge, raw = _ensure()
    pid = _resolve_player(player_id)
    if pid == -1:
        return {'success': False, 'error': f'Player not found: {player_id}'}
    try:
        r = ge.offer_right_of_way(pid)
        return {'success': r, 'player_id': pid}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def get_ranking() -> dict:
    """Get top players ranking by VP."""
    ctrl, ge, raw = refresh()
    ranking = ge.get_ranking(top_n=20)
    return {'ranking': ranking}


def get_battle_log() -> dict:
    """Get active battles and recent combat events."""
    ctrl, ge, raw = refresh()
    armies_data = get_armies(raw)
    players = get_players(raw)
    battles = []
    for aid, a in armies_data.items():
        if not isinstance(a, dict):
            continue
        if a.get('o') == 88 and a.get('s') == 3:  # our ATTACKING armies
            target = a.get('tg', {})
            target_id = target.get('id', 0) if isinstance(target, dict) else 0
            battles.append({
                'army_id': int(aid), 'status': 'ATTACKING',
                'hp': round(army_hp(a), 1), 'target': target_id,
            })
        elif a.get('o') != 88 and a.get('s') in (2, 3):  # enemy moving/attacking
            owner = a.get('o', 0)
            nation = players.get(owner, {}).get('nationName', f'P{owner}')
            battles.append({
                'army_id': int(aid), 'status': 'ENEMY', 'owner': nation,
                'hp': round(army_hp(a), 1),
            })
    return {'active_battles': battles, 'count': len(battles)}


def scan_threats() -> dict:
    """Scan for enemy armies near our territory — early warning system."""
    ctrl, ge, raw = refresh()
    locs = get_locations(raw)
    armies_data = get_armies(raw)
    players = get_players(raw)

    # Get center of our territory
    our_provs = [l for l in locs if isinstance(l, dict) and l.get('o') == 88 and 'c' in l]
    if not our_provs:
        return {'threats': [], 'warning': 'No territory found'}
    avg_x = sum(l['c'].get('x', 0) for l in our_provs if isinstance(l.get('c'), dict)) / len(our_provs)
    avg_y = sum(l['c'].get('y', 0) for l in our_provs if isinstance(l.get('c'), dict)) / len(our_provs)

    threats = []
    for aid, a in armies_data.items():
        if not isinstance(a, dict) or a.get('o') == 88:
            continue
        pos = a.get('p', {})
        if not isinstance(pos, dict):
            continue
        d = math.hypot(pos.get('x', 0) - avg_x, pos.get('y', 0) - avg_y)
        if d < 500:  # within 500px threat radius
            owner = a.get('o', 0)
            nation = players.get(owner, {}).get('nationName', f'P{owner}')
            threats.append({
                'army_id': int(aid), 'owner': nation, 'owner_id': owner,
                'distance': round(d), 'hp': round(army_hp(a), 1),
                'status': army_status_str(a.get('s', 0)),
            })
    threats.sort(key=lambda x: x['distance'])
    return {'threats': threats[:20], 'total_nearby': len(threats)}


def smart_expansion() -> dict:
    """Analyze map for optimal expansion targets — weakest neighbors with most provinces."""
    ctrl, ge, raw = refresh()
    locs = get_locations(raw)
    players = get_players(raw)

    # Our border provinces
    our_provs = set()
    for l in locs:
        if isinstance(l, dict) and l.get('o') == 88:
            our_provs.add(l.get('id'))

    # Our province positions for distance checks
    our_positions = []
    for l in locs:
        if isinstance(l, dict) and l.get('o') == 88:
            c = l.get('c', {})
            if isinstance(c, dict):
                our_positions.append((c.get('x', 0), c.get('y', 0)))

    # Find neighbors
    neighbor_owners = {}
    for l in locs:
        if not isinstance(l, dict) or l.get('o') == 88 or not l.get('o'):
            continue
        owner = l.get('o')
        c = l.get('c', {})
        if not isinstance(c, dict):
            continue
        cx, cy = c.get('x', 0), c.get('y', 0)
        for ox, oy in our_positions:
            if math.hypot(cx - ox, cy - oy) < 80:
                if owner not in neighbor_owners:
                    neighbor_owners[owner] = {'provs': 0, 'border_provs': set()}
                neighbor_owners[owner]['border_provs'].add(l.get('id'))
                break

    # Count total provinces per neighbor
    for l in locs:
        if isinstance(l, dict) and l.get('o') in neighbor_owners:
            neighbor_owners[l['o']]['provs'] += 1

    targets = []
    for pid, info in sorted(neighbor_owners.items(), key=lambda x: x[1]['provs']):
        p = players.get(pid, {})
        targets.append({
            'player_id': pid,
            'nation': p.get('nationName', ''),
            'is_bot': p.get('computerPlayer', False),
            'total_provinces': info['provs'],
            'border_provinces': len(info['border_provs']),
            'vp': p.get('vps', 0),
            'difficulty': 'EASY' if p.get('computerPlayer') and info['provs'] <= 10 else
                         'MEDIUM' if info['provs'] <= 20 else 'HARD',
        })
    return {'expansion_targets': targets}


def move_all_idle_to_target(player_id: int) -> dict:
    """Move ALL idle armies to provinces owned by a specific player. Can use player ID or nation name."""
    pid = _resolve_player(player_id)
    if pid == -1:
        return {'success': False, 'error': f'Player not found: {player_id}'}
    ctrl, ge, raw = refresh()
    locs = get_locations(raw)
    armies_data = get_armies(raw)
    players = get_players(raw)

    target_provs = [l for l in locs if isinstance(l, dict) and l.get('o') == pid]
    if not target_provs:
        name = players.get(pid, {}).get('nationName', f'P{pid}')
        return {'success': False, 'error': f'{name} has no provinces'}

    idle = [(int(aid), a) for aid, a in armies_data.items()
            if isinstance(a, dict) and a.get('o') == 88 and a.get('s') == 1]

    def army_pos(a):
        p = a.get('p', {})
        return (p.get('x', 0), p.get('y', 0)) if isinstance(p, dict) else (0, 0)

    assigned = set()
    moves = []
    for aid, a in sorted(idle, key=lambda x: -army_hp(x[1])):
        ax, ay = army_pos(a)
        best, best_d = None, float('inf')
        for loc in target_provs:
            if loc.get('id') in assigned:
                continue
            c = loc.get('c', {})
            if not isinstance(c, dict):
                continue
            d = math.hypot(c.get('x', 0) - ax, c.get('y', 0) - ay)
            if d < best_d:
                best_d, best = d, loc
        if best:
            assigned.add(best['id'])
            r = ctrl.move_army(aid, best['id'])
            ar = _extract_ar(r)
            moves.append({'army_id': aid, 'target': best['id'], 'success': ar == 1})

    nation = players.get(pid, {}).get('nationName', f'P{pid}')
    return {'target': nation, 'deployed': len(moves), 'moves': moves}


def _extract_ar(response):
    res = response.get('result', response)
    ar = res.get('actionResults', {})
    for k, v in ar.items():
        if k != '@c':
            return v
    return 0


TOOLS = [
    {
        "name": "get_status",
        "description": "Get full game dashboard: day, VP, provinces, resources, armies, production, wars",
        "fn": get_status,
        "parameters": {},
    },
    {
        "name": "get_armies_detail",
        "description": "Get all our armies with unit details, position, HP, morale, status",
        "fn": get_armies_detail,
        "parameters": {},
    },
    {
        "name": "get_cities_detail",
        "description": "Get all our cities with buildings, production status, available units and buildings to build",
        "fn": get_cities_detail,
        "parameters": {},
    },
    {
        "name": "get_resources_detail",
        "description": "Get detailed resource amounts, production and consumption rates",
        "fn": get_resources_detail,
        "parameters": {},
    },
    {
        "name": "get_players_info",
        "description": "Get all players with VP, provinces, relations, bot status",
        "fn": get_players_info,
        "parameters": {},
    },
    {
        "name": "get_research_info",
        "description": "Get research status: active research, completed, available slots",
        "fn": get_research_info,
        "parameters": {},
    },
    {
        "name": "get_enemy_provinces",
        "description": "Get all enemy provinces (war targets and weak AI bots)",
        "fn": get_enemy_provinces,
        "parameters": {},
    },
    {
        "name": "move_army",
        "description": "Move a specific army to a target province by ID",
        "fn": move_army,
        "parameters": {
            "army_id": {"type": "integer", "description": "The army ID to move"},
            "target_province": {"type": "integer", "description": "Target province ID"},
        },
    },
    {
        "name": "produce_unit",
        "description": "Produce a military unit in a city. Types: infantry, motorized_infantry, attack_helicopter, mbt, sam, recon, artillery, mlrs, strike_fighter, bomber",
        "fn": produce_unit,
        "parameters": {
            "city_id": {"type": "integer", "description": "City province ID"},
            "unit_type": {"type": "string", "description": "Unit type name (e.g. 'infantry', 'mbt', 'attack_helicopter')"},
        },
    },
    {
        "name": "build_building",
        "description": "Build a building in a specific city. Types: army_base, recruiting_office, local_industry, arms_industry, airbase, naval_base, barracks, propaganda, research_lab, radar, bunker, hospital",
        "fn": build_building,
        "parameters": {
            "city_id": {"type": "integer", "description": "City province ID"},
            "building_type": {"type": "string", "description": "Building type name"},
        },
    },
    {
        "name": "build_in_all_cities",
        "description": "Build a specific building type in ALL cities at once",
        "fn": build_in_all_cities,
        "parameters": {
            "building_type": {"type": "string", "description": "Building type name to build everywhere"},
        },
    },
    {
        "name": "declare_war",
        "description": "Declare war on a player. Accepts player ID number OR nation name like 'Ghana', 'Mali', 'Niger'",
        "fn": declare_war,
        "parameters": {
            "player_id": {"type": "string", "description": "Player ID or nation name (e.g. 29, 'Ghana', 'Mali')"},
        },
    },
    {
        "name": "offer_peace",
        "description": "Offer peace to a player. Accepts player ID or nation name like 'South Sudan'",
        "fn": offer_peace,
        "parameters": {
            "player_id": {"type": "string", "description": "Player ID or nation name"},
        },
    },
    {
        "name": "auto_conquer",
        "description": "Auto-send ALL idle armies to nearest enemy provinces",
        "fn": auto_conquer,
        "parameters": {},
    },
    {
        "name": "auto_produce",
        "description": "Auto-produce units in all idle cities",
        "fn": auto_produce,
        "parameters": {},
    },
    {
        "name": "declare_war_on_all_bots",
        "description": "Declare war on ALL weak AI bot nations (<=15 provinces)",
        "fn": declare_war_on_all_bots,
        "parameters": {},
    },
    {
        "name": "full_conquest_cycle",
        "description": "Run full conquest: re-declare wars on bots + auto-conquer + auto-produce",
        "fn": full_conquest_cycle,
        "parameters": {},
    },
    {
        "name": "move_all_idle_to_target",
        "description": "Move ALL idle armies toward a specific player's territory. Accepts player ID or nation name like 'Ghana', 'Mali'",
        "fn": move_all_idle_to_target,
        "parameters": {
            "player_id": {"type": "string", "description": "Player ID or nation name (e.g. 29, 'Ghana')"},
        },
    },
    {
        "name": "send_message",
        "description": "Send in-game message to a player. Accepts player ID or nation name",
        "fn": send_message,
        "parameters": {
            "player_id": {"type": "string", "description": "Player ID or nation name"},
            "message": {"type": "string", "description": "Message text"},
        },
    },
    {
        "name": "start_research",
        "description": "Start a research by its ID number",
        "fn": start_research,
        "parameters": {
            "research_id": {"type": "integer", "description": "Research type ID"},
        },
    },
    {
        "name": "deploy_spy",
        "description": "Recruit and deploy a spy to a province. mission_type: 0=economy, 1=military, 2=sabotage",
        "fn": deploy_spy,
        "parameters": {
            "province_id": {"type": "integer", "description": "Province to spy on"},
            "mission_type": {"type": "integer", "description": "0=economy, 1=military, 2=sabotage (default: 0)"},
        },
    },
    {
        "name": "auto_build_infrastructure",
        "description": "Auto-build essential buildings (Recruiting Office, Local Industry, Army Base, Arms Industry) in all cities that need them",
        "fn": auto_build_infrastructure,
        "parameters": {},
    },
    {
        "name": "buy_market_resource",
        "description": "Buy resources from the market. Types: metal, oil, manpower, electronics, supplies, fuel",
        "fn": buy_market_resource,
        "parameters": {
            "resource": {"type": "string", "description": "Resource type to buy"},
            "amount": {"type": "integer", "description": "Amount to buy"},
        },
    },
    {
        "name": "sell_market_resource",
        "description": "Sell resources on the market. Types: metal, oil, manpower, electronics, supplies, fuel",
        "fn": sell_market_resource,
        "parameters": {
            "resource": {"type": "string", "description": "Resource type to sell"},
            "amount": {"type": "integer", "description": "Amount to sell"},
        },
    },
    {
        "name": "get_spy_info",
        "description": "Get all our spy units with missions, locations, and status",
        "fn": get_spy_info,
        "parameters": {},
    },
    {
        "name": "offer_shared_intel",
        "description": "Offer shared intelligence alliance to a player. Accepts ID or nation name",
        "fn": offer_shared_intel,
        "parameters": {
            "player_id": {"type": "string", "description": "Player ID or nation name"},
        },
    },
    {
        "name": "offer_right_of_way",
        "description": "Offer right of way to a player. Accepts ID or nation name",
        "fn": offer_right_of_way,
        "parameters": {
            "player_id": {"type": "string", "description": "Player ID or nation name"},
        },
    },
    {
        "name": "get_ranking",
        "description": "Get top 20 players leaderboard with VP, nation, rank",
        "fn": get_ranking,
        "parameters": {},
    },
    {
        "name": "get_battle_log",
        "description": "Get active battles — our attacking armies and enemy armies nearby",
        "fn": get_battle_log,
        "parameters": {},
    },
    {
        "name": "scan_threats",
        "description": "Early warning system — scan for enemy armies near our territory",
        "fn": scan_threats,
        "parameters": {},
    },
    {
        "name": "smart_expansion",
        "description": "Analyze map for optimal expansion targets — shows weakest neighbors with difficulty rating",
        "fn": smart_expansion,
        "parameters": {},
    },
]
