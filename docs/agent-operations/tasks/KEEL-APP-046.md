### TASK HANDOFF RECORD
- **TASK ID**: KEEL-APP-046
- **TASK TITLE**: KStack Program — Mission-Mapped Skill Contracts, Builtin Execution Handlers, `/v1/kstack/execute`, Lifecycle Agent Manifests
- **CURRENT STATUS**: READY_FOR_REVIEW
- **LAST AGENT**: Devin
- **DATE**: 2026-11-19
- **BRANCH**: `feature/keel-app-046-kstack-program`
- **HEAD COMMIT**: (pending)

#### OBJECTIVE & ACCEPTANCE CRITERIA
- [x] Marketplace-advertised agent skills have real KStack `SKILL.md` contracts (`kstack/wcag-aa`, `kstack/finops-forecast`); their seed `manifestSha256` now references the real contract digests.
- [x] Mission-mapped gap skills authored against real `/v1` service surfaces: `kbrain-fact`, `golden-eval`, `cost-ledger`, `mesh-verify`, `sbom-audit`, `schedule-ops` (catalog 14 → 22, manifest regenerated + digest-verified).
- [x] `core/kstack/handlers.py`: `BUILTIN_HANDLERS` map wiring 8 skills to real services (airgap auditor, merkle verify, cost ledger, kbrain store, p2p mesh, sbom generator, flow scheduler). Fail-closed input validation; mutating mesh actions rejected.
- [x] `POST /v1/kstack/execute` under `EXECUTE_AGENT`: 404 unknown, 403 revoked, 501 no-handler (never echo), sealed `SkillExecutionProof` returned (`to_dict` added to proof model).
- [x] 12 `keelway.agent/v1` lifecycle manifests authored in `core/agents/builtin/` (names mirror `LIFECYCLE_AGENTS`), all pass `am.validate`; B/C-tier agents get `confirm_all`, `network: none`, worktree sandbox.
- [x] Idempotent lifespan bootstrap registers builtin manifests into the SQLite registry at startup (owner `system`).
- [x] Tests: positive + negative paths for contracts, manifest validity/parity, registration, kill-switch, handler validation, sealed proofs, unknown/revoked/no-handler execution.

#### WORK COMPLETED & FILES MODIFIED
- `core/kstack/skills/{wcag-aa,finops-forecast,kbrain-fact,golden-eval,cost-ledger,mesh-verify,sbom-audit,schedule-ops}/SKILL.md`: new contracts.
- `core/kstack/manifest.json`: regenerated (22 skills).
- `core/kstack/handlers.py`: new builtin handler registry.
- `core/kstack/models.py`: `SkillExecutionProof.to_dict()`.
- `core/api/routes.py`: `KStackExecuteRequest` + `POST /v1/kstack/execute`.
- `core/agents/builtin/`: 12 `.agent.json` manifests + loader `__init__.py`.
- `core/main.py`: lifespan bootstrap registering builtin manifests.
- `dev-app/src/lib/platformData.ts`: marketplace skill entries reference real digests/contract names.
- `tests/test_kstack_execute.py`, `tests/test_lifecycle_agent_manifests.py`: new suites.
- `core/dev_app_dist/`: rebuilt bundle.

#### TESTS EXECUTED & EVIDENCE
- `pytest tests/test_kstack_execute.py`: `11 passed`
- `pytest tests/test_lifecycle_agent_manifests.py`: `5 passed`
- `pytest tests/test_kstack_kbrain_khub_kspaces_kflow.py`: `8 passed, 1 skipped` (pre-existing env skip — pytest-asyncio absent)
- `pytest tests/test_agent_manifest_api.py tests/test_agent_manifest_registry_and_cost.py`: `23 passed`
- `kstack_registry.verify_manifest()`: True, 22 skills
- `npx vitest run phase20-mcp-lockfile-and-bench.test.tsx`: `4 passed`; `npx tsc --noEmit`: clean; `npm run build`: clean

#### KNOWN RISKS & BLOCKERS
- `golden-eval` contract exists but has no handler — `DriftDetector.run_evaluation_and_create_receipt` is async; endpoint is handler-sync. Returns honest 501 until an async dispatch path is designed.
- Process-only skills (`plan`, `review`, `qa`, etc.) intentionally return 501 — they are contracts, not service calls.
- Frontend lifecycle-agent cards remain seed data; the rail/cards do not yet read `/v1/agents/registry` live (registry is now real, alignment is display-level next step).

#### NEXT RECOMMENDED ACTION
- Merge PR; then consider: async handler dispatch for `golden-eval`, live registry read in the Agents view, and a CLI `kstack execute` path.
