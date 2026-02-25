#!/usr/bin/env python3
"""
LLM Prompt Test Suite — Tests that the AI agent correctly interprets
user commands and calls the right tools with correct parameters.

Tests the full LLM → tool calling → execution pipeline.
"""

import sys, os, json, time
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tui_agent import GradientAgent, _execute_function, SYSTEM_PROMPT, _build_openai_tools
from actions import TOOLS, _connect

# ── Test harness ──────────────────────────────────────────

class ToolCallTracker:
    """Intercepts tool calls to verify correct tool selection."""
    def __init__(self, agent):
        self.agent = agent
        self.calls = []  # list of (name, args) tuples
        self.originals = {}

    def start(self):
        """Start tracking by wrapping execute."""
        self.calls = []
        orig_log = self.agent._log
        def tracking_log(msg):
            if '⚡' in msg:
                # Parse: "  ⚡ name(arg1=val1, arg2=val2)"
                try:
                    parts = msg.split('⚡')[1].strip()
                    fname = parts.split('(')[0].strip()
                    self.calls.append(fname)
                except:
                    pass
            orig_log(msg)
        self.agent._log = tracking_log

    def get_calls(self):
        return self.calls


def run_prompt_tests():
    """Run comprehensive prompt tests."""
    print("═══════════════════════════════════════════════════")
    print("  SWW3 AI AGENT — LLM PROMPT TEST SUITE")
    print("═══════════════════════════════════════════════════\n")

    api_key = os.environ.get('GRADIENT_API_KEY', '')
    if not api_key:
        print("❌ Set GRADIENT_API_KEY env var first!")
        sys.exit(1)

    print("🔌 Connecting to game server...")
    _connect()
    print("✅ Connected!\n")

    agent = GradientAgent(api_key)
    agent.verbose = False
    agent.connect_game()

    tracker = ToolCallTracker(agent)
    tracker.start()

    passed = 0
    failed = 0
    errors = 0
    total = 0
    results = []

    def test(prompt, expected_tools, description="", timeout=45):
        """Test that a prompt triggers the expected tool calls.

        expected_tools: list of tool names that should be called (order doesn't matter).
                       Use '*' to accept any tool call.
                       Use '!' prefix to indicate must NOT call this tool.
        """
        nonlocal passed, failed, errors, total
        total += 1

        # Reset conversation for each test (keep system prompt)
        agent.messages = [{'role': 'system', 'content': SYSTEM_PROMPT}]
        tracker.calls = []

        try:
            start = time.time()
            result = agent.execute(prompt)
            elapsed = time.time() - start
            calls = tracker.get_calls()

            # Check expected tools
            ok = True
            details = []

            must_call = [t for t in expected_tools if not t.startswith('!')]
            must_not_call = [t[1:] for t in expected_tools if t.startswith('!')]

            if '*' in must_call:
                # Any tool call is fine, just check something was called
                if not calls:
                    ok = False
                    details.append("expected tool call but got none")
            else:
                for tool in must_call:
                    if tool not in calls:
                        ok = False
                        details.append(f"missing: {tool}")

            for tool in must_not_call:
                if tool in calls:
                    ok = False
                    details.append(f"unexpected: {tool}")

            if ok:
                passed += 1
                status = "✅"
                detail_str = f"tools={calls} ({elapsed:.1f}s)"
            else:
                failed += 1
                status = "❌"
                detail_str = f"tools={calls} expected={expected_tools} {', '.join(details)}"

            desc = description or prompt[:50]
            print(f"  {status} [{total:3d}] {desc}")
            if not ok:
                print(f"         {detail_str}")
                if result:
                    print(f"         response: {result[:120]}...")

            results.append({
                'id': total, 'prompt': prompt, 'status': 'pass' if ok else 'fail',
                'calls': calls, 'expected': expected_tools, 'time': elapsed
            })

        except Exception as e:
            errors += 1
            print(f"  💥 [{total:3d}] {description or prompt[:50]}: {e}")
            results.append({
                'id': total, 'prompt': prompt, 'status': 'error', 'error': str(e)
            })

    # ═══════════════════════════════════════════════════════
    # Category 1: STATUS & INFO (read-only, should call info tools)
    # ═══════════════════════════════════════════════════════
    print("\n── STATUS & INFO ──")
    test("cek status game", ["get_status"], "status check")
    test("berapa VP kita sekarang?", ["get_status"], "VP query")
    test("sekarang hari ke berapa?", ["get_status"], "day query")
    test("liat semua army kita", ["get_armies_detail"], "list armies")
    test("ada berapa army idle?", ["get_armies_detail"], "idle armies")
    test("list semua kota", ["get_cities_detail"], "list cities")
    test("kota mana yang lagi produksi?", ["get_cities_detail"], "producing cities")
    test("cek resource kita", ["get_resources_detail"], "resources")
    test("berapa uang kita?", ["get_resources_detail"], "money query")
    test("siapa player teratas?", ["get_ranking"], "ranking")
    test("top 10 leaderboard", ["get_ranking"], "leaderboard")
    test("ada pertempuran aktif?", ["get_battle_log"], "battles")
    test("cek riset apa yang aktif", ["get_research_info"], "research")
    test("info player Ghana", ["get_players_info"], "player info")
    test("cek spy kita", ["get_spy_info"], "spy status")

    # ═══════════════════════════════════════════════════════
    # Category 2: THREATS & EXPANSION (analysis tools)
    # ═══════════════════════════════════════════════════════
    print("\n── THREATS & EXPANSION ──")
    test("ada ancaman musuh ga?", ["scan_threats"], "scan threats")
    test("scan ada army musuh mendekat?", ["scan_threats"], "threat scan")
    test("target ekspansi paling gampang?", ["smart_expansion"], "smart expand")
    test("negara mana yang lemah?", ["smart_expansion"], "weak targets")
    test("analisis target invasi", ["smart_expansion"], "invasion analysis")

    # ═══════════════════════════════════════════════════════
    # Category 3: WAR DECLARATION (should call declare_war)
    # ═══════════════════════════════════════════════════════
    print("\n── WAR DECLARATION ──")
    test("declare war ke Ghana", ["declare_war"], "war Ghana")
    test("serang Mali", ["declare_war"], "attack Mali")
    test("perang sama Sudan", ["declare_war"], "war Sudan")

    # ═══════════════════════════════════════════════════════
    # Category 4: ARMY MOVEMENT (should use army tools)
    # ═══════════════════════════════════════════════════════
    print("\n── ARMY MOVEMENT ──")
    test("kirim semua army ke Ghana", ["move_all_idle_to_target"], "move all to Ghana")
    test("deploy army idle ke Mali", ["move_all_idle_to_target"], "deploy to Mali")

    # ═══════════════════════════════════════════════════════
    # Category 5: BUILDING (should call build tools)
    # ═══════════════════════════════════════════════════════
    print("\n── BUILDING ──")
    test("bangun recruiting office di semua kota",
         ["build_in_all_cities"], "build recruiting everywhere")
    test("bangun army base di semua kota",
         ["build_in_all_cities"], "build army base everywhere")
    test("auto build infrastructure",
         ["auto_build_infrastructure"], "auto infra")

    # ═══════════════════════════════════════════════════════
    # Category 6: PRODUCTION (should call produce tools)
    # ═══════════════════════════════════════════════════════
    print("\n── PRODUCTION ──")
    test("produce unit di semua kota idle",
         ["auto_produce"], "auto produce")
    test("produce infantry di semua kota",
         ["auto_produce"], "produce all infantry")

    # ═══════════════════════════════════════════════════════
    # Category 7: CONQUEST CYCLE (should call composite tools)
    # ═══════════════════════════════════════════════════════
    print("\n── CONQUEST CYCLE ──")
    test("jalankan full conquest cycle",
         ["full_conquest_cycle"], "full cycle")
    test("auto conquer semua musuh",
         ["auto_conquer"], "auto conquer")

    # ═══════════════════════════════════════════════════════
    # Category 8: MARKET (should call market tools)
    # ═══════════════════════════════════════════════════════
    print("\n── MARKET ──")
    test("beli metal 1000", ["buy_market_resource"], "buy metal")
    test("jual fuel 500", ["sell_market_resource"], "sell fuel")

    # ═══════════════════════════════════════════════════════
    # Category 9: DIPLOMACY (should call diplomacy tools)
    # ═══════════════════════════════════════════════════════
    print("\n── DIPLOMACY ──")
    test("tawarkan shared intel ke China", ["offer_shared_intel"], "offer intel China")
    test("tawarkan right of way ke Philippines", ["offer_right_of_way"], "offer ROW Philippines")
    test("kirim pesan ke Morocco: halo teman!", ["send_message"], "send message")
    test("tawarkan peace ke Turkmenistan", ["offer_peace"], "offer peace")

    # ═══════════════════════════════════════════════════════
    # Category 10: COMPLEX MULTI-STEP (should call multiple tools)
    # ═══════════════════════════════════════════════════════
    print("\n── COMPLEX / MULTI-STEP ──")
    test("cek status lalu scan ancaman",
         ["get_status", "scan_threats"], "status + threats")
    test("liat army lalu kirim semua ke Mali",
         ["get_armies_detail", "move_all_idle_to_target"], "armies + deploy")

    # ═══════════════════════════════════════════════════════
    # Category 11: WEB SEARCH (should use search_web)
    # ═══════════════════════════════════════════════════════
    print("\n── WEB SEARCH ──")
    test("cari strategi early game supremacy ww3", ["search_web"], "web search strategy")
    test("search tips attack helicopter usage", ["search_web"], "web search tips")

    # ═══════════════════════════════════════════════════════
    # Category 12: EDGE CASES (tricky prompts)
    # ═══════════════════════════════════════════════════════
    print("\n── EDGE CASES ──")
    test("bangun recruiting office di kota yang masih level 1",
         ["*"], "build specific — should get cities first")
    test("province musuh Ghana yang bisa diserang",
         ["get_enemy_provinces"], "enemy provinces")

    # ═══════════════════════════════════════════════════════
    # SUMMARY
    # ═══════════════════════════════════════════════════════
    print(f"\n{'═'*50}")
    total_ran = passed + failed + errors
    print(f"  RESULTS: {passed}/{total_ran} passed, {failed} failed, {errors} errors")
    pct = (passed / total_ran * 100) if total_ran > 0 else 0
    print(f"  ACCURACY: {pct:.0f}%")
    print(f"{'═'*50}")

    # Save results
    with open('/root/supremacy-ww3-bot/api/test_prompts_results.json', 'w') as f:
        json.dump({
            'passed': passed, 'failed': failed, 'errors': errors,
            'accuracy': pct, 'results': results
        }, f, indent=2, ensure_ascii=False)
    print(f"\n📄 Detailed results saved to api/test_prompts_results.json")

    return passed, failed, errors


if __name__ == '__main__':
    run_prompt_tests()
