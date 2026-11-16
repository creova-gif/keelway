# Keelway Dev Tool 10-View Workspace & Website Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver full, deep interactive capabilities across all 10 workspace views inside the local Keelway Dev Tool (`dev-app` at `:7420/app`) backed by SQLite WAL `/v1/platform/*` & `/v1/cluster/*` APIs, and remove the misplaced `/playground` workspace widget from the public marketing website (`website/`).

**Architecture:** Four file-disjoint parallel workstreams (`4A` Python Workspace Hub & FastAPI routes; `4B` Documentation, Security, Marketplace, PM, Product, Agents & No-Code views in `dev-app`; `4C` Automation, Operations, Platform API/Data contracts, Workspace Bar & `⌘K` Command Palette in `dev-app`; `4D` Website `/playground` removal, `308` redirect & single-row Header cleanup), followed by unified `useUnifiedPlatformState.tsx` + `App.tsx` wiring, Vite bundle export to `core/dev_app_dist`, 8-gate CI verification, and Vercel production deployment.

**Tech Stack:** Python 3.14, FastAPI, SQLite WAL, React 19, TypeScript 5, Vite, Vitest + `axe-core`, Next.js 15 App Router.

---

### Task 1 (Workstream 4A): Backend Workspace Hub CRUD & Security Scan Routes

**Files:**
- Modify: `core/platform/persistence.py`
- Modify: `core/platform/workspace_hub.py`
- Modify: `core/api/platform_routes.py`
- Modify: `tests/test_unified_platform.py`

- [ ] **Step 1:** Add `"docs"` and `"feedback"` to `VALID_WORKSPACE_COLLECTIONS` in `core/platform/persistence.py` (keep `<465` lines).
- [ ] **Step 2:** Extend `UnifiedWorkspaceHub` in `core/platform/workspace_hub.py` (keep `<720` lines) with rich Markdown `body` on seeded `docs`, `upsert_doc`, `update_issue`, `list_feedback`, `create_feedback`, and `scan_workspace_security` persisted to SQLite WAL.
- [ ] **Step 3:** Expose `GET/POST /v1/platform/docs`, `PUT /v1/platform/docs/{doc_id}`, `PATCH /v1/platform/pm/issues/{issue_id}`, `GET/POST /v1/platform/product/feedback`, and `POST /v1/platform/security/scan` in `core/api/platform_routes.py` (keep `<690` lines).
- [ ] **Step 4:** Add unit + ASGI integration tests in `tests/test_unified_platform.py` and verify `../kora-ai.nosync/.venv/bin/pytest tests/test_unified_platform.py tests/test_platform_persistence_and_enterprise.py -v`.

---

### Task 2 (Workstream 4B): Full-Depth Documentation, Security, Marketplace, PM, Product, Agents & No-Code Views

**Files:**
- Create: `dev-app/src/components/platform/DocumentationWorkspaceView.tsx` (`<420` lines)
- Create: `dev-app/src/components/platform/SecurityWorkspaceView.tsx` (`<420` lines)
- Modify: `dev-app/src/components/platform/MarketplaceAndDocsViews.tsx` (`<460` lines)
- Modify: `dev-app/src/components/platform/PmAndProductViews.tsx` (`<640` lines)
- Modify: `dev-app/src/components/platform/AgentsWorkspaceView.tsx` (`<460` lines)
- Modify: `dev-app/src/components/platform/NoCodeBuilderView.tsx` (`<390` lines)

- [ ] **Step 1:** Build split-pane `DocumentationWorkspaceView.tsx` with Diataxis tree, search, `Reader` / `Split Editor` / `Markdown` modes, `+ New Document`, `Save Document`, `Sync Doc from Active PRD`, and 9-Stage SDLC reference.
- [ ] **Step 2:** Build `SecurityWorkspaceView.tsx` combining `SecurityPostureBanner`, interactive `SOC2` / `HIPAA` / `ISO27001` / `GDPR` compliance evaluator, live workspace secret/prompt-injection/AST scanner, and `RecordAuditLedger`.
- [ ] **Step 3:** Upgrade `MarketplaceWorkspaceView` in `MarketplaceAndDocsViews.tsx` with search, publisher-tier filter, SHA-256 + SPDX purchase/install receipt banner, and installed-extension config drawer; re-export `DocumentationWorkspaceView` and `SecurityPostureBanner`.
- [ ] **Step 4:** Upgrade `ProjectManagerView` (`List View` + 5-column `Kanban Board` + Issue Inspector) and `ProductWorkspaceView` (`+ Author New PRD`, interactive RICE calculator, `+ Log Feedback`, `Generate Sprint Issues in PM`) in `PmAndProductViews.tsx`.
- [ ] **Step 5:** Add Agent Session Supervisor & `keelway.agent/v1` Manifest Inspector in `AgentsWorkspaceView.tsx` and Interactive Live App Preview in `NoCodeBuilderView.tsx`. All new callback props MUST be optional with local-state fallbacks so existing callers and tests stay 100% green.

