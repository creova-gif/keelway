"""
Unit and contract tests for Keelway Anthropic Claude Provider Adapter.

Tests AnthropicProviderAdapter with mock HTTP transports, validating:
- Request normalization and headers
- Top-level system prompt extraction
- Non-streaming message generation, usage parsing, and token cost attribution
- SSE streaming response parsing (content_block_delta)
- Error normalization (401 authentication error, 429 rate limit error, 400 context length exceeded)
- Pricing rate card calculation for Claude 3.5 Sonnet, Claude 3.5 Haiku, and Claude 3 Opus
"""

from __future__ import annotations

import json
import pytest
import httpx

from core.api.schemas import MessageSchema, Provider, CompletionRequestSchema, CompletionResponseSchema
from core.models.registry import ModelCategory
from core.models.provider import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    StreamChunk,
    ProviderAuthenticationError,
    ProviderRateLimitError,
    ContextLengthExceededError,
)
from core.models.adapters.anthropic_provider import AnthropicProviderAdapter


@pytest.mark.asyncio
async def test_anthropic_adapter_non_streaming():
    """Verify Anthropic Claude non-streaming completion, usage, and cost calculation."""
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/messages"
        assert request.headers.get("x-api-key") == "sk-ant-test-key-mock"
        assert request.headers.get("anthropic-version") == "2023-06-01"
        assert request.headers.get("content-type") == "application/json"

        payload = json.loads(request.content.decode("utf-8"))
        assert payload["model"] == "claude-3-5-sonnet"
        assert payload["stream"] is False
        assert payload["max_tokens"] == 2048
        assert payload["temperature"] == 0.2
        assert len(payload["messages"]) == 1
        assert payload["messages"][0] == {"role": "user", "content": "Explain quantum computing"}

        response_body = {
            "id": "msg_01XFDUDYJACGeNeNuEumuNe1",
            "type": "message",
            "role": "assistant",
            "content": [
                {
                    "type": "text",
                    "text": "Quantum computing uses quantum mechanics concepts such as superposition and entanglement.",
                }
            ],
            "model": "claude-3-5-sonnet-20241022",
            "stop_reason": "end_turn",
            "usage": {
                "input_tokens": 1200,
                "output_tokens": 300,
            },
        }
        return httpx.Response(200, json=response_body)

    mock_transport = httpx.MockTransport(handler)
    adapter = AnthropicProviderAdapter(
        api_key="sk-ant-test-key-mock",
        base_url="https://api.anthropic.com/v1",
        transport=mock_transport,
    )

    req = ChatCompletionRequest(
        model="claude-3-5-sonnet",
        messages=[MessageSchema(role="user", content="Explain quantum computing")],
        temperature=0.2,
        max_tokens=2048,
    )

    resp = await adapter.complete(req)
    assert isinstance(resp, ChatCompletionResponse)
    assert resp.id == "msg_01XFDUDYJACGeNeNuEumuNe1"
    assert "Quantum computing uses quantum mechanics" in resp.content
    assert resp.model == "claude-3-5-sonnet-20241022"
    assert resp.provider == Provider.ANTHROPIC
    assert resp.category == ModelCategory.CLOSED_PROPRIETARY
    assert resp.finish_reason == "stop"
    assert resp.usage["prompt_tokens"] == 1200
    assert resp.usage["completion_tokens"] == 300
    assert resp.usage["total_tokens"] == 1500

    # Pricing: claude-3-5-sonnet: $3.00/1M prompt ($0.0036) + $15.00/1M completion ($0.0045) = $0.0081
    expected_cost = (1200 * 3.0 / 1_000_000) + (300 * 15.0 / 1_000_000)
    assert resp.cost_usd == pytest.approx(expected_cost, rel=1e-4)
    assert resp.latency_ms > 0.0


