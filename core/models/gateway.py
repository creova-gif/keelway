"""
Kora AI Model Gateway & Policy Router.
"""

from typing import Dict, List, Optional
import logging

from core.api.schemas import CompletionRequestSchema, CompletionResponseSchema, Provider
from core.models.adapters.base import ModelAdapter
from core.models.adapters.anthropic import AnthropicAdapter
from core.models.adapters.local import LocalAdapter
from core.models.adapters.gemini import GeminiAdapter
from core.models.adapters.openai import OpenAIAdapter

logger = logging.getLogger(__name__)


class ModelGateway:
    """Multi-provider model gateway with policy-based routing and automated failover."""

    def __init__(self, adapters: Optional[Dict[Provider, ModelAdapter]] = None):
        if adapters is not None:
            self.adapters = adapters
        else:
            self.adapters = {
                Provider.ANTHROPIC: AnthropicAdapter(),
                Provider.GOOGLE: GeminiAdapter(),
                Provider.OPENAI: OpenAIAdapter(),
                Provider.LOCAL: LocalAdapter(),
            }

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
        """Execute request with automated failover across available providers."""
        provider_order = self.resolve_provider_order(request)
        last_error: Optional[Exception] = None

        for provider in provider_order:
            adapter = self.adapters.get(provider)
            if not adapter or not adapter.is_available():
                continue

            try:
                logger.info(f"Routing request to provider: {provider.value}")
                response = await adapter.complete(request)
                return response
            except Exception as e:
                logger.warning(f"Provider {provider.value} failed: {e}. Attempting fallback...")
                last_error = e

        raise RuntimeError(f"All model providers failed or unavailable. Last error: {last_error}")


gateway = ModelGateway()
