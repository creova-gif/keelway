# KEEL-ENG-070 — `disallow_untyped_defs` mypy ratchet

- **Status**: COMPLETED
- **Agent**: Devin
- **Date**: 2026-11-27
- **Branch**: `chore/keel-eng-070-untyped-defs`

## Objective & acceptance

P2 backlog ratchet (continues KEEL-ENG-062..065 pattern): enable
`disallow_untyped_defs` in the mypy first-gate config. Acceptance:
flag enabled, `mypy` clean on the full checked set, `ruff` clean,
targeted tests green, no behavior change.

## Approach

- Inventory: 177 `no-untyped-def` errors across 30 files (155 missing
  return types, 22 missing param annotations).
- `ruff check --select ANN201,ANN202,ANN204,ANN205 --fix --unsafe-fixes`
  fixed 71 safe cases automatically (mostly `__init__`, `__post_init__`,
  mutators → `-> None`).
- Remaining ~105 sites annotated by hand: FastAPI handlers →
  `Dict[str, Any]` / `StreamingResponse` / `Union`, SSE generators →
  `AsyncGenerator[str, None]`, context managers → precise `Self`-style
  returns, params → `Mapping`/`Coroutine`/`Namespace`/`TYPE_CHECKING`
  forward refs as appropriate.

## Changes of note (beyond mechanical annotations)

- `core/api/routes.py`: `execute_terminal_command` annotated `-> Never`
  (always raises — matches the fail-closed "no verified isolation
  boundary" design); `assert agent.guard is not None` added before
  `agent.guard.signed = ...` — a latent None-deref the ratchet surfaced.
- `cli.py` `_main`: added explicit `return 0` for the unmatched-command
  fall-through (previously implicit `None`, coerced by `main() or 0`).
- FastAPI response-model guard: `response_model=None` added to
  `/v1/chat/completions`, `/v1/responses`, `/v1/terminal/exec` —
  `Union[StreamingResponse, Dict]` and `Never` are not valid Pydantic
  response fields; runtime behavior unchanged.

## Evidence

- `mypy` (2.4.1, with `disallow_untyped_defs = true`): **0 errors, 297 files**
- `ruff check .`: clean
- `pytest` targeted: 188 passed — test_api, test_cli_ai, test_ast_index,
  test_agent_guard, test_editor_sync_bridge, test_evidence_room,
  test_sdk, test_speculative, test_flight_recorder,
  test_entitlements_and_sbom, test_mcp_client_and_plugins,
  test_sync_engine, test_core_runner_routes, test_runner_daemon,
  test_runner_environments, test_runner_spool, test_kstack_execute,
  test_p2p_mesh, test_mesh_api, test_external_agent_acp,
  test_guided_builder, test_mcp_stdio, test_eval_gating
- `py_compile` on all edited entry points: clean
- 31 files, +215/−206 — annotations only, no logic changes

## Residual

Newly typed function bodies are now under `check_untyped_defs` scrutiny;
the only non-annotation change required was the `agent.guard` assert.
`strict_optional`-grade Optional tightening remains a separate ratchet.
