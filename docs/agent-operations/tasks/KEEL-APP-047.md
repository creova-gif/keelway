### TASK HANDOFF RECORD
- **TASK ID**: KEEL-APP-047
- **TASK TITLE**: KStack Async Dispatch — `execute_skill_async` + real `golden-eval` handler
- **CURRENT STATUS**: READY_FOR_REVIEW
- **LAST AGENT**: Devin
- **DATE**: 2026-11-19
- **BRANCH**: `feature/keel-app-047-async-dispatch`
- **HEAD COMMIT**: (pending)

#### OBJECTIVE & ACCEPTANCE CRITERIA
- [x] `KStackRegistry.execute_skill_async` awaits awaitable handler results; proof building shared via `_resolve_for_execution`/`_seal_execution`.
- [x] Sync `execute_skill` fails closed (records `success: false`) on awaitable results and closes the coroutine — no leaked coroutine, no coroutine repr sealed into a proof.
- [x] `kstack/golden-eval` wired to `DriftDetector.run_evaluation_and_create_receipt` via `EvaluationReceiptStore` (honest 501→real handler); `compare_to` rejected until drift wiring exists.
- [x] Endpoint dispatches async; live verification proves sealed proofs for sync and async handlers.

#### WORK COMPLETED & FILES MODIFIED
- `core/kstack/registry.py`: shared helpers + `execute_skill_async`.
- `core/kstack/handlers.py`: async `_golden_eval` handler registered.
- `core/api/routes.py`: endpoint awaits `execute_skill_async`.
- `tests/test_kstack_execute.py`: +4 tests (real benchmark, compare_to rejection, sync-awaitable fail-closed, endpoint sealed proof).

#### TESTS EXECUTED & EVIDENCE
- `pytest tests/test_kstack_execute.py`: `15 passed`
- Live isolated stack: `POST /v1/kstack/execute {"name":"kstack/golden-eval"}` → `success:true`, `total_tasks:10`, `pass_rate_pct:90.0`, sealed receipt + signature; `sbom-audit` sealed proof; 501/404/401 verified.

#### KNOWN RISKS & BLOCKERS
- `save_receipt:true` persists to `.keelway/evals/receipts` (platform state dir) — intended.
- `sbom-audit` reported `component_count:0` in the isolated env (no dependency manifest found there) — honest output, env-specific.

#### NEXT RECOMMENDED ACTION
- Merge; then drift-compare handler and Agents-view live registry read.
