"""
Anthropic Claude Model Adapter.
"""

import os
import time
from typing import Any, Dict, List, Optional
import httpx

from core.api.schemas import CompletionRequestSchema, CompletionResponseSchema, Provider
from core.models.adapters.base import ModelAdapter
from core.config import settings


class AnthropicAdapter(ModelAdapter):
    provider = Provider.ANTHROPIC
    DEFAULT_MODEL = "claude-3-5-sonnet-20241022"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")
        self.base_url = "https://api.anthropic.com/v1/messages"

    def is_available(self) -> bool:
        return bool(self.api_key)

    async def complete(self, request: CompletionRequestSchema) -> CompletionResponseSchema:
        if not self.is_available():
            raise RuntimeError("Anthropic API key is not configured.")

        system_prompt: Optional[str] = None
        messages_payload: List[Dict[str, str]] = []

        for msg in request.messages:
            if msg.role == "system":
                system_prompt = msg.content
            else:
                messages_payload.append({"role": msg.role, "content": msg.content})

        if not self.api_key:
            raise RuntimeError("Anthropic API key not configured")
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        payload: Dict[str, Any] = {
            "model": self.DEFAULT_MODEL,
            "messages": messages_payload,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
        }
        if system_prompt:
            payload["system"] = system_prompt

        start_time = time.perf_counter()
        async with httpx.AsyncClient(timeout=settings.default_timeout_seconds) as client:
            resp = await client.post(self.base_url, headers=headers, json=payload)
            latency_ms = (time.perf_counter() - start_time) * 1000.0

            if resp.status_code != 200:
                raise RuntimeError(f"Anthropic API error ({resp.status_code}): {resp.text}")

            data = resp.json()

        content = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                content += block.get("text", "")

        usage_data = data.get("usage", {})
        prompt_tokens = usage_data.get("input_tokens", 0)
        completion_tokens = usage_data.get("output_tokens", 0)

        # Sonnet cost model: $3.00 / MTok in, $15.00 / MTok out
        cost_usd = (prompt_tokens * 3.0 / 1_000_000) + (completion_tokens * 15.0 / 1_000_000)

        return CompletionResponseSchema(
            content=content,
            provider=self.provider,
            model=data.get("model", self.DEFAULT_MODEL),
            usage={
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
            latency_ms=round(latency_ms, 2),
            cost_usd=round(cost_usd, 6),
        )
