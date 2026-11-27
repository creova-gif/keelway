"""
Keelway OpenCore — Real Neural Runtime Bridges, Modelfile Compiler & LoRA Registry.

Provides deterministic Ollama Modelfile compilation, cryptographic LoRA adapter
hot-swap tracking, local runtime discovery (Ollama & vLLM), and live neural
inference bridges with zero cloud egress ($0.00 cost).
"""

from __future__ import annotations

import hashlib
import json
import shlex
import time
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple, Union

import httpx
from pydantic import BaseModel, Field

from core.api.schemas import Provider
from core.config import settings
from core.models.provider import ChatCompletionRequest, ChatCompletionResponse, ProviderError, StreamChunk
from core.models.registry import ModelCategory
from core.opencore.adaptation import AdaptationTask, TargetLanguage
from core.opencore.weights import QuantizationLevel, WeightManager, weight_manager

CANONICAL_MODEL_IDS: Tuple[str, ...] = (
    "keelway-core:7b",
    "keelway-coder:7b",
    "keelway-reasoning:14b",
    "keelway-nano:1.5b",
)

ROLE_SYSTEM_PROMPTS: Dict[str, Tuple[str, float]] = {
    "coder": (
        "You are Keelway OpenCore Coder, a sovereign zero-egress software engineering model "
        "specialized in AST-verified code synthesis, strict type safety, and security invariants.",
        0.2,
    ),
    "reasoning": (
        "You are Keelway OpenCore Reasoning, a sovereign formal derivation engine. "
        "Always enclose explicit multi-step axiomatic derivations inside <thought>...</thought> "
        "blocks before stating your final verified conclusion.",
        0.3,
    ),
    "nano": (
        "You are Keelway OpenCore Nano, an ultra-low-latency sovereign edge and speculative-draft "
        "assistant. Respond with concise, direct, high-precision answers.",
        0.4,
    ),
    "core": (
        "You are Keelway OpenCore, a sovereign multilingual AI foundation model engineered for "
        "zero-egress privacy, systems architecture, and fluent reasoning across English, Swahili, "
        "Yoruba, Hausa, Amharic, and French.",
        0.7,
    ),
}


def build_ollama_create_command(model_id: str, modelfile_path: str) -> str:
    """Build a shell-safe `ollama create` CLI command for registering an OpenCore tag."""
    return f"ollama create {shlex.quote(model_id)} -f {shlex.quote(modelfile_path)}"


async def _post_local_json(
    base_url: str, path: str, payload: Dict[str, Any], transport: Optional[Any], timeout_s: float, label: str, model: str
) -> Tuple[Dict[str, Any], float]:
    t0 = time.perf_counter()
    try:
        timeout = httpx.Timeout(timeout_s, connect=min(timeout_s, 5.0))
        async with httpx.AsyncClient(base_url=base_url, transport=transport, timeout=timeout) as client:
            resp = await client.post(path, json=payload)
            resp.raise_for_status()
            data = resp.json()
    except httpx.TimeoutException as exc:
        raise ProviderError(
            f"{label} runtime timed out after {timeout_s}s at {base_url} for '{model}'",
            provider=Provider.LOCAL,
            status_code=503,
        ) from exc
    except httpx.HTTPStatusError as exc:
        raise ProviderError(
            f"{label} runtime HTTP {exc.response.status_code} for '{model}'",
            provider=Provider.LOCAL,
            status_code=exc.response.status_code,
        ) from exc
    except Exception as exc:
        raise ProviderError(f"{label} runtime unreachable at {base_url}: {exc}", provider=Provider.LOCAL, status_code=503) from exc
    return data, round((time.perf_counter() - t0) * 1000.0, 2)


class ModelfileSpec(BaseModel):
    """Specification for compiling an Ollama-compatible OpenCore Modelfile."""
    model_id: str
    base_source: str
    quantization: QuantizationLevel = QuantizationLevel.Q4_K_M
    temperature: float = 0.7
    top_p: float = 0.9
    num_ctx: int = 32768
    system_prompt: str
    stop_tokens: List[str] = Field(default_factory=lambda: ["<|im_end|>", "<|endoftext|>"])
    manifest_sha256: Optional[str] = None
    adapter_path: Optional[str] = None
    adapter_id: Optional[str] = None
    adapter_sha256: Optional[str] = None


