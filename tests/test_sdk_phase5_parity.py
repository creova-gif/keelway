"""
Keelway Python SDK — Phase 4 & Phase 5 Platform Runtime Parity Verification Suite.

Verifies 100% synchronous (`KeelwayClient.platform`) and asynchronous (`AsyncKeelwayClient.platform`)
parity across Phase 4 Workspace endpoints and Phase 5 Multi-Workspace, 5-Role RBAC, AES-256-GCM
Vault, HMAC-SHA256 Webhooks, and chunk-boundary-safe SSE Live Execution streaming.
"""

from __future__ import annotations

import inspect
import json
from typing import Any, AsyncIterator, Dict, Iterator, List, Tuple

import httpx
import pytest

from core.sdk import (
    AsyncKeelwayClient,
    AsyncPlatformClient,
    KeelwayClient,
    KeelwayError,
    PermissionDeniedError,
    SyncPlatformClient,
    TaskNotFoundError,
)


class _ChunkedSyncStream(httpx.SyncByteStream):
    def __init__(self, chunks: List[bytes]) -> None:
        self._chunks = chunks

    def __iter__(self) -> Iterator[bytes]:
        yield from self._chunks


class _ChunkedAsyncStream(httpx.AsyncByteStream):
    def __init__(self, chunks: List[bytes]) -> None:
        self._chunks = chunks

    async def __aiter__(self) -> AsyncIterator[bytes]:
        for chunk in self._chunks:
            yield chunk


def _build_split_sse_chunks(run_id: str) -> List[bytes]:
    bullet = "·".encode("utf-8")  # 2-byte UTF-8 sequence split across chunks
    return [
        b": heartbeat\r\n\r\nda",
        f'ta: {{"run_id":"{run_id}","seq":1,"event":"run.started","detail":"Dispatch '.encode("utf-8") + bullet[:1],
        bullet[1:] + b' initialized"}\r',
        b"\n\r\n",
        f'data: {{"run_id":"{run_id}","seq":2,"event":"p10.held","status":"awaiting_p10_approval"}}\n\n'.encode("utf-8"),
        f'data: {{"run_id":"{run_id}","seq":3,"event":"run.completed","status":"completed"}}\n'.encode("utf-8"),
        b"\ndata: [DO",
        b"NE]\n\ndata: {\"seq\":99,\"event\":\"must_not_yield\"}\n\n",
    ]


