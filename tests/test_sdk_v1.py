"""
Keelway Python SDK v1 & Interactive Hybrid Web Console Verification Suite.

Exercises both `AsyncKeelwayClient` and `KeelwayClient` deterministically over
`httpx.MockTransport` (zero network sockets required) plus structural, air-gap CSP,
and JavaScript syntax validation on `web-console/index.html`.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, List, Tuple

import httpx
import pytest

from core.sdk import (
    AirGapEgressError,
    AsyncKeelwayClient,
    AuthenticationError,
    BudgetExceededError,
    KeelwayClient,
    KeelwayError,
    PermissionDeniedError,
    PolicyViolationError,
    QuorumRequiredError,
    RateLimitExceededError,
    TaskNotFoundError,
)


def _make_mock_router() -> Tuple[httpx.MockTransport, List[Dict[str, Any]]]:
    """Builds a deterministic MockTransport recording all requests for sync & async clients."""
    recorded: List[Dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        raw_body = request.content.decode("utf-8") if request.content else ""
        parsed_body = json.loads(raw_body) if raw_body else None
        recorded.append(
            {
                "method": request.method,
                "path": request.url.path,
                "params": dict(request.url.params),
                "headers": dict(request.headers),
                "json": parsed_body,
            }
        )

        path = request.url.path
        method = request.method

        if method == "GET" and path == "/v1/models":
            return httpx.Response(
                200,
                json={
                    "object": "list",
                    "data": [
                        {"id": "keelway-core:7b", "category": "open_weight", "owned_by": "open_weight"},
                        {"id": "gpt-4o", "category": "closed_proprietary", "owned_by": "openai"},
                    ],
                },
            )

        if method == "GET" and path == "/v1/usage":
            return httpx.Response(
                200,
                json={
                    "sovereign_efficiency_index": 98.4,
                    "local_inference_ratio": 0.85,
                    "quantified_local_savings_usd": 42.50,
                    "billed_cloud_expenditure_usd": 1.25,
                    "total_cost_usd": 1.25,
                },
            )

        if method == "POST" and path == "/v1/chat/completions":
            if parsed_body and parsed_body.get("stream"):
                sse_body = (
                    ": keep-alive\n\n"
                    'data: {"id":"chatcmpl-1","choices":[{"index":0,"delta":{"content":"def "}}]}\n\n'
                    'data: {"id":"chatcmpl-1","choices":[{"index":0,"delta":{"content":"verify(): pass"}}]}\n\n'
                    "data: [DONE]\n\n"
                    'data: {"id":"ignored-after-done","choices":[{"index":0,"delta":{"content":"NEVER"}}]}\n\n'
                )
                return httpx.Response(
                    200,
                    content=sse_body.encode("utf-8"),
                    headers={"Content-Type": "text/event-stream"},
                )
            return httpx.Response(
                200,
                json={
                    "id": "chatcmpl-sync-1",
                    "object": "chat.completion",
                    "model": parsed_body.get("model") or "keelway-core:7b",
                    "choices": [{"index": 0, "message": {"role": "assistant", "content": '{"ok": true}'}}],
                    "usage": {"prompt_tokens": 12, "completion_tokens": 6, "total_tokens": 18},
                },
            )

        if method == "POST" and path == "/v1/responses":
            return httpx.Response(
                200,
                json={
                    "id": "resp_keelway_001",
                    "object": "response",
                    "model": parsed_body.get("model") or "keelway-core:7b",
                    "previous_response_id": parsed_body.get("previous_response_id"),
                    "output_text": "Stateful response verified.",
                    "usage": {"total_tokens": 24},
                },
            )

        if method == "GET" and path.startswith("/v1/responses/"):
            resp_id = path.split("/")[-1]
            return httpx.Response(
                200,
                json={
                    "id": resp_id,
                    "object": "response",
                    "output_text": "Fetched stored response.",
                },
            )

        if method == "POST" and path == "/v1/routing/explain":
            return httpx.Response(
                200,
                json={
                    "selected_model": "keelway-core:7b",
                    "provenance": {
                        "model_license": "Apache-2.0 (Open-Weight)",
                        "hosting_location": "Local Loopback",
                        "inference_operator": "Self-Hosted Keelway Daemon",
                        "data_residency_boundary": "Zero External Egress",
                    },
                    "fallback_chain": ["keelway-core:7b", "qwen2.5-coder:7b"],
                    "routing_reason": "Privacy private enforced zero-egress OpenCore checkpoint.",
                },
            )

        if method == "GET" and path == "/v1/opencore/status":
            return httpx.Response(
                200,
                json={
                    "status": "healthy",
                    "hardware": {"accelerator": "mps", "vram_gb": 36.0},
                    "telemetry": {"loaded_count": 1, "allocated_vram_gb": 4.5},
                },
            )

        if method == "GET" and path == "/v1/opencore/weights":
            return httpx.Response(
                200,
                json=[{"model_id": "keelway-core:7b", "quantization": "awq_4bit", "is_cached": True}],
            )

        if method == "POST" and path == "/v1/opencore/models/load":
            return httpx.Response(
                200,
                json={
                    "model_id": parsed_body["model_id"],
                    "backend": parsed_body.get("backend", "mock"),
                    "quantization": parsed_body.get("quantization", "awq_4bit"),
                    "resident": True,
                },
            )

        if method == "POST" and path == "/v1/opencore/models/unload":
            return httpx.Response(
                200,
                json={"model_id": parsed_body["model_id"], "unloaded": True},
            )

        if method == "POST" and path == "/v1/opencore/modelfile":
            return httpx.Response(
                200,
                json={
                    "model_id": parsed_body["model_id"],
                    "modelfile": f"FROM {parsed_body['base_source']}\nPARAMETER temperature 0.2",
                    "sha256": "a" * 64,
                },
            )

        if method == "POST" and path == "/v1/opencore/adapt/recipe":
            return httpx.Response(
                200,
                json={
                    "base_model_id": parsed_body["base_model_id"],
                    "task": parsed_body["task"],
                    "target_languages": parsed_body.get("target_languages", []),
                    "peft_config": {"r": 16, "lora_alpha": 32},
                    "unsloth_recipe": "# unsloth recipe",
                },
            )

        if method == "POST" and path == "/v1/governance/tenants":
            return httpx.Response(200, json={"status": "created", **parsed_body})

        if method == "POST" and path == "/v1/governance/keys":
            return httpx.Response(
                200,
                json={
                    "tenant_id": parsed_body["tenant_id"],
                    "name": parsed_body["name"],
                    "scopes": parsed_body.get("scopes", []),
                    "api_key": "kw_live_test_99887766",
                },
            )

        if method == "POST" and path == "/v1/governance/evaluate":
            return httpx.Response(
                200,
                json={"allowed": True, "decision": "ALLOW", "evaluated": parsed_body},
            )

        if method == "GET" and path == "/v1/governance/audit":
            return httpx.Response(
                200,
                json={
                    "chain_valid": True,
                    "entries": [{"seq": 1, "tenant_id": "t-1", "action": "create_tenant", "entry_hash": "f" * 64}],
                },
            )

        if method == "POST" and path == "/v1/eval/swarm":
            return httpx.Response(
                200,
                json={
                    "graph_id": "keelway-mirofish-01",
                    "savings_pct": 74.5,
                    "open_weight_calls": 6,
                    "closed_cloud_calls": 2,
                    "profiles": [{"name": "NairobiCoreDev", "tier": "citizen"}],
                    "episodes": [{"round": 1, "agent": "NairobiCoreDev", "action": "POST", "content": "Adopted"}],
                },
            )

        if method == "GET" and path == "/health":
            return httpx.Response(200, json={"status": "ok", "database_connected": True})

        return httpx.Response(404, json={"detail": f"Unhandled mock route {method} {path}"})

    return httpx.MockTransport(handler), recorded


def test_sync_models_and_usage():
    transport, recorded = _make_mock_router()
    with KeelwayClient(token="kw_live_demo", transport=transport) as client:
        models = client.list_models(category="open_weight", provider="open_weight", capability="code")
        assert len(models["data"]) == 2
        assert recorded[0]["params"] == {
            "category": "open_weight",
            "provider": "open_weight",
            "capability": "code",
        }
        assert recorded[0]["headers"]["authorization"] == "Bearer kw_live_demo"

        usage = client.get_usage()
        assert usage["sovereign_efficiency_index"] == 98.4
        assert usage["local_inference_ratio"] == 0.85


@pytest.mark.asyncio
async def test_async_models_and_usage():
    transport, recorded = _make_mock_router()
    async with AsyncKeelwayClient(token="kw_live_async", transport=transport) as client:
        models = await client.list_models(category="closed_proprietary")
        assert models["object"] == "list"
        assert recorded[0]["params"] == {"category": "closed_proprietary"}

        usage = await client.get_usage()
        assert usage["quantified_local_savings_usd"] == 42.50


def test_sync_chat_complete_json_mode_and_privacy():
    transport, recorded = _make_mock_router()
    with KeelwayClient(transport=transport) as client:
        resp = client.chat_complete(
            messages=[{"role": "user", "content": "Return JSON status"}],
            model="keelway-core:7b",
            temperature=0.1,
            max_tokens=512,
            response_format={"type": "json_object"},
            privacy_level="private",
            required_capabilities=["code", "json"],
            max_cost_usd=0.0,
        )
        assert resp["choices"][0]["message"]["content"] == '{"ok": true}'
        sent = recorded[0]["json"]
        assert sent["privacy_level"] == "private"
        assert sent["response_format"] == {"type": "json_object"}
        assert sent["required_capabilities"] == ["code", "json"]
        assert sent["max_cost_usd"] == 0.0
        assert sent["stream"] is False


@pytest.mark.asyncio
async def test_async_chat_complete_and_string_shorthand():
    transport, recorded = _make_mock_router()
    async with AsyncKeelwayClient(transport=transport) as client:
        resp = await client.chat_complete(
            messages="Quick prompt shorthand",
            model="keelway-core:7b",
            privacy_level="private",
        )
        assert resp["model"] == "keelway-core:7b"
        assert recorded[0]["json"]["messages"] == [{"role": "user", "content": "Quick prompt shorthand"}]


def test_sync_stream_chat_sse_parsing():
    transport, recorded = _make_mock_router()
    with KeelwayClient(transport=transport) as client:
        chunks = list(
            client.stream_chat(
                messages=[{"role": "user", "content": "Stream code"}],
                model="keelway-core:7b",
                privacy_level="private",
            )
        )
        assert len(chunks) == 2
        text = "".join(c["choices"][0]["delta"]["content"] for c in chunks)
        assert text == "def verify(): pass"
        assert recorded[0]["json"]["stream"] is True


@pytest.mark.asyncio
async def test_async_stream_chat_sse_parsing():
    transport, _ = _make_mock_router()
    async with AsyncKeelwayClient(transport=transport) as client:
        chunks = []
        async for chunk in client.stream_chat(
            messages=[{"role": "user", "content": "Stream async"}],
            model="keelway-core:7b",
        ):
            chunks.append(chunk)
        assert len(chunks) == 2
        assert chunks[0]["choices"][0]["delta"]["content"] == "def "
        assert chunks[1]["choices"][0]["delta"]["content"] == "verify(): pass"


@pytest.mark.asyncio
async def test_responses_api_create_and_get_both_clients():
    transport, recorded = _make_mock_router()
    async with AsyncKeelwayClient(transport=transport) as aclient:
        created = await aclient.create_response(
            input_data="Explain zero-egress routing",
            model="keelway-core:7b",
            instructions="Be concise",
            previous_response_id="resp_prev_00",
            speculative=True,
            privacy_level="private",
            text={"format": {"type": "json_object"}},
        )
        assert created["id"] == "resp_keelway_001"
        assert recorded[0]["json"] == {
            "input": "Explain zero-egress routing",
            "model": "keelway-core:7b",
            "instructions": "Be concise",
            "previous_response_id": "resp_prev_00",
            "speculative": True,
            "privacy_level": "private",
            "text": {"format": {"type": "json_object"}},
        }
        fetched = await aclient.get_response("resp_keelway_001")
        assert fetched["id"] == "resp_keelway_001"

    sync_transport, _ = _make_mock_router()
    with KeelwayClient(transport=sync_transport) as sclient:
        s_created = sclient.create_response(input_data="Turn 2", previous_response_id="resp_keelway_001")
        assert s_created["previous_response_id"] == "resp_keelway_001"
        s_fetched = sclient.get_response("resp_keelway_001")
        assert s_fetched["output_text"] == "Fetched stored response."


@pytest.mark.asyncio
async def test_explain_route_sync_and_async():
    transport, recorded = _make_mock_router()
    async with AsyncKeelwayClient(transport=transport) as aclient:
        explanation = await aclient.explain_route(
            messages=[{"role": "user", "content": "Inspect sensitive ledger"}],
            privacy_level="private",
            required_capabilities=["code"],
            max_cost_usd=0.01,
        )
        assert explanation["selected_model"] == "keelway-core:7b"
        assert explanation["provenance"]["data_residency_boundary"] == "Zero External Egress"
        assert recorded[0]["path"] == "/v1/routing/explain"

    sync_transport, _ = _make_mock_router()
    with KeelwayClient(transport=sync_transport) as sclient:
        s_exp = sclient.explain_route(messages="Check route", model="keelway-core:7b")
        assert "fallback_chain" in s_exp


@pytest.mark.asyncio
async def test_opencore_subsystem_methods_sync_and_async():
    transport, recorded = _make_mock_router()
    async with AsyncKeelwayClient(transport=transport) as aclient:
        st = await aclient.opencore_status()
        assert st["status"] == "healthy"

        weights = await aclient.opencore_weights()
        assert weights[0]["model_id"] == "keelway-core:7b"

        loaded = await aclient.opencore_load_model("keelway-core:7b", quantization="awq_4bit", backend="mock")
        assert loaded["resident"] is True

        mf = await aclient.opencore_modelfile(
            model_id="keelway-core:7b",
            base_source="qwen3.5:latest",
            quantization="q4_k_m",
            adapter_id="afri-lora-v1",
        )
        assert "FROM qwen3.5:latest" in mf["modelfile"]
        assert recorded[3]["json"]["adapter_id"] == "afri-lora-v1"

        recipe = await aclient.opencore_adapt_recipe(
            base_model_id="keelway-core:7b",
            task="multilingual_localization",
            target_languages=["Swahili", "Yoruba", "Hausa", "Amharic"],
        )
        assert recipe["target_languages"] == ["swahili", "yoruba", "hausa", "amharic"]

        unloaded = await aclient.opencore_unload_model("keelway-core:7b")
        assert unloaded["unloaded"] is True

    sync_transport, _ = _make_mock_router()
    with KeelwayClient(transport=sync_transport) as sclient:
        assert sclient.opencore_status()["status"] == "healthy"
        assert len(sclient.opencore_weights()) == 1
        assert sclient.opencore_load_model("keelway-nano:1.5b")["resident"] is True
        assert "FROM" in sclient.opencore_modelfile("keelway-nano:1.5b")["modelfile"]
        assert sclient.opencore_adapt_recipe(target_languages=["Swahili"])["target_languages"] == ["swahili"]
        assert sclient.opencore_unload_model("keelway-nano:1.5b")["unloaded"] is True


@pytest.mark.asyncio
async def test_governance_and_api_keys_sync_and_async():
    transport, _ = _make_mock_router()
    async with AsyncKeelwayClient(transport=transport) as aclient:
        tenant = await aclient.create_tenant(
            "tenant-nairobi",
            "Nairobi Sovereign Bank",
            budget_usd=50.0,
            data_residency="zero_egress",
        )
        assert tenant["tenant_id"] == "tenant-nairobi"
        assert tenant["budget_usd"] == 50.0

        key = await aclient.issue_api_key("tenant-nairobi", "prod-worker", scopes=["inference:write"])
        assert key["api_key"].startswith("kw_live_")

        verdict = await aclient.evaluate_governance(
            tenant_id="tenant-nairobi",
            model="keelway-core:7b",
            estimated_cost_usd=0.0,
        )
        assert verdict["allowed"] is True

        audit = await aclient.get_governance_audit()
        assert audit["chain_valid"] is True

    sync_transport, _ = _make_mock_router()
    with KeelwayClient(transport=sync_transport) as sclient:
        assert sclient.create_tenant("t-2", "Org 2", rate_limit_rpm=60)["rate_limit_rpm"] == 60
        assert sclient.issue_api_key("t-2", "k-2")["api_key"].startswith("kw_live_")
        assert sclient.evaluate_governance(tenant_id="t-2")["decision"] == "ALLOW"
        assert sclient.get_governance_audit()["chain_valid"] is True


@pytest.mark.asyncio
async def test_mirofish_swarm_execution_sync_and_async():
    entities = [
        {"name": "Regulator", "type": "Government", "summary": "Central bank", "tier": "influencer"},
        {"name": "Builder", "type": "Developer", "summary": "OSS fintech dev", "tier": "citizen"},
    ]
    transport, recorded = _make_mock_router()
    async with AsyncKeelwayClient(transport=transport) as aclient:
        report = await aclient.run_swarm(
            seed_text="Sovereign payment rail launch",
            simulation_goal="Forecast Q3 developer adoption",
            entities_spec=entities,
            rounds=2,
            mode="mock",
        )
        assert report["savings_pct"] == 74.5
        assert report["open_weight_calls"] == 6
        assert recorded[0]["json"]["rounds"] == 2

    sync_transport, _ = _make_mock_router()
    with KeelwayClient(transport=sync_transport) as sclient:
        s_report = sclient.run_swarm("Seed", "Goal", entities, rounds=3, mode="mock")
        assert s_report["graph_id"] == "keelway-mirofish-01"


@pytest.mark.parametrize(
    "status_code,detail,expected_exc",
    [
        (401, "Invalid or expired kw_live token", AuthenticationError),
        (402, "Tenant monthly spend cap of $25.00 exceeded", BudgetExceededError),
        (403, "Blocked external cloud egress under Air-Gap policy", AirGapEgressError),
        (403, "Dual-human quorum approval required", QuorumRequiredError),
        (403, "Scope governance:admin missing", PermissionDeniedError),
        (404, "Response resp_missing not found", TaskNotFoundError),
        (422, "Model violates sovereign policy", PolicyViolationError),
        (429, "Tenant rate limit 120 RPM exceeded", RateLimitExceededError),
        (500, "Unexpected upstream error", KeelwayError),
    ],
)
def test_typed_error_mapping_sync(status_code: int, detail: str, expected_exc: type):
    transport = httpx.MockTransport(lambda _req: httpx.Response(status_code, json={"detail": detail}))
    with KeelwayClient(transport=transport) as client:
        with pytest.raises(expected_exc) as exc_info:
            client.get_usage()
        assert exc_info.value.details.get("status") == status_code


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status_code,detail,expected_exc",
    [
        (401, "Missing bearer token", AuthenticationError),
        (402, "Tenant budget exhausted", BudgetExceededError),
        (403, "Zero-egress boundary blocked cloud call", AirGapEgressError),
        (404, "Checkpoint not loaded", TaskNotFoundError),
        (422, "Invalid residency constraint", PolicyViolationError),
        (429, "Rate limit exceeded", RateLimitExceededError),
    ],
)
async def test_typed_error_mapping_async_and_streaming(status_code: int, detail: str, expected_exc: type):
    transport = httpx.MockTransport(lambda _req: httpx.Response(status_code, json={"detail": detail}))
    async with AsyncKeelwayClient(transport=transport) as client:
        with pytest.raises(expected_exc):
            await client.chat_complete(messages="Hello")
        with pytest.raises(expected_exc):
            async for _ in client.stream_chat(messages="Hello"):
                pass


def test_backwards_compatible_legacy_methods_preserved():
    transport, _ = _make_mock_router()
    with KeelwayClient(transport=transport) as client:
        assert client.get_health()["status"] == "ok"
        for legacy_method in (
            "get_status",
            "run_doctor",
            "get_sbom",
            "get_evidence_room",
            "create_task",
            "get_task",
            "list_tasks",
            "step_agent",
            "approve_step",
            "list_flight_tapes",
            "get_flight_tape",
            "fork_flight_tape",
            "search_codebase",
            "get_code_hierarchy",
            "record_fact",
            "query_facts",
            "execute_self_healing",
        ):
            assert callable(getattr(client, legacy_method))
            assert callable(getattr(AsyncKeelwayClient, legacy_method))


class _ConsoleHTMLInspector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.external_assets: List[str] = []
        self.tab_buttons: List[str] = []
        self.tab_panels: List[str] = []
        self.scripts: List[str] = []
        self._in_script = False
        self._script_buf: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, str | None]]) -> None:
        attr_map = dict(attrs)
        if tag in ("script", "link", "img", "iframe"):
            url = attr_map.get("src") or attr_map.get("href") or ""
            if url.startswith("http://") or url.startswith("https://") or url.startswith("//"):
                self.external_assets.append(url)
        classes = (attr_map.get("class") or "").split()
        if "nav-tab" in classes and attr_map.get("id"):
            self.tab_buttons.append(attr_map["id"] or "")
        if "tab-panel" in classes and attr_map.get("id"):
            self.tab_panels.append(attr_map["id"] or "")
        if tag == "script" and not attr_map.get("src"):
            self._in_script = True
            self._script_buf = []

    def handle_data(self, data: str) -> None:
        if self._in_script:
            self._script_buf.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._in_script:
            self._in_script = False
            self.scripts.append("".join(self._script_buf))


def test_web_console_six_tabs_airgap_csp_and_js_syntax():
    console_path = Path(__file__).resolve().parent.parent / "web-console" / "index.html"
    assert console_path.exists(), "web-console/index.html must exist"
    html_text = console_path.read_text(encoding="utf-8")

    inspector = _ConsoleHTMLInspector()
    inspector.feed(html_text)

    # 1. Zero external http/https CDN assets (strict Air-Gap CSP compliance)
    assert inspector.external_assets == [], f"Air-gap violation: external assets found: {inspector.external_assets}"
    assert not re.search(r"<script[^>]+src=['\"]https?://", html_text, re.IGNORECASE)

    # 2. All 6 interactive tabs & panels present
    assert inspector.tab_buttons == [
        "tab-playground",
        "tab-opencore",
        "tab-routing",
        "tab-swarm",
        "tab-governance",
        "tab-sync",
    ]
    assert inspector.tab_panels == [
        "panel-playground",
        "panel-opencore",
        "panel-routing",
        "panel-swarm",
        "panel-governance",
        "panel-sync",
    ]

    # 3. Keelway visual tokens & required API routes wired
    # Palette tokens track the KEEL-WEB-028 monochrome zinc refresh:
    # surface #09090B (was #0B0F14), amber remapped to zinc secondary #D4D4D8.
    for required_token in (
        "#09090B",
        "#2DD4BF",
        "#D4D4D8",
        "/v1/models",
        "/v1/chat/completions",
        "/v1/responses",
        "previous_response_id",
        "/v1/usage",
        "/v1/opencore/status",
        "/v1/opencore/runtime/discover",
        "/v1/opencore/models/load",
        "/v1/opencore/models/unload",
        "/v1/opencore/modelfile",
        "/v1/opencore/adapt/recipe",
        "Swahili",
        "Yoruba",
        "Hausa",
        "Amharic",
        "/v1/routing/explain",
        "/v1/routing/decisions",
        "/v1/eval/swarm",
        "/v1/governance/tenants",
        "/v1/governance/keys",
        "/v1/governance/evaluate",
        "/v1/governance/audit",
        "Vector Clocks",
        "Cross-Machine",
    ):
        assert required_token in html_text, f"Missing expected console token: {required_token}"

    # 4. Validate embedded JavaScript syntax via `node --check` when Node is installed
    assert len(inspector.scripts) >= 1
    combined_js = "\n".join(inspector.scripts)
    node_bin = shutil.which("node")
    if node_bin:
        with tempfile.NamedTemporaryFile("w", suffix=".js", encoding="utf-8", delete=False) as tmp:
            tmp.write(combined_js)
            tmp_path = Path(tmp.name)
        try:
            proc = subprocess.run(
                [node_bin, "--check", str(tmp_path)],
                capture_output=True,
                text=True,
                timeout=10,
            )
            assert proc.returncode == 0, f"Embedded JS syntax error: {proc.stderr}"
        finally:
            tmp_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_async_client_live_asgi_transport_integration():
    """Verifies AsyncKeelwayClient transport=ASGITransport(...) against live FastAPI routes."""
    from fastapi import FastAPI
    from httpx import ASGITransport
    from core.main import app
    from core.api.opencore_routes import router as opencore_router
    from core.security.auth import launch_token

    token = launch_token()
    transport = ASGITransport(app=app)
    async with AsyncKeelwayClient(base_url="http://testserver", token=token, transport=transport) as client:
        models = await client.list_models(category="open_weight")
        assert models["object"] == "list"
        assert len(models["data"]) >= 1

        usage = await client.get_usage()
        assert "currency" in usage

    oc_app = FastAPI()
    oc_app.include_router(opencore_router)
    async with AsyncKeelwayClient(base_url="http://testserver", transport=ASGITransport(app=oc_app)) as oc_client:
        oc_status = await oc_client.opencore_status()
        assert oc_status["status"] == "healthy"

        mf = await oc_client.opencore_modelfile("keelway-core:7b")
        assert "FROM" in mf["modelfile"]

        recipe = await oc_client.opencore_adapt_recipe(target_languages=["Swahili", "Yoruba"])
        assert "swahili" in recipe["target_languages"]

