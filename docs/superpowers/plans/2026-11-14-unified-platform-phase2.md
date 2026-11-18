# Keelway Unified Platform Phase 2 — Durable Persistence, Ed25519 Signing, Enterprise Controls, SDK Parity & `/marketplace` Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete Phase 2 of the 10-Pillar Implementation Strategy by adding crash-safe SQLite WAL persistence, Ed25519 cryptographic manifest/package signing (`KEEL-MANIFEST-007`), Enterprise data-retention/branding/VPC governance, full Python + TypeScript (`@keelway/sdk`) platform client parity, live `/v1/platform/*` full-stack binding in `/app`, and a dedicated `/marketplace` route on the Next.js 15 website.

**Architecture:** Four conflict-free parallel workstreams extending `core/platform/` with `SQLitePlatformStore` (`PRAGMA journal_mode=WAL`), `Ed25519ManifestSigner`, and `EnterpriseGovernanceManager`, exposing typed `.platform` namespaces in both official SDKs (`core.sdk` & `@keelway/sdk`), wiring live same-origin API hydration/mutation in `dev-app/`, and launching `/marketplace` in `website/`.

**Tech Stack:** Python 3.11+ / FastAPI / SQLite3 WAL / `cryptography` Ed25519; TypeScript (`@keelway/sdk`, zero runtime deps); React 19 / Vite / Vitest + `axe-core`; Next.js 15 App Router.

**Spec:** `docs/superpowers/specs/2026-11-14-unified-agent-platform-design.md`

## Global Constraints

- Execute all commands inside `/Users/justinmafie/Documents/antigravity/mysterious-brahmagupta/keelway`; keep Git `user.email = creativeinnovationspace@gmail.com`.
- Every newly created `.py`, `.ts`, and `.tsx` file must stay strictly `<750` lines; `@keelway/sdk` (`sdk/typescript/package.json`) must retain **zero** runtime `dependencies`.
- Zero external font/CSS CDNs (`fonts.googleapis.com`, `fonts.gstatic.com`, `cdn.tailwindcss.com`, `cdnjs.cloudflare.com`).
- Preserve all P-10 human-only approval invariants, BYOM consumer-subscription non-assumption guards, and 100% of existing tests.

## Review Focus

- Tampering with any field of an Ed25519-signed `keelway.package/v1` or `keelway.agent/v1` manifest after signing must fail verification (`valid=False`, `reason="INVALID_ED25519_SIGNATURE"`), and unknown `key_id`s must fail closed (`UNKNOWN_PUBLISHER_KEY`).
- Restarting `MarketplaceRegistry` and `UnifiedWorkspaceHub` pointed at the same SQLite WAL database file must preserve published packages, workspace installs, created PM issues, PRDs, workflows, and registered SDK extensions without duplicating seed records.
- Enterprise data-retention enforcement must reject retention modes outside `{ephemeral_0d, standard_30d, regulated_365d, worm_7y}` and isolate tenant configurations by `tenant_id`.
- Both `core.sdk` and `@keelway/sdk` must map HTTP `422` Marketplace security rejections to `PolicyViolationError` with structured findings intact.
- When `/app` runs offline or `/v1/platform/*` returns non-2xx, `useUnifiedPlatformState` must keep optimistic local state working without uncaught promise rejections.

---

### Task 1 (Workstream A): SQLite WAL Platform Store, Ed25519 Package/Agent Signing (`KEEL-MANIFEST-007`) & Enterprise Governance

**Files:**
- Create: `core/platform/persistence.py`
- Create: `core/platform/signing.py`
- Create: `core/platform/enterprise.py`
- Modify: `core/platform/marketplace.py`
- Modify: `core/platform/workspace_hub.py`
- Modify: `core/platform/__init__.py`
- Modify: `core/api/platform_routes.py`
- Test: `tests/test_platform_persistence_and_enterprise.py`

