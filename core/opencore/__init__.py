"""
Keelway OpenCore Subsystem.

Exposes model weights, hardware quantization profiling, serving engine,
real neural runtime bridges, Modelfile compilation, LoRA hot-swapping,
and sovereign adaptation capabilities for Keelway foundation models.
"""

from core.opencore.weights import (
    CANONICAL_OPENCORE_MANIFESTS,
    HardwareProfile,
    HardwareProfiler,
    QuantizationLevel,
    WeightFormat,
    WeightManager,
    WeightManifest,
    weight_manager,
)
from core.opencore.serving import (
    ClusterTelemetry,
    LoadedModelInfo,
    OpenCoreServingEngine,
    OpenCoreWorkerBackend,
    OpenCoreWorkerStatus,
    opencore_serving_engine,
)
from core.opencore.adaptation import (
    AdaptationConfig,
    AdaptationTask,
    DomainDatasetBuilder,
    TargetLanguage,
    generate_peft_config,
    generate_unsloth_recipe,
)
from core.opencore.runtime import (
    CANONICAL_MODEL_IDS,
    LoRAAdapterRecord,
    LoRAAdapterRegistry,
    LocalRuntimeDiscovery,
    ModelfileSpec,
    OllamaRuntimeBridge,
    OpenCoreModelfileCompiler,
    RuntimeProbeResult,
    VLLMRuntimeBridge,
    build_ollama_create_command,
    lora_adapter_registry,
    modelfile_compiler,
    runtime_discovery,
)

__all__ = [
    "CANONICAL_OPENCORE_MANIFESTS",
    "CANONICAL_MODEL_IDS",
    "HardwareProfile",
    "HardwareProfiler",
    "QuantizationLevel",
    "WeightFormat",
    "WeightManager",
    "WeightManifest",
    "weight_manager",
    "ClusterTelemetry",
    "LoadedModelInfo",
    "OpenCoreServingEngine",
    "OpenCoreWorkerBackend",
    "OpenCoreWorkerStatus",
    "opencore_serving_engine",
    "AdaptationConfig",
    "AdaptationTask",
    "DomainDatasetBuilder",
    "TargetLanguage",
    "generate_peft_config",
    "generate_unsloth_recipe",
    "LoRAAdapterRecord",
    "LoRAAdapterRegistry",
    "LocalRuntimeDiscovery",
    "ModelfileSpec",
    "OllamaRuntimeBridge",
    "OpenCoreModelfileCompiler",
    "RuntimeProbeResult",
    "VLLMRuntimeBridge",
    "build_ollama_create_command",
    "lora_adapter_registry",
    "modelfile_compiler",
    "runtime_discovery",
]
