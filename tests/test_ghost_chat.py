"""GhostSpy lewat chat Telegram: parse /ghost + handler offline (tanpa network)."""
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from sww3bot.agent_engine import Engine
from sww3bot.ghost_chat import parse_ghost_args, players_from_state, war_graph_from_state, wars_from_state
from sww3bot.ghostspy import GhostSession, GhostSpy, unit_name
from sww3bot.telegram_bot import TelegramBot


@pytest.fixture
def ghost_bot(settings, store):
    executor = SimpleNamespace(list_games=AsyncMock(return_value=[]),
        validate_game=AsyncMock(), session=lambda gid: SimpleNamespace(player_id=7))
    engine = Engine(settings, AsyncMock(), executor, store)
    value = TelegramBot(settings, store, engine)
    value.app = SimpleNamespace(bot=SimpleNamespace(send_message=AsyncMock()))
    return value


def update(text, uid=123, update_id=1):
    return SimpleNamespace(effective_user=SimpleNamespace(id=uid),
        effective_chat=SimpleNamespace(type='private'),
        effective_message=SimpleNamespace(text=text), update_id=update_id,
        callback_query=None)


def test_parse_help_status_spy():
    assert parse_ghost_args('')[0] == 'help'
    assert parse_ghost_args('help')[0] == 'help'
    assert parse_ghost_args('status')[0] == 'status'
    assert parse_ghost_args('10925912') == ('spy', {'game_id': 10925912})
    assert parse_ghost_args('spy 10925912') == ('spy', {'game_id': 10925912})
    assert parse_ghost_args('players 10925912') == ('players', {'game_id': 10925912})


def test_parse_track_find():
    assert parse_ghost_args('track 42') == ('track', {'user_id': 42, 'username': ''})
    assert parse_ghost_args('track 42 RedStorm') == ('track', {'user_id': 42, 'username': 'RedStorm'})
    assert parse_ghost_args('find RedStorm') == ('find', {'username': 'RedStorm'})


def test_parse_rejects_bad_input():
    for bad in ('spy', 'spy abc', 'spy -5', 'spy 0', 'track', 'track abc', 'track 0', 'find', 'find   ', 'rusak total'):
        action, info = parse_ghost_args(bad)
        assert action == 'error'
        assert info['message']


def test_players_from_state_counts_provinces_and_units():
    raw = {'states': {
        '1': {'players': {'7': {'playerID': 7, 'userName': 'Saya', 'nationName': 'Indonesia', 'siteUserID': 111},
                          '8': {'playerID': 8, 'userName': 'Musuh', 'nationName': 'Niger', 'siteUserID': 222}}},
        '3': {'map': {'locations': ['', [{'id': 10, 'o': 7}, {'id': 11, 'o': 7}, {'id': 12, 'o': 8}]]}},
        '6': {'armies': {'1': {'id': 1, 'o': 7, 'u': ['', [{'id': 1}, {'id': 2}]]},
                         '2': {'id': 2, 'o': 8, 'u': ['', [{'id': 3}]]}}}}}
    players = players_from_state(raw)
    by_id = {p['id']: p for p in players}
    assert by_id[111]['provinces'] == 2
    assert by_id[111]['army_strength'] == 2
    assert by_id[222]['provinces'] == 1
    assert by_id[222]['army_strength'] == 1
    assert players_from_state({}) == []
    assert players_from_state(None) == []


class FakeSpy(GhostSpy):
    def __init__(self):
        super().__init__(web_api=None)
        session = GhostSession(game_id=10925912, game_server='xgs1.c.bytro.com', is_active=True)
        session.players_found = [
            {'id': 42, 'name': 'Target', 'nation': 'Niger', 'provinces': 20, 'army_strength': 150},
            {'id': 43, 'name': 'Other', 'nation': 'Chad', 'provinces': 4, 'army_strength': 30},
        ]
        self.sessions[10925912] = session

    def infiltrate_game(self, game_id):
        return self.sessions[10925912]

    def find_player_games(self, username):
        assert username == 'Target'
        return [{'id': 10925912, 'label': 'Game 10925912 — Niger'}]


async def test_ghost_help_lists_subcommands(ghost_bot):
    await ghost_bot.handle(update('/ghost'), None)
    sent = ghost_bot.app.bot.send_message.call_args.kwargs['text']
    assert 'spy' in sent and 'track' in sent and 'find' in sent and 'status' in sent


