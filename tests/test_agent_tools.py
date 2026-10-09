import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
import requests

from api import actions
from api._conn import discover_player, get_players
from sww3bot.agent_engine import Runtime
from sww3bot.agent_store import Store
from sww3bot.agent_tools import GameExecutor, Registry, game_registry
from sww3bot.game_session import GameSession, bind_session
from sww3bot.instance_lock import InstanceLock


def raw_state(player=7):
    return {'states': {
        '1': {'players': {'7': {'playerID': 7, 'userID': 123, 'name': 'test-account', 'nationName': 'Nigeria'},
                          '88': {'playerID': 88, 'userID': 999, 'nationName': 'Niger'},
                          '8': {'playerID': 8, 'nationName': 'Sudan'},
                          '9': {'playerID': 9, 'nationName': 'South Sudan'}}},
        '3': {'map': {'locations': ['', [
            {'id': 10, 'o': player, 'plv': 4, 'name': 'Abuja', 'c': {'x': 0, 'y': 0}},
            {'id': 11, 'o': 88, 'plv': 4, 'name': 'Lagos', 'c': {'x': 1, 'y': 1}},
            {'id': 12, 'o': 8, 'plv': 4, 'name': 'Springfield', 'c': {'x': 2, 'y': 2}},
            {'id': 13, 'o': 9, 'plv': 4, 'name': 'Springfield', 'c': {'x': 3, 'y': 3}},
        ]]}, 'properties': {}},
        '6': {'armies': {'1': {'o': player, 's': 1, 'p': {}, 'u': ['', []]},
                         '2': {'o': 88, 's': 1, 'p': {}, 'u': ['', []]}}},
        '5': {'relations': {'neighborRelations': {str(player): {'8': -2}}}},
    }}


class Controller:
    def __init__(self, raw):
        self.state = raw
        self.client = SimpleNamespace(player_id=7, session=MagicMock())
        self.sent = []
        self.on_send = None
        self.fail = False

    def refresh_state(self):
        return self.state

    def _send_sub_action(self, sub):
        self.sent.append(sub)
        if self.fail:
            raise requests.Timeout('network gone')
        if self.on_send:
            self.on_send()
        return {'result': {'actionResults': {'a': 1}}}

    def move_army(self, army, target):
        return self._send_sub_action({'@c': 'Move', 'army': army, 'target': target})

    def build_building(self, city, building):
        return self._send_sub_action({'@c': 'Build', 'city': city, 'building': building})


@pytest.fixture
def executor(settings):
    executor = GameExecutor(settings)
    raw = raw_state()
    controller = Controller(raw)
    ge = MagicMock()
    ge.get_resources.return_value = {}
    ge.get_goldmark.return_value = 0
    executor.sessions[42] = GameSession(42, 7, controller, ge, raw)
    return executor


def rt(settings, store):
    return Runtime(store.new_task(42, 'test'), settings, store, AsyncMock())


def test_registry_required_optional_types_and_no_extra_args():
    registry = game_registry()
    definitions = {d['function']['name']: d['function']['parameters'] for d in registry.schemas()}
    assert definitions['deploy_spy']['required'] == ['province_id']
    assert definitions['move_army']['additionalProperties'] is False
    for args in ({'army_id': '1', 'target_province': 10}, {'army_id': True, 'target_province': 10},
                 {'army_id': 1, 'target_province': -1}, {'army_id': 1, 'target_province': 10, 'extra': 1}):
        tool, error = registry.validate('move_army', args)
        assert tool is None
        assert error.error['code'] == 'invalid_arguments'
    assert registry.validate('deploy_spy', {'province_id': 10})[1]['mission_type'] == 0
    assert registry.validate('declare_war', {'player_id': 8})[0] is not None
    assert registry.validate('buy_market_resource', {'resource': 'metal', 'amount': 0})[0] is None