class LoRAAdapterRecord(BaseModel):
    """Cryptographically verified descriptor for a sovereign PEFT / GGUF LoRA adapter."""
    adapter_id: str
    name: str
    base_model_id: str = "keelway-core:7b"
    task: AdaptationTask = AdaptationTask.MULTILINGUAL_LOCALIZATION
    languages: List[str] = Field(default_factory=lambda: [TargetLanguage.ENGLISH.value])
    adapter_path: str
    sha256_checksum: str
    lora_r: int = 16
    lora_alpha: int = 32
    created_at: float = Field(default_factory=time.time)


class LoRAAdapterRegistry:
    """Manages registration, SHA-256 integrity verification, and per-model LoRA hot-swapping."""

    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache_dir = cache_dir or (Path.home() / ".keelway" / "adapters")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._adapters: Dict[str, LoRAAdapterRecord] = {}
        self._attached_by_model: Dict[str, str] = {}

    def register_adapter(
        self, record: Optional[LoRAAdapterRecord] = None, *, verify_on_disk: bool = False, **kwargs: Any
    ) -> LoRAAdapterRecord:
        adapter = record if record is not None else LoRAAdapterRecord(**kwargs)
        if verify_on_disk and not self.verify_adapter_integrity(adapter):
            raise ValueError(f"SHA-256 integrity verification failed for LoRA adapter '{adapter.adapter_id}'")
        self._adapters[adapter.adapter_id] = adapter
        return adapter

    def get_adapter(self, adapter_id: str) -> Optional[LoRAAdapterRecord]:
        return self._adapters.get(adapter_id)

    def list_adapters(self, base_model_id: Optional[str] = None) -> List[LoRAAdapterRecord]:
        if base_model_id:
            return [a for a in self._adapters.values() if a.base_model_id == base_model_id]
        return list(self._adapters.values())

    def get_attached_map(self) -> Dict[str, str]:
        return dict(self._attached_by_model)

    def verify_adapter_integrity(self, adapter: Union[str, LoRAAdapterRecord]) -> bool:
        rec = self._adapters.get(adapter) if isinstance(adapter, str) else adapter
        return bool(rec and WeightManager.verify_checksum(Path(rec.adapter_path), rec.sha256_checksum))

    def attach_adapter(self, model_id: str, adapter_id: str, verify_integrity: bool = False) -> LoRAAdapterRecord:
        rec = self._adapters.get(adapter_id)
        if rec is None:
            raise KeyError(f"LoRA adapter '{adapter_id}' is not registered")
        if rec.base_model_id != model_id:
            raise ValueError(f"LoRA adapter '{adapter_id}' targets '{rec.base_model_id}', cannot attach to '{model_id}'")
        if verify_integrity and not self.verify_adapter_integrity(rec):
            raise ValueError(f"LoRA adapter '{adapter_id}' failed SHA-256 checksum verification on disk")
        self._attached_by_model[model_id] = adapter_id
        return rec

    def detach_adapter(self, model_id: str) -> bool:
        return self._attached_by_model.pop(model_id, None) is not None

    def get_attached_adapter(self, model_id: str) -> Optional[LoRAAdapterRecord]:
        aid = self._attached_by_model.get(model_id)
        return self._adapters.get(aid) if aid else None

    def create_mock_adapter_for_testing(
        self,
        adapter_id: str = "lora-swahili-v1",
        base_model_id: str = "keelway-core:7b",
        directory: Optional[Path] = None,
        name: str = "Keelway Sovereign Multilingual LoRA",
        task: AdaptationTask = AdaptationTask.MULTILINGUAL_LOCALIZATION,
        languages: Optional[List[str]] = None,
        lora_r: int = 16,
        lora_alpha: int = 32,
        content: bytes = b"MOCK_GGUF_LORA_ADAPTER_V1_WEIGHTS",
    ) -> LoRAAdapterRecord:
        target_dir = directory or self.cache_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        file_path = target_dir / f"{adapter_id.replace(':', '_')}.safetensors"
        file_path.write_bytes(content)
        rec = LoRAAdapterRecord(
            adapter_id=adapter_id,
            name=name,
            base_model_id=base_model_id,
            task=task,
            languages=languages or ["swahili", "yoruba", "english"],
            adapter_path=str(file_path),
            sha256_checksum=hashlib.sha256(content).hexdigest(),
            lora_r=lora_r,
            lora_alpha=lora_alpha,
        )
        return self.register_adapter(rec, verify_on_disk=True)


