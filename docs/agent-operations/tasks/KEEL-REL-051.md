# KEEL-REL-051 — `keelway tape` User-Facing Verification

| Field | Value |
|---|---|
| **Status** | `VERIFIED_COMPLETE` |
| **Category** | `RELEASE / VERIFICATION / DEVEX` |
| **Agent** | Devin |
| **Date** | 2026-11-16 |
| **Branch** | `fix/KEEL-REL-051-tape-verify` |

## Objective
Release gap #4: evidence existed (step_sha256/tape_sha256 in the SQLite flight-tape engine) but there was no user-facing way to list or verify platform tapes — only `flight verify` for `.flight.json` files.

## Implementation
- `SQLiteFlightTapeEngine.verify_tape(workspace_id, trace_id)` — recomputes every `step_sha256` and `tape_sha256` from stored canonical fields; returns per-step and tape-level verdicts plus `verification_scope: "unkeyed_sha256_recompute"` (honest: detects tampering, not forgery by a DB writer).
- `keelway tape list [--db-path] [--workspace] [--limit] [--json]` — table of recorded tapes.
- `keelway tape verify --trace-id ... [--db-path] [--workspace] [--json]` — prints claimed vs calculated seals; exit 0 valid / 1 tamper-or-missing.

## Evidence
- Live: ingested a real span → `tape verify` printed matching claimed/calculated seals, rc=0; direct SQL tamper of `output_text` → `[✗] TAMPER DETECTED`, rc=1; bogus trace → `tape_not_found`, rc=1.
- 5 new tests (valid verify, step tamper isolation, missing tape, CLI list+verify, tape-meta tamper exit 1). 26 related regression tests pass.

## Honest Limits
Unkeyed SHA-256 recompute proves stored data matches its seals; it does not authenticate the writer. Signed/HMAC receipts remain under `keelway receipt verify`.

## Next Recommended Action
KEEL-REL-052 (onboarding runbook + early-access fulfillment).