async def test_nondefault_player_status_and_context_isolation(executor, settings, store):
    result = await executor.execute(42, 'get_status', {}, rt(settings, store))
    assert result.ok
    assert result.data['provinces'] == 1
    assert [a['id'] for a in result.data['armies']] == [1]
    assert [c['id'] for c in result.data['cities']] == [10]
    other = GameSession(43, 88, executor.session(42).ctrl, executor.session(42).ge, raw_state())
    with bind_session(other):
        assert actions._player_id() == 88
    assert executor.session(42).player_id == 7


async def test_preflight_prevents_other_players_army_and_city(executor, settings, store):
    for name, args in [('move_army', {'army_id': 2, 'target_province': 10}),
                       ('build_building', {'city_id': 11, 'building_type': 'army_base'}),
                       ('move_army', {'army_id': 1, 'target_province': 999})]:
        result = await executor.execute(42, name, args, rt(settings, store))
        assert not result.ok
    assert executor.session(42).ctrl.sent == []


async def test_journal_before_send_and_successful_mutation(executor, settings, store):
    runtime = rt(settings, store)
    def on_send():
        assert store.steps(runtime.task_id)[0]['status'] == 'started'
    # SQLite stays on the event loop: examine through action_event rather than worker.
    events = []
    original = runtime.action_event
    async def record(event, **data):
        events.append(event)
        return await original(event, **data)
    runtime.action_event = record
    result = await executor.execute(42, 'move_army', {'army_id': 1, 'target_province': 12}, runtime)
    assert result.ok
    assert events == ['start', 'finish']
    assert store.steps(runtime.task_id)[0]['status'] == 'completed'
    assert len(executor.session(42).ctrl.sent) == 1


async def test_unknown_network_result_stops_composite_without_retry(executor, settings, store):
    runtime = rt(settings, store)
    executor.session(42).ctrl.fail = True
    result = await executor.execute(42, 'build_in_all_cities', {'building_type': 'army_base'}, runtime)
    assert result.error['code'] == 'interrupted'
    assert len(executor.session(42).ctrl.sent) == 1
    assert store.steps(runtime.task_id)[0]['status'] == 'unknown'


async def test_cancel_composite_after_first_mutation(executor, settings, store):
    runtime = rt(settings, store)
    executor.session(42).raw['states']['3']['map']['locations'][1][1]['o'] = 7
    executor.session(42).ctrl.on_send = runtime.cancelled.set
    result = await executor.execute(42, 'build_in_all_cities', {'building_type': 'army_base'}, runtime)
    assert result.error['code'] == 'cancelled'
    assert len(executor.session(42).ctrl.sent) == 1
    assert store.steps(runtime.task_id)[0]['status'] == 'completed'


async def test_mutation_budget_inside_composite(executor, settings, store):
    settings.max_tools = 1
    executor.session(42).raw['states']['3']['map']['locations'][1][1]['o'] = 7
    runtime = rt(settings, store)
    result = await executor.execute(42, 'build_in_all_cities', {'building_type': 'army_base'}, runtime)
    assert result.error['code'] == 'limited'
    assert len(executor.session(42).ctrl.sent) == 1


async def test_ambiguous_city_returns_choices_and_no_mutation(executor, settings, store):
    result = await executor.execute(42, 'resolve_target', {'kind': 'city', 'query': 'Springfield'}, rt(settings, store))
    assert result.error['code'] == 'ambiguous'
    assert result.error['field'] == 'city_id'
    assert [c['id'] for c in result.error['candidates']] == [12, 13]
    assert executor.session(42).ctrl.sent == []


async def test_partial_country_resolution_never_picks_first(executor, settings, store):
    result = await executor.execute(42, 'declare_war', {'player_id': 'Suda'}, rt(settings, store))
    assert result.error['code'] == 'ambiguous'
    assert len(result.error['candidates']) == 2
    assert executor.session(42).ctrl.sent == []


def test_discover_player_identity_and_reject_mismatch():
    assert discover_player(raw_state(), 123, 'test-account') == 7
    with pytest.raises(ValueError):
        discover_player(raw_state(), 123, 'test-account', configured=88)
    with pytest.raises(ValueError):
        discover_player(raw_state(), 987, 'unknown')
    with pytest.raises(ValueError):
        discover_player(raw_state(), 987, 'unknown', configured=88)


