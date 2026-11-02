"""
Local / Edge Model Adapter: Ollama, or any OpenAI-compatible local server (vLLM, llama.cpp, LM Studio).

The server and its installed models are discovered at runtime, so the gateway only routes to
local when something is actually listening, and uses a model that is actually installed.
"""

import functools
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import httpx

from core.api.schemas import CompletionRequestSchema, CompletionResponseSchema, Provider
from core.models.adapters.base import ModelAdapter
from core.config import settings

PROBE_TIMEOUT_S = 0.5
UP_TTL_S = 30.0
DOWN_TTL_S = 5.0


@dataclass
class LocalRuntime:
    api: Optional[str]  # "ollama" | "openai" | None when nothing answered
    models: List[str] = field(default_factory=list)
    checked_at: float = 0.0

    @property
    def up(self) -> bool:
        return self.api is not None


def _is_chat_model(entry: Dict[str, Any]) -> bool:
    """Ollama lists embedding models (nomic-embed-text, bge-m3, all-minilm...) alongside chat models; /api/chat rejects them."""
    name = str(entry.get("name", "")).lower()
    details = entry.get("details") or {}
    families = [str(f).lower() for f in (details.get("families") or [details.get("family") or ""])]
    return "embed" not in name and not any("bert" in f for f in families)


@functools.lru_cache(maxsize=1)
def _recommended_model() -> str:
    from core.models.edge_loader import EdgeRuntimeManager
    return EdgeRuntimeManager().detect_hardware().recommended_model


class LocalAdapter(ModelAdapter):
    provider = Provider.LOCAL

    def __init__(
        self,
        base_url: Optional[str] = None,
        default_model: Optional[str] = None,
        api: Optional[str] = None,
        transport: Optional[httpx.BaseTransport] = None,
    ):
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.default_model = default_model or settings.default_local_model
        self.api = (api or settings.local_api).lower()
        self._transport = transport
        self._runtime: Optional[LocalRuntime] = None

    def _probe(self) -> LocalRuntime:
        kinds = ["ollama", "openai"] if self.api == "auto" else [self.api]
        with httpx.Client(timeout=PROBE_TIMEOUT_S, transport=self._transport) as client:
            for kind in kinds:
                try:
                    if kind == "ollama":
                        r = client.get(f"{self.base_url}/api/tags")
                        if r.status_code == 200:
                            return LocalRuntime("ollama", [m["name"] for m in r.json().get("models", []) if m.get("name") and _is_chat_model(m)])
                    else:
                        r = client.get(f"{self.base_url}/v1/models")
                        if r.status_code == 200:
                            return LocalRuntime("openai", [m["id"] for m in r.json().get("data", []) if m.get("id")])
                except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError):
                    continue
        return LocalRuntime(None)

    def runtime(self, refresh: bool = False) -> LocalRuntime:
        rt = self._runtime
        ttl = UP_TTL_S if rt and rt.up else DOWN_TTL_S
        if refresh or rt is None or time.monotonic() - rt.checked_at > ttl:
            rt = self._probe()
            rt.checked_at = time.monotonic()
            self._runtime = rt
        return rt

    def resolve_model(self) -> str:
        """Configured model if installed, else the hardware-recommended one, else whatever is installed."""
        installed = self.runtime().models
        if not installed:
            return self.default_model
        for want in (self.default_model, _recommended_model()):
            for name in installed:
                if name == want or name == f"{want}:latest" or name.split(":latest")[0] == want:
                    return name
        return installed[0]

    def is_available(self) -> bool:
        return self.runtime().up

    def describe(self) -> Dict[str, Any]:
        rt = self.runtime()
        return {
            "up": rt.up,
            "api": rt.api,
            "endpoint": self.base_url,
            "model": self.resolve_model() if rt.up else None,
            "installed": rt.models,
            "recommended": _recommended_model(),
        }

    async def complete(self, request: CompletionRequestSchema) -> CompletionResponseSchema:
        rt = self.runtime()
        if not rt.up:
            raise RuntimeError(f"No local model server answering at {self.base_url} (start Ollama or vLLM).")
        model = self.resolve_model()
        messages = [{"role": m.role, "content": m.content} for m in request.messages]
        if rt.api == "ollama":
            url = f"{self.base_url}/api/chat"
            payload: Dict[str, Any] = {
                "model": model,
                "messages": messages,
                "stream": False,
                "options": {"temperature": request.temperature, "num_predict": request.max_tokens},
            }
        else:
            url = f"{self.base_url}/v1/chat/completions"
            payload = {"model": model, "messages": messages, "temperature": request.temperature, "max_tokens": request.max_tokens}

        start_time = time.perf_counter()
        timeout_val = max(settings.default_timeout_seconds, 180.0)
        try:
            async with httpx.AsyncClient(timeout=timeout_val, transport=self._transport) as client:
                resp = await client.post(url, json=payload)
        except httpx.TimeoutException:
            raise RuntimeError(f"Local model generation timed out after {timeout_val:.0f}s.")
        except httpx.HTTPError as e:
            self._runtime = None
            raise RuntimeError(f"Local model server unreachable: {e}")
        latency_ms = (time.perf_counter() - start_time) * 1000.0

        if resp.status_code == 404 and rt.api == "ollama":
            raise RuntimeError(f"Local model '{model}' is not installed. Run: ollama pull {_recommended_model()}")
        if resp.status_code != 200:
            raise RuntimeError(f"Local runtime error ({resp.status_code}): {resp.text[:500]}")
        data = resp.json()

        if rt.api == "ollama":
            content = data.get("message", {}).get("content", "")
            prompt_tokens = data.get("prompt_eval_count", 0)
            completion_tokens = data.get("eval_count", 0)
        else:
            choices = data.get("choices") or [{}]
            content = (choices[0].get("message") or {}).get("content") or ""
            usage = data.get("usage") or {}
            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)

        return CompletionResponseSchema(
            content=content,
            provider=self.provider,
            model=data.get("model", model),
            usage={
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
            latency_ms=round(latency_ms, 2),
            cost_usd=0.0,
        )
