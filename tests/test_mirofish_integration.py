"""
Keelway × MiroFish Integration & Multi-Agent Swarm Verification Suite.

Exercises all core Keelway platform ideas under MiroFish's multi-agent prediction workload:
1. OpenAI SDK wire compatibility (`response_format={"type": "json_object"}` & `max_completion_tokens`).
2. Gemini 3.x native `responseMimeType: "application/json"` & internal `thought` part filtering.
3. Local GraphRAG (`LocalZepGraphStore`) replacing Zep Cloud with automatic secret redaction.
4. Hybrid cost arbitrage across OASIS swarm rounds (OpenCore $0.00 citizens + Gemini frontier influencers).
5. Speculative decoding (`keelway-nano:1.5b` -> `gemini-3.5-flash-lite`) for ReportAgent synthesis.
6. Security firewall prompt-injection blocking & Air-Gap zero-egress enforcement.
"""

from __future__ import annotations

import json
import httpx
import pytest

from core.api.schemas import Provider, MessageSchema
from core.eval.mirofish_swarm import (
    LocalZepGraphStore,
    MiroFishSwarmHarness,
    probe_openai_compat_endpoint,
)
from core.main import app
from core.models.adapters.gemini_provider import GeminiProviderAdapter
from core.models.adapters.open_weight import OpenWeightProviderAdapter
from core.models.gateway import ModelGateway
from core.models.provider import ChatCompletionRequest


def _make_mock_gemini_adapter() -> GeminiProviderAdapter:
    """Mock Gemini 3.5 Flash Lite returning realistic JSON + Gemini 3.x thought traces."""

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        sys_text = json.dumps(body.get("systemInstruction", "")).lower()
        user_text = json.dumps(body.get("contents", [])).lower()
        wants_json = body.get("generationConfig", {}).get("responseMimeType") == "application/json"

        if wants_json and "entity_types" in sys_text:
            answer = json.dumps({
                "entity_types": [
                    {
                        "name": "AIEngineer",
                        "description": "Developer evaluating hybrid sovereign AI platforms",
                        "attributes": [{"name": "role", "type": "text", "description": "Engineering role"}],
                        "examples": ["Amara Diallo", "Tunde Bakare"],
                    },
                    {
                        "name": "EnterpriseRegulator",
                        "description": "Data residency and governance authority",
                        "attributes": [{"name": "jurisdiction", "type": "text", "description": "Region"}],
                        "examples": ["East Africa Data Commission"],
                    },
                ],
                "edge_types": [
                    {
                        "name": "DEBATES_WITH",
                        "description": "Engages in public policy and technical discourse",
                        "source_targets": [{"source": "AIEngineer", "target": "EnterpriseRegulator"}],
                        "attributes": [],
                    }
                ],
                "analysis_summary": "Hybrid local-first + frontier routing balances cost and data residency.",
            })
        elif wants_json and "persona" in sys_text and "oasis social action" not in sys_text:
            answer = json.dumps({
                "bio": "Policy & AI infrastructure commentator tracking sovereign AI adoption across global markets.",
                "persona": "Analytical, evidence-driven thought leader focused on verifiable benchmarks and privacy guarantees.",
                "profession": "AI Governance Lead",
                "interested_topics": ["Hybrid AI", "Data Residency", "OpenCore Models"],
            })
        elif wants_json and "oasis social action" in sys_text:
            answer = json.dumps({
                "action": "QUOTE_POST",
                "stance": "supportive",
                "content": "Empirical telemetry confirms hybrid routing cuts inference spend by >65% with zero private data egress.",
            })
        elif "draft" in user_text or "verify" in sys_text or "accept" in sys_text:
            answer = "ACCEPT [Keelway OpenCore Nano 1.5B (Edge)]: Consensus favors sovereign hybrid AI adoption."
        else:
            answer = "MiroFish ReportAgent Prediction: Strong developer convergence toward hybrid OpenCore + Gemini routing."

        # Include a Gemini 3.x `thought: True` part to verify `_extract_non_thought_text` strips it cleanly!
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "role": "model",
                            "parts": [
                                {"thought": True, "text": "Internal reasoning trace that must not pollute JSON..."},
                                {"text": answer},
                            ],
                        },
                        "finishReason": "STOP",
                    }
                ],
                "usageMetadata": {
                    "promptTokenCount": 180,
                    "candidatesTokenCount": 95,
                    "totalTokenCount": 275,
                },
                "modelVersion": "gemini-3.5-flash-lite",
            },
        )

    return GeminiProviderAdapter(
        api_key="mock-gemini-key",
        default_model="gemini-3.5-flash-lite",
        transport=httpx.MockTransport(handler),
    )


@pytest.mark.asyncio
async def test_openai_sdk_json_mode_and_max_completion_tokens_compat(monkeypatch):
    """Verify MiroFish's OpenAI SDK wire format (`response_format` + `max_completion_tokens`) works via `/v1/chat/completions`."""
    from core.config import settings

    monkeypatch.setattr(settings, "auth_required", False)
    payload = await probe_openai_compat_endpoint(app, model="keelway-core:7b")

    assert payload["object"] == "chat.completion"
    content = payload["choices"][0]["message"]["content"]
    parsed = json.loads(content)
    assert "entity_types" in parsed
    assert "edge_types" in parsed
    assert payload["keelway_metadata"]["cost_usd"] == 0.0


