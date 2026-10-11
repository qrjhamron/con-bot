# Integration capability matrix (P0.2) — status 2026-10-10

Source preference: authorized interface > player export > manual input >
sanitized fixtures. No live reverse-engineered transport is enabled.

| Source | State | Research | Cities | Resources | Armies | Enemies | Prod | Completion | Events | Mutations | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|
| FixtureAdapter | y | y | y | y | y | n | y | y | n | — | fixture-verified |
| ExportAdapter (`CONBOT_EXPORT_PATH`, schema v1) | y | y | y | y | y | y | y | y | n | none (read-only) | export-verified |
| ProtoAdapter (authorized RawSource → typed decode) | y | y | y | y | y | y | y | y | n | none (advisory) | source-dependent |
| ReplayAdapter (scripted frames) | y | y | y | y | y | y | y | y | n | none | fixture-verified |
| DisabledAdapter (unapproved live) | — | — | — | — | — | — | — | — | — | none | unsupported (explicit error) |
| Live CoN transport | — | — | — | — | — | — | — | — | — | — | BLOCKED: no permitted live API; zero production traffic captured/sent in 4.2 |

Verification vocabulary used by `conbot doctor`: `verified-live`
(probed this run), `verified-export` (parsed+validated file),
`fixture` (deterministic doubles), `not tested`, `unsupported`.

- Meta Model API: OpenAI-compatible Chat Completions at
  `https://api.meta.ai/v1/chat/completions`; models include
  `muse-spark-1.3` / `muse-spark-1.3-contributor` (confirmed via provider
  ecosystem docs 2026; official Meta docs require account access).
  Client behavior (auth, completion, native tools, retry) is unit-tested
  with httptest doubles; live format is covered by the opt-in
  `TestLiveMeta` (CONBOT_LIVE_TEST=1, minimal prompt, no game data).
- Telegram: Bot API long polling + getMe probe; live covered by opt-in
  `TestLiveTelegramGetMe` (no messages sent). Owner gating, private-chat
  restriction, dedup, and splitting are unit-tested.
- Research catalog provenance: wiki structure (Research + Units pages,
  fetched 2026-10-10; wiki last edited 2020 — treated as structure only,
  never live numbers) plus `live_observed` imports via validated JSON.
  Costs, durations, and day unlocks ship as unknown until verified.
