"""
Keelway Proprietary Closed-Model Provider Adapter for OpenAI.

Provides production integration with OpenAI Commercial Chat Completions API.
Supports dynamic model selection (gpt-4o, gpt-4o-mini), non-streaming generation,
Server-Sent Events (SSE) token streaming, error classification, and accurate token billing.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, AsyncIterator, Dict, Optional
import httpx

from core.api.schemas import Provider, CompletionRequestSchema, CompletionResponseSchema
from core.config import settings
from core.models.registry import ModelCategory
from core.models.provider import (
    BaseModelProvider,
    ChatCompletionRequest,
    ChatCompletionResponse,
    StreamChunk,
    ProviderError,
    ProviderAuthenticationError,
    ProviderRateLimitError,
    ContextLengthExceededError,
    ProviderTimeoutError,
)
from core.models.adapters.base import ModelAdapter


# Standard OpenAI rate card per million tokens (input, output) in USD
OPENAI_RATES: Dict[str, tuple[float, float]] = {
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-2024-08-06": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o-mini-2024-07-18": (0.15, 0.60),
    "o1": (15.00, 60.00),
    "o1-mini": (3.00, 12.00),
    "o3-mini": (1.10, 4.40),
}


class OpenAIProviderAdapter(BaseModelProvider, ModelAdapter):
    """Proprietary Model Provider Adapter for OpenAI."""

    provider_id = Provider.OPENAI
    provider = Provider.OPENAI
    category = ModelCategory.CLOSED_PROPRIETARY
    DEFAULT_MODEL = "gpt-4o"

    def __init__(
        self,
        api_key: Optional[str] = None,
        default_model: Optional[str] = None,
        base_url: Optional[str] = None,
        transport: Optional[httpx.BaseTransport] = None,
    ):
        self._explicit_api_key = api_key
        self.default_model = default_model or self.DEFAULT_MODEL
        self.base_url = (base_url or "https://api.openai.com/v1").rstrip("/")
        self._transport = transport

    @property
    def api_key(self) -> Optional[str]:
        if self._explicit_api_key is not None:
            return self._explicit_api_key
        return settings.openai_api_key or os.getenv("OPENAI_API_KEY")

    def is_available(self) -> bool:
        return bool(self.api_key)

    def _get_pricing(self, model: str) -> tuple[float, float]:
        for prefix, rates in OPENAI_RATES.items():
            if model.startswith(prefix):
                return rates
        return (2.50, 10.00)

    def _compute_cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        rate_in, rate_out = self._get_pricing(model)
        return (prompt_tokens * rate_in / 1_000_000.0) + (completion_tokens * rate_out / 1_000_000.0)

    def _map_http_error(self, status_code: int, response_text: str) -> Exception:
        lower = response_text.lower()
        if status_code == 401 or "invalid_api_key" in lower or "incorrect api key" in lower:
            return ProviderAuthenticationError("Invalid or missing OpenAI API key.", provider=self.provider_id, status_code=status_code)
        if status_code == 429 or "rate_limit_exceeded" in lower or "quota" in lower:
            return ProviderRateLimitError(f"OpenAI rate limit or quota exceeded: {response_text[:200]}", provider=self.provider_id, status_code=status_code)
        if status_code == 400 and ("context_length_exceeded" in lower or "maximum context length" in lower):
            return ContextLengthExceededError(f"OpenAI context length exceeded: {response_text[:200]}", provider=self.provider_id, status_code=status_code)
        return ProviderError(f"OpenAI API returned error ({status_code}): {response_text[:300]}", provider=self.provider_id, status_code=status_code)

    async def complete(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        """Execute non-streaming chat completion."""
        if not self.is_available():
            raise ProviderAuthenticationError("OpenAI API key is not configured.", provider=self.provider_id)

        model = request.model or self.default_model
        messages = [{"role": m.role, "content": m.content} for m in request.messages]
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "stream": False,
        }
        if request.tools:
            payload["tools"] = request.tools

        timeout_val = settings.default_timeout_seconds
        start_time = time.perf_counter()

        try:
            async with httpx.AsyncClient(timeout=timeout_val, transport=self._transport) as client:
                resp = await client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(f"OpenAI generation timed out after {timeout_val:.0f}s", provider=self.provider_id) from exc
        except httpx.HTTPError as e:
            raise ProviderError(f"Failed to connect to OpenAI API: {e}", provider=self.provider_id) from e

        latency_ms = (time.perf_counter() - start_time) * 1000.0

        if resp.status_code != 200:
            raise self._map_http_error(resp.status_code, resp.text)

        data = resp.json()
        choices = data.get("choices") or [{}]
        content = (choices[0].get("message") or {}).get("content") or ""
        tool_calls = (choices[0].get("message") or {}).get("tool_calls")
        usage = data.get("usage") or {}
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        total_tokens = usage.get("total_tokens", prompt_tokens + completion_tokens)
        cost_usd = self._compute_cost(model, prompt_tokens, completion_tokens)

        return ChatCompletionResponse(
            model=data.get("model", model),
            provider=self.provider_id,
            category=self.category,
            content=content,
            finish_reason=choices[0].get("finish_reason", "stop"),
            usage={
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
            },
            latency_ms=round(latency_ms, 2),
            cost_usd=round(cost_usd, 6),
            routing_reason=f"Closed Commercial Frontier API ({model})",
            tool_calls=tool_calls,
        )

    async def stream_complete(self, request: ChatCompletionRequest) -> AsyncIterator[StreamChunk]:
        """Execute streaming completion yielding StreamChunks."""
        if not self.is_available():
            raise ProviderAuthenticationError("OpenAI API key is not configured.", provider=self.provider_id)

        model = request.model or self.default_model
        messages = [{"role": m.role, "content": m.content} for m in request.messages]
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "stream": True,
            "stream_options": {"include_usage": True},
        }

        timeout_val = settings.default_timeout_seconds
        async with httpx.AsyncClient(timeout=timeout_val, transport=self._transport) as client:
            async with client.stream("POST", f"{self.base_url}/chat/completions", headers=headers, json=payload) as resp:
                if resp.status_code != 200:
                    body = await resp.aread()
                    raise self._map_http_error(resp.status_code, body.decode("utf-8", errors="replace"))

                async for line in resp.aiter_lines():
                    line = line.strip()
                    if not line or not line.startswith("data:"):
                        continue
                    data_str = line[len("data:"):].strip()
                    if data_str == "[DONE]":
                        yield StreamChunk(
                            model=model,
                            provider=self.provider_id,
                            delta_content="",
                            finish_reason="stop",
                        )
                        break
                    try:
                        chunk_data = json.loads(data_str)
                        choices = chunk_data.get("choices") or []
                        delta = choices[0].get("delta", {}).get("content", "") if choices else ""
                        finish = choices[0].get("finish_reason") if choices else None
                        usage_data = chunk_data.get("usage")
                        yield StreamChunk(
                            id=chunk_data.get("id", ""),
                            model=chunk_data.get("model", model),
                            provider=self.provider_id,
                            delta_content=delta,
                            finish_reason=finish,
                            usage=usage_data,
                        )
                    except Exception:
                        continue

    async def health_check(self) -> Dict[str, Any]:
        return {
            "provider": self.provider_id.value,
            "category": self.category.value,
            "configured": bool(self.api_key),
            "endpoint": self.base_url,
            "default_model": self.default_model,
        }

    # Backward compatibility with ModelAdapter.complete
    async def complete_legacy(self, request: CompletionRequestSchema) -> CompletionResponseSchema:
        chat_req = ChatCompletionRequest(
            messages=request.messages,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            tools=[t.model_dump() for t in request.tools] if request.tools else None,
        )
        res = await self.complete(chat_req)
        return CompletionResponseSchema(
            content=res.content,
            provider=self.provider,
            model=res.model,
            usage=res.usage,
            latency_ms=res.latency_ms,
            cost_usd=res.cost_usd,
            routing_reason=res.routing_reason,
            tool_calls=res.tool_calls,
        )
