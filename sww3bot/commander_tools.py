"""Native tool interfaces for explicit queue goals and commander inspections."""
from .commander_queue import Action, QueueArguments, action_args, validate_target, TERMINAL, IN_FLIGHT


def context():
    from .agent_tools import current_execution
    from .game_session import current_session
    return current_execution(), current_session()


def queue_game_action(action: dict, depends_on=None, quantity: int = 1):
    from .agent_tools import _on_loop
    execution, session = context()
    parsed = Action.model_validate(action)
    args = action_args(parsed)
    if quantity > 1 and parsed.kind != 'produce':
        return {'error': 'Quantity lebih dari satu hanya untuk produksi unit.'}
    validate_target(session, parsed.kind, args)
    deps = list(depends_on or [])
    result = []
    for _ in range(quantity):
        node = _on_loop(execution.loop, execution.runtime.store.enqueue_commander,
                        session.game_id, session.player_id, parsed.kind, args, deps)
        result.append(node['id'])
        deps = [node['id']]
    _on_loop(execution.loop, execution.runtime.store.set_preference, f'commander_paused:{session.game_id}', False)
    return {'node_ids': result, 'state': 'queued',
            'note': 'Queue tersimpan; dependency menunggu selesai di game, bukan sekadar perintah diterima.'}


def get_commander_queue():
    from .agent_tools import _on_loop
    execution, session = context()
    store = execution.runtime.store
    nodes = _on_loop(execution.loop, store.commander_nodes, session.game_id)
    return {'paused': _on_loop(execution.loop, store.preference, f'commander_paused:{session.game_id}', False),
            'nodes': [{'id': n['id'], 'kind': n['kind'], 'arguments': n['args'], 'state': n['state'],
                       'depends_on': n['dependencies'], 'detail': n['detail'], 'source': n['source']}
                      for n in nodes],
            'last_check': _on_loop(execution.loop, store.preference, f'commander_last:{session.game_id}', {})}


def cancel_game_action(node_id: int):
    from .agent_tools import _on_loop
    execution, session = context()
    store = execution.runtime.store
    node = _on_loop(execution.loop, store.commander_node, node_id, session.game_id)
    if not node or node['state'] in TERMINAL | IN_FLIGHT:
        return {'error': 'Item tidak ditemukan, sudah berjalan, atau sudah selesai. Perintah yang terkirim tetap dipantau.'}
    _on_loop(execution.loop, store.set_commander_node, node_id, 'cancelled', 'Dibatalkan pemilik.')
    return {'node_id': node_id, 'cancelled': True}


def get_economy_plan():
    from .agent_tools import _on_loop
    from .commander import economy_plan
    from api import actions
    actions.refresh()
    execution, session = context()
    nodes = _on_loop(execution.loop, execution.runtime.store.commander_nodes, session.game_id)
    return economy_plan(session, nodes)


def get_military_plan():
    from .commander import military_plan
    from api import actions
    actions.refresh()
    _, session = context()
    return military_plan(session)


def get_game_events():
    from .agent_tools import _on_loop
    execution, session = context()
    return {'events': _on_loop(execution.loop, execution.runtime.store.commander_events, session.game_id)}


def _session_raw(session):
    raw = getattr(session, 'raw', {})
    return raw if isinstance(raw, dict) else {}


def get_war_map():
    """Peta perang game aktif dari koran + relasi (-2 = WAR). Read-only."""
    from . import ghost_chat
    _, session = context()
    raw = _session_raw(session)
    wars = ghost_chat.wars_from_state(raw)
    pairs = ghost_chat.war_graph_from_state(raw)
    names = {}
    for player in ghost_chat.players_from_state(raw):
        if isinstance(player, dict) and 'player_id' in player:
            names[str(player['player_id'])] = player.get('name', '?')
    counts = {}
    for first, second in pairs:
        counts[str(first)] = counts.get(str(first), 0) + 1
        counts[str(second)] = counts.get(str(second), 0) + 1
    top = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:10]
    return {'wars': wars[:15], 'war_count': len(wars), 'front_pairs': len(pairs),
            'top_fronts': [{'player_id': pid, 'name': names.get(pid, f'ID {pid}'),
                            'fronts': fronts} for pid, fronts in top],
            'note': 'Korban besar = pertempuran sengit; relasi hanya mencatat tetangga.'}


