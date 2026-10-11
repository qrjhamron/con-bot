# CON-BOT 4.0 — Architecture

Go module `github.com/qrjhamron/con-bot`, SQLite via `modernc.org/sqlite`
(pure Go, no CGO). Context-aware HTTP, typed domain objects, structured
logging (`internal/telemetry`), dry-run by default.

```
cmd/conbot/            production runtime (Telegram long polling + recovery)
internal/
  config/      validated env config (Meta/Telegram/game/budgets, exec gate)
  errcode/     canonical typed error codes (17 codes)
  state/       GameSnapshot v2: canonical immutable versioned model + diff
  gamedata/    reference names with provenance; NO invented costs/stats
  tools/       33 audited action contracts (read vs mutating, auth class)
  gameadapter/ typed GameAdapter boundary + fixtures + unavailable double
  actions/     unified auth/execution gateway (dry-run default, no resend)
  conversation/ intent classifier + tone adapter (guardrails, not the model)
  agent/       Meta Muse Spark client (native tools, retry) + engine + memory
  queue/       persistent dependency DAG engine (15 states, leases, audit)
  ledger/      transactional resource reservations (no double-count)
  reconcile/   verified-change → workflow → notification loop (deduped)
  protocol/    versioned spec DB + confidence + typed raw-map decoder
  syncer/      sync engine (versions, sequences, partial merge, history)
  events/      transport-independent event bus with persisted dedupe
  economy/     forecast identity + shortage diagnosis (no double-count)
  research/    prerequisite/day/slot/cost classification, no invented data
  military/    analysis-only assessment + conditional odds (no win guarantees)
  strategy/    /brief + dependency-ordered /plan builder
  simulator/   offline what-if on cloned snapshots (MutatedReal=false)
  storage/     SQLite: prefs/history/updates/tasks/steps/workflows/audit
  security/    scopes, budgets, redaction, injection stripping
  telegram/    commands/keyboards/handler over injectable Sender (16 cmds)
  telemetry/   redacting structured logger
tests/         cross-module integration (18-scenario failure catalogue)
docs/          audit, architecture, action matrix, migration, deployment
```

## Rules enforced

- Domain logic never imports Telegram; AI orchestration never touches game
  HTTP shapes; all game I/O passes `GameAdapter`.
- One normalized `GameSnapshot` powers every analysis module.
- Reads vs mutations are distinct types/paths; every mutation crosses the
  gateway (scope + budget + audit + verification).
- Failed refresh never replaces a valid snapshot; missing data is never
  zero; invisible enemies are unknown, never nonexistent.
- ETA expiry never equals completion; lost responses become
  `OUTCOME_UNKNOWN`, never resent.
- Model output / search / game text never grants permissions.
