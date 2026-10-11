import copy
import json
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from sww3bot.agent_engine import Runtime
from sww3bot.agent_store import Store
from sww3bot.agent_tools import GameExecutor, game_registry
from sww3bot.catalog import Catalog
from sww3bot.commander import cycle, defensive_moves, economy_plan, plan
from sww3bot.commander_queue import observed, readiness, reconcile
from sww3bot.commander_state import Budget, snapshot, unit_inventory, unit_totals
from sww3bot.game_session import GameSession


def raw():
    entries = {str(rid): {'amount0': 10000, 'time0': 1000, 'rate': 0, 'production': 1000}
               for rid in (1, 2, 3, 4, 5, 6, 20)}
    return {'timeStamp': '1000', 'states': {
        '1': {'players': {'7': {'playerID': 7, 'nationName': 'Indonesia'}}},
        '3': {'map': {'locations': ['', [
            {'id': 10, 'o': 7, 'plv': 5, 'm': 70, 'c': {'x': 0, 'y': 0}, 'us': ['', []], 'cos': ['', []], 'prs': ['', []]},
            {'id': 20, 'o': 7, 'plv': 5, 'm': 70, 'c': {'x': 50, 'y': 0}, 'us': ['', []], 'cos': ['', []], 'prs': ['', []]},
            {'id': 30, 'o': 7, 'plv': 1, 'm': 70, 'c': {'x': 25, 'y': 0}},
            {'id': 40, 'o': 88, 'plv': 5, 'm': 70, 'c': {'x': 100, 'y': 0}},
        ]]}, 'properties': {str(cid): {'queueableUpgrades': ['', [{'id': 100}, {'id': 101}]],
                                       'queueableProductions': ['', [{'unit': {'t': 201, 'id': 9000 + cid}}]]}
                             for cid in (10, 20)}},
        '4': {'resourceProfs': {'7': {'categories': {'0': {'resourceEntries': entries}}}}},
        '5': {'relations': {'neighborRelations': {'7': {}}}},
        '6': {'armies': {'1': {'id': 1, 'o': 7, 's': 1, 'l': 10, 'p': {'x': 0, 'y': 0}, 'c': ['', []],
                               'u': ['', [{'id': 500, 't': 201, 's': 1, 'hp': 20}]]},
                         '999': {'id': 999, 'o': 88, 's': 9, 'l': 40, 'u': ['', [{'id': 9999, 't': 201, 's': 9}]]}}},
        '12': {'dayOfGame': 3, 'timeScale': .25},
        '23': {'researchSlots': 1, 'currentResearches': ['', []], 'completedResearches': {'90': {}}},
    }}


def catalog():
    return Catalog([
        {'itemID': 100, '@c': 'UltUpgradeType', 'upgrName': 'Arms Industry', 'costs': 'a20=1000,a5=100'},
        {'itemID': 101, '@c': 'UltUpgradeType', 'upgrName': 'Recruiting Office', 'costs': 'a20=500'},
        {'itemID': 201, '@c': 'UltUnitType', 'unitName': 'Motorized Infantry', 'unitClass': 0,
         'costs': 'a20=500,a1=100', 'dailyCosts': 'a20=50', 'requiredResearches': 'a90=1'},
        {'itemID': 202, '@c': 'UltUnitType', 'unitName': 'Motorized Infantry', 'unitClass': 0,
         'costs': 'a20=500', 'requiredResearches': 'a91=1'},
        {'itemID': 90, '@c': 'UltResearchType', 'name': 'Motorized Infantry EU', 'costs': 'a20=100', 'dayAvailable': 1},
        {'itemID': 91, '@c': 'UltResearchType', 'name': 'Motorized Infantry EU', 'costs': 'a20=500,a4=100',
         'dayAvailable': 2, 'requiredResearches': 'a90=1'},
    ])


