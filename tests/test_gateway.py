"""
Unit tests for the Model Gateway and policy routing.
"""

import pytest
from unittest.mock import AsyncMock

from core.api.schemas import (
    CompletionRequestSchema,
    CompletionResponseSchema,
    MessageSchema,
    Provider,
)
from core.models.gateway import ModelGateway
from core.models.adapters.base import ModelAdapter


class MockAdapter(ModelAdapter):
    def __init__(self, provider: Provider, available: bool = True, should_fail: bool = False):
        self.provider = provider
        self.available = available
        self.should_fail = should_fail
        self.call_count = 0

    def is_available(self) -> bool:
        return self.available

    async def complete(self, request: CompletionRequestSchema) -> CompletionResponseSchema:
        self.call_count += 1
        if self.should_fail:
            raise RuntimeError(f"Simulated failure on provider {self.provider.value}")
        return CompletionResponseSchema(
            content=f"Response from {self.provider.value}",
            provider=self.provider,
            model="mock-model",
            usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
            latency_ms=45.0,
            cost_usd=0.001,
        )


def test_provider_order_resolution_defaults():
    gateway = ModelGateway()
    request = CompletionRequestSchema(messages=[MessageSchema(role="user", content="Hello")])
    order = gateway.resolve_provider_order(request)
    # Default fallbacks
    assert Provider.ANTHROPIC in order
    assert Provider.LOCAL in order


def test_provider_order_resolution_privacy_override():
    gateway = ModelGateway()
    request = CompletionRequestSchema(
        messages=[MessageSchema(role="user", content="Secret data")],
        privacy_level="private",
    )
    order = gateway.resolve_provider_order(request)
    # When private, local model must be evaluated first
    assert order[0] == Provider.LOCAL


@pytest.mark.asyncio
async def test_gateway_automated_fallback():
    failing_anthropic = MockAdapter(provider=Provider.ANTHROPIC, should_fail=True)
    healthy_local = MockAdapter(provider=Provider.LOCAL, should_fail=False)

    gw = ModelGateway(adapters={
        Provider.ANTHROPIC: failing_anthropic,
        Provider.LOCAL: healthy_local,
    })

    request = CompletionRequestSchema(
        messages=[MessageSchema(role="user", content="Test prompt")],
        preferred_provider=Provider.ANTHROPIC,
    )

    response = await gw.complete(request)

    # Primary failed, fallback succeeded
    assert failing_anthropic.call_count == 1
    assert healthy_local.call_count == 1
    assert response.provider == Provider.LOCAL
    assert "Response from local" in response.content
