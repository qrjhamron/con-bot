"""Persistent multi-action queue: acceptance and completion are separate states."""
import time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .commander_state import (Budget, locations, armies, item_costs, resource_lines,
                              queue_entries, busy_construction, finished_building, unit_totals, unit_inventory)
from .protocol import collection, commands, same_point
from .combat import CombatPolicy

TERMINAL = {'completed', 'failed', 'cancelled', 'expired'}
IN_FLIGHT = {'accepted', 'dispatching', 'outcome_unknown'}


class Action(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    kind: Literal['build', 'produce', 'research', 'move', 'conquer', 'group_move', 'group_conquer', 'air_patrol', 'air_relocate', 'naval_move']
    item_id: int | None = Field(default=None, gt=0)
    city_id: int | None = Field(default=None, gt=0)
    army_id: int | None = Field(default=None, gt=0)
    target_province: int | None = Field(default=None, gt=0)
    target_player_id: int | None = Field(default=None, gt=0)
    army_ids: list[int] | None = Field(default=None, min_length=1, max_length=20)
    unit_ids: list[int] | None = Field(default=None, min_length=1, max_length=500)
    protected_city_ids: list[int] = Field(default_factory=list, max_length=500)
    combat_policy: CombatPolicy | None = None
    is_rally: bool = False
    require_merged: bool = False

    @model_validator(mode='after')
    def required_targets(self):
        fields = {'build': {'item_id', 'city_id'}, 'produce': {'item_id', 'city_id'},
                  'research': {'item_id'}, 'move': {'army_id', 'target_province'},
                  'conquer': {'army_id', 'target_province'},
                  'air_patrol': {'army_id', 'target_province'}, 'air_relocate': {'army_id', 'target_province'},
                  'naval_move': {'army_id', 'target_province'},
                  'group_move': {'army_ids', 'unit_ids', 'target_province'},
                  'group_conquer': {'army_ids', 'unit_ids', 'target_province'}}[self.kind]
        supplied = {k for k in ('item_id', 'city_id', 'army_id', 'target_province', 'target_player_id', 'army_ids', 'unit_ids') if getattr(self, k) is not None}
        if supplied != fields and not (self.kind in ('conquer', 'group_conquer') and supplied == fields | {'target_player_id'}):
            raise ValueError('Target harus sesuai jenis aksi.')
        if self.require_merged and not self.kind.startswith('group_'):
            raise ValueError('Merge policy hanya untuk kelompok.')
        if self.is_rally and self.kind != 'group_move':
            raise ValueError('Rally hanya untuk group_move.')
        if self.combat_policy is not None and self.kind not in ('conquer', 'group_conquer'):
            raise ValueError('Combat policy hanya untuk conquer.')
        if self.protected_city_ids and not self.kind.startswith('group_'):
            raise ValueError('Protected cities hanya untuk koordinasi kelompok.')
        if any(type(n) is not int or n <= 0 for n in (self.army_ids or []) + self.protected_city_ids):
            raise ValueError('ID army dan kota harus positif.')
        if any(type(n) is not int or n == 0 for n in self.unit_ids or []):
            raise ValueError('ID unit harus integer bukan nol.')
        return self


class QueueArguments(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    action: Action
    depends_on: list[int] = Field(default_factory=list, max_length=20)
    quantity: int = Field(default=1, ge=1, le=20)


def action_args(action):
    values = action.model_dump(exclude_none=True)
    values.pop('kind')
    if not values.get('require_merged'):
        values.pop('require_merged', None)
    if not values.get('is_rally'):
        values.pop('is_rally', None)
    if not values.get('protected_city_ids'):
        values.pop('protected_city_ids', None)
    return values


def validate_target(session, kind, args):
    catalog = session.ctrl.catalog
    pid = session.player_id
    if kind in ('air_patrol', 'air_relocate'):
        if str(args['army_id']) not in armies(session.raw, pid) or locations(session.raw).get(args['target_province'], {}).get('o') != pid:
            raise ValueError('Pesawat atau target udara tidak sesuai akun.')
        return
    if kind == 'naval_move':
        army = armies(session.raw, pid).get(str(args['army_id']), {})
        target = locations(session.raw).get(args['target_province'], {})
        if not army or 'Sea' not in target.get('@c', '') or target.get('tt') not in (18, 19, 20, 22):
            raise ValueError('Naval move memerlukan armada sendiri dan titik laut.')
        return
    if kind.startswith('group_'):
        from .coordination import resolve_group
        resolve_group(session, args)
        target = locations(session.raw).get(args['target_province'])
        if not target or (kind == 'group_move' and target.get('o') != pid):
            raise ValueError('Tujuan kelompok tidak dikenal atau rally bukan wilayah sendiri.')
        return
    if kind in ('build', 'produce'):
        city = locations(session.raw).get(args['city_id'])
        if not city or city.get('o') != pid or city.get('plv', 0) < 4:
            raise ValueError('Kota bukan milik pemain aktif.')
        table = catalog.buildings if kind == 'build' else catalog.units
        if args['item_id'] not in table:
            raise ValueError('Item tidak dikenal pada katalog resmi.')
    elif kind == 'research':
        if args['item_id'] not in catalog.researches:
            raise ValueError('Riset tidak dikenal pada katalog resmi.')
    else:
        army = armies(session.raw, pid).get(str(args['army_id']))
        target = locations(session.raw).get(args['target_province'])
        if not army or not target or (kind == 'move' and target.get('o') != pid):
            raise ValueError('Pasukan harus milik sendiri; move memerlukan tujuan sendiri, conquer memerlukan target yang dikenal.')
        if kind == 'conquer':
            from .tactics import can_capture, point
            if not can_capture(session, army) or not point(target.get('c')):
                raise ValueError('Conquer memerlukan pasukan darat hidup yang bisa menguasai wilayah dan koordinat target.')


def cost_for(session, node):
    if node['kind'] in ('move', 'conquer', 'group_move', 'group_conquer', 'air_patrol', 'air_relocate', 'naval_move'):
        return {}
    return item_costs(session.ctrl.catalog.items.get(node['args']['item_id'], {}))


def readiness(session, node, all_nodes):
    args, kind = node['args'], node['kind']
    if kind.startswith('group_'):
        if node['player_id'] != session.player_id:
            return 'failed', 'Identitas pemain berubah.'
        for other in all_nodes:
            if other['id'] == node['id'] or other['state'] != 'outcome_unknown':
                continue
            if set(args.get('unit_ids', [])).intersection(other['args'].get('unit_ids', [])) or set(args.get('army_ids', [])).intersection(
                    other['args'].get('army_ids', []) + ([other['args']['army_id']] if other['args'].get('army_id') else [])):
                return 'waiting_observation', 'Ada hasil perintah kelompok sebelumnya yang belum diketahui.'
        from .coordination import group_readiness
        return group_readiness(session, node)
    try:
        validate_target(session, kind, args)
    except ValueError as exc:
        return 'failed', str(exc)
    if node['player_id'] != session.player_id:
        return 'failed', 'Identitas pemain berubah.'
    for other in all_nodes:
        if other['id'] == node['id'] or other['state'] != 'outcome_unknown':
            continue
        if kind in ('move', 'conquer') and other['kind'].startswith('group_'):
            own_ids = {u.get('id') for u in collection(armies(session.raw, session.player_id).get(str(args['army_id']), {}).get('u')) if isinstance(u, dict)}
            if args['army_id'] in other['args'].get('army_ids', []) or own_ids.intersection(other['args'].get('unit_ids', [])):
                return 'waiting_observation', 'Hasil perintah kelompok pada unit ini belum diketahui.'
        same_slot = ((kind == 'research' and other['kind'] == 'research') or
                     (kind == other['kind'] and args.get('city_id') and args.get('city_id') == other['args'].get('city_id')) or
                     (kind in ('move', 'conquer', 'air_patrol', 'air_relocate', 'naval_move') and other['kind'] in ('move', 'conquer', 'air_patrol', 'air_relocate', 'naval_move') and args.get('army_id') == other['args'].get('army_id')))
        if same_slot:
            return 'waiting_observation', 'Ada hasil aksi sebelumnya yang belum diketahui pada target ini.'
    raw, catalog = session.raw, session.ctrl.catalog
    if kind in ('air_patrol', 'air_relocate'):
        from .advanced_plans import air_readiness
        return air_readiness(session, kind, args)
    if kind == 'naval_move':
        army = armies(raw, session.player_id)[str(args['army_id'])]
        units = collection(army.get('u'))
        if commands(army) or army.get('fs'):
            return 'waiting_slot', 'Armada masih bertugas atau bertempur.'
        if not units or not all(isinstance(u, dict) and catalog.domain(u.get('t',0)) == 'sea' and
                               isinstance(u.get('hp'), (int,float)) and isinstance(u.get('mhp'), (int,float)) and
                               u['mhp'] > 0 and u['hp']/u['mhp'] >= .55 for u in units):
            return 'waiting_policy', 'Armada belum sehat atau identitas tidak sesuai.'
        return 'ready', ''
    if kind in ('build', 'produce'):
        city = locations(raw)[args['city_id']]
        if kind == 'build' and busy_construction(city, catalog):
            return 'waiting_slot', 'Pembangunan sebelumnya masih berjalan.'
        if kind == 'produce' and queue_entries(city, 'produce'):
            return 'waiting_slot', 'Produksi sebelumnya masih berjalan.'
        props = raw.get('states', {}).get('3', {}).get('properties', {}).get(str(args['city_id']), {})
        key = 'queueableUpgrades' if kind == 'build' else 'queueableProductions'
        available = [t.get('id') if kind == 'build' else t.get('unit', {}).get('t')
                     for t in collection(props.get(key)) if isinstance(t, dict)]
        if args['item_id'] not in available:
            return 'waiting_prerequisite', 'Template item belum tersedia di kota ini.'
    elif kind == 'research':
        state = raw.get('states', {}).get('23', {})
        slots = state.get('researchSlots')
        if not isinstance(slots, int) or slots <= len([r for r in collection(state.get('currentResearches')) if isinstance(r, dict)]):
            return 'waiting_slot', 'Slot riset belum tersedia.'
        if args['item_id'] not in {r['id'] for r in catalog.available_research(raw, session.player_id)}:
            return 'waiting_prerequisite', 'Hari, doctrine, atau prasyarat riset belum sesuai.'
    else:
        army = armies(raw, session.player_id)[str(args['army_id'])]
        if commands(army) or army.get('fs', 0):
            return 'waiting_slot', 'Pasukan memiliki perintah atau sedang bertempur.'
        if army.get('a') or not collection(army.get('u')) or not all(
            isinstance(u, dict) and catalog.domain(u.get('t', 0)) == 'land' for u in collection(army.get('u'))
        ):
            return 'failed', 'Penempatan pertahanan otomatis hanya untuk pasukan darat.'
        if kind == 'conquer':
            from .tactics import at_war
            owner = locations(raw)[args['target_province']].get('o')
            if owner != session.player_id:
                if args.get('target_player_id') and owner != args['target_player_id']:
                    return 'waiting_policy', 'Pemilik target berubah; perlu rencana baru untuk negara tersebut.'
                if type(owner) is not int or owner <= 0 or not at_war(raw, session.player_id, owner):
                    return 'waiting_diplomacy', 'Target belum berada dalam perang; tidak otomatis mendeklarasikan perang.'
        if node['source'] != 'manual' and kind == 'move':
            from .commander import defensive_moves
            if args not in defensive_moves(session):
                return 'waiting_policy', 'Penempatan berubah; pertahankan garrison dan hindari kota rawan.'
    if kind == 'conquer' and node['source'] != 'manual':
        from .advanced_plans import occupation_plan
        if any(args['army_id'] in city['garrison_army_ids'] and len(city['garrison_army_ids']) <= 1
               for city in occupation_plan(session)['cities']):
            return 'waiting_policy', 'Garnisun terakhir tidak boleh ditarik oleh full auto.'
    if kind == 'conquer':
        from .combat import plan_combat
        combat = plan_combat(session, [args['army_id']], args['target_province'], args.get('combat_policy'))
        if not combat['advance_allowed']:
            return 'waiting_combat', combat['decision'] + ': ' + ' '.join(combat['reasons'])
    if kind in ('move', 'conquer'):
        return 'ready', ''
    resources = resource_lines(raw, session.player_id)
    costs = cost_for(session, node)
    shortages = Budget(resources).shortages(costs)
    if shortages:
        return 'waiting_resources', str(shortages)
    if kind in ('produce', 'build'):
        future_upkeep = {}
        assets = [node] + [n for n in all_nodes if n['id'] != node['id'] and n['state'] == 'accepted' and
                          n['kind'] in ('produce', 'build')]
        for asset in assets:
            item = catalog.items.get(asset['args']['item_id'], {})
            daily = item.get('dailyCosts', '')
            upkeep = item_costs({'costs': daily}) if daily else {}
            if upkeep is None:
                return 'waiting_resources', 'Biaya pemeliharaan belum diketahui.'
            for name, amount in upkeep.items():
                future_upkeep[name] = future_upkeep.get(name, 0) + amount
        scale = raw.get('states', {}).get('12', {}).get('timeScale')
        if future_upkeep and (not isinstance(scale, (int, float)) or scale <= 0):
            return 'waiting_resources', 'Kecepatan game belum diketahui untuk forecast pemeliharaan.'
        for name, daily in future_upkeep.items():
            line = resources.get(name)
            if line is None:
                return 'waiting_resources', f'Saldo pemeliharaan {name} belum diketahui.'
            net = line['net_per_day'] - daily
            after = line['amount'] - (costs or {}).get(name, 0) * 1.25 + min(0, net) * 4 / (24 * scale)
            if after < Budget(resources).reserves.get(name, 0):
                return 'waiting_resources', f'Cadangan {name} tidak cukup untuk forecast pemeliharaan 4 jam.'
    return 'ready', ''


def observed(session, node):
    """Return completed, accepted, or None; elapsed ETA alone proves nothing."""
    kind, args, baseline = node['kind'], node['args'], node.get('baseline') or {}
    raw = session.raw
    if kind.startswith('group_'):
        from .coordination import group_observed
        return group_observed(session, node)
    if kind in ('build', 'produce'):
        city = locations(raw).get(args['city_id'], {})
        if city.get('o') != session.player_id:
            return None
        if kind == 'build' and finished_building(city, args['item_id']):
            return 'completed'
        matching = [p for p in queue_entries(city, kind) if
                    (p.get('u', {}).get('id') if kind == 'build' else p.get('u', {}).get('unit', {}).get('t')) == args['item_id']]
        if matching and baseline and any(p.get('s', 0) >= baseline.get('game_time', float('inf')) for p in matching):
            return 'accepted'
        if kind == 'produce' and baseline and not matching:
            # Global counts distinguish production from existing armies arriving in a city.
            before = baseline.get('unit_totals', {}).get(str(args['item_id']), 0)
            now = unit_totals(raw, session.player_id).get(str(args['item_id']), 0)
            old_units = baseline.get('units', {})
            current_units = unit_inventory(raw, session.player_id)
            future_id = baseline.get('production_unit_id')
            if future_id is not None and str(future_id) not in old_units and \
                    current_units.get(str(future_id), {}).get('item_id') == args['item_id']:
                return 'completed'
            at_city = {uid: u for uid, u in current_units.items() if u['item_id'] == args['item_id'] and
                       u['province_id'] == args['city_id'] and u['stationary']}
            new_here = any(uid not in old_units for uid in at_city)
            relevant_old = {uid for uid, u in old_units.items() if u['item_id'] == args['item_id']}
            grew_here = (bool(old_units) and relevant_old.issubset(current_units) and any(
                uid in old_units and u['count'] > old_units[uid]['count'] for uid, u in at_city.items()))
            if 'units' in baseline and now > before and (new_here or grew_here):
                return 'completed'
    elif kind == 'research':
        state = raw.get('states', {}).get('23', {})
        if str(args['item_id']) in state.get('completedResearches', {}):
            return 'completed'
        if baseline and any(r.get('researchTypeID', r.get('researchID')) == args['item_id'] and
                            r.get('startTime', 0) >= baseline.get('game_time', float('inf'))
                            for r in collection(state.get('currentResearches')) if isinstance(r, dict)):
            return 'accepted'
    elif kind in ('air_patrol', 'air_relocate'):
        army = armies(raw, session.player_id).get(str(args['army_id']), {})
        target = locations(raw).get(args['target_province'], {})
        matching = [c for c in commands(army) if c.get('@c') == 'pc' and
                    c.get('type') == ('Guard' if kind == 'air_patrol' else 'AirplaneRelocation') and
                    same_point(c.get('targetPos'), target.get('c'))]
        if kind == 'air_patrol' and matching and matching[-1].get('approaching') is False:
            return 'completed'
        if kind == 'air_relocate' and not commands(army) and same_point(army.get('p'), target.get('c')) and army.get('aip', {}).get('airField') == f"p{args['target_province']}":
            return 'completed'
        if baseline and matching:
            return 'accepted'
    else:
        if kind == 'conquer' and locations(raw).get(args['target_province'], {}).get('o') == session.player_id:
            return 'completed'
        army = armies(raw, session.player_id).get(str(args['army_id']), {})
        target = locations(raw).get(args['target_province'], {})
        if kind == 'move' and target.get('o') != session.player_id:
            return None
        if kind in ('move', 'naval_move') and same_point(army.get('p'), target.get('c')) and not commands(army):
            return 'completed'
        if baseline and any(c.get('@c') == 'gc' and same_point(c.get('tp'), target.get('c')) for c in commands(army)):
            return 'accepted'
    return None


def reconcile(session, store, game_id):
    for node in store.commander_nodes(game_id):
        if node['state'] in TERMINAL or node['player_id'] != session.player_id:
            continue
        if node['kind'] == 'produce' and node['baseline'] and node['state'] in IN_FLIGHT:
            city = locations(session.raw).get(node['args']['city_id'], {})
            matches = [p for p in queue_entries(city, 'produce') if
                       p.get('u', {}).get('unit', {}).get('t') == node['args']['item_id'] and
                       p.get('s', 0) >= node['baseline'].get('game_time', float('inf'))]
            if len(matches) == 1 and not node['baseline'].get('production_unit_id'):
                node['baseline']['production_unit_id'] = matches[0].get('u', {}).get('unit', {}).get('id')
                store.set_commander_node(node['id'], node['state'], node['detail'], node['baseline'])
        state = observed(session, node)
        if state == 'completed' or (state == 'accepted' and node['state'] == 'outcome_unknown'):
            store.set_commander_node(node['id'], state, 'Kondisi teramati di state game; sumber perubahan bisa manual.')
        elif node['state'] in IN_FLIGHT:
            if node['kind'] in ('move', 'conquer') and str(node['args']['army_id']) not in armies(session.raw, session.player_id):
                store.set_commander_node(node['id'], 'failed', 'ID pasukan tidak lagi teramati; bisa hilang atau bergabung.')
                continue
            target = locations(session.raw).get(node['args'].get('city_id', node['args'].get('target_province')))
            if node['kind'] not in ('conquer', 'group_conquer') and target and target.get('o') != session.player_id:
                store.set_commander_node(node['id'], 'failed', 'Target tidak lagi milik pemain.')


def node_tool(node):
    args = node['args']
    if node['kind'].startswith('group_'):
        return 'move_army_group', {'unit_ids': args['unit_ids'], 'target_province': args['target_province'],
                                 'combat_policy': args.get('combat_policy'),
                                 'protected_city_ids': args.get('protected_city_ids', []),
                                 'target_player_id': args.get('target_player_id'), 'is_rally': args.get('is_rally', False), 'require_merged': args.get('require_merged', False)}
    return {
        'build': ('build_building', {'city_id': args.get('city_id'), 'building_type': str(args.get('item_id'))}),
        'produce': ('produce_unit', {'city_id': args.get('city_id'), 'unit_type': str(args.get('item_id'))}),
        'research': ('start_research', {'research_id': args.get('item_id')}),
        'air_patrol': ('air_patrol', {'army_id': args.get('army_id'), 'target_province': args.get('target_province')}),
        'air_relocate': ('air_relocate', {'army_id': args.get('army_id'), 'target_province': args.get('target_province')}),
        'naval_move': ('move_army', {'army_id': args.get('army_id'), 'target_province': args.get('target_province')}),
        'move': ('move_army', {'army_id': args.get('army_id'), 'target_province': args.get('target_province')}),
        'conquer': ('move_army', {'army_id': args.get('army_id'), 'target_province': args.get('target_province')}),
    }[node['kind']]


async def drain(executor, store, game_id, runtime, config=None, limit=3):
    from .agent_tools import TaskStop
    session = executor.session(game_id)
    report = []
    config = config or {}
    for node in store.commander_nodes(game_id):
        if len(report) >= limit or store.preference(f'commander_paused:{game_id}', False):
            break
        if node['state'] in TERMINAL | IN_FLIGHT:
            continue
        if node['source'] != 'manual' and (not config.get('enabled') or time.time() >= config.get('deadline', 0)
                                         or node['source'] != f"auto:{config.get('started_at')}"):
            store.set_commander_node(node['id'], 'expired', 'Izin kontrol otomatis telah berakhir.')
            continue
        deps = [store.commander_node(i, game_id) for i in node['dependencies']]
        if any(d is None or d['state'] in ('failed', 'cancelled', 'expired') for d in deps):
            store.set_commander_node(node['id'], 'failed', 'Dependency gagal atau dibatalkan.')
            continue
        if any(d['state'] != 'completed' for d in deps):
            store.set_commander_node(node['id'], 'waiting_prerequisite', 'Menunggu dependency benar-benar selesai.')
            continue
        state, detail = readiness(session, node, store.commander_nodes(game_id))
        if state != 'ready':
            store.set_commander_node(node['id'], state, detail)
            continue
        runtime.checkpoint()
        clock = float(session.raw.get('timeStamp') or 0)
        import math
        if not math.isfinite(clock) or clock <= 0:
            store.set_commander_node(node['id'], 'waiting_observation', 'Waktu server belum tersedia.')
            continue
        baseline = {'game_time': clock,
                    'unit_totals': unit_totals(session.raw, session.player_id),
                    'units': unit_inventory(session.raw, session.player_id)}
        store.set_commander_node(node['id'], 'dispatching', baseline=baseline)

        guard_nodes = store.commander_nodes(game_id)

        def guard(live, sub, expected=node):
            kind = sub.get('@c', '').rsplit('.', 1)[-1]
            args = expected['args']
            allowed = False
            if expected['kind'] in ('build', 'produce'):
                mode = 1 if expected['kind'] == 'build' else 2
                iid = sub.get('upgrade', {}).get('id') if mode == 1 else sub.get('upgrade', {}).get('unit', {}).get('t')
                allowed = (kind == 'UltUpdateProvinceAction' and sub.get('mode') == mode and
                           collection(sub.get('provinceIDs')) == [args['city_id']] and iid == args['item_id'])
            elif expected['kind'] == 'research':
                allowed = kind == 'UltResearchAction' and not sub.get('cancel') and sub.get('researchID') == args['item_id']
            elif expected['kind'].startswith('group_'):
                from .coordination import resolve_group
                entries = collection(sub.get('armies'))
                target = locations(live.raw).get(args['target_province'], {})
                try:
                    current_ids = {a['id'] for a in resolve_group(live, args)}
                except ValueError:
                    current_ids = set()
                sent_units = {u.get('id') for a in entries for u in collection(a.get('u')) if isinstance(u, dict)}
                allowed = (kind == 'UltArmyAction' and current_ids and len(entries) == len(current_ids) and
                           {a.get('id') for a in entries} == current_ids and sent_units == set(args['unit_ids']) and
                           all(a.get('o') == live.player_id and len(commands(a)) == 1 and
                               commands(a)[0].get('@c') == 'gc' and same_point(commands(a)[0].get('tp'), target.get('c')) for a in entries))
            else:
                entries = collection(sub.get('armies'))
                target = locations(live.raw).get(args['target_province'], {})
                allowed = (kind == 'UltArmyAction' and len(entries) == 1 and entries[0].get('id') == args['army_id'] and
                           len(commands(entries[0])) == 1 and commands(entries[0])[0].get('@c') == ('pc' if expected['kind'].startswith('air_') else 'gc') and
                           same_point(commands(entries[0])[0].get('targetPos') if expected['kind'].startswith('air_') else commands(entries[0])[0].get('tp'), target.get('c')) and
                           (not expected['kind'].startswith('air_') or commands(entries[0])[0].get('type') == ('Guard' if expected['kind'] == 'air_patrol' else 'AirplaneRelocation')))
            if not allowed or readiness(live, expected, guard_nodes)[0] != 'ready':
                raise TaskStop('rejected', 'State, slot, atau budget berubah; rencana ditahan sebelum dikirim.')

        runtime.action_guard = guard
        tool, arguments = node_tool(node)
        before_steps = len(store.steps(runtime.task_id))
        try:
            result = await executor.execute(game_id, tool, arguments, runtime)
        finally:
            runtime.action_guard = None
        if result.ok:
            if node['kind'] == 'produce':
                city = locations(session.raw).get(node['args']['city_id'], {})
                matches = [p for p in queue_entries(city, 'produce') if
                           p.get('u', {}).get('unit', {}).get('t') == node['args']['item_id']]
                if len(matches) == 1:
                    baseline['production_unit_id'] = matches[0].get('u', {}).get('unit', {}).get('id')
            store.set_commander_node(node['id'], 'accepted', 'Perintah terverifikasi; penyelesaian masih dipantau.', baseline)
            report.append({'id': node['id'], 'state': 'accepted', 'kind': node['kind']})
        else:
            code = (result.error or {}).get('code')
            if code in ('cancelled', 'limited') or (code == 'rejected' and len(store.steps(runtime.task_id)) == before_steps):
                store.set_commander_node(node['id'], 'queued', 'Ditahan sebelum pengiriman.')
            else:
                unknown = code in ('interrupted', 'unknown')
                state = 'outcome_unknown' if unknown else 'failed'
                store.set_commander_node(node['id'], state, str(result.error))
                report.append({'id': node['id'], 'state': state, 'kind': node['kind']})
            break
    return report
