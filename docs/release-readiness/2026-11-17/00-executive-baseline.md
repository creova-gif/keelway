# Executive Baseline — 2026-11-17

- Repo: creova-gif/kora (product branding: Keelway v1.1.0 — see ADR-001, OWNER_DECISION_REQUIRED)
- Baseline main SHA: 37bbad2 (branch `audit/release-readiness-2026-11-17` cut from it)
- Environment: macOS (Darwin arm64), Python 3.14.0, Node v24.11.1, Go 1.25.6, Docker 29.6.2, git 2.54.0
- Test suite at baseline: 936 passed, 1 skipped, 1 warning (StarletteDeprecationWarning)
- Env var names referenced in code (names only, no values): ANTHROPIC_API_KEY, OPENAI_API_KEY, GEMINI_API_KEY, KEELWAY_DEBUG, KEELWAY_DEV_CLI, KEELWAY_GITHUB_WEBHOOK_SECRET, KEELWAY_GOVERNANCE_ALLOWED_ORIGINS, KEELWAY_LIVE_MODEL, KEELWAY_LIVE_MODEL_URL, KEELWAY_REF_DB, OLLAMA_MODELS + standard PATH/TERM/USER/VIRTUAL_ENV/NO_COLOR/PYTHONPATH. env.example documents 24 variables.

## Verdict (honest)

The product is a single-user local-first FastAPI + vanilla-JS Studio IDE. The past sessions verified the *governance/observability* surface end-to-end (approvals, evidence, flight tapes, RBAC matrix, token admin, scheduler, team orchestration — all live-verified in browser with real API data). The golden coding loop (import repo → agent plan → approval → isolated edit → test → diff → checkpoint → PR) is PARTIAL: individual pieces exist and were verified, but the composed 30-step journey has not been run end-to-end from a clean environment. Multi-tenant enterprise features (SSO/SCIM/org directory) are absent by design today — MISSING, not broken.

## Highest-risk architecture mismatches

1. Two API surfaces described in README (core :7420 vs governance :8000) — the running product serves everything from one FastAPI app; a separate `governance` API exists in code but its deployment authority is UNVERIFIED.
2. Persistence is file-based JSON under `.keelway/` + in-memory registries (KFlow, scheduler, runner jobs) — no migration system; restart loses scheduler/queue state (UI labels this honestly).
3. `cli.py` (~2.5k LOC monolith, 56 commands) vs `keelway_core/cli.py` reference CLI — two CLIs with different rigor.
4. Sandbox/isolated-runner: terminal execution is fail-closed when isolation unverifiable (good), but no Docker Runner implementation of the report's `create/exec/snapshot/restore` contract — UNVERIFIED gap.

## Gate 0 status: PARTIAL → continuing inventory (≥95% endpoint/command coverage achieved in CSVs)
