# CON-BOT 4.0 — Legacy Audit (Python → Go)

Date: 2026-10-09. Scope: full `api/` + `sww3bot/` tree at v2.0.2.

## 1. Action inventory

`api/actions.py` `TOOLS` holds **33 entries** (spec §0/§4 says 32 — discrepancy
documented here; all 33 are covered by typed contracts in
`internal/tools`).

Read-only / analysis (14): `get_status`, `get_armies_detail`,
`get_cities_detail`, `get_resources_detail`, `get_players_info`,
`get_research_info`, `get_enemy_provinces`, `find_cities`, `get_spy_info`,
`get_enemy_intel`, `get_ranking`, `get_battle_log`, `scan_threats`,
`smart_expansion`. All retained with normalized return types.

Scoped mutations, capability-gated (12): `move_army`, `produce_unit`,
`build_building`, `build_in_all_cities` (split into per-city proposals),
`declare_war`, `offer_peace`, `send_message`, `start_research`, `deploy_spy`,
`buy_market_resource`, `sell_market_resource`, `offer_shared_intel`,
`offer_right_of_way`.

Retired autonomous ops (6, `UNSUPPORTED_ACTION` with scoped alternative):
`auto_conquer`, `auto_produce`, `declare_war_on_all_bots`,
`full_conquest_cycle`, `auto_build_infrastructure`, `move_all_idle_to_target`.

Agent-local helpers (2, not game actions): `resolve_target`, `search_web`.

## 2. Findings

1. **Stale cross-game models** (`sww3bot/models.py`): Supremacy-WW3 resource
   set (cash/food/goods/energy/oil/rare/components/manpower), buildings
   (recruiting_office/barracks/workshop/harbor/railroad/factory/…), units
   (motorized/mechanized/naval/airborne infantry, cavalry…). Real CoN
   surface uses Money/Supplies/Manpower/Components/Rare Materials/Fuel/
   Electronics. **Not ported** — `internal/gamedata` carries names only, no
   invented stats/costs.
2. **Unsafe classification**: broad ops (`declare_war_on_all_bots`,
   `full_conquest_cycle`) were plain model tools. Retired in 4.0.
3. **Reconnect/auth**: `api/_conn.py` (531 lines) + `sww3bot/auth.py` live
   protocol stays behind `GameAdapter`; the agent never touches HTTP shapes.
4. **Good patterns kept as behavioral specs**: `agent_tools.GameExecutor`
   guarded send (verify-before-send, no resend after lost response →
   `OUTCOME_UNKNOWN`), `agent_engine` budgets/TaskStop semantics,
   `agent_store` journal + `recover()` (→ storage recovery +
   `queue.Recover`), Meta native tool calling with strict validation,
   Telegram dedup (`updates` table) and owner-only private-chat gating.
5. **Removed**: `autoplay.py`, `autoqueue.py` autonomous loops, `/auto`
   command, simplistic `battlecalc.py` damage model (replaced by conditional
   `internal/military` assessment), decorative `dashboard.py` walls.

## 3. Trace sample (one action end-to-end, old → new)

`build_building`: AI schema (`TOOLS`) → pydantic validation (`Registry`) →
ownership preflight → `ctrl._send_sub_action` guarded send → `action_result`
code → `verification()` snapshot check. New: `tools.Contract` →
`actions.Gateway.Propose/Execute` → `security.Authorizer` scope →
`gameadapter.Execute` once → snapshot re-observe → queue `Signal`.

## 4. Test fixtures captured

`gameadapter.SampleSnapshot`, research/economy fixtures in package tests,
and the 18-scenario integration suite in `tests/scenarios_test.go`.
Python implementation is **retained untouched** until migration validates.