class Controller:
    def __init__(self, state):
        self.state = state
        self.catalog = catalog()
        self.client = SimpleNamespace(player_id=7, session=MagicMock())
        self.sent = []
        self.reject = False

    def refresh_state(self):
        self.state['timeStamp'] = str(int(self.state['timeStamp']) + 100)
        return self.state

    def city(self, cid):
        return next(c for c in self.state['states']['3']['map']['locations'][1] if c['id'] == cid)

    def _send_sub_action(self, sub):
        self.sent.append(copy.deepcopy(sub))
        if self.reject:
            return {'result': {'actionResults': {'a': -1}}}
        clock = int(self.state['timeStamp']) + 1
        if sub['@c'].endswith('UltUpdateProvinceAction'):
            for cid in sub['provinceIDs'][1]:
                field = 'cos' if sub['mode'] == 1 else 'prs'
                self.city(cid)[field] = ['', [{'u': copy.deepcopy(sub['upgrade']), 's': clock, 't': clock + 100000}]]
        elif sub['@c'].endswith('UltResearchAction'):
            self.state['states']['23']['currentResearches'] = ['', [
                {'researchTypeID': sub['researchID'], 'startTime': clock, 'endTime': clock + 100000}]]
        else:
            for a in sub['armies'][1]:
                self.state['states']['6']['armies'][str(a['id'])]['c'] = copy.deepcopy(a['c'])
        return {'result': {'actionResults': {'a': 1}}}

    def build_building(self, cid, iid):
        return self._send_sub_action({'@c': 'ultshared.action.UltUpdateProvinceAction', 'mode': 1,
                                     'provinceIDs': ['', [cid]], 'upgrade': {'id': iid, 'built': False, 'cn': True}})

    def produce_unit(self, cid, iid):
        return self._send_sub_action({'@c': 'ultshared.action.UltUpdateProvinceAction', 'mode': 2,
                                     'provinceIDs': ['', [cid]], 'upgrade': {'unit': {'t': iid, 'id': 10000 + len(self.sent)}}})

    def research(self, iid):
        return self._send_sub_action({'@c': 'ultshared.action.UltResearchAction', 'researchID': iid})

    def move_army(self, aid, cid):
        return self._send_sub_action({'@c': 'ultshared.action.UltArmyAction', 'armies': ['', [
            {'id': aid, 'c': ['', [{'@c': 'gc', 'at': 99999, 'tp': self.city(cid)['c']}]]}]]})


@pytest.fixture
def commander_executor(settings):
    from sww3bot.exploits import GameExploits
    state = raw()
    ctrl = Controller(state)
    executor = GameExecutor(settings)
    executor.sessions[42] = GameSession(42, 7, ctrl, GameExploits(ctrl), state)
    return executor


def runtime(settings, store):
    return Runtime(store.new_task(42, 'commander'), settings, store, AsyncMock())


async def test_build_dependency_waits_for_completion_not_eta_or_acceptance(commander_executor, settings, store):
    first = store.enqueue_commander(42, 7, 'build', {'city_id': 10, 'item_id': 100})
    second = store.enqueue_commander(42, 7, 'produce', {'city_id': 10, 'item_id': 201}, [first['id']])
    await cycle(commander_executor, store, runtime(settings, store), {'game_id': 42})
    assert store.commander_node(first['id'], 42)['state'] == 'accepted'
    assert store.commander_node(second['id'], 42)['state'] == 'waiting_prerequisite'
    ctrl = commander_executor.session(42).ctrl
    ctrl.city(10)['cos'][1][0]['t'] = 1  # ETA passed, but building remains unfinished.
    await cycle(commander_executor, store, runtime(settings, store), {'game_id': 42})
    assert len(ctrl.sent) == 1
    ctrl.city(10)['cos'] = ['', []]
    ctrl.city(10)['us'] = ['', [{'id': 100, 'built': True}]]
    await cycle(commander_executor, store, runtime(settings, store), {'game_id': 42})
    assert store.commander_node(first['id'], 42)['state'] == 'completed'
    assert store.commander_node(second['id'], 42)['state'] == 'accepted'
    assert len(ctrl.sent) == 2


async def test_production_completion_requires_output_and_is_city_specific(commander_executor, settings, store):
    a = store.enqueue_commander(42, 7, 'produce', {'city_id': 10, 'item_id': 201})
    b = store.enqueue_commander(42, 7, 'produce', {'city_id': 20, 'item_id': 201})
    await cycle(commander_executor, store, runtime(settings, store), {'game_id': 42})
    session = commander_executor.session(42)
    ctrl = session.ctrl
    output = ctrl.city(20)['prs'][1][0]['u']['unit']
    ctrl.city(20)['prs'] = ['', []]
    ctrl.city(10)['prs'] = ['', []]  # Could be a cancellation; free slot is not success.
    session.raw['states']['6']['armies']['2'] = {'id': 2, 'o': 7, 'l': 20, 'p': {'x': 50, 'y': 0},
                                               'u': ['', [dict(output, s=1, hp=20)]]}
    reconcile(session, store, 42)
    assert store.commander_node(b['id'], 42)['state'] == 'completed'
    assert store.commander_node(a['id'], 42)['state'] == 'accepted'


