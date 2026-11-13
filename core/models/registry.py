"""
Keelway Centralized Model Registry.

Provides a unified, metadata-rich catalog for both Open-Weight and Closed/Proprietary AI models.
Tracks model identity, provider, deployment type, context window, capabilities,
streaming support, tool-calling support, structured output support, licensing, and pricing.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from core.api.schemas import Provider


class ModelCategory(str, Enum):
    OPEN_WEIGHT = "open_weight"
    CLOSED_PROPRIETARY = "closed_proprietary"


class ModelFamily(str, Enum):
    KEELWAY_CORE = "keelway_core"
    LLAMA = "llama"
    QWEN = "qwen"
    MISTRAL = "mistral"
    DEEPSEEK = "deepseek"
    GEMMA = "gemma"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    OTHER = "other"


class DeploymentType(str, Enum):
    LOCAL_DAEMON = "local_daemon"         # E.g. Ollama, local llama.cpp
    SELF_HOSTED_GPU = "self_hosted_gpu"   # E.g. vLLM, TGI in VPC/cluster
    MANAGED_CLOUD_API = "managed_cloud_api" # E.g. OpenAI, Anthropic, Google Gemini


class ModelMetadata(BaseModel):
    """Normalized metadata descriptor for a model in the Keelway platform."""
    id: str = Field(..., description="Unique model identifier, e.g. 'qwen2.5-coder:7b' or 'gpt-4o'")
    name: str = Field(..., description="Human-readable display name")
    provider: Provider = Field(..., description="Provider enum identifier")
    category: ModelCategory = Field(..., description="open_weight or closed_proprietary")
    family: ModelFamily = Field(default=ModelFamily.OTHER, description="Model architectural family")
    deployment: DeploymentType = Field(..., description="Deployment topology")
    context_window: int = Field(..., description="Maximum context length in tokens")
    max_output_tokens: int = Field(default=4096, description="Maximum generation output tokens")
    capabilities: List[str] = Field(default_factory=list, description="Supported capabilities: chat, streaming, tools, structured_output, code, reasoning, vision")
    supports_streaming: bool = Field(default=True, description="Whether streaming generation is supported")
    supports_tools: bool = Field(default=False, description="Whether tool calling / function calling is supported")
    supports_structured_output: bool = Field(default=False, description="Whether JSON schema / structured output is supported")
    modalities: List[str] = Field(default_factory=lambda: ["text"], description="Supported modalities: text, vision, audio")
    pricing_input_usd_per_mtok: float = Field(default=0.0, description="Input price in USD per million tokens")
    pricing_output_usd_per_mtok: float = Field(default=0.0, description="Output price in USD per million tokens")
    license: str = Field(..., description="License identifier or commercial terms, e.g. 'Apache-2.0', 'Llama-3.3-Community', 'Proprietary'")
    recommended_vram_gb: Optional[float] = Field(default=None, description="Recommended VRAM in GB for open-weight weights")
    description: str = Field(default="", description="Summary of model architecture and primary use cases")
    is_active: bool = Field(default=True, description="Whether model is actively available for routing")
    version: str = Field(default="1.0", description="Model version or checkpoint revision")


# Pre-seeded canonical models for Keelway platform
CANONICAL_MODELS: List[ModelMetadata] = [
    # --------------------------------------------------------------------------
    # Keelway OpenCore Models (Sovereign Open-Weight Suite)
    # --------------------------------------------------------------------------
    ModelMetadata(
        id="keelway-core:7b",
        name="Keelway OpenCore 7B",
        provider=Provider.LOCAL,
        category=ModelCategory.OPEN_WEIGHT,
        family=ModelFamily.KEELWAY_CORE,
        deployment=DeploymentType.LOCAL_DAEMON,
        context_window=65536,
        max_output_tokens=8192,
        capabilities=["chat", "streaming", "reasoning", "code", "structured_output", "multilingual"],
        supports_streaming=True,
        supports_tools=True,
        supports_structured_output=True,
        modalities=["text"],
        pricing_input_usd_per_mtok=0.0,
        pricing_output_usd_per_mtok=0.0,
        license="Apache-2.0",
        recommended_vram_gb=6.0,
        description="Keelway sovereign open-weight foundation model. Optimized for local reasoning, instruction following, and multilingual workflows.",
    ),
    ModelMetadata(
        id="keelway-coder:7b",
        name="Keelway OpenCore Coder 7B",
        provider=Provider.LOCAL,
        category=ModelCategory.OPEN_WEIGHT,
        family=ModelFamily.KEELWAY_CORE,
        deployment=DeploymentType.LOCAL_DAEMON,
        context_window=65536,
        max_output_tokens=8192,
        capabilities=["chat", "streaming", "code", "tools", "structured_output"],
        supports_streaming=True,
        supports_tools=True,
        supports_structured_output=True,
        modalities=["text"],
        pricing_input_usd_per_mtok=0.0,
        pricing_output_usd_per_mtok=0.0,
        license="Apache-2.0",
        recommended_vram_gb=6.0,
        description="Keelway sovereign code intelligence model specialized in full-stack synthesis, refactoring, and test harness generation.",
    ),
    ModelMetadata(
        id="keelway-reasoning:14b",
        name="Keelway OpenCore Reasoning 14B",
        provider=Provider.LOCAL,
        category=ModelCategory.OPEN_WEIGHT,
        family=ModelFamily.KEELWAY_CORE,
        deployment=DeploymentType.SELF_HOSTED_GPU,
        context_window=131072,
        max_output_tokens=16384,
        capabilities=["chat", "streaming", "reasoning", "code", "structured_output"],
        supports_streaming=True,
        supports_tools=True,
        supports_structured_output=True,
        modalities=["text"],
        pricing_input_usd_per_mtok=0.0,
        pricing_output_usd_per_mtok=0.0,
        license="Apache-2.0",
        recommended_vram_gb=12.0,
        description="Deep chain-of-thought mathematical, algorithmic, and architectural derivation model with verified step-by-step proofs.",
    ),
    ModelMetadata(
        id="keelway-nano:1.5b",
        name="Keelway OpenCore Nano 1.5B (Edge Draft)",
        provider=Provider.LOCAL,
        category=ModelCategory.OPEN_WEIGHT,
        family=ModelFamily.KEELWAY_CORE,
        deployment=DeploymentType.LOCAL_DAEMON,
        context_window=32768,
        max_output_tokens=4096,
        capabilities=["chat", "streaming", "code"],
        supports_streaming=True,
        supports_tools=False,
        supports_structured_output=True,
        modalities=["text"],
        pricing_input_usd_per_mtok=0.0,
        pricing_output_usd_per_mtok=0.0,
        license="Apache-2.0",
        recommended_vram_gb=1.8,
        description="Ultra-compact edge draft model designed for speculative lookahead decoding and low-power African edge nodes.",
    ),
    # --------------------------------------------------------------------------
    # Open-Weight Models (First-Class Citizens)
    # --------------------------------------------------------------------------
    ModelMetadata(
        id="qwen2.5-coder:7b",
        name="Qwen 2.5 Coder 7B",
        provider=Provider.LOCAL,
        category=ModelCategory.OPEN_WEIGHT,
        family=ModelFamily.QWEN,
        deployment=DeploymentType.LOCAL_DAEMON,
        context_window=32768,
        max_output_tokens=8192,
        capabilities=["chat", "streaming", "code", "structured_output"],
        supports_streaming=True,
        supports_tools=True,
        supports_structured_output=True,
        modalities=["text"],
        pricing_input_usd_per_mtok=0.0,
        pricing_output_usd_per_mtok=0.0,
        license="Apache-2.0",
        recommended_vram_gb=6.0,
        description="High-efficiency code intelligence open-weight model by Alibaba Cloud. Zero-cost local inference.",
    ),
    ModelMetadata(
        id="qwen2.5-coder:1.5b",
        name="Qwen 2.5 Coder 1.5B (Edge)",
        provider=Provider.LOCAL,
        category=ModelCategory.OPEN_WEIGHT,
        family=ModelFamily.QWEN,
        deployment=DeploymentType.LOCAL_DAEMON,
        context_window=32768,
        max_output_tokens=4096,
        capabilities=["chat", "streaming", "code"],
        supports_streaming=True,
        supports_tools=False,
        supports_structured_output=True,
        modalities=["text"],
        pricing_input_usd_per_mtok=0.0,
        pricing_output_usd_per_mtok=0.0,
        license="Apache-2.0",
        recommended_vram_gb=2.0,
        description="Ultra-lightweight code model designed for resource-constrained edge laptops and speculative decoding.",
    ),
    ModelMetadata(
        id="llama-3.3-70b-instruct",
        name="Llama 3.3 70B Instruct",
        provider=Provider.LOCAL,
        category=ModelCategory.OPEN_WEIGHT,
        family=ModelFamily.LLAMA,
        deployment=DeploymentType.SELF_HOSTED_GPU,
        context_window=131072,
        max_output_tokens=8192,
        capabilities=["chat", "streaming", "reasoning", "code", "tools", "structured_output"],
        supports_streaming=True,
        supports_tools=True,
        supports_structured_output=True,
        modalities=["text"],
        pricing_input_usd_per_mtok=0.0,
        pricing_output_usd_per_mtok=0.0,
        license="Llama-3.3-Community",
        recommended_vram_gb=40.0,
        description="Meta's frontier open-weight model with 128k context and state-of-the-art general reasoning.",
    ),
    ModelMetadata(
        id="mistral-nemo:12b",
        name="Mistral Nemo 12B",
        provider=Provider.LOCAL,
        category=ModelCategory.OPEN_WEIGHT,
        family=ModelFamily.MISTRAL,
        deployment=DeploymentType.LOCAL_DAEMON,
        context_window=128000,
        max_output_tokens=4096,
        capabilities=["chat", "streaming", "code", "structured_output"],
        supports_streaming=True,
        supports_tools=True,
        supports_structured_output=True,
        modalities=["text"],
        pricing_input_usd_per_mtok=0.0,
        pricing_output_usd_per_mtok=0.0,
        license="Apache-2.0",
        recommended_vram_gb=10.0,
        description="Mistral AI & NVIDIA collaborative 12B model with large context and multilingual enterprise reasoning.",
    ),
    ModelMetadata(
        id="deepseek-r1:7b",
        name="DeepSeek R1 Distill 7B",
        provider=Provider.LOCAL,
        category=ModelCategory.OPEN_WEIGHT,
        family=ModelFamily.DEEPSEEK,
        deployment=DeploymentType.LOCAL_DAEMON,
        context_window=65536,
        max_output_tokens=8192,
        capabilities=["chat", "streaming", "reasoning", "code"],
        supports_streaming=True,
        supports_tools=False,
        supports_structured_output=False,
        modalities=["text"],
        pricing_input_usd_per_mtok=0.0,
        pricing_output_usd_per_mtok=0.0,
        license="MIT",
        recommended_vram_gb=6.0,
        description="DeepSeek open-weight reasoning model distilled with chain-of-thought verification capabilities.",
    ),

    # --------------------------------------------------------------------------
    # Closed / Proprietary Commercial Frontier Models
    # --------------------------------------------------------------------------
    ModelMetadata(
        id="gpt-4o",
        name="OpenAI GPT-4o",
        provider=Provider.OPENAI,
        category=ModelCategory.CLOSED_PROPRIETARY,
        family=ModelFamily.OPENAI,
        deployment=DeploymentType.MANAGED_CLOUD_API,
        context_window=128000,
        max_output_tokens=16384,
        capabilities=["chat", "streaming", "reasoning", "code", "tools", "structured_output", "vision"],
        supports_streaming=True,
        supports_tools=True,
        supports_structured_output=True,
        modalities=["text", "vision"],
        pricing_input_usd_per_mtok=2.50,
        pricing_output_usd_per_mtok=10.00,
        license="Proprietary (OpenAI Commercial API)",
        recommended_vram_gb=None,
        description="OpenAI flagship multimodal frontier model with low latency and deep tool calling.",
    ),
    ModelMetadata(
        id="gpt-4o-mini",
        name="OpenAI GPT-4o Mini",
        provider=Provider.OPENAI,
        category=ModelCategory.CLOSED_PROPRIETARY,
        family=ModelFamily.OPENAI,
        deployment=DeploymentType.MANAGED_CLOUD_API,
        context_window=128000,
        max_output_tokens=16384,
        capabilities=["chat", "streaming", "reasoning", "code", "tools", "structured_output", "vision"],
        supports_streaming=True,
        supports_tools=True,
        supports_structured_output=True,
        modalities=["text", "vision"],
        pricing_input_usd_per_mtok=0.15,
        pricing_output_usd_per_mtok=0.60,
        license="Proprietary (OpenAI Commercial API)",
        recommended_vram_gb=None,
        description="Cost-effective high-throughput proprietary model for lightweight tasks and batch processing.",
    ),
    ModelMetadata(
        id="claude-3-5-sonnet",
        name="Anthropic Claude 3.5 Sonnet",
        provider=Provider.ANTHROPIC,
        category=ModelCategory.CLOSED_PROPRIETARY,
        family=ModelFamily.ANTHROPIC,
        deployment=DeploymentType.MANAGED_CLOUD_API,
        context_window=200000,
        max_output_tokens=8192,
        capabilities=["chat", "streaming", "reasoning", "code", "tools", "structured_output", "vision"],
        supports_streaming=True,
        supports_tools=True,
        supports_structured_output=True,
        modalities=["text", "vision"],
        pricing_input_usd_per_mtok=3.00,
        pricing_output_usd_per_mtok=15.00,
        license="Proprietary (Anthropic Commercial API)",
        recommended_vram_gb=None,
        description="Anthropic frontier coding and complex reasoning model with 200k token context window.",
    ),
    ModelMetadata(
        id="gemini-2.5-flash",
        name="Google Gemini 2.5 Flash",
        provider=Provider.GOOGLE,
        category=ModelCategory.CLOSED_PROPRIETARY,
        family=ModelFamily.GEMINI,
        deployment=DeploymentType.MANAGED_CLOUD_API,
        context_window=1000000,
        max_output_tokens=8192,
        capabilities=["chat", "streaming", "reasoning", "code", "tools", "structured_output", "vision"],
        supports_streaming=True,
        supports_tools=True,
        supports_structured_output=True,
        modalities=["text", "vision"],
        pricing_input_usd_per_mtok=0.075,
        pricing_output_usd_per_mtok=0.30,
        license="Proprietary (Google Cloud / AI Studio)",
        recommended_vram_gb=None,
        description="Google ultra-long 1M token context window model optimized for multimodal speed and economy.",
    ),
    ModelMetadata(
        id="gemini-3.5-flash-lite",
        name="Google Gemini 3.5 Flash Lite",
        provider=Provider.GEMINI,
        category=ModelCategory.CLOSED_PROPRIETARY,
        family=ModelFamily.GEMINI,
        deployment=DeploymentType.MANAGED_CLOUD_API,
        context_window=1000000,
        max_output_tokens=8192,
        capabilities=["chat", "streaming", "reasoning", "code", "tools", "structured_output", "vision"],
        supports_streaming=True,
        supports_tools=True,
        supports_structured_output=True,
        modalities=["text", "vision"],
        pricing_input_usd_per_mtok=0.075,
        pricing_output_usd_per_mtok=0.30,
        license="Proprietary (Google Cloud / AI Studio)",
        recommended_vram_gb=None,
        description="High-throughput low-latency Gemini 3.5 Flash Lite model ideal for multi-agent swarm orchestration and JSON extraction.",
    ),
    ModelMetadata(
        id="gemini-3.5-flash",
        name="Google Gemini 3.5 Flash",
        provider=Provider.GEMINI,
        category=ModelCategory.CLOSED_PROPRIETARY,
        family=ModelFamily.GEMINI,
        deployment=DeploymentType.MANAGED_CLOUD_API,
        context_window=1000000,
        max_output_tokens=8192,
        capabilities=["chat", "streaming", "reasoning", "code", "tools", "structured_output", "vision", "complex_reasoning", "long_context"],
        supports_streaming=True,
        supports_tools=True,
        supports_structured_output=True,
        modalities=["text", "vision"],
        pricing_input_usd_per_mtok=0.15,
        pricing_output_usd_per_mtok=0.60,
        license="Proprietary (Google Cloud / AI Studio)",
        recommended_vram_gb=None,
        description="Frontier multimodal Gemini 3.5 Flash model with 1M context window, native JSON mode, and reasoning.",
    ),
]


class ModelRegistry:
    """Centralized Registry managing all available models across Open-Weight and Closed providers."""

    def __init__(self, models: Optional[List[ModelMetadata]] = None):
        self._models: Dict[str, ModelMetadata] = {}
        for m in (models or CANONICAL_MODELS):
            self.register(m)

    def register(self, metadata: ModelMetadata) -> None:
        """Register or update a model definition."""
        self._models[metadata.id] = metadata

    def get(self, model_id: str) -> Optional[ModelMetadata]:
        """Look up a model by ID or alias."""
        # Exact match
        if model_id in self._models:
            return self._models[model_id]
        # Match without tag (e.g. "qwen2.5-coder" matches "qwen2.5-coder:7b")
        for mid, meta in self._models.items():
            if mid.startswith(f"{model_id}:") or model_id.startswith(f"{mid}:"):
                return meta
        return None

    def list_models(
        self,
        category: Optional[ModelCategory] = None,
        provider: Optional[Provider] = None,
        capability: Optional[str] = None,
        active_only: bool = True,
    ) -> List[ModelMetadata]:
        """List models filtered by category, provider, or required capability."""
        res = []
        for m in self._models.values():
            if active_only and not m.is_active:
                continue
            if category and m.category != category:
                continue
            if provider and m.provider != provider:
                continue
            if capability and capability not in m.capabilities:
                continue
            res.append(m)
        return res

    def to_discovery_dict(self) -> Dict[str, Any]:
        """Return discovery list compatible with standard API specs."""
        return {
            "object": "list",
            "data": [
                {
                    "id": m.id,
                    "object": "model",
                    "name": m.name,
                    "created": 1730000000,
                    "owned_by": m.provider.value,
                    "category": m.category.value,
                    "family": m.family.value,
                    "deployment": m.deployment.value,
                    "context_window": m.context_window,
                    "max_output_tokens": m.max_output_tokens,
                    "capabilities": m.capabilities,
                    "supports_streaming": m.supports_streaming,
                    "supports_tools": m.supports_tools,
                    "supports_structured_output": m.supports_structured_output,
                    "modalities": m.modalities,
                    "pricing": {
                        "input_usd_per_mtok": m.pricing_input_usd_per_mtok,
                        "output_usd_per_mtok": m.pricing_output_usd_per_mtok,
                    },
                    "license": m.license,
                    "recommended_vram_gb": m.recommended_vram_gb,
                    "description": m.description,
                }
                for m in self.list_models()
            ],
            "categories": {
                "open_weight": len(self.list_models(category=ModelCategory.OPEN_WEIGHT)),
                "closed_proprietary": len(self.list_models(category=ModelCategory.CLOSED_PROPRIETARY)),
            },
        }


# Singleton registry instance
model_registry = ModelRegistry()
