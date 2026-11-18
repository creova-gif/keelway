# Phase 6 Calibrated Pricing, MiroFish Simulation, CLI Runtime & Operations Simulator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix and calibrate Keelway's 5-tier pricing models (`$0` Community, `$15/$19` BYOM at `0%` token markup, `$29/$35` Pro, `Custom` Enterprise, `85/15` Marketplace), empirically validate them against legacy pricing via a 5-persona MiroFish OASIS swarm & unit-economics harness, eliminate `STREAM 1..5` jargon and wrapping bugs on `/pricing`, ship `keelway vault|workspace|run|pricing-eval` CLI commands + tri-SDK `simulate_pricing` parity, and mount a live Quota & Pricing Simulator panel in the Dev Tool (`:7420/app`).

**Architecture:** Four parallel, zero-overlap workstreams (`6A` Backend + MiroFish, `6B` Website `/pricing` + Drift Gate, `6C` CLI Runtime + Python/TS/Go SDK parity, `6D` Dev App Operations Simulator), keeping every source and test file strictly `<750` lines, followed by Lead integration, OpenAPI 3.1 export, 8-gate verification, and production push to Vercel.

**Tech Stack:** Python 3.14 (`FastAPI`, `MiroFishSwarmHarness`, `LocalZepGraphStore`, `SpeculativeDecodingEngine`), Next.js 15 + React 19 (`website/`), React 19 + Vite + Vitest + `axe-core` (`dev-app/`), TypeScript (`@keelway/sdk`), Go 1.25 (`keelway-go`).

---

### Task 1 (Workstream 6A): Calibrated Subscription Engine, MiroFish 5-Persona Pricing Harness & FastAPI Route

**Exclusive Files:**
- Modify: `core/platform/subscription.py` (`<470` lines)
- Create: `core/eval/pricing_mirofish.py` (`<350` lines)
- Modify: `core/api/platform_runtime_routes.py` (`<560` lines)
- Modify: `tests/test_unified_platform.py`
- Create: `tests/test_pricing_mirofish.py` (`<380` lines)

- [ ] **Step 1:** Update `SUBSCRIPTION_TIERS` in `core/platform/subscription.py`:
  - `pro`: `monthly_price_usd = 35`, `annual_monthly_price_usd = 29`, `token_markup_pct = 0.0`, `badge_label = "MOST POPULAR · FULL STACK"`.
  - `byom`: `monthly_price_usd = 19`, `annual_monthly_price_usd = 15`, `token_markup_pct = 0.0`, `badge_label = "BYOM · 0% TOKEN MARKUP"`.
  - `community`: `badge_label = "OPEN-CORE · APACHE-2.0"`.
  - `enterprise`: `badge_label = "SOVEREIGN VPC & SLA"`, `pricing_label = "Dedicated VPC · Air-Gap · SLA"`.
  - `marketplace`: `badge_label = "CREATOR MARKETPLACE · 85/15"`.
- [ ] **Step 2:** Create `core/eval/pricing_mirofish.py` (`PricingMiroFishSimulator`):
  - Define `LEGACY_PRICING_SCHEDULE` (`pro=$39/$49`, `byom_display_price=None`, `has_stream_jargon=True`) and `CALIBRATED_PRICING_SCHEDULE` (`pro=$29/$35`, `byom=$15/$19`, `byom_display_price=15`, `token_markup_pct=0.0`, `has_stream_jargon=False`).
  - Compute deterministic unit economics (`hosted_open_weight_cost_per_1m_usd = 0.06`, P50 & P95 daily token utilization margins for `byom` and `pro`, anti-cannibalization spread `$29 - $15 = $14` covering 2.5M/day hosted pool, and monthly proxy-tax savings vs a 20%-markup gateway).
  - Run 5 OASIS buyer/creator personas (`Amara Diallo` Indie OSS Dev, `Marcus Vance` Heavy-BYOM Startup CTO, `Elena Rostova` Product/Ops Non-Coder Lead, `David Okafor` Enterprise CISO/FinOps, `Priya Nair` Marketplace Creator) both deterministically AND through `MiroFishSwarmHarness` (`extract_ontology` -> `build_seed_world_and_personas` -> `run_swarm_rounds` -> `synthesize_report_speculative` -> `verify_security_and_airgap_invariants` using an deterministic mock Gemini + OpenCore adapter when offline).