def get_enemy_production():
    """Kapasitas produksi militer tiap negara dari bangunan terlihat. Read-only."""
    from .ghostspy import MILITARY_BUILDINGS
    _, session = context()
    raw = _session_raw(session)
    catalog = getattr(getattr(session, 'ctrl', None), 'catalog', None)
    if catalog is None:
        return {'error': 'Katalog game tidak tersedia.'}
    name_cache = {}

    def building_name(bid):
        if bid not in name_cache:
            try:
                name_cache[bid] = catalog.name(bid)
            except Exception:
                name_cache[bid] = ''
        return name_cache[bid]

    states = raw.get('states', {}) if isinstance(raw.get('states'), dict) else {}
    s3 = states.get('3', {}) if isinstance(states, dict) else {}
    map_data = s3.get('map', {}) if isinstance(s3, dict) else {}
    locs = map_data.get('locations', []) if isinstance(map_data, dict) else []
    locs = locs[1] if isinstance(locs, list) and len(locs) > 1 else []
    s1 = states.get('1', {}) if isinstance(states, dict) else {}
    pool = s1.get('players', {}) if isinstance(s1, dict) else {}
    nations = {}
    for key, player in pool.items():
        if not isinstance(player, dict):
            continue
        try:
            pid = int(player.get('playerID', key))
        except (TypeError, ValueError):
            continue
        nations[pid] = str(player.get('nationName', player.get('name', '?')))
    production = {}
    for loc in locs:
        if not isinstance(loc, dict):
            continue
        try:
            owner = int(loc.get('o', 0))
        except (TypeError, ValueError):
            continue
        upgrades = loc.get('us', [])
        entries = upgrades[1] if isinstance(upgrades, list) and len(upgrades) > 1 else []
        for built in entries:
            if not isinstance(built, dict):
                continue
            try:
                bid = int(built.get('id', 0))
            except (TypeError, ValueError):
                continue
            category = MILITARY_BUILDINGS.get(building_name(bid), '')
            if not category:
                continue
            slot = production.setdefault(owner, {})
            slot[category] = slot.get(category, 0) + 1
    me = getattr(session, 'player_id', 0)
    rows = [{'player_id': pid, 'nation': nations.get(pid, f'ID {pid}'),
             'military': military, 'total': sum(military.values()),
             'self': pid == me}
            for pid, military in production.items()]
    rows.sort(key=lambda r: r['total'], reverse=True)
    return {'producers': rows[:15],
            'note': 'Bangunan terlihat publik; isi dan level pasukan tetap butuh kontak/scout.'}


def record_lesson(text):
    """Catat pelajaran penting agar diingat di tugas berikut. Maks 20 per game."""
    from .agent_tools import _on_loop
    execution, session = context()
    text = str(text or '').strip()[:500]
    if not text:
        return {'error': 'Isi pelajaran tidak boleh kosong.'}
    store = execution.runtime.store
    key = f'lessons:{session.game_id}'
    lessons = _on_loop(execution.loop, store.preference, key, [])
    lessons = [entry for entry in lessons if isinstance(entry, dict)][:19]
    states = _session_raw(session).get('states', {})
    day = states.get('12', {}).get('dayOfGame', 0) if isinstance(states, dict) else 0
    lessons.append({'text': text, 'day': day if isinstance(day, int) else 0})
    _on_loop(execution.loop, store.set_preference, key, lessons)
    return {'recorded': text, 'lessons': len(lessons)}


def get_lessons():
    """Baca pelajaran yang dicatat di game aktif."""
    from .agent_tools import _on_loop
    execution, session = context()
    lessons = _on_loop(execution.loop, execution.runtime.store.preference,
                       f'lessons:{session.game_id}', [])
    return {'lessons': lessons if isinstance(lessons, list) else []}


