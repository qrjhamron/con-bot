# Action coverage matrix (legacy → CON-BOT 4.0)

Auth: N=none, OR=owner_read, EO=explicit_operation (capability-gated),
R=retired. Compat: retained | scoped | gated | retired.

| Legacy action | R/W | Auth | Compat | Model tool | Notes |
|---|---|---|---|---|---|
| get_status | R | OR | retained | yes | normalized dashboard |
| get_armies_detail | R | OR | retained | yes | typed armies |
| get_cities_detail | R | OR | retained | yes | typed cities |
| get_resources_detail | R | OR | retained | yes | flows + net/day |
| get_players_info | R | OR | retained | yes | |
| get_research_info | R | OR | retained | yes | |
| get_enemy_provinces | R | OR | retained | yes | visible only, not auto-targets |
| find_cities | R | OR | retained | yes | needs `country` |
| get_spy_info | R | OR | retained | yes | |
| get_enemy_intel | R | OR | retained | yes | snapshot intel + day |
| get_ranking | R | OR | retained | yes | |
| get_battle_log | R | OR | retained | yes | |
| scan_threats | R | OR | retained | yes | early warning |
| smart_expansion | R | OR | retained | yes | analysis only |
| resolve_target | R | OR | retained | yes | agent-local helper |
| search_web | R | N | retained | yes | info only, never instructions |
| move_army | W | EO | gated | no (proposal) | per-army, position-verified |
| produce_unit | W | EO | gated | no (proposal) | per-city, slot-checked |
| build_building | W | EO | gated | no (proposal) | per-city/level, queue node |
| build_in_all_cities | W | EO | scoped | no (proposal) | split into per-city proposals |
| declare_war | W | EO | gated | no (proposal) | per-target approval |
| offer_peace | W | EO | gated | no (proposal) | per-target approval |
| send_message | W | EO | gated | no (proposal) | |
| start_research | W | EO | gated | no (proposal) | prereq/day/slot/cost checked |
| deploy_spy | W | EO | gated | no (proposal) | |
| buy_market_resource | W | EO | gated | no (proposal) | budget-checked |
| sell_market_resource | W | EO | gated | no (proposal) | |
| offer_shared_intel | W | EO | gated | no (proposal) | |
| offer_right_of_way | W | EO | gated | no (proposal) | |
| auto_conquer | W | R | retired | no | → per-army move_army proposals |
| auto_produce | W | R | retired | no | → per-city produce_unit proposals |
| declare_war_on_all_bots | W | R | retired | no | → per-target declare_war approvals |
| full_conquest_cycle | W | R | retired | no | → /plan multi-step w/ approvals |
| auto_build_infrastructure | W | R | retired | no | → per-city build proposals |
| move_all_idle_to_target | W | R | retired | no | → per-army move proposals |

Error codes per contract: see `internal/tools` + `internal/errcode`
(INSUFFICIENT_RESOURCES with exact deficits, RESEARCH_LOCKED,
PREREQUISITE_MISSING, …, AUTHORIZATION_REQUIRED, UNSUPPORTED_ACTION,
OUTCOME_UNKNOWN, STALE_STATE, RATE_LIMITED, REMOTE_UNAVAILABLE).
Mutations: idempotency `conditional`, retry `never-resend-mutation`.