def _make_phase5_mock_transport(*, async_mode: bool = False) -> Tuple[httpx.BaseTransport | httpx.AsyncBaseTransport, List[Dict[str, Any]]]:
    recorded: List[Dict[str, Any]] = []

    def _dispatch(request: httpx.Request) -> httpx.Response:
        raw = request.content.decode("utf-8") if request.content else ""
        body = json.loads(raw) if raw else None
        path = request.url.path
        method = request.method
        params = dict(request.url.params)
        recorded.append({"method": method, "path": path, "params": params, "json": body})

        # --- Phase 4 Workspace Endpoints ---
        if method == "GET" and path == "/v1/platform/docs":
            docs = [
                {"id": "DOC-01", "title": "Vault Guide", "diataxis_kind": "how_to"},
                {"id": "DOC-02", "title": "API Spec", "diataxis_kind": "reference"},
            ]
            return httpx.Response(200, json={"workspace_id": params.get("workspace_id", "default"), "count": 2, "docs": docs})
        if method == "POST" and path == "/v1/platform/docs":
            return httpx.Response(201, json={"id": "DOC-03", **body})
        if method == "PUT" and path.startswith("/v1/platform/docs/"):
            doc_id = path.rsplit("/", 1)[-1]
            return httpx.Response(200, json={"id": doc_id, **body})
        if method == "PATCH" and path.startswith("/v1/platform/pm/issues/"):
            issue_id = path.rsplit("/", 1)[-1]
            return httpx.Response(200, json={"id": issue_id, **body})
        if method == "GET" and path == "/v1/platform/product/feedback":
            return httpx.Response(200, json={"workspace_id": params["workspace_id"], "feedback": [{"id": "FB-01"}], "total": 1})
        if method == "POST" and path == "/v1/platform/product/feedback":
            return httpx.Response(201, json={"id": "FB-02", **body})
        if method == "POST" and path == "/v1/platform/security/scan":
            has_secret = "sk-live-" in body["snippet"]
            return httpx.Response(
                200,
                json={
                    "workspace_id": body["workspace_id"],
                    "target_path": body["target_path"],
                    "passed": not has_secret,
                    "risk_grade": "BLOCKED" if has_secret else "A",
                    "findings_count": 1 if has_secret else 0,
                },
            )

        # --- Phase 5 Multi-Workspace & RBAC ---
        if method == "GET" and path == "/v1/platform/workspaces":
            return httpx.Response(200, json={"workspaces": [{"id": "default"}, {"id": "hipaa-intake"}], "total": 2})
        if method == "POST" and path == "/v1/platform/workspaces":
            return httpx.Response(201, json={**body, "status": "active"})
        if method == "GET" and path == "/v1/platform/rbac/members":
            return httpx.Response(
                200,
                json={
                    "workspace_id": params["workspace_id"],
                    "members": [{"actor_id": "op-1", "role": "owner"}],
                    "roles": ["owner", "admin", "builder", "operator", "viewer"],
                },
            )
        if method == "POST" and path == "/v1/platform/rbac/members":
            return httpx.Response(200, json={**body, "updated": True})
        if method == "POST" and path == "/v1/platform/rbac/check":
            role = body.get("role") or ("viewer" if body["actor_id"] == "guest" else "owner")
            allowed = role in {"owner", "admin"} or body["permission"] == "workspace:read"
            return httpx.Response(
                200,
                json={"allowed": allowed, "role": role, "permission": body["permission"], "reason": "ok" if allowed else "denied"},
            )

        # --- Phase 5 Vault & Webhooks ---
        if method == "GET" and path == "/v1/platform/vault/secrets":
            return httpx.Response(
                200,
                json={
                    "workspace_id": params["workspace_id"],
                    "secrets": [{"name": "OPENAI_API_KEY", "namespace": "byom", "masked_preview": "sk-l****2345", "version": 1}],
                },
            )
        if method == "POST" and path == "/v1/platform/vault/secrets":
            val = body["secret_value"]
            masked = f"{val[:4]}****{val[-4:]}" if len(val) >= 8 else "****"
            return httpx.Response(
                201,
                json={
                    "name": body["name"],
                    "namespace": body["namespace"],
                    "workspace_id": body["workspace_id"],
                    "masked_preview": masked,
                    "fingerprint_sha256": "deadbeef" * 8,
                    "version": 1,
                },
            )
        if method == "POST" and path.startswith("/v1/platform/vault/secrets/") and path.endswith("/rotate"):
            secret_name = path.split("/")[5]
            return httpx.Response(
                200,
                json={"name": secret_name, "workspace_id": body["workspace_id"], "masked_preview": "sk-r****9999", "version": 2},
            )
        if method == "DELETE" and path.startswith("/v1/platform/vault/secrets/"):
            secret_name = path.rsplit("/", 1)[-1]
            return httpx.Response(200, json={"name": secret_name, "workspace_id": params["workspace_id"], "deleted": True})

        if method == "GET" and path == "/v1/platform/webhooks":
            return httpx.Response(200, json={"workspace_id": params["workspace_id"], "webhooks": [{"id": "WH-01"}], "deliveries": []})
        if method == "POST" and path == "/v1/platform/webhooks":
            if "169.254.169.254" in body["url"]:
                return httpx.Response(400, json={"detail": "SSRF target blocked: 169.254.169.254"})
            return httpx.Response(201, json={"id": "WH-02", "url": body["url"], "events": body["events"], "workspace_id": body["workspace_id"]})
        if method == "DELETE" and path.startswith("/v1/platform/webhooks/"):
            wh_id = path.rsplit("/", 1)[-1]
            return httpx.Response(200, json={"id": wh_id, "workspace_id": params["workspace_id"], "deleted": True})
        if method == "POST" and path.startswith("/v1/platform/webhooks/") and path.endswith("/test"):
            wh_id = path.split("/")[4]
            return httpx.Response(
                200,
                json={
                    "webhook_id": wh_id,
                    "event_type": body["event_type"],
                    "signature": "sha256=abcdef123456",
                    "delivered": True,
                },
            )
        if method == "POST" and path == "/v1/platform/webhooks/verify":
            valid = body["signature"].startswith("sha256=") and body["tolerance_seconds"] >= 60
            return httpx.Response(200, json={"valid": valid, "timestamp": body["timestamp"]})

        # --- Phase 5 Live Execution & Chunked SSE ---
        if method == "POST" and path == "/v1/platform/execution/runs":
            return httpx.Response(
                201,
                json={
                    "run_id": "EXRUN-01",
                    "kind": body["kind"],
                    "target_id": body["target_id"],
                    "objective": body["objective"],
                    "requires_p10": body["requires_p10"],
                    "stream": body["stream"],
                    "status": "awaiting_p10_approval" if body["requires_p10"] else "completed",
                },
            )
        if method == "GET" and path.startswith("/v1/platform/execution/runs/") and path.endswith("/events"):
            run_id = path.split("/")[5]
            if run_id == "MISSING":
                return httpx.Response(404, json={"detail": "Execution run MISSING not found"})
            if run_id == "FORBIDDEN":
                return httpx.Response(403, json={"detail": "RBAC viewer cannot stream privileged run"})
            chunks = _build_split_sse_chunks(run_id)
            stream_obj = _ChunkedAsyncStream(chunks) if async_mode else _ChunkedSyncStream(chunks)
            return httpx.Response(200, headers={"Content-Type": "text/event-stream"}, stream=stream_obj)
        if method == "POST" and path.startswith("/v1/platform/execution/runs/") and path.endswith("/p10"):
            run_id = path.split("/")[5]
            return httpx.Response(
                200,
                json={
                    "run_id": run_id,
                    "decision": body["decision"],
                    "approver": body["approver"],
                    "status": "completed" if body["decision"] == "approve" else "aborted",
                },
            )

        return httpx.Response(404, json={"detail": f"Unhandled {method} {path}"})

    if async_mode:
        class _AsyncRouter(httpx.AsyncBaseTransport):
            async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
                await request.aread()
                return _dispatch(request)

        return _AsyncRouter(), recorded

    return httpx.MockTransport(_dispatch), recorded


