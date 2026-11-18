"""Unit and API integration tests for Keelway Hybrid Model Routing and Unified AI API.

Validates:
- Explicit model routing to open-weight and closed models
- Privacy fail-closed invariant (strict blocking of cloud egress for private data)
- Air-gap fail-closed invariant
- GET /v1/models catalog discovery
- POST /v1/chat/completions (OpenAI compatible, non-streaming & streaming)
- GET /v1/usage cost ledger interrogation
"""

from __future__ import annotations

import json
import pytest
import httpx
from httpx import AsyncClient, ASGITransport

from core.main import app
from core.api.schemas import MessageSchema, Provider
from core.models.registry import model_registry, ModelCategory
from core.models.provider import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    StreamChunk,
)
from core.models.adapters.open_weight import OpenWeightProviderAdapter
from core.models.adapters.openai_provider import OpenAIProviderAdapter
from core.models.gateway import ModelGateway


# ---------------------------------------------------------------------------
# Routing & Gateway Policy Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_gateway_explicit_open_weight_routing():
    """Verify gateway directs open-weight model requests to OpenWeightProviderAdapter."""
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/version":
            return httpx.Response(200, json={"version": "0.1.32"})
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "qwen2.5-coder:7b"}]})
        return httpx.Response(200, json={
            "model": "qwen2.5-coder:7b",
            "message": {"role": "assistant", "content": "print('ok')"},
            "done": True,
            "prompt_eval_count": 10,
            "eval_count": 5,
        })

    mock_transport = httpx.MockTransport(handler)
    gw = ModelGateway()
    gw.open_weight_adapter = OpenWeightProviderAdapter(
        base_url="http://localhost:11434",
        api="ollama",
        transport=mock_transport,
    )
    gw.adapters[Provider.LOCAL] = gw.open_weight_adapter

    req = ChatCompletionRequest(
        model="qwen2.5-coder:7b",
        messages=[MessageSchema(role="user", content="Write code")],
    )
    resp = await gw.chat_complete(req)

    assert resp.content == "print('ok')"
    assert resp.model == "qwen2.5-coder:7b"
    assert resp.provider == Provider.LOCAL
    assert resp.category == ModelCategory.OPEN_WEIGHT
    assert resp.cost_usd == 0.0


@pytest.mark.asyncio
async def test_gateway_privacy_fail_closed_invariant():
    """CRITICAL SECURITY TEST:

    When privacy_level is 'private', requests MUST NEVER route to closed cloud providers.
    Attempting to route private data to an explicit closed proprietary model must fail closed.
    """
    gw = ModelGateway()

    req = ChatCompletionRequest(
        model="gpt-4o",  # Closed proprietary cloud model
        privacy_level="private",
        messages=[MessageSchema(role="user", content="Confidential internal source code")],
    )

    # Calling with privacy_level="private" for a cloud model results in empty allowed order -> fail closed
    with pytest.raises(RuntimeError) as exc_info:
        await gw.chat_complete(req)

    assert "No model provider allowed" in str(exc_info.value) or "failed or unavailable" in str(exc_info.value)


