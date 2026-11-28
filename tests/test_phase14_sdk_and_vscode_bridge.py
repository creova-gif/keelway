"""
Phase 14B & Integration Verification Suite — Tri-Language SDK Parity, Official VS Code / Cursor
Extension Bridge (`extensions/vscode-keelway`), Zero-Origin Loopback Security, and Website
`280`-Route OpenAPI + `22`-Feature Product-Facts Synchronization.
"""

from __future__ import annotations

import inspect
import json
import uuid
from pathlib import Path
from typing import Any, Dict, List

import httpx
import pytest
from httpx import ASGITransport

from core.main import app
from core.sdk import (
    AsyncKeelwayClient,
    AsyncPlatformClient,
    KeelwayClient,
    PermissionDeniedError,
    PolicyViolationError,
    SyncPlatformClient,
)
from core.security.auth import launch_token

REPO_ROOT = Path(__file__).resolve().parent.parent
SITE_DIR = REPO_ROOT / "web-next"
EXT_DIR = REPO_ROOT / "extensions" / "vscode-keelway"

PHASE14_PYTHON_METHODS = (
    "set_breakpoint",
    "list_breakpoints",
    "delete_breakpoint",
    "start_debug_session",
    "list_debug_sessions",
    "step_debug_session",
    "get_debugger_codelens",
)

PHASE14_TS_METHODS = (
    "setBreakpoint",
    "listBreakpoints",
    "deleteBreakpoint",
    "startDebugSession",
    "listDebugSessions",
    "stepDebugSession",
    "getDebuggerCodelens",
)

PHASE14_GO_METHODS = (
    "SetBreakpoint",
    "ListBreakpoints",
    "DeleteBreakpoint",
    "StartDebugSession",
    "ListDebugSessions",
    "StepDebugSession",
    "GetDebuggerCodelens",
)

FORBIDDEN_PRIVATE_TOKENS = (
    # NOTE: "creova-gif" removed in KEEL-WEB-055 — the public open-core org
    # is deliberately linked from the shipped site; "creovas-projects" stays forbidden.
    "creovas-projects",
    "keelway.git",
    "KEEL-",
    "verify_engineering_gates.sh",
    "Antigravity",
    "gstack",
)


