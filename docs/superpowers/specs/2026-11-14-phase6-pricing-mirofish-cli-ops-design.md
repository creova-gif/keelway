# Phase 6 Design Spec (`KEEL-PRICING-013`) — Calibrated Pricing Models, MiroFish 5-Persona Market & Margin Simulation, CLI Runtime Parity & Dev App Operations Simulator

- **Date**: `2026-11-14`
- **Status**: `DRAFT_FOR_REVIEW`
- **Scope**: Backend Subscription Engine + MiroFish Pricing Harness + Website `/pricing` Fix + Sovereign CLI Runtime Commands + Local Dev Tool (`:7420/app`) Quota/Pricing Inspector

---

## 1. Root-Cause Diagnosis of Existing Pricing Issues

Inspecting the live `/pricing` page and `core/platform/subscription.py` surfaced four concrete defects:
1. **Missing Dollar Price & Wrapping Layout Bug on BYOM Card (`PricingTiers.tsx`)**:
   - While `core/platform/subscription.py` modeled a dollar price for `byom`, `PricingTiers.tsx` rendered `"0%\nMarkup  + platform\nseat"` wrapped across two lines with **no dollar figure**, creating hidden-fee ambiguity (`"what does platform seat cost?"`).
2. **Uncalibrated Pro Anchor (`$49/mo`) & Single-Tier Seat Slider**:
   - `$49/seat/mo` (`$39` annual) priced individual developers and early teams well above category benchmarks (`$15–$29/seat/mo`), while the top seat slider (`"Keelway Pro / BYOM Seats: 8 seats ($392/mo)"`) multiplied only Pro's rate and ignored BYOM seats.
3. **Internal Monetization Jargon on Customer Cards (`STREAM 1`–`STREAM 5`)**:
   - Public badges displayed `"STREAM 1 · APACHE-2.0"`, `"STREAM 2 · MOST POPULAR"`, `"STREAM 3 · 0% MARKUP"`, `"STREAM 4 · SOVEREIGN VPC"`, and `"STREAM 5 · MARKETPLACE"`, exposing internal spec phrasing instead of customer-centric tier labels, and Card 4 wrapped `"Custom annual / usage\n/ VPC"` awkwardly across lines.
4. **No Empirical Market / Unit-Economics Gate**:
   - Pricing tiers were not stress-tested through `MiroFishSwarmHarness` (`core/eval/mirofish_swarm.py`) for multi-persona willingness-to-pay (WTP), hidden-fee distrust, BYOM-vs-Pro cannibalization, or hosted open-weight pool gross margins.

---

## 2. Calibrated 5-Tier Pricing Model (Single Source of Truth)

Synchronized identically across `core/platform/subscription.py`, `website/src/components/pricing/PricingTiers.tsx`, `website/src/data/pricing.ts`, `website/src/app/pricing/page.tsx`, SDKs, and Dev App:

| Plan (`id`) | Customer Badge | Annual Billing (`/seat/mo`) | Monthly Billing (`/seat/mo`) | Core Value & Quotas |
|---|---|---|---|---|
| **Free / Community** (`community`) | `OPEN-CORE · APACHE-2.0` | **\$0** forever | **\$0** forever | Unlimited local OpenCore weights (\$0.00/tok), 150K/day hosted community pool (20 RPM), 2 concurrent agents, IDE & basic DAGs, P-10 gate & local SQLite WAL ledger |
| **Bring Your Own Model** (`byom`) | `BYOM · 0% TOKEN MARKUP` | **\$15** / seat / mo | **\$19** / seat / mo | **0% token proxy markup** on authorized OpenAI, Anthropic, Gemini & vLLM API keys; pays strictly for 10-View Workspace, 12 lifecycle agents, KFlow orchestration, P-10 governance + 500K/day hosted open-weight fallback |
| **Keelway Pro** (`pro`) | `MOST POPULAR · FULL STACK` | **\$29** / seat / mo | **\$35** / seat / mo | Includes **2.5M daily hosted open-weight tokens** (120 RPM), all 12 lifecycle agents & multi-agent squads, hosted KSpaces CRDT sync, unlimited KFlow workflows & PM boards, **plus** 0%-markup BYOM included |
| **Keelway Enterprise** (`enterprise`) | `SOVEREIGN VPC & SLA` | **Custom** | `Dedicated VPC · Air-Gap · SLA` | Dedicated regional GPU VPCs or air-gapped on-prem racks (50M+ tok/day, 2,000 RPM), SAML/OIDC SSO, multi-org RBAC, dual-human P-10 quorum, CycloneDX 1.5 SBOMs, 99.95% SLA |
| **Keelway Marketplace** (`marketplace`) | `CREATOR MARKETPLACE · 85/15` | **85% Creator / 15% Platform** | `80/20` Partner · `\$0` OSS | Verified third-party creators keep 85% gross revenue; mandatory pre-publication security scan + Ed25519 manifest signing + SHA-256 settlement receipts |

- **Mandatory BYOM Compliance Invariant Preserved**: Consumer web subscriptions (ChatGPT Plus/Pro, Claude Pro/Max, session cookies) remain strictly fail-closed (`CREDENTIAL_TYPE_UNSUPPORTED_CONSUMER_SUBSCRIPTION`) and clearly disclosed on `/pricing#byom-compliance` and FAQ.

---

## 3. Architecture & Modular File Boundaries (`<750` Lines Each)