- [ ] **Step 3:** Add `POST /v1/platform/pricing/simulate` in `core/api/platform_runtime_routes.py` accepting `{ "schedule": "calibrated" | "legacy" | "compare", "seats": 8, "monthly_api_spend_usd": 1200, "run_swarm": true }`.
- [ ] **Step 4:** Update `tests/test_unified_platform.py` for calibrated prices (`29`/`35` Pro, `15`/`19` BYOM) and write `tests/test_pricing_mirofish.py` verifying legacy vs calibrated conversion lift, zero hidden-fee distrust, positive P50/P95 margins, full 5-stage `MiroFishSwarmHarness` execution, and FastAPI endpoint response.

---

### Task 2 (Workstream 6B): Website `/pricing` Overhaul & Customer-Clean Drift Gate

**Exclusive Files:**
- Modify: `website/src/components/pricing/PricingTiers.tsx` (`<560` lines)
- Modify: `website/src/data/pricing.ts` (`<180` lines)
- Modify: `website/src/app/pricing/page.tsx` (`<110` lines)
- Modify: `tests/test_website_facts.py` (`<600` lines)

- [ ] **Step 1:** Remove ALL `STREAM 1`–`STREAM 5` labels from `PricingTiers.tsx`; replace with `OPEN-CORE · APACHE-2.0`, `BYOM · 0% TOKEN MARKUP`, `MOST POPULAR · FULL STACK`, `SOVEREIGN VPC & SLA`, and `CREATOR MARKETPLACE · 85/15`.
- [ ] **Step 2:** Fix price typography and layout on all 4 cards (`Community $0 forever`, `BYOM $15` annual / `$19` monthly `/ seat / mo` + crisp `0% token markup · ${seats} seats = $${byomTeamMonthly}/mo` line, `Keelway Pro $29` annual / `$35` monthly `/ seat / mo` + `${seats} seats = $${proTeamMonthly}/mo` highlighted card, `Enterprise Custom` + non-wrapping `Dedicated VPC · Air-Gap · SLA`).
- [ ] **Step 3:** Upgrade the top interactive calculator bar with a `1–50` seat slider + monthly upstream API spend preset/readout showing **both** `BYOM ($15×N/mo)` and `Keelway Pro ($29×N/mo)` totals alongside estimated savings vs a 20% proxy token tax.
- [ ] **Step 4:** Sync `website/src/data/pricing.ts`, `website/src/app/pricing/page.tsx`, and `tests/test_website_facts.py` (asserting zero `STREAM 1..5` tokens, explicit `$15` & `$29` calibrated prices, and preserved ChatGPT/Claude consumer-subscription compliance text). Verify `(cd website && npm run typecheck && npm run build)` and `pytest tests/test_website_facts.py -v`.

---

### Task 3 (Workstream 6C): Sovereign CLI Phase 6 Runtime & MiroFish Eval + Tri-SDK Parity

**Exclusive Files:**
- Create: `core/cli_runtime.py` (`<320` lines)
- Modify: `core/cli_tui.py` (`<480` lines)
- Modify: `core/sdk/platform_runtime_client.py` (`<390` lines)
- Modify: `sdk/typescript/src/platform-runtime.ts`, `sdk/typescript/src/platform-types.ts`, `sdk/typescript/src/platform.ts`, `sdk/typescript/test/platform-runtime.test.mjs`
- Modify: `sdk/go/platform_runtime.go`, `sdk/go/platform_runtime_test.go`
- Create: `tests/test_cli_runtime_phase6.py` (`<300` lines)