async def test_ghost_rejects_bad_id_without_network(ghost_bot):
    ghost_bot.ghost_spy = FakeSpy()
    await ghost_bot.handle(update('/ghost spy abc'), None)
    sent = ghost_bot.app.bot.send_message.call_args.kwargs['text']
    assert 'ID game' in sent


async def test_ghost_spy_renders_live_session(ghost_bot):
    ghost_bot.ghost_spy = FakeSpy()
    await ghost_bot.handle(update('/ghost 10925912'), None)
    sent = ghost_bot.app.bot.send_message.call_args.kwargs['text']
    assert 'GHOST SPY' in sent and 'Target' in sent


async def test_ghost_track_renders_cross_game_intel(ghost_bot):
    ghost_bot.ghost_spy = FakeSpy()
    await ghost_bot.handle(update('/ghost track 42 Target'), None)
    sent = ghost_bot.app.bot.send_message.call_args.kwargs['text']
    assert 'CROSS-GAME INTEL' in sent


async def test_ghost_find_lists_games(ghost_bot):
    ghost_bot.ghost_spy = FakeSpy()
    await ghost_bot.handle(update('/ghost find Target'), None)
    sent = ghost_bot.app.bot.send_message.call_args.kwargs['text']
    assert '10925912' in sent


async def test_ghost_status_lists_sessions(ghost_bot):
    ghost_bot.ghost_spy = FakeSpy()
    await ghost_bot.handle(update('/ghost status'), None)
    sent = ghost_bot.app.bot.send_message.call_args.kwargs['text']
    assert 'GHOST SPY NETWORK' in sent


def rich_state():
    return {'states': {
        '1': {'players': {
            '7': {'playerID': 7, 'userName': 'Saya', 'nationName': 'Indonesia',
                  'siteUserID': 111, 'teamID': 1},
            '8': {'playerID': 8, 'userName': 'Musuh', 'nationName': 'Niger',
                  'siteUserID': 222, 'defeated': True},
            '9': {'playerID': 9, 'userName': 'Bot AI', 'nationName': 'Chad',
                  'siteUserID': 333, 'computerPlayer': True}}},
        '3': {'map': {'locations': ['', [
            {'id': 10, 'o': 7, 'm': 80, 'plv': 100, 'rp': 50},
            {'id': 11, 'o': 7, 'm': 60, 'plv': 50, 'rp': 30},
            {'id': 12, 'o': 8, 'm': 20, 'plv': 10, 'rp': 5},
            {'id': 'rusak', 'o': '??'},
        ]]}},
        '6': {'armies': {
            '1': {'id': 1, 'o': 7, 'l': 10,
                  'u': ['', [{'t': 1, 's': 5}, {'t': 11, 's': 3}]],
                  'c': ['', [{'@c': 'gc', 'at': 'jam 5'}]]},
            '2': {'id': 2, 'o': 8, 'l': 12,
                  'u': ['', [{'t': 9999, 's': 2}]],
                  'c': ['', [{'@c': 'ac'}]]},
            '3': {'id': 3, 'o': 7, 'l': 11,
                  'u': ['', [{'t': 1, 's': 2}]]},
        }}}}


def test_players_from_state_enriches_intel():
    players = players_from_state(rich_state())
    by_id = {p['id']: p for p in players}
    saya = by_id[111]
    assert saya['morale'] == 70
    assert saya['victory_points'] == 150
    assert saya['income'] == 80
    assert saya['army_strength'] == 10
    assert saya['armies'] == 2
    assert saya['units'] == {1: 7, 11: 3}
    assert saya['moving'] == 1
    assert saya['attacking'] == 0
    assert saya['team'] == 1
    assert saya['defeated'] is False
    assert saya['is_ai'] is False
    assert len(saya['moves']) == 1
    assert saya['moves'][0]['command'] == 'move'
    assert saya['moves'][0]['arrival'] == 'jam 5'
    musuh = by_id[222]
    assert musuh['morale'] == 20
    assert musuh['attacking'] == 1
    assert musuh['defeated'] is True
    assert by_id[333]['is_ai'] is True


