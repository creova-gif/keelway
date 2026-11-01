"""
Unit tests for the Model Gateway and policy routing.
"""

import sys

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


def _gw(*providers, **kw):
    return ModelGateway(adapters={p: MockAdapter(provider=p, **kw) for p in providers})


def _req(**kw):
    return CompletionRequestSchema(messages=[MessageSchema(role="user", content="Refactor this")], **kw)


ALL = (Provider.ANTHROPIC, Provider.OPENAI, Provider.GOOGLE, Provider.LOCAL)


def test_routes_local_first_at_zero_cost_by_default():
    order, reason = _gw(*ALL).explain_route(_req())
    assert order[0] == Provider.LOCAL
    assert "local-first" in reason


def test_escalates_to_cheapest_cloud_model_only_for_frontier_work():
    order, reason = _gw(*ALL).explain_route(_req(required_capabilities=["complex_reasoning"]))
    assert order == [Provider.GOOGLE, Provider.OPENAI, Provider.ANTHROPIC, Provider.LOCAL]
    assert "complex_reasoning" in reason


def test_budget_drops_cloud_models_that_could_exceed_it():
    order, _ = _gw(*ALL).explain_route(_req(required_capabilities=["vision"], max_tokens=1000, max_cost_usd=0.001))
    assert order == [Provider.GOOGLE, Provider.LOCAL]


def test_private_requests_never_leave_the_machine():
    order, _ = _gw(*ALL).explain_route(_req(privacy_level="private", preferred_provider=Provider.ANTHROPIC))
    assert order == [Provider.LOCAL]


@pytest.mark.asyncio
async def test_private_request_fails_closed_when_local_is_down():
    gw = _gw(Provider.ANTHROPIC, Provider.LOCAL)
    gw.adapters[Provider.LOCAL].should_fail = True
    with pytest.raises(RuntimeError):
        await gw.complete(_req(privacy_level="private"))
    assert gw.adapters[Provider.ANTHROPIC].call_count == 0


@pytest.mark.asyncio
async def test_response_explains_its_route_including_fallback():
    gw = _gw(Provider.ANTHROPIC, Provider.LOCAL)
    gw.adapters[Provider.LOCAL].should_fail = True
    res = await gw.complete(_req())
    assert res.provider == Provider.ANTHROPIC
    assert res.routing_reason == "local-first: $0.00 inference; fell back to anthropic"


def test_budget_counts_every_prompt_byte_so_emoji_cannot_sneak_past_it():
    gw = _gw(Provider.GOOGLE, Provider.LOCAL)
    req = CompletionRequestSchema(messages=[MessageSchema(role="user", content="🔥" * 1000)], max_tokens=1)
    assert gw.estimate_cost_usd(Provider.GOOGLE, req) >= 4000 * 0.075 / 1_000_000


def test_unpriced_cloud_provider_never_fits_a_budget(monkeypatch):
    g = sys.modules[ModelGateway.__module__]
    monkeypatch.setattr(g, "PRICE_PER_MTOK", {Provider.LOCAL: (0.0, 0.0)})
    order, _ = _gw(Provider.OPENAI, Provider.LOCAL).explain_route(_req(required_capabilities=["vision"], max_cost_usd=0.0))
    assert order == [Provider.LOCAL]
