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
- `pytest tests/test_m6_crash_recovery.py -v` → **6 passed** (SIGKILL/WAL,
  read-only dir, auto-mkdir, `:memory:` fallback, torn page, concurrent writers)
- GitHub Actions run `44208133157` (commit `0e548e5`) → **all 4 jobs green**
  on Python 3.11 and 3.14, including the torn-page test on Linux CI

Torn-page determinism notes (hard-won on CI): the corrupt target is the
`harness_interceptions` root page from `sqlite_master`, never a guessed
offset; each detection check runs on its own byte-level copy with a fresh
first connection (a detecting connection's close-checkpoint can rewrite the
torn page for later connections); `quick_check` output is asserted as
`!= "ok"` rather than `pytest.raises` because newer SQLite builds report
corruption as result rows instead of raising.

## Follow-on: OS-level crash suite (added 2026-11-17)

`tests/test_m6_crash_recovery.py` — 6 tests against real subprocesses and
filesystem states:

| Test | Verified contract |
|---|---|
| SIGKILL mid-write | Fresh engine reopens the DB, WAL replays, committed rows intact, writes resume |
| Read-only directory | `sqlite3.OperationalError` on open — fails closed |
| Missing parent dirs | **Auto-created** (`_resolve_sqlite_target` mkdirs) — actual contract |
| Unwritable parent (file blocks mkdir) | **Silent `:memory:` fallback** — works but evidence is ephemeral. Asserted so a future fail-closed fix can't regress silently; flagged as an evidence-loss surface |
| Torn page (corrupt page mid-file) | `quick_check` detects — `DatabaseError` or non-`ok` rows, both accepted (version-dependent); first engine write through a torn copy raises — corruption is lazy, writes surface it |
| Two writers, one SIGKILLed | `integrity_check ok`; surviving + fresh engine consistent |

## Known Limits

- Perf baselines are single-machine; CI runners will differ. Ceilings are
  generous (≥10× headroom) to avoid flaky gates.
- Reads on uncorrupted pages of a partially-torn DB can still succeed —
  page-granularity is inherent to SQLite; `integrity_check` is the
  full-store detector.
- `:memory:` fallback on unwritable parents means interception evidence is
  silently lost — see surfaced finding above.
