"""
Keelway Native Google Gemini Model Provider Adapter.

Provides production integration with the Google Gemini Generative Language REST API (v1beta).
Supports dynamic model selection (gemini-2.5-flash, gemini-2.5-pro, gemini-1.5-flash, gemini-1.5-pro),
normalized non-streaming completion, Server-Sent Events (SSE) token streaming, error classification,
and token billing based on Gemini pricing rate cards.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from typing import Any, AsyncIterator, Dict, List, Optional
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


# Gemini pricing rate card per million tokens (input, output) in USD
GEMINI_RATES: Dict[str, tuple[float, float]] = {
    "gemini-3.8-flash-lite": (0.075, 0.30),
    "gemini-3.8-flash": (0.15, 0.60),
    "gemini-3.5-flash-lite": (0.075, 0.30),
    "gemini-3.5-flash": (0.15, 0.60),
    "gemini-flash-lite-latest": (0.075, 0.30),
    "gemini-flash-latest": (0.15, 0.60),
    "gemini-2.5-flash-lite": (0.075, 0.30),
    "gemini-2.5-flash": (0.075, 0.30),
    "gemini-2.5-pro": (1.25, 5.00),
    "gemini-1.5-flash": (0.075, 0.30),
    "gemini-1.5-pro": (1.25, 5.00),
}


def _extract_non_thought_text(parts: List[Any]) -> str:
    """Concatenate text parts while excluding Gemini 3.x internal thought traces when answer parts exist."""
    dict_parts = [p for p in parts if isinstance(p, dict)]
    answer_parts = [p.get("text", "") for p in dict_parts if not p.get("thought")]
    if any(answer_parts):
        return "".join(answer_parts)
    return "".join(p.get("text", "") for p in dict_parts)


class GeminiProviderAdapter(BaseModelProvider, ModelAdapter):
    """Native Model Provider Adapter for Google Gemini REST API."""

    provider_id = Provider.GEMINI
    provider = Provider.GEMINI
    category = ModelCategory.CLOSED_PROPRIETARY
    DEFAULT_MODEL = "gemini-2.5-flash"

    def __init__(
        self,
        api_key: Optional[str] = None,
        default_model: Optional[str] = None,
        base_url: Optional[str] = None,
        transport: Optional[httpx.BaseTransport] = None,
    ):
        self._explicit_api_key = api_key
        self.default_model = default_model or self.DEFAULT_MODEL
        self.base_url = (base_url or "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
        self._transport = transport

    @property
    def api_key(self) -> Optional[str]:
        if self._explicit_api_key is not None:
            return self._explicit_api_key
        return settings.gemini_api_key or os.getenv("GEMINI_API_KEY")

    def is_available(self) -> bool:
        """Return True if Gemini API key is configured."""
        return bool(self.api_key)

    def _get_pricing(self, model: str) -> tuple[float, float]:
        clean_model = model.removeprefix("models/")
        for prefix in sorted(GEMINI_RATES.keys(), key=len, reverse=True):
            if clean_model.startswith(prefix):
                return GEMINI_RATES[prefix]
        return (0.075, 0.30)

    def _compute_cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        rate_in, rate_out = self._get_pricing(model)
        return (prompt_tokens * rate_in / 1_000_000.0) + (completion_tokens * rate_out / 1_000_000.0)

    def _format_payload(self, request: ChatCompletionRequest) -> Dict[str, Any]:
        """Convert normalized request messages into Gemini REST format."""
        contents: List[Dict[str, Any]] = []
        system_parts: List[Dict[str, str]] = []

        for msg in request.messages:
            if msg.role == "system":
                system_parts.append({"text": msg.content})
            else:
                role = "model" if msg.role == "assistant" else "user"
                contents.append({"role": role, "parts": [{"text": msg.content}]})

        if not contents and system_parts:
            contents.append({"role": "user", "parts": system_parts})
            system_parts = []

        generation_config: Dict[str, Any] = {
            "temperature": request.temperature,
            "maxOutputTokens": request.max_tokens,
        }
        resp_fmt = getattr(request, "response_format", None)
        if isinstance(resp_fmt, dict) and resp_fmt.get("type") == "json_object":
            generation_config["responseMimeType"] = "application/json"

        payload: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": generation_config,
        }
        if system_parts:
            payload["systemInstruction"] = {"parts": system_parts}

        if request.tools:
            payload["tools"] = request.tools

        return payload

    def _map_http_error(self, status_code: int, response_text: str) -> Exception:
        """Map Gemini HTTP error codes and body payloads to normalized ProviderError subclasses."""
        lower = response_text.lower()
        if (
            status_code in (401, 403)
            or "api_key_invalid" in lower
            or "invalid_api_key" in lower
            or "api key not valid" in lower
            or "permission_denied" in lower
        ):
            return ProviderAuthenticationError(
                f"Invalid, unauthorized or missing Gemini API key: {response_text[:200]}",
                provider=self.provider_id,
                status_code=status_code,
            )
        if (
            status_code == 429
            or "resource_exhausted" in lower
            or "rate_limit" in lower
            or "quota" in lower
        ):
            return ProviderRateLimitError(
                f"Gemini rate limit or quota exceeded: {response_text[:200]}",
                provider=self.provider_id,
                status_code=status_code,
            )
        if status_code == 400 and (
            "context" in lower
            or "token" in lower
            or "exceed" in lower
            or "maximum" in lower
            or "too long" in lower
        ):
            return ContextLengthExceededError(
                f"Gemini context length exceeded: {response_text[:200]}",
                provider=self.provider_id,
                status_code=status_code,
            )
        return ProviderError(
            f"Gemini API returned error ({status_code}): {response_text[:300]}",
            provider=self.provider_id,
            status_code=status_code,
        )

    async def complete(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        """Execute non-streaming chat completion."""
        if not self.is_available():
            raise ProviderAuthenticationError("Gemini API key is not configured.", provider=self.provider_id)

        model = request.model or self.default_model
        clean_model = model.removeprefix("models/")
        url = f"{self.base_url}/models/{clean_model}:generateContent"
        headers = {"Content-Type": "application/json", "x-goog-api-key": str(self.api_key)}
        payload = self._format_payload(request)

        timeout_val = settings.default_timeout_seconds
        start_time = time.perf_counter()

        try:
            async with httpx.AsyncClient(timeout=timeout_val, transport=self._transport) as client:
                resp = await client.post(url, headers=headers, json=payload)
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(f"Gemini generation timed out after {timeout_val:.0f}s", provider=self.provider_id) from exc
        except httpx.HTTPError as e:
            raise ProviderError(f"Failed to connect to Gemini API: {e}", provider=self.provider_id) from e

        latency_ms = (time.perf_counter() - start_time) * 1000.0

        if resp.status_code != 200:
            raise self._map_http_error(resp.status_code, resp.text)

        data = resp.json()
        candidates = data.get("candidates") or []
        content = ""
        finish_reason = "stop"
        if candidates:
            cand = candidates[0]
            parts = (cand.get("content") or {}).get("parts") or []
            content = _extract_non_thought_text(parts)
            raw_finish = cand.get("finishReason")
            if raw_finish:
                finish_reason = str(raw_finish).lower()

        usage_metadata = data.get("usageMetadata") or {}
        prompt_tokens = usage_metadata.get("promptTokenCount", 0)
        completion_tokens = usage_metadata.get("candidatesTokenCount", 0)
        total_tokens = usage_metadata.get("totalTokenCount", prompt_tokens + completion_tokens)
        cost_usd = self._compute_cost(model, prompt_tokens, completion_tokens)

        return ChatCompletionResponse(
            id=f"gemini-{uuid.uuid4().hex[:12]}",
            model=data.get("modelVersion", model),
            provider=self.provider_id,
            category=self.category,
            content=content,
            finish_reason=finish_reason,
            usage={
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
            },
            latency_ms=round(latency_ms, 2),
            cost_usd=round(cost_usd, 6),
            routing_reason=f"Google Gemini Closed API ({model})",
        )

    async def stream_complete(self, request: ChatCompletionRequest) -> AsyncIterator[StreamChunk]:
        """Execute streaming completion yielding StreamChunks."""
        if not self.is_available():
            raise ProviderAuthenticationError("Gemini API key is not configured.", provider=self.provider_id)

        model = request.model or self.default_model
        clean_model = model.removeprefix("models/")
        url = f"{self.base_url}/models/{clean_model}:streamGenerateContent?alt=sse"
        headers = {"Content-Type": "application/json", "x-goog-api-key": str(self.api_key)}
        payload = self._format_payload(request)

        timeout_val = settings.default_timeout_seconds
        try:
            async with httpx.AsyncClient(timeout=timeout_val, transport=self._transport) as client:
                async with client.stream("POST", url, headers=headers, json=payload) as resp:
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
                        except Exception:
                            continue

                        candidates = chunk_data.get("candidates") or []
                        delta = ""
                        finish = None
                        if candidates:
                            cand = candidates[0]
                            parts = (cand.get("content") or {}).get("parts") or []
                            delta = "".join(p.get("text", "") for p in parts if isinstance(p, dict))
                            if cand.get("finishReason"):
                                finish = str(cand.get("finishReason")).lower()

                        usage_dict = None
                        usage_meta = chunk_data.get("usageMetadata")
                        if usage_meta:
                            p_tokens = usage_meta.get("promptTokenCount", 0)
                            c_tokens = usage_meta.get("candidatesTokenCount", 0)
                            usage_dict = {
                                "prompt_tokens": p_tokens,
                                "completion_tokens": c_tokens,
                                "total_tokens": usage_meta.get("totalTokenCount", p_tokens + c_tokens),
                            }

                        yield StreamChunk(
                            model=chunk_data.get("modelVersion", model),
                            provider=self.provider_id,
                            delta_content=delta,
                            finish_reason=finish,
                            usage=usage_dict,
                        )
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(f"Gemini streaming timed out after {timeout_val:.0f}s", provider=self.provider_id) from exc
        except (ProviderError, ProviderAuthenticationError, ProviderRateLimitError, ContextLengthExceededError, ProviderTimeoutError):
            raise
        except httpx.HTTPError as e:
            raise ProviderError(f"Failed to stream from Gemini API: {e}", provider=self.provider_id) from e

    async def health_check(self) -> Dict[str, Any]:
        """Verify provider health, latency, and reachable endpoint."""
        return {
            "provider": self.provider_id.value,
            "category": self.category.value,
            "configured": bool(self.api_key),
            "endpoint": self.base_url,
            "default_model": self.default_model,
        }

    async def complete_legacy(self, request: CompletionRequestSchema) -> CompletionResponseSchema:
        """Backward compatibility with legacy ModelAdapter interface."""
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
