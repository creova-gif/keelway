"""KEEL-PROD-041 — OpenCore runtime-alias serving tests.

Verifies the hybrid weights decision: flagship ``keelway-*`` manifests
(``runtime_alias=True``) are served by a compatible installed local runtime
model (Ollama/vLLM) when one is reachable, while alias-incapable models
(``keelway-nano:1.5b``) and unreachable runtimes remain honestly simulated.
"""

from __future__ import annotations

import json

import httpx
import pytest

from core.api.schemas import MessageSchema
from core.models.provider import ChatCompletionRequest
from core.opencore.runtime import (
    LocalRuntimeDiscovery,
    OllamaRuntimeBridge,
    VLLMRuntimeBridge,
)
from core.opencore.serving import (
    OpenCoreServingEngine,
    OpenCoreWorkerBackend,
)


def _ollama_transport() -> httpx.MockTransport:
    """Mock Ollama: one installed model plus a deterministic chat reply."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "qwen3.5:latest"}]})
        if request.url.path == "/api/chat":
            body = json.loads(request.content.decode("utf-8"))
            return httpx.Response(
                200,
                json={
                    "model": body["model"],
                    "message": {"role": "assistant", "content": f"real weights reply via {body['model']}"},
                    "done": True,
                    "prompt_eval_count": 11,
                    "eval_count": 7,
                },
            )
        return httpx.Response(404)

    return httpx.MockTransport(handler)


def _dead_transport() -> httpx.MockTransport:
    return httpx.MockTransport(lambda r: httpx.Response(503))


def _engine_with_ollama() -> OpenCoreServingEngine:
    tx = _ollama_transport()
    return OpenCoreServingEngine(
        ollama_bridge=OllamaRuntimeBridge(transport=tx),
        vllm_bridge=VLLMRuntimeBridge(transport=_dead_transport()),
        discovery=LocalRuntimeDiscovery(transport=tx),
    )


def _engine_dead() -> OpenCoreServingEngine:
    dead = _dead_transport()
    return OpenCoreServingEngine(
        ollama_bridge=OllamaRuntimeBridge(transport=dead),
        vllm_bridge=VLLMRuntimeBridge(transport=dead),
        discovery=LocalRuntimeDiscovery(transport=dead),
    )


@pytest.mark.asyncio
async def test_flagship_model_auto_aliases_to_ollama():
    """keelway-core:7b with a reachable Ollama serves real weights, not the mock."""
    engine = _engine_with_ollama()
    req = ChatCompletionRequest(
        model="keelway-core:7b",
        messages=[MessageSchema(role="user", content="Say hi")],
    )
    res = await engine.forward_inference(req)
    assert res.simulated is False
    assert "real weights reply via qwen3.5:latest" in res.content
    assert "runtime_model=qwen3.5:latest" in (res.routing_reason or "")
    info = engine.get_model_info("keelway-core:7b")
    assert info is not None and info.backend == OpenCoreWorkerBackend.OLLAMA
    assert info.resolved_runtime_model == "qwen3.5:latest"


@pytest.mark.asyncio
async def test_flagship_model_falls_back_to_mock_when_runtime_down():
    """No reachable runtime -> honest simulated mock backend."""
    engine = _engine_dead()
    req = ChatCompletionRequest(
        model="keelway-core:7b",
        messages=[MessageSchema(role="user", content="Say hi")],
    )
    res = await engine.forward_inference(req)
    assert res.simulated is True
    assert "SIMULATED" in (res.routing_reason or "")
    info = engine.get_model_info("keelway-core:7b")
    assert info is not None and info.backend == OpenCoreWorkerBackend.MOCK


@pytest.mark.asyncio
async def test_nano_never_aliases_even_with_runtime():
    """keelway-nano:1.5b is alias-incapable: always mock-served."""
    engine = _engine_with_ollama()
    req = ChatCompletionRequest(
        model="keelway-nano:1.5b",
        messages=[MessageSchema(role="user", content="Say hi")],
    )
    res = await engine.forward_inference(req)
    assert res.simulated is True
    info = engine.get_model_info("keelway-nano:1.5b")
    assert info is not None and info.backend == OpenCoreWorkerBackend.MOCK


@pytest.mark.asyncio
async def test_explicit_backend_still_honored():
    """Callers may still pin backend=mock for deterministic/demo runs."""
    engine = _engine_with_ollama()
    req = ChatCompletionRequest(
        model="keelway-core:7b",
        messages=[MessageSchema(role="user", content="Say hi")],
    )
    res = await engine.forward_inference(req, backend=OpenCoreWorkerBackend.MOCK)
    assert res.simulated is True
    info = engine.get_model_info("keelway-core:7b")
    assert info is not None and info.backend == OpenCoreWorkerBackend.MOCK


@pytest.mark.asyncio
async def test_streaming_alias_uses_real_runtime():
    """stream_inference auto-selects OLLAMA and yields real token chunks."""
    engine = _engine_with_ollama()

    def stream_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "qwen3.5:latest"}]})
        if request.url.path == "/api/chat":
            body = json.loads(request.content.decode("utf-8"))
            lines = [
                {"model": body["model"], "message": {"role": "assistant", "content": "real "}, "done": False},
                {
                    "model": body["model"],
                    "message": {"role": "assistant", "content": "stream"},
                    "done": True,
                    "prompt_eval_count": 5,
                    "eval_count": 2,
                },
            ]
            return httpx.Response(200, content="\n".join(json.dumps(x) for x in lines) + "\n")
        return httpx.Response(404)

    tx = httpx.MockTransport(stream_handler)
    engine = OpenCoreServingEngine(
        ollama_bridge=OllamaRuntimeBridge(transport=tx),
        vllm_bridge=VLLMRuntimeBridge(transport=_dead_transport()),
        discovery=LocalRuntimeDiscovery(transport=tx),
    )
    req = ChatCompletionRequest(
        model="keelway-coder:7b",
        messages=[MessageSchema(role="user", content="code")],
    )
    chunks = [c async for c in engine.stream_inference(req)]
    text = "".join(c.delta_content for c in chunks)
    assert "real stream" in text
    assert all(c.simulated is False for c in chunks)
