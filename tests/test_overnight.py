import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from sww3bot.agent_engine import Runtime
from sww3bot.agent_tools import TaskStop
from sww3bot.catalog import Catalog
from sww3bot.overnight import RESERVES, affordable, candidates, cycle


def test_resource_amount_uses_server_game_time_and_caps():
    from sww3bot.protocol import resource_amount
    assert resource_amount({'amount0': 10, 'time0': 1000, 'rate': 2}, 2000) == 12
    assert resource_amount({'amount0': 10, 'time0': 1000, 'rate': 2, 'maxAmount': 11}, 2000) == 11
    assert resource_amount({'amount0': 10, 'time0': 1000, 'rate': -20}, 2000) == 0
    assert resource_amount({'amount0': 10, 'time0': 1000, 'rate': 2}, 500) == 10


def session():
    catalog = Catalog([
        {'itemID': 2275, '@c': 'UltUpgradeType', 'upgrName': 'Arms Industry', 'costs': 'a20=1250,a5=350'},
        {'itemID': 2245, '@c': 'UltUpgradeType', 'upgrName': 'Population level 6'},
        {'itemID': 2270, '@c': 'UltUpgradeType', 'upgrName': 'Recruiting Office'},
    ])
    resources = {k: {'amount': v + 10000} for k, v in RESERVES.items()}
    city = {'id': 10, 'o': 7, 'plv': 5, 'us': ['', []],
            'cos': ['', [{'u': {'id': 2245}}]]}
    raw = {'states': {'3': {'map': {'locations': ['', [city]]},
                           'properties': {'10': {'queueableUpgrades': ['', [{'id': 2275}]]}}}}}
    return SimpleNamespace(player_id=7, raw=raw, ctrl=SimpleNamespace(catalog=catalog),
                           ge=SimpleNamespace(get_resources=lambda: resources))


def test_costs_require_known_resources_and_reserve():
    resources = {'Money': {'amount': 2250}}
    assert not affordable({'costs': 'a20=1250'}, resources)
    resources['Money']['amount'] = 3000
    assert affordable({'costs': 'a20=1250'}, resources)
    for costs in ('', 'a0=5', 'a20=-5', 'bad', 'a20=1,a999=1'):
        assert not affordable({'costs': costs}, resources)
    assert not affordable({'costs': 'a20=1', 'costsFunction': 'dynamic'}, resources)


def test_candidates_wait_for_slot_and_skip_existing_or_foreign_city():
    live = session()
    assert candidates(live) == [{'city_id': 10, 'building_type': '2275'}]
    city = live.raw['states']['3']['map']['locations'][1][0]
    city['cos'][1].append({'u': {'id': 2270}})
    assert candidates(live) == []
    city['cos'][1].pop()
    city['us'] = ['', [{'id': 2275, 'built': False}]]
    assert candidates(live) == []
    city['us'] = ['', []]
    city['o'] = 88
    assert candidates(live) == []


def test_deadline_stops_actions(settings, store):
    runtime = Runtime(store.new_task(42, 'overnight'), settings, store, AsyncMock())
    runtime.deadline = time.time() - 1
    with pytest.raises(TaskStop):
        runtime.checkpoint(mutation=True)


async def test_unknown_action_disables_autonomy(settings, store):
    from sww3bot.agent_tools import ToolResult
    live = session()
    executor = SimpleNamespace(session=lambda gid: live, execute=AsyncMock(side_effect=[
        ToolResult(ok=True, data={}),
        ToolResult(ok=False, error={'code': 'interrupted', 'message': 'unknown'}),
    ]))
    config = {'enabled': True, 'game_id': 42, 'player_id': 7,
              'deadline': time.time() + 3600, 'started_at': time.time()}
    store.set_preference('overnight_control', config)
    runtime = Runtime(store.new_task(42, 'overnight'), settings, store, AsyncMock())
    result = await cycle(executor, store, runtime, config)
    assert result.status == 'failed'
    assert store.preference('overnight_control')['enabled'] is False
    assert executor.execute.call_count == 2


async def test_cancelled_control_not_reenabled_by_cycle(settings, store):
    from sww3bot.agent_tools import ToolResult
    live = session()
    live.ge.get_resources = lambda: {}
    config = {'enabled': True, 'game_id': 42, 'player_id': 7,
              'deadline': time.time() + 3600, 'started_at': time.time()}
    store.set_preference('overnight_control', dict(config, enabled=False))
    executor = SimpleNamespace(session=lambda gid: live,
                               execute=AsyncMock(return_value=ToolResult(ok=True, data={})))
    runtime = Runtime(store.new_task(42, 'overnight'), settings, store, AsyncMock())
    await cycle(executor, store, runtime, config)
    assert not store.preference('overnight_control')['enabled']


async def test_resource_change_before_send_is_blocked(settings, store):
    from sww3bot.agent_tools import ToolResult
    live = session()
    executor = SimpleNamespace(session=lambda gid: live, execute=AsyncMock(side_effect=[
        ToolResult(ok=True, data={}), ToolResult(ok=True, data={'verification': [{'status': 'verified'}]})]))
    config = {'enabled': True, 'game_id': 42, 'player_id': 7,
              'deadline': time.time() + 3600, 'started_at': time.time()}
    store.set_preference('overnight_control', config)
    runtime = Runtime(store.new_task(42, 'overnight'), settings, store, AsyncMock())
    await cycle(executor, store, runtime, config)
    sub = {'@c': 'ultshared.action.UltUpdateProvinceAction', 'mode': 1,
           'provinceIDs': ['', [10]], 'upgrade': {'id': 2275}}
    runtime.action_guard(live, sub)
    live.ge.get_resources = lambda: {'Money': {'amount': 1}}
    with pytest.raises(TaskStop):
        runtime.action_guard(live, sub)
