"""Persistent group membership and a rally barrier before joint advancement."""
import math

from pydantic import BaseModel, ConfigDict, Field

from .commander_state import armies, locations
from .protocol import collection, commands, same_point, army_status
from .tactics import point, can_capture
from .combat import CombatPolicy


class GroupMoveArguments(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    unit_ids: list[int] = Field(min_length=1, max_length=500)
    target_province: int = Field(gt=0)
    combat_policy: CombatPolicy | None = None
    protected_city_ids: list[int] = Field(default_factory=list, max_length=500)
    target_player_id: int | None = Field(default=None, gt=0)
    is_rally: bool = False
    require_merged: bool = False


def resolve_group(session, args):
    wanted = set(args['unit_ids'])
    if not wanted or any(type(uid) is not int or uid == 0 for uid in wanted):
        raise ValueError('Identitas unit kelompok belum tersedia.')
    candidates, found = [], set()
    for aid, army in armies(session.raw, session.player_id).items():
        units = [u for u in collection(army.get('u')) if isinstance(u, dict) and u.get('hp', 0) > 0]
        ids = {u.get('id') for u in units}
        if not wanted.intersection(ids):
            continue
        if not ids.issubset(wanted):
            raise ValueError('Kelompok bergabung dengan unit di luar rencana; perlu pemilihan ulang.')
        found.update(ids)
        candidates.append(army)
    if found != wanted:
        raise ValueError('Ada ID unit yang hilang/berubah; keanggotaan kelompok belum terverifikasi.')
    return sorted(candidates, key=lambda a: a['id'])


def group_observed(session, node):
    args, kind = node['args'], node['kind']
    target = locations(session.raw).get(args['target_province'], {})
    if kind == 'group_conquer' and target.get('o') == session.player_id:
        return 'completed'
    try:
        members = resolve_group(session, args)
    except ValueError:
        return None
    arrived = [same_point(a.get('p'), target.get('c')) and army_status(a) == 'IDLE' and not a.get('fs') for a in members]
    if kind == 'group_move' and target.get('o') == session.player_id and all(arrived):
        return 'completed'
    if node.get('baseline') and all(done or any(c.get('@c') == 'gc' and same_point(c.get('tp'), target.get('c'))
                                               for c in commands(a)) for a, done in zip(members, arrived)):
        return 'accepted'
    return None


def group_readiness(session, node):
    from .combat import plan_combat
    from .tactics import at_war
    args = node['args']
    try:
        members = resolve_group(session, args)
    except ValueError as exc:
        return 'waiting_observation', str(exc)
    if len(members) > 20:
        return 'waiting_coordination', 'Kelompok tersebar menjadi lebih dari 20 stack; perlu pengelompokan ulang.'
    if args.get('require_merged') and not args.get('is_rally') and len(members) != 1:
        return 'waiting_coordination', 'Semua tiba, tetapi belum menjadi satu stack; tunggu merge sebelum maju bersama.'
    if any(army_status(a) != 'IDLE' or a.get('fs') for a in members):
        return 'waiting_coordination', 'Kelompok belum semuanya idle atau masih bertempur.'
    if any(a.get('a') or not all(session.ctrl.catalog.domain(u.get('t', 0)) == 'land'
           for u in collection(a.get('u')) if isinstance(u, dict)) for a in members):
        return 'failed', 'Koordinasi ini memerlukan pasukan darat.'
    target = locations(session.raw).get(args['target_province'])
    if not target or not point(target.get('c')):
        return 'failed', 'Koordinat tujuan kelompok tidak tersedia.'
    if node['kind'] == 'group_move' and target.get('o') != session.player_id:
        return 'failed', 'Rally/tujuan move bukan lagi wilayah sendiri.'
    if args.get('is_rally'):
        from .tactics import visible_contacts
        if target.get('m', 0) < 40:
            return 'waiting_coordination', 'Morale rally turun; pilih tempat berkumpul lain.'
        if any(c.get('is_hostile') and (c.get('province_id') == target['id'] or
               math.hypot(c['position']['x']-target['c']['x'], c['position']['y']-target['c']['y']) <= 40)
               for c in visible_contacts(session)):
            return 'waiting_combat', 'Ada kontak musuh terlihat dekat rally; pilih atau amankan rally dahulu.'
    member_ids = {str(a['id']) for a in members}
    for cid in args.get('protected_city_ids', []):
        city = locations(session.raw).get(cid, {})
        leaving = any(a.get('l') == cid and not same_point(a.get('p'), target.get('c')) for a in members)
        if city.get('o') == session.player_id and leaving and not any(str(aid) not in member_ids and
                a.get('l') == cid and army_status(a) == 'IDLE' and not a.get('a') and
                any(session.ctrl.catalog.domain(u.get('t', 0)) == 'land' and u.get('hp', 0) > 0
                    for u in collection(a.get('u')) if isinstance(u, dict)) for aid, a in armies(session.raw, session.player_id).items()):
            return 'waiting_coordination', 'Garnisun kota awal perlu pengganti sebelum kelompok berangkat.'
    if node['kind'] == 'group_conquer':
        owner = target.get('o')
        if args.get('target_player_id') and owner not in (session.player_id, args['target_player_id']):
            return 'waiting_policy', 'Pemilik target berubah; perlu rencana negara baru.'
        if owner != session.player_id and (type(owner) is not int or owner <= 0 or not at_war(session.raw, session.player_id, owner)):
            return 'waiting_diplomacy', 'Kelompok menunggu diplomasi; tidak otomatis deklarasi perang.'
        if not any(can_capture(session, a) for a in members):
            return 'waiting_coordination', 'Kelompok memerlukan unit yang dapat menguasai wilayah.'
        combat = plan_combat(session, [a['id'] for a in members], args['target_province'], args.get('combat_policy'))
        if not combat['advance_allowed']:
            return 'waiting_combat', combat['decision'] + ': ' + ' '.join(combat['reasons'])
    return 'ready', ''


def coordinated_plan(session, request, eligible, targets, protected):
    locs = locations(session.raw)
    unit_ids = [u.get('id') for a in eligible.values() for u in collection(a.get('u')) if isinstance(u, dict)]
    if not unit_ids or len(unit_ids) > 500 or any(type(uid) is not int or uid == 0 for uid in unit_ids):
        raise ValueError('ID unit kelompok tidak lengkap atau melebihi batas.')
    if len(eligible) > 20:
        raise ValueError('Pilih maksimal 20 army_ids untuk satu kelompok.')
    selected = set(eligible)
    candidates = []
    for cid, p in locs.items():
        if p.get('o') != session.player_id or p.get('m', 0) < 40 or not point(p.get('c')):
            continue
        outsiders = any(int(aid) not in selected and a.get('l') == cid and army_status(a) == 'IDLE'
                        for aid, a in armies(session.raw, session.player_id).items())
        if not outsiders:
            candidates.append(p)
    if request.rally_province is not None:
        candidates = [p for p in candidates if p['id'] == request.rally_province]
    if not candidates:
        raise ValueError('Pilih rally sendiri yang aman dan tidak berisi unit di luar kelompok.')
    rally = min(candidates, key=lambda p: sum(math.hypot(a['p']['x']-p['c']['x'], a['p']['y']-p['c']['y']) for a in eligible.values()))
    common = {'army_ids': sorted(eligible), 'unit_ids': sorted(set(unit_ids)), 'require_merged': request.require_merged,
              'protected_city_ids': sorted(cid for cid, p in locs.items() if request.preserve_garrisons and p.get('o') == session.player_id and p.get('plv', 0) >= 4)}
    nodes = [{'kind': 'group_move', 'args': dict(common, target_province=rally['id'], is_rally=True)}]
    owners = set()
    for target in targets:
        province = locs.get(target)
        if not province or not point(province.get('c')):
            raise ValueError('Target atau koordinat tidak ditemukan.')
        kind = 'group_conquer' if request.mode == 'conquer' and province.get('o') != session.player_id else 'group_move'
        if kind == 'group_move' and province.get('o') != session.player_id:
            raise ValueError('Move kelompok hanya menuju wilayah sendiri.')
        args = dict(common, target_province=target)
        if kind == 'group_conquer':
            if type(province.get('o')) is not int or province['o'] <= 0:
                raise ValueError('Pemilik target belum diketahui.')
            args.update(target_player_id=province['o'], combat_policy=request.combat_policy.model_dump())
            owners.add(province['o'])
        nodes.append({'kind': kind, 'args': args})
    from .tactics import at_war
    from .combat import plan_combat
    previews = [{'target_province': t, 'assessment': plan_combat(session, sorted(eligible), t, request.combat_policy.model_dump())}
                for t in targets[:3] if locs[t].get('o') != session.player_id]
    return {'mode': request.mode, 'coordinated': True, 'rally_province': rally['id'],
            'routes': [{'army_id': min(eligible), 'army_ids': sorted(eligible), 'province_ids': [rally['id']] + targets, 'nodes': nodes}],
            'protected_army_ids': protected, 'target_count': len(targets), 'combat_preview': previews,
            'war_required_player_ids': sorted(o for o in owners if not at_war(session.raw, session.player_id, o)),
            'notes': ['Semua unit berkumpul dahulu; kepala rute maju setelah seluruh kelompok tiba dan idle.',
                      'Default menunggu merge menjadi satu stack sebelum maju; jika require_merged=false, waktu tiba stack dapat berbeda.',
                      'Keanggotaan dilacak lewat ID unit sendiri meski ID army berubah karena merge.',
                      'Jika ID unit hilang atau ada unit di luar kelompok yang ikut merge, rute ditahan untuk penilaian ulang.']}