def war_state():
    link_a = "{{{countryLink 'India' '6'}}}"
    link_b = "{{{countryLink 'Belarus' '52'}}}"
    return {'states': {'2': {'articles': [
        {'title': f"{link_a}, {link_b} at War", 'day': 12,
         'messageBody': f'<p>Casualties:\n{link_a} - 1,763\n{link_b} - 2,083</p>'},
        {'title': "{{{countryLink 'Greece' '58'}}}, {{{countryLink 'Italy' '15'}}} at War",
         'day': 10,
         'messageBody': "<p>Casualties:\n{{{countryLink 'Greece' '58'}}} - 640\n"
                        "{{{countryLink 'Italy' '15'}}} - 100</p>"},
        {'title': 'Widespread Dissent in Greece', 'day': 13, 'messageBody': 'protes warga'},
        {'title': 'Rusak at War', 'day': 1, 'messageBody': None},
        'bukan-dict',
    ]}}}


def test_parse_wars_action():
    assert parse_ghost_args('wars 10925912') == ('wars', {'game_id': 10925912})
    action, info = parse_ghost_args('wars')
    assert action == 'error' and info['message']


def test_wars_from_state_parses_casualties():
    wars = wars_from_state(war_state())
    assert len(wars) == 2
    assert wars[0]['a_name'] == 'India'
    assert wars[0]['a_losses'] == 1763
    assert wars[0]['b_losses'] == 2083
    assert wars[0]['day'] == 12
    assert wars[1]['a_name'] == 'Greece'
    assert wars[1]['a_losses'] == 640
    assert wars_from_state({}) == []
    assert wars_from_state(None) == []


def test_render_wars_shows_battlefield():
    session = GhostSession(game_id=10925912, game_server='xgs1.c.bytro.com', is_active=True)
    session.wars = wars_from_state(war_state())
    output = GhostSpy().render_wars(session)
    assert 'MEDAN PERANG' in output
    assert 'India vs Belarus' in output
    assert '1763' in output


def test_war_graph_reads_hostile_relations():
    raw = {'states': {'5': {'relations': {'neighborRelations': {
        '6': {'52': -2, '14': -2, '7': 6},
        '52': {'6': -2},
        '7': {'6': 6, '6b': 'rusak'},
        'rusak': 'bukan-dict',
        '9': {'9': -2},
    }}}}}
    assert war_graph_from_state(raw) == [('14', '6'), ('52', '6')]
    assert war_graph_from_state({}) == []
    assert war_graph_from_state(None) == []
    assert war_graph_from_state({'states': {'5': {}}}) == []


def test_render_wars_shows_relation_map():
    session = GhostSession(game_id=10925912, game_server='xgs1.c.bytro.com', is_active=True)
    session.wars = []
    session.war_pairs = [('14', '6'), ('52', '6')]
    session.players_found = [
        {'id': 1, 'player_id': 6, 'name': 'India', 'nation': '?', 'provinces': 1,
         'army_strength': 0, 'morale': 0, 'victory_points': 0, 'income': 0},
    ]
    output = GhostSpy().render_wars(session)
    assert 'belum mencatat' in output
    assert 'Peta relasi: 2 pasangan perang' in output
    assert 'India — 2 front' in output
    assert 'ID 14 — 1 front' in output


def test_render_wars_empty_reports_no_war():
    session = GhostSession(game_id=1, is_active=True)
    assert 'belum mencatat' in GhostSpy().render_wars(session)


async def test_ghost_wars_renders_battlefield(ghost_bot):
    ghost_bot.ghost_spy = FakeSpy()
    ghost_bot.ghost_spy.sessions[10925912].wars = wars_from_state(war_state())
    await ghost_bot.handle(update('/ghost wars 10925912'), None)
    sent = ghost_bot.app.bot.send_message.call_args.kwargs['text']
    assert 'MEDAN PERANG' in sent and 'India vs Belarus' in sent


def test_players_from_state_counts_military_buildings():
    names = {2270: 'Recruiting Office', 2275: 'Arms Industry',
             2255: 'Air Base', 9999: 'Crater'}
    raw = {'states': {
        '1': {'players': {'7': {'playerID': 7, 'userName': 'Saya',
                                'nationName': 'Indonesia', 'siteUserID': 111}}},
        '3': {'map': {'locations': ['', [
            {'id': 10, 'o': 7, 'm': 70,
             'us': ['', [{'id': 2270}, {'id': 2275}, {'id': 9999}, {'id': 'rusak'}, 'bukan-dict']]},
            {'id': 11, 'o': 7, 'm': 70, 'us': ['', [{'id': 2255}, {'id': 2270}]]},
        ]]}}}}
    players = players_from_state(raw, names)
    assert players[0]['military'] == {'recruit': 2, 'arms': 1, 'air': 1}
    assert players_from_state(raw)[0]['military'] == {}


