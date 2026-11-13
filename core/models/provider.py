"""
Keelway Unified Model Provider Interface & Normalization Abstraction.

Defines the core contract for all inference providers (Open-Weight local/self-hosted runtimes
and Closed commercial API providers). Provides normalized request/response formats,
streaming chunk generators, token usage tracking, and typed error hierarchies.
"""

from __future__ import annotations

import time
import uuid
from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Dict, List, Optional
from pydantic import BaseModel, Field, model_validator

from core.api.schemas import Provider, MessageSchema
from core.models.registry import ModelCategory


class ProviderError(Exception):
    """Base class for all normalized model provider errors."""
    def __init__(self, message: str, provider: Provider, status_code: Optional[int] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.provider = provider
        self.status_code = status_code
        self.details = details or {}


class ProviderAuthenticationError(ProviderError):
    """Raised when provider credentials (API key) are invalid or missing."""
    pass


class ProviderRateLimitError(ProviderError):
    """Raised when provider rate limits or quotas are exceeded."""
    pass


class ModelNotFoundError(ProviderError):
    """Raised when requested model is not found or not installed."""
    pass


class ContextLengthExceededError(ProviderError):
    """Raised when input tokens exceed model context limit."""
    pass


class ProviderTimeoutError(ProviderError):
    """Raised when inference times out."""
    pass


class ChatCompletionRequest(BaseModel):
    """Normalized unified request for inference."""
    messages: List[MessageSchema] = Field(..., min_length=1, description="List of role/content messages")
    model: Optional[str] = Field(default=None, description="Explicit model tag (e.g. 'qwen2.5-coder:7b' or 'gpt-4o')")
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, ge=1, le=128000)
    max_completion_tokens: Optional[int] = Field(default=None, ge=1, le=128000, description="OpenAI GPT-5/o-series alias for max_tokens")
    response_format: Optional[Dict[str, Any]] = Field(default=None, description="OpenAI response_format, e.g. {'type': 'json_object'}")
    stream: bool = Field(default=False, description="Whether to stream completion via SSE")
    tools: Optional[List[Dict[str, Any]]] = Field(default=None, description="Optional tool/function definitions")
    preferred_provider: Optional[Provider] = Field(default=None, description="Specific provider preference")
    category_preference: Optional[ModelCategory] = Field(default=None, description="open_weight or closed_proprietary")
    privacy_level: str = Field(default="standard", description="'standard' | 'sensitive' | 'private' (private enforces zero external egress)")
    required_capabilities: List[str] = Field(default_factory=list, description="Capabilities like 'code', 'vision', 'reasoning'")
    max_cost_usd: Optional[float] = Field(default=None, description="Budget cap in USD")
    max_latency_ms: Optional[int] = Field(default=None, description="Maximum acceptable latency")

    @model_validator(mode="after")
    def _sync_completion_token_alias(self) -> "ChatCompletionRequest":
        if self.max_completion_tokens is not None and "max_tokens" not in self.model_fields_set:
            self.max_tokens = self.max_completion_tokens
        return self


class StreamChunk(BaseModel):
    """Normalized streaming token event."""
    id: str = Field(default_factory=lambda: f"chatcmpl-{uuid.uuid4().hex[:12]}")
    object: str = "chat.completion.chunk"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str
    provider: Provider
    delta_content: str = ""
    finish_reason: Optional[str] = None
    usage: Optional[Dict[str, int]] = None

    def to_sse(self) -> str:
        """Format as standard Server-Sent Event string."""
        import json
        payload = {
            "id": self.id,
            "object": self.object,
            "created": self.created,
            "model": self.model,
            "choices": [
                {
                    "index": 0,
                    "delta": {"content": self.delta_content} if self.delta_content else {},
                    "finish_reason": self.finish_reason,
                }
            ],
        }
        if self.usage:
            payload["usage"] = self.usage
        return f"data: {json.dumps(payload)}\n\n"


class ChatCompletionResponse(BaseModel):
    """Normalized non-streaming completion response."""
    id: str = Field(default_factory=lambda: f"chatcmpl-{uuid.uuid4().hex[:12]}")
    object: str = "chat.completion"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str
    provider: Provider
    category: ModelCategory
    content: str
    finish_reason: str = "stop"
    usage: Dict[str, int] = Field(..., description="prompt_tokens, completion_tokens, total_tokens")
    latency_ms: float
    cost_usd: float = 0.0
    routing_reason: str = ""
    tool_calls: Optional[List[Dict[str, Any]]] = None

    def to_openai_dict(self) -> Dict[str, Any]:
        """Convert to standard OpenAI Chat Completions API response format."""
        return {
            "id": self.id,
            "object": self.object,
            "created": self.created,
            "model": self.model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": self.content,
                        "tool_calls": self.tool_calls,
                    },
                    "finish_reason": self.finish_reason,
                }
            ],
            "usage": self.usage,
            "keelway_metadata": {
                "provider": self.provider.value,
                "category": self.category.value,
                "latency_ms": self.latency_ms,
                "cost_usd": self.cost_usd,
                "routing_reason": self.routing_reason,
            },
        }


class BaseModelProvider(ABC):
    """Abstract interface implemented by all Keelway model provider adapters."""

    provider_id: Provider
    category: ModelCategory

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if credentials or endpoints are currently active and reachable."""
        pass

    @abstractmethod
    async def complete(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        """Execute a non-streaming completion request."""
        pass

    @abstractmethod
    async def stream_complete(self, request: ChatCompletionRequest) -> AsyncIterator[StreamChunk]:
        """Stream generation tokens as an asynchronous generator of StreamChunks."""
        pass

    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Verify provider health, latency, and reachable models."""
        pass
