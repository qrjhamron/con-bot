"""Plans from authenticated configuration and current owned/visible game data."""
import itertools
import math
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal
from .combat import numbers, plan_combat, finite
from .commander_state import armies, locations, finished_building
from .protocol import collection, commands, army_status, same_point
from .presentation import province_name, remaining_hours
from .tactics import can_capture, point


class StackArguments(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    army_ids: list[int] = Field(default_factory=list, max_length=40)
    target_province: int | None = Field(default=None, gt=0)
    domain: Literal['land', 'air', 'sea'] = 'land'
    preserve_garrisons: bool = True


class AirArguments(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    province_ids: list[int] = Field(default_factory=list, max_length=30)
    army_ids: list[int] = Field(default_factory=list, max_length=30)


class OccupationArguments(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    release_morale: int = Field(default=40, ge=35, le=100)


class Scenario(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    label: str = Field(min_length=1, max_length=100)
    army_ids: list[int] = Field(min_length=1, max_length=20)
    target_province: int = Field(gt=0)
    wait_hours: float = Field(default=0, ge=0, le=48)


class SimulationArguments(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    scenarios: list[Scenario] = Field(min_length=1, max_length=6)


def config(session, tid):
    mod = getattr(session.ctrl.catalog, 'game_mod', {})
    return mod.get('allUnitTypes', {}).get(str(tid), {}) or mod.get('unitTypes', {}).get(str(tid), {})


def numeric_map(value):
    if isinstance(value, str):
        return numbers(value) or {}
    if isinstance(value, dict):
        result = {}
        for k, v in value.items():
            if not str(k).lstrip('-').isdigit() or isinstance(v, bool):
                continue
            try:
                number = float(v)
            except (TypeError, ValueError):
                continue
            if math.isfinite(number):
                result[int(k)] = number
        return result
    return {}


def stacking(session, count, terrain, domain='land'):
    mod = getattr(session.ctrl.catalog, 'game_mod', {})
    if not mod:
        return {'damage_factor': None, 'speed_factor': None, 'optimal_size': None, 'known': False}
    if 75 not in collection(mod.get('gameFeatures')):
        return {'damage_factor': 1.0, 'speed_factor': 1.0, 'optimal_size': 1000, 'known': True}
    key = str(1 if domain == 'air' else terrain)
    table = mod.get('armyStackingPenaltyConfig')
    if not isinstance(table, dict) or count <= 0:
        return {'damage_factor': None, 'speed_factor': None, 'optimal_size': None, 'known': False}
    def segments(field):
        row = table.get(field, {}).get(key, {})
        return sorted((float(k), float(v)) for k, v in row.get('segmentValues', {}).items()
                      if k != '@c' and finite(v))
    damage_segments, speed_segments = segments('damageFactorScalings'), segments('speedFactorScalings')
    previous, factor, total = 0.0, 1.0, 0.0
    for threshold, following in damage_segments:
        if count < threshold:
            break
        total += (threshold - previous) * factor
        previous, factor = threshold, following
    total += (count - previous) * factor
    speed = 1.0
    for threshold, following in speed_segments:
        if count < threshold:
            break
        speed = following
    return {'damage_factor': max(0, total / count), 'speed_factor': max(0, speed),
            'optimal_size': int(damage_segments[0][0]) if damage_segments else 1000, 'known': True,
            'source': 'game mod / armyStackingPenaltyConfig'}


def distance(session, a, b):
    a, b = point(a), point(b)
    if not a or not b:
        return None
    dx = abs(a['x'] - b['x'])
    m = session.raw.get('states', {}).get('3', {}).get('map', {})
    if m.get('overlapX', 0) > 0 and finite(m.get('width')) and m['width'] > 0:
        dx %= m['width']
        dx = min(dx, m['width'] - dx)
    return math.hypot(dx, a['y'] - b['y'])


def owned_units(session, army):
    rows = []
    for unit in collection(army.get('u')):
        if not isinstance(unit, dict) or unit.get('cru'):
            continue
        tid = unit.get('t'); item = session.ctrl.catalog.units.get(tid, {})
        cfg = config(session, tid)
        domain = session.ctrl.catalog.domain(tid)
        terrain_class = 1 if domain == 'air' else 18 if domain == 'sea' else 0
        damage_area = numeric_map(cfg.get('damageArea', item.get('damageArea'))).get(terrain_class)
        rows.append({'unit_id': unit.get('id'), 'type_id': tid, 'name': session.ctrl.catalog.name(tid),
                     'count': unit.get('s', 1), 'domain': domain, 'hp': unit.get('hp'), 'max_hp': unit.get('mhp'),
                     'echelon_weight': damage_area,
                     'echelon': 'unknown',
                     'echelon_note': 'Bobot damageArea tersedia; label barisan memerlukan threshold frontend aktif.',
                     'attack': numeric_map(cfg.get('strength', item.get('strength'))),
                     'defense': numeric_map(cfg.get('defence', item.get('defence'))),
                     'officer_bonuses': cfg.get('armyBoostConfig', {}).get('bonuses'),
                     'stacking_class': cfg.get('stackingConfig', {}).get('class', -1),
                     'stacking_limit': cfg.get('stackingConfig', {}).get('limit')})
    return rows


def occupation_plan(session, release_morale=40):
    locs, mine = locations(session.raw), armies(session.raw, session.player_id)
    from .tactics import visible_contacts
    threats = visible_contacts(session)
    cities = []
    for city in locs.values():
        if city.get('o') != session.player_id or city.get('plv', 0) < 4:
            continue
        guards, incoming = [], []
        for aid, army in mine.items():
            if not can_capture(session, army):
                continue
            if not commands(army) and same_point(army.get('p'), city.get('c')):
                guards.append(int(aid))
            route = commands(army)
            if route and same_point(route[-1].get('tp'), city.get('c')):
                incoming.append(int(aid))
        morale = city.get('m')
        nearby = [x['army_id'] for x in threats if x.get('is_hostile') and
                  (x.get('province_id') == city['id'] or
                   (distance(session, x.get('position'), city.get('c')) or 10**9) < 80)]
        risk = 'unknown' if not finite(morale) else 'high' if morale <= 33 else 'watch' if morale < release_morale else 'stable'
        state = 'reinforce' if nearby else 'garrison_needed' if risk in ('high', 'unknown') and not guards else 'hold' if risk != 'stable' else 'eligible_for_review'
        cities.append({'city_id': city['id'], 'city_name': province_name(session.raw, city['id']),
                       'morale': morale, 'risk': risk, 'decision': state,
                       'garrison_army_ids': guards, 'incoming_army_ids': incoming, 'visible_threat_ids': nearby,
                       'release_allowed': risk == 'stable' and not nearby and len(guards) > 1,
                       'note': 'Satu garnisun kota tetap dipertahankan. Morale bukan jaminan kota bebas ancaman.'})
    return {'cities': sorted(cities, key=lambda c: (c['release_allowed'], c['morale'] if finite(c['morale']) else -1)),
            'release_morale': release_morale, 'revolt_time_predictable': False,
            'limits': ['Risiko memakai ambang kebijakan; bukan persentase spawn insurgent.',
                       'Garnisun dihitung jika benar-benar tiba di pusat kota; pasukan bergerak belum menjaga kota.']}


def optimize_stacks(session, army_ids=None, target_province=None, domain='land', preserve_garrisons=True):
    mine, locs = armies(session.raw, session.player_id), locations(session.raw)
    ids = list(dict.fromkeys(army_ids or [int(a) for a in mine]))
    if any(str(a) not in mine for a in ids):
        raise ValueError('Pilih pasukan milik sendiri.')
    target = locs.get(target_province) if target_province else None
    if target_province and not target:
        raise ValueError('Target tidak ditemukan.')
    terrain = target.get('tt') if target else 10 if domain == 'land' else 20 if domain == 'sea' else 1
    occ = occupation_plan(session)
    protected = {a for city in occ['cities'] for a in city['garrison_army_ids'][:1]} if preserve_garrisons else set()
    pool, held = [], []
    for aid in ids:
        army = mine[str(aid)]; units = owned_units(session, army)
        if not units or any(u['domain'] != domain for u in units) or army_status(army) != 'IDLE' or aid in protected:
            held.append({'army_id': aid, 'reason': 'garnisun/aktivitas/domain tidak cocok'})
            continue
        if any(not finite(u['hp']) or not finite(u['max_hp']) or u['max_hp'] <= 0 or u['hp']/u['max_hp'] < .55 for u in units):
            held.append({'army_id': aid, 'reason': 'HP rendah atau belum diketahui'})
            continue
        pool.append((aid, units))
    # Whole armies only: membership remains exact, without inventing a split RPC.
    pool.sort(key=lambda a: sum(u['hp'] for u in a[1]), reverse=True)
    candidates = []
    examined = 0
    for length in range(1, min(5, len(pool)) + 1):
        for group in itertools.combinations(pool[:18], length):
            examined += 1
            if examined > 2000:
                break
            rows = [u for _, units in group for u in units]
            count = sum(u['count'] for u in rows)
            penalty = stacking(session, count, terrain, domain)
            if not penalty['known'] or count > penalty['optimal_size']:
                continue
            if any(sum(v['count'] for v in rows if v['stacking_class'] == u['stacking_class']) > u['stacking_limit']
                   for u in rows if u['stacking_limit'] is not None):
                continue
            exposure_mass = sum(u['hp'] * (u['echelon_weight'] or 0) for u in rows)
            exposure = [{'unit_id': u['unit_id'], 'name': u['name'],
                         'relative_exposure_proxy': round(u['hp'] * (u['echelon_weight'] or 0) / exposure_mass, 3) if exposure_mass else None}
                        for u in rows]
            roles = sorted({role for u in rows for role, kind in
                            [('anti_ground', 0), ('anti_air', 1), ('anti_helicopter', 2), ('anti_naval', 4)]
                            if u['attack'].get(kind, 0) > 0 or u['defense'].get(kind, 0) > 0})
            ids_group = [a for a, _ in group]
            combat = plan_combat(session, ids_group, target_province) if target and domain == 'land' else None
            score = sum(sum(u['attack'].get(k, 0) for k in (0, 1, 2, 4)) * u['count'] * u['hp']/u['max_hp'] for u in rows)
            score *= penalty['damage_factor'] * (1 + .05 * len(roles))
            if domain == 'land' and not any(can_capture(session, mine[str(a)]) for a in ids_group):
                score *= .5
            if combat and combat['attack_estimate']:
                score = combat['attack_estimate']['lower']
            candidates.append({'army_ids': ids_group, 'unit_ids': [u['unit_id'] for u in rows],
                               'unit_count': count, 'units': [{k:v for k,v in u.items() if k not in ('attack','defense')} for u in rows],
                               'stacking': penalty, 'roles': roles, 'echelon_exposure_proxy': exposure, 'heuristic_score': round(score, 3),
                               'combat': combat, 'execution': 'queue_campaign coordinate=true setelah diperintahkan; merge aktual harus terbukti'})
        if examined > 2000:
            break
    candidates.sort(key=lambda c: (c['combat']['advance_allowed'] if c['combat'] else True, c['heuristic_score']), reverse=True)
    selected, used = [], set()
    for candidate in candidates:
        if used.isdisjoint(candidate['army_ids']):
            selected.append(candidate); used.update(candidate['army_ids'])
    return {'domain': domain, 'target_province': target_province, 'groups': selected[:8], 'held': held,
            'unassigned_army_ids': [a for a, _ in pool if a not in used], 'combinations_examined': min(examined, 2000),
            'limits': ['Pencarian kombinasi dibatasi; skor heuristik bukan optimum global atau peluang menang.',
                       'Army tidak dipecah otomatis; stack besar perlu keputusan split tersendiri.',
                       'Echelon exposure adalah proxy HP × damageArea untuk membandingkan kerentanan; bukan proporsi casualty server. Buff officer/token belum disimulasikan.']}


def air_bases(session):
    result = []
    for loc in locations(session.raw).values():
        if loc.get('o') != session.player_id:
            continue
        buildings = []
        for b in collection(loc.get('us')):
            if not isinstance(b, dict) or not finished_building(loc, b.get('id')):
                continue
            item = session.ctrl.catalog.buildings.get(b.get('id'), {})
            feature = numeric_map(item.get('features'))
            # AIRFIELD feature 8, positive live building condition and enabled status.
            if feature.get(8, 0) > 0 and b.get('e', True) and finite(b.get('c')) and b['c'] >= float(item.get('minCondition') or 0):
                buildings.append(b['id'])
        if buildings:
            result.append({'province_id': loc['id'], 'name': province_name(session.raw, loc['id']),
                           'position': loc.get('c'), 'building_ids': buildings})
    return result


def air_operations(session, province_ids=None, army_ids=None):
    locs, mine = locations(session.raw), armies(session.raw, session.player_id)
    targets = province_ids or [p['id'] for p in locs.values() if p.get('o') == session.player_id and p.get('plv', 0) >= 4]
    if any(t not in locs or locs[t].get('o') != session.player_id for t in targets):
        raise ValueError('Patroli pertahanan memilih wilayah milik sendiri.')
    ids = army_ids or list(map(int, mine))
    if any(str(a) not in mine for a in ids):
        raise ValueError('Pesawat harus milik sendiri.')
    bases = air_bases(session); rows = []
    for aid in ids:
        army = mine[str(aid)]; units = owned_units(session, army)
        if not units or not all(u['domain'] == 'air' for u in units):
            continue
        configs = [config(session, u['type_id']).get('airplaneConfig', {}) for u in units]
        flight = min((float(c['maxFlightTime']) for c in configs if finite(c.get('maxFlightTime')) and c['maxFlightTime'] > 0), default=None)
        refuel = max((float(c['refuelTime']) for c in configs if finite(c.get('refuelTime'))), default=None)
        radius = army.get('patrolRadius')
        operational_range = army.get('r')
        base_ref = army.get('aip', {}).get('airField')
        base_id = int(base_ref[1:]) if isinstance(base_ref, str) and base_ref.startswith('p') and base_ref[1:].isdigit() else None
        current_base = next((b for b in bases if b['province_id'] == base_id), None)
        if current_base is None and not commands(army):
            current_base = next((b for b in bases if same_point(army.get('p'), b['position'])), None)
        reachable = []
        for tid in targets:
            for base in bases:
                d = distance(session, base['position'], locs[tid].get('c'))
                if d is not None and finite(operational_range) and d <= operational_range:
                    reachable.append({'target_province': tid, 'base_province': base['province_id'], 'distance': round(d, 2),
                                      'covers_city_center': True, 'is_current_base': current_base == base})
        reachable.sort(key=lambda x: (not x['is_current_base'], x['distance']))
        scale = session.raw.get('states', {}).get('12', {}).get('timeScale')
        rows.append({'army_id': aid, 'status': army_status(army), 'units': units,
                     'base_province': current_base['province_id'] if current_base else None,
                     'operational_range': operational_range, 'patrol_radius': radius,
                     'flight_budget_real_hours': flight * scale / 3600 if flight and finite(scale) else None,
                     'refuel_real_minutes': refuel * scale / 60 if refuel is not None and finite(scale) else None,
                     'current_refuel_hours_remaining': remaining_hours(session.raw, army.get('at')) if army_status(army) == 'WAITING' else None,
                     'current_flight_hours_remaining': remaining_hours(session.raw, army.get('aip', {}).get('maxFlightTime')),
                     'reachable_targets': reachable[:12],
                     'decision': 'maintain_current_order' if commands(army) else 'patrol_candidate' if current_base and reachable else 'base_or_config_review'})
    return {'bases': bases, 'aircraft': rows, 'target_province_ids': targets,
            'limits': ['Jarak geometris hanya pemeriksaan range; ETA rute memakai hasil server.',
                       'Patrol dapat menyerang lawan dalam lingkaran; area netral tidak otomatis diizinkan.',
                       'Rotasi hanya boleh mengganti pesawat setelah pengganti siap; timer sendiri bukan bukti overlap tanpa celah.']}


def simulate_options(session, scenarios):
    rows = []
    for item in scenarios:
        request = Scenario.model_validate(item)
        result = plan_combat(session, request.army_ids, request.target_province)
        mine = armies(session.raw, session.player_id)
        positions = [distance(session, mine[str(a)].get('p'), locations(session.raw)[request.target_province].get('c')) for a in request.army_ids]
        timings = [remaining_hours(session.raw, commands(mine[str(a)])[-1].get('at')) for a in request.army_ids
                   if commands(mine[str(a)]) and same_point(commands(mine[str(a)])[-1].get('tp'), locations(session.raw)[request.target_province].get('c'))]
        rows.append({'label': request.label, 'target_province': request.target_province,
                     'army_ids': request.army_ids, 'wait_hours': request.wait_hours,
                     'route_distance_estimate': round(sum(d for d in positions if d is not None), 2),
                     'observed_arrival_real_hours': max(timings) if timings and all(t is not None for t in timings) else None,
                     'future_state_projected': False, 'combat': result,
                     'note': 'Skenario menunggu memakai kondisi sekarang; musuh, heal, dan resource masa depan tidak diasumsikan.'})
    rows.sort(key=lambda r: (not r['combat']['advance_allowed'], bool(r['combat']['unknowns']),
                             -(r['combat']['conservative_damage_ratio'] or 0), r['wait_hours'], r['route_distance_estimate']))
    return {'scenarios': rows, 'recommended_label': rows[0]['label'] if rows and rows[0]['combat']['advance_allowed'] else None,
            'limits': ['Perbandingan estimasi saat ini; bukan simulasi peluang menang, casualty pasti, atau perubahan fog masa depan.']}


def definitions():
    def call(fn, **kwargs):
        from api import actions
        from .game_session import current_session
        actions.refresh()
        return fn(current_session(), **kwargs)
    return [
        {'name': 'configure_full_auto', 'description': 'Aktifkan full auto 0-8 jam atau hentikan; hanya jika pemilik jelas meminta full auto. Default 8 jam, reasoning high. Tidak memperpanjang sesi aktif.', 'fn': configure_full_auto, 'parameters': {'hours': {'type': 'number'}, 'enabled': {'type': 'boolean'}}, 'mutates': True},
        {'name': 'get_full_auto_status', 'description': 'Baca deadline full auto, keputusan terakhir dan penugasan semua pasukan. Read-only.', 'fn': get_full_auto_status, 'parameters': {}, 'mutates': False},
        {'name': 'air_patrol', 'description': 'Perintah patroli pertahanan udara terjaga; hanya setelah pengguna meminta tindakan atau lewat queue full auto.', 'fn': air_patrol, 'parameters': {'army_id': {'type': 'integer'}, 'target_province': {'type': 'integer'}}, 'mutates': True},
        {'name': 'air_relocate', 'description': 'Relokasi pesawat ke pangkalan sendiri operasional, memakai command udara resmi. Hanya setelah diminta.', 'fn': air_relocate, 'parameters': {'army_id': {'type': 'integer'}, 'target_province': {'type': 'integer'}}, 'mutates': True},
        {'name': 'optimize_army_stacks', 'description': 'Susun grup dari army sendiri berdasarkan HP, terrain, stacking server, echelon dan target. Menjaga garnisun; read-only.', 'fn': lambda **kw: call(optimize_stacks, **kw), 'argument_model': StackArguments, 'mutates': False},
        {'name': 'get_air_operations_plan', 'description': 'Pangkalan operasional, range, patroli pertahanan, refuel dan flight budget nyata. Read-only.', 'fn': lambda **kw: call(air_operations, **kw), 'argument_model': AirArguments, 'mutates': False},
        {'name': 'get_occupation_plan', 'description': 'Risiko insurgency, garnisun yang sudah tiba, reinforcement dan kelayakan pelepasan kota. Read-only.', 'fn': lambda **kw: call(occupation_plan, **kw), 'argument_model': OccupationArguments, 'mutates': False},
        {'name': 'simulate_strategy_options', 'description': 'Bandingkan sampai enam skenario army/target/waktu tunggu dengan intel sah. Estimasi, bukan kepastian menang.', 'fn': lambda **kw: call(simulate_options, **kw), 'argument_model': SimulationArguments, 'mutates': False},
    ]


def air_readiness(session, kind, args):
    army = armies(session.raw, session.player_id).get(str(args['army_id']))
    target = locations(session.raw).get(args['target_province'])
    if not army or not target or target.get('o') != session.player_id:
        return 'failed', 'Tujuan udara harus wilayah sendiri dan pesawat milik sendiri.'
    units = owned_units(session, army)
    if not units or not all(u['domain'] == 'air' and finite(u['hp']) and finite(u['max_hp']) and u['max_hp'] > 0 and u['hp']/u['max_hp'] >= .55 for u in units):
        return 'waiting_policy', 'Pesawat belum sehat atau identitas belum diketahui.'
    if commands(army) or army.get('fs'):
        return 'waiting_slot', 'Pesawat masih bertugas/refuel.'
    if kind == 'air_relocate':
        if args['target_province'] not in {b['province_id'] for b in air_bases(session)}:
            return 'waiting_prerequisite', 'Pangkalan tujuan belum operasional.'
        return 'ready', ''
    plan = air_operations(session, [args['target_province']], [args['army_id']])
    row = plan['aircraft'][0] if plan['aircraft'] else {}
    if not row.get('base_province') or not any(r['is_current_base'] for r in row.get('reachable_targets', [])):
        return 'waiting_prerequisite', 'Pangkalan/range patroli belum sesuai.'
    radius = row.get('patrol_radius')
    if not finite(radius) or radius <= 0 or row.get('flight_budget_real_hours') is None:
        return 'waiting_observation', 'Radius atau konfigurasi penerbangan belum diketahui.'
    from .tactics import visible_contacts
    for contact in visible_contacts(session):
        d = distance(session, contact.get('position'), target.get('c'))
        if not contact.get('is_hostile') and d is not None and d <= radius:
            return 'waiting_diplomacy', 'Ada kontak nonmusuh dalam area patroli.'
    # Keep the complete patrol disk in owned land, not just its centre.
    for loc in locations(session.raw).values():
        d = distance(session, loc.get('c'), target.get('c'))
        if loc.get('o') != session.player_id and d is not None and d <= radius + 20:
            return 'waiting_policy', 'Area patroli dekat wilayah nonmilik; perlu rencana khusus.'
    return 'ready', ''


def execute_air(army_id: int, target_province: int, mode: str):
    from api import actions
    from .game_session import current_session
    from .protocol import action_result
    actions.refresh(); session = current_session()
    kind = 'air_patrol' if mode == 'patrol' else 'air_relocate'
    state, detail = air_readiness(session, kind, {'army_id': army_id, 'target_province': target_province})
    if state != 'ready':
        raise ValueError(detail)
    army = armies(session.raw, session.player_id)[str(army_id)]
    target = locations(session.raw)[target_province]
    cmd = {'@c': 'pc', 'targetPos': dict(target['c']), 'approaching': True,
           'type': 'Guard' if mode == 'patrol' else 'AirplaneRelocation',
           'airField': f"p{target_province}" if mode == 'relocate' else army.get('aip', {}).get('airField') or f"p{air_operations(session, [target_province], [army_id])['aircraft'][0]['base_province']}"}
    sub = {'@c': 'ultshared.action.UltArmyAction', 'language': 'en',
           'armies': ['java.util.LinkedList', [session.ctrl._army_order(army, [cmd])]]}
    response = session.ctrl._send_sub_action(sub)
    return {'success': action_result(response, response.get('_request_id')) == 1,
            'army_id': army_id, 'target_province': target_province, 'mode': mode}


def air_patrol(army_id: int, target_province: int):
    return execute_air(army_id, target_province, 'patrol')


def air_relocate(army_id: int, target_province: int):
    return execute_air(army_id, target_province, 'relocate')



def configure_full_auto(hours: float = 8.0, enabled: bool = True):
    """Persist bounded owner authorization; Telegram scheduler picks it up."""
    from .agent_tools import current_execution, _on_loop
    from .game_session import current_session
    import time
    if not 0 < hours <= 8:
        raise ValueError('Sesi full auto harus lebih dari 0 sampai 8 jam.')
    execution, session = current_execution(), current_session()
    def save():
        store = execution.runtime.store
        current = store.preference('overnight_control', {})
        if not enabled:
            current.update(enabled=False, reason='owner_stopped')
            store.set_preference('overnight_control', current)
            return {'enabled': False, 'note': 'Aksi yang sudah dikirim tetap dipantau.'}
        if current.get('enabled') and current.get('mode') == 'full_auto' and current.get('game_id') == session.game_id and time.time() < current.get('deadline', 0):
            return dict(current, note='Sesi masih aktif; deadline tidak diperpanjang otomatis.')
        now = time.time()
        config = {'enabled': True, 'game_id': session.game_id, 'player_id': session.player_id,
                  'started_at': now, 'deadline': now + hours * 3600, 'mode': 'full_auto',
                  'next_check': 0, 'reasoning_effort': 'high'}
        store.set_preference('overnight_control', config)
        store.set_preference(f'commander_paused:{session.game_id}', False)
        return dict(config, note='Scheduler aktif di bot Telegram. Evaluasi 5 menit, ringkasan 30 menit, stop /fullauto off.')
    return _on_loop(execution.loop, save)


def get_full_auto_status():
    from .agent_tools import current_execution, _on_loop
    from .game_session import current_session
    execution, session = current_execution(), current_session()
    def read():
        store = execution.runtime.store
        return {'control': store.preference('overnight_control', {}),
                'last_evaluation': store.preference(f'full_auto_last:{session.game_id}', {})}
    return _on_loop(execution.loop, read)