@pytest.mark.asyncio
async def test_anthropic_adapter_system_prompt_extraction():
    """Verify system message is extracted to top-level system parameter in Anthropic payload."""
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/messages"
        payload = json.loads(request.content.decode("utf-8"))

        # Verify system prompt was moved to top-level
        assert payload.get("system") == "You are a master systems engineer.\n\nBe concise."
        # Verify messages list contains only user / assistant roles
        assert payload["messages"] == [
            {"role": "user", "content": "Hello, Claude"}
        ]

        response_body = {
            "id": "msg_sys_test",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": "Acknowledged."}],
            "model": "claude-3-5-sonnet",
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 20, "output_tokens": 5},
        }
        return httpx.Response(200, json=response_body)

    mock_transport = httpx.MockTransport(handler)
    adapter = AnthropicProviderAdapter(api_key="sk-ant-test", transport=mock_transport)

    req = ChatCompletionRequest(
        messages=[
            MessageSchema(role="system", content="You are a master systems engineer."),
            MessageSchema(role="system", content="Be concise."),
            MessageSchema(role="user", content="Hello, Claude"),
        ]
    )

    resp = await adapter.complete(req)
    assert resp.content == "Acknowledged."
    assert resp.usage["prompt_tokens"] == 20
    assert resp.usage["completion_tokens"] == 5


@pytest.mark.asyncio
async def test_anthropic_adapter_pricing_rate_cards():
    """Verify cost calculation across Claude 3.5 Sonnet, Claude 3.5 Haiku, and Claude 3 Opus."""
    adapter = AnthropicProviderAdapter(api_key="sk-ant-test")

    # claude-3-5-sonnet: ($3.00, $15.00)
    cost_sonnet = adapter._compute_cost("claude-3-5-sonnet", 1_000_000, 1_000_000)
    assert cost_sonnet == pytest.approx(18.00, rel=1e-4)

    # claude-3-5-haiku: ($0.80, $4.00)
    cost_haiku = adapter._compute_cost("claude-3-5-haiku", 1_000_000, 1_000_000)
    assert cost_haiku == pytest.approx(4.80, rel=1e-4)

    # claude-3-opus: ($15.00, $75.00)
    cost_opus = adapter._compute_cost("claude-3-opus", 1_000_000, 1_000_000)
    assert cost_opus == pytest.approx(90.00, rel=1e-4)

    # Partial tokens test (e.g. 1000 prompt, 500 completion on Haiku)
    # (1000 * 0.80 / 1e6) + (500 * 4.00 / 1e6) = 0.0008 + 0.0020 = 0.0028
    assert adapter._compute_cost("claude-3-5-haiku", 1000, 500) == pytest.approx(0.0028, rel=1e-4)


