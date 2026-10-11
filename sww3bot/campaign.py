"""Explicit multi-army routes; conquest goals depend on actual ownership."""
import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .commander_state import armies, locations
from .commander_queue import validate_target, TERMINAL
from .protocol import army_status, collection
from .tactics import geography, can_capture, point, visible_contacts, at_war
from .combat import CombatPolicy, plan_combat


class Route(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    army_id: int = Field(gt=0)
    province_ids: list[int] = Field(min_length=1, max_length=100)

    @model_validator(mode='after')
    def targets(self):
        if any(type(n) is not int or n <= 0 for n in self.province_ids):
            raise ValueError('ID provinsi harus integer positif.')
        return self


class CampaignArguments(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    mode: Literal['move', 'conquer'] = 'conquer'
    routes: list[Route] = Field(default_factory=list, max_length=20)
    army_ids: list[int] = Field(default_factory=list, max_length=20)
    province_ids: list[int] = Field(default_factory=list, max_length=200)
    player_id: int | None = Field(default=None, gt=0)
    homeland_only: bool = True
    cities_only: bool = False
    preserve_garrisons: bool = True
    coordinate: bool = False
    require_merged: bool = True
    rally_province: int | None = Field(default=None, gt=0)
    combat_policy: CombatPolicy = Field(default_factory=CombatPolicy)

    @model_validator(mode='after')
    def scope(self):
        if self.rally_province is not None and not self.coordinate:
            raise ValueError('Rally memerlukan coordinate=true.')
        if self.coordinate and self.routes and any(r.province_ids != self.routes[0].province_ids for r in self.routes):
            raise ValueError('Koordinasi kelompok memerlukan tujuan yang sama untuk semua pasukan.')
        if any(type(n) is not int or n <= 0 for n in self.army_ids + self.province_ids):
            raise ValueError('ID harus integer positif.')
        if len(set(self.army_ids)) != len(self.army_ids):
            raise ValueError('Army ID tidak boleh duplikat.')
        if self.routes:
            if self.army_ids or self.province_ids or self.player_id is not None:
                raise ValueError('Pilih routes eksplisit atau pemilihan target otomatis.')
            if len({r.army_id for r in self.routes}) != len(self.routes):
                raise ValueError('Satu rute untuk setiap pasukan.')
        elif bool(self.province_ids) == (self.player_id is not None):
            raise ValueError('Pilih province_ids atau player_id target.')
        if (len(self.routes[0].province_ids) if self.coordinate and self.routes else sum(len(r.province_ids) for r in self.routes)) > 200:
            raise ValueError('Maksimal 200 tujuan per campaign.')
        return self


def build_plan(session, request):
    raw, pid = session.raw, session.player_id
    mine, locs = armies(raw, pid), locations(raw)
    requested_ids = [r.army_id for r in request.routes] or request.army_ids
    eligible = {}
    for aid, a in mine.items():
        if requested_ids and int(aid) not in requested_ids:
            continue
        units = collection(a.get('u'))
        if army_status(a) != 'IDLE' or a.get('fs') or not point(a.get('p')) or a.get('a') or not units:
            continue
        if not all(isinstance(u, dict) and u.get('hp', 0) > 0 and session.ctrl.catalog.domain(u.get('t', 0)) == 'land' for u in units):
            continue
        if request.mode == 'conquer' and not request.coordinate and not can_capture(session, a):
            continue
        eligible[int(aid)] = a
    if requested_ids and set(requested_ids) != set(eligible):
        raise ValueError('Pasukan yang diminta tidak semuanya idle, hidup, milik sendiri, atau sesuai tugas.')
    protected = []
    if request.preserve_garrisons:
        for city in locs.values():
            if city.get('o') != pid or city.get('plv', 0) < 4:
                continue
            stationed = sorted(int(aid) for aid, a in mine.items() if a.get('l') == city['id'] and army_status(a) == 'IDLE')
            if stationed and all(aid in eligible for aid in stationed):
                aid = stationed[0]
                eligible.pop(aid)
                protected.append(aid)
        if request.routes and any(r.army_id not in eligible for r in request.routes):
            raise ValueError('Rute akan mengosongkan garnisun kota. Pilih pasukan cadangan atau preserve_garrisons=false jika memang diperintahkan.')
    if not eligible:
        raise ValueError('Tidak ada pasukan cadangan yang bisa menjalankan rute tanpa mengosongkan kota.')

    if request.routes:
        routes = [r.model_dump() for r in request.routes]
        if request.coordinate:
            from .coordination import coordinated_plan
            if request.mode == 'conquer' and not any(can_capture(session, a) for a in eligible.values()):
                raise ValueError('Kelompok perlu minimal satu unit yang bisa menguasai wilayah.')
            return coordinated_plan(session, request, eligible, request.routes[0].province_ids, protected)
    else:
        targets = request.province_ids or [p['province_id'] for p in geography(session, request.player_id, request.homeland_only, request.cities_only)['provinces']]
        if not targets:
            raise ValueError('Target tidak ditemukan; homeland tidak ditebak jika coreIDs tidak tersedia.')
        if any(t not in locs for t in targets):
            raise ValueError('Ada provinsi yang tidak dikenal dalam peta game.')
        targets = list(dict.fromkeys(targets))
        if request.mode == 'conquer':
            targets = [t for t in targets if locs[t].get('o') != pid]
        if not targets:
            raise ValueError('Semua target sudah milik sendiri.')
        if len(targets) > 200:
            raise ValueError('Lebih dari 200 target; bagi menjadi beberapa campaign.')
        if request.coordinate:
            from .coordination import coordinated_plan
            if request.mode == 'conquer' and not any(can_capture(session, a) for a in eligible.values()):
                raise ValueError('Kelompok perlu unit yang bisa menguasai wilayah.')
            if any(not point(locs[t].get('c')) for t in targets):
                raise ValueError('Koordinat target tidak tersedia.')
            pending = set(targets)
            cursor = next(iter(eligible.values()))['p']
            ordered = []
            while pending:
                city_first = [t for t in pending if locs[t].get('plv', 0) >= 4] or list(pending)
                target = min(city_first, key=lambda t: (math.hypot(cursor['x']-locs[t]['c']['x'], cursor['y']-locs[t]['c']['y']), t))
                ordered.append(target)
                cursor = locs[target]['c']
                pending.remove(target)
            return coordinated_plan(session, request, eligible, ordered, protected)
        route_map = {aid: [] for aid in eligible}
        endpoints = {aid: a['p'] for aid, a in eligible.items()}
        # Prioritize cities, then allocate nearby targets across available armies.
        for target in sorted(targets, key=lambda t: (locs[t].get('plv', 0) < 4, t)):
            pos = point(locs[target].get('c'))
            if not pos:
                raise ValueError('Koordinat target tidak tersedia.')
            aid = min(eligible, key=lambda a: (len(route_map[a]), math.hypot(endpoints[a]['x']-pos['x'], endpoints[a]['y']-pos['y']), a))
            route_map[aid].append(target)
            endpoints[aid] = pos
        routes = [{'army_id': aid, 'province_ids': targets} for aid, targets in route_map.items() if targets]

    planned = []
    owners = set()
    for route in routes:
        nodes = []
        for target in route['province_ids']:
            province = locs.get(target)
            if not province:
                raise ValueError('Provinsi tidak dikenal.')
            kind = 'conquer' if request.mode == 'conquer' and province.get('o') != pid else 'move'
            args = {'army_id': route['army_id'], 'target_province': target}
            if kind == 'conquer':
                owner = province.get('o')
                if type(owner) is not int or owner <= 0:
                    raise ValueError('Pemilik wilayah target belum diketahui.')
                args['target_player_id'] = owner
                args['combat_policy'] = request.combat_policy.model_dump()
                owners.add(owner)
            validate_target(session, kind, args)
            nodes.append({'kind': kind, 'args': args})
        planned.append({'army_id': route['army_id'], 'province_ids': route['province_ids'], 'nodes': nodes})
    return {'mode': request.mode, 'routes': planned, 'protected_army_ids': protected,
            'target_count': sum(len(r['nodes']) for r in planned),
            'war_required_player_ids': sorted(o for o in owners if not at_war(raw, pid, o)),
            'visible_contacts': visible_contacts(session),
            'combat_preview': [plan_combat(session, [r['army_id']], r['nodes'][0]['args']['target_province'], request.combat_policy.model_dump())
                               for r in planned[:3] if r['nodes'] and r['nodes'][0]['kind'] == 'conquer'],
            'notes': ['Rute diproses per pasukan dan tersimpan setelah restart.',
                      'Conquer menunggu kepemilikan berpindah. Kedatangan saja belum berarti berhasil.',
                      'Tidak otomatis mendeklarasikan perang; target damai menunggu keputusan diplomasi.',
                      'Jarak dipakai untuk alokasi, bukan jaminan path, waktu tiba, atau kekuatan tempur.']}
