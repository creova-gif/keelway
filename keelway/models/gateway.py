"""Keelway Model Gateway.
Implements FR-04 (model routing, local Ollama/vLLM adapters) and FR-10 (budget hard stop).
"""
from __future__ import annotations

import enum
from typing import Any, Dict, List, Optional
import httpx
from pydantic import BaseModel


class ProviderKind(str, enum.Enum):
    LOCAL_OLLAMA = "local_ollama"
    LOCAL_VLLM = "local_vllm"
    OPENAI_COMPATIBLE = "openai_compatible"
    DETERMINISTIC_MOCK = "deterministic_mock"


class ModelCapabilities(BaseModel):
    supports_structured_output: bool = True
    supports_code_generation: bool = True
    max_context_window: int = 128000
    cost_per_1k_tokens_cents: float = 0.5


class ModelGatewayError(Exception):
    pass


class BudgetExceededError(ModelGatewayError):
    pass


class ModelGateway:
    """Manages LLM routing, token tracking, and hard budget cancellation."""

    def __init__(
        self,
        provider: ProviderKind = ProviderKind.DETERMINISTIC_MOCK,
        model_name: str = "local-deepseek-coder",
        endpoint_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        self.provider = provider
        self.model_name = model_name
        self.endpoint_url = endpoint_url or self._default_endpoint(provider)
        self.api_key = api_key
        self.capabilities = ModelCapabilities()

    def _default_endpoint(self, provider: ProviderKind) -> str:
        if provider == ProviderKind.LOCAL_OLLAMA:
            return "http://localhost:11434"
        elif provider == ProviderKind.LOCAL_VLLM:
            return "http://localhost:8000"
        return "https://api.openai.com"

    def generate_patch_proposal(
        self,
        task_prompt: str,
        file_tree: List[str],
        token_ceiling: int = 50000,
        tokens_used_so_far: int = 0,
        timeout_seconds: float = 30.0,
    ) -> Dict[str, Any]:
        """Requests patch generation while strictly enforcing token ceilings."""
        if tokens_used_so_far >= token_ceiling:
            raise BudgetExceededError(
                f"Run token ceiling of {token_ceiling} exceeded (consumed: {tokens_used_so_far})"
            )

        if self.provider == ProviderKind.DETERMINISTIC_MOCK:
            simulated_tokens = 150
            cost_cents = int(simulated_tokens * self.capabilities.cost_per_1k_tokens_cents / 1000)
            patch_content = (
                f"# Governed change applied by Keelway: {task_prompt}\n"
                f"def governed_feature() -> str:\n"
                f"    return 'keelway_verified'\n"
            )
            return {
                "file_path": "governed_module.py",
                "content": patch_content,
                "tokens_consumed": simulated_tokens,
                "cost_cents": max(1, cost_cents),
                "model_used": self.model_name,
                "provider": self.provider.value,
            }

        elif self.provider == ProviderKind.LOCAL_OLLAMA:
            url = f"{self.endpoint_url}/api/generate"
            payload = {
                "model": self.model_name,
                "prompt": f"Write the code patch for: {task_prompt}\nTarget files: {file_tree}",
                "stream": False,
            }
            try:
                with httpx.Client(timeout=timeout_seconds) as client:
                    resp = client.post(url, json=payload)
                    resp.raise_for_status()
                    data = resp.json()
                    tokens_consumed = data.get("prompt_eval_count", 50) + data.get("eval_count", 100)
                    response_text = data.get("response", "")
                    cost_cents = int(tokens_consumed * self.capabilities.cost_per_1k_tokens_cents / 1000)
                    return {
                        "file_path": "governed_module.py",
                        "content": response_text,
                        "tokens_consumed": tokens_consumed,
                        "cost_cents": cost_cents,
                        "model_used": self.model_name,
                        "provider": self.provider.value,
                    }
            except Exception as e:
                raise ModelGatewayError(f"Ollama generation failed: {e}") from e

        elif self.provider in (ProviderKind.LOCAL_VLLM, ProviderKind.OPENAI_COMPATIBLE):
            url = f"{self.endpoint_url}/v1/chat/completions"
            headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
            payload = {
                "model": self.model_name,
                "messages": [
                    {"role": "system", "content": "You are a governed code engineering agent."},
                    {"role": "user", "content": f"Task: {task_prompt}\nFiles: {file_tree}"},
                ],
            }
            try:
                with httpx.Client(timeout=timeout_seconds) as client:
                    resp = client.post(url, json=payload, headers=headers)
                    resp.raise_for_status()
                    data = resp.json()
                    usage = data.get("usage", {})
                    tokens_consumed = usage.get("total_tokens", 150)
                    content = data["choices"][0]["message"]["content"]
                    cost_cents = int(tokens_consumed * self.capabilities.cost_per_1k_tokens_cents / 1000)
                    return {
                        "file_path": "governed_module.py",
                        "content": content,
                        "tokens_consumed": tokens_consumed,
                        "cost_cents": cost_cents,
                        "model_used": self.model_name,
                        "provider": self.provider.value,
                    }
            except Exception as e:
                raise ModelGatewayError(f"OpenAI/vLLM completion failed: {e}") from e

        raise ModelGatewayError(f"Unsupported provider: {self.provider}")
