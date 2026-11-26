# KEEL-ENG-063 — strict_optional ratchet (mypy gate tightening)

## Problem
KEEL-ENG-062 landed the mypy gate with `strict_optional = false` — the
first-gate posture. Enabling `strict_optional` reported **122 errors in
29 files** under pinned `mypy==2.4.1`, all Optional-handling defects:
`X | None` attribute/index/operand access without narrowing (`union-attr`,
`index`, `operator` — ~55%), `X | None` passed to `X` (`arg-type` — ~25%),
`X | None` assigned/returned where `X` declared, and one implicit-Optional
parameter (`cli.py cmd_chat system_prompt`, rejected under
`no_implicit_optional=True`).

## What shipped
- `pyproject.toml`: `strict_optional = true`. Gate now enforces it.
- **0 errors on 297 files** under pinned `mypy==2.4.1` (both the
  `--strict-optional` flag and the config read).
- 30 files touched, +107/-76 lines. Fix idioms, in order of frequency:
  - `x is None` guards folded into existing `hasattr`/readiness checks
    (gateway adapters, routes, studio, auth).
  - `assert` for structural invariants (`Report.ok ⇒ manifest is not None`
    — the property literally requires it).
  - Walrus narrowing in `x if isinstance((x := get(...)), dict) else {}`
    codegen idiom (line-neutral — `structured_self_healing.py` stayed at
    478 under the phase16 `<480` cap).
  - Per-branch variable renames where a name was reused across elif
    branches with different types (`src`/`dst`, `c`→`cand`, `record`→
    `tok_record`, `payload`→`fb_payload`).
  - `Optional[str]` model fallbacks resolved to the canonical
    `keelway-core:7b` default in `opencore/serving.py` and
    `opencore/runtime.py` (`request.model` is `Optional[str]` in the
    schema; bridges/serving now resolve it before use).
  - `Optional[...]` parameter annotations where `None` was the real
    contract (`cmd_chat system_prompt`, `mesh_prune payload`).

## Real defects fixed (not just annotations)
- `auth.py` pairing-code spend: `_aware(record.expires_at)` returns
  `Optional[datetime]` — a `None` expiry would have crashed the `<=`
  comparison. Now fails closed (unspendable).
- `mcp_client._start_subprocess`: called with `self.command` unverified
  (the `not self.command` guard lived in `connect()` only) — guard
  hoisted into the method itself.
- `anthropic.py`: `httpx` headers dict carried `api_key: Optional[str]` —
  a `None` key would crash inside httpx. Now fails closed with a clear
  RuntimeError.
- `routes.py` WS gate: `principal.can(...)` invoked while `principal`
  could still be `None` when `auth_required` is off — now closes the
  socket with `Unauthenticated` instead of crashing.
- `runner.py`: `ok` flag no longer implies `res is not None` — both
  checked before `res.model_dump()`.
- `cli.py models import`: `import_bundle(None)` path — missing `--path`
  now prints usage instead of crashing inside the importer.

## Verification
- `python -m mypy` (2.4.1, config `strict_optional = true`): **0 errors /
  297 files**
- `ruff check .`: clean
- `py_compile` on all 30 touched files: clean
- Parity: `test_phase15_sdk_and_website_sync`, `test_phase16_sdk_and_
  website_sync` — 6 passed (line caps intact; edits to the capped file
  were line-neutral)
- Focused: ~280 tests across auth, gateway, manifests, mcp, worktree,
  self-healing, studio, opencore, flight tape, pilot kit, enterprise,
  receipt verifier, evidence room, cli_ai — all green
- Known pre-existing flake: `test_cli_ai.py::
  test_cli_swarm_offline_benchmark_json` hangs on the documented
  `MiroFishSwarmHarness.run_full_experiment` event-loop deadlock
  (proven identical on clean HEAD in ENG-062).

## Risks
- The `keelway-core:7b` default resolution for absent `request.model` is
  a behavior-visible choice: requests that previously carried `None`
  through to a crash or an Ollama `400` now resolve to the canonical
  default. Matches the file's own `base_model_id` convention.
- `agent.flight_recorder` is now honestly `Optional` — consumers that
  assumed non-None (e.g. `demo.py`) got explicit guards.
