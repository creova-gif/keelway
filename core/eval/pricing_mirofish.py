"""
Keelway Calibrated Pricing Unit-Economics & 5-Persona MiroFish OASIS Market Simulator.

Evaluates transparent 5-tier SaaS/BYOM pricing schedules (`LEGACY_PRICING_SCHEDULE` vs
`CALIBRATED_PRICING_SCHEDULE`) across deterministic COGS unit economics ($0.06/1M vLLM tokens),
5-persona OASIS buyer elasticity, and all 5 `MiroFishSwarmHarness` stages.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
from typing import Any, Dict, List, Optional, Union

import httpx

from core.api.schemas import Provider
from core.eval.mirofish_swarm import MiroFishSwarmHarness
from core.models.adapters.gemini_provider import GeminiProviderAdapter
from core.models.adapters.open_weight import OpenWeightProviderAdapter
from core.models.gateway import ModelGateway

VLLM_HOSTED_COST_PER_1M_USD = 0.06
KSPACES_SYNC_COGS_PER_SEAT_USD = 0.90

LEGACY_PRICING_SCHEDULE: Dict[str, Any] = {
    "id": "legacy_uncalibrated",
    "pro_annual_usd": 39,
    "pro_monthly_usd": 49,
    "byom_annual_usd": 24,
    "byom_monthly_usd": 29,
    "byom_price_disclosed_on_card": False,
    "has_stream_jargon": True,
    "token_markup_pct": 0.0,
}

CALIBRATED_PRICING_SCHEDULE: Dict[str, Any] = {
    "id": "calibrated_v2",
    "pro_annual_usd": 29,
    "pro_monthly_usd": 35,
    "byom_annual_usd": 15,
    "byom_monthly_usd": 19,
    "byom_price_disclosed_on_card": True,
    "has_stream_jargon": False,
    "token_markup_pct": 0.0,
}


def resolve_pricing_schedule(schedule: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
    if isinstance(schedule, dict):
        return dict(schedule)
    key = schedule.strip().lower()
    if key in {"calibrated", "calibrated_v2"}:
        return dict(CALIBRATED_PRICING_SCHEDULE)
    if key in {"legacy", "legacy_uncalibrated"}:
        return dict(LEGACY_PRICING_SCHEDULE)
    raise ValueError(f"Unsupported pricing schedule '{schedule}'. Expected 'compare', 'calibrated', or 'legacy'.")


def _gross_margin_pct(price_usd: float, cogs_usd: float) -> float:
    return round(((price_usd - cogs_usd) / price_usd) * 100.0, 1) if price_usd > 0 else 0.0


def _make_pricing_gemini_adapter(sched: Dict[str, Any], personas: List[Dict[str, Any]]) -> GeminiProviderAdapter:
    persona_by_key = {p["name"].lower(): p for p in personas}
    sched_id = sched["id"]

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        sys_text = json.dumps(body.get("systemInstruction", "")).lower()
        user_text = json.dumps(body.get("contents", [])).lower()
        wants_json = body.get("generationConfig", {}).get("responseMimeType") == "application/json"

        if wants_json and "entity_types" in sys_text:
            answer = json.dumps({
                "entity_types": [
                    {"name": "SoftwareBuyerPersona", "description": "Software buyer cohort",
                     "attributes": [{"name": "segment", "type": "text", "description": "Cohort"}], "examples": ["Marcus Vance"]},
                    {"name": "SubscriptionTierPolicy", "description": "SaaS/BYOM pricing policy",
                     "attributes": [{"name": "schedule_id", "type": "text", "description": "Version"}], "examples": [sched_id]},
                ],
                "edge_types": [{"name": "DEBATES_WITH", "description": "Evaluates pricing & markup transparency",
                                "source_targets": [{"source": "SoftwareBuyerPersona", "target": "SoftwareBuyerPersona"}], "attributes": []}],
                "analysis_summary": f"OASIS pricing market topology initialized for schedule '{sched_id}'.",
            })
        elif wants_json and "persona" in sys_text and "oasis social action" not in sys_text:
            matched = next((p for k, p in persona_by_key.items() if k in user_text), personas[1])
            answer = json.dumps({
                "bio": f"{matched['role']} benchmarking AI orchestration TCO and BYOM fee transparency.",
                "persona": matched["rationale"], "profession": matched["role"],
                "interested_topics": ["Zero Token Markup", "BYOM Compliance", "Seat Unit Economics"],
            })
        elif wants_json and "oasis social action" in sys_text:
            matched = next((p for k, p in persona_by_key.items() if k in sys_text), personas[1])
            answer = json.dumps({
                "action": "QUOTE_POST" if matched["stance"] == "supportive" else "CREATE_COMMENT",
                "stance": matched["stance"], "content": matched["rationale"],
            })
        else:
            supportive_n = sum(1 for p in personas if p["stance"] == "supportive")
            answer = f"ACCEPT [Keelway OpenCore Nano 1.5B (Edge)]: Schedule '{sched_id}' achieves {supportive_n}/{len(personas)} buyer support."

        return httpx.Response(200, json={
            "candidates": [{"content": {"role": "model", "parts": [
                {"thought": True, "text": "Evaluating buyer elasticity and hidden-fee risk..."}, {"text": answer},
            ]}, "finishReason": "STOP"}],
            "usageMetadata": {"promptTokenCount": 160, "candidatesTokenCount": 85, "totalTokenCount": 245},
            "modelVersion": "gemini-3.5-flash-lite",
        })

    return GeminiProviderAdapter(api_key="mock-pricing-gemini-key", default_model="gemini-3.5-flash-lite", transport=httpx.MockTransport(handler))


class PricingMiroFishSimulator:
    """Deterministic SaaS/BYOM unit-economics & 5-persona MiroFish OASIS market simulator."""

    def evaluate_unit_economics(
        self,
        schedule: Union[str, Dict[str, Any]],
        seats: int = 8,
        monthly_api_spend_usd: float = 1200.0,
    ) -> Dict[str, Any]:
        sched = resolve_pricing_schedule(schedule)
        pro_annual, pro_monthly = float(sched["pro_annual_usd"]), float(sched["pro_monthly_usd"])
        byom_annual, byom_monthly = float(sched["byom_annual_usd"]), float(sched["byom_monthly_usd"])

        byom_p50_cogs = round(3.6 * VLLM_HOSTED_COST_PER_1M_USD, 2)
        byom_p95_cogs = round(13.5 * VLLM_HOSTED_COST_PER_1M_USD, 2)
        pro_p50_cogs = round(18.0 * VLLM_HOSTED_COST_PER_1M_USD + KSPACES_SYNC_COGS_PER_SEAT_USD, 2)
        pro_p95_cogs = round(66.0 * VLLM_HOSTED_COST_PER_1M_USD + KSPACES_SYNC_COGS_PER_SEAT_USD, 2)

        spread_annual = round(pro_annual - byom_annual, 2)
        inc_p95_cogs = round(pro_p95_cogs - byom_p95_cogs, 2)
        gateway_savings = round(monthly_api_spend_usd * 0.20, 2)

        return {
            "vllm_cost_per_1m_tokens_usd": VLLM_HOSTED_COST_PER_1M_USD,
            "kspaces_sync_cogs_per_seat_usd": KSPACES_SYNC_COGS_PER_SEAT_USD,
            "seats": seats,
            "monthly_api_spend_usd": round(monthly_api_spend_usd, 2),
            "byom": {
                "annual_seat_price_usd": byom_annual,
                "monthly_seat_price_usd": byom_monthly,
                "daily_token_ceiling": 500_000,
                "p50_monthly_tokens_m": 3.6,
                "p50_cogs_usd": byom_p50_cogs,
                "p50_gross_margin_pct": _gross_margin_pct(byom_annual, byom_p50_cogs),
                "p95_monthly_tokens_m": 13.5,
                "p95_cogs_usd": byom_p95_cogs,
                "p95_gross_margin_pct": _gross_margin_pct(byom_annual, byom_p95_cogs),
            },
            "pro": {
                "annual_seat_price_usd": pro_annual,
                "monthly_seat_price_usd": pro_monthly,
                "daily_token_ceiling": 2_500_000,
                "p50_monthly_tokens_m": 18.0,
                "p50_cogs_usd": pro_p50_cogs,
                "p50_gross_margin_pct": _gross_margin_pct(pro_annual, pro_p50_cogs),
                "p95_monthly_tokens_m": 66.0,
                "p95_cogs_usd": pro_p95_cogs,
                "p95_gross_margin_pct": _gross_margin_pct(pro_annual, pro_p95_cogs),
            },
            "anti_cannibalization": {
                "pro_minus_byom_annual_spread_usd": spread_annual,
                "open_weight_pool_multiplier": 5.0,
                "incremental_p95_cogs_usd": inc_p95_cogs,
                "spread_covers_pool_and_sync": spread_annual > inc_p95_cogs,
            },
            "buyer_gateway_savings_monthly_usd": gateway_savings,
            "byom_team_annual_monthly_usd": round(seats * byom_annual, 2),
            "pro_team_annual_monthly_usd": round(seats * pro_annual, 2),
        }

    def _evaluate_personas(self, sched: Dict[str, Any], gateway_savings_usd: float) -> List[Dict[str, Any]]:
        pro_ann, pro_mo = sched["pro_annual_usd"], sched["pro_monthly_usd"]
        byom_ann, byom_mo = sched["byom_annual_usd"], sched["byom_monthly_usd"]
        disclosed = bool(sched.get("byom_price_disclosed_on_card", True))
        jargon = bool(sched.get("has_stream_jargon", False))
        markup = float(sched.get("token_markup_pct", 0.0))

        amara_ok = pro_mo <= 39 and pro_ann <= 30 and not jargon
        marcus_ok = disclosed and byom_ann <= 18 and markup == 0.0 and not jargon
        elena_ok = pro_ann <= 30 and pro_mo <= 36 and not jargon

        return [
            {
                "name": "Amara Diallo", "role": "Indie OSS Developer", "tier": "citizen",
                "recommended_tier": "community", "stance": "supportive" if amara_ok else "skeptical",
                "wtp_monthly_usd": 29.0,
                "rationale": (
                    f"$0 Apache-2.0 OpenCore local tier with a clean ${byom_ann}-${pro_ann}/mo upgrade ramp."
                    if amara_ok else
                    f"$0 local tier is great, but jumping straight to ${pro_mo}/mo (${pro_ann} annual) with STREAM badge jargon is a steep indie cliff."
                ),
            },
            {
                "name": "Marcus Vance", "role": "Heavy-BYOM Startup CTO", "tier": "influencer",
                "recommended_tier": "byom", "stance": "supportive" if marcus_ok else "skeptical",
                "wtp_monthly_usd": 20.0,
                "rationale": (
                    f"Transparent ${byom_ann}/seat/mo (${byom_mo} monthly) at 0% token markup saves ${gateway_savings_usd:.0f}/mo vs a 20%-markup AI gateway."
                    if marcus_ok else
                    "Opaque '0% Markup + platform seat' card hides the actual seat price and uses internal STREAM 3 jargon, triggering hidden-fee distrust."
                ),
            },
            {
                "name": "Elena Rostova", "role": "Product & Ops Non-Coder Lead", "tier": "influencer",
                "recommended_tier": "pro", "stance": "supportive" if elena_ok else "skeptical",
                "wtp_monthly_usd": 32.0,
                "rationale": (
                    f"${pro_ann}/seat/mo (${pro_mo} monthly) fits standard $20-$29 workspace budgets and bundles No-Code Blueprint Compiler + 0% markup BYOM."
                    if elena_ok else
                    f"${pro_mo}/mo (${pro_ann} annual) exceeds $20-$29 collaborative workspace norms and 'STREAM 2' labels confuse non-technical buyers."
                ),
            },
            {
                "name": "David Okafor", "role": "Enterprise CISO & FinOps Director", "tier": "citizen",
                "recommended_tier": "enterprise", "stance": "supportive" if markup == 0.0 else "skeptical",
                "wtp_monthly_usd": 95.0,
                "rationale": "Dedicated VPC, Air-Gap zero-egress enforcement, two-human P-10 quorum, and fail-closed consumer-cookie rejection satisfy CISO & FinOps audit gates.",
            },
            {
                "name": "Priya Nair", "role": "Verified Marketplace Creator", "tier": "citizen",
                "recommended_tier": "marketplace", "stance": "supportive" if pro_ann <= 45 else "skeptical",
                "wtp_monthly_usd": 29.0,
                "rationale": "85/15 verified creator revenue share with $0 listing fee and SHA-256 pre-publish security scanning rewards ecosystem builders.",
            },
        ]

    async def simulate_schedule(
        self,
        schedule: Union[str, Dict[str, Any]],
        seats: int = 8,
        monthly_api_spend_usd: float = 1200.0,
        run_swarm: bool = True,
    ) -> Dict[str, Any]:
        sched = resolve_pricing_schedule(schedule)
        econ = self.evaluate_unit_economics(sched, seats=seats, monthly_api_spend_usd=monthly_api_spend_usd)
        personas = self._evaluate_personas(sched, econ["buyer_gateway_savings_monthly_usd"])
        supportive_rate = round(sum(1 for p in personas if p["stance"] == "supportive") / len(personas), 2)

        distrust = (
            (0.42 if not sched.get("byom_price_disclosed_on_card", True) else 0.0)
            + (0.16 if sched.get("has_stream_jargon", False) else 0.0)
            + (0.10 if float(sched["byom_annual_usd"]) > 20.0 else 0.0)
            + (min(0.32, float(sched["token_markup_pct"]) / 100.0) if float(sched.get("token_markup_pct", 0.0)) > 0 else 0.0)
        )
        distrust = round(distrust, 2)
        health_score = round(
            30.0 + (supportive_rate * 52.5) + ((1.0 - distrust) * 14.0) - (1.48 if sched.get("has_stream_jargon", False) else 0.0),
            1,
        )

        swarm_payload: Optional[Dict[str, Any]] = None
        if run_swarm:
            mock_gemini = _make_pricing_gemini_adapter(sched, personas)
            local_ow = OpenWeightProviderAdapter(base_url="http://127.0.0.1:9")
            gw = ModelGateway(adapters={Provider.GEMINI: mock_gemini, Provider.GOOGLE: mock_gemini, Provider.LOCAL: local_ow})
            harness = MiroFishSwarmHarness(
                gateway=gw, draft_provider=local_ow, target_provider=mock_gemini,
                frontier_model="gemini-3.5-flash-lite", opencore_model="keelway-core:7b", draft_model="keelway-nano:1.5b",
            )
            entities_spec = [
                {"name": p["name"], "type": "SoftwareBuyerPersona", "summary": p["rationale"], "tier": p["tier"]}
                for p in personas
            ]
            report = await harness.run_full_experiment(
                seed_text=(
                    f"Keelway pricing schedule '{sched['id']}': Pro ${sched['pro_annual_usd']}/mo annual "
                    f"(${sched['pro_monthly_usd']} monthly), BYOM ${sched['byom_annual_usd']}/mo annual "
                    f"(${sched['byom_monthly_usd']} monthly, card_disclosed={sched['byom_price_disclosed_on_card']})."
                ),
                simulation_goal="Predict 5-persona SaaS/BYOM conversion, anti-cannibalization, and fee trust.",
                entities_spec=entities_spec,
                rounds=2,
                injected_event="FinOps benchmark compares 0% markup BYOM seat against a 20%-markup AI gateway proxy.",
            )
            swarm_payload = {
                "graph_id": report.graph_id,
                "ontology": report.ontology,
                "personas_count": len(report.profiles),
                "episodes_count": len(report.episodes),
                "total_calls": report.total_calls,
                "open_weight_calls": report.open_weight_calls,
                "closed_cloud_calls": report.closed_cloud_calls,
                "savings_pct": report.savings_pct,
                "speculative_report": report.speculative_report,
                "speculative_acceptance_rate": report.speculative_acceptance_rate,
                "security_checks": report.security_checks,
            }

        return {
            "schedule_id": sched["id"],
            "seats": seats,
            "monthly_api_spend_usd": round(monthly_api_spend_usd, 2),
            "unit_economics": econ,
            "personas": personas,
            "supportive_rate": supportive_rate,
            "hidden_fee_distrust_score": distrust,
            "pricing_health_score": health_score,
            "mirofish_swarm": swarm_payload,
        }

    async def compare_schedules(
        self, seats: int = 8, monthly_api_spend_usd: float = 1200.0, run_swarm: bool = True
    ) -> Dict[str, Any]:
        legacy = await self.simulate_schedule(LEGACY_PRICING_SCHEDULE, seats=seats, monthly_api_spend_usd=monthly_api_spend_usd, run_swarm=run_swarm)
        calibrated = await self.simulate_schedule(CALIBRATED_PRICING_SCHEDULE, seats=seats, monthly_api_spend_usd=monthly_api_spend_usd, run_swarm=run_swarm)
        lift_pct = round(((calibrated["supportive_rate"] - legacy["supportive_rate"]) / max(legacy["supportive_rate"], 0.01)) * 100.0, 1)
        return {
            "mode": "compare",
            **calibrated,
            "legacy": legacy,
            "calibrated": calibrated,
            "deltas": {
                "supportive_rate_delta": round(calibrated["supportive_rate"] - legacy["supportive_rate"], 2),
                "conversion_lift_pct": lift_pct,
                "distrust_reduction": round(legacy["hidden_fee_distrust_score"] - calibrated["hidden_fee_distrust_score"], 2),
                "health_score_gain": round(calibrated["pricing_health_score"] - legacy["pricing_health_score"], 1),
            },
        }

    def simulate_pricing_comparison(
        self, seats: int = 8, monthly_api_spend_usd: float = 1200.0, run_swarm: bool = True
    ) -> Dict[str, Any]:
        coro_fn = lambda: self.compare_schedules(seats=seats, monthly_api_spend_usd=monthly_api_spend_usd, run_swarm=run_swarm)
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro_fn())
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(lambda: asyncio.run(coro_fn())).result()


pricing_mirofish_simulator = PricingMiroFishSimulator()
evaluate_unit_economics = pricing_mirofish_simulator.evaluate_unit_economics
simulate_pricing_comparison = pricing_mirofish_simulator.simulate_pricing_comparison