@pytest.mark.asyncio
async def test_gateway_air_gap_fail_closed_invariant():
    """CRITICAL SECURITY TEST:

    When air-gap mode is active in the environment, all cloud egress must be blocked.
    """
    gw = ModelGateway()
    gw.air_gap.enabled = True

    req = ChatCompletionRequest(
        model="gpt-4o",
        messages=[MessageSchema(role="user", content="Hello")],
    )

    with pytest.raises(RuntimeError) as exc_info:
        await gw.chat_complete(req)

    assert "All model providers failed or unavailable" in str(exc_info.value) or "No model provider allowed" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Unified AI API Endpoint Tests (GET /v1/models, POST /v1/chat/completions)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_api_get_v1_models(monkeypatch):
    """Verify GET /v1/models returns the registered catalog with category metadata."""
    # Deterministic runtime state: no local model server reachable.
    from types import SimpleNamespace
    from core.models.adapters.open_weight import OpenWeightProviderAdapter

    monkeypatch.setattr(
        OpenWeightProviderAdapter,
        "local_runtime",
        lambda self: SimpleNamespace(up=False, models=[], api="ollama"),
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/v1/models")
        assert resp.status_code == 200
        data = resp.json()

        assert data["object"] == "list"
        assert "data" in data
        assert len(data["data"]) >= 9

        model_ids = [m["id"] for m in data["data"]]
        # Both open-weight and closed models are represented
        assert "qwen2.5-coder:7b" in model_ids
        assert "gpt-4o" in model_ids
        assert "claude-3-5-sonnet" in model_ids

        # Check model descriptor structure
        qwen = next(m for m in data["data"] if m["id"] == "qwen2.5-coder:7b")
        assert qwen["category"] == "open_weight"
        assert qwen["deployment"] == "local_daemon"
        assert "code" in qwen["capabilities"]

        # KEEL-ENG-039: registry-vs-reality disclosure fields
        for m in data["data"]:
            assert "installed" in m and "simulated" in m
            assert isinstance(m["simulated"], bool)
        keelway_model = next(m for m in data["data"] if m["id"] == "keelway-core:7b")
        # KEEL-PROD-041: flagship alias exists but no runtime is installed here.
        assert keelway_model["simulated"] is True
        assert keelway_model["runtime_alias"] is True
        assert keelway_model["resolved_model"] is None
        nano_model = next(m for m in data["data"] if m["id"] == "keelway-nano:1.5b")
        assert nano_model["simulated"] is True
        assert nano_model["runtime_alias"] is False
        gpt = next(m for m in data["data"] if m["id"] == "gpt-4o")
        assert gpt["installed"] is None and gpt["simulated"] is False


@pytest.mark.asyncio
async def test_api_post_v1_chat_completions_non_streaming(monkeypatch):
    """Verify POST /v1/chat/completions non-streaming response."""
    async def mock_chat_complete(self, request):
        return ChatCompletionResponse(
            id="chatcmpl-test-123",
            model=request.model or "qwen2.5-coder:7b",
            provider=Provider.LOCAL,
            category=ModelCategory.OPEN_WEIGHT,
            content="Mocked response from Keelway Engine",
            usage={"prompt_tokens": 15, "completion_tokens": 10, "total_tokens": 25},
            latency_ms=120.5,
            cost_usd=0.0,
            routing_reason="Open-Weight Inference ($0.00 external API cost)",
        )

    monkeypatch.setattr(ModelGateway, "chat_complete", mock_chat_complete)

    payload = {
        "model": "qwen2.5-coder:7b",
        "messages": [{"role": "user", "content": "Say hello"}],
        "temperature": 0.5,
        "stream": False,
    }

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/v1/chat/completions", json=payload)
        assert resp.status_code == 200
        body = resp.json()

        assert body["object"] == "chat.completion"
        assert body["id"] == "chatcmpl-test-123"
        assert body["model"] == "qwen2.5-coder:7b"
        assert body["choices"][0]["message"]["content"] == "Mocked response from Keelway Engine"
        assert body["usage"]["total_tokens"] == 25


@pytest.mark.asyncio
async def test_api_post_v1_chat_completions_streaming(monkeypatch):
    """Verify POST /v1/chat/completions with stream=True returns SSE chunks."""
    async def mock_stream_chat(self, request):
        yield StreamChunk(id="c1", model=request.model or "qwen2.5-coder:7b", provider=Provider.LOCAL, delta_content="Hello ")
        yield StreamChunk(id="c2", model=request.model or "qwen2.5-coder:7b", provider=Provider.LOCAL, delta_content="streaming world!")

    monkeypatch.setattr(ModelGateway, "stream_chat", mock_stream_chat)

    payload = {
        "model": "qwen2.5-coder:7b",
        "messages": [{"role": "user", "content": "Stream to me"}],
        "stream": True,
    }

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/v1/chat/completions", json=payload)
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]

        content = resp.text
        assert "data: " in content
        assert "Hello " in content
        assert "streaming world!" in content
        assert "data: [DONE]" in content


@pytest.mark.asyncio
async def test_api_get_v1_usage():
    """Verify GET /v1/usage returns cost tracking and aggregated token usage."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/v1/usage")
        assert resp.status_code == 200
        body = resp.json()

        assert "billed_cloud_expenditure_usd" in body
        assert "quantified_local_savings_usd" in body
        assert "total_tokens" in body
        assert "by_provider" in body
        assert "by_model" in body
        assert "total_inferences" in body
