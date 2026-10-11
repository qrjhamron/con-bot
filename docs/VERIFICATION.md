# Live state verification (4.3)

## Authorization status (binding)

No direct game-protocol requests were made: no authorized test
environment is available, so wire-protocol verification stays **blocked**.
Verification works through player screenshots, manual readings, permitted
exports, fixtures, and (if configured) authorized adapters. Service
reachability, auth success, decoder success, and UI correlation are
tracked as **separate** levels — none implies the others.

## Confidence ladder

`schema_verified` (authorized wire evidence only — currently 0 fields) ·
`ui_correlated` (matches official-interface observations) ·
`export_verified` · `fixture_verified` · `legacy_unverified` ·
`inferred` · `unknown` · `mismatch`. Screenshots promote to
`ui_correlated` at most; legacy mappings never jump to verified.

## How to verify (/verify)

1. Send readings as text (`hari: 5`, `komponen: 1050`) or a screenshot
   (photo → file_id reference only; vision transcription off unless
   `CONBOT_VISION=1`, probe-verified supported 2026-10-10).
2. Uncertain transcriptions stay screenshot-sourced; material planning use
   needs owner confirmation ("pakai").
3. `/verify` cross-checks every observation vs the snapshot with
   capture-time-aligned resource tolerance
   (`max(1.0, 5% of rate drift)` — derived, documented) and reports
   MATCH / MISMATCH / UNKNOWN per field plus coverage-vs-accuracy metrics.
4. Screenshot rows are pruned by retention policy; readings live on in
   reports, raw bytes never rest.

## Completion guarantees

Building/research verifiers confirm only on observed evidence conjunctions
(right entity, level, game, fresh source). Timers, queue absence, and
duplicates can never confirm — the evaluation corpus mandates **zero
false-positive completions**.

## Metrics bar

`/verify` and `Metrics.Report()` separate observed coverage from
accuracy-among-observed; unknowns cannot inflate scores. Track parser
errors, merge correctness, duplicates, and cross-game isolation alongside.