---

### Task 3 (Workstream 4C): Automation DAG Builder, Cluster Scheduler Ops, Platform API Contracts & `⌘K` View Switching

**Files:**
- Modify: `dev-app/src/lib/platformData.ts` (`<460` lines)
- Modify: `dev-app/src/lib/platformApi.ts` (`<470` lines)
- Modify: `dev-app/src/components/platform/AutomationAndOpsViews.tsx` (`<690` lines)
- Modify: `dev-app/src/components/platform/PlatformWorkspaceBar.tsx` (`<190` lines)
- Modify: `dev-app/src/components/shell/CommandPalette.tsx` (`<360` lines)

- [ ] **Step 1:** Extend `DocGuideItem` (`body?: string; updatedAt?: string; linkedPrdId?: string`) and `PmIssueItem` (`description?: string`) in `dev-app/src/lib/platformData.ts` with rich Markdown guide bodies, and add REST helpers (`postPlatformDoc`, `putPlatformDoc`, `postPlatformPrd`, `postPlatformWorkflow`, `patchPlatformIssue`, `postProductFeedback`, `postMarketplacePurchase`, `postSecurityScan`, `postEnterpriseComplianceCheck`, `postClusterSchedule`, `postModelLifecycleAction`) in `dev-app/src/lib/platformApi.ts`.
- [ ] **Step 2:** Upgrade `AutomationWorkspaceView` (custom multi-step DAG node builder + step run log viewer) and `OperationsWorkspaceView` (interactive GPU cluster workload scheduler + canary promote/rollback buttons) in `dev-app/src/components/platform/AutomationAndOpsViews.tsx`.
- [ ] **Step 3:** Add 10-View Workspace navigation items to `CommandPalette.tsx` (`onSelectPlatformView?: (view: PlatformViewId) => void`) and polish `PlatformWorkspaceBar.tsx`.

---

### Task 4 (Workstream 4D): Public Website `/playground` Removal & Single-Row Header Cleanup

**Files:**
- Delete: `website/src/app/playground/page.tsx`
- Delete: `website/src/components/playground/UnifiedPlatformPlayground.tsx`
- Modify: `website/next.config.ts`
- Modify: `website/src/components/layout/Header.tsx`
- Modify: `website/src/components/layout/Footer.tsx`
- Modify: `website/src/components/home/CustomerJourneyGrid.tsx`
- Modify: `website/src/components/layout/CommandPalette.tsx`
- Modify: `website/src/components/marketplace/MarketplaceCatalogExplorer.tsx`
- Modify: `website/src/app/sitemap.ts`
- Modify: `website/src/app/api/search-index/route.ts`
- Modify: `tests/test_website_facts.py`

- [ ] **Step 1:** Delete `/playground` route & component, add permanent redirect `/playground` → `/` in `website/next.config.ts`, and remove `Playground` from `Header.tsx` `PRIMARY_NAV` so the header stays clean on a single row.
- [ ] **Step 2:** Update `Footer.tsx`, `CustomerJourneyGrid.tsx`, `CommandPalette.tsx`, `MarketplaceCatalogExplorer.tsx`, `sitemap.ts`, and `search-index/route.ts` so zero `/playground` hrefs remain and Dev Tool journeys point cleanly to `/#quickstart` and `/docs`.
- [ ] **Step 3:** Update `tests/test_website_facts.py` to assert the `/playground` → `/` permanent redirect, zero stale `/playground` links across `website/src/`, and run `(cd website && npm run typecheck && npm run build)` + `pytest tests/test_website_facts.py -v`.

---

### Task 5 (Integration & Final Gate): Wire `useUnifiedPlatformState.tsx` + `App.tsx`, Expand Dev-App Tests, Build Bundle & Deploy

**Files:**
- Modify: `dev-app/src/components/platform/useUnifiedPlatformState.tsx`
- Modify: `dev-app/src/App.tsx`
- Modify: `dev-app/src/__tests__/unified-10view-platform.test.tsx`
- Rebuild: `core/dev_app_dist/*` & `website/openapi.json` / `website/public/openapi.json`

- [ ] **Step 1:** Wire all new callbacks (docs create/edit/sync, PRD create + issue generation, feedback create, issue patch, security scan/compliance, workflow custom nodes, marketplace purchase receipt, and `CommandPalette` `onSelectPlatformView`) in `useUnifiedPlatformState.tsx` and `App.tsx`.
- [ ] **Step 2:** Expand `dev-app/src/__tests__/unified-10view-platform.test.tsx` to verify every upgraded view capability + `0` `axe-core` violations, rebuild `dev-app` (`npm run build`), export OpenAPI 3.1, run `./scripts/verify_engineering_gates.sh`, commit, push `main`, and verify live on Vercel.