def test_sync_and_async_signature_parity():
    expected_new_methods = {
        "list_docs", "create_doc", "update_doc", "update_issue",
        "list_feedback", "create_feedback", "scan_workspace_security",
        "list_workspaces", "create_workspace", "list_rbac_members",
        "upsert_rbac_member", "check_rbac", "list_secrets", "put_secret",
        "rotate_secret", "delete_secret", "list_webhooks", "create_webhook",
        "delete_webhook", "test_webhook", "verify_webhook",
        "start_execution_run", "stream_execution_events", "resolve_execution_p10",
    }
    sync_methods = {
        name: inspect.signature(fn)
        for name, fn in inspect.getmembers(SyncPlatformClient, predicate=inspect.isfunction)
        if not name.startswith("_")
    }
    async_methods = {
        name: inspect.signature(fn)
        for name, fn in inspect.getmembers(AsyncPlatformClient, predicate=inspect.isfunction)
        if not name.startswith("_")
    }
    assert expected_new_methods.issubset(sync_methods.keys())
    assert set(sync_methods.keys()) == set(async_methods.keys())
    for name, sync_sig in sync_methods.items():
        async_sig = async_methods[name]
        assert list(sync_sig.parameters.values()) == list(async_sig.parameters.values()), f"Mismatch on {name}"