def definitions():
    from .campaign import CampaignArguments
    from .combat import CombatArguments
    from .coordination import GroupMoveArguments
    from pydantic import BaseModel, ConfigDict, Field
    from typing import Literal
    class CoordinationArguments(CampaignArguments):
        coordinate: Literal[True] = True
    class MapArguments(BaseModel):
        model_config = ConfigDict(extra='forbid', strict=True)
        player_id: int | None = Field(default=None, gt=0)
        homeland_only: bool = False
        cities_only: bool = False
    class ContactArguments(BaseModel):
        model_config = ConfigDict(extra='forbid', strict=True)
        player_id: int | None = Field(default=None, gt=0)
        province_id: int | None = Field(default=None, gt=0)
    return [
        {'name': 'get_combat_plan', 'description': 'Analisis tempur darat: HP, peran unit, terrain, damage vs kontak musuh terlihat, margin, rekomendasi maju/tahan/pulihkan. Read-only, bukan peluang menang.', 'fn': get_combat_plan, 'argument_model': CombatArguments, 'mutates': False},
        {'name': 'get_coordination_plan', 'description': 'Preview pengumpulan pasukan di rally sendiri lalu bergerak sebagai kelompok. Untuk rute sama gunakan coordinate=true; belum menjalankan aksi.', 'fn': get_coordination_plan, 'argument_model': CoordinationArguments, 'mutates': False},
        {'name': 'get_coordinations', 'description': 'Status kelompok tersimpan: rally, kesiapan, penahanan combat, dan target berikutnya.', 'fn': get_coordinations, 'parameters': {}, 'mutates': False},
        {'name': 'move_army_group', 'description': 'Pengiriman internal kelompok lewat queue campaign; gunakan queue_campaign coordinate=true untuk rencana persisten.', 'fn': move_army_group, 'argument_model': GroupMoveArguments, 'mutates': True},
        {'name': 'get_campaign_plan', 'description': 'Preview rute banyak pasukan/provinsi. Pilih routes eksplisit atau player_id/province_ids; homeland berdasarkan coreIDs. Tidak menjalankan aksi.', 'fn': get_campaign_plan, 'argument_model': CampaignArguments, 'mutates': False},
        {'name': 'queue_campaign', 'description': 'Simpan rute multi-army setelah pengguna memerintahkan move/conquer. mode conquer hanya untuk perintah taklukkan yang jelas. Dependency antar tujuan per pasukan. coordinate=true mengumpulkan semua di rally lalu bergerak bersama; combat_policy menahan serangan berisiko. Tidak deklarasi perang otomatis.', 'fn': queue_campaign, 'argument_model': CampaignArguments, 'mutates': True},
        {'name': 'cancel_campaign', 'description': 'Batalkan semua tujuan campaign yang belum dikirim.', 'fn': cancel_campaign, 'parameters': {'campaign_id': {'type': 'integer'}}},
        {'name': 'get_map_regions', 'description': 'Peta wilayah: kota, pemilik sekarang, core/homeland pemilik asli. player_id + homeland_only memilih homeland meski sudah diduduki negara lain.', 'fn': get_map_regions, 'argument_model': MapArguments, 'mutates': False},
        {'name': 'get_visible_enemy_units', 'description': 'Kontak musuh tanpa spy: sight sendiri, tempur, atau akses militer. Last_seen terpisah dari posisi sekarang; fog tetap unknown.', 'fn': get_visible_enemy_units, 'argument_model': ContactArguments, 'mutates': False},
        {'name': 'queue_game_action', 'description': 'Antrekan build/produce/research/move pertahanan atau conquer saat diperintahkan. Gunakan ID item dari data resmi. depends_on berisi ID node yang harus benar-benar selesai; quantity untuk produksi berulang. Hanya saat pengguna meminta tindakan.',
         'fn': queue_game_action, 'argument_model': QueueArguments, 'parameters': {}, 'mutates': True},
        {'name': 'get_commander_queue', 'description': 'Baca antrean semua bangunan, produksi, riset dan pergerakan, berikut status dan dependency.', 'fn': get_commander_queue, 'parameters': {}},
        {'name': 'get_economy_plan', 'description': 'Baca budget seluruh queue, resource cadangan, item yang mampu dibayar, dan perkiraan deplesi.', 'fn': get_economy_plan, 'parameters': {}},
        {'name': 'get_military_plan', 'description': 'Analisis pasukan sendiri, kota tanpa garrison, dan usulan penempatan defensif. Tidak menjalankan gerakan.', 'fn': get_military_plan, 'parameters': {}},
        {'name': 'get_game_events', 'description': 'Baca perubahan game yang benar-benar teramati, termasuk bangunan/riset selesai, kota direbut, dan produksi kosong.', 'fn': get_game_events, 'parameters': {}},
        {'name': 'cancel_game_action', 'description': 'Batalkan satu item queue yang belum dikirim.', 'fn': cancel_game_action,
         'parameters': {'node_id': {'type': 'integer', 'description': 'ID dari get_commander_queue'}}, 'mutates': True},
        {'name': 'get_war_map', 'description': 'Peta perang game aktif: perang koran + korban tiap pihak + front relasi terbanyak. Baca sebelum menyerang. Read-only.', 'fn': get_war_map, 'parameters': {}},
        {'name': 'get_enemy_production', 'description': 'Kapasitas produksi militer tiap negara dari bangunan terlihat (rekrut/senjata/udara/laut) dibanding milik sendiri. Baca sebelum menyerang. Read-only.', 'fn': get_enemy_production, 'parameters': {}},
        {'name': 'record_lesson', 'description': 'Catat pelajaran penting (taktik berhasil/gagal, perilaku musuh) agar diingat di tugas berikut. Maks 20 per game.', 'fn': record_lesson,
         'parameters': {'text': {'type': 'string', 'description': 'Pelajaran singkat dan spesifik'}}},
        {'name': 'get_lessons', 'description': 'Baca pelajaran yang dicatat di game aktif.', 'fn': get_lessons, 'parameters': {}},
    ]