class OpenCoreModelfileCompiler:
    """Compiles deterministic Ollama Modelfiles with role prompts, SHA-256 headers, and LoRA adapters."""

    def __init__(self, manager: Optional[WeightManager] = None, adapter_registry: Optional[LoRAAdapterRegistry] = None):
        self.weight_manager = manager or weight_manager
        self.adapter_registry = adapter_registry or lora_adapter_registry

    @staticmethod
    def get_role_defaults(model_id: str) -> Tuple[str, float]:
        low = model_id.lower()
        for key in ("coder", "reasoning", "nano"):
            if key in low:
                return ROLE_SYSTEM_PROMPTS[key]
        return ROLE_SYSTEM_PROMPTS["core"]

    def build_spec(
        self,
        model_id: str,
        base_source: Optional[str] = None,
        quantization: Optional[QuantizationLevel] = None,
        temperature: Optional[float] = None,
        top_p: float = 0.9,
        num_ctx: Optional[int] = None,
        system_prompt: Optional[str] = None,
        stop_tokens: Optional[List[str]] = None,
        adapter_path: Optional[str] = None,
        adapter_id: Optional[str] = None,
    ) -> ModelfileSpec:
        quant = quantization or QuantizationLevel.Q4_K_M
        manifest = self.weight_manager.get_manifest(model_id, quant)
        if manifest is None:
            candidates = self.weight_manager.list_manifests(model_id)
            if candidates:
                manifest, quant = candidates[0], candidates[0].quantization

        default_prompt, default_temp = self.get_role_defaults(model_id)
        resolved_source = base_source or (str(self.weight_manager.get_local_path(manifest)) if manifest else "qwen3.5:latest")
        res_adapter_path, res_adapter_sha, res_adapter_id = adapter_path, None, adapter_id
        if adapter_id and not res_adapter_path:
            rec = self.adapter_registry.get_adapter(adapter_id)
            if rec is None:
                raise KeyError(f"LoRA adapter '{adapter_id}' not found in registry")
            res_adapter_path, res_adapter_sha = rec.adapter_path, rec.sha256_checksum
        elif not adapter_id and not res_adapter_path:
            attached = self.adapter_registry.get_attached_adapter(model_id)
            if attached:
                res_adapter_id, res_adapter_path, res_adapter_sha = attached.adapter_id, attached.adapter_path, attached.sha256_checksum

        return ModelfileSpec(
            model_id=model_id,
            base_source=resolved_source,
            quantization=quant,
            temperature=default_temp if temperature is None else temperature,
            top_p=top_p,
            num_ctx=num_ctx or (manifest.context_length if manifest else 32768),
            system_prompt=system_prompt or default_prompt,
            stop_tokens=stop_tokens if stop_tokens is not None else ["<|im_end|>", "<|endoftext|>"],
            manifest_sha256=manifest.sha256_checksum if manifest else None,
            adapter_path=res_adapter_path,
            adapter_id=res_adapter_id,
            adapter_sha256=res_adapter_sha,
        )

    @staticmethod
    def render(spec: ModelfileSpec) -> str:
        lines = [
            "# Keelway OpenCore Sovereign Modelfile",
            f"# Model ID: {spec.model_id}",
            f"# Quantization: {spec.quantization.value}",
            f"# SHA-256 Manifest Checksum: {spec.manifest_sha256 or 'external-base-tag'}",
        ]
        if spec.adapter_id or spec.adapter_sha256:
            lines.append(f"# LoRA Adapter: {spec.adapter_id or 'custom'} (sha256={spec.adapter_sha256 or 'unverified'})")
        lines.append(f"FROM {spec.base_source}")
        if spec.adapter_path:
            lines.append(f"ADAPTER {spec.adapter_path}")
        lines.extend([
            f"PARAMETER temperature {spec.temperature}",
            f"PARAMETER top_p {spec.top_p}",
            f"PARAMETER num_ctx {spec.num_ctx}",
        ])
        for tok in spec.stop_tokens:
            lines.append(f'STOP "{tok.replace(chr(34), chr(92) + chr(34))}"')
        lines.append(f'SYSTEM """{spec.system_prompt}"""')
        return "\n".join(lines) + "\n"

    def compile(self, spec_or_model_id: Union[ModelfileSpec, str], **kwargs: Any) -> str:
        spec = spec_or_model_id if isinstance(spec_or_model_id, ModelfileSpec) else self.build_spec(spec_or_model_id, **kwargs)
        return self.render(spec)

    build_ollama_create_command = staticmethod(build_ollama_create_command)


