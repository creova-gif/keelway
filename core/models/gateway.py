"""
Kora AI Model Gateway & Policy Router.
"""

from typing import Dict, List, Optional
import logging

from core.api.schemas import CompletionRequestSchema, CompletionResponseSchema, Provider, MessageSchema
from core.models.adapters.base import ModelAdapter
from core.models.adapters.anthropic import AnthropicAdapter
from core.models.adapters.local import LocalAdapter
from core.models.adapters.gemini import GeminiAdapter
from core.models.adapters.openai import OpenAIAdapter
from core.security.firewall import SecurityGateway
from core.security.airgap import AirGapEnforcer
from core.security.style import StyleEngine, VoiceStyle

logger = logging.getLogger(__name__)


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

    def resolve_provider_order(self, request: CompletionRequestSchema) -> List[Provider]:
        """Determine provider evaluation order based on request hints and capability requirements."""
        order: List[Provider] = []

        if request.preferred_provider and request.preferred_provider in self.adapters:
            order.append(request.preferred_provider)

        # If privacy_level is 'private', evaluate local model first
        if request.privacy_level == "private" and Provider.LOCAL not in order:
            order.insert(0, Provider.LOCAL)

        # Add remaining available adapters in prioritized sequence
        default_priority = [Provider.ANTHROPIC, Provider.GOOGLE, Provider.OPENAI, Provider.LOCAL]
        for prov in default_priority:
            if prov not in order and prov in self.adapters:
                order.append(prov)

        return order

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
        provider_order = self.resolve_provider_order(sanitized_request)
        last_error: Optional[Exception] = None

        for provider in provider_order:
            # Enforce Air-Gap Zero-Egress restriction if enabled
            if self.air_gap.enabled and provider != Provider.LOCAL:
                logger.warning(f"Air-Gap Mode Active: Dropping outbound request to {provider.value}")
                continue

            adapter = self.adapters.get(provider)
            if not adapter or not adapter.is_available():
                continue

            try:
                logger.info(f"Routing request to provider: {provider.value}")
                response = await adapter.complete(sanitized_request)
                # De-slop output text
                clean_content, slop_found = StyleEngine.de_slop(response.content)
                if slop_found:
                    logger.info(f"StyleEngine pruned {len(slop_found)} AI slop tokens from output")
                return response.model_copy(update={"content": clean_content})
            except Exception as e:
                logger.warning(f"Provider {provider.value} failed: {e}. Attempting fallback...")
                last_error = e

        raise RuntimeError(f"All model providers failed or unavailable. Last error: {last_error}")


gateway = ModelGateway()
