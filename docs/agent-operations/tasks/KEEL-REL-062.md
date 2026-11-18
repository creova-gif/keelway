# KEEL-REL-062 — Durable Interval Schedules (D-002)

| Field | Value |
|---|---|
| **Status** | `IN_PROGRESS` |
| **Category** | `RELEASE / RELIABILITY / STATE` |
| **Agent** | Devin |
| **Date** | 2026-11-18 |
| **Branch** | `fix/KEEL-REL-062-durable-schedules` |

## Objective
Release-readiness defect **D-002 (P1)**: `KFlow/scheduler/runner-queue
in-memory; restart loses state`. The runner spool is already durable
(`core/runner/spool.py` is filesystem-backed by design). The real gap is
`FlowScheduler`: schedules lived only in a process dict and were lost on
restart, with `GET /v1/schedules` honestly reporting `persistent: false`.

## Acceptance criteria
1. `flow_scheduler` singleton persists to
   `$KEELWAY_STATE_DIR/schedules.json` (established env convention, see
   `core/platform/signing.py`) or `~/.keelway/schedules.json` with
   `legacy_aware` fallback to `~/.kora/schedules.json`.
2. Survives restart: add → kill → new instance sees the schedule with
   runs_completed/next_run intact.
3. Writes are atomic (tmp + rename); corrupt/missing files load to empty
   without crashing startup; persistence failure never kills the loop.
4. `GET /v1/schedules` `persistent` flag reflects actual config.
5. `FlowScheduler()` without a path stays in-memory (existing test
   semantics); conftest sets `KEELWAY_STATE_DIR` so tests never write
   real user state.

## Out of scope
- KFlow DAG registration persistence (`kflow_engine._flows` remains
  process-scoped — separate storage-model decision, recorded in
  `16-known-defects.csv` under D-002 residual).
- Runner queue: already durable (spool is filesystem-backed).

## Verification
- tests/test_schedule_and_token_admin.py + new persistence tests
