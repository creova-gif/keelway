# Keelway Unified AI-Native Agent Local Platform Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and ship the Keelway Unified AI-Native Agent Local Platform across the FastAPI core backend (`/v1/platform/*`), Claude-Code-style `keelway` CLI TUI, Unified 10-View Sovereign Dev App (`/app`), and Next.js 15 website (`/playground`, `/governance` labs, 5-stream `/pricing`, and prefix `⌘K`).

**Architecture:** Shared-infrastructure-first design (`core/platform/`) providing 5-stream subscription/BYOM/quota governance, a security-validated Marketplace & Extension SDK, 12 lifecycle specialized agents + multi-agent teams, and a unified project/PRD/issue/workflow hub consumed by the CLI, the 10-View React Dev App (`dev-app/` -> `core/dev_app_dist/`), and interactive website showcases (`website/`). Four non-overlapping workstreams execute in parallel followed by unified integration gates.

**Tech Stack:** Python 3.11+ / FastAPI / SQLite & durable JSON state / Pytest; React 19 / TypeScript / Vite / Radix UI / Vitest + `axe-core`; Next.js 15 App Router / Tailwind CSS / Vercel Flags SDK.

**Spec:** `docs/superpowers/specs/2026-11-14-unified-agent-platform-design.md`

## Global Constraints

- Always execute commands from `/Users/justinmafie/Documents/antigravity/mysterious-brahmagupta/keelway` and preserve Git `user.email = creativeinnovationspace@gmail.com`.
- Consumer `ChatGPT` or `Claude` web subscriptions must NEVER be assumed to grant third-party API access; `BYOM` requires authorized API credentials or officially supported integrations, with explicit disclosure in API, CLI, Dev App, and `/pricing`.
- Pre-publication security validation (`MarketplaceSecurityScanner`) must reject prompt injection, dangerous shell/eval execution, hardcoded secrets, and unscoped wildcard permissions before any Marketplace package is published.
- Every `.ts`, `.tsx`, and newly created `.py` file must remain strictly `<750` lines; zero external font/CSS CDNs (`fonts.googleapis.com`, `fonts.gstatic.com`, `cdn.tailwindcss.com`, `cdnjs.cloudflare.com`) anywhere in `dev-app/` or `website/`.
- All 46 existing `dev-app` Vitest + `axe-core` tests and all existing CLI/website/core pytest suites must continue to pass without regression.

## Review Focus

- Consumer web session tokens (`sk-ant-sid01-...`, `chatgpt-plus-session-...`, `claude-pro-cookie=...`) submitted to BYOM validation must fail closed with `CREDENTIAL_TYPE_UNSUPPORTED_CONSUMER_SUBSCRIPTION` and an actionable explanation, never silently accepted as API keys.
- Marketplace packages containing obfuscated case-insensitive prompt-injection directives (`Ignore Previous Instructions`, `BYPASS P-10`) or `subprocess.Popen(..., shell=True)` hooks must be blocked from publication with HTTP 422 / `passed=False`.
- Community-tier users exceeding `daily_open_weight_tokens` or `rpm_limit` must receive a deterministic `QUOTA_EXCEEDED` decision with upgrade/local-hardware guidance rather than an unhandled 500 error.
- Switching across any of the 10 Unified Workspace views (`Agents`, `IDE`, `Project Manager`, `Product`, `Automation`, `Marketplace`, `Security`, `Documentation`, `Operations`, `No-Code Builder`) or toggling `Builder` <-> `Non-Coder` mode in `dev-app` must preserve active project context, composer drafts, issues/PRDs created via No-Code Builder, and pending `P-10` approvals, while keeping existing `Tasks`/`Files`/`Record`/`Settings` rail landmarks 100% intact.
- Calling `get_banner(plain=True, use_color=False)` or setting `NO_COLOR=1` in `cli.py` must emit zero ANSI escape sequences (`\033[`) while still preserving `"_  ______ _____ _ __"`, `"Sovereign Local-First AI Developer Platform"`, `"Sorvex Labs"`, and `"https://keelway.dev"`.

---

### Task 1 (Workstream A): Core Platform Engine — Subscriptions/BYOM, Marketplace Security Validator, Unified Workspace Hub & `/v1/platform/*` API

**Files:**
- Create: `core/platform/__init__.py`
- Create: `core/platform/subscription.py`
- Create: `core/platform/marketplace.py`
- Create: `core/platform/workspace_hub.py`
- Create: `core/api/platform_routes.py`
- Modify: `core/main.py`
- Test: `tests/test_unified_platform.py`