def test_get_players_normalizes_dictionary_keys():
    assert get_players({'states': {'1': {'players': {'7': {'name': 'abc'}}}}}) == {7: {'name': 'abc'}}


def test_store_recovery_persistence_dedupe_and_waiting(tmp_path):
    path = str(tmp_path / 'bot.sqlite3')
    store = Store(path)
    task = store.new_task(42, 'move')
    store.finish_task(task, 'running')
    step = store.start_step(task, 'Move', {})
    waiting = store.new_task(42, 'choice')
    store.finish_task(waiting, 'waiting')
    store.set_preference('game_id', 42)
    assert store.accept_update(1)
    assert not store.accept_update(1)
    store.close()
    store = Store(path)
    store.recover()
    assert store.task(task)['status'] == 'interrupted'
    assert store.steps(task)[0]['status'] == 'unknown'
    assert store.task(waiting)['status'] == 'waiting'
    assert store.preference('game_id') == 42
    assert not store.accept_update(1)
    store.close()


def test_single_instance_lock(tmp_path):
    path = str(tmp_path / 'bot.sqlite3')
    lock = InstanceLock(path)
    try:
        with pytest.raises(ValueError):
            InstanceLock(path)
    finally:
        lock.close()
    InstanceLock(path).close()


async def test_known_zero_result_is_rejection_not_unknown(executor, settings, store):
    controller = executor.session(42).ctrl
    controller._send_sub_action = lambda sub: {'result': {'actionResults': {'a': 0}}}
    runtime = rt(settings, store)
    result = await executor.execute(42, 'move_army', {'army_id': 1, 'target_province': 12}, runtime)
    assert not result.ok
    assert result.error['code'] == 'action_failed'
    assert store.steps(runtime.task_id)[0]['status'] == 'failed'


async def test_successful_send_then_failed_refresh_retains_success(executor, settings, store):
    controller = executor.session(42).ctrl
    calls = 0
    original = controller.refresh_state
    def refresh():
        nonlocal calls
        calls += 1
        if calls >= 3:
            raise requests.Timeout('offline')
        return original()
    controller.refresh_state = refresh
    runtime = rt(settings, store)
    result = await executor.execute(42, 'move_army', {'army_id': 1, 'target_province': 12}, runtime)
    assert result.error['code'] == 'interrupted'
    assert store.steps(runtime.task_id)[0]['status'] == 'completed'
    assert len(controller.sent) == 1


def test_recovery_adds_action_evidence_to_history(store):
    task = store.new_task(42, 'move')
    store.finish_task(task, 'running')
    step = store.start_step(task, 'Move', {'army': 1, 'target': 12})
    store.finish_step(step, {'ok': True})
    store.save_history(42, [{'role': 'user', 'content': 'move'}])
    store.recover()
    assert 'Pemulihan tugas' in store.history(42)[-1]['content']
    assert 'completed' in store.history(42)[-1]['content']
    assert 'target' in store.history(42)[-1]['content']
    length = len(store.history(42))
    store.recover()
    assert len(store.history(42)) == length


def test_all_cli_adapters_parse_and_entrypoint_help_runs():
    import ast
    import subprocess
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    for path in (root / 'api').glob('*.py'):
        ast.parse(path.read_text(), filename=str(path))
    for path in ('api/agent.py', 'api/games.py'):
        process = subprocess.run([sys.executable, path, '--help'], cwd=root, capture_output=True, text=True)
        assert process.returncode == 0, process.stderr
        assert 'usage:' in process.stdout


async def test_cancel_during_progress_before_send_does_not_send(executor, settings, store):
    runtime = rt(settings, store)
    async def cancel_on_progress(text):
        runtime.cancelled.set()
    runtime.notify = cancel_on_progress
    result = await executor.execute(42, 'move_army', {'army_id': 1, 'target_province': 12}, runtime)
    assert result.error['code'] == 'cancelled'
    assert executor.session(42).ctrl.sent == []
    assert store.steps(runtime.task_id)[0]['status'] == 'cancelled'
