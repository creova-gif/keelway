"""
Local / Edge Model Adapter (Ollama / vLLM / OpenAI-compatible local runtime).
"""

import time
from typing import Any, Dict, List, Optional
import httpx

from core.api.schemas import CompletionRequestSchema, CompletionResponseSchema, Provider
from core.models.adapters.base import ModelAdapter
from core.config import settings


class LocalAdapter(ModelAdapter):
    provider = Provider.LOCAL

    def __init__(self, base_url: Optional[str] = None, default_model: Optional[str] = None):
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.default_model = default_model or settings.default_local_model

    def is_available(self) -> bool:
        return bool(self.base_url)

    async def complete(self, request: CompletionRequestSchema) -> CompletionResponseSchema:
        url = f"{self.base_url}/api/chat"
        messages_payload = [{"role": m.role, "content": m.content} for m in request.messages]

        payload: Dict[str, Any] = {
            "model": self.default_model,
            "messages": messages_payload,
            "stream": False,
            "options": {
                "temperature": request.temperature,
                "num_predict": request.max_tokens,
            },
        }

        start_time = time.perf_counter()
        timeout_val = max(settings.default_timeout_seconds, 180.0)
        try:
            async with httpx.AsyncClient(timeout=timeout_val) as client:
                resp = await client.post(url, json=payload)
                latency_ms = (time.perf_counter() - start_time) * 1000.0

                if resp.status_code != 200:
                    raise RuntimeError(f"Local runtime error ({resp.status_code}): {resp.text}")

                data = resp.json()
        except httpx.TimeoutException:
            raise RuntimeError(f"Local model generation timed out after {timeout_val:.0f}s.")

        content = data.get("message", {}).get("content", "")
        prompt_tokens = data.get("prompt_eval_count", 0)
        completion_tokens = data.get("eval_count", 0)

        # Local model cost is 0.0 USD
        return CompletionResponseSchema(
            content=content,
            provider=self.provider,
            model=data.get("model", self.default_model),
            usage={
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
            latency_ms=round(latency_ms, 2),
            cost_usd=0.0,
        )