def test_sync_phase4_and_phase5_full_parity():
    transport, recorded = _make_phase5_mock_transport(async_mode=False)
    with KeelwayClient(token="kw_live_sync", transport=transport) as client:
        # Phase 4 Docs, Issues, Feedback, Security Scan
        ref_docs = client.platform.list_docs("ws-1", diataxis_kind="reference")
        assert ref_docs["count"] == 1 and ref_docs["docs"][0]["id"] == "DOC-02"
        doc = client.platform.create_doc("Runbook", diataxis_kind="how_to", summary="Ops", body="# Steps", linked_prd_id="PRD-01", workspace_id="ws-1")
        assert doc["id"] == "DOC-03"
        updated_doc = client.platform.update_doc("DOC-03", "Runbook v2", diataxis_kind="how_to", workspace_id="ws-1")
        assert updated_doc["title"] == "Runbook v2"

        patched_issue = client.platform.update_issue("KEEL-101", workspace_id="ws-1", status="done", priority="high")
        assert patched_issue["status"] == "done" and patched_issue["priority"] == "high"

        assert client.platform.list_feedback("ws-1")["total"] == 1
        fb = client.platform.create_feedback("SecOps Lead", "Need vault rotation", impact_score=9.2, linked_prd_id="PRD-09", workspace_id="ws-1")
        assert fb["id"] == "FB-02" and fb["impact_score"] == 9.2

        scan = client.platform.scan_workspace_security("api_key = 'sk-live-secret-12345'", target_path="config.py", write_paths=["config.py"], workspace_id="ws-1")
        assert scan["passed"] is False and scan["risk_grade"] == "BLOCKED"

        # Phase 5 Workspaces & RBAC
        assert client.platform.list_workspaces()["total"] == 2
        ws = client.platform.create_workspace("hipaa-vault", "HIPAA Vault", branch="release", isolation_mode="seatbelt_local")
        assert ws["id"] == "hipaa-vault" and ws["status"] == "active"

        members = client.platform.list_rbac_members("hipaa-vault")
        assert "viewer" in members["roles"]
        assert client.platform.upsert_rbac_member("alice", "admin", workspace_id="hipaa-vault")["updated"] is True
        denied = client.platform.check_rbac("guest", "secrets:write", role="viewer", workspace_id="hipaa-vault")
        assert denied["allowed"] is False
        allowed = client.platform.check_rbac("alice", "secrets:write", role="admin", workspace_id="hipaa-vault")
        assert allowed["allowed"] is True

        # Phase 5 Vault & Webhooks
        put_res = client.platform.put_secret("OPENAI_API_KEY", "sk-live-secret-12345", namespace="byom", workspace_id="hipaa-vault")
        assert put_res["masked_preview"] == "sk-l****2345"
        assert "sk-live-secret-12345" not in json.dumps(put_res)
        assert len(client.platform.list_secrets("hipaa-vault")["secrets"]) == 1
        rot = client.platform.rotate_secret("OPENAI_API_KEY", "sk-rotated-99999", workspace_id="hipaa-vault")
        assert rot["version"] == 2
        assert client.platform.delete_secret("OPENAI_API_KEY", workspace_id="hipaa-vault")["deleted"] is True

        assert len(client.platform.list_webhooks("hipaa-vault")["webhooks"]) == 1
        with pytest.raises(KeelwayError):
            client.platform.create_webhook("http://169.254.169.254/latest/meta-data", ["agent.run.completed"])
        wh = client.platform.create_webhook("https://hooks.example.internal/keelway", ["agent.run.completed"], description="Audit sink", workspace_id="hipaa-vault")
        assert wh["id"] == "WH-02"
        ping = client.platform.test_webhook("WH-02", payload={"ok": True}, workspace_id="hipaa-vault")
        assert ping["delivered"] is True and ping["signature"].startswith("sha256=")
        ver = client.platform.verify_webhook({"ok": True}, ping["signature"], "whsec_test", timestamp=1794686400)
        assert ver["valid"] is True
        assert client.platform.delete_webhook("WH-02", workspace_id="hipaa-vault")["deleted"] is True

        # Phase 5 Live Execution & Chunked SSE Stream
        run = client.platform.start_execution_run("agent", "feature-coder", "Ship encrypted vault", requires_p10=True, workspace_id="hipaa-vault")
        assert run["run_id"] == "EXRUN-01" and run["stream"] is False
        assert recorded[-1]["json"]["stream"] is False

        events = list(client.platform.stream_execution_events("EXRUN-01"))
        assert [e["event"] for e in events] == ["run.started", "p10.held", "run.completed"]
        assert "·" in events[0]["detail"]

        with pytest.raises(TaskNotFoundError):
            list(client.platform.stream_execution_events("MISSING"))

        res_p10 = client.platform.resolve_execution_p10("EXRUN-01", "approve", approver="sec-lead", reason="Verified diff")
        assert res_p10["status"] == "completed"