- [ ] **Step 1:** Create `core/cli_runtime.py` implementing `keelway vault <list|put|rotate|delete>`, `keelway workspace <list|create|rbac-check>`, `keelway run --kind <agent|workflow> --target <ID> --objective <TEXT> [--no-p10] [--json]`, and `keelway pricing-eval [--compare-legacy] [--seats N] [--json]` (calling `PricingMiroFishSimulator` with clean standalone fallback). Wire into `core/cli_tui.py`.
- [ ] **Step 2:** Add `simulate_pricing` / `simulatePricing` / `SimulatePricing` (`POST /v1/platform/pricing/simulate`) across Python (`platform_runtime_client.py`), TypeScript (`@keelway/sdk`, rebuild `dist/`), and Go (`keelway-go`).
- [ ] **Step 3:** Verify `pytest tests/test_cli_runtime_phase6.py tests/test_cli_init_and_banner.py -v`, `(cd sdk/typescript && npm run build && npm test)`, and `(cd sdk/go && /usr/local/go/bin/go test -race ./...)`.

---

### Task 4 (Workstream 6D): Dev Tool (`:7420/app`) Operations Quota, Calibrated Pricing & MiroFish Simulator

**Exclusive Files:**
- Create: `dev-app/src/components/platform/QuotaAndPricingSimulatorPanel.tsx` (`<240` lines)
- Modify: `dev-app/src/lib/platformRuntimeApi.ts` (`<390` lines)
- Modify: `dev-app/src/components/platform/AutomationAndOpsViews.tsx` (`<640` lines)
- Create: `dev-app/src/__tests__/phase6-ops-pricing-simulator.test.tsx` (`<150` lines)

- [ ] **Step 1:** Add `postSimulatePricing` + typed response interfaces in `dev-app/src/lib/platformRuntimeApi.ts` (`POST /v1/platform/pricing/simulate` with deterministic 5-persona offline/Vitest fallback).
- [ ] **Step 2:** Build `QuotaAndPricingSimulatorPanel.tsx` showing calibrated tier cards (`Community $0`, `BYOM $15/mo · 0% Markup`, `Pro $29/mo · 2.5M tok/day`, `Enterprise Custom VPC`), interactive seat & monthly API spend controls, and a **"Run 5-Persona MiroFish Pricing Check"** action displaying persona stances (`Amara Diallo`, `Marcus Vance`, `Elena Rostova`, `David Okafor`, `Priya Nair`), conversion lift (`40% → 100%`), distrust score (`0.00`), and P50/P95 gross margins.
- [ ] **Step 3:** Mount `<QuotaAndPricingSimulatorPanel />` inside `OperationsWorkspaceView` in `AutomationAndOpsViews.tsx` and write `dev-app/src/__tests__/phase6-ops-pricing-simulator.test.tsx` verifying interactive simulation + `0` `axe-core` WCAG 2.2 AA violations.

---

### Task 5 (Lead Integration, OpenAPI Sync, 8-Gate Verification & Live Deployment)
- [ ] Audit `wc -l` across all created/modified files (`<750` lines strictly).
- [ ] Build `dev-app` (`core/dev_app_dist`), export OpenAPI 3.1 (`website/openapi.json` & `website/public/openapi.json`), update `website/product-facts.json` & `website/public/product-facts.json`, update `scripts/verify_engineering_gates.sh` & `ACTIVE_TASKS.md` (`KEEL-PRICING-013`).
- [ ] Run `(cd website && npm run typecheck && npm run build)` and `./scripts/verify_engineering_gates.sh` (`[1/8]`–`[8/8]` `100% VERIFIED`).
- [ ] Commit, `git push origin main`, and curl-verify `https://kora-sable.vercel.app/pricing` live!
