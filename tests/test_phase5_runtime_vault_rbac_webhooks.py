"""
Phase 5 Verification Suite — Encrypted Secret Vault (`AES-256-GCM`), Multi-Workspace 5-Role RBAC,
`HMAC-SHA256` Signed Webhooks with SSRF Defense, Live SSE Execution Streamer & FastAPI Routes.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
import stat
import time
from typing import Any, Dict, List

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
import pytest

from core.api.platform_runtime_routes import (
    get_execution_streamer,
    get_rbac_controller,
    get_secret_vault,
    get_webhook_bus,
    router as platform_runtime_router,
)
from core.platform.execution_stream import LiveExecutionStreamer
from core.platform.rbac_webhooks import (
    SignedWebhookBus,
    WebhookValidationError,
    WorkspaceRbacController,
)
from core.platform.vault import LocalSecretVault, VaultTamperError, _StdlibAESGCM
from core.security.auth import launch_token


# ---------------------------------------------------------------------------
# 1. LocalSecretVault (AES-256-GCM + HKDF-SHA256 + Tamper Detection)
# ---------------------------------------------------------------------------


def test_nist_sp800_38d_aes256gcm_official_vector() -> None:
    # NIST SP 800-38D Test Case 15: 256-bit key, 96-bit IV, 64-byte plaintext, empty AAD
    key = bytes.fromhex("feffe9928665731c6d6a8f9467308308feffe9928665731c6d6a8f9467308308")
    nonce = bytes.fromhex("cafebabefacedbaddecaf888")
    pt = bytes.fromhex(
        "d9313225f88406e5a55909c5aff5269a86a7a9531534f7da2e4c303d8a318a72"
        "1c3c0c95956809532fcf0e2449a6b525b16aedf5aa0de657ba637b391aafd255"
    )
    expected_ct = bytes.fromhex(
        "522dc1f099567d07f47f37a32a84427d643a8cdcbfe5c0c97598a2bd2555d1aa"
        "8cb08e48590dbb3da7b08b1056828838c5f61e6393ba7a0abcc9f662898015ad"
    )
    expected_tag = bytes.fromhex("b094dac5d93471bdec1a502270e3cc6c")
    cipher = _StdlibAESGCM(key)
    sealed = cipher.encrypt(nonce, pt, b"")
    assert sealed == expected_ct + expected_tag
    assert cipher.decrypt(nonce, sealed, b"") == pt


def test_vault_aes256gcm_encryption_masking_rotation_and_keyfile(tmp_path: Path) -> None:
    db_file = tmp_path / "vault.db"
    key_file = tmp_path / "vault_master.key"

    vault = LocalSecretVault(db_path=db_file, key_file_path=key_file)
    assert vault.journal_mode == "wal"
    assert key_file.exists()
    assert stat.S_IMODE(os.stat(key_file).st_mode) == 0o600

    raw_secret = "sk-live-secret-12345"
    put_res = vault.put_secret("default", "OPENAI_API_KEY", raw_secret, namespace="byom")
    assert put_res["workspace_id"] == "default"
    assert put_res["name"] == "OPENAI_API_KEY"
    assert put_res["namespace"] == "byom"
    assert put_res["masked_preview"] == "sk-l****2345"
    assert put_res["version"] == 1
    assert len(put_res["fingerprint_sha256"]) == 64
    for forbidden in ("secret_value", "nonce", "ciphertext"):
        assert forbidden not in put_res
    assert raw_secret not in json.dumps(put_res)

    # Short secrets mask completely to ****
    short_meta = vault.put_secret("default", "SHORT_PIN", "abcd1234", namespace="env")
    assert short_meta["masked_preview"] == "****"

    # Inspect raw SQLite storage: no plaintext stored anywhere
    conn = sqlite3.connect(str(db_file))
    row = conn.execute(
        "SELECT nonce, ciphertext, masked_preview FROM platform_secrets WHERE workspace_id=? AND name=?",
        ("default", "OPENAI_API_KEY"),
    ).fetchone()
    conn.close()
    assert row is not None
    nonce_bytes, ciphertext_bytes, stored_mask = bytes(row[0]), bytes(row[1]), str(row[2])
    assert len(nonce_bytes) == 12
    assert raw_secret.encode("utf-8") not in ciphertext_bytes
    assert stored_mask == "sk-l****2345"

    # List secrets never leaks plaintext, nonce, or ciphertext
    listed = vault.list_secrets("default")
    assert len(listed) == 2
    for item in listed:
        for forbidden in ("secret_value", "nonce", "ciphertext"):
            assert forbidden not in item
        assert raw_secret not in json.dumps(item)

    # Re-open vault using persisted 0600 key_file and decrypt for runtime
    vault.close()
    reopened = LocalSecretVault(db_path=db_file, key_file_path=key_file)
    assert reopened.resolve_secret_for_runtime("default", "OPENAI_API_KEY") == raw_secret

    # Rotate secret increments version and re-encrypts
    rotated_secret = "sk-live-rotated-9876"
    rot_meta = reopened.rotate_secret("default", "OPENAI_API_KEY", rotated_secret)
    assert rot_meta["version"] == 2
    assert rot_meta["masked_preview"] == "sk-l****9876"
    for forbidden in ("secret_value", "nonce", "ciphertext"):
        assert forbidden not in rot_meta
    assert reopened.resolve_secret_for_runtime("default", "OPENAI_API_KEY") == rotated_secret

    # Delete secret
    del_res = reopened.delete_secret("default", "SHORT_PIN")
    assert del_res["deleted"] is True
    with pytest.raises(KeyError):
        reopened.resolve_secret_for_runtime("default", "SHORT_PIN")
    reopened.close()


def test_vault_tamper_detection_and_validation(tmp_path: Path) -> None:
    db_file = tmp_path / "tamper.db"
    vault = LocalSecretVault(db_path=db_file, master_key="unit-test-master-secret")

    with pytest.raises(ValueError):
        vault.put_secret("default", "", "sk-valid-123456", namespace="byom")
    with pytest.raises(ValueError):
        vault.put_secret("default", "VALID_NAME", "   ", namespace="byom")
    with pytest.raises(ValueError):
        vault.put_secret("default", "VALID_NAME", "sk-valid-123456", namespace="invalid_ns")

    vault.put_secret("default", "STRIPE_WEBHOOK_KEY", "whsec_abcdef1234567890", namespace="webhook")
    vault.put_secret("default", "PLUGIN_TOKEN", "plg_token_abcdef9999", namespace="plugin")

    # 1) Out-of-band SQLite ciphertext byte flip -> VaultTamperError
    conn = sqlite3.connect(str(db_file))
    ct = bytes(
        conn.execute(
            "SELECT ciphertext FROM platform_secrets WHERE workspace_id='default' AND name='STRIPE_WEBHOOK_KEY'"
        ).fetchone()[0]
    )
    tampered_ct = bytes([ct[0] ^ 0xFF]) + ct[1:]
    conn.execute(
        "UPDATE platform_secrets SET ciphertext=? WHERE workspace_id='default' AND name='STRIPE_WEBHOOK_KEY'",
        (tampered_ct,),
    )
    conn.commit()
    with pytest.raises(VaultTamperError):
        vault.resolve_secret_for_runtime("default", "STRIPE_WEBHOOK_KEY")

    # 2) Out-of-band AAD metadata tamper (changing namespace in SQLite without re-encrypting) -> VaultTamperError
    conn.execute(
        "UPDATE platform_secrets SET namespace='env' WHERE workspace_id='default' AND name='PLUGIN_TOKEN'"
    )
    conn.commit()
    conn.close()
    with pytest.raises(VaultTamperError):
        vault.resolve_secret_for_runtime("default", "PLUGIN_TOKEN")

    vault.close()


# ---------------------------------------------------------------------------
# 2. WorkspaceRbacController & SignedWebhookBus (SSRF + HMAC-SHA256)
# ---------------------------------------------------------------------------


def test_workspace_rbac_seeding_and_5_role_matrix(tmp_path: Path) -> None:
    db_file = tmp_path / "rbac.db"
    rbac = WorkspaceRbacController(db_path=db_file)

    workspaces = rbac.list_workspaces()
    ws_ids = {w["id"] for w in workspaces}
    assert {"default", "hipaa-intake"}.issubset(ws_ids)

    created = rbac.create_workspace(
        workspace_id="eu-regulated",
        name="EU Sovereign Sandbox",
        branch="feat/eu-dora",
        isolation_mode="airgap_strict",
    )
    assert created["id"] == "eu-regulated"
    assert len(rbac.list_workspaces()) == 3

    rbac.upsert_member("eu-regulated", "alice@sorvex.io", "admin")
    rbac.upsert_member("eu-regulated", "bob@sorvex.io", "builder")
    rbac.upsert_member("eu-regulated", "ops@sorvex.io", "operator")
    rbac.upsert_member("eu-regulated", "audit@sorvex.io", "viewer")

    members = rbac.list_members("eu-regulated")
    assert any(m["actor_id"] == "alice@sorvex.io" and m["role"] == "admin" for m in members)

    # Owner & Admin permitted for secrets:write, webhooks:manage, p10:approve
    assert rbac.check_permission("eu-regulated", "root", "secrets:write", explicit_role="owner")["allowed"] is True
    assert rbac.check_permission("eu-regulated", "alice@sorvex.io", "secrets:write")["allowed"] is True
    assert rbac.check_permission("eu-regulated", "alice@sorvex.io", "webhooks:manage")["allowed"] is True
    assert rbac.check_permission("eu-regulated", "alice@sorvex.io", "p10:approve")["allowed"] is True

    # Builder can dispatch agents & run workflows, cannot write secrets or approve P-10
    assert rbac.check_permission("eu-regulated", "bob@sorvex.io", "agents:dispatch")["allowed"] is True
    assert rbac.check_permission("eu-regulated", "bob@sorvex.io", "secrets:write")["allowed"] is False
    assert rbac.check_permission("eu-regulated", "bob@sorvex.io", "p10:approve")["allowed"] is False

    # Operator can approve P-10 & run workflows, cannot write secrets or manage webhooks
    assert rbac.check_permission("eu-regulated", "ops@sorvex.io", "p10:approve")["allowed"] is True
    assert rbac.check_permission("eu-regulated", "ops@sorvex.io", "secrets:write")["allowed"] is False
    assert rbac.check_permission("eu-regulated", "ops@sorvex.io", "webhooks:manage")["allowed"] is False

    # Viewer is strictly read:all only
    assert rbac.check_permission("eu-regulated", "audit@sorvex.io", "read:all")["allowed"] is True
    for denied_perm in ("secrets:write", "webhooks:manage", "p10:approve", "agents:dispatch"):
        assert rbac.check_permission("eu-regulated", "audit@sorvex.io", denied_perm)["allowed"] is False

    rbac.close()


@pytest.mark.parametrize(
    "blocked_url",
    [
        "http://169.254.169.254/latest/meta-data/",
        "https://169.254.169.254/latest/api/token",
        "https://metadata.google.internal/computeMetadata/v1/",
        "http://100.100.100.200/latest/meta-data/",
        "http://0.0.0.0:8000/hook",
        "https://169.254.12.34/internal",
        "file:///etc/passwd",
        "ftp://hooks.example.com/upload",
        "gopher://127.0.0.1:70/_payload",
        "http://hooks.example.com/cleartext-remote",
    ],
)
def test_webhook_ssrf_blocklist(tmp_path: Path, blocked_url: str) -> None:
    bus = SignedWebhookBus(db_path=tmp_path / "wh_ssrf.db")
    with pytest.raises(WebhookValidationError):
        bus.create_webhook("default", url=blocked_url, events=["*"])
    bus.close()


def test_webhook_hmac_signing_and_replay_protection(tmp_path: Path) -> None:
    bus = SignedWebhookBus(db_path=tmp_path / "wh_sign.db")
    wh = bus.create_webhook(
        "default",
        url="https://hooks.sorvex.example/keelway",
        events=["execution.*"],
        description="Production audit sink",
        secret="whsec_super_secret_signing_key",
    )
    assert wh["url"] == "https://hooks.sorvex.example/keelway"
    assert "whsec_super_secret_signing_key" not in json.dumps(bus.list_webhooks("default"))

    receipts = bus.emit_event(
        "default",
        event_type="execution.p10.approved",
        payload={"run_id": "run-abc1234567", "approver": "local-operator"},
    )
    assert len(receipts) == 1
    receipt = receipts[0]
    assert receipt["signature"].startswith("sha256=")
    assert receipt["headers"]["X-Keelway-Signature-256"] == receipt["signature"]
    assert receipt["headers"]["X-Keelway-Timestamp"] == receipt["timestamp"]
    assert receipt["headers"]["X-Keelway-Event-Id"] == receipt["delivery_id"]

    # Authentic verification succeeds
    ok = bus.verify_signature(
        payload=receipt["payload"],
        signature=receipt["signature"],
        secret="whsec_super_secret_signing_key",
        timestamp=receipt["timestamp"],
    )
    assert ok == {"valid": True, "reason": "verified"}

    # Altered payload fails signature check
    tampered_payload = {**receipt["payload"], "tampered": True}
    bad_body = bus.verify_signature(
        payload=tampered_payload,
        signature=receipt["signature"],
        secret="whsec_super_secret_signing_key",
        timestamp=receipt["timestamp"],
    )
    assert bad_body["valid"] is False
    assert bad_body["reason"] == "signature_mismatch"

    # Expired timestamp (>300s old) fails replay window check
    old_ts = str(int(time.time()) - 600)
    expired = bus.verify_signature(
        payload=receipt["payload"],
        signature=receipt["signature"],
        secret="whsec_super_secret_signing_key",
        timestamp=old_ts,
        tolerance_seconds=300,
    )
    assert expired["valid"] is False
    assert expired["reason"] == "timestamp_expired"
    bus.close()


# ---------------------------------------------------------------------------
# 3. LiveExecutionStreamer (P-10 Hold, Approve/Deny & SSE Framing)
# ---------------------------------------------------------------------------


def test_execution_streamer_p10_hold_approve_deny_and_webhooks(tmp_path: Path) -> None:
    bus = SignedWebhookBus(db_path=tmp_path / "exec_wh.db")
    bus.create_webhook("default", url="http://127.0.0.1:9100/events", events=["*"], secret="whsec_local_12345")
    streamer = LiveExecutionStreamer(db_path=tmp_path / "exec.db", webhook_bus=bus)

    # Run requiring P-10 pauses at seq=4
    held_run = streamer.start_run(
        workspace_id="default",
        kind="agent",
        target_id="security-auditor",
        objective="Scan workspace secrets and apply DLP patch",
        requires_p10=True,
    )
    assert held_run["run_id"].startswith("run-")
    assert held_run["status"] == "awaiting_p10_approval"
    assert [e["type"] for e in held_run["events"]] == [
        "run.started",
        "step.tool_call",
        "step.completed",
        "p10.held",
    ]

    sse_frames = list(streamer.iter_sse_lines(held_run["run_id"]))
    assert sse_frames[-1] == "data: [DONE]\n\n"
    parsed_first = json.loads(sse_frames[0].removeprefix("data: ").strip())
    assert parsed_first["type"] == "run.started"

    # Approve P-10 -> completes with p10_receipt_sha256 & emits webhook
    approved = streamer.resolve_p10(held_run["run_id"], decision="approve", approver="sec-lead", reason="Verified")
    assert approved["status"] == "completed"
    assert [e["type"] for e in approved["events"][-2:]] == ["p10.approved", "run.completed"]
    assert len(approved["events"][-1]["p10_receipt_sha256"]) == 64

    # Deny P-10 on a second run -> aborts
    denied_seed = streamer.start_run(
        workspace_id="default",
        kind="workflow",
        target_id="WF-101",
        objective="Deploy production cluster",
        requires_p10=True,
    )
    denied = streamer.resolve_p10(denied_seed["run_id"], decision="deny", approver="sec-lead", reason="Freeze window")
    assert denied["status"] == "aborted_by_p10"
    assert [e["type"] for e in denied["events"][-2:]] == ["p10.denied", "run.aborted"]

    # Non-P10 run completes immediately
    fast_run = streamer.start_run(
        workspace_id="default",
        kind="agent",
        target_id="issue-triager",
        objective="Classify sprint backlog",
        requires_p10=False,
    )
    assert fast_run["status"] == "completed"
    assert fast_run["events"][-1]["type"] == "run.completed"

    deliveries = bus.list_deliveries("default")
    assert len(deliveries) >= 2
    streamer.close()
    bus.close()


# ---------------------------------------------------------------------------
# 4. FastAPI Router End-to-End Integration (`/v1/platform/*` 17 Endpoints)
# ---------------------------------------------------------------------------


def _build_test_app(tmp_path: Path) -> FastAPI:
    vault = LocalSecretVault(db_path=tmp_path / "api_vault.db", master_key="api-test-master-key")
    rbac = WorkspaceRbacController(db_path=tmp_path / "api_rbac.db")
    webhooks = SignedWebhookBus(db_path=tmp_path / "api_webhooks.db")
    streamer = LiveExecutionStreamer(db_path=tmp_path / "api_exec.db", webhook_bus=webhooks)

    app = FastAPI()
    app.include_router(platform_runtime_router)
    app.dependency_overrides[get_secret_vault] = lambda: vault
    app.dependency_overrides[get_rbac_controller] = lambda: rbac
    app.dependency_overrides[get_webhook_bus] = lambda: webhooks
    app.dependency_overrides[get_execution_streamer] = lambda: streamer
    return app


def _parse_chunk_split_sse(raw_sse: str, chunk_size: int = 19) -> List[Dict[str, Any]]:
    """Simulates TCP mid-line chunk splitting and reconstructs SSE JSON events."""
    buffer = ""
    events: List[Dict[str, Any]] = []
    done_seen = False
    for idx in range(0, len(raw_sse), chunk_size):
        buffer += raw_sse[idx : idx + chunk_size]
        while "\n\n" in buffer:
            frame, buffer = buffer.split("\n\n", 1)
            for line in frame.splitlines():
                if line.startswith("data: "):
                    payload = line[6:].strip()
                    if payload == "[DONE]":
                        done_seen = True
                    else:
                        events.append(json.loads(payload))
    assert done_seen is True
    return events


@pytest.mark.asyncio
async def test_fastapi_runtime_routes_vault_rbac_webhooks_and_sse(tmp_path: Path) -> None:
    app = _build_test_app(tmp_path)
    headers = {"Authorization": f"Bearer {launch_token()}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        # 1. Workspaces & RBAC endpoints
        ws_resp = await client.get("/v1/platform/workspaces", headers=headers)
        assert ws_resp.status_code == 200 and ws_resp.json()["total"] >= 2

        new_ws = await client.post("/v1/platform/workspaces", headers=headers, json={"id": "finops-prod", "name": "FinOps Production", "branch": "main", "isolation_mode": "seatbelt_local"})
        assert new_ws.status_code == 201 and new_ws.json()["id"] == "finops-prod"

        mem_upsert = await client.post("/v1/platform/rbac/members", headers=headers, json={"workspace_id": "finops-prod", "actor_id": "viewer-user", "role": "viewer"})
        assert mem_upsert.status_code == 200 and mem_upsert.json()["role"] == "viewer"

        mem_list = await client.get("/v1/platform/rbac/members?workspace_id=finops-prod", headers=headers)
        assert mem_list.status_code == 200 and len(mem_list.json()["roles"]) == 5

        rbac_chk = await client.post("/v1/platform/rbac/check", headers=headers, json={"workspace_id": "finops-prod", "actor_id": "viewer-user", "role": "viewer", "permission": "secrets:write"})
        assert rbac_chk.status_code == 200 and rbac_chk.json()["allowed"] is False

        # 2. Vault lifecycle + HTTP 400 validation + HTTP 403 viewer enforcement
        bad_secret = await client.post("/v1/platform/vault/secrets", headers=headers, json={"workspace_id": "finops-prod", "name": "BAD", "secret_value": "", "namespace": "byom"})
        assert bad_secret.status_code == 400

        viewer_headers = {**headers, "X-Keelway-Role": "viewer"}
        denied_vault = await client.post("/v1/platform/vault/secrets", headers=viewer_headers, json={"workspace_id": "finops-prod", "name": "ANTHROPIC_KEY", "secret_value": "sk-ant-1234567890", "namespace": "byom"})
        assert denied_vault.status_code == 403

        created_secret = await client.post("/v1/platform/vault/secrets", headers=headers, json={"workspace_id": "finops-prod", "name": "ANTHROPIC_KEY", "secret_value": "sk-live-secret-12345", "namespace": "byom"})
        assert created_secret.status_code == 201
        assert created_secret.json()["masked_preview"] == "sk-l****2345" and "sk-live-secret-12345" not in created_secret.text

        listed_sec = await client.get("/v1/platform/vault/secrets?workspace_id=finops-prod", headers=viewer_headers)
        assert listed_sec.status_code == 200 and listed_sec.json()["secrets"][0]["masked_preview"] == "sk-l****2345"
        assert "sk-live-secret-12345" not in listed_sec.text

        rot_sec = await client.post("/v1/platform/vault/secrets/ANTHROPIC_KEY/rotate", headers=headers, json={"workspace_id": "finops-prod", "secret_value": "sk-live-newkey-9999"})
        assert rot_sec.status_code == 200 and rot_sec.json()["version"] == 2 and rot_sec.json()["masked_preview"] == "sk-l****9999"

        assert (await client.delete("/v1/platform/vault/secrets/ANTHROPIC_KEY?workspace_id=finops-prod", headers=headers)).status_code == 200
        assert (await client.delete("/v1/platform/vault/secrets/ANTHROPIC_KEY?workspace_id=finops-prod", headers=headers)).status_code == 404

        # 3. Webhooks SSRF HTTP 400 + Viewer HTTP 403 + Test & Verify
        ssrf_resp = await client.post("/v1/platform/webhooks", headers=headers, json={"workspace_id": "finops-prod", "url": "http://169.254.169.254/latest/meta-data", "events": ["*"]})
        assert ssrf_resp.status_code == 400

        viewer_wh = await client.post("/v1/platform/webhooks", headers=viewer_headers, json={"workspace_id": "finops-prod", "url": "https://hooks.example.com/keelway", "events": ["*"]})
        assert viewer_wh.status_code == 403

        wh_resp = await client.post("/v1/platform/webhooks", headers=headers, json={"workspace_id": "finops-prod", "url": "https://hooks.example.com/keelway", "events": ["*"], "description": "Ops Pager", "secret": "whsec_route_secret_777"})
        assert wh_resp.status_code == 201
        wh_id = wh_resp.json()["id"]

        ping_resp = await client.post(f"/v1/platform/webhooks/{wh_id}/test", headers=headers)
        assert ping_resp.status_code == 200
        ping_data = ping_resp.json()
        assert ping_data["headers"]["X-Keelway-Signature-256"].startswith("sha256=")

        ver_ok = await client.post(
            "/v1/platform/webhooks/verify",
            headers=headers,
            json={
                "payload": ping_data["payload"],
                "signature": ping_data["signature"],
                "secret": "whsec_route_secret_777",
                "timestamp": ping_data["timestamp"],
            },
        )
        assert ver_ok.status_code == 200
        assert ver_ok.json()["valid"] is True

        ver_tampered = await client.post(
            "/v1/platform/webhooks/verify",
            headers=headers,
            json={
                "payload": {"altered": True},
                "signature": ping_data["signature"],
                "secret": "whsec_route_secret_777",
                "timestamp": ping_data["timestamp"],
            },
        )
        assert ver_tampered.status_code == 200
        assert ver_tampered.json()["valid"] is False

        wh_list = await client.get("/v1/platform/webhooks?workspace_id=finops-prod", headers=headers)
        assert wh_list.status_code == 200
        assert wh_list.json()["total"] == 1
        assert len(wh_list.json()["deliveries"]) >= 1

        # 4. Live Execution SSE Streaming + P-10 Hold/Resume + Viewer 403
        sse_run_resp = await client.post(
            "/v1/platform/execution/runs",
            headers=headers,
            json={
                "workspace_id": "finops-prod",
                "kind": "agent",
                "target_id": "devops-sre",
                "objective": "Roll out canary service",
                "requires_p10": True,
                "stream": True,
            },
        )
        assert sse_run_resp.status_code == 200
        assert sse_run_resp.headers["content-type"].startswith("text/event-stream")
        streamed_events = _parse_chunk_split_sse(sse_run_resp.text, chunk_size=17)
        assert streamed_events[-1]["type"] == "p10.held"
        run_id = streamed_events[0]["run_id"]

        # Viewer denied from resolving P-10 checkpoint
        viewer_p10 = await client.post(
            f"/v1/platform/execution/runs/{run_id}/p10",
            headers=viewer_headers,
            json={"decision": "approve", "approver": "viewer-user"},
        )
        assert viewer_p10.status_code == 403

        # Operator allowed to approve P-10 checkpoint
        operator_headers = {**headers, "X-Keelway-Role": "operator"}
        approved_resp = await client.post(
            f"/v1/platform/execution/runs/{run_id}/p10",
            headers=operator_headers,
            json={"decision": "approve", "approver": "ops-lead", "reason": "Canary healthy"},
        )
        assert approved_resp.status_code == 200
        assert approved_resp.json()["status"] == "completed"

        # Stream full post-approval events via GET /events
        events_resp = await client.get(f"/v1/platform/execution/runs/{run_id}/events", headers=headers)
        assert events_resp.status_code == 200
        assert events_resp.headers["content-type"].startswith("text/event-stream")
        final_events = _parse_chunk_split_sse(events_resp.text, chunk_size=23)
        assert [e["type"] for e in final_events] == [
            "run.started",
            "step.tool_call",
            "step.completed",
            "p10.held",
            "p10.approved",
            "run.completed",
        ]

        # Missing run -> 404; webhook delete -> 200 then 404; OpenAPI 3.1 schema exports cleanly
        assert (await client.get("/v1/platform/execution/runs/run-missing/events", headers=headers)).status_code == 404
        assert (await client.delete(f"/v1/platform/webhooks/{wh_id}", headers=headers)).status_code == 200
        assert (await client.delete(f"/v1/platform/webhooks/{wh_id}", headers=headers)).status_code == 404
        assert "/v1/platform/execution/runs" in app.openapi()["paths"]
