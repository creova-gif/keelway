"""
Tests for native Google Gemini Provider Adapter (GeminiProviderAdapter).

Validates non-streaming generation, SSE streaming token parsing, cost attribution
across Gemini model rate cards, request/message payload transformation,
and error normalization to typed Keelway ProviderError subclasses via httpx.MockTransport.
"""

import json
import httpx
import pytest

from core.api.schemas import MessageSchema, Provider
from core.models.registry import ModelCategory
from core.models.provider import (
    ChatCompletionRequest,
    ProviderAuthenticationError,
    ProviderRateLimitError,
    ContextLengthExceededError,
)
from core.models.adapters.gemini_provider import GeminiProviderAdapter


@pytest.mark.asyncio
async def test_gemini_adapter_complete_success():
    """Verify non-streaming completion, URL formatting, message conversion, usage, and cost calculation."""
    recorded_requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        recorded_requests.append(request)
        response_body = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": "Hello from Gemini 2.5 Flash!"}
                        ],
                        "role": "model",
                    },
                    "finishReason": "STOP",
                    "index": 0,
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 1000,
                "candidatesTokenCount": 200,
                "totalTokenCount": 1200,
            },
            "modelVersion": "gemini-2.5-flash",
        }
        return httpx.Response(200, json=response_body)

    mock_transport = httpx.MockTransport(handler)
    adapter = GeminiProviderAdapter(api_key="test-gemini-key", transport=mock_transport)

    assert adapter.is_available() is True
    assert adapter.provider_id == Provider.GEMINI
    assert adapter.category == ModelCategory.CLOSED_PROPRIETARY
    assert adapter.default_model == "gemini-2.5-flash"

    req = ChatCompletionRequest(
        model="gemini-2.5-flash",
        messages=[
            MessageSchema(role="system", content="You are a helpful coding assistant."),
            MessageSchema(role="user", content="Hello Gemini"),
            MessageSchema(role="assistant", content="Hi! How can I help?"),
            MessageSchema(role="user", content="Tell me a joke"),
        ],
        temperature=0.7,
        max_tokens=2048,
    )

    resp = await adapter.complete(req)

    # Verify response mapping
    assert resp.content == "Hello from Gemini 2.5 Flash!"
    assert resp.finish_reason == "stop"
    assert resp.provider == Provider.GEMINI
    assert resp.category == ModelCategory.CLOSED_PROPRIETARY
    assert resp.usage["prompt_tokens"] == 1000
    assert resp.usage["completion_tokens"] == 200
    assert resp.usage["total_tokens"] == 1200

    # Pricing for gemini-2.5-flash: $0.075 / 1M prompt + $0.30 / 1M completion
    # (1000 * 0.075 / 1M) + (200 * 0.30 / 1M) = 0.000075 + 0.000060 = 0.000135
    assert resp.cost_usd == pytest.approx(0.000135, rel=1e-3)
    assert resp.latency_ms >= 0.0

    # Verify HTTP request details (API key sent via x-goog-api-key header, never in URL query string)
    assert len(recorded_requests) == 1
    sent_req = recorded_requests[0]
    assert sent_req.method == "POST"
    assert "models/gemini-2.5-flash:generateContent" in str(sent_req.url)
    assert "key=" not in str(sent_req.url)
    assert sent_req.headers.get("x-goog-api-key") == "test-gemini-key"

    req_body = json.loads(sent_req.content.decode("utf-8"))
    assert req_body["systemInstruction"] == {"parts": [{"text": "You are a helpful coding assistant."}]}
    assert len(req_body["contents"]) == 3
    assert req_body["contents"][0] == {"role": "user", "parts": [{"text": "Hello Gemini"}]}
    assert req_body["contents"][1] == {"role": "model", "parts": [{"text": "Hi! How can I help?"}]}
    assert req_body["contents"][2] == {"role": "user", "parts": [{"text": "Tell me a joke"}]}
    assert req_body["generationConfig"]["temperature"] == 0.7
    assert req_body["generationConfig"]["maxOutputTokens"] == 2048


@pytest.mark.asyncio
async def test_gemini_adapter_pricing_rate_card():
    """Verify dollar cost computation across all specified Gemini model tiers."""
    def make_handler(model_version: str):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={
                "candidates": [{"content": {"parts": [{"text": "ack"}]}, "finishReason": "STOP"}],
                "usageMetadata": {
                    "promptTokenCount": 1_000_000,
                    "candidatesTokenCount": 1_000_000,
                    "totalTokenCount": 2_000_000,
                },
                "modelVersion": model_version,
            })
        return handler

    test_cases = [
        ("gemini-2.5-flash", 0.075 + 0.30),
        ("gemini-2.5-pro", 1.25 + 5.00),
        ("gemini-1.5-flash", 0.075 + 0.30),
        ("gemini-1.5-pro", 1.25 + 5.00),
    ]

    for model_name, expected_cost in test_cases:
        mock_transport = httpx.MockTransport(make_handler(model_name))
        adapter = GeminiProviderAdapter(api_key="test-key", transport=mock_transport)
        req = ChatCompletionRequest(
            model=model_name,
            messages=[MessageSchema(role="user", content="test")],
        )
        resp = await adapter.complete(req)
        assert resp.cost_usd == pytest.approx(expected_cost, rel=1e-3), f"Failed for {model_name}"


