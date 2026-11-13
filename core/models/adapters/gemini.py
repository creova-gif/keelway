"""
Google Gemini Model Adapter for Keelway Core.
Direct REST client targeting Google AI Studio or Vertex AI Gemini endpoints.
"""

import os
import time
from typing import Any, Dict, List, Optional
import httpx

from core.api.schemas import CompletionRequestSchema, CompletionResponseSchema, Provider
from core.models.adapters.base import ModelAdapter
from core.config import settings


class GeminiAdapter(ModelAdapter):
    provider = Provider.GOOGLE
    DEFAULT_MODEL = "gemini-3.8-flash"

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or settings.gemini_api_key or os.getenv("GEMINI_API_KEY")
        self.model = model or self.DEFAULT_MODEL

    def is_available(self) -> bool:
        return bool(self.api_key)

    async def complete(self, request: CompletionRequestSchema) -> CompletionResponseSchema:
        if not self.is_available():
            raise RuntimeError("Google Gemini API key is not configured.")

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        headers = {"Content-Type": "application/json", "x-goog-api-key": str(self.api_key)}

        contents: List[Dict[str, Any]] = []
        system_instruction: Optional[Dict[str, Any]] = None

        for msg in request.messages:
            if msg.role == "system":
                system_instruction = {"parts": [{"text": msg.content}]}
            else:
                role = "user" if msg.role == "user" else "model"
                contents.append({"role": role, "parts": [{"text": msg.content}]})

        payload: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": request.temperature,
                "maxOutputTokens": request.max_tokens,
            },
        }
        if system_instruction:
            payload["systemInstruction"] = system_instruction

        start_time = time.perf_counter()
        async with httpx.AsyncClient(timeout=settings.default_timeout_seconds) as client:
            resp = await client.post(url, headers=headers, json=payload)
            latency_ms = (time.perf_counter() - start_time) * 1000.0

            if resp.status_code != 200:
                raise RuntimeError(f"Gemini API error ({resp.status_code}): {resp.text}")

            data = resp.json()

        # Extract generated text
        content = ""
        candidates = data.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            for p in parts:
                content += p.get("text", "")

        usage_metadata = data.get("usageMetadata", {})
        prompt_tokens = usage_metadata.get("promptTokenCount", 0)
        completion_tokens = usage_metadata.get("candidatesTokenCount", 0)

        # Gemini 2.5 Flash pricing: $0.075 / MTok in, $0.30 / MTok out
        cost_usd = (prompt_tokens * 0.075 / 1_000_000) + (completion_tokens * 0.30 / 1_000_000)

        return CompletionResponseSchema(
            content=content,
            provider=self.provider,
            model=self.model,
            usage={
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
            latency_ms=round(latency_ms, 2),
            cost_usd=round(cost_usd, 6),
        )