def get_campaign_plan(**arguments):
    from .campaign import CampaignArguments, build_plan
    from api import actions
    actions.refresh()
    _, session = context()
    return build_plan(session, CampaignArguments.model_validate(arguments))


def queue_campaign(**arguments):
    from .campaign import CampaignArguments, build_plan
    from .agent_tools import _on_loop
    from api import actions
    actions.refresh()
    execution, session = context()
    plan = build_plan(session, CampaignArguments.model_validate(arguments))
    result = _on_loop(execution.loop, execution.runtime.store.enqueue_campaign,
                      session.game_id, session.player_id, plan)
    result.update(state='queued', paused=_on_loop(execution.loop, execution.runtime.store.preference, f'commander_paused:{session.game_id}', False),
                  war_required_player_ids=plan['war_required_player_ids'],
                  note='Rute tersimpan. Target damai menunggu; conquer selesai hanya setelah kepemilikan berubah.')
    return result


def cancel_campaign(campaign_id: int):
    from .agent_tools import _on_loop
    execution, session = context()
    store = execution.runtime.store
    def cancel():
        value = store.preference(f'campaign:{session.game_id}:{campaign_id}')
        if not value or value['player_id'] != session.player_id:
            return {'error': 'Campaign tidak ditemukan untuk pemain aktif.'}
        cancelled, in_flight = [], []
        for route in value['routes']:
            for node_id in route['node_ids']:
                node = store.commander_node(node_id, session.game_id)
                if node['state'] in IN_FLIGHT:
                    in_flight.append(node_id)
                elif node['state'] not in TERMINAL:
                    store.set_commander_node(node_id, 'cancelled', 'Campaign dibatalkan pemilik.')
                    cancelled.append(node_id)
        return {'campaign_id': campaign_id, 'cancelled': cancelled, 'already_sent': in_flight,
                'note': 'Perintah yang sudah dikirim tetap berlaku dan dipantau.'}
    return _on_loop(execution.loop, cancel)


def get_map_regions(player_id: int = None, homeland_only: bool = False, cities_only: bool = False):
    from .tactics import geography
    from api import actions
    actions.refresh()
    _, session = context()
    return geography(session, player_id, homeland_only, cities_only)