def test_building_names_from_mod_reads_catalog():
    from sww3bot.ghostspy import building_names_from_mod
    raw = {'result': {'@c': 'ultshared.UltMod',
                      'upgrades': {'@c': 'java.util.HashMap',
                                   '2270': {'upgrName': 'Recruiting Office'},
                                   '2255': {'upn': 'Air Base'},
                                   '9999': {},
                                   '@c2': 'bukan-dict'}}}
    assert building_names_from_mod(raw) == {2270: 'Recruiting Office', 2255: 'Air Base'}
    assert building_names_from_mod({}) == {}
    assert building_names_from_mod(None) == {}


def test_mod_building_names_caches_per_game():
    calls = []

    class ModApi:
        def game_state(self, game_id, state_type=0, option=0):
            calls.append((game_id, state_type))
            return {'result': {'upgrades': {'2270': {'upgrName': 'Recruiting Office'}}}}

        def get_game_token(self, game_id):
            raise AssertionError('token tak dipakai di sini')

    spy = GhostSpy(web_api=ModApi())
    assert spy.mod_building_names(10925912) == {2270: 'Recruiting Office'}
    assert spy.mod_building_names(10925912) == {2270: 'Recruiting Office'}
    assert calls == [(10925912, 11)]
    assert GhostSpy(web_api=None).mod_building_names(1) == {}


def test_mod_building_names_retries_after_empty():
    calls = []

    class FlakyApi:
        def game_state(self, game_id, state_type=0, option=0):
            calls.append(game_id)
            if len(calls) == 1:
                raise ConnectionError('putus')
            return {'result': {'upgrades': {'2270': {'upgrName': 'Recruiting Office'}}}}

    spy = GhostSpy(web_api=FlakyApi())
    assert spy.mod_building_names(10925912) == {}
    assert spy.mod_building_names(10925912) == {2270: 'Recruiting Office'}
    assert calls == [10925912, 10925912]


def test_render_session_shows_military_production():
    session = GhostSession(game_id=10925912, game_server='xgs1.c.bytro.com', is_active=True)
    session.players_found = [
        {'id': 111, 'player_id': 7, 'name': 'Saya', 'nation': 'Indonesia',
         'provinces': 10, 'army_strength': 0, 'morale': 70, 'victory_points': 100,
         'income': 50, 'military': {'recruit': 2, 'arms': 1}},
        {'id': 222, 'player_id': 8, 'name': 'Pasif', 'nation': 'Chad',
         'provinces': 3, 'army_strength': 0, 'morale': 60, 'victory_points': 10,
         'income': 5, 'military': {}},
    ]
    output = GhostSpy().render_session(session)
    assert 'Produksi militer' in output
    assert 'rekrut x2' in output and 'senjata x1' in output
    assert 'Pasif' in output  # tetap tampil di tabel walau tanpa bangunan militer


def test_unit_name_resolves_known_and_unknown():
    assert unit_name(1) == 'Infantry'
    assert unit_name(9999) == 'Unit 9999'
    assert unit_name('rusak') == 'Unit rusak'


def test_render_session_shows_rich_intel():
    session = GhostSession(game_id=10925912, game_server='xgs1.c.bytro.com', is_active=True)
    session.players_found = players_from_state(rich_state())
    output = GhostSpy().render_session(session)
    assert 'VP' in output and 'Mrl' in output
    assert '150' in output  # victory points Saya
    assert 'Gerakan terdeteksi' in output
    assert 'Infantry' in output
    assert 'menyerang' in output
    assert 'Unit 9999' in output
    assert '†' in output  # defeated Musuh
    assert '[AI]' in output


class StubTokenApi:
    def __init__(self, payload):
        self.payload = payload

    def get_game_token(self, game_id):
        assert game_id == 10925912
        return self.payload


def test_infiltrate_parses_nested_token_shape():
    api = StubTokenApi({'resultCode': 0, 'resultMessage': 'ok',
                        'result': {'token': {'gs': 'congs5.c.bytro.com',
                                             'authHash': 'hash-live',
                                             'authTstamp': '1791804406'}}})
    session = GhostSpy(web_api=api).infiltrate_game(10925912)
    assert session.is_active
    assert session.game_server == 'congs5.c.bytro.com'
    assert session.auth_hash == 'hash-live'
    assert session.error_code == 0