### Component A — MiroFish Pricing & Unit-Economics Simulator (`core/eval/pricing_mirofish.py` + API Route)
- **`core/eval/pricing_mirofish.py` (`<360` lines)**:
  - `PricingMiroFishSimulator`: Evaluates any pricing schedule (`legacy_uncalibrated` vs `calibrated_v2` or custom candidate) across two layers:
    1. **Deterministic Unit-Economics & Anti-Cannibalization Engine**: Models P50 and P95 daily hosted open-weight inference cost (`$0.06` per 1M open-weight hosted tokens on Spot/Cluster vLLM), computing net gross margin for `byom` (`$15` annual -> `>93%` gross margin) and `pro` (`$29` annual -> `>84%` gross margin at P50, positive margin even at P95), plus buyer proxy-tax savings vs 20%-markup AI gateways.
    2. **5-Persona OASIS Swarm Simulation on `MiroFishSwarmHarness`**: Runs `Amara Diallo` (Indie OSS Dev), `Marcus Vance` (Heavy-BYOM Startup CTO), `Elena Rostova` (Product/Ops Non-Coder Lead), `David Okafor` (Enterprise CISO/FinOps), and `Priya Nair` (Marketplace Creator) through `LocalZepGraphStore` + `SpeculativeDecodingEngine` (`ReportAgent`), quantifying supportive-stance conversion rate, hidden-fee distrust score (`0.68 -> 0.00`), and overall `pricing_health_score` (`0–100`).
- **API & SDK Exposure**:
  - `POST /v1/platform/pricing/simulate` mounted in `core/api/platform_runtime_routes.py` (stays `<560` lines) + `simulate_pricing` / `simulatePricing` / `SimulatePricing` added to Python, TypeScript, and Go SDKs.

### Component B — Website `/pricing` Redesign (`website/src/components/pricing/PricingTiers.tsx` & `website/src/data/pricing.ts`)
- Replaces all `STREAM 1..5` badges with clean customer badges (`OPEN-CORE · APACHE-2.0`, `MOST POPULAR · FULL STACK`, `BYOM · 0% TOKEN MARKUP`, `SOVEREIGN VPC & SLA`, `CREATOR MARKETPLACE · 85/15`).
- Renders **4 crisp, aligned cards** (`Community $0`, `BYOM $15/$19`, `Keelway Pro $29/$35` highlighted, `Enterprise Custom`) with single-line tabular typography (`whitespace-nowrap`) so zero price headers wrap awkwardly at `1280px–1440px`.
- Upgrades the **Interactive Team & Proxy-Tax Calculator Bar** so moving the `1–50` seat slider displays live monthly totals for **both** `BYOM ($15 × seats)` and `Keelway Pro ($29 × seats)` plus estimated monthly savings vs a 20% token-markup gateway.
- Updates `website/src/app/pricing/page.tsx` metadata (`$15/mo BYOM`, `$29/mo Keelway Pro`) and `tests/test_website_facts.py` assertions (enforcing zero `STREAM 1..5` jargon on `/pricing`).

### Component C — Sovereign CLI Phase 5/6 Runtime & MiroFish Commands (`core/cli_runtime.py` + `core/cli_tui.py`)
- **`core/cli_runtime.py` (`<320` lines)** wired via `core/cli_tui.py` (zero edits to `cli.py`):
  - `keelway vault <list|put|rotate|delete>` (operates against `LocalSecretVault` with masked `****` output; never prints plaintext secrets)
  - `keelway workspace <list|create|rbac-check>` (operates against `WorkspaceRbacController`)
  - `keelway run --kind <agent|workflow> --target <ID> --objective <TEXT> [--no-p10] [--json]` (streams deterministic execution trace events locally)
  - `keelway pricing-eval [--compare-legacy] [--json]` (executes `PricingMiroFishSimulator` from the terminal and prints persona conversion, distrust reduction, and unit-economics margins)

### Component D — Dev Tool (`:7420/app`) Operations Quota & MiroFish Pricing Panel
- **`dev-app/src/components/platform/QuotaAndPricingSimulatorPanel.tsx` (`<240` lines)** integrated into `OperationsWorkspaceView` (`AutomationAndOpsViews.tsx`):
  - Displays calibrated active tier cards (`Community $0`, `BYOM $15/mo`, `Pro $29/mo`, `Enterprise Custom`), live token/RPM fair-use quota meter, and a one-click **"Run 5-Persona Pricing & Margin Simulation"** button calling `POST /v1/platform/pricing/simulate` (with deterministic offline fallback) and rendering per-persona stance badges + gross margin & proxy-savings metrics with `0` `axe-core` WCAG 2.2 AA violations.

---

## 4. Verification Criteria
1. `tests/test_pricing_mirofish.py`: Verifies calibrated pricing beats legacy pricing on conversion rate, eliminates hidden-fee distrust (`0.0`), maintains positive gross margin across P50/P95 token loads, and completes all 5 stages of `MiroFishSwarmHarness`.
2. `tests/test_cli_runtime_phase6.py`: Verifies `keelway vault`, `keelway workspace`, `keelway run`, and `keelway pricing-eval` CLI subcommands (`--json` and human-readable output, zero secret leakage).
3. `dev-app/src/__tests__/phase6-ops-pricing-simulator.test.tsx`: Verifies the Operations Quota & Pricing Simulator panel + `0` `axe-core` violations.
4. `tests/test_website_facts.py` + `./scripts/verify_engineering_gates.sh`: `[1/8]`–`[8/8]` `100% VERIFIED`, Next.js build `17/17` static pages, `git push origin main`, and live curl verification on `https://kora-sable.vercel.app/pricing`.