- [ ] **Step 1:** Write failing tests in `tests/test_platform_persistence_and_enterprise.py` covering SQLite WAL restart durability, Ed25519 keygen/sign/verify + tamper detection, Enterprise retention/branding/VPC/compliance endpoints (`/v1/platform/enterprise/*`, `/v1/platform/marketplace/verify-signature`).
- [ ] **Step 2:** Implement `persistence.py`, `signing.py`, `enterprise.py`, and wire optional `store: Optional[SQLitePlatformStore]` into `MarketplaceRegistry` and `UnifiedWorkspaceHub` + routes in `platform_routes.py`.
- [ ] **Step 3:** Run `pytest tests/test_platform_persistence_and_enterprise.py tests/test_unified_platform.py -v` and confirm 100% pass.

---

### Task 2 (Workstream B): Official Python SDK (`core.sdk.platform`) & Zero-Dependency TypeScript SDK (`@keelway/sdk` `client.platform`)

**Files:**
- Create: `core/sdk/platform_client.py`
- Modify: `core/sdk/client.py`
- Modify: `core/sdk/__init__.py`
- Create: `sdk/typescript/src/platform-types.ts`
- Create: `sdk/typescript/src/platform.ts`
- Modify: `sdk/typescript/src/client.ts`
- Modify: `sdk/typescript/src/index.ts`
- Modify: `sdk/typescript/test/sdk.test.mjs`
- Test: `tests/test_sdk_platform.py`

- [ ] **Step 1:** Write failing Python tests (`tests/test_sdk_platform.py`) and Node test cases (`sdk/typescript/test/sdk.test.mjs`) exercising `client.platform.*` across overview, BYOM validation, quota checks, Marketplace list/scan/publish/install (including 422 -> `PolicyViolationError`), PM issues, PRDs, workflows, No-Code blueprint compilation, and Extension registration.
- [ ] **Step 2:** Implement `core/sdk/platform_client.py` (`AsyncPlatformClient` & `SyncPlatformClient`) and `sdk/typescript/src/platform.ts` (`PlatformNamespace`), compile `sdk/typescript/dist/` via `./website/node_modules/.bin/tsc -p sdk/typescript/tsconfig.json`.
- [ ] **Step 3:** Verify `pytest tests/test_sdk_v1.py tests/test_sdk_platform.py -v` and `(cd sdk/typescript && node --test test/sdk.test.mjs)`.

---

### Task 3 (Workstream C): Full-Stack `/v1/platform/*` Hydration & Mutation Sync in 10-View Dev App (`dev-app/`)

**Files:**
- Create: `dev-app/src/lib/platformApi.ts`
- Modify: `dev-app/src/components/platform/useUnifiedPlatformState.tsx`
- Modify: `dev-app/src/components/platform/MarketplaceAndDocsViews.tsx`
- Modify: `dev-app/src/__tests__/unified-10view-platform.test.tsx`
- Build Output: `core/dev_app_dist/*`

- [ ] **Step 1:** Add failing tests in `unified-10view-platform.test.tsx` verifying live `/v1/platform/*` hydration & POST sync (with mocked `fetch` + offline fallback) and live Marketplace package publishing into the workspace catalog once security scan passes.
- [ ] **Step 2:** Implement `platformApi.ts` (`<280` lines) and wire into `useUnifiedPlatformState.tsx` and `MarketplaceAndDocsViews.tsx`.
- [ ] **Step 3:** Run `cd dev-app && npm run typecheck && npm test && npm run build`.

---

### Task 4 (Workstream D): Dedicated Website `/marketplace` Catalog & Security Explorer (`website/`)

**Files:**
- Create: `website/src/components/marketplace/MarketplaceCatalogExplorer.tsx`
- Create: `website/src/app/marketplace/page.tsx`
- Modify: `website/src/components/layout/Header.tsx`
- Modify: `website/src/app/sitemap.ts`
- Modify: `website/src/app/api/search-index/route.ts`
- Modify: `tests/test_website_facts.py`

- [ ] **Step 1:** Add failing `/marketplace` route, category filter, Ed25519/SHA-256 badge, `85/15` split, and CLI/SDK install snippet checks in `tests/test_website_facts.py`.
- [ ] **Step 2:** Implement `MarketplaceCatalogExplorer.tsx` (`<500` lines) and `website/src/app/marketplace/page.tsx`, link in `Header.tsx`, `sitemap.ts`, and `search-index/route.ts`.
- [ ] **Step 3:** Run `(cd website && npm run typecheck && npm run build)` and `pytest tests/test_website_facts.py -v`.
