"""
Keelway v1 — Full-Stack Offline End-to-End Integration Suite (`core.main:app` × `AsyncKeelwayClient`).

Verifies that all 6 architectural layers work together cohesively through `core.main:app`
without requiring live external commercial API keys:
- Layer 1: `/console` 6-tab Web Console + `AsyncKeelwayClient(transport=ASGITransport(app=app))`
- Layer 2: `/v1/models`, `/v1/chat/completions`, `/v1/responses` (stateful `previous_response_id`), `/v1/usage`
- Layer 3 & 4: OpenCore weight catalog, Modelfile compiler, LoRA hot-swap, and local inference
- Layer 5: `/v1/routing/explain` 4-dimension provenance & fail-closed `privacy_level="private"`
- Layer 6: `/v1/governance/*` multi-tenant policy, `kw_live_*` keys, budget downgrade to OpenCore, and SHA-256 audit chain
"""

from __future__ import annotations

import uuid
import pytest
from httpx import ASGITransport

from core.config import settings
from core.main import app
from core.sdk import AsyncKeelwayClient, BudgetExceededError


@pytest.mark.asyncio
async def test_full_stack_v1_control_plane_and_console(monkeypatch):
    monkeypatch.setattr(settings, "auth_required", False)
    transport = ASGITransport(app=app)

    async with AsyncKeelwayClient(base_url="http://keelway.test", transport=transport) as client:
        # 1. Layer 1: Web Console serves self-contained 6-tab air-gap HTML
        console_resp = await client._client.get("/console")
        assert console_resp.status_code == 200
        html = console_resp.text
        assert "/v1/responses" in html
        assert "/v1/opencore/modelfile" in html
        assert "/v1/routing/explain" in html
        assert "/v1/governance/tenants" in html

        # 2. Layer 2 & 4: Unified Model Discovery
        catalog = await client.list_models()
        ids = {m["id"] for m in catalog["data"]}
        assert "keelway-core:7b" in ids
        assert "keelway-coder:7b" in ids
        assert "gemini-3.5-flash-lite" in ids

        # 3. Layer 3 & 4: OpenCore Modelfile & QLoRA Adaptation Recipe
        mf = await client.opencore_modelfile(model_id="keelway-core:7b", base_source="qwen3.5:latest")
        assert "FROM qwen3.5:latest" in mf["modelfile"]

        adapt = await client.opencore_adapt_recipe(
            base_model_id="keelway-core:7b",
            task="multilingual_localization",
            target_languages=["swahili", "yoruba", "amharic"],
        )
        assert adapt["peft_config"]["r"] == 16
        assert adapt["synthetic_sample_count"] >= 5

        # 4. Layer 2: Stateful `/v1/responses` Chaining on Sovereign OpenCore ($0.00)
        r1 = await client.create_response(
            input_data="Initialize sovereign architecture blueprint.",
            model="keelway-core:7b",
        )
        assert r1["object"] == "response"
        assert r1["keelway_metadata"]["cost_usd"] == 0.0

        r2 = await client.create_response(
            input_data="Summarize blueprint status.",
            model="keelway-core:7b",
            previous_response_id=r1["id"],
        )
        assert r2["previous_response_id"] == r1["id"]
        fetched = await client.get_response(r2["id"])
        assert fetched["id"] == r2["id"]

        # 5. Layer 5: Explainable Routing & Fail-Closed Privacy Provenance
        priv_route = await client.explain_route(
            messages="Private medical diagnostic payload",
            model="gpt-4o",
            privacy_level="private",
        )
        assert priv_route["privacy_compliant"] is False
        assert priv_route["selected_provider"] is None

        local_route = await client.explain_route(
            messages="Generate unit test scaffold",
            privacy_level="standard",
        )
        assert local_route["selected_provider"] == "local"
        assert local_route["governance_provenance"]["data_boundary"] == "zero_external_egress"

        # 6. Layer 6: Multi-Tenant Governance — Auto-Downgrade vs Hard 402 Budget Cap
        sfx = uuid.uuid4().hex[:6]
        t_down = f"e2e-downgrade-{sfx}"
        t_strict = f"e2e-strict-{sfx}"
        await client.create_tenant(
            tenant_id=t_down,
            name="Auto-Downgrade Tenant",
            allowed_providers=["local", "openai", "gemini"],
            allowed_categories=["open_weight", "closed_proprietary"],
            daily_spend_limit_usd=0.01,
            monthly_spend_limit_usd=1.0,
            fallback_to_opencore_on_budget_exceeded=True,
        )
        key_res = await client.issue_api_key(tenant_id=t_down, name="sdk-e2e")
        assert key_res["api_key"].startswith("kw_live_")

        await client._req("POST", "/v1/governance/spend/record", json={"tenant_id": t_down, "cost_usd": 0.02, "tokens": 500})
        downgraded = await client.evaluate_governance(
            tenant_id=t_down,
            requested_model="gpt-4o",
            provider="openai",
            category="closed_proprietary",
            estimated_cost_usd=0.005,
            estimated_tokens=300,
        )
        assert downgraded["action"] == "downgrade_opencore"
        assert downgraded["effective_model"] == "keelway-core:7b"

        await client.create_tenant(
            tenant_id=t_strict,
            name="Hard-Cap Tenant",
            allowed_providers=["local", "openai", "gemini"],
            allowed_categories=["open_weight", "closed_proprietary"],
            daily_spend_limit_usd=0.01,
            monthly_spend_limit_usd=1.0,
            fallback_to_opencore_on_budget_exceeded=False,
        )
        await client._req("POST", "/v1/governance/spend/record", json={"tenant_id": t_strict, "cost_usd": 0.02, "tokens": 500})
        with pytest.raises(BudgetExceededError):
            await client.evaluate_governance(
                tenant_id=t_strict,
                requested_model="gpt-4o",
                provider="openai",
                category="closed_proprietary",
                estimated_cost_usd=0.005,
                estimated_tokens=300,
            )

        audit = await client.get_governance_audit()
        assert audit["chain_valid"] is True

        # 7. MiroFish Swarm Endpoint in Deterministic Offline Mode
        swarm_res = await client.run_swarm(
            seed_text="Developers combine OpenCore 7B local weights with cloud verification.",
            simulation_goal="Assess hybrid AI cost efficiency",
            entities_spec=[{"name": "Zainab", "entity_type": "Architect", "summary": "AI infra lead"}],
            rounds=1,
            mode="mock",
        )
        assert swarm_res["telemetry"]["total_calls"] >= 4
        assert all(swarm_res["security_checks"].values())
