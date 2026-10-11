"""Persistent building queue: enqueue, drain in order, cancel, recover."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from sww3bot.agent_engine import Runtime
from sww3bot.agent_store import Store
from sww3bot.agent_tools import GameExecutor, game_registry, queue_building
from sww3bot.game_session import GameSession


def raw_state():
    return {'states': {
        '3': {'map': {'locations': ['', [
            {'id': 10, 'o': 7, 'plv': 4, 'name': 'Abuja'},
            {'id': 11, 'o': 88, 'plv': 4, 'name': 'Lagos'},
        ]]}, 'properties': {}},
    }}


class QueueController:
    def __init__(self, raw):
        self.state = raw
        self.client = SimpleNamespace(player_id=7, session=MagicMock())
        self.sent = []

    def refresh_state(self):
        return self.state

    def _send_sub_action(self, sub):
        self.sent.append(sub)
        if sub.get('@c', '').endswith('UltUpdateProvinceAction'):
            for pid in sub['provinceIDs'][1]:
                city = next(p for p in self.state['states']['3']['map']['locations'][1] if p['id'] == pid)
                city['us'] = ['', [sub['upgrade']]]
        return {'result': {'actionResults': {'a': 1}}}

    def build_building(self, city, building):
        return self._send_sub_action({'@c': 'ultshared.action.UltUpdateProvinceAction', 'mode': 1,
                                      'provinceIDs': ['', [city]], 'upgrade': {'id': building}})


@pytest.fixture
def queue_executor(settings):
    executor = GameExecutor(settings)
    raw = raw_state()
    executor.sessions[42] = GameSession(42, 7, QueueController(raw), MagicMock(), raw)
    return executor


def rt(settings, store):
    return Runtime(store.new_task(42, 'test'), settings, store, AsyncMock())


def test_registry_has_build_queue_tools():
    registry = game_registry()
    names = {d['function']['name'] for d in registry.schemas()}
    assert {'queue_building', 'list_build_queue', 'cancel_build_queue', 'process_build_queue'} <= names
    tool, args = registry.validate('queue_building', {'city_id': 10, 'building_type': 'barracks'})
    assert tool is not None and args == {'city_id': 10, 'building_type': 'barracks'}
    assert not tool.mutates is False
    read_tool, _ = registry.validate('list_build_queue', {})
    assert read_tool is not None and read_tool.mutates is False
    for name, args in [('queue_building', {'city_id': 0, 'building_type': 'x'}),
                       ('queue_building', {'city_id': 10, 'building_type': ''}),
                       ('cancel_build_queue', {'queue_id': 0}),
                       ('process_build_queue', {'limit': 0})]:
        tool, error = registry.validate(name, args)
        assert tool is None
        assert error.error['code'] == 'invalid_arguments'


def test_enqueue_dedup_list_cancel_and_recover(store):
    first = store.enqueue_build(42, 10, 'Barracks')
    assert first['position'] == 1
    duplicate = store.enqueue_build(42, 10, 'barracks')
    assert duplicate['queued'] is False
    assert duplicate['queue_id'] == first['queue_id']
    second = store.enqueue_build(42, 10, 'Radar')
    assert second['position'] == 2
    pending = store.pending_builds(42)
    assert [p['id'] for p in pending] == [first['queue_id'], second['queue_id']]
    assert store.cancel_queued_build(second['queue_id'], 42) is True
    assert store.cancel_queued_build(9999, 42) is False
    assert [p['id'] for p in store.pending_builds(42)] == [first['queue_id']]
    store.set_build_status(first['queue_id'], 'building')
    assert store.pending_builds(42) == []
    store.recover()
    assert [p['id'] for p in store.pending_builds(42)] == [first['queue_id']]
    history = store.builds(42)
    assert {b['status'] for b in history} == {'queued', 'cancelled'}


def test_queue_tool_needs_running_agent(store):
    with pytest.raises(RuntimeError, match='bot'):
        queue_building(10, 'barracks')


async def test_process_queue_builds_in_order(queue_executor, settings, store):
    runtime = rt(settings, store)
    first = await queue_executor.execute(42, 'queue_building', {'city_id': 10, 'building_type': 'recruiting_office'}, runtime)
    second = await queue_executor.execute(42, 'queue_building', {'city_id': 10, 'building_type': 'barracks'}, runtime)
    assert first.ok and second.ok
    assert first.data['position'] == 1
    assert second.data['position'] == 2
    listed = await queue_executor.execute(42, 'list_build_queue', {}, runtime)
    assert listed.ok and len(listed.data['pending']) == 2
    done = await queue_executor.execute(42, 'process_build_queue', {}, runtime)
    assert done.ok
    assert done.data['done'] == [first.data['queue_id'], second.data['queue_id']]
    assert done.data['remaining'] == 0
    sent = queue_executor.session(42).ctrl.sent
    assert [s['mode'] for s in sent] == [1, 1]
    assert [s['upgrade']['id'] for s in sent] == [2245, 2270]
    assert store.pending_builds(42) == []
    # One journal step per send: nested sends must not be double-guarded.
    assert [s['status'] for s in store.steps(runtime.task_id)].count('completed') == 2


async def test_process_queue_skips_failed_and_continues(queue_executor, settings, store):
    runtime = rt(settings, store)
    foreign = await queue_executor.execute(42, 'queue_building', {'city_id': 11, 'building_type': 'barracks'}, runtime)
    assert not foreign.ok
    store.enqueue_build(42, 11, 'barracks')
    store.enqueue_build(42, 10, 'kantor_hantu')
    done = await queue_executor.execute(42, 'process_build_queue', {}, runtime)
    assert done.ok
    assert done.data['done'] == []
    assert len(done.data['failed']) == 2
    assert done.data['remaining'] == 0
    assert queue_executor.session(42).ctrl.sent == []


async def test_process_queue_marks_already_built_done(queue_executor, settings, store):
    raw = queue_executor.session(42).raw
    city = next(p for p in raw['states']['3']['map']['locations'][1] if p['id'] == 10)
    city['us'] = ['', [{'id': 2270}]]
    runtime = rt(settings, store)
    queued = await queue_executor.execute(42, 'queue_building', {'city_id': 10, 'building_type': 'barracks'}, runtime)
    assert queued.ok
    done = await queue_executor.execute(42, 'process_build_queue', {}, runtime)
    assert done.ok
    assert done.data['skipped'] == [queued.data['queue_id']]
    assert queue_executor.session(42).ctrl.sent == []