def _make_sync_mock_transport() -> httpx.MockTransport:
    bp_store: List[Dict[str, Any]] = []
    sess_store: Dict[str, Dict[str, Any]] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        raw = request.content.decode("utf-8") if request.content else ""
        body = json.loads(raw) if raw else {}
        path, params = request.url.path, dict(request.url.params)
        role = request.headers.get("X-Keelway-Role", "owner")

        if role == "viewer" and request.method in ("POST", "DELETE"):
            return httpx.Response(403, json={"detail": "Permission denied for viewer role"})

        if path == "/v1/platform/debugger/breakpoints" and request.method == "POST":
            rec = {
                "breakpoint_id": f"bp-{len(bp_store) + 1}",
                "workspace_id": body.get("workspace_id", "default"),
                "workflow_id": body.get("workflow_id", "WF-STUDIO-01"),
                "condition_type": body.get("condition_type", "always"),
                "threshold": body.get("threshold"),
                "enabled": body.get("enabled", True),
            }
            bp_store.append(rec)
            return httpx.Response(200, json=rec)

        if path == "/v1/platform/debugger/breakpoints" and request.method == "GET":
            ws = params.get("workspace_id", "default")
            matched = [b for b in bp_store if b["workspace_id"] == ws]
            return httpx.Response(200, json={"workspace_id": ws, "count": len(matched), "breakpoints": matched})

        if path.startswith("/v1/platform/debugger/breakpoints/") and request.method == "DELETE":
            bp_id = path.rsplit("/", 1)[-1]
            return httpx.Response(200, json={"deleted": True, "breakpoint_id": bp_id, "workspace_id": params.get("workspace_id", "default")})

        if path == "/v1/platform/debugger/sessions" and request.method == "POST":
            sid = "dbg-sync-01"
            sess = {
                "session_id": sid,
                "workspace_id": body.get("workspace_id", "default"),
                "workflow_id": body.get("workflow_id", "WF-STUDIO-01"),
                "status": "PAUSED",
                "current_step_index": 1,
                "step_depth": 0,
                "total_steps": 3,
                "variables": dict(body.get("initial_state") or {"tenant": "acme"}),
                "mutation_count": 0,
                "frame_sha256": "a" * 64,
            }
            sess_store[sid] = sess
            return httpx.Response(200, json=sess)

        if path == "/v1/platform/debugger/sessions" and request.method == "GET":
            items = list(sess_store.values())
            return httpx.Response(200, json={"workspace_id": params.get("workspace_id", "default"), "count": len(items), "sessions": items})

        if path.endswith("/step") and request.method == "POST":
            sid = path.split("/")[-2]
            patch = body.get("state_patch") or {}
            if "sk-live-" in json.dumps(patch):
                return httpx.Response(422, json={"detail": "DLP secret blocked", "code": "policy_violation"})
            sess = dict(sess_store[sid])
            if body.get("action") == "mutate_state":
                sess["variables"] = {**sess["variables"], **patch}
                sess["mutation_count"] += 1
            elif body.get("action") == "continue":
                sess["status"] = "COMPLETED"
            sess_store[sid] = sess
            return httpx.Response(200, json=sess)

        if path == "/v1/platform/debugger/codelens" and request.method == "GET":
            ws = params.get("workspace_id", "default")
            return httpx.Response(
                200,
                json={
                    "workspace_id": ws,
                    "bridge": {
                        "extension_id": "keelway.vscode-keelway",
                        "vscode_attach_uri": f"vscode://keelway.vscode-keelway/attach?port=7420&workspace={ws}",
                        "cursor_attach_uri": f"cursor://keelway.vscode-keelway/attach?port=7420&workspace={ws}",
                    },
                    "lenses": [{"symbol": "triage_claim", "line_start": 8, "p50_ms": 142}],
                },
            )

        return httpx.Response(404, json={"detail": f"Unhandled {path}"})

    return httpx.MockTransport(handler)


def test_python_sync_and_async_debugger_sdk_signature_and_sync_parity() -> None:
    for method_name in PHASE14_PYTHON_METHODS:
        sync_fn = getattr(SyncPlatformClient, method_name)
        async_fn = getattr(AsyncPlatformClient, method_name)
        assert inspect.iscoroutinefunction(async_fn)
        assert not inspect.iscoroutinefunction(sync_fn)
        assert inspect.signature(sync_fn) == inspect.signature(async_fn), f"Signature mismatch on {method_name}"

    transport = _make_sync_mock_transport()
    with KeelwayClient(base_url="http://keelway.local", token="kw_test", transport=transport) as client:
        bp = client.platform.set_breakpoint("verify_ledger", workspace_id="ws-sync", condition_type="cost_usd_gt", threshold=0.25)
        assert bp["breakpoint_id"] == "bp-1"
        listed = client.platform.list_breakpoints(workspace_id="ws-sync")
        assert listed["count"] == 1
        sess = client.platform.start_debug_session("WF-STUDIO-01", workspace_id="ws-sync", initial_state={"env": "dev"})
        assert sess["status"] == "PAUSED"
        mutated = client.platform.step_debug_session(sess["session_id"], "mutate_state", workspace_id="ws-sync", state_patch={"route": "local"})
        assert mutated["mutation_count"] == 1
        with pytest.raises(PolicyViolationError):
            client.platform.step_debug_session(sess["session_id"], "mutate_state", workspace_id="ws-sync", state_patch={"leak": "sk-live-1234567890abcdef"})
        done = client.platform.step_debug_session(sess["session_id"], "continue", workspace_id="ws-sync")
        assert done["status"] == "COMPLETED"
        sessions = client.platform.list_debug_sessions(workspace_id="ws-sync")
        assert sessions["count"] == 1
        lenses = client.platform.get_debugger_codelens(workspace_id="ws-sync")
        assert lenses["bridge"]["extension_id"] == "keelway.vscode-keelway"
        deleted = client.platform.delete_breakpoint(bp["breakpoint_id"], workspace_id="ws-sync")
        assert deleted["deleted"] is True


