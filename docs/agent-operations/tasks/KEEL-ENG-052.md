# KEEL-ENG-052 — M6 Reliability: Fault-Injection & Performance Baselines

- **STATUS**: VERIFIED_COMPLETE
- **LAST AGENT**: Devin
- **DATE**: 2026-11-17
- **BRANCH**: `main`

## Objective & Acceptance Criteria

Milestone-6 slice from Master Prompt 03 Phase 13: exercise real failure
surfaces and establish measured performance baselines on the verified
subsystems (co-harness policy engine, flight tapes, audit chain).

- [x] Malformed/hostile input rejected, never reaches SQL
- [x] Single-use P-10 ticket consumption is atomic under a race
- [x] Corrupted persistence fails closed (raises, never fabricates)
- [x] Out-of-band tape tampering detected by recompute verification
- [x] Measured latency/throughput baselines recorded

## Implementation

`tests/test_m6_fault_injection_and_perf.py` — 9 tests, all real code paths
(no mocks of the unit under test):

| Test | Result |
|---|---|
| SQL-metachar `workspace_id` (`'; DROP TABLE--`, `" OR 1=1`, NUL) | Rejected by `_clean_workspace_id` validation → `AgentCoharnessValidationError`; never reaches SQL layer. Command text with metachars stored verbatim as data |
| Empty / 200KB commands | Empty → validation error; oversized → classified and stored normally |
| Single-use ticket race (2 threads, one APPROVED ticket) | Exactly one `ALLOW_WITH_TICKET`, one `DENY` — atomic consume via `UPDATE ... WHERE status='APPROVED'` |
| Corrupted DB (garbage bytes) | `sqlite3.DatabaseError` at engine init — raises, never fabricates a verdict |
| Out-of-band step payload mutation | `verify_tape` → `valid=False`, `steps_valid=False` |
| ACP evaluator error / missing binary | (pre-existing coverage in `test_external_agent_acp.py`) |

## Measured Baselines (Apple Silicon, SQLite WAL, 2026-11-17)

| Operation | Observed | Asserted ceiling |
|---|---|---|
| `intercept_tool_call` p50/p95 (n=200) | **0.06ms / 0.09ms** | <250ms |
| Concurrent intercepts (8×20 threads) | 160 unique ids, 0.01s | all succeed |
| Audit chain 500 events record+verify | <0.01s | <5s |
| Tape ingest+verify 100 spans | <0.01s | <5s |

These are baselines, not SLOs — no throughput claim beyond the test rig.

## Evidence

- `pytest tests/test_m6_fault_injection_and_perf.py -v` → **9 passed in 0.31s**

## Known Limits

- Fault surface covered: validation, persistence corruption, races, tamper.
  Not covered: OS-level faults (SIGKILL mid-write, disk-full), network
  partitions — no chaos/failure-injection framework yet.
- Perf baselines are single-machine; CI runners will differ. Ceilings are
  generous (≥10× headroom) to avoid flaky gates.
- M6 full scope (Phase 12/13) also wants provider-outage and worker-crash
  e2e faults — partially covered by existing adapter/retry tests; a
  dedicated crash-recovery suite remains open.
