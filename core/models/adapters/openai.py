"""
OpenAI Model Adapter for Keelway Core.
Targets OpenAI Chat Completions API.
"""

import os
import time
from typing import Any, Dict, List, Optional
import httpx

from core.api.schemas import CompletionRequestSchema, CompletionResponseSchema, Provider
from core.models.adapters.base import ModelAdapter
from core.config import settings


class OpenAIAdapter(ModelAdapter):
    provider = Provider.OPENAI
    DEFAULT_MODEL = "gpt-4o"

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or settings.openai_api_key or os.getenv("OPENAI_API_KEY")
        self.model = model or self.DEFAULT_MODEL
        self.base_url = "https://api.openai.com/v1/chat/completions"

    def is_available(self) -> bool:
        return bool(self.api_key)

    async def complete(self, request: CompletionRequestSchema) -> CompletionResponseSchema:
        if not self.is_available():
            raise RuntimeError("OpenAI API key is not configured.")

        messages_payload: List[Dict[str, str]] = [
            {"role": m.role, "content": m.content} for m in request.messages
        ]

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages_payload,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }

        start_time = time.perf_counter()
        async with httpx.AsyncClient(timeout=settings.default_timeout_seconds) as client:
            resp = await client.post(self.base_url, headers=headers, json=payload)
            latency_ms = (time.perf_counter() - start_time) * 1000.0

            if resp.status_code != 200:
                raise RuntimeError(f"OpenAI API error ({resp.status_code}): {resp.text}")

            data = resp.json()

        choices = data.get("choices", [])
        content = choices[0].get("message", {}).get("content", "") if choices else ""

        usage = data.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)

        # GPT-4o pricing: $2.50 / MTok in, $10.00 / MTok out
        cost_usd = (prompt_tokens * 2.50 / 1_000_000) + (completion_tokens * 10.0 / 1_000_000)

        return CompletionResponseSchema(
            content=content,
            provider=self.provider,
            model=data.get("model", self.model),
            usage={
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
            latency_ms=round(latency_ms, 2),
            cost_usd=round(cost_usd, 6),
        )
