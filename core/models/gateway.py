"""
Keelway Model Gateway & Policy Router.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Tuple

from core.api.schemas import CompletionRequestSchema, CompletionResponseSchema, Provider, MessageSchema
from core.models.adapters.base import ModelAdapter
from core.models.adapters.anthropic import AnthropicAdapter
from core.models.adapters.local import LocalAdapter
from core.models.adapters.gemini import GeminiAdapter
from core.models.adapters.openai import OpenAIAdapter
from core.security.firewall import SecurityGateway
from core.security.airgap import AirGapEnforcer
from core.security.style import StyleEngine, VoiceStyle
from core.models.cost_ledger import cost_ledger

logger = logging.getLogger(__name__)

# USD per million tokens (input, output), matching what each adapter bills.
PRICE_PER_MTOK: Dict[Provider, Tuple[float, float]] = {
    Provider.ANTHROPIC: (3.0, 15.0),
    Provider.OPENAI: (2.50, 10.0),
    Provider.GOOGLE: (0.075, 0.30),
    Provider.LOCAL: (0.0, 0.0),
}
# Capabilities that justify paying for a cloud frontier model instead of the local default.
FRONTIER_CAPABILITIES = {"complex_reasoning", "long_context", "vision"}


class ModelGateway:
    """Multi-provider model gateway with policy-based routing, automated failover, air-gap zero-egress, and style de-slopping."""

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
                Provider.ANTHROPIC: AnthropicAdapter(),
                Provider.GOOGLE: GeminiAdapter(),
                Provider.OPENAI: OpenAIAdapter(),
                Provider.LOCAL: LocalAdapter(),
            }
        self.security = security_gateway or SecurityGateway(block_on_injection=True, redact_secrets=True)
        self.air_gap = air_gap_enforcer or AirGapEnforcer(enabled=False)

    def register_adapter(self, provider: Provider, adapter: ModelAdapter) -> None:
        self.adapters[provider] = adapter

    def estimate_cost_usd(self, provider: Provider, request: CompletionRequestSchema) -> float:
        """Upper-bound cost: one token per prompt byte plus the full max_tokens budget; unpriced cloud providers cost inf."""
        unpriced = (0.0, 0.0) if provider == Provider.LOCAL else (float("inf"), float("inf"))
        price_in, price_out = PRICE_PER_MTOK.get(provider, unpriced)
        prompt_tokens = sum(len(m.content.encode("utf-8")) for m in request.messages)
        return (prompt_tokens * price_in + request.max_tokens * price_out) / 1_000_000

    def explain_route(self, request: CompletionRequestSchema) -> Tuple[List[Provider], str]:
        """Local-first cost arbitrage: $0 local models by default, the cheapest in-budget cloud model only when needed."""
        needs_frontier = sorted(set(request.required_capabilities) & FRONTIER_CAPABILITIES)
        cloud = [p for p in self.adapters if p != Provider.LOCAL]
        if request.max_cost_usd is not None:
            cloud = [p for p in cloud if self.estimate_cost_usd(p, request) <= request.max_cost_usd]
        cloud.sort(key=lambda p: self.estimate_cost_usd(p, request))
        local = [Provider.LOCAL] if Provider.LOCAL in self.adapters else []

        if request.privacy_level == "private":
            return local, "private: local models only, nothing leaves this machine"
        if needs_frontier:
            order, reason = cloud + local, f"escalated to cloud for {', '.join(needs_frontier)}"
        else:
            order, reason = local + cloud, "local-first: $0.00 inference"
        pref = request.preferred_provider
        if pref in order:
            order.remove(pref)
            order.insert(0, pref)
            reason = f"preferred {pref.value}"
        return order, reason

    def resolve_provider_order(self, request: CompletionRequestSchema) -> List[Provider]:
        return self.explain_route(request)[0]

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

        # Use request with sanitized messages
        sanitized_request = request.model_copy(update={"messages": sanitized_messages})
        provider_order, reason = self.explain_route(sanitized_request)
        last_error: Optional[Exception] = None

        for provider in provider_order:
            # Enforce Air-Gap Zero-Egress restriction if enabled
            if self.air_gap.enabled and provider != Provider.LOCAL:
                logger.warning(f"Air-Gap Mode Active: Dropping outbound request to {provider.value}")
                continue

            adapter = self.adapters.get(provider)
            # Off the event loop: the local adapter probes its server over HTTP.
            if not adapter or not await asyncio.to_thread(adapter.is_available):
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
            raise RuntimeError(f"No model provider allowed for this request ({reason}).")
        raise RuntimeError(f"All model providers failed or unavailable. Last error: {last_error}")


gateway = ModelGateway()
