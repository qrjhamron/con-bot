# Protocol specification v4.2.0 (client v374.p notes)

Machine-readable schema: `protocol.SchemaJSON()` (`internal/protocol`).
Field inventory with confidence: `protocol.Spec()` (60+ fields across
envelope, meta, players, diplomacy, province, economy, research, army,
action, updates). Counts: `protocol.ConfidenceCounts()`.

## Authorization status (binding)

- No live game traffic was captured or sent for this milestone. No
  WebSocket/HTTP inspection, no credential use beyond existing local config,
  no replay of state-changing requests.
- Sources: local legacy Python transport (unverified historical reference),
  recorded client-bundle notes in `docs/protocol-mapping.md`, official wiki
  pages, sanitized fixtures. Hence: **0 fields `verified`, most `legacy`,
  delivery `unknown`**.
- A field promotes to `verified` only after observation in an explicitly
  authorized integration. `inferred` never promotes without evidence.

## Verified vs inferred (highlights)

- Structural envelope (`states` map, `[tag, items]` Java collections,
  `actionResults` acceptance codes, `requestID` shape): legacy, consistent
  across 3+ local sources — still not live-verified.
- `army.hp/mhp/str`: **inferred** (single source) — consumers must treat as
  low confidence; military odds never hinge on them alone.
- Update delivery (push/delta/sequence numbers): **unknown** — the system
  assumes manual snapshots; sequences are local (sync engine), staleness is
  time-based and labeled.
- `UltBuildQueueAction`: **deprecated** (prefer province mode=2).
- IDs vary by doctrine/level/catalog: runtime/authorized tables override
  legacy tables; unknown IDs preserved (`Unit-T{id}` etc.), never dropped.

## State sections (observed keys)

`1` players · `2` ranking · `3` map+properties · `4` resourceProfs ·
`5` relations · `6` armies · `12` day/timeScale · `23` research ·
`30` premium inventory. Anything else triggers a drift note via
`CompatibilityCheck`, never silent decoding.

## Key schemas

- Economy: `4.resourceProfs.<player>.categories.*.resourceEntries.<id>` =
  `{amount0, production, dailyUnitConsumption, dailyUpgradeConsumption,
  dailyPopulationConsumption, rate, tradable, name}`; ids 1 Supplies,
  2 Components, 3 Manpower, 4 Rare Materials, 5 Fuel, 6 Electronics,
  7/8/9 scenario-only, 20 Money. Gold: `30.playerInventories.<player>.
  inventory."2028".amount` (premium, separate authorization).
- Research: `23.currentResearches[] = {researchTypeID|researchID,
  endTime ms}`, `23.completedResearches{<id>:…}`, `23.researchSlots`.
  Costs/durations/prereqs are NOT in raw state — they arrive via player
  export/research panel or stay unknown.
- Armies: `6.armies{<id>:{o,u[{t,hp,ml}],c[{@c:gc|ac|wc}],fs,p{x,y},
  l,s}}`. Status from orders + `fs`; `s` is stack size, never activity.
- Provinces: `{id,o,plv,m,n,c,tt,r,pst,us,prs,pi,cos,rp,tp}`;
  `pst` 55 homeland / 53 occupied; annex ids 2242/2243; `plv`≥4 city.
- Actions: `UltUpdateGameStateAction` wrapper; `UltArmyAction`,
  `UltUpdateProvinceAction` mode 1/2, `UltResearchAction`,
  `UltChangeRelationAction` (base64 signed byte), `UltSpyAction`.
  Acceptance code 1 ≠ completion; max 3 state polls; never resend after a
  lost response (advisory mode observes only).

## Sync & events

- Sync engine: per-game versions, sequence dedupe/stale-reject/gap record,
  field-level partial merge (omitted ≠ zero), malformed updates keep
  last-valid, bounded persisted history, explicit freshness.
- Bus events derived from diffs: GameStateUpdated, ResourceBalanceChanged,
  BuildingStarted/Completed, ProductionStarted/Completed (only with
  observed units), ResearchStarted/Completed/Unlocked,
  CityOwnershipChanged, ArmyStatusChanged, QueueDependencySatisfied,
  WorkflowBlocked/Ready, StateBecameStale. Persisted dedupe keys.
