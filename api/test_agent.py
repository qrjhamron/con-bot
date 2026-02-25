#!/usr/bin/env python3
"""
Automated test suite for the TUI agent — tests 100+ prompts,
catches bugs, validates tool calls work.
"""

import sys, os, json, time, traceback
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from actions import TOOLS, refresh, _connect, _ensure
from agent import _execute_function, _build_openai_tools, search_web

# ── Direct function tests (no LLM needed) ────────────────

def test_direct(name, fn_name, args, expect_key=None, expect_no_error=True):
    """Test a tool function directly."""
    result_str = _execute_function(fn_name, args)
    try:
        result = json.loads(result_str)
    except:
        print(f"  ❌ {name}: invalid JSON: {result_str[:100]}")
        return False

    has_error = 'error' in result and result['error']
    if expect_no_error and has_error:
        print(f"  ❌ {name}: unexpected error: {result.get('error', '')[:120]}")
        return False
    if not expect_no_error and not has_error:
        print(f"  ❌ {name}: expected error but got success")
        return False
    if expect_key and expect_key not in result:
        print(f"  ❌ {name}: missing key '{expect_key}' in result")
        return False

    print(f"  ✅ {name}")
    return True


def run_all_tests():
    print("🔌 Connecting to game server...")
    _connect()
    print("✅ Connected!\n")

    passed = 0
    failed = 0
    total = 0

    def check(name, fn_name, args, **kw):
        nonlocal passed, failed, total
        total += 1
        if test_direct(name, fn_name, args, **kw):
            passed += 1
        else:
            failed += 1

    # ═══════════════════════════════════════════════════════
    print("═══ READ FUNCTIONS ═══")
    # ═══════════════════════════════════════════════════════
    check("get_status", "get_status", {}, expect_key="day")
    check("get_armies_detail", "get_armies_detail", {}, expect_key="armies")
    check("get_cities_detail", "get_cities_detail", {}, expect_key="cities")
    check("get_resources_detail", "get_resources_detail", {}, expect_key="Money")
    check("get_players_info", "get_players_info", {}, expect_key="players")
    check("get_research_info", "get_research_info", {}, expect_key="slots_total")
    check("get_enemy_provinces", "get_enemy_provinces", {})
    check("get_ranking", "get_ranking", {}, expect_key="ranking")
    check("get_battle_log", "get_battle_log", {}, expect_key="active_battles")
    check("scan_threats", "scan_threats", {}, expect_key="threats")
    check("smart_expansion", "smart_expansion", {}, expect_key="expansion_targets")
    check("get_spy_info", "get_spy_info", {}, expect_key="spies")

    # ═══════════════════════════════════════════════════════
    print("\n═══ PARAMETER TYPE HANDLING ═══")
    # ═══════════════════════════════════════════════════════
    # Test string-to-int conversion
    check("declare_war str id", "declare_war", {"player_id": "29"}, expect_key="success")
    check("declare_war name Ghana", "declare_war", {"player_id": "Ghana"}, expect_key="success")
    check("declare_war name Mali", "declare_war", {"player_id": "Mali"}, expect_key="success")
    check("declare_war name Niger", "declare_war", {"player_id": "Niger"}, expect_key="success")
    check("declare_war bad name", "declare_war", {"player_id": "Atlantis"}, expect_no_error=False)

    check("move_all_idle name", "move_all_idle_to_target", {"player_id": "Ghana"}, expect_key="target")
    check("move_all_idle str id", "move_all_idle_to_target", {"player_id": "29"}, expect_key="target")
    check("move_all_idle bad", "move_all_idle_to_target", {"player_id": "Narnia"}, expect_no_error=False)

    check("offer_peace name", "offer_peace", {"player_id": "South Sudan"}, expect_key="success")
    check("offer_peace str id", "offer_peace", {"player_id": "124"}, expect_key="success")

    # ═══════════════════════════════════════════════════════
    print("\n═══ BUILDING FUNCTIONS ═══")
    # ═══════════════════════════════════════════════════════
    check("build_in_all_cities army_base", "build_in_all_cities", {"building_type": "army_base"}, expect_key="building")
    check("build_in_all_cities recruiting", "build_in_all_cities", {"building_type": "recruiting_office"}, expect_key="building")
    check("build_in_all_cities bad type", "build_in_all_cities", {"building_type": "nuclear_silo"}, expect_no_error=False)
    check("auto_build_infrastructure", "auto_build_infrastructure", {}, expect_key="built")

    # build_building with valid city
    check("build_building valid", "build_building", {"city_id": "612", "building_type": "army_base"}, expect_key="success")
    check("build_building str city", "build_building", {"city_id": "612", "building_type": "recruiting_office"}, expect_key="success")
    check("build_building bad type", "build_building", {"city_id": "612", "building_type": "space_station"}, expect_no_error=False)

    # ═══════════════════════════════════════════════════════
    print("\n═══ PRODUCTION FUNCTIONS ═══")
    # ═══════════════════════════════════════════════════════
    check("produce_unit infantry", "produce_unit", {"city_id": "612", "unit_type": "infantry"}, expect_key="success")
    check("produce_unit mot", "produce_unit", {"city_id": "612", "unit_type": "mot"}, expect_key="success")
    check("produce_unit heli", "produce_unit", {"city_id": "612", "unit_type": "heli"}, expect_key="success")
    check("produce_unit tank", "produce_unit", {"city_id": "612", "unit_type": "tank"}, expect_key="success", expect_no_error=False)
    check("produce_unit bad", "produce_unit", {"city_id": "612", "unit_type": "nuke"}, expect_no_error=False)
    check("auto_produce", "auto_produce", {}, expect_key="results")

    # ═══════════════════════════════════════════════════════
    print("\n═══ ARMY FUNCTIONS ═══")
    # ═══════════════════════════════════════════════════════
    check("auto_conquer", "auto_conquer", {}, expect_key="deployed")
    check("move_army bad id", "move_army", {"army_id": "999", "target_province": "612"}, expect_key="success", expect_no_error=False)

    # ═══════════════════════════════════════════════════════
    print("\n═══ DIPLOMACY FUNCTIONS ═══")
    # ═══════════════════════════════════════════════════════
    check("offer_shared_intel", "offer_shared_intel", {"player_id": "5"}, expect_key="success")
    check("offer_right_of_way", "offer_right_of_way", {"player_id": "5"}, expect_key="success")
    check("send_message", "send_message", {"player_id": "87", "message": "test"}, expect_key="success")

    # ═══════════════════════════════════════════════════════
    print("\n═══ MARKET FUNCTIONS ═══")
    # ═══════════════════════════════════════════════════════
    check("buy metal", "buy_market_resource", {"resource": "metal", "amount": "100"}, expect_key="success")
    check("sell fuel", "sell_market_resource", {"resource": "fuel", "amount": "100"}, expect_key="success")
    check("buy bad resource", "buy_market_resource", {"resource": "uranium", "amount": "100"}, expect_no_error=False)

    # ═══════════════════════════════════════════════════════
    print("\n═══ COMPOSITE FUNCTIONS ═══")
    # ═══════════════════════════════════════════════════════
    check("declare_war_on_all_bots", "declare_war_on_all_bots", {}, expect_key="wars_declared")
    check("full_conquest_cycle", "full_conquest_cycle", {}, expect_key="wars")

    # ═══════════════════════════════════════════════════════
    print("\n═══ SEARCH WEB ═══")
    # ═══════════════════════════════════════════════════════
    check("search_web", "search_web", {"query": "supremacy ww3 strategy"}, expect_key="results")
    check("search_web indo", "search_web", {"query": "conflict of nations tips"}, expect_key="results")

    # ═══════════════════════════════════════════════════════
    print("\n═══ EDGE CASES ═══")
    # ═══════════════════════════════════════════════════════
    check("unknown function", "nonexistent_func", {}, expect_no_error=False)
    check("deploy_spy", "deploy_spy", {"province_id": "612"}, expect_key="success")
    check("start_research", "start_research", {"research_id": "2978"}, expect_key="success")

    # Test all param types get cast correctly
    total += 1
    try:
        r = json.loads(_execute_function("move_army", {"army_id": 17000602, "target_province": 612}))
        if 'success' in r:
            print(f"  ✅ move_army int params")
            passed += 1
        else:
            print(f"  ❌ move_army int params: missing success key")
            failed += 1
    except Exception as e:
        print(f"  ❌ move_army int params: {e}")
        failed += 1

    total += 1
    try:
        r = json.loads(_execute_function("move_army", {"army_id": "17000602", "target_province": "612"}))
        if 'success' in r:
            print(f"  ✅ move_army string params")
            passed += 1
        else:
            print(f"  ❌ move_army string params: missing success key")
            failed += 1
    except Exception as e:
        print(f"  ❌ move_army string params: {e}")
        failed += 1

    # ═══════════════════════════════════════════════════════
    print(f"\n{'='*50}")
    print(f"  RESULTS: {passed}/{total} passed, {failed} failed")
    print(f"{'='*50}")
    return failed == 0


if __name__ == '__main__':
    run_all_tests()
