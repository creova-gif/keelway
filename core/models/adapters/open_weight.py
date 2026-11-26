"""
Keelway Open-Weight Model Provider Adapter.

Supports local and self-hosted open-weight inference engines:
1. Ollama (/api/chat, /api/tags)
2. OpenAI-compatible local/VPC servers: vLLM, llama.cpp server, TGI, LM Studio (/v1/chat/completions, /v1/models)

Provides both non-streaming generation and Server-Sent Events (SSE) token streaming.
Enforces zero external cloud egress ($0.00 external API billing).
"""

from __future__ import annotations

import json
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
    ProviderTimeoutError,
    ModelNotFoundError,
)
from core.models.adapters.base import ModelAdapter
from core.models.adapters.local import LocalAdapter, _recommended_model


class OpenWeightProviderAdapter(BaseModelProvider, ModelAdapter):
    """Unified Open-Weight Provider Adapter supporting Ollama and vLLM/OpenAI-compatible runtimes."""

    provider_id = Provider.LOCAL
    provider = Provider.LOCAL
    category = ModelCategory.OPEN_WEIGHT

    def __init__(
        self,
        base_url: Optional[str] = None,
        default_model: Optional[str] = None,
        api: Optional[str] = None,
        transport: Optional[httpx.BaseTransport] = None,
    ):
        self._local_adapter = LocalAdapter(base_url=base_url, default_model=default_model, api=api, transport=transport)
        self.base_url = self._local_adapter.base_url
        self.default_model = self._local_adapter.default_model
        self._transport = transport

    def is_available(self) -> bool:
        return self._local_adapter.is_available()

    def local_runtime(self):
        """Expose the underlying local runtime probe (installed models, API kind)."""
        return self._local_adapter.runtime()

    def resolve_model(self, requested_model: Optional[str] = None) -> str:
        if requested_model:
            # Check if requested model or tag is in runtime
            rt = self._local_adapter.runtime()
            if rt.models and requested_model in rt.models:
                return requested_model
            # Check if requested without :latest or with :latest
            for name in rt.models:
                if name.startswith(f"{requested_model}:") or requested_model.startswith(f"{name}:"):
                    return name
            # If not in local runtime but explicit, return requested (e.g. for self-hosted/vllm)
            return requested_model
        return self._local_adapter.resolve_model()

    async def complete(self, request: Any) -> ChatCompletionResponse:
        """Execute non-streaming completion."""
        rt = self._local_adapter.runtime()
        req_model = getattr(request, "model", None) or ""
        if req_model.startswith("keelway-") and (not rt.up or not rt.models or req_model not in rt.models):
            from core.opencore.serving import opencore_serving_engine
            if not isinstance(request, ChatCompletionRequest):
                request = ChatCompletionRequest(
                    messages=request.messages,
                    model=req_model,
                    temperature=getattr(request, "temperature", 0.2),
                    max_tokens=getattr(request, "max_tokens", 4096),
                )
            return await opencore_serving_engine.forward_inference(request)

        if not rt.up:
            raise ProviderError(
                f"No local open-weight model server reachable at {self.base_url}. Please start Ollama (ollama serve) or vLLM.",
                provider=self.provider_id,
            )

        model = self.resolve_model(req_model)
        messages = [{"role": m.role, "content": m.content} for m in request.messages]
        timeout_val = max(settings.default_timeout_seconds, 120.0)
        start_time = time.perf_counter()

        if rt.api == "ollama":
            url = f"{self.base_url}/api/chat"
            payload: Dict[str, Any] = {
                "model": model,
                "messages": messages,
                "stream": False,
                "think": "reasoning" in (getattr(request, "model", "") or "").lower()
                or "complex_reasoning" in (getattr(request, "required_capabilities", None) or []),
                "options": {
                    "temperature": request.temperature,
                    "num_predict": request.max_tokens,
                },
            }
        else:
            url = f"{self.base_url}/v1/chat/completions"
            payload = {
                "model": model,
                "messages": messages,
                "temperature": request.temperature,
                "max_tokens": request.max_tokens,
                "stream": False,
            }

        try:
            async with httpx.AsyncClient(timeout=timeout_val, transport=self._transport) as client:
                resp = await client.post(url, json=payload)
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(f"Open-weight model inference timed out after {timeout_val:.0f}s", provider=self.provider_id) from exc
        except httpx.HTTPError as e:
            raise ProviderError(f"Open-weight server connection error: {e}", provider=self.provider_id) from e

        latency_ms = (time.perf_counter() - start_time) * 1000.0

        if resp.status_code == 404 and rt.api == "ollama":
            raise ModelNotFoundError(
                f"Open-weight model '{model}' is not installed in Ollama. Pull it with: ollama pull {_recommended_model()}",
                provider=self.provider_id,
            )
        if resp.status_code != 200:
            raise ProviderError(f"Open-weight runtime returned error ({resp.status_code}): {resp.text[:300]}", provider=self.provider_id, status_code=resp.status_code)

        data = resp.json()
        if rt.api == "ollama":
            content = data.get("message", {}).get("content") or data.get("message", {}).get("thinking") or ""
            prompt_tokens = data.get("prompt_eval_count", 0)
            completion_tokens = data.get("eval_count", 0)
        else:
            choices = data.get("choices") or [{}]
            content = (choices[0].get("message") or {}).get("content") or ""
            usage = data.get("usage") or {}
            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)

        return ChatCompletionResponse(
            model=data.get("model", model),
            provider=self.provider_id,
            category=self.category,
            content=content,
            finish_reason="stop",
            usage={
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
            latency_ms=round(latency_ms, 2),
            cost_usd=0.0,  # Zero cloud egress billing
            routing_reason="Open-Weight Inference ($0.00 external API cost)",
        )

    async def stream_complete(self, request: ChatCompletionRequest) -> AsyncIterator[StreamChunk]:
        """Execute streaming completion yielding StreamChunks."""
        rt = self._local_adapter.runtime()
        req_model = getattr(request, "model", None) or ""
        if req_model.startswith("keelway-") and (not rt.up or not rt.models or req_model not in rt.models):
            from core.opencore.serving import opencore_serving_engine
            res = await opencore_serving_engine.forward_inference(request)
            yield StreamChunk(
                id=res.id,
                model=res.model,
                delta_content=res.content,
                finish_reason="stop",
                usage=res.usage,
            )
            return

        if not rt.up:
            raise ProviderError(
                f"No local open-weight model server reachable at {self.base_url} for streaming.",
                provider=self.provider_id,
            )

        model = self.resolve_model(request.model)
        messages = [{"role": m.role, "content": m.content} for m in request.messages]
        timeout_val = max(settings.default_timeout_seconds, 180.0)

        if rt.api == "ollama":
            url = f"{self.base_url}/api/chat"
            payload: Dict[str, Any] = {
                "model": model,
                "messages": messages,
                "stream": True,
                "think": "reasoning" in (getattr(request, "model", "") or "").lower()
                or "complex_reasoning" in (getattr(request, "required_capabilities", None) or []),
                "options": {
                    "temperature": request.temperature,
                    "num_predict": request.max_tokens,
                },
            }
        else:
            url = f"{self.base_url}/v1/chat/completions"
            payload = {
                "model": model,
                "messages": messages,
                "temperature": request.temperature,
                "max_tokens": request.max_tokens,
                "stream": True,
            }

        async with httpx.AsyncClient(timeout=timeout_val, transport=self._transport) as client:
            async with client.stream("POST", url, json=payload) as resp:
                if resp.status_code != 200:
                    body = await resp.aread()
                    raise ProviderError(f"Open-weight streaming error ({resp.status_code}): {body.decode('utf-8', errors='replace')[:300]}", provider=self.provider_id, status_code=resp.status_code)

                if rt.api == "ollama":
                    # Ollama streams ndjson lines
                    async for line in resp.aiter_lines():
                        if not line or not line.strip():
                            continue
                        try:
                            chunk_data = json.loads(line)
                            delta = chunk_data.get("message", {}).get("content", "")
                            done = chunk_data.get("done", False)
                            usage = None
                            if done:
                                usage = {
                                    "prompt_tokens": chunk_data.get("prompt_eval_count", 0),
                                    "completion_tokens": chunk_data.get("eval_count", 0),
                                    "total_tokens": chunk_data.get("prompt_eval_count", 0) + chunk_data.get("eval_count", 0),
                                }
                            yield StreamChunk(
                                model=chunk_data.get("model", model),
                                provider=self.provider_id,
                                delta_content=delta,
                                finish_reason="stop" if done else None,
                                usage=usage,
                            )
                        except Exception:
                            continue
                else:
                    # OpenAI-compatible SSE lines (vLLM, llama.cpp)
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
                            choices = chunk_data.get("choices") or [{}]
                            delta = choices[0].get("delta", {}).get("content", "")
                            finish = choices[0].get("finish_reason")
                            yield StreamChunk(
                                model=chunk_data.get("model", model),
                                provider=self.provider_id,
                                delta_content=delta,
                                finish_reason=finish,
                            )
                        except Exception:
                            continue

    async def health_check(self) -> Dict[str, Any]:
        rt = self._local_adapter.runtime(refresh=True)
        return {
            "provider": self.provider_id.value,
            "category": self.category.value,
            "reachable": rt.up,
            "api_type": rt.api,
            "endpoint": self.base_url,
            "installed_models": rt.models,
            "resolved_model": self.resolve_model() if rt.up else None,
            "recommended_model": _recommended_model(),
        }

    # Backward compatibility with ModelAdapter.complete
    async def complete_legacy(self, request: CompletionRequestSchema) -> CompletionResponseSchema:
        return await self._local_adapter.complete(request)
