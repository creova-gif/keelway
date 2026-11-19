# KEEL-REL-063 — Composed Coding Journey Test (D-003) + httpx2 Test Harness (D-007)

| Field | Value |
|---|---|
| **Status** | `IN_PROGRESS` |
| **Category** | `RELEASE / TESTING` |
| **Agent** | Devin |
| **Date** | 2026-11-18 |
| **Branch** | `feature/KEEL-REL-063-composed-journey` |

## Objective
Release-readiness defects **D-003 (P1)** and **D-007 (P3)**.

- D-003: no composed 30-step coding journey test from a clean environment.
  The two existing 20-stage journey tests cover the platform/user story but
  not the ordered GJ-1 coding slice through the real API.
- D-007: `StarletteDeprecationWarning` emitted by `httpx`/TestClient during
  the suite — upstream prescribes `httpx2`, but adopting it was rejected
  after verification: httpx2 2.16.x changes TestClient streaming semantics
  and breaks SSE reconnection (`test_studio_realtime_events` fails 0==1).
  Resolution is a scoped `pytest.ini` `filterwarnings` suppression.

## Acceptance criteria
1. One composed test drives ~30 ordered steps through `core.main:app`
   (ADR-0045 single authority) against a clean git repo: launch → workspace
   register/activate → file tree/read → traversal refusal → agent run →
   P-10 pause → fail-closed proof → approval → apply → isolated worktree →
   checkpoint → discard-and-restore rollback → real pytest → diff → commit
   proposal → commit → PR proposal → honest CI status → flight tape →
   Merkle audit → durable schedule → cleanup.
2. Every step uses real routes on `core.main:app`; no stubs, no mocks.
3. State isolation: `KEELWAY_STATE_DIR` + `DATABASE_URL` temp via conftest;
   durable-schedule persistence proven by reading `schedules.json` on disk.
4. D-007 resolved honestly: `httpx2` evaluated and rejected (breaks
   `test_studio_realtime_events` — SSE subscribers never register under
   httpx2's transport). `pytest.ini` gains one scoped filter line for
   `starlette.exceptions.StarletteDeprecationWarning` with a comment
   explaining why the upstream fix is deferred.

## Implementation
- `tests/test_composed_coding_journey.py` (new): single composed test, 30
  numbered steps. P-10 negative paths included (file write stays unapplied
  pre-approval; non-boolean approve → 400; path traversal → 403). Rollback
  proven by discarding the fix then restoring the checkpoint via API.
- `pytest.ini`: single scoped `filterwarnings` entry (the live pytest
  config; `pyproject.toml`'s `[tool.pytest.ini_options]` is dead — pytest.ini
  takes precedence and already carries every real setting).
- `docs/release-readiness/2026-11-17/16-known-defects.csv`: D-003, D-007
  marked closed with evidence.

## Verification
- `pytest tests/test_composed_coding_journey.py -x -q`: **1 passed**
- `pytest tests/test_composed_coding_journey.py tests/test_full_beta_developer_journey.py tests/test_full_beta_user_journey.py tests/test_workspace_registry.py tests/test_schedule_and_token_admin.py -x -q`: **21 passed**
- `pytest tests/test_studio_realtime_events.py tests/test_composed_coding_journey.py -q`: **9 passed, 0 warnings**
- httpx2 causation proven: same file fails `assert 0 == 1` with httpx2 installed, 8 passed without

## Handoff notes
- Remaining open defects after this slice: D-004 (isolated Runner backend),
  D-005 (canonical-CLI decision — owner scope), OD-3/OD-4/OD-5 decisions.
- D-004 is a real feature (Docker create/exec/snapshot backend); D-005
  needs an ADR-class decision on `cli.py` vs `keelway_core/cli.py`.