class RuntimeProbeResult(BaseModel):
    """Discovery snapshot of a local open-weight serving runtime (Ollama or vLLM)."""
    runtime: str
    base_url: str
    reachable: bool
    installed_models: List[str] = Field(default_factory=list)
    recommended_bindings: Dict[str, Optional[str]] = Field(default_factory=dict)
    error: Optional[str] = None


class LocalRuntimeDiscovery:
    """Probes local Ollama and vLLM endpoints and maps OpenCore tags to resident weights."""

    ROLE_FALLBACK_PREFIXES: Dict[str, Tuple[str, ...]] = {
        "coder": ("keelway-coder", "qwen2.5-coder", "qwen3-coder", "codestral", "deepseek-coder", "qwen3.5", "qwen3", "qwen2.5", "llama3"),
        "reasoning": ("keelway-reasoning", "deepseek-r1", "qwq", "qwen3.5", "qwen3", "qwen2.5", "llama3"),
        "nano": ("keelway-nano", "qwen2.5:1.5b", "qwen2.5:0.5b", "llama3.2:1b", "smollm", "qwen3.5", "qwen3", "qwen2.5", "llama3"),
        "core": ("keelway-core", "qwen3.5", "qwen3", "qwen2.5", "llama3.3", "llama3.2", "llama3.1", "llama3", "mistral", "gemma"),
    }

    def __init__(self, transport: Optional[Any] = None, timeout_s: float = 2.5):
        self.transport = transport
        self.timeout_s = timeout_s

    @classmethod
    def resolve_compatible_model(cls, model_id: str, installed_models: List[str], fallback_base_model: bool = True) -> Optional[str]:
        if model_id in installed_models:
            return model_id
        if not fallback_base_model or not installed_models:
            return None
        role = next((r for r in ("coder", "reasoning", "nano") if r in model_id.lower()), "core")
        for prefix in cls.ROLE_FALLBACK_PREFIXES[role]:
            for tag in installed_models:
                if tag.lower().startswith(prefix):
                    return tag
        return installed_models[0]

    async def _probe(
        self, runtime: str, base_url: str, path: str, extractor: Any, fallback_base_model: bool, transport: Optional[Any]
    ) -> RuntimeProbeResult:
        try:
            async with httpx.AsyncClient(base_url=base_url, transport=transport or self.transport, timeout=self.timeout_s) as client:
                resp = await client.get(path)
                resp.raise_for_status()
                tags = extractor(resp.json())
            bindings = {mid: self.resolve_compatible_model(mid, tags, fallback_base_model) for mid in CANONICAL_MODEL_IDS}
            return RuntimeProbeResult(runtime=runtime, base_url=base_url, reachable=True, installed_models=tags, recommended_bindings=bindings)
        except Exception as exc:
            return RuntimeProbeResult(
                runtime=runtime, base_url=base_url, reachable=False, recommended_bindings={mid: None for mid in CANONICAL_MODEL_IDS}, error=str(exc)
            )

    async def discover_ollama(
        self, base_url: Optional[str] = None, fallback_base_model: bool = True, transport: Optional[Any] = None
    ) -> RuntimeProbeResult:
        return await self._probe(
            "ollama", base_url or settings.ollama_base_url, "/api/tags",
            lambda p: [str(i.get("name") or i.get("model")) for i in p.get("models", []) if isinstance(i, dict) and (i.get("name") or i.get("model"))],
            fallback_base_model, transport,
        )

    async def discover_vllm(
        self, base_url: str = "http://127.0.0.1:8000", fallback_base_model: bool = True, transport: Optional[Any] = None
    ) -> RuntimeProbeResult:
        return await self._probe(
            "vllm", base_url, "/v1/models",
            lambda p: [str(i.get("id")) for i in p.get("data", []) if isinstance(i, dict) and i.get("id")],
            fallback_base_model, transport,
        )