@pytest.mark.asyncio
async def test_async_python_sdk_live_asgi_debugger_roundtrip_rbac_and_dlp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_file = tmp_path / "phase14_asgi.db"
    monkeypatch.setenv("KEELWAY_PLATFORM_DB_PATH", str(db_file))
    ws_id = f"ws-p14-{uuid.uuid4().hex[:8]}"
    token = launch_token()

    async with AsyncKeelwayClient(
        base_url="http://127.0.0.1:7420",
        token=token,
        transport=ASGITransport(app=app),
    ) as client:
        bp = await client.platform.set_breakpoint(
            workspace_id=ws_id,
            workflow_id="WF-STUDIO-01",
            condition_type="cost_usd_gt",
            threshold=0.25,
            label="Spend guard",
        )
        assert bp["condition_type"] == "cost_usd_gt"

        bp_list = await client.platform.list_breakpoints(workspace_id=ws_id, workflow_id="WF-STUDIO-01")
        assert bp_list["count"] == 1

        sess = await client.platform.start_debug_session("WF-STUDIO-01", workspace_id=ws_id, initial_state={"mode": "audit"})
        assert sess["status"] == "PAUSED"
        assert sess["current_step_index"] == 1
        initial_sha = sess["frame_sha256"]
        assert len(initial_sha) == 64

        stepped_in = await client.platform.step_debug_session(sess["session_id"], "step_into", workspace_id=ws_id)
        assert stepped_in["step_depth"] == 1

        patched = await client.platform.step_debug_session(
            sess["session_id"],
            "mutate_state",
            workspace_id=ws_id,
            state_patch={"override_model": "keelway-core:7b"},
        )
        assert patched["mutation_count"] == 1
        assert patched["variables"]["override_model"] == "keelway-core:7b"
        assert patched["frame_sha256"] != initial_sha

        with pytest.raises(PolicyViolationError):
            await client.platform.step_debug_session(
                sess["session_id"],
                "mutate_state",
                workspace_id=ws_id,
                state_patch={"api_key": "sk-live-secret1234567890abcdef"},
            )

        completed = await client.platform.step_debug_session(sess["session_id"], "continue", workspace_id=ws_id)
        assert completed["status"] == "COMPLETED"

        codelens = await client.platform.get_debugger_codelens(workspace_id=ws_id, workflow_id="WF-STUDIO-01")
        assert codelens["bridge"]["cursor_attach_uri"].startswith("cursor://keelway.vscode-keelway/attach")
        assert len(codelens["lenses"]) >= 3

        rm_res = await client.platform.delete_breakpoint(bp["breakpoint_id"], workspace_id=ws_id)
        assert rm_res["deleted"] is True

    async with AsyncKeelwayClient(
        base_url="http://127.0.0.1:7420",
        token=token,
        transport=ASGITransport(app=app),
    ) as viewer_client:
        http_attr = getattr(viewer_client, "_http", None) or viewer_client._client
        http_attr.headers["X-Keelway-Role"] = "viewer"
        http_attr.headers["X-Keelway-Actor"] = "viewer-actor"
        with pytest.raises(PermissionDeniedError):
            await viewer_client.platform.set_breakpoint(workspace_id=ws_id, condition_type="always")


