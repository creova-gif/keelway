# Keelway Unified Platform — Phase 3 Implementation Plan (`KEEL-CLUSTER-008` + `KEEL-SDK-009`)

> **For agentic workers:** REQUIRED SUB-SKILL: Use `dispatching-parallel-agents` across the 4 file-isolated workstreams below, followed by unified OpenAPI 3.1 + `product-facts.json` + `ACTIVE_TASKS.md` + `./scripts/verify_engineering_gates.sh` integration, commit, push, and live Vercel production verification.

**Goal:** Complete the remaining backlog pillars of Keelway (`KEEL-CLUSTER-008` Multi-Node GPU Cluster Scheduler, PostgreSQL Row-Locked Governance Adapter & Model Lifecycle Registry; `KEEL-SDK-009` Official Zero-Dependency Go Client SDK `keelway-go`; Marketplace Commercial Settlement Ledger; and Unified Dev App Cluster Operations + Customer-Clean Website Sync).

**Strict Constraints:**
- Every newly created or modified `.py` (new/platform/cluster), `.ts`, `.tsx`, and `.go` file must remain strictly `<750` lines (target `<550` lines).
- Zero external runtime dependencies in `@keelway/sdk` (`sdk/typescript`) and zero external module dependencies in `keelway-go` (`sdk/go/go.mod`).
- Customer-facing website files (`website/src/**`, `website/public/**`) MUST NOT contain any private/internal repo slugs (`creova-gif`, `creovas-projects`, `kora.git`), internal ticket IDs (`KEEL-*`), internal harness names (`Antigravity`, `gstack`), or internal script names (`verify_engineering_gates.sh`).

---

## Workstream 3A — `KEEL-CLUSTER-008`: Multi-Node GPU Cluster Scheduler, PostgreSQL Governance Adapter & Model Lifecycle
- **Files:** `core/cluster/{__init__,scheduler,postgres_adapter,lifecycle}.py`, `core/api/cluster_routes.py`, `core/main.py`, `tests/test_cluster_and_postgres_governance.py`
- **Deliverables:**
  1. `ClusterScheduler`: GPU worker registration (`vllm`, `ray_serve`, `ollama_metal`), VRAM + tensor-parallel placement, regional residency fail-closed filtering (`us`, `eu`, `africa`, `airgap_local`, `global`), queue depth scoring, and node `drain` / `restore`.
  2. `PostgresGovernanceAdapter`: Canonical PostgreSQL DDL (`keelway_tenant_budgets`, `keelway_audit_chain`), parameterized `SELECT ... FOR UPDATE` row-locked SQL builders, DB-API 2.0 injection support, and deterministic local transactional SQLite parity execution for atomic USD spend reservations and Genesis-anchored SHA-256 chain verification.
  3. `ModelLifecycleRegistry`: Canary weight management (`0`–`100%`), benchmark-gated `canary -> stable` promotion, and automatic canary rollback.
  4. FastAPI `/v1/cluster/*` router mounted in `core/main.py` + comprehensive pytest suite.

## Workstream 3B — `KEEL-SDK-009`: Official Zero-Dependency Go Client SDK (`sdk/go`)
- **Files:** `sdk/go/{go.mod,errors.go,client.go,platform.go,client_test.go,README.md}`
- **Deliverables:**
  1. Pure standard-library Go package (`module github.com/keelway/keelway-go`) with typed HTTP error hierarchy (`AuthenticationError`, `BudgetExceededError`, `AirGapEgressError`, `NotFoundError`, `PolicyViolationError` with `Findings`, `RateLimitError`, `UpstreamProviderError`).
  2. `Responses.Create`, chunk-boundary-safe SSE `Responses.Stream`, `Routing.Explain`, `Platform.*` (Overview, Agents, Teams, Issues, Marketplace List/Scan/Publish/Install, Blueprint Compile, Enterprise Policy & Compliance), and `Cluster.*` (ListNodes, Schedule, ListLifecycle).
  3. Full `go test ./... -v -race` suite via `net/http/httptest`.

## Workstream 3C — Marketplace Settlement Ledger, Python/TS SDK Cluster Parity & CLI `keelway cluster`
- **Files:** `core/platform/settlement.py`, `core/platform/{persistence,__init__}.py`, `core/api/platform_routes.py`, `core/sdk/{cluster_client,client,__init__,platform_client}.py`, `sdk/typescript/src/{cluster,client,index,platform,platform-types}.ts` + `dist/*` + `test/sdk.test.mjs`, `core/cli_tui.py`, `cli.py`, `tests/test_cli_init_and_banner.py`, `tests/test_marketplace_settlement_and_cluster_sdk.py`
- **Deliverables:**
  1. `MarketplaceSettlementLedger` persisted in `SQLitePlatformStore` (`PRAGMA journal_mode=WAL`) computing cent-accurate `85/15`, `80/20`, and `100/0` splits with SHA-256 receipt digests (`POST /v1/platform/marketplace/purchase`, `GET /v1/platform/marketplace/settlements`).
  2. `client.cluster` + Marketplace settlement methods in both `core.sdk` (Python sync + async) and `@keelway/sdk` (TypeScript, compiled cleanly to `dist/`).
  3. `keelway cluster` (`nodes`, `schedule`, `lifecycle`) CLI subcommands in `core/cli_tui.py` & `cli.py`.

## Workstream 3D — Dev App Cluster Operations UI & Customer-Clean Website Sync
- **Files:** `dev-app/src/components/platform/AutomationAndOpsViews.tsx`, `dev-app/src/lib/platformApi.ts`, `dev-app/src/__tests__/unified-10view-platform.test.tsx`, `core/dev_app_dist/*`, `website/src/components/docs/DocsHub.tsx`, `website/src/components/home/QuickstartTerminal.tsx`
- **Deliverables:**
  1. Live Multi-Node GPU Cluster & Model Canary Rollout panel + Creator Settlement Summary inside Dev App's **Operations View**, hydrated from `/v1/cluster/nodes` & `/v1/platform/marketplace/settlements` with offline fallback, `0` `axe-core` violations, and fresh Vite build in `core/dev_app_dist/`.
  2. Go SDK (`keelway-go`) snippet tab in `QuickstartTerminal.tsx` and updated `"AVAILABLE TODAY"` capabilities in `DocsHub.tsx` with zero internal/private token leakage.
