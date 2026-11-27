# KEEL-ENG-065 — warn_unreachable ratchet (mypy gate tightening)

## Problem
After KEEL-ENG-063/064 the gate enforces `strict_optional` and
`check_untyped_defs`, but dead code still slips through: unreachable
statements, impossible `isinstance` arms, and platform-gated branches
folded away on the developer's OS. Enabling `warn_unreachable`
reported **23 errors in 13 files**.

## What shipped
- `pyproject.toml`: `warn_unreachable = true` under `[tool.mypy]`.
- 23 errors fixed across 13 files; net +36/-35 lines.

## Fix classes
- **Platform-folded branches** (`sandbox.py` ×2, `cli_tui.py`): mypy
  folds `sys.platform == "linux"`/`!=`/`startswith` against the host
  OS, so Linux-only code reads as dead on macOS. Bound `sys.platform`
  to a local first — the comparison is no longer folded, Linux CI and
  macOS dev both see all branches, and `monkeypatch.setattr(sys,
  "platform", ...)` keeps working (verified by
  `test_sandbox_diagnose_and_bubblewrap_diagnostics`).
- **Impossible isinstance arms** (`mcp_lockfile_and_bench.py` ×2,
  `agent_loop.py`): `str`/`bytes` arm after a `list`/`tuple` check can
  never fire; `dict` check on a `str` param likewise. Removed the dead
  arm / widened the param to `Any` where the guard is intentional.
- **Declared-type defensive guards** (`signing.py`,
  `flight_tape.py`, `receipt_verifier.py`, `spool.py`): functions
  typed `Dict`/`Sequence[Dict]`/`Union[str, Path, Dict]` but written
  to reject malformed wire input. Widened the parameters to `Any` so
  the guards are real, matching the untrusted-input contract.
- **Real dead code** (`multi_agent.py`, `langgraph_migrator.py`,
  `platform_enterprise_routes.py`): fallback return after an
  exhaustive `AgentRole` if/elif chain (missing-return now guards new
  enum members), `v_ast is None` on `ast.Dict.values` (never None —
  keys can be for `**` unpacking, values can't), and a `dict` guard on
  a pydantic-enforced `List[Dict]` field.
- **Narrowing artifacts** (`kstack/registry.py`,
  `platform_runtime_client.py`): `outputs` declared `Dict` made the
  coroutine check dead — bound the raw handler result separately;
  `self.done` mutated inside `_parse_line` defeated mypy's attr
  narrowing — `_parse_line` now returns `(event, is_done)` so the
  done signal is explicit.

## Verification
- `python -m mypy` (2.4.1): 0 errors / 297 files
- `ruff check .`: clean; `py_compile` all 13 files: clean
- 170 focused tests green incl. `test_agent_sandbox`,
  `test_runner_spool`, `test_receipt_verifier`, `test_kstack_execute`,
  `test_multi_agent_coordination`, `test_licence_signing`,
  `test_phase11_flight_tape_otel_and_langgraph_migrator`,
  `test_phase20_mcp_lockfile_and_bench_cli`,
  `test_phase21_kstack_registry_sdk_parity`,
  `test_enterprise_idp_interop`, `test_sdk_platform`,
  `test_unified_platform`, `test_platform_persistence_and_enterprise`,
  `test_phase9_enterprise_identity_siem_metrics`,
  `test_agent_loop{,_policy_quorum}`
- Line-cap parity: no touched file is in the phase15/16 <480 lists

## Remaining ratchet headroom
- `disallow_untyped_defs`: 176 errors / 30 files (signature
  annotations; mechanical but large)
- `warn_return_any`: 356 errors / mostly `Any`-returning helpers —
  high noise-to-signal
- `packages` expansion beyond `core` remains open
