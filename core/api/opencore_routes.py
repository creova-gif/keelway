"""
Keelway OpenCore REST API Routes.

Exposes endpoints for OpenCore cluster telemetry, weight cache inspection,
model lifecycle (load/unload), local runtime discovery, Modelfile compilation,
LoRA hot-swap management, sovereign adaptation recipes, and direct inference.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from core.api.schemas import MessageSchema
from core.models.provider import ChatCompletionRequest, ChatCompletionResponse, ProviderError
from core.opencore.weights import (
    HardwareProfiler,
    QuantizationLevel,
    weight_manager,
)
from core.opencore.serving import (
    LoadedModelInfo,
    OpenCoreWorkerBackend,
    opencore_serving_engine,
)
from core.opencore.adaptation import (
    AdaptationConfig,
    AdaptationTask,
    DomainDatasetBuilder,
    generate_peft_config,
    generate_unsloth_recipe,
)
from core.opencore.runtime import (
    CANONICAL_MODEL_IDS,
    LoRAAdapterRecord,
    OpenCoreModelfileCompiler,
    build_ollama_create_command,
    lora_adapter_registry,
)

router = APIRouter(prefix="/v1/opencore", tags=["OpenCore"])


class LoadModelRequest(BaseModel):
    model_id: str = Field(..., description="Canonical model ID, e.g. 'keelway-core:7b'")
    quantization: Optional[QuantizationLevel] = Field(default=None)
    backend: Optional[OpenCoreWorkerBackend] = Field(default=OpenCoreWorkerBackend.MOCK)
    base_model_override: Optional[str] = Field(default=None)


class UnloadModelRequest(BaseModel):
    model_id: str = Field(..., description="Model ID to unload")


class CompileModelfileRequest(BaseModel):
    model_id: str = Field(default="keelway-core:7b")
    base_source: Optional[str] = Field(default=None)
    quantization: Optional[QuantizationLevel] = Field(default=QuantizationLevel.Q4_K_M)
    adapter_id: Optional[str] = Field(default=None)
    temperature: Optional[float] = Field(default=None)
    top_p: float = Field(default=0.9)
    num_ctx: Optional[int] = Field(default=None)
    modelfile_path: str = Field(default="./Modelfile")


class RegisterAdapterRequest(BaseModel):
    adapter_id: str = Field(..., description="Unique LoRA adapter ID")
    name: str = Field(..., description="Human-readable adapter name")
    base_model_id: str = Field(default="keelway-core:7b")
    task: AdaptationTask = Field(default=AdaptationTask.MULTILINGUAL_LOCALIZATION)
    languages: List[str] = Field(default_factory=lambda: ["english", "swahili"])
    adapter_path: str = Field(..., description="Local filesystem path to adapter weights")
    sha256_checksum: str = Field(..., description="Expected SHA-256 hex digest")
    lora_r: int = Field(default=16)
    lora_alpha: int = Field(default=32)
    verify_on_disk: bool = Field(default=False)


class AttachAdapterRequest(BaseModel):
    model_id: str = Field(..., description="Target OpenCore model ID")
    adapter_id: str = Field(..., description="Registered LoRA adapter ID to attach")
    verify_integrity: bool = Field(default=False)


class DetachAdapterRequest(BaseModel):
    model_id: str = Field(..., description="Target OpenCore model ID")


class OpenCoreInferRequest(BaseModel):
    model: str = Field(default="keelway-core:7b")
    model_id: Optional[str] = Field(default=None)
    messages: List[MessageSchema]
    temperature: float = Field(default=0.7)
    max_tokens: Optional[int] = Field(default=None)
    response_format: Optional[Dict[str, Any]] = Field(default=None)
    backend: Optional[OpenCoreWorkerBackend] = Field(default=None)
    base_model_override: Optional[str] = Field(default=None)


@router.get("/status")
async def get_opencore_status() -> Dict[str, Any]:
    """Retrieve active cluster telemetry, resident models, and host hardware detection."""
    hw = HardwareProfiler.detect()
    telemetry = opencore_serving_engine.get_cluster_telemetry()
    return {
        "status": "healthy",
        "hardware": hw.model_dump(),
        "telemetry": telemetry.model_dump(),
    }


@router.get("/weights")
async def list_opencore_weights() -> List[Dict[str, Any]]:
    """List canonical OpenCore weight manifests and their local disk cache status."""
    manifests = weight_manager.list_manifests()
    results = []
    for m in manifests:
        cached = weight_manager.is_cached(m)
        local_path = weight_manager.get_local_path(m)
        results.append({
            **m.model_dump(),
            "is_cached": cached,
            "local_path": str(local_path),
        })
    return results


@router.post("/models/load", response_model=LoadedModelInfo)
async def load_model_checkpoint(req: LoadModelRequest) -> LoadedModelInfo:
    """Load an OpenCore foundation model into accelerator memory."""
    try:
        info = await opencore_serving_engine.load_model(
            model_id=req.model_id,
            quantization=req.quantization,
            backend=req.backend or OpenCoreWorkerBackend.MOCK,
            base_model_override=req.base_model_override,
        )
        return info
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to load OpenCore model '{req.model_id}': {str(e)}",
        )


@router.post("/models/unload")
async def unload_model_checkpoint(req: UnloadModelRequest) -> Dict[str, Any]:
    """Unload an OpenCore model to reclaim accelerator memory."""
    success = await opencore_serving_engine.unload_model(req.model_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model '{req.model_id}' was not loaded.",
        )
    return {
        "model_id": req.model_id,
        "unloaded": True,
        "message": f"Successfully unloaded '{req.model_id}' from memory.",
    }


@router.post("/adapt/recipe")
async def generate_adaptation_recipe(config: AdaptationConfig) -> Dict[str, Any]:
    """Generate fine-tuning dataset and executable Unsloth/PEFT recipes for sovereign model training."""
    peft_cfg = generate_peft_config(config)
    unsloth_script = generate_unsloth_recipe(config)
    multilingual_samples = DomainDatasetBuilder.get_multilingual_samples(config.target_languages)

    return {
        "base_model_id": config.base_model_id,
        "task": config.task.value,
        "target_languages": [lang.value for lang in config.target_languages],
        "peft_config": peft_cfg,
        "unsloth_recipe": unsloth_script,
        "synthetic_sample_count": len(multilingual_samples),
        "sample_preview": multilingual_samples[:2],
    }


@router.get("/runtime/discover")
async def discover_local_runtimes(
    ollama_url: Optional[str] = Query(default=None),
    vllm_url: Optional[str] = Query(default=None),
    fallback_base_model: bool = Query(default=True),
) -> Dict[str, Any]:
    """Probe local Ollama & vLLM runtimes and return installed weights & recommended bindings."""
    ollama_probe = await opencore_serving_engine.discovery.discover_ollama(
        base_url=ollama_url or opencore_serving_engine.ollama_bridge.base_url,
        fallback_base_model=fallback_base_model,
        transport=opencore_serving_engine.ollama_bridge.transport,
    )
    vllm_probe = await opencore_serving_engine.discovery.discover_vllm(
        base_url=vllm_url or opencore_serving_engine.vllm_bridge.base_url,
        fallback_base_model=fallback_base_model,
        transport=opencore_serving_engine.vllm_bridge.transport,
    )
    cached_weights = [
        {
            "model_id": m.model_id,
            "quantization": m.quantization.value,
            "local_path": str(weight_manager.get_local_path(m)),
        }
        for m in weight_manager.list_manifests()
        if weight_manager.is_cached(m)
    ]
    recommended = {
        mid: (
            ollama_probe.recommended_bindings.get(mid)
            if ollama_probe.reachable
            else vllm_probe.recommended_bindings.get(mid)
        )
        for mid in CANONICAL_MODEL_IDS
    }
    return {
        "ollama": ollama_probe.model_dump(),
        "vllm": vllm_probe.model_dump(),
        "cached_weights": cached_weights,
        "recommended_bindings": recommended,
    }


@router.post("/modelfile")
async def compile_opencore_modelfile(req: CompileModelfileRequest) -> Dict[str, Any]:
    """Compile a deterministic Ollama Modelfile and CLI command for an OpenCore model."""
    compiler = OpenCoreModelfileCompiler(
        manager=opencore_serving_engine.weight_manager,
        adapter_registry=opencore_serving_engine.adapter_registry,
    )
    try:
        spec = compiler.build_spec(
            model_id=req.model_id,
            base_source=req.base_source,
            quantization=req.quantization,
            temperature=req.temperature,
            top_p=req.top_p,
            num_ctx=req.num_ctx,
            adapter_id=req.adapter_id,
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    modelfile_str = compiler.render(spec)
    cli_command = build_ollama_create_command(req.model_id, req.modelfile_path)
    return {
        "model_id": req.model_id,
        "spec": spec.model_dump(),
        "modelfile": modelfile_str,
        "cli_command": cli_command,
    }


@router.post("/adapters/register")
async def register_lora_adapter(req: RegisterAdapterRequest) -> Dict[str, Any]:
    """Register a sovereign LoRA adapter and optionally verify SHA-256 disk integrity."""
    registry = opencore_serving_engine.adapter_registry
    record = LoRAAdapterRecord(
        adapter_id=req.adapter_id,
        name=req.name,
        base_model_id=req.base_model_id,
        task=req.task,
        languages=req.languages,
        adapter_path=req.adapter_path,
        sha256_checksum=req.sha256_checksum,
        lora_r=req.lora_r,
        lora_alpha=req.lora_alpha,
    )
    try:
        saved = registry.register_adapter(record, verify_on_disk=req.verify_on_disk)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return {
        "adapter": saved.model_dump(),
        "integrity_verified": registry.verify_adapter_integrity(saved),
    }


@router.get("/adapters")
async def list_lora_adapters(
    base_model_id: Optional[str] = Query(default=None),
) -> Dict[str, Any]:
    """List registered sovereign LoRA adapters and active per-model attachments."""
    registry = opencore_serving_engine.adapter_registry
    attached_map = registry.get_attached_map()
    adapters = []
    for rec in registry.list_adapters(base_model_id=base_model_id):
        attached_to = [mid for mid, aid in attached_map.items() if aid == rec.adapter_id]
        adapters.append({
            **rec.model_dump(),
            "attached_models": attached_to,
            "is_attached": len(attached_to) > 0,
        })
    return {
        "adapters": adapters,
        "attached_by_model": attached_map,
    }


@router.post("/adapters/attach")
async def attach_lora_adapter(req: AttachAdapterRequest) -> Dict[str, Any]:
    """Hot-attach a registered LoRA adapter to an OpenCore model."""
    registry = opencore_serving_engine.adapter_registry
    try:
        rec = registry.attach_adapter(
            model_id=req.model_id,
            adapter_id=req.adapter_id,
            verify_integrity=req.verify_integrity,
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    info = opencore_serving_engine.get_model_info(req.model_id)
    if info is not None:
        info.attached_adapter_id = rec.adapter_id

    return {
        "model_id": req.model_id,
        "attached": True,
        "adapter": rec.model_dump(),
    }


@router.post("/adapters/detach")
async def detach_lora_adapter(req: DetachAdapterRequest) -> Dict[str, Any]:
    """Detach any active LoRA adapter from the specified OpenCore model."""
    detached = opencore_serving_engine.adapter_registry.detach_adapter(req.model_id)
    info = opencore_serving_engine.get_model_info(req.model_id)
    if info is not None:
        info.attached_adapter_id = None
    return {
        "model_id": req.model_id,
        "detached": detached,
    }


@router.post("/infer", response_model=ChatCompletionResponse)
async def infer_opencore_model(req: OpenCoreInferRequest) -> ChatCompletionResponse:
    """Execute direct inference through OpenCoreServingEngine (mock, Ollama, or vLLM)."""
    target_model = req.model_id or req.model
    req_kwargs: Dict[str, Any] = {
        "model": target_model,
        "messages": req.messages,
        "temperature": req.temperature,
        "response_format": req.response_format,
    }
    if req.max_tokens is not None:
        req_kwargs["max_tokens"] = req.max_tokens
    chat_req = ChatCompletionRequest(**req_kwargs)
    try:
        return await opencore_serving_engine.forward_inference(
            chat_req,
            backend=req.backend,
            base_model_override=req.base_model_override,
        )
    except ProviderError as exc:
        raise HTTPException(
            status_code=exc.status_code or status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
