# KEEL-APP-050 — Sovereign CLI: `skill execute` for KStack Handlers

- **STATUS**: VERIFIED_COMPLETE
- **DATE**: 2026-11-19
- **BRANCH**: `feature/keel-app-050-cli-kstack-execute`
- **SCOPE**: `cli.py` + `tests/test_kstack_execute.py` (CLI surface; no backend changes)

## OBJECTIVE & ACCEPTANCE CRITERIA

- [x] `python cli.py skill execute <name> [--inputs JSON] [--actor ID]` executes a skill through `BUILTIN_HANDLERS` + `execute_skill_async` — the same dispatch path as `POST /v1/kstack/execute`, in-process (no HTTP, no server required).
- [x] Prints the sealed `SkillExecutionProof` as JSON (`execution_id`, `skill_digest_sha256`, `actor`, `inputs`, `outputs`, `permissions_used`, `success`, `duration_ms`, `timestamp_utc`, `signature_sha256`).
- [x] Fail-closed parity with the API: unknown skill → `[-] Skill '<name>' not found.` exit 1; registered-but-handlerless skill → `[-] ... no registered execution handler.` exit 1; revoked skill → `PermissionError` path → exit 1; handler failure → sealed proof with `success:false`, exit 1.
- [x] `--inputs` must be a JSON object — malformed JSON and non-object values fail before dispatch with clear errors.
- [x] `--actor` identity is recorded in the sealed proof (default `cli`).
- [x] Async handlers work through `asyncio.run(execute_skill_async)` — `golden-eval` runs the real 10-task benchmark from the CLI (`pass_rate_pct: 90.0`, real receipt outputs).

## FILES MODIFIED

- `cli.py` — `cmd_skill` gains `inputs`/`actor` params + `execute` branch; `skill execute` argparse subcommand; dispatch wiring.
- `tests/test_kstack_execute.py` — 5 new tests: sealed-proof happy path, actor/inputs recorded, no-handler + unknown fail-closed, malformed inputs rejected, end-to-end argparse dispatch via `main()` (`SystemExit` carries the code).

## TESTS & EVIDENCE

- `pytest tests/test_kstack_execute.py` — 20/20 pass.
- `pytest tests/test_kstack_kbrain_khub_kspaces_kflow.py tests/test_keelway_core_cli.py tests/test_cli_init_and_banner.py` — 28 pass, 1 pre-existing asyncio-env skip.
- Manual: `python cli.py skill execute kstack/sbom-audit` → real CycloneDX SBOM in sealed proof; `kstack/golden-eval` → `pass_rate_pct: 90.0` real receipt; `kstack/plan` → exit 1 no-handler; `kstack/nope-skill` → exit 1 not-found; malformed `--inputs` → exit 1.

## HONEST LIMITS

- CLI execution is unauthenticated in-process (actor is an assertion, not a credential) — same trust model as every other `cli.py` command. The HTTP path remains the RBAC-gated surface (`EXECUTE_AGENT`).
- Process skills (`kstack/plan`, `kstack/review`, `kstack/wcag-aa`) intentionally exit 1 with "no registered execution handler" — they are contracts, not services.
- `golden-eval` `compare_to` drift wiring remains parked.