**Interfaces:**
- Consumes: `core.billing.entitlements.LicenseTier`, `core.security.redact.redact_text`, `core.security.auth.require_role` / FastAPI router conventions in `core/api/governance_routes.py`.
- Produces:
  - `SubscriptionPolicyEngine`: `list_tiers()`, `check_quota(org_id, tier, tokens_requested, current_rpm)`, `validate_byom_credential(provider, credential_kind, api_key_preview, model_id, commercial_use)`, `calculate_marketplace_split(publisher_tier, gross_usd)`.
  - `MarketplaceRegistry` & `MarketplaceSecurityScanner`: `scan_package(payload) -> SecurityValidationReport`, `list_packages(kind=None, query=None)`, `publish_package(payload)`, `install_package(package_id, workspace_id, config=None)`.
  - `UnifiedWorkspaceHub` & `ExtensionRegistry`: 12 specialized lifecycle agents (`LIFECYCLE_AGENTS`), multi-agent teams (`MULTI_AGENT_TEAMS`), 9-stage cross-agent SDLC (`SDLC_WORKFLOW_STAGES`), PM issues/sprints, Product PRDs, Automation workflows, `compile_nocode_blueprint(idea, workspace_id, target_stack)`, `register_extension(spec)`.
  - FastAPI `router` mounted at `/v1/platform` in `core/main.py`.

- [ ] **Step 1: Write failing comprehensive tests in `tests/test_unified_platform.py`**
  Cover: (a) 5 monetization streams + Community token/RPM quota enforcement; (b) BYOM rejection of consumer ChatGPT/Claude web subscriptions (`consumer_subscription` / session cookie prefixes) vs acceptance of authorized API keys + model license commercial-use check; (c) Marketplace revenue-share split (`85/15` verified third-party) and `MarketplaceSecurityScanner` blocking prompt-injection, `shell=True`/`eval(`, wildcard `/` write scopes, and leaked `sk-` secrets while passing valid packages; (d) 12 lifecycle agents + multi-agent team dispatch with P-10 approval gates on sensitive actions; (e) Extension SDK registration without core mutation; (f) `compile_nocode_blueprint()` generating linked Project + PRD + Sprint Issues + Automation DAG + Agent Team; (g) FastAPI `TestClient` checks across `/v1/platform/overview`, `/v1/platform/subscriptions/*`, `/v1/platform/marketplace/*`, `/v1/platform/nocode/blueprint`, and `/v1/platform/extensions`.
- [ ] **Step 2: Run pytest to confirm initial failure**
  Run: `pytest tests/test_unified_platform.py -v`
  Expected: FAIL (`ModuleNotFoundError: No module named 'core.platform'`).
- [ ] **Step 3: Implement `core/platform/{__init__,subscription,marketplace,workspace_hub}.py`, `core/api/platform_routes.py`, and mount router in `core/main.py`**
  Keep every file `<550` lines with strict type annotations and deterministic defaults.
- [ ] **Step 4: Run `pytest tests/test_unified_platform.py -v` and adjacent API export/governance tests**
  Run: `pytest tests/test_unified_platform.py tests/test_tenant_governance.py -v`
  Expected: PASS (`0` failures).

---

### Task 2 (Workstream B): Claude-Code-Style `keelway` CLI TUI Launch Card, Slash Strip & `marketplace` / `blueprint` Commands

**Files:**
- Create: `core/cli_tui.py`
- Modify: `cli.py`
- Test: `tests/test_cli_init_and_banner.py`

**Interfaces:**
- Consumes: `core.config.settings` (and optional lazy import of `core.platform` when `marketplace` or `blueprint` subcommands run).
- Produces:
  - `core/cli_tui.py`: `render_sovereign_tui_banner(plain: bool = False, use_color: Optional[bool] = None, workspace: Optional[Path] = None) -> str`, `render_slash_command_strip(plain: bool = False, use_color: Optional[bool] = None) -> str`, `register_platform_cli_subparsers(subparsers)`, `dispatch_platform_cli(args) -> Optional[int]`.
  - `cli.py`: `get_banner()` delegates to `render_sovereign_tui_banner()`, `main([])` displays the framed TUI launch card + slash command strip + `Essential Commands:`, and `build_parser()` / `main()` wire `keelway marketplace <list|scan>` and `keelway blueprint "<idea>"`.

