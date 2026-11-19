# KEEL-APP-051 — KStack `golden-eval`: `compare_to` Drift Wiring

- **STATUS**: VERIFIED_COMPLETE
- **DATE**: 2026-11-19
- **BRANCH**: `feature/keel-app-051-golden-eval-drift`
- **SCOPE**: `core/kstack/handlers.py` + `evals/drift_detector.py` + `tests/test_kstack_execute.py`

## OBJECTIVE & ACCEPTANCE CRITERIA

- [x] `compare_to=<eval_run_id>` resolves the named receipt from the store and attaches a real `DriftAnalysis` (`drift` field) to the handler output — `DriftDetector.compare`, not a new comparison mechanism.
- [x] `compare_to="latest"` resolves the most recent persisted receipt, excluding the candidate itself (self-comparison can never report zero drift by construction).
- [x] Unresolvable baseline → `ValueError` → sealed `success:false` `SkillExecutionProof` on the execute path (fail-closed, never silently ignored).
- [x] `save_receipt:false` still compares — the store is opened read-only for the baseline; the candidate is not persisted. Verified: store holds exactly the baseline after a `save_receipt:false` compare run.
- [x] New optional `receipts_dir` input lets callers (and tests) point at an alternate receipt store; default remains `.keelway/evals/receipts`.
- [x] Same-second run-id collision fixed: auto `eval_run_id` is now ms-precision (`eval_{int(time.time()*1000)}`) — two back-to-back evals can no longer overwrite each other's receipt file.
- [x] Parity across all three surfaces — the same `BUILTIN_HANDLERS` dispatch serves `POST /v1/kstack/execute`, `execute_skill_async`, and `cli.py skill execute` with no surface-specific code.
- [x] `SKILL.md` contract was already truthful (`compare_to` documented, `drift` output declared) — the implementation now matches it.

## FILES MODIFIED

- `core/kstack/handlers.py` — `_golden_eval` accepts `compare_to` (run id or `"latest"`) and `receipts_dir`; loads the baseline via `EvaluationReceiptStore`, attaches `DriftDetector.compare(...).to_dict()` as `outputs.drift`; raises `ValueError` on unresolvable baselines.
- `evals/drift_detector.py` — auto `eval_run_id` uses ms-precision timestamps (same-second collision fix).
- `tests/test_kstack_execute.py` — 4 new tests: explicit-baseline drift attached + candidate-not-persisted, `"latest"` resolves the newest prior receipt, unknown baseline `ValueError`, and sealed `success:false` proof through `execute_skill_async`.

## TESTS & EVIDENCE

- `pytest tests/test_kstack_execute.py tests/test_eval_drift.py` — 29 passed, 1 pre-existing asyncio-env skip.
- Manual (tmp receipts dir): baseline run → `compare_to=<id>` returns `drift.baseline_run_id`/`candidate_run_id` with `drift_severity: NONE`; `compare_to="latest"` resolves the newest prior receipt; `compare_to="eval_nope"` raises `baseline receipt 'eval_nope' not found in <dir>`.
- `DriftDetector.compare` semantics (task-regression → CRITICAL, pass-rate drop → HIGH, latency >25% → MEDIUM) were already covered by `tests/test_eval_drift.py`; the new tests cover only the handler wiring.

## HONEST LIMITS

- `compare_to` requires the baseline receipt to live in the same receipts dir as the store being read — there is no cross-store or remote receipt lookup (and none is claimed).
- The drift verdict is only as meaningful as the deterministic benchmark — it compares the 10-task golden suite, not production traffic.
- Process skills (`kstack/plan`, `kstack/review`, `kstack/wcag-aa`) remain intentionally handlerless (501 / exit 1).