def get_visible_enemy_units(player_id: int = None, province_id: int = None):
    from .tactics import visible_contacts
    from .agent_tools import _on_loop
    from api import actions
    actions.refresh()
    execution, session = context()
    contacts = visible_contacts(session)
    def match(contact):
        return (player_id is None or contact['owner_id'] == player_id) and (province_id is None or contact.get('province_id') == province_id)
    history = _on_loop(execution.loop, execution.runtime.store.preference,
                       f'contact_history:{session.game_id}:{session.player_id}', {})
    currently_visible = {c['army_id'] for c in contacts}
    return {'contacts': [c for c in contacts if match(c)],
            'last_seen': [dict(c, visible_now=False) for aid, c in history.items() if aid not in currently_visible and match(c)],
            'complete_enemy_map': False,
            'note': 'Tanpa spy: hanya sight sendiri, kontak tempur, atau akses militer sah. Last_seen bukan posisi sekarang; fog/stealth tetap unknown.'}


def get_combat_plan(target_province: int, army_ids=None, policy=None):
    from api import actions
    _, ge, _ = actions.refresh()
    return ge.get_combat_plan(target_province, army_ids, policy)


def get_coordination_plan(**arguments):
    arguments['coordinate'] = True
    return get_campaign_plan(**arguments)


def move_army_group(unit_ids, target_province: int, combat_policy=None, protected_city_ids=None, target_player_id=None, is_rally=False, require_merged=False):
    """Executor entry point for one guarded, ordinary multi-army action."""
    from .coordination import resolve_group, group_readiness
    from .commander_state import locations
    from .agent_tools import TaskStop
    _, session = context()
    args = {'unit_ids': unit_ids, 'target_province': target_province,
            'combat_policy': combat_policy, 'protected_city_ids': protected_city_ids or [],
            'target_player_id': target_player_id, 'is_rally': is_rally, 'require_merged': require_merged}
    members = resolve_group(session, args)
    kind = 'group_move' if locations(session.raw).get(target_province, {}).get('o') == session.player_id else 'group_conquer'
    state, detail = group_readiness(session, {'kind': kind, 'args': args})
    if state != 'ready':
        raise TaskStop('rejected', detail)
    response = session.ctrl.move_armies([a['id'] for a in members], target_province)
    from .protocol import action_result
    return {'success': action_result(response, response.get('_request_id')) == 1,
            'army_ids': [a['id'] for a in members], 'target_province': target_province}


def get_coordinations():
    from .agent_tools import _on_loop
    from .coordination import resolve_group
    from api import actions
    actions.refresh()
    execution, session = context()
    store = execution.runtime.store
    def read():
        result = []
        for campaign in store.campaigns(session.game_id):
            if not campaign.get('coordinated') or campaign['player_id'] != session.player_id:
                continue
            nodes = [store.commander_node(nid, session.game_id) for r in campaign['routes'] for nid in r['node_ids']]
            pending = [n for n in nodes if n and n['state'] not in TERMINAL]
            if all(n and n['state'] == 'completed' for n in nodes):
                phase = 'completed'
            elif any(n and n['state'] == 'failed' for n in nodes):
                phase = 'blocked'
            elif not pending:
                phase = 'cancelled'
            elif pending[0]['state'] == 'outcome_unknown':
                phase = 'verification_pending'
            elif pending[0]['state'].startswith('waiting_'):
                phase = pending[0]['state']
            elif nodes[0]['state'] != 'completed':
                phase = 'rally_order_accepted' if nodes[0]['state'] == 'accepted' else 'rally_queued'
            else:
                phase = 'advance_order_accepted' if pending[0]['state'] == 'accepted' else 'next_target_queued'
            try:
                members = resolve_group(session, nodes[0]['args'])
                membership = {'current_army_ids': [a['id'] for a in members], 'merged': len(members) == 1}
            except ValueError as exc:
                membership = {'membership_note': str(exc), 'merged': None}
            result.append(dict(campaign, phase=phase, **membership,
                               nodes=[{'id': n['id'], 'kind': n['kind'], 'state': n['state'], 'detail': n['detail']} for n in nodes if n]))
        return result
    return {'groups': _on_loop(execution.loop, read),
            'note': 'Rally harus benar-benar selesai sebelum kelompok maju; perintah diterima belum berarti tiba.'}
