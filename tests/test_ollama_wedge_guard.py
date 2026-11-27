"""P0-6: Ollama wedge guard — OLLAMA_BASE_URL is honored, request timeouts
are bounded, and timeouts surface as honest ProviderError(503)."""

import httpx
import pytest

from core.config import settings
from core.models.provider import ProviderError
from core.opencore.runtime import OllamaRuntimeBridge, _post_local_json
from keelway.models.gateway import ModelGateway, ProviderKind


def test_ollama_bridge_defaults_to_configured_base_url():
    bridge = OllamaRuntimeBridge()
    assert bridge.base_url == settings.ollama_base_url
    assert bridge.timeout_s <= 30.0


def test_keelway_gateway_honors_ollama_base_url_env(monkeypatch):
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://custom-host:9999")
    gw = ModelGateway(provider=ProviderKind.LOCAL_OLLAMA)
    assert gw.endpoint_url == "http://custom-host:9999"


@pytest.mark.asyncio
async def test_timeout_maps_to_honest_provider_error():
    def _timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("connect timed out", request=request)

    transport = httpx.MockTransport(_timeout)
    with pytest.raises(ProviderError) as exc_info:
        await _post_local_json("http://127.0.0.1:1", "/api/chat", {}, transport, 30.0, "Ollama", "keelway-core:7b")
    assert exc_info.value.status_code == 503
    assert "timed out" in str(exc_info.value)