class OllamaRuntimeBridge:
    """Live neural inference bridge to local Ollama (`/api/chat`) at $0.00 sovereign cost."""

    def __init__(self, base_url: Optional[str] = None, transport: Optional[Any] = None, timeout_s: float = 30.0):
        self.base_url = base_url or settings.ollama_base_url
        self.transport = transport
        self.timeout_s = timeout_s

    def _build_chat_payload(
        self, request: ChatCompletionRequest, target_model: str, stream: bool, system_override: Optional[str] = None
    ) -> Dict[str, Any]:
        messages = [{"role": m.role, "content": m.content} for m in request.messages]
        if system_override:
            if messages and messages[0]["role"] == "system":
                messages[0] = {"role": "system", "content": f"{system_override}\n\n{messages[0]['content']}"}
            else:
                messages.insert(0, {"role": "system", "content": system_override})
        options: Dict[str, Any] = {"temperature": request.temperature}
        max_toks = request.max_completion_tokens or request.max_tokens
        if max_toks is not None:
            options["num_predict"] = max_toks
        use_think = "reasoning" in (request.model or "").lower() or "complex_reasoning" in request.required_capabilities
        payload: Dict[str, Any] = {"model": target_model, "messages": messages, "stream": stream, "think": use_think, "options": options}
        resp_fmt = getattr(request, "response_format", None)
        if isinstance(resp_fmt, dict) and resp_fmt.get("type") == "json_object":
            payload["format"] = "json"
        return payload

    async def generate(
        self, request: ChatCompletionRequest, resolved_base_model: Optional[str] = None, system_override: Optional[str] = None
    ) -> ChatCompletionResponse:
        target_model = resolved_base_model or request.model or "keelway-core:7b"
        payload = self._build_chat_payload(request, target_model, stream=False, system_override=system_override)
        data, latency_ms = await _post_local_json(self.base_url, "/api/chat", payload, self.transport, self.timeout_s, "Ollama", target_model)
        msg = data.get("message") or {}
        content = str((msg.get("content") or msg.get("thinking") or "") if isinstance(msg, dict) else data.get("response", ""))
        p_tok, c_tok = int(data.get("prompt_eval_count") or 0), int(data.get("eval_count") or 0)
        finish = str(data.get("done_reason") or ("stop" if data.get("done", True) else "length"))
        return ChatCompletionResponse(
            id=f"chatcmpl-ollama-{int(time.time() * 1000)}",
            object="chat.completion",
            created=int(time.time()),
            model=request.model or target_model,
            provider=Provider.LOCAL,
            category=ModelCategory.OPEN_WEIGHT,
            content=content,
            finish_reason=finish,
            usage={"prompt_tokens": p_tok, "completion_tokens": c_tok, "total_tokens": p_tok + c_tok},
            latency_ms=latency_ms,
            cost_usd=0.0,
            routing_reason=f"Keelway OpenCore Ollama Bridge (runtime_model={target_model}, $0.00 local sovereign weights)",
        )

    async def stream_generate(
        self, request: ChatCompletionRequest, resolved_base_model: Optional[str] = None, system_override: Optional[str] = None
    ) -> AsyncIterator[StreamChunk]:
        target_model = resolved_base_model or request.model or "keelway-core:7b"
        payload = self._build_chat_payload(request, target_model, stream=True, system_override=system_override)
        chunk_id, created_ts = f"chatcmpl-ollama-stream-{int(time.time() * 1000)}", int(time.time())
        try:
            timeout = httpx.Timeout(self.timeout_s, connect=min(self.timeout_s, 5.0))
            async with httpx.AsyncClient(base_url=self.base_url, transport=self.transport, timeout=timeout) as client:
                async with client.stream("POST", "/api/chat", json=payload) as resp:
                    resp.raise_for_status()
                    async for raw_line in resp.aiter_lines():
                        if not raw_line.strip():
                            continue
                        item = json.loads(raw_line)
                        msg = item.get("message") or {}
                        done = bool(item.get("done", False))
                        p_tok, c_tok = int(item.get("prompt_eval_count") or 0), int(item.get("eval_count") or 0)
                        yield StreamChunk(
                            id=chunk_id,
                            created=created_ts,
                            model=request.model or target_model,
                            provider=Provider.LOCAL,
                            delta_content=str(msg.get("content", "")) if isinstance(msg, dict) else "",
                            finish_reason=str(item.get("done_reason") or "stop") if done else None,
                            usage={"prompt_tokens": p_tok, "completion_tokens": c_tok, "total_tokens": p_tok + c_tok} if done else None,
                        )
        except httpx.HTTPStatusError as exc:
            raise ProviderError(
                f"Ollama streaming HTTP {exc.response.status_code} for '{target_model}'",
                provider=Provider.LOCAL,
                status_code=exc.response.status_code,
            ) from exc
        except Exception as exc:
            raise ProviderError(f"Ollama streaming error at {self.base_url}: {exc}", provider=Provider.LOCAL, status_code=503) from exc


