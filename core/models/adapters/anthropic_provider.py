"""
Keelway Proprietary Closed-Model Provider Adapter for Anthropic Claude.

Provides production integration with Anthropic Claude Messages API.
Supports dynamic model selection (claude-3-5-sonnet, claude-3-5-haiku, claude-3-opus),
message normalization with system prompt extraction, Server-Sent Events (SSE) token streaming,
error classification, and token cost attribution.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, AsyncIterator, Dict, List, Optional
import httpx

from core.api.schemas import Provider, CompletionRequestSchema, CompletionResponseSchema, MessageSchema
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


# Standard Anthropic rate card per million tokens (input, output) in USD
ANTHROPIC_RATES: Dict[str, tuple[float, float]] = {
    "claude-3-5-sonnet": (3.00, 15.00),
    "claude-3-5-haiku": (0.80, 4.00),
    "claude-3-opus": (15.00, 75.00),
    "claude-3-sonnet": (3.00, 15.00),
    "claude-3-haiku": (0.25, 1.25),
}


class AnthropicProviderAdapter(BaseModelProvider):
    """Proprietary Model Provider Adapter for Anthropic Claude."""

    provider_id = Provider.ANTHROPIC
    provider = Provider.ANTHROPIC
    category = ModelCategory.CLOSED_PROPRIETARY
    DEFAULT_MODEL = "claude-3-5-sonnet"

    def __init__(
        self,
        api_key: Optional[str] = None,
        default_model: Optional[str] = None,
        base_url: Optional[str] = None,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ):
        self._explicit_api_key = api_key
        self.default_model = default_model or self.DEFAULT_MODEL
        self.base_url = (base_url or "https://api.anthropic.com/v1").rstrip("/")
        self._transport = transport

    @property
    def api_key(self) -> Optional[str]:
        if self._explicit_api_key is not None:
            return self._explicit_api_key
        return settings.anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")

    def is_available(self) -> bool:
        return bool(self.api_key)

    def _get_pricing(self, model: str) -> tuple[float, float]:
        for prefix in sorted(ANTHROPIC_RATES.keys(), key=len, reverse=True):
            if model.startswith(prefix) or prefix in model:
                return ANTHROPIC_RATES[prefix]
        return (3.00, 15.00)

    def _compute_cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        rate_in, rate_out = self._get_pricing(model)
        return (prompt_tokens * rate_in / 1_000_000.0) + (completion_tokens * rate_out / 1_000_000.0)

    def _headers(self) -> Dict[str, str]:
        return {
            "x-api-key": self.api_key or "",
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

    def _prepare_messages(self, messages: List[MessageSchema]) -> tuple[Optional[str], List[Dict[str, Any]]]:
        system_parts: List[str] = []
        chat_messages: List[Dict[str, Any]] = []

        for msg in messages:
            if msg.role == "system":
                if msg.content:
                    system_parts.append(msg.content)
            else:
                chat_messages.append({"role": msg.role, "content": msg.content})

        system_prompt = "\n\n".join(system_parts) if system_parts else None
        return system_prompt, chat_messages

    def _map_http_error(self, status_code: int, response_text: str) -> Exception:
        lower = response_text.lower()
        if status_code == 401 or "authentication_error" in lower or "invalid x-api-key" in lower or "api_key" in lower:
            return ProviderAuthenticationError(
                f"Invalid or missing Anthropic API key: {response_text[:200]}",
                provider=self.provider_id,
                status_code=status_code,
            )
        if status_code == 429 or "rate_limit" in lower:
            return ProviderRateLimitError(
                f"Anthropic rate limit exceeded: {response_text[:200]}",
                provider=self.provider_id,
                status_code=status_code,
            )
        if status_code == 400 and (
            "context_length" in lower
            or "prompt is too long" in lower
            or "max_tokens" in lower
            or "too many tokens" in lower
            or "token limit" in lower
            or "maximum context" in lower
        ):
            return ContextLengthExceededError(
                f"Anthropic context length or token limit exceeded: {response_text[:200]}",
                provider=self.provider_id,
                status_code=status_code,
            )
        return ProviderError(
            f"Anthropic API returned error ({status_code}): {response_text[:300]}",
            provider=self.provider_id,
            status_code=status_code,
        )

    async def complete(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        """Execute non-streaming chat completion."""
        if not self.is_available():
            raise ProviderAuthenticationError("Anthropic API key is not configured.", provider=self.provider_id)

        model = request.model or self.default_model
        system_prompt, messages = self._prepare_messages(request.messages)
        headers = self._headers()

        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": request.max_tokens or 4096,
            "temperature": request.temperature,
            "stream": False,
        }
        if system_prompt:
            payload["system"] = system_prompt
        if request.tools:
            payload["tools"] = request.tools

        timeout_val = settings.default_timeout_seconds
        start_time = time.perf_counter()

        try:
            async with httpx.AsyncClient(timeout=timeout_val, transport=self._transport) as client:
                resp = await client.post(f"{self.base_url}/messages", headers=headers, json=payload)
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(f"Anthropic generation timed out after {timeout_val:.0f}s", provider=self.provider_id) from exc
        except httpx.HTTPError as e:
            raise ProviderError(f"Failed to connect to Anthropic API: {e}", provider=self.provider_id) from e

        latency_ms = (time.perf_counter() - start_time) * 1000.0

        if resp.status_code != 200:
            raise self._map_http_error(resp.status_code, resp.text)

        data = resp.json()

        # Parse text content from content blocks
        content = ""
        for block in data.get("content", []):
            if isinstance(block, dict) and block.get("type") == "text":
                content += block.get("text", "")
        if not content and data.get("content"):
            first_block = data["content"][0]
            if isinstance(first_block, dict):
                content = first_block.get("text", "")

        stop_reason = data.get("stop_reason")
        finish_reason = "stop" if stop_reason in ("end_turn", "stop_sequence", None) else stop_reason

        usage_data = data.get("usage") or {}
        prompt_tokens = usage_data.get("input_tokens", 0)
        completion_tokens = usage_data.get("output_tokens", 0)
        total_tokens = prompt_tokens + completion_tokens
        cost_usd = self._compute_cost(model, prompt_tokens, completion_tokens)

        resp_id = data.get("id")
        kwargs: Dict[str, Any] = {
            "model": data.get("model", model),
            "provider": self.provider_id,
            "category": self.category,
            "content": content,
            "finish_reason": finish_reason,
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
            },
            "latency_ms": round(latency_ms, 2),
            "cost_usd": round(cost_usd, 6),
            "routing_reason": f"Closed Commercial Frontier API ({model})",
        }
        if resp_id:
            kwargs["id"] = resp_id

        return ChatCompletionResponse(**kwargs)

    async def stream_complete(self, request: ChatCompletionRequest) -> AsyncIterator[StreamChunk]:
        """Execute streaming completion yielding StreamChunks."""
        if not self.is_available():
            raise ProviderAuthenticationError("Anthropic API key is not configured.", provider=self.provider_id)

        model = request.model or self.default_model
        system_prompt, messages = self._prepare_messages(request.messages)
        headers = self._headers()

        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": request.max_tokens or 4096,
            "temperature": request.temperature,
            "stream": True,
        }
        if system_prompt:
            payload["system"] = system_prompt
        if request.tools:
            payload["tools"] = request.tools

        timeout_val = settings.default_timeout_seconds
        msg_id: Optional[str] = None
        input_tokens = 0
        output_tokens = 0

        async with httpx.AsyncClient(timeout=timeout_val, transport=self._transport) as client:
            async with client.stream("POST", f"{self.base_url}/messages", headers=headers, json=payload) as resp:
                if resp.status_code != 200:
                    body = await resp.aread()
                    raise self._map_http_error(resp.status_code, body.decode("utf-8", errors="replace"))

                async for line in resp.aiter_lines():
                    line = line.strip()
                    if not line or not line.startswith("data:"):
                        continue
                    data_str = line[len("data:"):].strip()
                    if not data_str:
                        continue
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk_data = json.loads(data_str)
                    except Exception:
                        continue

                    event_type = chunk_data.get("type")
                    if event_type == "message_start":
                        msg = chunk_data.get("message", {})
                        if msg.get("id"):
                            msg_id = msg.get("id")
                        usage = msg.get("usage", {})
                        input_tokens += usage.get("input_tokens", 0)
                        output_tokens += usage.get("output_tokens", 0)

                    elif event_type == "content_block_delta":
                        delta_obj = chunk_data.get("delta") or {}
                        delta_text = delta_obj.get("text", "")
                        if delta_text:
                            yield StreamChunk(
                                id=msg_id or chunk_data.get("id", ""),
                                model=model,
                                provider=self.provider_id,
                                delta_content=delta_text,
                            )

                    elif event_type == "message_delta":
                        delta_obj = chunk_data.get("delta") or {}
                        stop_reason = delta_obj.get("stop_reason")
                        usage = chunk_data.get("usage", {})
                        output_tokens += usage.get("output_tokens", 0)
                        total_usage = None
                        if input_tokens or output_tokens:
                            total_usage = {
                                "prompt_tokens": input_tokens,
                                "completion_tokens": output_tokens,
                                "total_tokens": input_tokens + output_tokens,
                            }
                        yield StreamChunk(
                            id=msg_id or chunk_data.get("id", ""),
                            model=model,
                            provider=self.provider_id,
                            delta_content="",
                            finish_reason=stop_reason or "stop",
                            usage=total_usage,
                        )

                    elif event_type == "message_stop":
                        break

                    else:
                        # Fallback for generic chunks that contain delta.text
                        delta_obj = chunk_data.get("delta")
                        if isinstance(delta_obj, dict) and "text" in delta_obj:
                            delta_text = delta_obj.get("text", "")
                            if delta_text:
                                yield StreamChunk(
                                    id=msg_id or chunk_data.get("id", ""),
                                    model=model,
                                    provider=self.provider_id,
                                    delta_content=delta_text,
                                )

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
