# 13 — Release Report (release candidate, 2026-11-27)

## 1. Initial repository assessment
See `01_REPOSITORY_AUDIT.md`. Verdict: healthy engineering base — 1,565
pytest tests, full CI matrix (3.11/3.14, mypy+ruff gates, wheel+SBOM,
dev-app build), sovereign single-operator architecture. The risk was
scope honesty, not capability: single-user local-first product — no
registration/SSO/multi-tenancy by design.

## 2. Architecture changes
No rewrites. Two scoped additions:
- `keelway_conversations` table + session bind/persist (PR #256).
- `settings.ollama_base_url` consumed by all Ollama/vLLM bridge surfaces
  (PR #258) — config already existed; bridges previously hardcoded
  `127.0.0.1:11434`.

## 3. Completed features
| PR | Deliverable |
| --- | ----------- |
| #255 | `docs/beta/` 00-13 evidence-based audit + backlog (KEEL-BETA-001) |
| #256 | Conversation persistence — P0-1 (KEEL-ENG-066) |
| #258 | Ollama wedge guard — P0-6 (KEEL-ENG-067) |
| #259 | `?token=` log mitigation + honest limitations — P0-4 (KEEL-ENG-068) |
| — | P0-2 golden journey: verified green on clean main (see §5) |
| — | P0-3 compose deploy smoke: verified live (see §8) |
| — | P0-5 onboarding path: cold-run verified (see §8) |
| #261 | Offline swarm determinism — P1-1 (KEEL-ENG-069): measured root cause (real Ollama inference in "offline" mode, ~24s vs 30s budget); zero-network mock local provider; `swarm run` 23.8s→0.63s |

**P1 verification sweep (no code needed):**
- P1-2 usage analytics: `SettingsBillingPanel` reads real spend via
  `GET /v1/governance/tenants/default` + marketplace settlement; ARIA
  progressbars + honest unreachable state.
- P1-3 file-intelligence upload: `POST /v1/files/upload` journey green
  (3/3 tests, ZipSlip-protected); no UI surface ships a fake upload.
- P1-4 Monaco/symbol nav: self-hosted Monaco assets present; symbol nav
  wired `/v1/codebase/symbols` → `handleSelectSymbol` → `setPosition`.
- P1-5 runner env contract: `GET /v1/runner/environment/status` honest
  (docker probe + diagnostic); 12/12 tests green.

## 4. Remaining limitations
See `11_KNOWN_LIMITATIONS.md` — all entries verified honest. Headline:
single-operator auth model; `?token=` URL convention retained (documented,
access-log-safe); in-memory scheduler state resets on restart; no schema
migration framework; `keelway swarm` offline mode now deterministic —
live inference only under `--live` (P1-1 resolved); desktop not
packaged/signed; helm/k8s/terraform unverified E2E.

## 5. Test results and evidence
- Baseline: 1,565 pytest tests; dev-app ~72 tests; both web builds green.
- `pytest tests/test_composed_coding_journey.py` → 1 passed in 3.22s
  (P0-2 golden journey, clean `origin/main`).
- `pytest tests/test_conversation_persistence.py` → 7 passed (P0-1).
- `pytest tests/test_ollama_wedge_guard.py` + related → 19 passed in 0.83s.
- `pytest tests/test_cli_ai.py` → 5 passed in 3.91s (swarm test previously
  timed out at 30s; run now completes in 0.63s deterministically).
- `pytest tests/test_file_upload.py` → 3 passed; `pytest
  tests/test_runner_environments.py` → 12 passed.
- mypy 2.4.1 `packages=["core"]`, `strict_optional`, `check_untyped_defs`,
  `warn_unreachable` → 0 errors / 297 files; ruff clean.
- All merged PRs green on CI: test (3.11), test (3.14),
  website-devapp-and-sdks, wheel-and-sbom-verification, IaC validate.
- Known flake unchanged (pre-existing): `test_cli_swarm_offline_benchmark_json`.

## 6. Security assessment
See `07_SECURITY_FRAMEWORK.md`. In release scope:
- Authz/tenant isolation: owner-scoped conversation retrieval verified.
- Secrets: none committed; `.env` gitignored; `KEELWAY_POLICY_SIGNING_KEY`
  required for compose.
- `?token=` retained but access-log-safe (live-verified); header auth
  always accepted; rotation path documented. Post-beta: header-only.
- Sandbox: seatbelt ENFORCED, confinement verified (`keelway doctor` §10).
- Residuals: `Any`-widened wire boundaries; HAL-verifier coverage.
No known unresolved critical/high-severity findings in release scope.

## 7. Performance assessment
- dev-app bundle: 1.2 MB js (322 kB gzip) — code-split candidate P2.
- Ollama worst-case latency bounded: 30s request / 5s connect (was ~120s
  wedge); test suite wall-time for local-runtime paths dropped to <1s.
- No load/soak testing performed — single-operator local product; not
  a gate for beta scope.

## 8. Deployment status
- Vercel website (`kora-sable.vercel.app`): deployed continuously, green.
- Self-host compose: SMOKE-TESTED 2026-11-27 — image builds; `/health`
  `{"status":"ok","database_connected":true}`; `/app/` 200; container
  request logs token-free. Control-plane service requires
  `KEELWAY_POLICY_SIGNING_KEY` (platform service smoke ran without it).
- `keelway dev` cold-run: `doctor` HEALTHY 10/10; launch URL+token path
  documented in `09_DEPLOYMENT_RUNBOOK`.
- Helm/k8s/terraform: manifests exist, `Validate IaC` CI green, not
  E2E-deployed — flagged limitation, not beta-blocking.

## 9. Rollback instructions
See `09_DEPLOYMENT_RUNBOOK.md`. Summary: snapshot `KEELWAY_DB_PATH`
SQLite + `.keelway/` before upgrade; rollback = prior wheel reinstall /
`git checkout <prev-tag> && docker compose up --build` / Vercel instant
rollback. Conversations table is additive — no forward-migration needed.

## 10. Go / no-go recommendation
**GO — conditional.** All P0 items resolved or honestly documented;
release gates green; deploy smoke verified; limitations ship-honest.
P1 sweep complete: one real fix (P1-1), four verified-honest surfaces.
Conditions for the release owner:
- Beta onboarding must use the `09` runbook path (not helm/k8s — unverified).
- Communicate the single-operator model — this is not multi-tenant SaaS.
Final approval rests with the release owner per `10_BETA_RELEASE_CHECKLIST`.