@pytest.mark.asyncio
async def test_gemini_json_mime_type_and_thought_part_filtering():
    """Verify Gemini adapter sets `responseMimeType: application/json` and strips Gemini 3.x `thought: True` parts."""
    gemini = _make_mock_gemini_adapter()
    req = ChatCompletionRequest(
        model="gemini-3.5-flash-lite",
        messages=[
            MessageSchema(role="system", content="Return entity_types and edge_types JSON."),
            MessageSchema(role="user", content="Analyze sovereign AI ecosystem."),
        ],
        response_format={"type": "json_object"},
        max_completion_tokens=512,
    )
    assert req.max_tokens == 512

    resp = await gemini.complete(req)
    parsed = json.loads(resp.content)
    assert parsed["entity_types"][0]["name"] == "AIEngineer"
    assert "Internal reasoning trace" not in resp.content


def test_local_zep_graph_store_redacts_secrets():
    """Verify LocalZepGraphStore replaces Zep Cloud locally and strips leaked credentials from edges & episodes."""
    store = LocalZepGraphStore(graph_id="test-graph")
    n1 = store.upsert_entity("Amara Diallo", "AIEngineer", "Principal ML Engineer")
    n2 = store.upsert_entity("Keelway Labs", "Organization", "Hybrid AI Platform")
    store.add_edge(n1.uuid, n2.uuid, "WORKS_FOR", "Token JWT_SECRET=super-secret-value-12345")
    ep = store.add_episode("Amara Diallo", "CREATE_POST", "Accidentally pasted AKIAABCDEFGHIJKLMNOP", 1)

    assert "super-secret-value-12345" not in store.edges[0]["fact"]
    assert "AKIAABCDEFGHIJKLMNOP" not in ep["content"]
    assert n1.get_entity_type() == "AIEngineer"


@pytest.mark.asyncio
async def test_full_mirofish_five_stage_hybrid_swarm_pipeline():
    """Run all 5 MiroFish stages through Keelway and verify hybrid cost arbitrage, speculative synthesis, and security."""
    mock_gemini = _make_mock_gemini_adapter()
    local_open_weight = OpenWeightProviderAdapter(base_url="http://127.0.0.1:9")  # offline daemon -> routes to OpenCore

    gw = ModelGateway(
        adapters={
            Provider.GEMINI: mock_gemini,
            Provider.GOOGLE: mock_gemini,
            Provider.LOCAL: local_open_weight,
        }
    )

    harness = MiroFishSwarmHarness(
        gateway=gw,
        draft_provider=local_open_weight,
        target_provider=mock_gemini,
        frontier_model="gemini-3.5-flash-lite",
        opencore_model="keelway-core:7b",
        draft_model="keelway-nano:1.5b",
    )

    report = await harness.run_full_experiment(
        seed_text=(
            "Enterprises across Nairobi, Lagos, and London are evaluating hybrid AI gateways "
            "that combine zero-egress OpenCore 7B/1.5B weights with Gemini 3.5 Flash cloud burst."
        ),
        simulation_goal="Predict developer and regulator sentiment after a 65% inference cost reduction announcement.",
        entities_spec=[
            {
                "name": "Amara Diallo",
                "type": "AIEngineer",
                "summary": "Influential open-source ML systems lead benchmarking latency and cost.",
                "tier": "influencer",
            },
            {
                "name": "Kwame Mensah",
                "type": "AIEngineer",
                "summary": "Fintech backend engineer requiring strict zero-egress privacy for customer data.",
                "tier": "citizen",
            },
            {
                "name": "Zainab Osei",
                "type": "AIEngineer",
                "summary": "Startup CTO running high-volume agent workflows on edge GPUs.",
                "tier": "citizen",
            },
        ],
        rounds=2,
        injected_event="Keelway publishes Apache-2.0 OpenCore weights with verified SHA-256 manifests and speculative decoding.",
    )

    # Stage 1: Ontology verified
    assert len(report.ontology["entity_types"]) >= 2
    assert len(report.ontology["edge_types"]) >= 1

    # Stage 2: Personas verified
    assert len(report.profiles) == 3
    tiers = [p.tier for p in report.profiles]
    assert tiers.count("influencer") == 1
    assert tiers.count("citizen") == 2

    # Stage 3: Hybrid Cost Arbitrage verified (citizens ran on OpenCore at $0.00, influencer/ontology/verifier on Gemini)
    assert report.open_weight_calls >= 6  # 2 citizen personas + 4 citizen swarm turns + speculative draft
    assert report.closed_cloud_calls >= 4  # ontology + influencer persona + influencer swarm turns + verifier
    assert report.savings_pct > 50.0

    # Stage 4: Speculative ReportAgent synthesis verified
    assert len(report.speculative_report) > 15

    # Stage 5: All 3 security & air-gap invariants verified
    assert report.security_checks == {
        "prompt_injection_blocked": True,
        "episode_secret_redacted": True,
        "airgap_cloud_egress_blocked": True,
    }
