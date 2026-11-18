# KEEL-PRICING-013 — Phase 6: Calibrated 5-Tier Pricing Ladder, MiroFish 5-Persona Market & Unit-Economics Swarm Simulator, Sovereign CLI Runtime & Operations Quota UI

- **Status**: `VERIFIED_COMPLETE`
- **Assigned Agent**: Google Antigravity (4-Agent Parallel Wave: `6A`, `6B`, `6C`, `6D`)
- **Date**: 2026-11-14
- **Branch**: `main`

## Summary

Calibrated Keelway's 5-tier subscription and monetization ladder across the backend policy engine (`core/platform/subscription.py`), flagship website (`website/src/components/pricing/PricingTiers.tsx`), Sovereign CLI (`core/cli_runtime.py`), Python/TypeScript/Go SDKs, and Local Dev Tool (`:7420/app` Operations view), validated end-to-end via a 5-persona MiroFish OASIS buyer/creator swarm and P50/P95 unit-economics harness (`core/eval/pricing_mirofish.py` + `POST /v1/platform/pricing/simulate`).

## Key Deliverables

1. **Calibrated 5-Tier Pricing Ladder & Customer-Clean Website `/pricing`**:
   - **Free / Community** (`community`): `$0` forever (`OPEN-CORE · APACHE-2.0`, unlimited local OpenCore weights at `$0.00/tok`, 150K/day hosted pool · 20 RPM).
   - **Bring Your Own Model (BYOM)** (`byom`): `$15 / seat / mo` annual (`$19` monthly) (`BYOM · 0% TOKEN MARKUP`, explicit dollar seat pricing replacing the legacy 2-line `"0% Markup + platform seat"` display, `0%` proxy markup on authorized OpenAI/Anthropic/Gemini/vLLM API keys + 500K/day open-weight fallback, fail-closed rejection of ChatGPT Plus/Pro and Claude Pro/Max consumer web sessions).
   - **Keelway Pro** (`pro`): `$29 / seat / mo` annual (`$35` monthly) (`MOST POPULAR · FULL STACK`, highlighted card, 2.5M/day hosted open-weight tokens · 120 RPM, all 12 lifecycle agents & squads, KSpaces CRDT sync, unlimited KFlow DAGs + 0%-markup BYOM included).
   - **Keelway Enterprise** (`enterprise`): `Custom` (`SOVEREIGN VPC & SLA`, single-line non-wrapping `Dedicated VPC · Air-Gap · SLA`).
   - **Keelway Marketplace** (`marketplace`): `85% Creator / 15% Platform` (`CREATOR MARKETPLACE · 85/15`, zero internal `STREAM 1..5` labels).
2. **MiroFish 5-Persona Market & Unit-Economics Swarm Harness (`core/eval/pricing_mirofish.py`)**:
   - Evaluates `legacy`, `calibrated`, and `compare` schedules across 5 OASIS personas (`Amara Diallo`, `Marcus Vance`, `Elena Rostova`, `David Okafor`, `Priya Nair`) using `MiroFishSwarmHarness` (`LocalZepGraphStore` + `SpeculativeDecodingEngine`).
   - Verified deltas (`legacy` -> `calibrated`): `supportive_rate` `0.40 -> 1.00`, `hidden_fee_distrust_score` `0.68 -> 0.00`, `pricing_health_score` `54.0 -> 96.5`, P50/P95 gross margin `98.5%/94.6%` (`byom`) and `93.2%/83.2%` (`pro`), saving `$240/mo` vs a 20% proxy markup on `$1,200/mo` API spend.
3. **Sovereign CLI Phase 5/6 Runtime & Tri-SDK Parity**:
   - Added `keelway vault <list|put|rotate|delete>`, `keelway workspace <list|create|rbac-check>`, `keelway run`, and `keelway pricing-eval` in `core/cli_runtime.py`.
   - Added `simulate_pricing` / `simulatePricing` / `SimulatePricing` across Python (`core.sdk`), TypeScript (`@keelway/sdk`), and Go (`keelway-go`).
4. **Local Dev Tool (`:7420/app`) Operations Quota & MiroFish Simulator**:
   - Shipped `QuotaAndPricingSimulatorPanel.tsx` inside `OperationsWorkspaceView` with live daily token quota gauge, BYOM license preflight tester, and 1-click MiroFish Legacy vs Calibrated comparison (`0` `axe-core` WCAG 2.2 AA violations).
