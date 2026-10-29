"""
Base Model Adapter Interface for Kora AI Core.
"""

from abc import ABC, abstractmethod
from core.api.schemas import CompletionRequestSchema, CompletionResponseSchema, Provider


class ModelAdapter(ABC):
    """Abstract base class for all model provider adapters."""

    provider: Provider

    @abstractmethod
    async def complete(self, request: CompletionRequestSchema) -> CompletionResponseSchema:
        """Execute a completion request against the provider."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Verify whether this adapter has valid credentials/endpoint configured."""
        pass
