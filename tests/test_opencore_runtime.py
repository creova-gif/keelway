"""
Keelway OpenCore Neural Runtime, Modelfile Compiler & LoRA Hot-Swap Test Suite.

Covers deterministic Ollama Modelfile compilation, cryptographic LoRA adapter lifecycle,
local runtime discovery, Ollama & vLLM live bridges via httpx.MockTransport,
OpenCoreServingEngine neural backend telemetry, and FastAPI /v1/opencore/* routes.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport

from core.api import opencore_routes
from core.api.schemas import MessageSchema, Provider
from core.models.provider import ChatCompletionRequest, ProviderError
from core.opencore.adaptation import AdaptationTask
from core.opencore.runtime import (
    CANONICAL_MODEL_IDS,
    LoRAAdapterRecord,
    LoRAAdapterRegistry,
    LocalRuntimeDiscovery,
    OllamaRuntimeBridge,
    OpenCoreModelfileCompiler,
    VLLMRuntimeBridge,
    build_ollama_create_command,
)
from core.opencore.serving import OpenCoreServingEngine, OpenCoreWorkerBackend, opencore_serving_engine
from core.opencore.weights import QuantizationLevel, WeightManager


def _build_isolated_app() -> FastAPI:
    app = FastAPI()
    app.include_router(opencore_routes.router)
    return app


def test_modelfile_compiler_all_canonical_models(tmp_path: Path):
    """Verify deterministic Modelfile output across all 4 canonical OpenCore models."""
    wm = WeightManager(cache_dir=tmp_path / "weights")
    reg = LoRAAdapterRegistry(cache_dir=tmp_path / "adapters")
    compiler = OpenCoreModelfileCompiler(manager=wm, adapter_registry=reg)

    expected_ctx = {
        "keelway-core:7b": 65536,
        "keelway-coder:7b": 65536,
        "keelway-reasoning:14b": 131072,
        "keelway-nano:1.5b": 32768,
    }
    expected_markers = {
        "keelway-core:7b": "multilingual",
        "keelway-coder:7b": "AST-verified",
        "keelway-reasoning:14b": "<thought>",
        "keelway-nano:1.5b": "speculative-draft",
    }

    for mid in CANONICAL_MODEL_IDS:
        manifest = wm.get_manifest(mid, QuantizationLevel.Q4_K_M)
        assert manifest is not None
        out = compiler.compile(mid)
        assert f"# Model ID: {mid}" in out
        assert f"# SHA-256 Manifest Checksum: {manifest.sha256_checksum}" in out
        assert f"FROM {wm.get_local_path(manifest)}" in out
        assert f"PARAMETER num_ctx {expected_ctx[mid]}" in out
        assert 'STOP "<|im_end|>"' in out
        assert expected_markers[mid] in out
        assert out == compiler.compile(mid)


def test_modelfile_compiler_base_override_lora_and_cli_command(tmp_path: Path):
    """Verify base_source tag override, ADAPTER directive, custom tag, and CLI helper."""
    wm = WeightManager(cache_dir=tmp_path / "weights")
    reg = LoRAAdapterRegistry(cache_dir=tmp_path / "adapters")
    adapter = reg.create_mock_adapter_for_testing(
        adapter_id="lora-yoruba-v2", base_model_id="keelway-core:7b", lora_r=32, lora_alpha=64
    )
    compiler = OpenCoreModelfileCompiler(manager=wm, adapter_registry=reg)

    rendered = compiler.compile(
        "keelway-core:7b",
        base_source="qwen3.5:latest",
        adapter_id=adapter.adapter_id,
        temperature=0.55,
        top_p=0.92,
        num_ctx=16384,
    )
    assert "FROM qwen3.5:latest" in rendered
    assert f"ADAPTER {adapter.adapter_path}" in rendered
    assert f"sha256={adapter.sha256_checksum}" in rendered
    assert "PARAMETER temperature 0.55" in rendered
    assert "PARAMETER top_p 0.92" in rendered
    assert "PARAMETER num_ctx 16384" in rendered

    custom = compiler.compile("keelway-custom:3b", base_source="qwen2.5:3b")
    assert "# SHA-256 Manifest Checksum: external-base-tag" in custom
    assert "FROM qwen2.5:3b" in custom
    assert build_ollama_create_command("keelway-core:7b", "/tmp/my dir/Modelfile") == (
        "ollama create keelway-core:7b -f '/tmp/my dir/Modelfile'"
    )


def test_lora_adapter_registry_checksum_and_tamper_detection(tmp_path: Path):
    """Verify LoRA registration, SHA-256 integrity checks, and tamper rejection."""
    reg = LoRAAdapterRegistry(cache_dir=tmp_path / "adapters")
    rec = reg.create_mock_adapter_for_testing(
        adapter_id="lora-swahili-fin", base_model_id="keelway-core:7b", content=b"SOVEREIGN_LORA_V1"
    )
    assert reg.verify_adapter_integrity(rec.adapter_id) is True

    Path(rec.adapter_path).write_bytes(b"CORRUPTED_BYTES")
    assert reg.verify_adapter_integrity(rec.adapter_id) is False
    with pytest.raises(ValueError, match="SHA-256"):
        reg.attach_adapter("keelway-core:7b", rec.adapter_id, verify_integrity=True)

    bad_record = LoRAAdapterRecord(
        adapter_id="lora-bad",
        name="Tampered Adapter",
        base_model_id="keelway-core:7b",
        adapter_path=rec.adapter_path,
        sha256_checksum=hashlib.sha256(b"EXPECTED_DIFFERENT").hexdigest(),
    )
    with pytest.raises(ValueError, match="SHA-256 integrity verification failed"):
        reg.register_adapter(bad_record, verify_on_disk=True)


@pytest.mark.asyncio
async def test_lora_hot_swap_lifecycle_and_serving_attribution(tmp_path: Path):
    """Verify attach/detach lifecycle, base model mismatch guard, and routing_reason injection."""
    wm = WeightManager(cache_dir=tmp_path / "weights")
    reg = LoRAAdapterRegistry(cache_dir=tmp_path / "adapters")
    dead = httpx.MockTransport(lambda r: httpx.Response(503))
    engine = OpenCoreServingEngine(
        manager=wm,
        adapter_registry=reg,
        ollama_bridge=OllamaRuntimeBridge(transport=dead),
        vllm_bridge=VLLMRuntimeBridge(transport=dead),
        discovery=LocalRuntimeDiscovery(transport=dead),
    )
    adapter = reg.create_mock_adapter_for_testing(
        adapter_id="lora-hausa-v1", base_model_id="keelway-core:7b", task=AdaptationTask.MULTILINGUAL_LOCALIZATION
    )

    with pytest.raises(ValueError, match="cannot attach"):
        reg.attach_adapter("keelway-coder:7b", adapter.adapter_id)

    reg.attach_adapter("keelway-core:7b", adapter.adapter_id, verify_integrity=True)
    req = ChatCompletionRequest(
        model="keelway-core:7b", messages=[MessageSchema(role="user", content="Sannu, explain sovereignty.")]
    )
    resp = await engine.forward_inference(req)
    assert "LoRA adapter=lora-hausa-v1" in (resp.routing_reason or "")
    assert "task=multilingual_localization" in (resp.routing_reason or "")
    info = engine.get_model_info("keelway-core:7b")
    assert info is not None and info.attached_adapter_id == "lora-hausa-v1"

    assert reg.detach_adapter("keelway-core:7b") is True
    assert reg.detach_adapter("keelway-core:7b") is False
    resp_after = await engine.forward_inference(req)
    assert "LoRA adapter=" not in (resp_after.routing_reason or "")


@pytest.mark.asyncio
async def test_local_runtime_discovery_exact_and_fallback_bindings():
    """Verify Ollama discovery maps exact keelway tags or role-aware open-weight fallbacks."""
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return httpx.Response(
                200,
                json={"models": [{"name": "keelway-nano:1.5b"}, {"name": "qwen2.5-coder:7b"}, {"name": "qwen3.5:latest"}]},
            )
        return httpx.Response(404)

    discovery = LocalRuntimeDiscovery(transport=httpx.MockTransport(handler))
    probe = await discovery.discover_ollama()
    assert probe.reachable is True
    assert probe.recommended_bindings["keelway-nano:1.5b"] == "keelway-nano:1.5b"
    assert probe.recommended_bindings["keelway-coder:7b"] == "qwen2.5-coder:7b"
    assert probe.recommended_bindings["keelway-core:7b"] == "qwen3.5:latest"
    assert probe.recommended_bindings["keelway-reasoning:14b"] == "qwen3.5:latest"

    strict_probe = await discovery.discover_ollama(fallback_base_model=False)
    assert strict_probe.recommended_bindings["keelway-nano:1.5b"] == "keelway-nano:1.5b"
    assert strict_probe.recommended_bindings["keelway-core:7b"] is None


@pytest.mark.asyncio
async def test_local_runtime_discovery_offline_graceful():
    """Verify unreachable local runtimes return reachable=False without raising."""
    def failing(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Connection refused", request=request)

    probe = await LocalRuntimeDiscovery(transport=httpx.MockTransport(failing)).discover_ollama()
    assert probe.reachable is False
    assert probe.installed_models == []
    assert probe.error is not None


@pytest.mark.asyncio
async def test_ollama_runtime_bridge_non_streaming_and_json_mode():
    """Verify OllamaRuntimeBridge POST /api/chat payload, JSON mode, token usage, and $0 cost."""
    captured: List[Dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        captured.append(body)
        content = json.dumps({"status": "verified", "sovereign": True}) if body.get("format") == "json" else "Habari! Sovereign active."
        return httpx.Response(
            200,
            json={
                "model": body["model"],
                "message": {"role": "assistant", "content": content},
                "done": True,
                "done_reason": "stop",
                "prompt_eval_count": 42,
                "eval_count": 18,
            },
        )

    bridge = OllamaRuntimeBridge(transport=httpx.MockTransport(handler))
    req_text = ChatCompletionRequest(
        model="keelway-core:7b", messages=[MessageSchema(role="user", content="Greet me")], temperature=0.6, max_tokens=256
    )
    res_text = await bridge.generate(req_text, resolved_base_model="qwen3.5:latest", system_override="Sovereign Sys")
    assert res_text.model == "keelway-core:7b"
    assert res_text.provider == Provider.LOCAL
    assert res_text.cost_usd == 0.0
    assert res_text.usage == {"prompt_tokens": 42, "completion_tokens": 18, "total_tokens": 60}
    assert res_text.latency_ms >= 0.0
    assert "Habari!" in res_text.content
    assert captured[0]["model"] == "qwen3.5:latest"
    assert captured[0]["stream"] is False
    assert captured[0]["messages"][0]["role"] == "system"
    assert captured[0]["options"]["num_predict"] == 256
    assert "format" not in captured[0]

    req_json = ChatCompletionRequest(
        model="keelway-core:7b", messages=[MessageSchema(role="user", content="JSON")], response_format={"type": "json_object"}
    )
    res_json = await bridge.generate(req_json, resolved_base_model="qwen3.5:latest")
    assert captured[1]["format"] == "json"
    assert json.loads(res_json.content)["sovereign"] is True


@pytest.mark.asyncio
async def test_ollama_runtime_bridge_streaming_ndjson():
    """Verify OllamaRuntimeBridge.stream_generate yields StreamChunks and final usage."""
    ndjson = "\n".join([
        json.dumps({"model": "qwen3.5:latest", "message": {"role": "assistant", "content": "Zero "}, "done": False}),
        json.dumps({"model": "qwen3.5:latest", "message": {"role": "assistant", "content": "egress!"}, "done": False}),
        json.dumps({"model": "qwen3.5:latest", "message": {"role": "assistant", "content": ""}, "done": True, "done_reason": "stop", "prompt_eval_count": 20, "eval_count": 6}),
    ]) + "\n"

    def handler(request: httpx.Request) -> httpx.Response:
        assert json.loads(request.content.decode("utf-8"))["stream"] is True
        return httpx.Response(200, content=ndjson.encode("utf-8"))

    bridge = OllamaRuntimeBridge(transport=httpx.MockTransport(handler))
    req = ChatCompletionRequest(model="keelway-nano:1.5b", messages=[MessageSchema(role="user", content="Ping")], stream=True)
    chunks = [c async for c in bridge.stream_generate(req, resolved_base_model="qwen3.5:latest")]
    assert len(chunks) == 3
    assert "".join(c.delta_content for c in chunks) == "Zero egress!"
    assert chunks[-1].finish_reason == "stop"
    assert chunks[-1].usage == {"prompt_tokens": 20, "completion_tokens": 6, "total_tokens": 26}


@pytest.mark.asyncio
async def test_vllm_runtime_bridge_and_discovery():
    """Verify VLLMRuntimeBridge OpenAI-compatible /v1/chat/completions and /v1/models discovery."""
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/models":
            return httpx.Response(200, json={"data": [{"id": "Qwen/Qwen2.5-Coder-7B-Instruct"}]})
        if request.url.path == "/v1/chat/completions":
            body = json.loads(request.content.decode("utf-8"))
            return httpx.Response(
                200,
                json={
                    "id": "cmpl-vllm-001",
                    "created": 1730000000,
                    "model": body["model"],
                    "choices": [{"index": 0, "message": {"role": "assistant", "content": "def add(a: int, b: int) -> int: return a + b"}, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 25, "completion_tokens": 14, "total_tokens": 39},
                },
            )
        return httpx.Response(404)

    tx = httpx.MockTransport(handler)
    probe = await LocalRuntimeDiscovery(transport=tx).discover_vllm()
    assert probe.reachable is True
    assert probe.recommended_bindings["keelway-coder:7b"] == "Qwen/Qwen2.5-Coder-7B-Instruct"

    res = await VLLMRuntimeBridge(transport=tx).generate(
        ChatCompletionRequest(model="keelway-coder:7b", messages=[MessageSchema(role="user", content="Write add")]),
        resolved_model="Qwen/Qwen2.5-Coder-7B-Instruct",
    )
    assert res.cost_usd == 0.0
    assert res.provider == Provider.LOCAL
    assert res.usage["total_tokens"] == 39
    assert "def add" in res.content


@pytest.mark.asyncio
async def test_serving_engine_ollama_backend_telemetry_and_streaming(tmp_path: Path):
    """Verify OpenCoreServingEngine delegates OLLAMA inference & streaming and updates telemetry."""
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "qwen3.5:latest"}]})
        if request.url.path == "/api/chat":
            body = json.loads(request.content.decode("utf-8"))
            if body.get("stream"):
                s = "\n".join([
                    json.dumps({"message": {"content": "<thought>ok</thought> "}, "done": False}),
                    json.dumps({"message": {"content": "Verified."}, "done": True, "prompt_eval_count": 15, "eval_count": 9}),
                ])
                return httpx.Response(200, content=s.encode("utf-8"))
            return httpx.Response(200, json={"message": {"role": "assistant", "content": "<thought>Step 1</thought>\nQ.E.D."}, "done": True, "prompt_eval_count": 30, "eval_count": 12})
        return httpx.Response(404)

    tx = httpx.MockTransport(handler)
    wm = WeightManager(cache_dir=tmp_path / "weights")
    reg = LoRAAdapterRegistry(cache_dir=tmp_path / "adapters")
    adapter = reg.create_mock_adapter_for_testing(
        adapter_id="lora-math-v1", base_model_id="keelway-reasoning:14b", task=AdaptationTask.MATHEMATICAL_REASONING
    )
    reg.attach_adapter("keelway-reasoning:14b", adapter.adapter_id)
    engine = OpenCoreServingEngine(
        manager=wm, adapter_registry=reg, ollama_bridge=OllamaRuntimeBridge(transport=tx), discovery=LocalRuntimeDiscovery(transport=tx)
    )

    loaded = await engine.load_model("keelway-reasoning:14b", backend=OpenCoreWorkerBackend.OLLAMA)
    assert loaded.backend == OpenCoreWorkerBackend.OLLAMA
    assert loaded.resolved_runtime_model == "qwen3.5:latest"
    assert loaded.attached_adapter_id == "lora-math-v1"
    initial_kv = loaded.kv_cache_usage_pct

    req = ChatCompletionRequest(model="keelway-reasoning:14b", messages=[MessageSchema(role="user", content="Prove sqrt(2)")])
    resp = await engine.forward_inference(req, backend=OpenCoreWorkerBackend.OLLAMA)
    assert "Q.E.D." in resp.content
    assert "runtime_model=qwen3.5:latest" in (resp.routing_reason or "")
    assert "LoRA adapter=lora-math-v1" in (resp.routing_reason or "")

    chunks = [c async for c in engine.stream_inference(req, backend=OpenCoreWorkerBackend.OLLAMA)]
    assert "".join(c.delta_content for c in chunks) == "<thought>ok</thought> Verified."
    info = engine.get_model_info("keelway-reasoning:14b")
    assert info is not None and info.requests_served == 2 and info.tokens_generated == 21
    assert info.kv_cache_usage_pct > initial_kv


@pytest.mark.asyncio
async def test_ollama_bridge_error_maps_to_provider_error():
    """Verify HTTP 500 from Ollama translates cleanly into ProviderError(Provider.LOCAL)."""
    bridge = OllamaRuntimeBridge(transport=httpx.MockTransport(lambda req: httpx.Response(500, json={"error": "boom"})))
    req = ChatCompletionRequest(model="keelway-core:7b", messages=[MessageSchema(role="user", content="Fail")])
    with pytest.raises(ProviderError) as exc_info:
        await bridge.generate(req)
    assert exc_info.value.provider == Provider.LOCAL and exc_info.value.status_code == 500


@pytest.mark.asyncio
async def test_asgi_routes_discover_and_modelfile(monkeypatch: pytest.MonkeyPatch):
    """Verify GET /v1/opencore/runtime/discover and POST /v1/opencore/modelfile via ASGI."""
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "qwen3.5:latest"}]})
        return httpx.Response(503)

    tx = httpx.MockTransport(handler)
    monkeypatch.setattr(opencore_serving_engine.ollama_bridge, "transport", tx)
    monkeypatch.setattr(opencore_serving_engine.vllm_bridge, "transport", tx)

    async with httpx.AsyncClient(transport=ASGITransport(app=_build_isolated_app()), base_url="http://test") as client:
        disc = (await client.get("/v1/opencore/runtime/discover")).json()
        assert disc["ollama"]["reachable"] is True
        assert disc["recommended_bindings"]["keelway-core:7b"] == "qwen3.5:latest"

        mf = (await client.post(
            "/v1/opencore/modelfile",
            json={"model_id": "keelway-coder:7b", "base_source": "qwen3.5:latest", "quantization": "q4_k_m", "modelfile_path": "./Modelfile.coder"},
        )).json()
        assert "FROM qwen3.5:latest" in mf["modelfile"]
        assert mf["cli_command"] == "ollama create keelway-coder:7b -f ./Modelfile.coder"


@pytest.mark.asyncio
async def test_asgi_routes_adapters_and_infer_lifecycle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Verify /adapters/* registration/attach/detach and /infer across mock and ollama backends."""
    isolated_reg = LoRAAdapterRegistry(cache_dir=tmp_path / "adapters")
    monkeypatch.setattr(opencore_serving_engine, "adapter_registry", isolated_reg)

    def ollama_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "qwen3.5:latest"}]})
        if request.url.path == "/api/chat":
            body = json.loads(request.content.decode("utf-8"))
            return httpx.Response(200, json={"message": {"role": "assistant", "content": f"Live Ollama reply from {body['model']}"}, "done": True, "prompt_eval_count": 19, "eval_count": 11})
        return httpx.Response(404)

    monkeypatch.setattr(opencore_serving_engine.ollama_bridge, "transport", httpx.MockTransport(ollama_handler))

    adapter_file = tmp_path / "swahili_lora.safetensors"
    adapter_bytes = b"LORA_WEIGHTS_ASGI_TEST"
    adapter_file.write_bytes(adapter_bytes)

    async with httpx.AsyncClient(transport=ASGITransport(app=_build_isolated_app()), base_url="http://test") as client:
        reg_resp = await client.post(
            "/v1/opencore/adapters/register",
            json={
                "adapter_id": "lora-asgi-swahili",
                "name": "ASGI Swahili LoRA",
                "base_model_id": "keelway-core:7b",
                "task": "multilingual_localization",
                "languages": ["swahili", "english"],
                "adapter_path": str(adapter_file),
                "sha256_checksum": hashlib.sha256(adapter_bytes).hexdigest(),
                "lora_r": 16,
                "lora_alpha": 32,
                "verify_on_disk": True,
            },
        )
        assert reg_resp.status_code == 200 and reg_resp.json()["integrity_verified"] is True

        att_resp = await client.post(
            "/v1/opencore/adapters/attach",
            json={"model_id": "keelway-core:7b", "adapter_id": "lora-asgi-swahili", "verify_integrity": True},
        )
        assert att_resp.status_code == 200 and att_resp.json()["attached"] is True

        list_data = (await client.get("/v1/opencore/adapters")).json()
        assert len(list_data["adapters"]) == 1
        assert list_data["attached_by_model"]["keelway-core:7b"] == "lora-asgi-swahili"

        infer_ollama = await client.post(
            "/v1/opencore/infer",
            json={
                "model": "keelway-core:7b",
                "messages": [{"role": "user", "content": "Eleza OpenCore kwa Kiswahili"}],
                "backend": "ollama",
                "base_model_override": "qwen3.5:latest",
            },
        )
        assert infer_ollama.status_code == 200
        infer_data = infer_ollama.json()
        assert "Live Ollama reply from qwen3.5:latest" in infer_data["content"]
        assert "LoRA adapter=lora-asgi-swahili" in infer_data["routing_reason"]
        assert infer_data["cost_usd"] == 0.0

        det_resp = await client.post("/v1/opencore/adapters/detach", json={"model_id": "keelway-core:7b"})
        assert det_resp.status_code == 200 and det_resp.json()["detached"] is True

        infer_mock = await client.post(
            "/v1/opencore/infer",
            json={"model": "keelway-core:7b", "messages": [{"role": "user", "content": "Verify mock"}], "backend": "mock"},
        )
        assert infer_mock.status_code == 200
        assert "Keelway OpenCore 7B Sovereign Engine" in infer_mock.json()["content"]
        assert "LoRA adapter=" not in infer_mock.json()["routing_reason"]
