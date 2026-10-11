# Migration & Deployment (updated 4.1)

## Pre-flight: `conbot doctor`

```bash
go build -o conbot ./cmd/conbot
./conbot doctor
```

Reports config presence (never values), DB migration counts, dry-run vs
execution mode, data-source capabilities, snapshot/research/queue health.
Live Meta/Telegram probes only with `CONBOT_LIVE_TEST=1` (getMe; one
minimal completion without game data; no messages sent).

## Data sources

- Default: sanitized fixtures (deterministic dev/simulation).
- Supported: player export JSON (`CONBOT_EXPORT_PATH=path/to/export.json`,
  schema v1, validated; unknown fields become completeness gaps).
- Live CoN transport: no permitted API identified — stays disabled via
  `DisabledAdapter` (explicit errors, never silent).

## Migration

## Python → Go migration

The Python runtime (`api/`, `sww3bot/`, `play.py`) is **retained untouched**
until parity + migration validate. Steps:

1. Run legacy + Go side by side (different `BOT_DB_PATH`).
2. Migrate SQLite: legacy tables (`preferences`, `conversations`, `tasks`,
   `steps`) are schema-compatible with `internal/storage` — copy the file
   and open with the Go runtime; `LegacyStats()` verifies row counts.
   New tables (`workflows`, `nodes`, `edges`, `events`, `audit`,
   `snapshots`, `memory`) are created automatically.
3. Re-select game via `/games <ID>`; strategic goals must be re-approved
   explicitly (never auto-imported as goals — imported text lands in
   conversation memory only).
4. Validate: `go test ./...`, `go test -race ./...`, `go vet ./...`,
   plus the `tests/` scenario suite against fixtures.
5. Only then: remove Python from the production path (keep an archived
   reference tag, e.g. `archive/python-2.x`).

## Deployment

```bash
go build -o conbot ./cmd/conbot
MODEL_API_KEY=... BOT_USER=... BOT_PASS=... \
TELEGRAM_BOT_TOKEN=... TELEGRAM_OWNER_ID=... \
GAME_ID=0 BOT_DB_PATH=data/con-bot.sqlite3 ./conbot
```

- Advisory default: no `CONBOT_EXEC_ENABLED` → dry-run proposals only.
- Authorized env: `CONBOT_EXEC_ENABLED=1` + explicit per-game scopes
  granted at runtime; `CONBOT_READ_ONLY=1` forces read-only (conflicts
  with exec).
- Model: `muse-spark-1.3-contributor` default (`CONBOT_MODEL` overrides
  only to the standard tier).
- Restart behavior: interrupted tasks/steps → `interrupted`/`unknown`;
  running queue nodes → `outcome_unknown` (never resent, never assumed).

## Telegram surface

/start /help /games /brief /plan /research /simulate /economy /military
/queue /tasks /cancel /pause /resume /status /reset. No `/auto`.
Free-text chat is first-class; inline keyboards for game select, targets,
plans, queue control, and permitted approvals.
