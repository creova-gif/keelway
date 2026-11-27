# 01 — Repository Audit (evidence-based)

**Date:** 2026-11-27 ~00:30 UTC · **Auditor:** Devin · **Baseline:** `bdab521`

## 1. Verified commands (run this turn)

| Command | Result |
| ------- | ------ |
| `python -m mypy` (2.4.1, strict_optional+check_untyped_defs+warn_unreachable) | **0 errors / 297 files** |
| `ruff check .` (F+B ruleset) | clean |
| `python -m pytest --collect-only -q` | **1565 tests / 212 files** |
| `dev-app: npm run build` (vite → `core/dev_app_dist`) | **pass 2.16s** (1.2 MB js / 322 kB gzip — chunk-size warning only) |
| `dev-app: npm run typecheck` (tsc --noEmit) | pass |
| `website: npm run build` (next build) | **pass** — all routes static except middleware (34.5 kB) |
| CI (latest `main`): test 3.11/3.14, website-devapp-and-sdks, wheel-sbom | all green on `bdab521` |

## 2. Surface inventory

| Surface | Path | State | Notes |
| ------- | ---- | ----- | ----- |
| Product UI (React) | `dev-app/` → `core/dev_app_dist` | WORKING | 10+ views: agents, files, records, settings, platform panels; 25 test files (~72 tests) |
| Backend API | `core/` FastAPI (`core.main:app`) | WORKING | ~30 route modules under `core/api/`; REST + SSE |
| CLI | `cli.py` (~3.3k LOC, 56+ subcommands) | WORKING | `init/dev/desktop/demo/doctor/mobile/sync/pilot/token/…` |
| Governance plane | `keelway/` (46 py files, `api/app.py`) | PARTIAL | second API surface (:8000); deployment authority per ADR-0045 |
| Reference CLI | `keelway_core/` (3 files) | DEPRECATED | excluded from wheel (KEEL-REL-065) |
| Marketing site (deployed) | `website/` → Vercel `kora-sable` | WORKING | Next 15.5.x, /product /legal /blog /sign-in /offline; axe WCAG 2.2 AA in CI |
| V3 site (successor) | `web-next/` | IN FLIGHT | tokens-freshness gate vs dev-app; not the deployed site |
| SDKs | `sdk/typescript`, `sdk/go` | WORKING | zero-dep posture locked; parity tests per phase |
| Mobile companion | `mobile/` (Expo SDK 54) | PARTIAL | pairing flow; device re-verify open on live stack |
| Deploy | `Dockerfile`, `docker-compose.yml`, `deploy/{helm,k8s,terraform}` | UNVERIFIED E2E | compose defines control-plane+platform; no deploy smoke test found |
| Legacy console | `web-console/` | STALE | single `index.html`, superseded by dev-app |

## 3. Auth & security posture (verified)

- Token model: per-process **launch token** (owner), named role tokens
  (hashed SHA-256 at rest), expiring phone pairing codes; dev-app sends
  `X-Studio-Token` + `Authorization: Bearer` (token also accepted via
  `?token=` URL param — flag in 07).
- RBAC: `Principal.can(permission)` enforced at routes; phone tokens
  restricted to `PHONE_ROUTES` allowlist.
- Sandbox: macOS seatbelt + Linux bubblewrap, fail-closed; 6 live
  confinement tests on Linux CI.
- CI security gates: gitleaks, pip-audit on `requirements.lock`
  (hash-verified), no criticals at last audit.
- Known residual: `dev-app` token in URL query (`?token=`) lands in
  browser history/server logs — acceptable for localhost, must be
  documented or removed before any non-localhost deploy.

## 4. Persistence (verified)

- SQLite via SQLAlchemy 2.x (`core/storage/models.py`, `Mapped` cols)
  at `KEELWAY_DB_PATH` (audit ledger, tokens, schedules, registry).
- File JSON state under `.keelway/` + in-memory registries for
  scheduler/runner queue (restart loss is labeled in UI).
- **No migration system** — schema evolution is additive-by-hand.
- `InteractiveChatSession.history` is in-process memory — chat
  conversations do NOT persist across restarts. **P0 gap.**

## 5. Implemented / partial / missing (vs beta scope)

**Implemented & tested:** model gateway + provider adapters +
air-gap fail-closed; token auth + RBAC; sandboxed execution; Merkle
flight tapes + receipts; workspace registry; SBOM; doctor diagnostics;
10-axis doctor; settings panels; website incl. legal/blog/signup.

**Partial (ship-blocking to verify):** conversation persistence;
composed 30-step coding journey (test exists since REL-063 — re-verify
on beta env); deploy path (compose/k8s unsmoked); mesh multi-node;
Monaco LSP/symbol nav; docker runner environment contract.

**Missing by design:** SSO/SCIM/org directory; multi-user sessions;
user self-registration. Do NOT build these for beta — document as
limitations, or the beta positioning changes to hosted offering
(owner decision).

## 6. Environmental risks (proven this week)

- Host Ollama at hardcoded `127.0.0.1:11434` (`core/opencore/runtime.py`
  `OllamaBridge`) wedges under load → LOCAL-path tests flake ~120 s.
  Pre-existing; ignores `OLLAMA_BASE_URL`.
- `MiroFishSwarmHarness.run_full_experiment` event-loop deadlock —
  `test_cli_swarm_offline_benchmark_json` hangs on clean HEAD.
- One Node-24 ESM failure locally; CI pins Node 22 (fine).

## 7. Bottom line

The engineering base is **unusually strong for a beta**: 1565 tests,
five CI quality gates on two Python legs, two green web builds, and
a 10-day-old audit whose every defect was since closed. The beta risk
is not code health — it is **scope honesty**: ship the sovereign
local-first product that exists, document the SaaS modules that do
not, and close the ~6 real gaps in `04_ENGINEERING_BACKLOG.md`.