@pytest.mark.asyncio
async def test_async_phase4_and_phase5_full_parity():
    transport, _ = _make_phase5_mock_transport(async_mode=True)
    async with AsyncKeelwayClient(token="kw_live_async", transport=transport) as client:
        assert (await client.platform.list_docs("ws-2", diataxis_kind="how_to"))["count"] == 1
        doc = await client.platform.create_doc("Async Architecture", workspace_id="ws-2")
        assert (await client.platform.update_doc(doc["id"], "Async Arch v2", workspace_id="ws-2"))["title"] == "Async Arch v2"
        assert (await client.platform.update_issue("KEEL-202", workspace_id="ws-2", status="in_progress"))["status"] == "in_progress"
        assert (await client.platform.list_feedback("ws-2"))["total"] == 1
        assert (await client.platform.create_feedback("PM", "Great DX", workspace_id="ws-2"))["id"] == "FB-02"
        assert (await client.platform.scan_workspace_security("clean = True", workspace_id="ws-2"))["passed"] is True

        assert (await client.platform.list_workspaces())["total"] == 2
        assert (await client.platform.create_workspace("ws-2", "Workspace 2"))["id"] == "ws-2"
        assert len((await client.platform.list_rbac_members("ws-2"))["members"]) == 1
        assert (await client.platform.upsert_rbac_member("bob", "operator", workspace_id="ws-2"))["updated"] is True
        assert (await client.platform.check_rbac("guest", "p10:approve", role="viewer", workspace_id="ws-2"))["allowed"] is False

        secret = await client.platform.put_secret("ANTHROPIC_KEY", "sk-ant-secret-9876", workspace_id="ws-2")
        assert secret["masked_preview"] == "sk-a****9876"
        assert len((await client.platform.list_secrets("ws-2"))["secrets"]) == 1
        assert (await client.platform.rotate_secret("ANTHROPIC_KEY", "sk-ant-new-9999", workspace_id="ws-2"))["version"] == 2
        assert (await client.platform.delete_secret("ANTHROPIC_KEY", workspace_id="ws-2"))["deleted"] is True

        wh = await client.platform.create_webhook("https://hooks.example.internal/events", ["p10.resolved"], secret="whsec_1", workspace_id="ws-2")
        assert len((await client.platform.list_webhooks("ws-2"))["webhooks"]) == 1
        ping = await client.platform.test_webhook(wh["id"], event_type="p10.resolved", workspace_id="ws-2")
        assert (await client.platform.verify_webhook({"id": 1}, ping["signature"], "whsec_1", timestamp=1794686400))["valid"] is True
        assert (await client.platform.delete_webhook(wh["id"], workspace_id="ws-2"))["deleted"] is True

        run = await client.platform.start_execution_run("workflow", "WF-101", "Nightly compliance gate", requires_p10=True, workspace_id="ws-2")
        streamed = [ev async for ev in client.platform.stream_execution_events(run["run_id"])]
        assert [e["event"] for e in streamed] == ["run.started", "p10.held", "run.completed"]

        with pytest.raises(PermissionDeniedError):
            _ = [ev async for ev in client.platform.stream_execution_events("FORBIDDEN")]

        resolved = await client.platform.resolve_execution_p10(run["run_id"], "deny", reason="Hold release")
        assert resolved["status"] == "aborted"


@pytest.mark.asyncio
async def test_live_asgi_phase4_workspace_endpoints_roundtrip():
    from fastapi import FastAPI
    from httpx import ASGITransport

    from core.api.platform_routes import get_platform_hub, router as platform_router
    from core.platform.workspace_hub import UnifiedWorkspaceHub
    from core.security.auth import launch_token

    hub = UnifiedWorkspaceHub()
    app = FastAPI()
    app.include_router(platform_router)
    app.dependency_overrides[get_platform_hub] = lambda: hub

    async with AsyncKeelwayClient(
        base_url="http://testserver",
        token=launch_token(),
        transport=ASGITransport(app=app),
    ) as client:
        created_doc = await client.platform.create_doc(
            "Phase 5 Vault Spec",
            diataxis_kind="explanation",
            summary="AES-256-GCM design",
            body="Ciphertext stored with 12-byte random nonce.",
            workspace_id="ws-phase4-live",
        )
        updated_doc = await client.platform.update_doc(
            created_doc["id"],
            "Phase 5 Vault Architecture",
            diataxis_kind="explanation",
            summary="Updated summary",
            body="Updated body.",
            workspace_id="ws-phase4-live",
        )
        assert updated_doc["title"] == "Phase 5 Vault Architecture"
        docs = await client.platform.list_docs("ws-phase4-live", diataxis_kind="explanation")
        assert any(d["id"] == created_doc["id"] for d in docs["docs"])

        issue = await client.platform.create_issue("Wire RBAC guard", workspace_id="ws-phase4-live")
        patched = await client.platform.update_issue(issue["id"], workspace_id="ws-phase4-live", status="done")
        assert patched["status"] == "done"

        fb = await client.platform.create_feedback("Enterprise CISO", "Signed webhooks required", impact_score=9.5, workspace_id="ws-phase4-live")
        assert fb["persona"] == "Enterprise CISO"
        assert (await client.platform.list_feedback("ws-phase4-live"))["total"] >= 1

        scan = await client.platform.scan_workspace_security("TOKEN='sk-live-abcdef1234567890'", target_path="env.py", workspace_id="ws-phase4-live")
        assert scan["passed"] is False
        assert scan["risk_grade"] == "BLOCKED"