class VLLMRuntimeBridge:
    """Live OpenAI-compatible neural bridge to local vLLM (`/v1/chat/completions`) at $0.00 cost."""

    def __init__(self, base_url: str = "http://127.0.0.1:8000", transport: Optional[Any] = None, timeout_s: float = 60.0):
        self.base_url = base_url
        self.transport = transport
        self.timeout_s = timeout_s

    async def generate(self, request: ChatCompletionRequest, resolved_model: Optional[str] = None) -> ChatCompletionResponse:
        target_model = resolved_model or request.model or "keelway-core:7b"
        payload: Dict[str, Any] = {
            "model": target_model,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            "temperature": request.temperature,
            "stream": False,
        }
        max_toks = request.max_completion_tokens or request.max_tokens
        if max_toks is not None:
            payload["max_tokens"] = max_toks
        if getattr(request, "response_format", None):
            payload["response_format"] = request.response_format

        data, latency_ms = await _post_local_json(self.base_url, "/v1/chat/completions", payload, self.transport, self.timeout_s, "vLLM", target_model)
        first = (data.get("choices") or [{}])[0]
        raw_usage = data.get("usage") or {}
        p_tok, c_tok = int(raw_usage.get("prompt_tokens") or 0), int(raw_usage.get("completion_tokens") or 0)
        return ChatCompletionResponse(
            id=str(data.get("id") or f"chatcmpl-vllm-{int(time.time() * 1000)}"),
            object="chat.completion",
            created=int(data.get("created") or time.time()),
            model=request.model or target_model,
            provider=Provider.LOCAL,
            category=ModelCategory.OPEN_WEIGHT,
            content=str((first.get("message") or {}).get("content") or ""),
            finish_reason=str(first.get("finish_reason") or "stop"),
            usage={"prompt_tokens": p_tok, "completion_tokens": c_tok, "total_tokens": int(raw_usage.get("total_tokens") or (p_tok + c_tok))},
            latency_ms=latency_ms,
            cost_usd=0.0,
            routing_reason=f"Keelway OpenCore vLLM Bridge (runtime_model={target_model}, $0.00 local sovereign weights)",
        )


lora_adapter_registry = LoRAAdapterRegistry()
modelfile_compiler = OpenCoreModelfileCompiler()
runtime_discovery = LocalRuntimeDiscovery()