@pytest.mark.asyncio
async def test_anthropic_adapter_streaming_sse():
    """Verify Anthropic SSE stream parsing (content_block_delta, message_start, message_delta)."""
    sse_events = (
        b'event: message_start\n'
        b'data: {"type": "message_start", "message": {"id": "msg_stream_42", "model": "claude-3-5-sonnet", "usage": {"input_tokens": 100, "output_tokens": 1}}}\n\n'
        b'event: content_block_delta\n'
        b'data: {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "Hello"}}\n\n'
        b'event: content_block_delta\n'
        b'data: {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": " from"}}\n\n'
        b'event: content_block_delta\n'
        b'data: {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": " Claude 3.5!"}}\n\n'
        b'event: message_delta\n'
        b'data: {"type": "message_delta", "delta": {"stop_reason": "end_turn"}, "usage": {"output_tokens": 15}}\n\n'
        b'event: message_stop\n'
        b'data: {"type": "message_stop"}\n\n'
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/messages"
        payload = json.loads(request.content.decode("utf-8"))
        assert payload["stream"] is True
        return httpx.Response(200, content=sse_events)

    mock_transport = httpx.MockTransport(handler)
    adapter = AnthropicProviderAdapter(api_key="sk-ant-test", transport=mock_transport)

    req = ChatCompletionRequest(
        model="claude-3-5-sonnet",
        messages=[MessageSchema(role="user", content="Stream greeting")],
        stream=True,
    )

    deltas = []
    chunks = []
    async for chunk in adapter.stream_complete(req):
        assert isinstance(chunk, StreamChunk)
        assert chunk.provider == Provider.ANTHROPIC
        chunks.append(chunk)
        if chunk.delta_content:
            deltas.append(chunk.delta_content)

    assert "".join(deltas) == "Hello from Claude 3.5!"
    # Verify final chunk contains usage and finish reason
    finish_chunk = chunks[-1]
    assert finish_chunk.finish_reason == "end_turn"
    assert finish_chunk.usage is not None
    assert finish_chunk.usage["prompt_tokens"] == 100
    assert finish_chunk.usage["completion_tokens"] == 16


@pytest.mark.asyncio
async def test_anthropic_adapter_error_normalization_401():
    """Verify Anthropic 401 unauthorized converts to ProviderAuthenticationError."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401,
            json={
                "type": "error",
                "error": {
                    "type": "authentication_error",
                    "message": "invalid x-api-key provided",
                },
            },
        )

    mock_transport = httpx.MockTransport(handler)
    adapter = AnthropicProviderAdapter(api_key="sk-ant-invalid", transport=mock_transport)

    req = ChatCompletionRequest(
        messages=[MessageSchema(role="user", content="Hi")]
    )

    with pytest.raises(ProviderAuthenticationError) as exc_info:
        await adapter.complete(req)

    assert exc_info.value.status_code == 401
    assert exc_info.value.provider == Provider.ANTHROPIC
    assert "Invalid or missing Anthropic API key" in str(exc_info.value)


@pytest.mark.asyncio
async def test_anthropic_adapter_error_normalization_429():
    """Verify Anthropic 429 rate limit converts to ProviderRateLimitError."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429,
            json={
                "type": "error",
                "error": {
                    "type": "rate_limit_error",
                    "message": "Number of request tokens has exceeded your rate limit (Tier 1)",
                },
            },
        )

    mock_transport = httpx.MockTransport(handler)
    adapter = AnthropicProviderAdapter(api_key="sk-ant-test", transport=mock_transport)

    req = ChatCompletionRequest(
        messages=[MessageSchema(role="user", content="Hi")]
    )

    with pytest.raises(ProviderRateLimitError) as exc_info:
        await adapter.complete(req)

    assert exc_info.value.status_code == 429
    assert exc_info.value.provider == Provider.ANTHROPIC
    assert "rate limit exceeded" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_anthropic_adapter_error_normalization_400_context_length():
    """Verify Anthropic 400 token limit converts to ContextLengthExceededError."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={
                "type": "error",
                "error": {
                    "type": "invalid_request_error",
                    "message": "prompt is too long: 250000 tokens exceeds 200000 maximum context length",
                },
            },
        )

    mock_transport = httpx.MockTransport(handler)
    adapter = AnthropicProviderAdapter(api_key="sk-ant-test", transport=mock_transport)

    req = ChatCompletionRequest(
        messages=[MessageSchema(role="user", content="Huge context")]
    )

    with pytest.raises(ContextLengthExceededError) as exc_info:
        await adapter.complete(req)

    assert exc_info.value.status_code == 400
    assert exc_info.value.provider == Provider.ANTHROPIC
    assert "context length" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_anthropic_adapter_availability_and_health_check():
    """Verify is_available, unconfigured key guard, and health_check."""
    unconfigured = AnthropicProviderAdapter(api_key="")
    assert unconfigured.is_available() is False

    req = ChatCompletionRequest(messages=[MessageSchema(role="user", content="Hi")])
    with pytest.raises(ProviderAuthenticationError):
        await unconfigured.complete(req)

    configured = AnthropicProviderAdapter(api_key="sk-ant-valid-key")
    assert configured.is_available() is True

    health = await configured.health_check()
    assert health["provider"] == "anthropic"
    assert health["category"] == "closed_proprietary"
    assert health["configured"] is True
    assert health["default_model"] == "claude-3-5-sonnet"


@pytest.mark.asyncio
async def test_anthropic_adapter_legacy_complete():
    """Verify complete_legacy for backward compatibility with ModelAdapter."""
    def handler(request: httpx.Request) -> httpx.Response:
        response_body = {
            "id": "msg_legacy_test",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": "Legacy output"}],
            "model": "claude-3-5-sonnet",
            "usage": {"input_tokens": 100, "output_tokens": 50},
        }
        return httpx.Response(200, json=response_body)

    mock_transport = httpx.MockTransport(handler)
    adapter = AnthropicProviderAdapter(api_key="sk-ant-test", transport=mock_transport)

    legacy_req = CompletionRequestSchema(
        messages=[MessageSchema(role="user", content="Legacy ping")],
        temperature=0.2,
        max_tokens=1000,
    )

    resp = await adapter.complete_legacy(legacy_req)
    assert isinstance(resp, CompletionResponseSchema)
    assert resp.content == "Legacy output"
    assert resp.provider == Provider.ANTHROPIC
    assert resp.usage["prompt_tokens"] == 100
    assert resp.usage["completion_tokens"] == 50