def test_vscode_cursor_extension_tri_sdk_and_website_280_route_parity() -> None:
    # 1. Official VS Code & Cursor Extension structure, CSP, zero-Origin & hygiene
    pkg = json.loads((EXT_DIR / "package.json").read_text(encoding="utf-8"))
    assert pkg["name"] == "vscode-keelway"
    assert pkg["publisher"] == "keelway"
    assert pkg["version"] == "1.1.0"
    assert "dependencies" not in pkg
    cmd_ids = {c["command"] for c in pkg["contributes"]["commands"]}
    for expected_cmd in (
        "keelway.attachBridge",
        "keelway.toggleConditionalBreakpoint",
        "keelway.stepOverNode",
        "keelway.stepIntoAgent",
        "keelway.continueExecution",
        "keelway.openStudioPanel",
    ):
        assert expected_cmd in cmd_ids

    bridge_src = (EXT_DIR / "src" / "bridgeClient.ts").read_text(encoding="utf-8")
    webview_src = (EXT_DIR / "src" / "studioWebview.ts").read_text(encoding="utf-8")
    assert "delete headers.Origin" in bridge_src
    assert "default-src 'none'" in webview_src
    assert "acquireVsCodeApi" in webview_src
    assert "fetch(" not in webview_src.split("<script")[1], "Studio Webview script must never issue direct browser fetch()"

    for ext_file in EXT_DIR.rglob("*"):
        # Skip vendored toolchains (KEEL-WEB-054 added per-package node_modules)
        # and compiled output — the cap + token scan binds to authored sources.
        if "node_modules" in ext_file.parts or "dist" in ext_file.parts:
            continue
        if ext_file.is_file() and ext_file.suffix in {".ts", ".mjs", ".json", ".md"}:
            txt = ext_file.read_text(encoding="utf-8")
            assert len(txt.splitlines()) < 480, f"{ext_file} exceeds 480-line cap"
            for tok in FORBIDDEN_PRIVATE_TOKENS:
                assert tok not in txt, f"Private token '{tok}' leaked in {ext_file}"

    # 2. TypeScript & Go SDK Phase 14 method parity
    ts_src = (REPO_ROOT / "sdk" / "typescript" / "src" / "platformDebugger.ts").read_text(encoding="utf-8")
    go_src = (REPO_ROOT / "sdk" / "go" / "platform_phase14.go").read_text(encoding="utf-8")
    for ts_m in PHASE14_TS_METHODS:
        assert ts_m in ts_src, f"Missing TypeScript SDK method {ts_m}"
    for go_m in PHASE14_GO_METHODS:
        assert f"func (p *PlatformService) {go_m}(" in go_src, f"Missing Go SDK method {go_m}"

    # 3. Website OpenAPI (280 paths) & Product-Facts (22 features) zero-drift verification
    openapi_raw = (SITE_DIR / "openapi.json").read_text(encoding="utf-8")
    pub_openapi_raw = (SITE_DIR / "public" / "openapi.json").read_text(encoding="utf-8")
    assert openapi_raw == pub_openapi_raw
    openapi_doc = json.loads(openapi_raw)
    assert len(openapi_doc["paths"]) >= 280
    assert len(app.openapi()["paths"]) >= 280
    for route in (
        "/v1/platform/debugger/breakpoints",
        "/v1/platform/debugger/breakpoints/{breakpoint_id}",
        "/v1/platform/debugger/sessions",
        "/v1/platform/debugger/sessions/{session_id}",
        "/v1/platform/debugger/sessions/{session_id}/step",
        "/v1/platform/debugger/codelens",
        "/v1/platform/debugger/codelens/inspect",
    ):
        assert route in openapi_doc["paths"], f"Missing OpenAPI route {route}"

    facts_raw = (SITE_DIR / "product-facts.json").read_text(encoding="utf-8")
    pub_facts_raw = (SITE_DIR / "public" / "product-facts.json").read_text(encoding="utf-8")
    assert facts_raw == pub_facts_raw
    for tok in FORBIDDEN_PRIVATE_TOKENS:
        assert tok not in facts_raw, f"Private token '{tok}' leaked in product-facts.json"
    facts = json.loads(facts_raw)
    assert len(facts["features"]) >= 22
    dbg_feat = facts["features"]["step_through_debugger_and_ide_extension_bridge"]
    assert dbg_feat["status"] == "AVAILABLE"
    assert "extensions/vscode-keelway/src/extension.ts" in dbg_feat["code_path"]