def test_existing_army_arrival_never_counts_as_production(commander_executor):
    session = commander_executor.session(42)
    baseline = {'unit_totals': unit_totals(session.raw, 7), 'units': unit_inventory(session.raw, 7), 'game_time': 1000}
    node = {'kind': 'produce', 'args': {'city_id': 20, 'item_id': 201}, 'baseline': baseline}
    session.raw['states']['6']['armies']['1']['l'] = 20
    assert observed(session, node) is None


async def test_research_queue_tracks_actual_completion(commander_executor, settings, store):
    node = store.enqueue_commander(42, 7, 'research', {'item_id': 91})
    await cycle(commander_executor, store, runtime(settings, store), {'game_id': 42})
    assert store.commander_node(node['id'], 42)['state'] == 'accepted'
    state = commander_executor.session(42).raw['states']['23']
    state['currentResearches'] = ['', []]
    state['completedResearches']['91'] = {}
    reconcile(commander_executor.session(42), store, 42)
    assert store.commander_node(node['id'], 42)['state'] == 'completed'


def test_restart_recovers_dispatching_without_resending(tmp_path):
    path = str(tmp_path / 'queue.db')
    first = Store(path)
    node = first.enqueue_commander(42, 7, 'build', {'city_id': 10, 'item_id': 100})
    first.set_commander_node(node['id'], 'dispatching', baseline={'game_time': 1000})
    first.close()
    second = Store(path)
    second.recover()
    assert second.commander_node(node['id'], 42)['state'] == 'outcome_unknown'
    second.close()


def test_budget_reserves_whole_plan_and_does_not_double_debit_accepted(commander_executor, store):
    budget = Budget({'Money': {'amount': 2500}}, {'Money': 1000})
    assert budget.reserve({'Money': 1000})
    assert not budget.reserve({'Money': 500})
    one = store.enqueue_commander(42, 7, 'build', {'city_id': 10, 'item_id': 100})
    two = store.enqueue_commander(42, 7, 'research', {'item_id': 91})
    store.set_commander_node(one['id'], 'accepted')
    report = economy_plan(commander_executor.session(42), store.commander_nodes(42))
    assert report['resources']['Money']['planned_cost_with_margin'] == 625
    assert two['id'] in report['fundable_nodes']


def test_defense_preserves_last_garrison_and_low_morale_territory(commander_executor):
    session = commander_executor.session(42)
    assert defensive_moves(session) == []
    spare = copy.deepcopy(session.raw['states']['6']['armies']['1'])
    spare.update(id=2, l=30, p={'x': 25, 'y': 0})
    spare['u'][1][0]['id'] = 501
    session.raw['states']['6']['armies']['2'] = spare
    assert defensive_moves(session) == [{'army_id': 2, 'target_province': 20}]
    session.ctrl.city(30)['m'] = 30
    assert defensive_moves(session) == []


def test_events_are_durable_deduplicated_and_never_include_hidden_units(commander_executor, store):
    session = commander_executor.session(42)
    before = snapshot(session)
    assert '999' not in before['armies']
    assert before['unit_totals'] == {'201': 1}
    assert store.observe_commander(42, before) == []
    session.ctrl.city(20)['o'] = 88
    after = snapshot(session)
    events = store.observe_commander(42, after)
    assert ('city_lost', {'city_id': 20}) in events
    assert store.observe_commander(42, after) == []
    assert len(store.commander_events(42)) == len(events)