@pytest.mark.asyncio
async def test_live_asgi_phase5_vault_rbac_webhooks_and_sse_roundtrip(tmp_path):
    from httpx import ASGITransport

    from core.api.platform_runtime_routes import (
        get_execution_streamer,
        get_rbac_controller,
        get_secret_vault,
        get_webhook_bus,
    )
    from core.main import app
    from core.platform.execution_stream import LiveExecutionStreamer
    from core.platform.rbac_webhooks import SignedWebhookBus, WorkspaceRbacController
    from core.platform.vault import LocalSecretVault
    from core.security.auth import launch_token

    vault = LocalSecretVault(db_path=tmp_path / "vault.db", master_key="live-e2e-master-secret")
    rbac = WorkspaceRbacController(db_path=tmp_path / "rbac.db")
    bus = SignedWebhookBus(db_path=tmp_path / "webhooks.db")
    streamer = LiveExecutionStreamer(db_path=tmp_path / "exec.db", webhook_bus=bus)

    app.dependency_overrides[get_secret_vault] = lambda: vault
    app.dependency_overrides[get_rbac_controller] = lambda: rbac
    app.dependency_overrides[get_webhook_bus] = lambda: bus
    app.dependency_overrides[get_execution_streamer] = lambda: streamer

    try:
        async with AsyncKeelwayClient(
            base_url="http://localhost",
            token=launch_token(),
            transport=ASGITransport(app=app),
        ) as client:
            created_ws = await client.platform.create_workspace(
                "finops-live",
                "FinOps Live Sandbox",
                branch="feat/phase5",
                isolation_mode="sqlite_wal_local",
            )
            assert created_ws["id"] == "finops-live"
            ws_list = await client.platform.list_workspaces()
            assert any(w["id"] == "finops-live" for w in ws_list["workspaces"])

            member = await client.platform.upsert_rbac_member("alice@keelway.dev", "operator", workspace_id="finops-live")
            assert member["role"] == "operator"
            verdict = await client.platform.check_rbac("alice@keelway.dev", "p10:approve", workspace_id="finops-live")
            assert verdict["allowed"] is True

            stored = await client.platform.put_secret(
                "ANTHROPIC_LIVE_KEY",
                "sk-ant-live-secret-99887766",
                workspace_id="finops-live",
                namespace="plugins",
            )
            assert "secret_value" not in stored
            assert "****" in stored["masked_preview"]

            rotated = await client.platform.rotate_secret(
                "ANTHROPIC_LIVE_KEY",
                "sk-ant-live-secret-rotated-1122",
                workspace_id="finops-live",
            )
            assert rotated["version"] == 2
            assert (await client.platform.delete_secret("ANTHROPIC_LIVE_KEY", workspace_id="finops-live"))["deleted"] is True

            wh = await client.platform.create_webhook(
                "https://hooks.example.org/keelway",
                events=["*"],
                workspace_id="finops-live",
                secret="whsec_live_e2e_secret",
            )
            ping = await client.platform.test_webhook(wh["id"], workspace_id="finops-live")
            assert ping["signature"].startswith("sha256=")
            verified = await client.platform.verify_webhook(
                ping["payload"],
                ping["signature"],
                "whsec_live_e2e_secret",
                timestamp=int(ping["timestamp"]),
            )
            assert verified["valid"] is True

            run = await client.platform.start_execution_run(
                "agent",
                "AG-CODE",
                "Generate signed migration plan",
                requires_p10=True,
                workspace_id="finops-live",
            )
            assert run["status"] == "awaiting_p10_approval"
            initial_events = [ev async for ev in client.platform.stream_execution_events(run["run_id"])]
            assert any(ev.get("type") == "p10.held" for ev in initial_events)

            approved = await client.platform.resolve_execution_p10(
                run["run_id"],
                "approve",
                approver="alice@keelway.dev",
                reason="Human operator verified diff",
            )
            assert approved["status"] == "completed"
    finally:
        app.dependency_overrides.pop(get_secret_vault, None)
        app.dependency_overrides.pop(get_rbac_controller, None)
        app.dependency_overrides.pop(get_webhook_bus, None)
        app.dependency_overrides.pop(get_execution_streamer, None)
        streamer.close()
        bus.close()
        rbac.close()
        vault.close()
