"""Unit and contract tests for Keelway Hybrid Model Adapters.

Tests OpenWeightProviderAdapter and OpenAIProviderAdapter with mock HTTP transports,
validating request normalization, response parsing, error mapping, and SSE streaming.
"""

from __future__ import annotations

import json
import pytest
import httpx

from core.api.schemas import MessageSchema, Provider
from core.models.registry import ModelCategory
from core.models.provider import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    StreamChunk,
    ProviderAuthenticationError,
    ProviderRateLimitError,
    ModelNotFoundError,
    ContextLengthExceededError,
    ProviderTimeoutError,
)
from core.models.adapters.open_weight import OpenWeightProviderAdapter
from core.models.adapters.openai_provider import OpenAIProviderAdapter


# ---------------------------------------------------------------------------
# Open-Weight Provider Tests (Ollama & OpenAI-Compatible Local Runtimes)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_open_weight_adapter_ollama_non_streaming():
    """Verify Ollama native API request and response parsing."""
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/version":
            return httpx.Response(200, json={"version": "0.1.32"})
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "qwen2.5-coder:7b"}]})
        assert request.url.path == "/api/chat"
        payload = json.loads(request.content.decode("utf-8"))
        assert payload["model"] == "qwen2.5-coder:7b"
        assert len(payload["messages"]) == 1
        assert payload["stream"] is False

        response_body = {
            "model": "qwen2.5-coder:7b",
            "created_at": "2026-03-31T12:00:00Z",
            "message": {
                "role": "assistant",
                "content": "def add(a, b): return a + b",
            },
            "done": True,
            "prompt_eval_count": 24,
            "eval_count": 18,
        }
        return httpx.Response(200, json=response_body)

    mock_transport = httpx.MockTransport(handler)
    adapter = OpenWeightProviderAdapter(
        base_url="http://localhost:11434",
        api="ollama",
        transport=mock_transport,
    )

    req = ChatCompletionRequest(
        model="qwen2.5-coder:7b",
        messages=[MessageSchema(role="user", content="Write a python add function")],
        temperature=0.2,
    )

    resp = await adapter.complete(req)
    assert isinstance(resp, ChatCompletionResponse)
    assert resp.content == "def add(a, b): return a + b"
    assert resp.model == "qwen2.5-coder:7b"
    assert resp.usage["prompt_tokens"] == 24
    assert resp.usage["completion_tokens"] == 18
    assert resp.cost_usd == 0.0  # Open-weight local inference has $0 cloud API cost
    assert resp.category == ModelCategory.OPEN_WEIGHT


@pytest.mark.asyncio
async def test_open_weight_adapter_ollama_streaming():
    """Verify Ollama native API streaming NDJSON chunks."""
    chunks = [
        json.dumps({"message": {"role": "assistant", "content": "Hello"}}),
        json.dumps({"message": {"role": "assistant", "content": " from"}}),
        json.dumps({"message": {"role": "assistant", "content": " Keelway!"}, "done": True}),
    ]
    raw_content = "\n".join(chunks).encode("utf-8")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/version":
            return httpx.Response(200, json={"version": "0.1.32"})
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "qwen2.5-coder:7b"}]})
        assert request.url.path == "/api/chat"
        return httpx.Response(200, content=raw_content)

    mock_transport = httpx.MockTransport(handler)
    adapter = OpenWeightProviderAdapter(
        base_url="http://localhost:11434",
        api="ollama",
        transport=mock_transport,
    )

    req = ChatCompletionRequest(
        model="qwen2.5-coder:7b",
        messages=[MessageSchema(role="user", content="Greet me")],
        stream=True,
    )

    accumulated = []
    async for chunk in adapter.stream_complete(req):
        assert isinstance(chunk, StreamChunk)
        accumulated.append(chunk.delta_content)

    full_text = "".join(accumulated)
    assert full_text == "Hello from Keelway!"


# ---------------------------------------------------------------------------
# Closed Provider Tests (OpenAI Commercial API Adapter)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_openai_adapter_non_streaming():
    """Verify OpenAI provider chat completion and token cost attribution."""
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        assert request.headers.get("Authorization") == "Bearer sk-test-key-mock"
        payload = json.loads(request.content.decode("utf-8"))
        assert payload["model"] == "gpt-4o"

        response_body = {
            "id": "chatcmpl-openai-999",
            "object": "chat.completion",
            "created": 1711886400,
            "model": "gpt-4o",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "Proprietary intelligence"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 1000,
                "completion_tokens": 200,
                "total_tokens": 1200,
            },
        }
        return httpx.Response(200, json=response_body)

    mock_transport = httpx.MockTransport(handler)
    adapter = OpenAIProviderAdapter(api_key="sk-test-key-mock", transport=mock_transport)

    req = ChatCompletionRequest(
        model="gpt-4o",
        messages=[MessageSchema(role="user", content="Hello GPT-4o")],
    )

    resp = await adapter.complete(req)
    assert resp.content == "Proprietary intelligence"
    assert resp.usage["prompt_tokens"] == 1000
    assert resp.usage["completion_tokens"] == 200
    # GPT-4o pricing: $2.50 / 1M prompt ($0.0025) + $10.00 / 1M completion ($0.0020) = $0.0045
    assert resp.cost_usd == pytest.approx(0.0045, rel=1e-3)
    assert resp.category == ModelCategory.CLOSED_PROPRIETARY


@pytest.mark.asyncio
async def test_openai_adapter_streaming_sse():
    """Verify OpenAI provider SSE stream parsing."""
    sse_payload = (
        b'data: {"id":"chatcmpl-1","choices":[{"delta":{"content":"Chunk1"}}]}\n\n'
        b'data: {"id":"chatcmpl-1","choices":[{"delta":{"content":" Chunk2"}}]}\n\n'
        b'data: [DONE]\n\n'
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=sse_payload)

    mock_transport = httpx.MockTransport(handler)
    adapter = OpenAIProviderAdapter(api_key="sk-test-key-mock", transport=mock_transport)

    req = ChatCompletionRequest(
        model="gpt-4o",
        messages=[MessageSchema(role="user", content="Stream test")],
        stream=True,
    )

    deltas = []
    async for chunk in adapter.stream_complete(req):
        deltas.append(chunk.delta_content)

    assert "".join(deltas) == "Chunk1 Chunk2"


@pytest.mark.asyncio
async def test_openai_adapter_error_normalization():
    """Verify OpenAI status codes are converted to normalized ProviderError subclasses."""
    def auth_err_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"message": "Invalid API key"}})

    auth_transport = httpx.MockTransport(auth_err_handler)
    auth_adapter = OpenAIProviderAdapter(api_key="bad-key", transport=auth_transport)

    req = ChatCompletionRequest(model="gpt-4o", messages=[MessageSchema(role="user", content="hi")])

    with pytest.raises(ProviderAuthenticationError) as exc_info:
        await auth_adapter.complete(req)
    assert exc_info.value.status_code == 401
    assert "Invalid or missing OpenAI API key" in str(exc_info.value)

    def rate_limit_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": {"message": "Rate limit exceeded"}})

    rl_transport = httpx.MockTransport(rate_limit_handler)
    rl_adapter = OpenAIProviderAdapter(api_key="key", transport=rl_transport)

    with pytest.raises(ProviderRateLimitError) as exc_info_rl:
        await rl_adapter.complete(req)
    assert exc_info_rl.value.status_code == 429