async def test_unverified_or_rejected_action_is_not_retried(commander_executor, settings, store):
    executor = commander_executor
    executor.session(42).ctrl.reject = True
    config = {'enabled': True, 'game_id': 42, 'player_id': 7, 'mode': 'commander',
              'started_at': time.time(), 'deadline': time.time() + 3600}
    store.set_preference('overnight_control', config)
    await cycle(executor, store, runtime(settings, store), config)
    assert not store.preference('overnight_control')['enabled']
    sent = len(executor.session(42).ctrl.sent)
    await cycle(executor, store, runtime(settings, store), {'game_id': 42})
    assert len(executor.session(42).ctrl.sent) == sent


async def test_strict_native_queue_tool_validates_targets_and_dependencies(commander_executor, settings, store):
    registry = game_registry()
    assert registry.validate('queue_game_action', {'action': {'kind': 'produce', 'item_id': 201, 'city_id': 10}, 'quantity': 2})[0]
    assert registry.validate('queue_game_action', {'action': {'kind': 'move', 'city_id': 10}})[0] is None
    rt = runtime(settings, store)
    result = await commander_executor.execute(42, 'queue_game_action', {
        'action': {'kind': 'produce', 'item_id': 201, 'city_id': 10}, 'quantity': 2}, rt)
    assert result.ok
    ids = result.data['node_ids']
    assert store.commander_node(ids[1], 42)['dependencies'] == [ids[0]]
    foreign = await commander_executor.execute(42, 'queue_game_action', {
        'action': {'kind': 'build', 'item_id': 100, 'city_id': 40}}, rt)
    assert not foreign.ok
    assert commander_executor.session(42).ctrl.sent == []


def test_data_unknown_or_insufficient_resources_holds_queue(commander_executor, store):
    session = commander_executor.session(42)
    node = store.enqueue_commander(42, 7, 'produce', {'city_id': 10, 'item_id': 201})
    session.raw['states']['4']['resourceProfs']['7']['categories']['0']['resourceEntries']['20']['amount0'] = 100
    assert readiness(session, node, [node])[0] == 'waiting_resources'
    session.raw['states']['3']['properties'] = {}
    assert readiness(session, node, [node])[0] == 'waiting_prerequisite'


async def test_expired_nodes_are_not_sent(commander_executor, settings, store):
    node = store.enqueue_commander(42, 7, 'build', {'city_id': 10, 'item_id': 100}, source='auto:123')
    await cycle(commander_executor, store, runtime(settings, store),
                {'enabled': True, 'game_id': 42, 'player_id': 7, 'mode': 'commander', 'started_at': 123, 'deadline': 1})
    assert store.commander_node(node['id'], 42)['state'] == 'expired'
    assert commander_executor.session(42).ctrl.sent == []

async def test_queue_pause_prevents_new_dispatch(commander_executor, settings, store):
    store.enqueue_commander(42, 7, 'build', {'city_id': 10, 'item_id': 100})
    store.set_preference('commander_paused:42', True)
    await cycle(commander_executor, store, runtime(settings, store), {'game_id': 42})
    assert not commander_executor.session(42).ctrl.sent

async def test_resource_change_at_final_guard_holds_send(commander_executor, settings, store):
    node = store.enqueue_commander(42, 7, 'build', {'city_id': 10, 'item_id': 100})
    ctrl = commander_executor.session(42).ctrl
    original = ctrl.refresh_state
    calls = 0
    def refresh():
        nonlocal calls
        calls += 1
        if calls >= 2:
            ctrl.state['states']['4']['resourceProfs']['7']['categories']['0']['resourceEntries']['20']['amount0'] = 100
        return original()
    ctrl.refresh_state = refresh
    await cycle(commander_executor, store, runtime(settings, store), {'game_id': 42})
    assert not ctrl.sent
    assert store.commander_node(node['id'], 42)['state'] in ('queued', 'waiting_resources')

async def test_recovered_production_captures_future_unit_identity(commander_executor, settings, store):
    node = store.enqueue_commander(42, 7, 'produce', {'city_id': 10, 'item_id': 201})
    await cycle(commander_executor, store, runtime(settings, store), {'game_id': 42})
    accepted = store.commander_node(node['id'], 42)
    accepted['baseline'].pop('production_unit_id')
    store.set_commander_node(node['id'], 'outcome_unknown', baseline=accepted['baseline'])
    reconcile(commander_executor.session(42), store, 42)
    recovered = store.commander_node(node['id'], 42)
    assert recovered['state'] == 'accepted'
    assert recovered['baseline']['production_unit_id']