@pytest.mark.asyncio
async def test_gemini_adapter_streaming_sse():
    """Verify Gemini SSE stream parsing into StreamChunks with deltas and usage."""
    recorded_requests = []
    sse_payload = (
        b'data: {"candidates":[{"content":{"parts":[{"text":"Gemini"}]},"finishReason":null}]}\n\n'
        b'data: {"candidates":[{"content":{"parts":[{"text":" is"}]},"finishReason":null}]}\n\n'
        b'data: {"candidates":[{"content":{"parts":[{"text":" streaming!"}]},"finishReason":"STOP"}],'
        b'"usageMetadata":{"promptTokenCount":25,"candidatesTokenCount":5,"totalTokenCount":30}}\n\n'
        b'data: [DONE]\n\n'
    )

    def handler(request: httpx.Request) -> httpx.Response:
        recorded_requests.append(request)
        return httpx.Response(200, content=sse_payload)

    mock_transport = httpx.MockTransport(handler)
    adapter = GeminiProviderAdapter(api_key="stream-key", transport=mock_transport)

    req = ChatCompletionRequest(
        model="gemini-2.5-flash",
        messages=[MessageSchema(role="user", content="Stream tokens please")],
        stream=True,
    )

    chunks = []
    async for chunk in adapter.stream_complete(req):
        chunks.append(chunk)

    # 3 content chunks + 1 stop chunk from [DONE]
    assert len(chunks) == 4
    deltas = [c.delta_content for c in chunks]
    assert "".join(deltas) == "Gemini is streaming!"

    assert chunks[2].finish_reason == "stop"
    assert chunks[2].usage == {
        "prompt_tokens": 25,
        "completion_tokens": 5,
        "total_tokens": 30,
    }

    # Verify stream URL formatting & header credential safety
    assert len(recorded_requests) == 1
    sent_url = str(recorded_requests[0].url)
    assert "streamGenerateContent" in sent_url
    assert "alt=sse" in sent_url
    assert "key=" not in sent_url
    assert recorded_requests[0].headers.get("x-goog-api-key") == "stream-key"


@pytest.mark.asyncio
async def test_gemini_adapter_auth_error_normalization():
    """Verify 403 or 400 with API_KEY_INVALID raises ProviderAuthenticationError."""
    # 403 Forbidden
    def auth_403_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"error": {"code": 403, "message": "Permission denied", "status": "PERMISSION_DENIED"}})

    adapter_403 = GeminiProviderAdapter(api_key="bad-key", transport=httpx.MockTransport(auth_403_handler))
    req = ChatCompletionRequest(messages=[MessageSchema(role="user", content="hi")])

    with pytest.raises(ProviderAuthenticationError) as exc_info:
        await adapter_403.complete(req)
    assert exc_info.value.status_code == 403
    assert exc_info.value.provider == Provider.GEMINI

    # 400 with API_KEY_INVALID
    def auth_invalid_key_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={
                "error": {
                    "code": 400,
                    "message": "API key not valid. Please pass a valid API key.",
                    "status": "INVALID_ARGUMENT",
                    "details": [{"reason": "API_KEY_INVALID"}],
                }
            },
        )

    adapter_invalid = GeminiProviderAdapter(api_key="invalid-key", transport=httpx.MockTransport(auth_invalid_key_handler))
    with pytest.raises(ProviderAuthenticationError) as exc_info_invalid:
        await adapter_invalid.complete(req)
    assert exc_info_invalid.value.status_code == 400
    assert "Invalid, unauthorized or missing Gemini API key" in str(exc_info_invalid.value)


@pytest.mark.asyncio
async def test_gemini_adapter_rate_limit_normalization():
    """Verify 429 or RESOURCE_EXHAUSTED raises ProviderRateLimitError."""
    def rate_limit_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429,
            json={
                "error": {
                    "code": 429,
                    "message": "Resource has been exhausted (e.g. check quota).",
                    "status": "RESOURCE_EXHAUSTED",
                }
            },
        )

    adapter = GeminiProviderAdapter(api_key="quota-key", transport=httpx.MockTransport(rate_limit_handler))
    req = ChatCompletionRequest(messages=[MessageSchema(role="user", content="hi")])

    with pytest.raises(ProviderRateLimitError) as exc_info:
        await adapter.complete(req)
    assert exc_info.value.status_code == 429
    assert exc_info.value.provider == Provider.GEMINI
    assert "rate limit or quota exceeded" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_gemini_adapter_context_overflow_normalization():
    """Verify 400 context overflow raises ContextLengthExceededError."""
    def context_overflow_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={
                "error": {
                    "code": 400,
                    "message": "The input token count exceeds the maximum context length of 1000000 tokens.",
                    "status": "INVALID_ARGUMENT",
                }
            },
        )

    adapter = GeminiProviderAdapter(api_key="valid-key", transport=httpx.MockTransport(context_overflow_handler))
    req = ChatCompletionRequest(messages=[MessageSchema(role="user", content="very long message")])

    with pytest.raises(ContextLengthExceededError) as exc_info:
        await adapter.complete(req)
    assert exc_info.value.status_code == 400
    assert exc_info.value.provider == Provider.GEMINI


@pytest.mark.asyncio
async def test_gemini_adapter_missing_key_and_health_check():
    """Verify behavior when API key is missing and verify health_check output."""
    adapter_no_key = GeminiProviderAdapter(api_key="")
    assert adapter_no_key.is_available() is False

    req = ChatCompletionRequest(messages=[MessageSchema(role="user", content="hi")])
    with pytest.raises(ProviderAuthenticationError) as exc_info:
        await adapter_no_key.complete(req)
    assert "API key is not configured" in str(exc_info.value)

    with pytest.raises(ProviderAuthenticationError):
        async for _ in adapter_no_key.stream_complete(req):
            pass

    adapter_with_key = GeminiProviderAdapter(api_key="configured-key")
    health = await adapter_with_key.health_check()
    assert health["provider"] == "gemini"
    assert health["category"] == "closed_proprietary"
    assert health["configured"] is True
    assert health["default_model"] == "gemini-2.5-flash"
