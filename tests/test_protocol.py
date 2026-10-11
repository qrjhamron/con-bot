import copy
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from sww3bot.catalog import Catalog
from sww3bot.controller import GameController
from sww3bot.protocol import action_result, army_status, collection, verification


def sample_army():
    return {'id': 15, 'o': 7, 's': 3, 'p': {'x': 10, 'y': 20}, 'l': 10,
            'u': ['[Lultshared.warfare.UltUnit;', [{'@c': 'u', 't': 2039, 's': 3}]]}


def controller():
    client = SimpleNamespace(player_id=7, session=MagicMock())
    ctrl = GameController(client)
    ctrl._state_cache = {'states': {'6': {'armies': {'15': sample_army()}},
        '3': {'map': {'locations': ['', [{'id': 20, 'o': 8, 'c': {'x': 30, 'y': 40}}]]}}}}
    ctrl._send_sub_action = MagicMock(return_value={'result': {'actionResults': {'req': 1}}})
    return ctrl


def test_stack_size_is_not_activity():
    for size in (1, 2, 3, 4, 6, 20):
        assert army_status({'s': size}) == 'IDLE'
    assert army_status({'s': 1, 'c': ['', [{'@c': 'gc', 'at': 123}]]}) == 'MOVING'
    assert army_status({'s': 2, 'fs': 7}) == 'ATTACKING'
    assert army_status({'s': 3, 'fs': 3}) == 'PATROL'
    assert army_status({'s': 1, 'c': ['', [{'@c': 'gc', 'tp': {}}]]}) == 'ORDERED'


def test_move_serialization_includes_units_and_only_client_command_fields():
    ctrl = controller()
    ctrl.move_army(15, 20)
    action = ctrl._send_sub_action.call_args.args[0]
    army = collection(action['armies'])[0]
    assert army['s'] == 3
    assert army['u'][0] == '[Lultshared.warfare.UltUnit;'
    assert army['u'][1][0]['t'] == 2039
    assert collection(army['c']) == [{'@c': 'gc', 'sp': {'x': 10, 'y': 20}, 'tp': {'x': 30, 'y': 40}}]


def test_attack_position_and_signed_war_byte():
    ctrl = controller()
    ctrl.attack_province(15, 20)
    army = collection(ctrl._send_sub_action.call_args.args[0]['armies'])[0]
    command = collection(army['c'])[0]
    assert command == {'@c': 'ac', 'targetPos': {'x': 30, 'y': 40}, 'targetUnitID': 0, 'userGiven': True}
    ctrl.declare_war(100)
    assert ctrl._send_sub_action.call_args.args[0]['relationType'] == '/g=='
    assert ctrl._send_sub_action.call_args.args[0]['playerB'] == [100]


def test_response_must_match_request_and_not_boolean_or_first_other_response():
    response = {'result': {'actionResults': {'other': 1, 'expected': -1}}}
    assert action_result(response, 'expected') == -1
    assert action_result(response, 'missing') is None
    assert action_result(response) is None
    assert action_result({'result': {'actionResults': {'x': True}}}) is None


def test_verify_route_endpoint_instead_of_response_or_stack_size():
    ctrl = controller()
    ctrl.move_army(15, 20)
    action = ctrl._send_sub_action.call_args.args[0]
    raw = copy.deepcopy(ctrl.state)
    assert verification(action, raw, 7) is None
    raw['states']['6']['armies']['15']['c'] = ['', [
        {'@c': 'gc', 'tp': {'x': 15, 'y': 25}, 'at': 123},
        {'@c': 'gc', 'tp': {'x': 30, 'y': 40}}]]
    assert verification(action, raw, 7)['armies'][0]['status'] == 'MOVING'
    raw['states']['6']['armies']['15']['c'][1][-1]['tp'] = {'x': 90, 'y': 100}
    assert verification(action, raw, 7) is None


def test_catalog_names_domain_and_city_specific_ids():
    catalog = Catalog([
        {'@c': 'ultshared.warfare.UltUnitType', 'itemID': '2039', 'unitName': 'Motorized Infantry', 'unitClass': '0'},
        {'@c': 'ultshared.warfare.UltUnitType', 'itemID': '2175', 'unitName': 'Air Superiority Fighter', 'unitClass': '2'},
        {'@c': 'ultshared.upgrades.UltUpgradeType', 'itemID': '2255', 'upgrName': {'en': 'Air Base'}},
    ])
    assert catalog.name(2255) == 'Air Base'
    assert catalog.domain(2175) == 'air'
    assert catalog.domain(2039) == 'land'
    assert catalog.domain(123456) == 'unknown'
    assert catalog.resolve_available('infantry', [{'unit': {'t': 2039}}], 'unit') == 2039
    assert catalog.resolve_available('airbase', [{'id': 2255}], 'building') == 2255
    with pytest.raises(ValueError):
        catalog.resolve_available('3294', [{'unit': {'t': 2039}}], 'unit')


def test_grounded_plane_cannot_be_sent_to_enemy_province_as_capture_unit():
    ctrl = controller()
    ctrl.catalog = Catalog([])
    ctrl.state['states']['6']['armies']['15']['a'] = True
    with pytest.raises(ValueError, match='Pesawat'):
        ctrl.move_army(15, 20)
    ctrl._send_sub_action.assert_not_called()


def test_no_fabricated_building_template():
    ctrl = controller()
    with pytest.raises(ValueError, match='template'):
        ctrl.build_building(10, 2250)
    ctrl._send_sub_action.assert_not_called()


def build_sub(mode=1, provinces=(10,), upgrade=None, slot=0):
    sub = {'@c': 'ultshared.action.UltUpdateProvinceAction', 'mode': mode,
           'provinceIDs': ['', list(provinces)]}
    if mode in (1, 2):
        sub['upgrade'] = upgrade
    else:
        sub['slot'] = slot
    return sub


def province_state(pid=10, owner=7, **fields):
    loc = {'id': pid, 'o': owner}
    loc.update(fields)
    return {'states': {'3': {'map': {'locations': ['', [loc]]}}}}


def test_construction_in_progress_is_observed_but_not_complete():
    sub = build_sub(upgrade={'id': 2245})
    raw = province_state(us=['', []], cos=['', [{'u': {'id': 2245}, 't': 999}]])
    assert verification(sub, raw, 7) == {
        'province_ids': [10], 'item_id': 2245, 'observed': True, 'completed': False}
    raw = province_state(us=['', [{'id': 2245}]], cos=['', [None]])
    assert verification(sub, raw, 7) == {
        'province_ids': [10], 'item_id': 2245, 'observed': True, 'completed': True}
    raw = province_state(us=['', []], cos=['', [None]])
    assert verification(sub, raw, 7) is None


def test_cancel_building_verifies_only_a_free_slot():
    assert verification(build_sub(mode=3), province_state(cos=['', [None]]), 7) == {
        'province_ids': [10], 'cancelled': True, 'observed': True}
    assert verification(build_sub(mode=3), province_state(cos=['', [{'u': {'id': 2245}}]]), 7) is None
    assert verification(build_sub(mode=3), province_state(), 7) is None
    assert verification(build_sub(mode=3), province_state(cos=['', [None]], owner=88), 7) is None


def test_cancel_production_verifies_only_a_free_slot():
    assert verification(build_sub(mode=4), province_state(prs=['', [None]]), 7) == {
        'province_ids': [10], 'cancelled': True, 'observed': True}
    assert verification(build_sub(mode=4), province_state(prs=['', [{'u': {'unit': {'t': 3294}}}]]), 7) is None
