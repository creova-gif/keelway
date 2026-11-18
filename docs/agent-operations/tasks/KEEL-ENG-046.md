# KEEL-ENG-046 — Agent Conformance Suite + Flight-Tape Bridge

| Field | Value |
|---|---|
| **Status** | `VERIFIED_COMPLETE` |
| **Category** | `ENGINEERING / EXTENSIBILITY / AGENTS / TESTING` |
| **Agent** | Devin |
| **Date** | 2026-11-16 |
| **Branch** | `test/KEEL-ENG-046-agent-conformance` |

## Objective
Phase E start: implement the §6 six-point compatibility acceptance criteria as an automated per-adapter conformance suite, plus the flight-tape evidence bridge the criteria require.

## Implementation
- `core/agents/external/tape.py` — `record_hook_evaluation()`: ingests each `evaluate_hook_payload` result as a `tool` span via `SQLiteFlightTapeEngine.ingest_traces` (workflow `external-agent:<id>`, framework `keelway-agent-adapter`).
- `core/cli_harness.py` — `agents intercept --tape [--trace-id] [--tape-db-path]`.
- `tests/test_external_agent_conformance.py` — 13 tests, parametrized over `claude_code`+`codex_cli`:
  1. detect install (fixture binaries)
  2. launch spec + normalized events (**PARTIAL** — spawn/streaming not implemented)
  3. destructive → deny
  4. sensitive mutation → HOLD_TICKET + ticket_id
  5. flight-tape evidence: `step_sha256` and `tape_sha256` **recomputed** in-test and matched
  6. secret-laden payload → DLP redaction/deny, raw secret absent from stored tape JSON
  + CLI `--tape` end-to-end

## Acceptance Criteria
- [x] All 6 criteria exercised per adapter against real engines (no Keelway mocks)
- [x] Hash integrity verified by recomputation, not just presence
- [x] Live-vendor criteria honestly marked PARTIAL in test docstrings
- [x] 13 conformance + 38 combined tests pass

## Known Limits / Honest Claim Boundary
- Criteria 2's spawn/stream portion and real host hook delivery are NOT verified — no "compatible" claim permitted yet.
- Cursor/OpenCode/Cline/ACP have no adapters; suite auto-extends via `EXTERNAL_AGENT_ADAPTERS`.

## Next Recommended Action
Phase D remainder (process spawn + event streaming) or live-vendor validation run against pinned `claude`/`codex` binaries to flip criterion 2 to verified.
