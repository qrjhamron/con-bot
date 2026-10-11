# Traceability matrix (P0.1) — verified 2026-10-10

Counts are pinned by `TestRegistryTallies`: **35 contracts = 33 legacy
`api/actions.py` TOOLS entries + 2 agent helpers** (`resolve_target`,
`search_web`). Model tools: 16 read-only. Gated mutations: 13. Retired: 6.

| # | Legacy (`api/actions.py`) | Contract (`tools`) | Compat | Model | Gateway path | Tests |
|---|---|---|---|---|---|---|
| 1 | get_status | get_status v2 | retained | yes | Read → Snapshot | gateway, adapter |
| 2 | get_armies_detail | get_armies_detail v2 | retained | yes | Read → Snapshot | gateway |
| 3 | get_cities_detail | get_cities_detail v2 | retained | yes | Read → Snapshot | gateway |
| 4 | get_resources_detail | get_resources_detail v2 | retained | yes | Read → Snapshot | gateway, economy |
| 5 | get_players_info | get_players_info v2 | retained | yes | Read → Snapshot | gateway |
| 6 | get_research_info | get_research_info v2 | retained | yes | Read → Snapshot | gateway, research |
| 7 | get_enemy_provinces | get_enemy_provinces v2 | retained | yes | Read → Snapshot | gateway |
| 8 | find_cities | find_cities v2 | retained | yes | Read → Snapshot | gateway |
| 9 | get_spy_info | get_spy_info v2 | retained | yes | Read → Snapshot | gateway |
| 10 | get_enemy_intel | get_enemy_intel v2 | retained | yes | Read → Snapshot | gateway |
| 11 | get_ranking | get_ranking v2 | retained | yes | Read → Snapshot | gateway |
| 12 | get_battle_log | get_battle_log v2 | retained | yes | Read → Snapshot | gateway |
| 13 | scan_threats | scan_threats v2 | retained | yes | Read → Snapshot | gateway |
| 14 | smart_expansion | smart_expansion v2 | retained | yes | Read → Snapshot | gateway |
| 15 | move_army | move_army v2 | gated | proposal | Propose → approve → Execute | gateway |
| 16 | produce_unit | produce_unit v2 | gated | proposal | Propose → approve → Execute | gateway |
| 17 | build_building | build_building v2 | gated | proposal | Propose → queue → Execute | gateway, queue, reconcile |
| 18 | build_in_all_cities | build_in_all_cities v2 | scoped | proposal | split per-city → queue | gateway, strategy |
| 19 | declare_war | declare_war v2 | gated | proposal | Propose → approve → Execute | gateway, scenarios |
| 20 | offer_peace | offer_peace v2 | gated | proposal | Propose → approve → Execute | gateway |
| 21 | send_message | send_message v2 | gated | proposal | Propose → approve → Execute | gateway |
| 22 | start_research | start_research v2 | gated | proposal | prereq/day/slot/cost → queue | gateway, research |
| 23 | deploy_spy | deploy_spy v2 | gated | proposal | Propose → approve → Execute | gateway |
| 24 | buy_market_resource | buy_market_resource v2 | gated | proposal | budget → Execute | gateway |
| 25 | sell_market_resource | sell_market_resource v2 | gated | proposal | budget → Execute | gateway |
| 26 | offer_shared_intel | offer_shared_intel v2 | gated | proposal | Propose → approve → Execute | gateway |
| 27 | offer_right_of_way | offer_right_of_way v2 | gated | proposal | Propose → approve → Execute | gateway |
| 28 | auto_conquer | auto_conquer v2 | retired | no | UNSUPPORTED_ACTION | gateway |
| 29 | auto_produce | auto_produce v2 | retired | no | UNSUPPORTED_ACTION | gateway |
| 30 | declare_war_on_all_bots | declare_war_on_all_bots v2 | retired | no | UNSUPPORTED_ACTION | gateway |
| 31 | full_conquest_cycle | full_conquest_cycle v2 | retired | no | UNSUPPORTED_ACTION | gateway |
| 32 | auto_build_infrastructure | auto_build_infrastructure v2 | retired | no | UNSUPPORTED_ACTION | gateway |
| 33 | move_all_idle_to_target | move_all_idle_to_target v2 | retired | no | UNSUPPORTED_ACTION | gateway |
| H1 | (agent_tools.resolve_target) | resolve_target v2 | retained | yes | Read (state lookup) | agent |
| H2 | (agent_tools.search_web) | search_web v2 | retained | yes | info only | agent |

Legacy `game_registry()` exposed 33 + 2 = 35 callables; the Go registry
covers all 35. Previous reports saying "32" were off by the audit above.