def test_infiltrate_parses_flat_token_shape():
    api = StubTokenApi({'resultCode': 0, 'resultMessage': 'ok',
                        'result': {'gs': 'xgs1.c.bytro.com', 'authHash': 'h',
                                   'authTstamp': 1700000000, 'rights': {'read': True}}})
    session = GhostSpy(web_api=api).infiltrate_game(10925912)
    assert session.is_active
    assert session.rights == {'read': True}


def test_infiltrate_records_server_error():
    api = StubTokenApi({'resultCode': -70, 'resultMessage': 'parameter value is invalid',
                        'result': 'parameter value is invalid'})
    session = GhostSpy(web_api=api).infiltrate_game(10925912)
    assert not session.is_active
    assert session.error_code == -70
    assert 'invalid' in session.error


class DeadSpy(GhostSpy):
    def __init__(self):
        super().__init__(web_api=None)

    def infiltrate_game(self, game_id):
        session = GhostSession(game_id=game_id, error_code=-70,
                               error='parameter value is invalid')
        self.sessions[game_id] = session
        return session


async def test_ghost_spy_unknown_game_says_not_found(ghost_bot):
    ghost_bot.ghost_spy = DeadSpy()
    await ghost_bot.handle(update('/ghost spy 10928323'), None)
    sent = ghost_bot.app.bot.send_message.call_args.kwargs['text']
    assert 'tidak ditemukan' in sent and '10928323' in sent


async def test_ghost_spy_token_failure_keeps_generic_message(ghost_bot):
    ghost_bot.ghost_spy = FakeSpy()
    ghost_bot.ghost_spy.sessions[10925912].is_active = False
    await ghost_bot.handle(update('/ghost 10925912'), None)
    sent = ghost_bot.app.bot.send_message.call_args.kwargs['text']
    assert 'token tidak diterima' in sent


def test_build_live_spy_signs_as_uber_client(monkeypatch):
    import sww3bot.auth as auth_module
    import sww3bot.webapi as webapi_module
    import sww3bot.ghostspy as ghostspy_module
    from sww3bot.ghost_chat import build_live_spy
    captured = {}

    class FakeAuth:
        def __init__(self):
            self.user_id = 7
            self.uber_auth = 'UH'
            self.uber_tstamp = '123'
            self.session = SimpleNamespace(cookies={})

        def login(self, username, password):
            assert username == 'user' and password == 'pass'
            return {}

    class FakeWeb:
        def __init__(self, api_key='', auth_hash='', auth_tstamp='', user_id=0, **kwargs):
            captured.update(api_key=api_key, auth_hash=auth_hash,
                            auth_tstamp=auth_tstamp, user_id=user_id)
            self.session = SimpleNamespace(cookies={})

    class FakeSpyCtor:
        def __init__(self, web_api=None):
            captured['web_api'] = web_api

    monkeypatch.setattr(auth_module, 'BytroAuth', FakeAuth)
    monkeypatch.setattr(webapi_module, 'BytroWebAPI', FakeWeb)
    monkeypatch.setattr(ghostspy_module, 'GhostSpy', FakeSpyCtor)
    settings = SimpleNamespace(bot_user=SimpleNamespace(get_secret_value=lambda: 'user'),
                               bot_pass=SimpleNamespace(get_secret_value=lambda: 'pass'))
    build_live_spy(settings)
    assert captured['api_key'] == 'uberCon'
    assert captured['auth_hash'] == 'UH'
    assert captured['auth_tstamp'] == '123'
    assert captured['user_id'] == 7
    assert isinstance(captured['web_api']._web, FakeWeb)


def test_track_aggregates_vp_and_morale():
    spy = GhostSpy()
    first = GhostSession(game_id=1, game_server='xgs1.c.bytro.com', is_active=True)
    first.players_found = [
        {'id': 42, 'name': 'Target', 'nation': 'Niger', 'provinces': 20,
         'army_strength': 150, 'victory_points': 300, 'morale': 30},
    ]
    second = GhostSession(game_id=2, game_server='xgs2.c.bytro.com', is_active=True)
    second.players_found = [
        {'id': 42, 'name': 'Target', 'nation': 'Chad', 'provinces': 10,
         'army_strength': 50, 'victory_points': 100, 'morale': 20},
    ]
    spy.sessions[1] = first
    spy.sessions[2] = second
    intel = spy.track_player(42, 'Target')
    assert intel.total_vp == 400
    assert intel.avg_morale == 25
    assert 'Low morale — revolt risk' in intel.weaknesses_detected
    output = spy.render_cross_game_intel(intel)
    assert 'Total VP' in output and '400' in output
    assert 'Avg morale' in output