- [ ] **Step 1: Extend `tests/test_cli_init_and_banner.py` with failing TUI card, slash-strip, `NO_COLOR`/`plain=True`, and `marketplace`/`blueprint` CLI tests**
  Keep all existing tests untouched and add assertions for framed Unicode box (`╭───` / `╰───` when Unicode enabled), `+---` ASCII frame when `plain=True`, live telemetry labels (`Workspace`, `Runtime`, `Sandbox`, `Posture`), slash strip (`/agents`, `/marketplace`, `/nocode`, `/airgap`, `/audit`), and `main(["marketplace", "list"])` / `main(["blueprint", "Build an invoice approval portal"])`.
- [ ] **Step 2: Run pytest to verify new CLI tests fail**
  Run: `pytest tests/test_cli_init_and_banner.py -v`
  Expected: FAIL on new TUI frame / subcommand assertions.
- [ ] **Step 3: Implement `core/cli_tui.py` (<350 lines) and wire minimal hooks in `cli.py`**
  Preserve `"_  ______ _____ _ __"`, `"Sovereign Local-First AI Developer Platform"`, `"Sorvex Labs"`, `"https://keelway.dev"`, and `"Essential Commands:"` verbatim.
- [ ] **Step 4: Verify CLI test suite passes**
  Run: `pytest tests/test_cli_init_and_banner.py tests/test_cli_ai.py -v`
  Expected: PASS.

---

### Task 3 (Workstream C): Unified 10-View Keelway Dev App & Dual Builder / Non-Coder Experience (`dev-app/`)

**Files:**
- Create: `dev-app/src/lib/platformData.ts`
- Create: `dev-app/src/components/platform/PlatformWorkspaceBar.tsx`
- Create: `dev-app/src/components/platform/AgentsWorkspaceView.tsx`
- Create: `dev-app/src/components/platform/PmAndProductViews.tsx`
- Create: `dev-app/src/components/platform/AutomationAndOpsViews.tsx`
- Create: `dev-app/src/components/platform/MarketplaceAndDocsViews.tsx`
- Create: `dev-app/src/components/platform/NoCodeBuilderView.tsx`
- Modify: `dev-app/src/lib/types.ts`
- Modify: `dev-app/src/lib/api.ts`
- Modify: `dev-app/src/App.tsx`
- Test: `dev-app/src/__tests__/unified-10view-platform.test.tsx`
- Build Output: `core/dev_app_dist/*`

**Interfaces:**
- Consumes: `/v1/platform/*` endpoints (with deterministic offline local-first state in `platformData.ts` so `/app` works 100% air-gapped), plus existing `TasksWorkspace`, `FilesWorkspace`, `RecordAuditLedger`, `SettingsWorkspace`, `DevAppShell`, and `P10ApprovalCard`.
- Produces:
  - `PlatformViewId`: `"agents" | "ide" | "pm" | "product" | "automation" | "marketplace" | "security" | "docs" | "operations" | "nocode"`.
  - `ExperienceMode`: `"builder" | "non_coder"`.
  - Full 10-View Unified Workspace mounted inside `App.tsx` while keeping the 4 primary rail landmarks (`Tasks`, `Files`, `Record`, `Settings`), all keyboard shortcuts (`F6`, `⌘K`, `⌘J`, `Alt+A`), and all 46 existing tests 100% passing!

- [ ] **Step 1: Write failing Vitest + `axe-core` suite in `dev-app/src/__tests__/unified-10view-platform.test.tsx`**
  Test: (a) switching across all 10 Unified Workspace views (`Agents`, `IDE`, `Project Manager`, `Product`, `Automation`, `Marketplace`, `Security`, `Documentation`, `Operations`, `No-Code Builder`) preserves shared project context, branch, active model, and pending `P-10` count; (b) toggling `Builder` <-> `Guided Non-Coder` adapts the workspace and opens/drives `No-Code Builder`, where submitting a natural-language idea generates a PRD (visible in `Product`), Linear-style sprint issues (visible in `Project Manager`), and an automation workflow (visible in `Automation`); (c) `Marketplace` filters packages, displays `Pre-Publish Security Verified` badges, installs a skill/agent, and rejects prompt-injection payloads in the live Pre-Publish Validator; (d) `axe-core` reports `0` violations across new views.
- [ ] **Step 2: Run Vitest to confirm failure**
  Run: `cd dev-app && npm test -- src/__tests__/unified-10view-platform.test.tsx`
  Expected: FAIL.
- [ ] **Step 3: Implement modular `<450`-line platform components and wire into `App.tsx` (<740 lines)**
  Ensure every `.ts`/`.tsx` file in `dev-app/src/` stays strictly `<750` lines.
