"""
Keelway Model Gateway & Hybrid Policy Router.

Coordinates unified inference across Open-Weight (local/self-hosted runtimes)
and Closed commercial providers (OpenAI, Anthropic, Google Gemini).
Enforces security guardrails, deterministic privacy containment, air-gap zero-egress,
automated failover, explainable routing, and cost accounting.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple

from core.api.schemas import CompletionRequestSchema, CompletionResponseSchema, Provider, MessageSchema
from core.models.adapters.base import ModelAdapter
from core.models.adapters.anthropic import AnthropicAdapter
from core.models.adapters.local import LocalAdapter
from core.models.adapters.gemini import GeminiAdapter
from core.models.adapters.openai import OpenAIAdapter
from core.models.adapters.open_weight import OpenWeightProviderAdapter
from core.models.adapters.openai_provider import OpenAIProviderAdapter
from core.models.adapters.anthropic_provider import AnthropicProviderAdapter
from core.models.adapters.gemini_provider import GeminiProviderAdapter
from core.models.registry import model_registry, ModelCategory
from core.models.provider import (
    BaseModelProvider,
    ChatCompletionRequest,
    ChatCompletionResponse,
    StreamChunk,
    ProviderError,
    ProviderAuthenticationError,
    ModelNotFoundError,
)
from core.security.firewall import SecurityGateway
from core.security.airgap import AirGapEnforcer
from core.security.style import StyleEngine
from core.models.cost_ledger import cost_ledger

logger = logging.getLogger(__name__)

# USD per million tokens (input, output)
PRICE_PER_MTOK: Dict[Provider, Tuple[float, float]] = {
    Provider.ANTHROPIC: (3.0, 15.0),
    Provider.OPENAI: (2.50, 10.0),
    Provider.GOOGLE: (0.075, 0.30),
    Provider.GEMINI: (0.075, 0.30),
    Provider.LOCAL: (0.0, 0.0),
}
FRONTIER_CAPABILITIES = {"complex_reasoning", "long_context", "vision"}


class ModelGateway:
    """Multi-provider model gateway with policy-based routing, automated failover,
    air-gap zero-egress, and style de-slopping."""

    def __init__(
        self,
        adapters: Optional[Dict[Provider, ModelAdapter]] = None,
        security_gateway: Optional[SecurityGateway] = None,
        air_gap_enforcer: Optional[AirGapEnforcer] = None,
    ):
        if adapters is not None:
            self.adapters = adapters
        else:
            self.adapters = {
                Provider.ANTHROPIC: AnthropicProviderAdapter(),
                Provider.GOOGLE: GeminiProviderAdapter(),
                Provider.GEMINI: GeminiProviderAdapter(),
                Provider.OPENAI: OpenAIProviderAdapter(),
                Provider.LOCAL: OpenWeightProviderAdapter(),
            }
        self.security = security_gateway or SecurityGateway(block_on_injection=True, redact_secrets=True)
        self.air_gap = air_gap_enforcer or AirGapEnforcer(enabled=False)

    def register_adapter(self, provider: Provider, adapter: ModelAdapter) -> None:
        self.adapters[provider] = adapter

    def estimate_cost_usd(self, provider: Provider, request: Any) -> float:
        """Upper-bound cost: one token per prompt byte plus the full max_tokens budget; unpriced cloud providers cost inf."""
        unpriced = (0.0, 0.0) if provider == Provider.LOCAL else (float("inf"), float("inf"))
        price_in, price_out = PRICE_PER_MTOK.get(provider, unpriced)
        prompt_tokens = sum(len(m.content.encode("utf-8")) for m in request.messages)
        return (prompt_tokens * price_in + request.max_tokens * price_out) / 1_000_000

    def explain_route(self, request: Any) -> Tuple[List[Provider], str]:
        """Local-first cost arbitrage: $0 local models by default, the cheapest in-budget cloud model only when needed.
        Respects explicit model IDs, category preference, capabilities, and privacy containment."""
        req_model = getattr(request, "model", None)
        category_pref = getattr(request, "category_preference", None)

        # Check if an explicit model was requested
        explicit_provider: Optional[Provider] = None
        if req_model:
            meta = model_registry.get(req_model)
            if meta:
                explicit_provider = meta.provider
            else:
                norm_model = req_model.lower().removeprefix("models/")
                if norm_model.startswith(("gemini-", "gemma-4-")):
                    explicit_provider = Provider.GEMINI
                elif norm_model.startswith("claude-"):
                    explicit_provider = Provider.ANTHROPIC
                elif norm_model.startswith(("gpt-", "o1", "o3", "o4")):
                    explicit_provider = Provider.OPENAI
                elif norm_model.startswith(("keelway-", "qwen", "llama", "mistral", "deepseek")):
                    explicit_provider = Provider.LOCAL

        needs_frontier = sorted(set(request.required_capabilities) & FRONTIER_CAPABILITIES)
        cloud = [p for p in self.adapters if p != Provider.LOCAL]

        # Category preference filter
        if category_pref == ModelCategory.OPEN_WEIGHT:
            cloud = []
        elif category_pref == ModelCategory.CLOSED_PROPRIETARY:
            local = []

        if request.max_cost_usd is not None and cloud:
            cloud = [p for p in cloud if self.estimate_cost_usd(p, request) <= request.max_cost_usd]
        cloud.sort(key=lambda p: self.estimate_cost_usd(p, request))
        local = [Provider.LOCAL] if Provider.LOCAL in self.adapters and category_pref != ModelCategory.CLOSED_PROPRIETARY else []

        # Privacy invariant: private requests NEVER egress to cloud
        if request.privacy_level == "private":
            if explicit_provider and explicit_provider != Provider.LOCAL:
                return [], "private: requested cloud provider rejected by privacy policy (zero-egress)"
            return local, "private: local models only, nothing leaves this machine"

        if needs_frontier:
            order, reason = cloud + local, f"escalated to cloud for {', '.join(needs_frontier)}"
        else:
            order, reason = local + cloud, "local-first: $0.00 inference"

        # Explicit model preference or requested provider preference
        pref = explicit_provider or request.preferred_provider
        if pref in order:
            order.remove(pref)
            order.insert(0, pref)
            reason = f"preferred {pref.value}" + (f" ({req_model})" if req_model else "")
        elif pref and pref not in order and request.privacy_level != "private" and pref in self.adapters:
            order.insert(0, pref)
            reason = f"explicit {pref.value} ({req_model})"

        return order, reason

    def resolve_provider_order(self, request: Any) -> List[Provider]:
        return self.explain_route(request)[0]

    async def _provider_ready(self, provider: Provider, adapter: Any, request: Any) -> bool:
        """Return True if adapter is ready or if request targets an in-process Keelway OpenCore model."""
        if not adapter:
            return False
        req_model = getattr(request, "model", None) or ""
        if provider == Provider.LOCAL and isinstance(adapter, OpenWeightProviderAdapter) and req_model.startswith("keelway-"):
            return True
        return await asyncio.to_thread(adapter.is_available)

    async def complete(self, request: CompletionRequestSchema) -> CompletionResponseSchema:
        """Execute request with automated failover across available providers after security sanitization."""
        # Security Guardrail Inspection & Sanitization
        sanitized_messages: List[MessageSchema] = []
        for msg in request.messages:
            sec_res = self.security.inspect_and_sanitize(msg.content)
            if not sec_res.is_safe:
                logger.error(f"Request blocked by Security Gateway: {sec_res.blocked_reason}")
                raise ValueError(f"Security Gateway Violation: {sec_res.blocked_reason}")
            sanitized_messages.append(MessageSchema(role=msg.role, content=sec_res.sanitized_text))

        sanitized_request = request.model_copy(update={"messages": sanitized_messages})
        provider_order, reason = self.explain_route(sanitized_request)
        last_error: Optional[Exception] = None

        for provider in provider_order:
            # Enforce Air-Gap Zero-Egress restriction if enabled
            if self.air_gap.enabled and provider != Provider.LOCAL:
                logger.warning(f"Air-Gap Mode Active: Dropping outbound request to {provider.value}")
                continue

            adapter = self.adapters.get(provider)
            if not await self._provider_ready(provider, adapter, sanitized_request):
                continue

            try:
                logger.info(f"Routing request to provider: {provider.value}")
                response = await adapter.complete(sanitized_request)

                # De-slop output text
                clean_content, slop_found = StyleEngine.de_slop(response.content)
                if slop_found:
                    logger.info(f"StyleEngine pruned {len(slop_found)} AI slop tokens from output")
                if provider != provider_order[0]:
                    reason = f"{reason}; fell back to {provider.value}"

                try:
                    cost_ledger.record_completion(
                        provider=provider,
                        model=response.model,
                        usage=response.usage,
                        latency_ms=response.latency_ms,
                        cost_usd=response.cost_usd,
                        routing_reason=reason,
                    )
                except Exception as rec_err:
                    logger.warning(f"Failed to record in cost ledger: {rec_err}")

                return response.model_copy(update={"content": clean_content, "routing_reason": reason})
            except Exception as e:
                logger.warning(f"Provider {provider.value} failed: {e}. Attempting fallback...")
                last_error = e

        if not provider_order:
            raise RuntimeError("No model provider allowed for this request.")
        if last_error is not None:
            logger.warning("All model providers failed or unavailable. Last error: %s", last_error)
        raise RuntimeError("All model providers failed or unavailable.")

    async def chat_complete(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        """Unified chat completion supporting open-weight & closed providers."""
        # Sanitize messages
        sanitized_messages: List[MessageSchema] = []
        for msg in request.messages:
            sec_res = self.security.inspect_and_sanitize(msg.content)
            if not sec_res.is_safe:
                raise ValueError(f"Security Gateway Violation: {sec_res.blocked_reason}")
            sanitized_messages.append(MessageSchema(role=msg.role, content=sec_res.sanitized_text))

        sanitized_request = request.model_copy(update={"messages": sanitized_messages})
        provider_order, reason = self.explain_route(sanitized_request)
        last_error: Optional[Exception] = None

        for provider in provider_order:
            if self.air_gap.enabled and provider != Provider.LOCAL:
                logger.warning(f"Air-Gap Mode Active: Dropping outbound request to {provider.value}")
                continue

            adapter = self.adapters.get(provider)
            if not await self._provider_ready(provider, adapter, sanitized_request):
                continue

            try:
                if hasattr(adapter, "complete") and isinstance(adapter, BaseModelProvider):
                    resp = await adapter.complete(sanitized_request)
                else:
                    # Fallback for adapters only implementing legacy complete
                    legacy_req = CompletionRequestSchema(
                        messages=sanitized_request.messages,
                        temperature=sanitized_request.temperature,
                        max_tokens=sanitized_request.max_tokens,
                    )
                    leg_resp = await adapter.complete(legacy_req)
                    cat = ModelCategory.OPEN_WEIGHT if provider == Provider.LOCAL else ModelCategory.CLOSED_PROPRIETARY
                    resp = ChatCompletionResponse(
                        model=leg_resp.model,
                        provider=provider,
                        category=cat,
                        content=leg_resp.content,
                        usage=leg_resp.usage,
                        latency_ms=leg_resp.latency_ms,
                        cost_usd=leg_resp.cost_usd or 0.0,
                        routing_reason=reason,
                    )

                clean_content, _ = StyleEngine.de_slop(resp.content)
                if provider != provider_order[0]:
                    reason = f"{reason}; fell back to {provider.value}"

                try:
                    cost_ledger.record_completion(
                        provider=provider,
                        model=resp.model,
                        usage=resp.usage,
                        latency_ms=resp.latency_ms,
                        cost_usd=resp.cost_usd,
                        routing_reason=reason,
                    )
                except Exception as rec_err:
                    logger.warning(f"Failed to record in cost ledger: {rec_err}")

                return resp.model_copy(update={"content": clean_content, "routing_reason": reason})
            except Exception as e:
                logger.warning(f"Provider {provider.value} failed: {e}. Attempting fallback...")
                last_error = e

        if not provider_order:
            raise RuntimeError("No model provider allowed for this request.")
        if last_error is not None:
            logger.warning("All model providers failed or unavailable. Last error: %s", last_error)
        raise RuntimeError("All model providers failed or unavailable.")

    async def stream_chat(self, request: ChatCompletionRequest) -> AsyncIterator[StreamChunk]:
        """Unified streaming chat completion yielding SSE chunks."""
        # Sanitize messages
        sanitized_messages: List[MessageSchema] = []
        for msg in request.messages:
            sec_res = self.security.inspect_and_sanitize(msg.content)
            if not sec_res.is_safe:
                raise ValueError(f"Security Gateway Violation: {sec_res.blocked_reason}")
            sanitized_messages.append(MessageSchema(role=msg.role, content=sec_res.sanitized_text))

        sanitized_request = request.model_copy(update={"messages": sanitized_messages})
        provider_order, reason = self.explain_route(sanitized_request)

        selected_provider: Optional[Provider] = None
        selected_adapter: Optional[Any] = None

        for provider in provider_order:
            if self.air_gap.enabled and provider != Provider.LOCAL:
                continue
            adapter = self.adapters.get(provider)
            if await self._provider_ready(provider, adapter, sanitized_request):
                selected_provider = provider
                selected_adapter = adapter
                break

        if not selected_adapter:
            raise RuntimeError("No available model provider reachable for streaming.")

        if hasattr(selected_adapter, "stream_complete"):
            async for chunk in selected_adapter.stream_complete(sanitized_request):
                yield chunk
        else:
            # Emulate streaming chunk if provider lacks native streaming
            resp = await selected_adapter.complete(sanitized_request)
            yield StreamChunk(
                model=resp.model,
                provider=selected_provider,
                delta_content=resp.content,
                finish_reason="stop",
                usage=resp.usage,
            )


gateway = ModelGateway()
