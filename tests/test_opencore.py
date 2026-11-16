"""
Keelway OpenCore Subsystem Verification Suite.

Tests canonical model registration, hardware profiling, cryptographic weight validation,
serving engine lifecycle, sovereign adaptation pipelines, and REST API endpoints.
"""

import pytest
import httpx
from httpx import ASGITransport

from core.main import app
from core.api.schemas import Provider, MessageSchema, CompletionRequestSchema
from core.models.registry import model_registry, ModelCategory, ModelFamily
from core.models.provider import ChatCompletionRequest
from core.models.gateway import ModelGateway
from core.opencore.weights import (
    HardwareProfiler,
    QuantizationLevel,
    WeightFormat,
    WeightManager,
    weight_manager,
)
from core.opencore.serving import (
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


@pytest.mark.asyncio
async def test_opencore_canonical_model_registry():
    """Verify canonical OpenCore models exist with correct metadata and zero-cost local pricing."""
    core_models = [
        "keelway-core:7b",
        "keelway-coder:7b",
        "keelway-reasoning:14b",
        "keelway-nano:1.5b",
    ]
    for mid in core_models:
        meta = model_registry.get(mid)
        assert meta is not None, f"Model {mid} missing from registry"
        assert meta.family == ModelFamily.KEELWAY_CORE
        assert meta.category == ModelCategory.OPEN_WEIGHT
        assert meta.provider == Provider.LOCAL
        assert meta.license == "Apache-2.0"
        assert meta.pricing_input_usd_per_mtok == 0.0
        assert meta.pricing_output_usd_per_mtok == 0.0


def test_hardware_profiler_detection():
    """Verify hardware profiler correctly discovers CPU and memory metrics."""
    profile = HardwareProfiler.detect()
    assert profile.cpu_count >= 1
    assert profile.total_ram_gb > 0
    assert profile.recommended_quantization in (
        QuantizationLevel.Q8_0,
        QuantizationLevel.Q4_K_M,
        QuantizationLevel.Q4_0,
    )


def test_weight_manager_manifests_and_checksum(tmp_path):
    """Verify weight manifests and cryptographic integrity validation."""
    custom_mgr = WeightManager(cache_dir=tmp_path)
    manifest = custom_mgr.get_manifest("keelway-core:7b", QuantizationLevel.Q4_K_M)
    assert manifest is not None
    assert manifest.context_length == 65536
    assert manifest.format == WeightFormat.GGUF

    # Verify not cached initially
    assert not custom_mgr.is_cached(manifest)

    # Create synthetic test weights
    mock_bytes = b"GGUF_MAGIC_V3_KEELWAY_TEST_DATA"
    file_path = custom_mgr.create_mock_weight_for_testing(manifest, content=mock_bytes)
    assert file_path.exists()
    assert custom_mgr.is_cached(manifest)

    # Verify checksum matches
    assert custom_mgr.verify_checksum(file_path, manifest.sha256_checksum)
    assert not custom_mgr.verify_checksum(file_path, "invalid_hash_here")


@pytest.mark.asyncio
async def test_serving_engine_lifecycle():
    """Verify loading, inference forwarding, telemetry tracking, and unloading."""
    engine = OpenCoreServingEngine()

    # Initial state
    assert len(engine.get_loaded_models()) == 0

    # Load model
    loaded = await engine.load_model("keelway-coder:7b", QuantizationLevel.Q4_K_M)
    assert loaded.status == OpenCoreWorkerStatus.READY
    assert loaded.model_id == "keelway-coder:7b"
    assert loaded.vram_allocated_gb == 5.8

    # Forward inference
    req = ChatCompletionRequest(
        model="keelway-coder:7b",
        messages=[MessageSchema(role="user", content="Write a quicksort in Python")],
    )
    res = await engine.forward_inference(req)
    assert res.model == "keelway-coder:7b"
    assert res.cost_usd == 0.0
    assert "Keelway OpenCore Coder 7B" in res.content
    assert res.usage["total_tokens"] > 0
    assert res.simulated is True
    assert "simulated" in res.to_openai_dict()["keelway_metadata"]
    assert res.to_openai_dict()["keelway_metadata"]["simulated"] is True

    # Verify telemetry updated
    telem = engine.get_cluster_telemetry()
    assert telem.active_workers == 1
    assert telem.used_vram_gb == 5.8
    assert telem.kv_cache_hit_rate_pct > 0.0

    # Test reasoning personality
    req_reason = ChatCompletionRequest(
        model="keelway-reasoning:14b",
        messages=[MessageSchema(role="user", content="Prove Fermat's little theorem")],
    )
    res_reason = await engine.forward_inference(req_reason)
    assert "<thought>" in res_reason.content

    # Unload
    unloaded = await engine.unload_model("keelway-coder:7b")
    assert unloaded is True
    assert len(engine.get_loaded_models()) == 1  # reasoning remains loaded


def test_sovereign_adaptation_recipes_and_datasets():
    """Verify PEFT configuration and African multilingual dataset assembly."""
    cfg = AdaptationConfig(
        base_model_id="keelway-core:7b",
        task=AdaptationTask.MULTILINGUAL_LOCALIZATION,
        target_languages=[
            TargetLanguage.SWAHILI,
            TargetLanguage.YORUBA,
            TargetLanguage.HAUSA,
            TargetLanguage.AMHARIC,
        ],
        lora_r=32,
        lora_alpha=64,
    )

    # Check PEFT config
    peft_dict = generate_peft_config(cfg)
    assert peft_dict["r"] == 32
    assert peft_dict["lora_alpha"] == 64
    assert peft_dict["base_model_name_or_path"] == "keelway-core:7b"

    # Check Unsloth recipe script
    recipe = generate_unsloth_recipe(cfg)
    assert "from unsloth import FastLanguageModel" in recipe
    assert "r=32" in recipe

    # Check multilingual dataset
    samples = DomainDatasetBuilder.get_multilingual_samples(cfg.target_languages)
    languages = {s["language"] for s in samples}
    assert "swahili" in languages
    assert "yoruba" in languages
    assert "hausa" in languages
    assert "amharic" in languages


@pytest.mark.asyncio
async def test_opencore_api_routes():
    """Verify all REST API endpoints under /v1/opencore."""
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. GET /v1/opencore/status
        resp_status = await client.get("/v1/opencore/status")
        assert resp_status.status_code == 200
        data_status = resp_status.json()
        assert data_status["status"] == "healthy"
        assert "hardware" in data_status
        assert "telemetry" in data_status

        # 2. GET /v1/opencore/weights
        resp_weights = await client.get("/v1/opencore/weights")
        assert resp_weights.status_code == 200
        manifests = resp_weights.json()
        assert len(manifests) >= 4
        model_ids = {m["model_id"] for m in manifests}
        assert "keelway-core:7b" in model_ids
        assert "keelway-nano:1.5b" in model_ids

        # 3. POST /v1/opencore/models/load
        resp_load = await client.post(
            "/v1/opencore/models/load",
            json={"model_id": "keelway-nano:1.5b", "backend": "mock"},
        )
        assert resp_load.status_code == 200
        loaded_info = resp_load.json()
        assert loaded_info["model_id"] == "keelway-nano:1.5b"
        assert loaded_info["status"] == "ready"

        # 4. POST /v1/opencore/models/unload
        resp_unload = await client.post(
            "/v1/opencore/models/unload",
            json={"model_id": "keelway-nano:1.5b"},
        )
        assert resp_unload.status_code == 200
        assert resp_unload.json()["unloaded"] is True

        # 5. POST /v1/opencore/adapt/recipe
        resp_recipe = await client.post(
            "/v1/opencore/adapt/recipe",
            json={
                "base_model_id": "keelway-core:7b",
                "task": "multilingual_localization",
                "target_languages": ["swahili", "english"],
            },
        )
        assert resp_recipe.status_code == 200
        recipe_data = resp_recipe.json()
        assert recipe_data["base_model_id"] == "keelway-core:7b"
        assert "unsloth_recipe" in recipe_data
        assert recipe_data["synthetic_sample_count"] > 0


@pytest.mark.asyncio
async def test_gateway_routing_to_opencore():
    """Verify ModelGateway seamlessly routes requests to OpenCore models at $0.00 cost."""
    gw = ModelGateway()
    req = CompletionRequestSchema(
        model="keelway-core:7b",
        messages=[MessageSchema(role="user", content="Provide sovereign architecture guidance.")],
    )
    res = await gw.complete(req)
    assert res.model == "keelway-core:7b"
    assert res.provider == Provider.LOCAL
    assert res.cost_usd == 0.0
    assert "Keelway OpenCore" in res.content