- [ ] **Step 4: Typecheck, run full Vitest + `axe-core` suite, and build `core/dev_app_dist/`**
  Run: `cd dev-app && npm run typecheck && npm test && npm run build`
  Expected: PASS (`0` TS errors, all 7 test files green, compiled bundle written to `core/dev_app_dist/`).

---

### Task 4 (Workstream D): Website Creative Labs (`/governance`, `/playground`, 5-Stream `/pricing`, Prefix `⌘K`)

**Files:**
- Create: `website/src/components/governance/RecordTamperLab.tsx`
- Create: `website/src/components/governance/ManifestDriftSimulator.tsx`
- Create: `website/src/components/playground/UnifiedPlatformPlayground.tsx`
- Create: `website/src/app/playground/page.tsx`
- Modify: `website/src/app/governance/page.tsx`
- Modify: `website/src/data/pricing.ts`
- Modify: `website/src/components/pricing/PricingTiers.tsx`
- Modify: `website/src/app/pricing/page.tsx`
- Modify: `website/src/components/layout/CommandPalette.tsx`
- Modify: `website/src/components/layout/Header.tsx`
- Modify: `website/src/app/sitemap.ts`
- Modify: `website/src/app/api/search-index/route.ts`
- Test: `tests/test_website_facts.py`

**Interfaces:**
- Consumes: `website/src/lib/analytics.ts` (`trackEvent`), existing design tokens in `globals.css`.
- Produces:
  - `/governance` interactive `RecordTamperLab` + `ManifestDriftSimulator` (prompt drift + Marketplace package security scanner).
  - `/playground` interactive 10-View Unified Platform & Dual `Builder` / `Non-Coder` browser workbench.
  - `/pricing` 5-Stream Subscription & Monetization layout (`Free / Community`, `Keelway Pro`, `Bring Your Own Model (BYOM)` with explicit consumer ChatGPT/Claude subscription non-assumption banner, `Keelway Enterprise`, `Marketplace Revenue Share`).
  - Prefix-aware Global `⌘K` (`>`, `@`, `/`, `#`).

- [ ] **Step 1: Add failing assertions in `tests/test_website_facts.py`**
  Assert existence and contract wiring of `/playground`, `RecordTamperLab`, `ManifestDriftSimulator`, 5-stream pricing + BYOM consumer-subscription compliance disclaimer, and `CommandPalette` prefix modes (`>`, `@`, `/`, `#`), alongside zero third-party CDNs.
- [ ] **Step 2: Run `pytest tests/test_website_facts.py -v` to confirm failure**
  Expected: FAIL on new showcase/pricing/playground assertions.
- [ ] **Step 3: Implement `/governance` labs, `/playground` route & workbench, 5-stream `/pricing`, and prefix `⌘K`**
  Keep every `.ts`/`.tsx` file strictly `<750` lines and WCAG AA compliant.
- [ ] **Step 4: Run `npm run typecheck`, `npm run build` in `website/`, and `pytest tests/test_website_facts.py -v`**
  Expected: PASS (`0` TS errors, clean static/SSR Next.js 15 build including `/playground`, all website drift tests green).

---

### Task 5 (Integration): Synchronize `product-facts.json`, Cross-Agent Registry, Universal Engineering Gates & Git Push

**Files:**
- Modify: `website/product-facts.json`
- Modify: `website/public/product-facts.json`
- Modify: `docs/agent-operations/ACTIVE_TASKS.md`
- Modify: `scripts/verify_engineering_gates.sh`

- [ ] **Step 1: Register verified `"AVAILABLE"` platform capabilities in `website/product-facts.json` and mirror identically to `website/public/product-facts.json`**
- [ ] **Step 2: Add `tests/test_unified_platform.py` and `tests/test_cli_init_and_banner.py` to `scripts/verify_engineering_gates.sh` and update `docs/agent-operations/ACTIVE_TASKS.md` (`KEEL-PLATFORM-010`)**
- [ ] **Step 3: Execute full verification across all layers**
  Run: `(cd dev-app && npm run typecheck && npm test && npm run build) && (cd website && npm run typecheck && npm run build) && ./scripts/verify_engineering_gates.sh`
  Expected: `ALL KEELWAY ENGINEERING GATES PASSED [100% VERIFIED]`.
- [ ] **Step 4: Verify `<750`-line file cap on all new/modified files, verify `website/.env.local` is untracked, commit with `creativeinnovationspace@gmail.com`, and push `main` to `origin/main`**
