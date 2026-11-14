"""
Phase 6A Calibrated Pricing, Unit-Economics & MiroFish OASIS Swarm Verification Suite.

Verifies:
1. Calibrated 5-tier `SUBSCRIPTION_TIERS` pricing, badge labels with zero internal `STREAM` jargon,
   and fail-closed consumer web subscription / session-cookie rejection.
2. Deterministic SaaS/BYOM unit economics & anti-cannibalization margins (`>94%` BYOM, `>83%` Pro).
3. 5-Persona MiroFish OASIS simulation (`LEGACY_PRICING_SCHEDULE` vs `CALIBRATED_PRICING_SCHEDULE`),
   end-to-end 5-stage `MiroFishSwarmHarness` execution, and security/air-gap invariants.
4. FastAPI `POST /v1/platform/pricing/simulate` across `compare`, `calibrated`, and `legacy` modes.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from core.config import settings
from core.eval.pricing_mirofish import (
    CALIBRATED_PRICING_SCHEDULE,
    LEGACY_PRICING_SCHEDULE,
    PricingMiroFishSimulator,
    evaluate_unit_economics,
    simulate_pricing_comparison,
)
from core.main import app
from core.platform.subscription import SUBSCRIPTION_TIERS, SubscriptionPolicyEngine
from core.security.auth import launch_token


def test_calibrated_five_tier_pricing_badges_and_consumer_cookie_guard() -> None:
    engine = SubscriptionPolicyEngine()
    tiers = {t["id"]: t for t in engine.list_tiers()}
    assert list(tiers.keys()) == ["community", "pro", "byom", "enterprise", "marketplace"]

    # 1. Community
    comm = tiers["community"]
    assert comm["monthly_price_usd"] == 0
    assert comm["annual_monthly_price_usd"] == 0
    assert comm["badge_label"] == "OPEN-CORE · APACHE-2.0"

    # 2. Pro ($29 annual / $35 monthly + 0% markup BYOM included)
    pro = tiers["pro"]
    assert pro["annual_monthly_price_usd"] == 29
    assert pro["monthly_price_usd"] == 35
    assert pro["token_markup_pct"] == 0.0
    assert pro["badge_label"] == "MOST POPULAR · FULL STACK"
    expected_pro_caps = {
        "advanced_lifecycle_agents",
        "multi_agent_orchestration",
        "unlimited_workspace_projects",
        "kspaces_encrypted_sync",
        "priority_open_weight_routing",
        "nocode_blueprint_compiler",
        "zero_token_markup_byom_included",
    }
    assert expected_pro_caps.issubset(set(pro["capabilities"]))

    # 3. BYOM ($15 annual / $19 monthly, 0% markup)
    byom = tiers["byom"]
    assert byom["annual_monthly_price_usd"] == 15
    assert byom["monthly_price_usd"] == 19
    assert byom["token_markup_pct"] == 0.0
    assert byom["badge_label"] == "BYOM · 0% TOKEN MARKUP"
    assert byom["platform_billing_mode"] == "separate_orchestration_and_workspace"

    # 4. Enterprise
    ent = tiers["enterprise"]
    assert ent["monthly_price_usd"] is None
    assert ent["annual_monthly_price_usd"] is None
    assert ent["pricing_label"] == "Dedicated VPC · Air-Gap · SLA"
    assert ent["badge_label"] == "SOVEREIGN VPC & SLA"

    # 5. Marketplace
    mp = tiers["marketplace"]
    assert mp["monthly_price_usd"] == 0
    assert mp["annual_monthly_price_usd"] == 0
    assert mp["badge_label"] == "CREATOR MARKETPLACE · 85/15"

    # Zero internal "STREAM" badge jargon on any tier
    for tier_id, spec in SUBSCRIPTION_TIERS.items():
        assert "stream" not in spec["badge_label"].lower(), f"Jargon leaked on {tier_id}"

    # Consumer web subscriptions & cookies still fail-closed
    rejected = engine.validate_byom_credential(
        provider="openai",
        credential_kind="consumer_subscription",
        api_key_preview="chatgpt-plus-web-session",
        model_id="gpt-4.1",
    )
    assert rejected["valid"] is False
    assert rejected["code"] == "CREDENTIAL_TYPE_UNSUPPORTED_CONSUMER_SUBSCRIPTION"


def test_calibrated_unit_economics_and_anti_cannibalization_margins() -> None:
    econ = evaluate_unit_economics(CALIBRATED_PRICING_SCHEDULE, seats=8, monthly_api_spend_usd=1200.0)

    # BYOM: $0.22 P50 COGS & $0.81 P95 COGS -> >94% gross margin at $15/mo annual
    assert econ["byom"]["p50_cogs_usd"] == 0.22
    assert econ["byom"]["p95_cogs_usd"] == 0.81
    assert econ["byom"]["p50_gross_margin_pct"] > 94.0
    assert econ["byom"]["p95_gross_margin_pct"] == 94.6

    # Pro: $1.98 P50 COGS (93.2% GM) & $4.86 P95 COGS (83.2% GM) -> >80% gross margin at $29/mo annual
    assert econ["pro"]["p50_cogs_usd"] == 1.98
    assert econ["pro"]["p50_gross_margin_pct"] == 93.2
    assert econ["pro"]["p95_cogs_usd"] == 4.86
    assert econ["pro"]["p95_gross_margin_pct"] == 83.2
    assert econ["pro"]["p95_gross_margin_pct"] > 80.0

    # Anti-cannibalization spread: $29 - $15 = $14/seat/mo covers 5x open-weight pool + KSpaces sync
    anti = econ["anti_cannibalization"]
    assert anti["pro_minus_byom_annual_spread_usd"] == 14.0
    assert anti["open_weight_pool_multiplier"] == 5.0
    assert anti["incremental_p95_cogs_usd"] == 4.05
    assert anti["spread_covers_pool_and_sync"] is True

    # Buyer monthly savings vs 20%-markup AI gateway proxy at $1,200/mo API spend
    assert econ["buyer_gateway_savings_monthly_usd"] == 240.0


@pytest.mark.asyncio
async def test_mirofish_five_persona_legacy_vs_calibrated_swarm_simulation() -> None:
    simulator = PricingMiroFishSimulator()
    legacy = await simulator.simulate_schedule(LEGACY_PRICING_SCHEDULE, seats=8, monthly_api_spend_usd=1200.0)
    calibrated = await simulator.simulate_schedule(CALIBRATED_PRICING_SCHEDULE, seats=8, monthly_api_spend_usd=1200.0)

    expected_names = [
        "Amara Diallo",
        "Marcus Vance",
        "Elena Rostova",
        "David Okafor",
        "Priya Nair",
    ]
    assert [p["name"] for p in legacy["personas"]] == expected_names
    assert [p["name"] for p in calibrated["personas"]] == expected_names

    # Legacy schedule: Amara, Marcus, Elena skeptical -> 2/5 = 0.4 supportive, 0.68 distrust, 54.0 health
    legacy_stances = {p["name"]: p["stance"] for p in legacy["personas"]}
    assert legacy_stances["Marcus Vance"] == "skeptical"
    assert legacy_stances["Elena Rostova"] == "skeptical"
    assert legacy_stances["Amara Diallo"] == "skeptical"
    assert legacy["supportive_rate"] == 0.4
    assert legacy["hidden_fee_distrust_score"] == 0.68
    assert legacy["pricing_health_score"] == 54.0

    # Calibrated schedule: 5/5 = 1.0 supportive, 0.0 distrust, 96.5 health
    assert all(p["stance"] == "supportive" for p in calibrated["personas"])
    assert calibrated["supportive_rate"] == 1.0
    assert calibrated["hidden_fee_distrust_score"] == 0.0
    assert calibrated["pricing_health_score"] == 96.5

    # Full 5-stage MiroFishSwarmHarness verification on both schedules
    for res in (legacy, calibrated):
        swarm = res["mirofish_swarm"]
        assert swarm is not None
        assert swarm["graph_id"].startswith("keelway-mirofish-")
        assert len(swarm["ontology"]["entity_types"]) >= 2
        assert swarm["personas_count"] == 5
        assert swarm["episodes_count"] >= 10
        assert swarm["open_weight_calls"] >= 9
        assert swarm["closed_cloud_calls"] >= 6
        assert swarm["savings_pct"] > 50.0
        assert len(swarm["speculative_report"]) > 15
        assert swarm["security_checks"] == {
            "prompt_injection_blocked": True,
            "episode_secret_redacted": True,
            "airgap_cloud_egress_blocked": True,
        }

    # Sync comparison wrapper works inside an active asyncio event loop as well
    comp = simulate_pricing_comparison(seats=8, monthly_api_spend_usd=1200.0, run_swarm=False)
    assert comp["legacy"]["supportive_rate"] == 0.4
    assert comp["calibrated"]["supportive_rate"] == 1.0
    assert comp["deltas"] == {
        "supportive_rate_delta": 0.6,
        "conversion_lift_pct": 150.0,
        "distrust_reduction": 0.68,
        "health_score_gain": 42.5,
    }


def test_fastapi_pricing_simulate_route_modes_and_rbac(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "auth_required", True)
    headers = {"Authorization": f"Bearer {launch_token()}"}

    with TestClient(app) as client:
        # Unauthenticated blocked
        assert client.post("/v1/platform/pricing/simulate", json={}).status_code == 401

        # 1. Compare mode (default)
        resp_cmp = client.post(
            "/v1/platform/pricing/simulate",
            headers=headers,
            json={"schedule": "compare", "seats": 8, "monthly_api_spend_usd": 1200.0, "run_swarm": True},
        )
        assert resp_cmp.status_code == 200
        cmp_body = resp_cmp.json()
        assert cmp_body["mode"] == "compare"
        assert cmp_body["legacy"]["supportive_rate"] == 0.4
        assert cmp_body["calibrated"]["supportive_rate"] == 1.0
        assert cmp_body["deltas"]["conversion_lift_pct"] == 150.0
        assert cmp_body["deltas"]["distrust_reduction"] == 0.68
        assert cmp_body["mirofish_swarm"]["security_checks"]["airgap_cloud_egress_blocked"] is True

        # 2. Calibrated single-schedule mode (also permitted for viewer role via read:all)
        resp_cal = client.post(
            "/v1/platform/pricing/simulate",
            headers={**headers, "X-Keelway-Role": "viewer"},
            json={"schedule": "calibrated", "seats": 10, "monthly_api_spend_usd": 2000.0, "run_swarm": False},
        )
        assert resp_cal.status_code == 200
        cal_body = resp_cal.json()
        assert cal_body["schedule_id"] == "calibrated_v2"
        assert cal_body["supportive_rate"] == 1.0
        assert cal_body["unit_economics"]["buyer_gateway_savings_monthly_usd"] == 400.0
        assert cal_body["mirofish_swarm"] is None

        # 3. Legacy single-schedule mode
        resp_leg = client.post(
            "/v1/platform/pricing/simulate",
            headers=headers,
            json={"schedule": "legacy", "seats": 8, "monthly_api_spend_usd": 1200.0, "run_swarm": False},
        )
        assert resp_leg.status_code == 200
        assert resp_leg.json()["schedule_id"] == "legacy_uncalibrated"
        assert resp_leg.json()["supportive_rate"] == 0.4

        # 4. Invalid schedule returns HTTP 400
        resp_bad = client.post(
            "/v1/platform/pricing/simulate",
            headers=headers,
            json={"schedule": "nonexistent_schedule"},
        )
        assert resp_bad.status_code == 400
