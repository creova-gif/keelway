import httpx
import pytest

from core.api.schemas import CompletionRequestSchema, MessageSchema
from core.models.adapters import local as local_mod
from core.models.adapters.local import LocalAdapter


def _req():
    return CompletionRequestSchema(messages=[MessageSchema(role="user", content="hi")], max_tokens=16)


def _transport(routes):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        fn = routes.get((request.method, request.url.path))
        return fn(request) if fn else httpx.Response(404, json={"error": "not found"})

    t = httpx.MockTransport(handler)
    t.calls = calls
    return t


@pytest.fixture(autouse=True)
def _fixed_hardware(monkeypatch):
    monkeypatch.setattr(local_mod, "_recommended_model", lambda: "qwen2.5-coder:7b")


def test_down_server_is_unavailable():
    def boom(request):
        raise httpx.ConnectError("refused")
    a = LocalAdapter(base_url="http://x", api="auto", transport=_transport({("GET", "/api/tags"): boom, ("GET", "/v1/models"): boom}))
    assert a.is_available() is False
    assert a.describe()["up"] is False


def test_ollama_uses_installed_model_when_configured_one_is_missing():
    t = _transport({
        ("GET", "/api/tags"): lambda r: httpx.Response(200, json={"models": [{"name": "llama3.2:3b"}, {"name": "qwen2.5-coder:7b"}]}),
    })
    a = LocalAdapter(base_url="http://x", default_model="qwen3.5:latest", api="auto", transport=t)
    assert a.is_available()
    assert a.resolve_model() == "qwen2.5-coder:7b"  # hardware-recommended beats arbitrary first


def test_configured_model_matches_latest_tag():
    t = _transport({("GET", "/api/tags"): lambda r: httpx.Response(200, json={"models": [{"name": "mistral:latest"}]})})
    assert LocalAdapter(base_url="http://x", default_model="mistral", api="ollama", transport=t).resolve_model() == "mistral:latest"


@pytest.mark.asyncio
async def test_ollama_chat_roundtrip():
    def chat(r):
        body = r.read().decode()
        assert '"model":"llama3.2:3b"' in body.replace(" ", "")
        return httpx.Response(200, json={"model": "llama3.2:3b", "message": {"content": "ok"}, "prompt_eval_count": 3, "eval_count": 2})
    t = _transport({
        ("GET", "/api/tags"): lambda r: httpx.Response(200, json={"models": [{"name": "llama3.2:3b"}]}),
        ("POST", "/api/chat"): chat,
    })
    res = await LocalAdapter(base_url="http://x", api="auto", transport=t).complete(_req())
    assert (res.content, res.cost_usd, res.usage["total_tokens"]) == ("ok", 0.0, 5)


@pytest.mark.asyncio
async def test_vllm_openai_compatible_roundtrip():
    t = _transport({
        ("GET", "/api/tags"): lambda r: httpx.Response(404),
        ("GET", "/v1/models"): lambda r: httpx.Response(200, json={"data": [{"id": "Qwen/Qwen2.5-Coder-7B-Instruct"}]}),
        ("POST", "/v1/chat/completions"): lambda r: httpx.Response(200, json={
            "model": "Qwen/Qwen2.5-Coder-7B-Instruct",
            "choices": [{"message": {"role": "assistant", "content": "vllm ok"}}],
            "usage": {"prompt_tokens": 4, "completion_tokens": 3},
        }),
    })
    a = LocalAdapter(base_url="http://x", api="auto", transport=t)
    assert a.describe()["api"] == "openai"
    res = await a.complete(_req())
    assert (res.content, res.model, res.cost_usd) == ("vllm ok", "Qwen/Qwen2.5-Coder-7B-Instruct", 0.0)


@pytest.mark.asyncio
async def test_missing_ollama_model_says_what_to_pull():
    t = _transport({
        ("GET", "/api/tags"): lambda r: httpx.Response(200, json={"models": []}),
        ("POST", "/api/chat"): lambda r: httpx.Response(404, json={"error": "model not found"}),
    })
    a = LocalAdapter(base_url="http://x", api="ollama", transport=t)
    assert a.is_available() is False
    assert a.describe()["up"] is True and a.describe()["model"] is None
    with pytest.raises(RuntimeError, match="ollama pull qwen2.5-coder:7b"):
        await a.complete(_req())


def test_probe_is_cached():
    t = _transport({("GET", "/api/tags"): lambda r: httpx.Response(200, json={"models": [{"name": "m"}]})})
    a = LocalAdapter(base_url="http://x", api="ollama", transport=t)
    for _ in range(5):
        a.is_available()
    assert len(t.calls) == 1


def test_embedding_models_are_never_picked_for_chat():
    t = _transport({("GET", "/api/tags"): lambda r: httpx.Response(200, json={"models": [
        {"name": "nomic-embed-text:latest", "details": {"family": "nomic-bert"}},
        {"name": "bge-m3:latest", "details": {"families": ["bert"]}},
        {"name": "llama3.2:3b", "details": {"family": "llama"}},
    ]})})
    a = LocalAdapter(base_url="http://x", default_model="qwen3.5:latest", api="ollama", transport=t)
    assert a.resolve_model() == "llama3.2:3b"
    assert a.describe()["installed"] == ["llama3.2:3b"]
