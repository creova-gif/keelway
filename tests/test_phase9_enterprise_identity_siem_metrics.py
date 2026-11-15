"""
Phase 9A Verification Suite — Enterprise OIDC/SAML Federation, SCIM 2.0 Provisioning,
Dual-Human P-10 Quorum, Tamper-Evident SIEM Exporter (`ocsf`/`cef`/`jsonl`),
Prometheus 0.0.4 + OpenTelemetry OTLP Observability, and Sovereign Enterprise CLI.
"""

from __future__ import annotations

import json
from pathlib import Path
import sqlite3

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
import pytest

from cli import main as cli_main
from core.api.platform_enterprise_routes import (
    get_enterprise_identity_siem_manager,
    router as platform_enterprise_router,
)
from core.api.platform_runtime_routes import (
    get_rbac_controller,
    router as platform_runtime_router,
)
from core.main import app as live_app
from core.platform.enterprise_identity_siem import (
    EnterpriseIdentitySiemManager,
    build_hs256_id_token,
    enterprise_identity_siem_manager,
)
from core.platform.kflow_crdt import KFlowDagEngine, KSpacesCrdtEngine
from core.platform.mcp_registry import PlatformMcpRegistry
from core.platform.rbac_webhooks import WorkspaceRbacController
from core.security.auth import launch_token


def test_oidc_ssrf_encryption_jwt_hardening_and_state_dir_isolation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_file = tmp_path / "phase9_oidc.db"
    mgr = EnterpriseIdentitySiemManager(db_path=db_file)
    assert mgr.journal_mode == "wal"

    default_cfg = mgr.get_oidc("ws-ent")
    assert default_cfg["enabled"] is False and default_cfg["signing_secret_configured"] is False

    # 1. SSRF & secret validation rejections
    bad_issuers = [
        "file:///etc/passwd",
        "http://169.254.169.254/latest/meta-data/",
        "https://metadata.google.internal/computeMetadata/v1",
        "https://10.0.1.25/oidc",
        "https://192.168.1.10/oidc",
        "https://172.16.8.4/oidc",
        "http://idp.enterprise.example/oidc",
    ]
    for bad_url in bad_issuers:
        with pytest.raises(ValueError):
            mgr.configure_oidc("ws-ent", bad_url, "keelway-oidc", "super-secret-oidc-signing-key-0123", {})

    with pytest.raises(ValueError, match="at least 16"):
        mgr.configure_oidc("ws-ent", "https://idp.enterprise.example", "keelway-oidc", "short-secret", {})

    with pytest.raises(ValueError, match="Unsupported mapped role"):
        mgr.configure_oidc(
            "ws-ent",
            "https://idp.enterprise.example",
            "keelway-oidc",
            "super-secret-oidc-signing-key-0123",
            {"grp": "superadmin"},
        )

    # 2. Loopback HTTP allowed for local IdP testing + HTTPS public IdP with AES-256-GCM encrypted secret
    raw_secret = "oidc-hs256-enterprise-secret-key-9876543210"
    assert mgr.configure_oidc("ws-local", "http://127.0.0.1:8080/realms/dev", "local-cid", raw_secret)["enabled"] is True

    cfg = mgr.configure_oidc(
        workspace_id="ws-ent",
        issuer_url="https://idp.enterprise.example",
        client_id="keelway-oidc",
        signing_secret=raw_secret,
        group_role_mapping={
            "keelway-viewers": "viewer",
            "keelway-builders": "builder",
            "keelway-operators": "operator",
            "keelway-admins": "admin",
        },
    )
    assert cfg["signing_secret_configured"] is True
    assert str(cfg["signing_secret_fingerprint"]).startswith("sha256:")
    assert "signing_secret" not in cfg and raw_secret not in json.dumps(cfg)
    raw_db_bytes = db_file.read_bytes()
    assert raw_secret.encode("utf-8") not in raw_db_bytes

    # Updating mapping without resending signing_secret preserves encrypted secret
    updated_cfg = mgr.configure_oidc(
        workspace_id="ws-ent",
        issuer_url="https://idp.enterprise.example",
        client_id="keelway-oidc",
        signing_secret=None,
        group_role_mapping={"keelway-operators": "operator", "keelway-admins": "admin", "keelway-owners": "owner"},
    )
    assert updated_cfg["signing_secret_fingerprint"] == cfg["signing_secret_fingerprint"]

    # 3. Valid JWT exchange + multi-group rank precedence + unmapped least-privilege fallback
    valid_tok = build_hs256_id_token(
        issuer="https://idp.enterprise.example",
        client_id=["other-client", "keelway-oidc"],
        signing_secret=raw_secret,
        subject="uid-alice",
        email="alice@enterprise.example",
        groups=["unmapped-team", "keelway-operators", "keelway-admins"],
    )
    exchanged = mgr.exchange_oidc_token("ws-ent", valid_tok)
    assert exchanged == {
        "workspace_id": "ws-ent",
        "authenticated": True,
        "subject": "uid-alice",
        "email": "alice@enterprise.example",
        "groups": ["unmapped-team", "keelway-operators", "keelway-admins"],
        "mapped_role": "admin",
        "issuer": "https://idp.enterprise.example",
    }

    unmapped_tok = build_hs256_id_token(
        issuer="https://idp.enterprise.example",
        client_id="keelway-oidc",
        signing_secret=raw_secret,
        subject="uid-contractor",
        groups=["external-contractors"],
    )
    assert mgr.exchange_oidc_token("ws-ent", unmapped_tok)["mapped_role"] == "viewer"

    # 4. Strict alg="none", RS256 downgrade, bad sig, expired, future nbf, wrong iss/aud rejections
    none_tok = build_hs256_id_token(
        "https://idp.enterprise.example", "keelway-oidc", raw_secret, header_overrides={"alg": "none"}
    )
    rs256_tok = build_hs256_id_token(
        "https://idp.enterprise.example", "keelway-oidc", raw_secret, header_overrides={"alg": "RS256"}
    )
    wrong_sig_tok = build_hs256_id_token(
        "https://idp.enterprise.example", "keelway-oidc", "wrong-signing-secret-key-0000000000"
    )
    expired_tok = build_hs256_id_token(
        "https://idp.enterprise.example", "keelway-oidc", raw_secret, exp_offset_seconds=-120
    )
    future_nbf_tok = build_hs256_id_token(
        "https://idp.enterprise.example", "keelway-oidc", raw_secret, nbf_offset_seconds=120
    )
    wrong_iss_tok = build_hs256_id_token("https://evil.example", "keelway-oidc", raw_secret)
    wrong_aud_tok = build_hs256_id_token("https://idp.enterprise.example", "wrong-aud", raw_secret)

    for rejected_tok in (
        none_tok, rs256_tok, wrong_sig_tok, expired_tok, future_nbf_tok,
        wrong_iss_tok, wrong_aud_tok, "not.a.jwt.token", "two.parts",
    ):
        with pytest.raises(PermissionError):
            mgr.exchange_oidc_token("ws-ent", rejected_tok)

    mgr.close()

    # 5. Dynamic KEELWAY_STATE_DIR resolution on default singleton per call
    isolated_state = tmp_path / "isolated_state_dir"
    monkeypatch.delenv("KEELWAY_RUNTIME_DB_PATH", raising=False)
    monkeypatch.setenv("KEELWAY_STATE_DIR", str(isolated_state))
    assert Path(enterprise_identity_siem_manager.db_path) == (isolated_state / "platform_runtime.db").resolve()
    assert enterprise_identity_siem_manager.get_oidc("default")["enabled"] is False


def test_scim_quorum_siem_dlp_and_observability_metrics(tmp_path: Path) -> None:
    db_file = tmp_path / "phase9_core.db"
    rbac = WorkspaceRbacController(db_path=db_file)
    kflow = KFlowDagEngine(db_path=db_file)
    crdt = KSpacesCrdtEngine(db_path=db_file)
    mcp = PlatformMcpRegistry(db_path=db_file)
    mgr = EnterpriseIdentitySiemManager(db_path=db_file)

    try:
        # Empty workspace SIEM export emits heartbeat
        hb = mgr.export_siem("ws-sec", export_format="ocsf")
        assert hb["record_count"] == 1 and hb["records"][0]["activity_name"] == "heartbeat"

        mgr.configure_oidc(
            "ws-sec",
            "https://okta.enterprise.example",
            "keelway-prod",
            "okta-signing-secret-0123456789abcdef",
            {"sec-operators": "operator", "sec-admins": "admin"},
        )

        # 1. SCIM 2.0 Provisioning + Deactivation RBAC sync
        u1 = mgr.provision_scim_user(
            "ws-sec", "sre@enterprise.example", "SRE Lead", groups=["sec-operators"], active=True, rbac=rbac
        )
        assert u1["mapped_role"] == "operator" and u1["active"] is True
        assert rbac.check_permission("ws-sec", "sre@enterprise.example", "p10:approve")["allowed"] is True

        deact = mgr.patch_scim_user("ws-sec", u1["id"], active=False, rbac=rbac)
        assert deact["active"] is False and deact["mapped_role"] == "viewer"
        assert rbac.check_permission("ws-sec", "sre@enterprise.example", "p10:approve")["allowed"] is False

        react = mgr.patch_scim_user("ws-sec", u1["id"], active=True, groups=["sec-admins"], rbac=rbac)
        assert react["active"] is True and react["mapped_role"] == "admin"
        assert rbac.check_permission("ws-sec", "sre@enterprise.example", "rbac:manage")["allowed"] is True

        listing = mgr.list_scim_users("ws-sec")
        assert listing["schemas"] == ["urn:ietf:params:scim:api:messages:2.0:ListResponse"]
        assert listing["totalResults"] == 1 and listing["Resources"][0]["userName"] == "sre@enterprise.example"

        with pytest.raises(KeyError):
            mgr.patch_scim_user("ws-sec", "scim-missing", active=False)

        # 2. Dual-Human P-10 Quorum invariants & secret redaction in reason
        with pytest.raises(ValueError):
            mgr.approve_p10_quorum("ws-sec", "prop-1", "alice", "owner", required_approvals=1)
        for bad_role in ("admin", "builder", "viewer"):
            with pytest.raises(PermissionError):
                mgr.approve_p10_quorum("ws-sec", "prop-1", "alice", bad_role)
        for bot_id in ("agent-release", "bot-ci", "system-worker", ""):
            with pytest.raises(PermissionError):
                mgr.approve_p10_quorum("ws-sec", "prop-1", bot_id, "operator")
        with pytest.raises(PermissionError, match="Self-approval"):
            mgr.approve_p10_quorum("ws-sec", "prop-1", "initiator-dan", "owner", initiator_id="initiator-dan")

        leaked_openai = "sk-proj-SuperSecretLeakToken1234567890"
        leaked_kw = "kw_live_SecretKeelwayApiToken987654321"
        leaked_gh = "ghp_0123456789abcdefghijklmnopqrstuvwxyzABCD"

        first = mgr.approve_p10_quorum(
            "ws-sec",
            "prop-1",
            "alice@enterprise.example",
            "operator",
            initiator_id="initiator-dan",
            reason=f"Checked run {leaked_openai} and {leaked_kw}",
        )
        assert first["status"] == "awaiting_quorum" and first["approval_count"] == 1
        assert leaked_openai not in json.dumps(first) and leaked_kw not in json.dumps(first)

        # Recorded initiator still blocked on subsequent approval even if initiator_id omitted
        with pytest.raises(PermissionError, match="Self-approval"):
            mgr.approve_p10_quorum("ws-sec", "prop-1", "initiator-dan", "owner")

        # Duplicate approval from same human -> RuntimeError (409)
        with pytest.raises(RuntimeError, match="Duplicate quorum approval"):
            mgr.approve_p10_quorum("ws-sec", "prop-1", "alice@enterprise.example", "operator")

        second = mgr.approve_p10_quorum(
            "ws-sec", "prop-1", "bob@enterprise.example", "owner", reason=f"Final signoff {leaked_gh}"
        )
        assert second["status"] == "quorum_approved" and second["approval_count"] == 2
        assert second["quorum_receipt_sha256"].startswith("sha256:")
        assert mgr.get_p10_quorum("ws-sec", "prop-1")["quorum_receipt_sha256"] == second["quorum_receipt_sha256"]

        # Seed KFlow, CRDT, and MCP rows (plus an unredacted raw SQL row to prove SIEM export scrubs on read too)
        kflow.execute_dag("ws-sec", "WF-9", [{"id": "n1", "label": "Check", "depends_on": []}])
        crdt.apply_ops("ws-sec", "peer-1", [{"namespace": "ops", "key": "k1", "op": "set", "value": "ok"}])
        mcp.register_server("ws-sec", "ext-mcp", "Ext MCP", "sse", "https://mcp.enterprise.example/sse")
        with sqlite3.connect(str(db_file)) as raw_conn:
            raw_conn.execute(
                "INSERT INTO platform_kflow_runs VALUES (?, ?, ?, ?, ?, ?)",
                ("kflow-raw", "ws-sec", "WF-LEAK", "failed", json.dumps({"err": leaked_openai, "gh": leaked_gh}), "2026-11-15T00:00:00+00:00"),
            )

        # 3. SIEM export across OCSF, CEF, JSONL with zero secret leakage
        for fmt in ("ocsf", "cef", "jsonl"):
            exp = mgr.export_siem("ws-sec", export_format=fmt, limit=25)
            assert exp["format"] == fmt and exp["record_count"] >= 4
            assert exp["batch_sha256"].startswith("sha256:")
            dumped = json.dumps(exp)
            for secret in (leaked_openai, leaked_kw, leaked_gh):
                assert secret not in dumped
            if fmt == "ocsf":
                assert exp["records"][0]["metadata"]["product"]["version"] == "1.0.0"
            elif fmt == "cef":
                assert all(line.startswith("CEF:0|SorvexLabs|Keelway|1.0.0|") for line in exp["records"])
            else:
                assert all(json.loads(line)["workspace_id"] == "ws-sec" for line in exp["records"])

        # 4. Prometheus & OTLP Metrics
        prom_m = mgr.get_observability_metrics("ws-sec", metrics_format="prometheus")
        otlp_m = mgr.get_observability_metrics("ws-sec", metrics_format="otlp")
        assert otlp_m["format"] == "otlp_json"
        assert prom_m["counters"] == {
            "keelway_kflow_runs_total": 2,
            "keelway_crdt_entries_total": 1,
            "keelway_mcp_servers_total": 1,
            "keelway_scim_active_users": 1,
            "keelway_p10_quorum_approved_total": 1,
            "keelway_siem_exports_total": 4,
        }
        assert '# TYPE keelway_p10_quorum_approved_total counter' in prom_m["prometheus_text"]
        assert 'keelway_scim_active_users{workspace="ws-sec"} 1' in prom_m["prometheus_text"]
        attrs = {a["key"]: a["value"]["stringValue"] for a in otlp_m["otlp_resource_metrics"]["resource"]["attributes"]}
        assert attrs["service.name"] == "keelway-core" and attrs["service.version"] == "1.0.0"
        assert len(otlp_m["otlp_resource_metrics"]["scopeMetrics"][0]["metrics"]) == 6
    finally:
        mgr.close()
        mcp.close()
        crdt.close()
        kflow.close()
        rbac.close()


@pytest.mark.asyncio
async def test_fastapi_enterprise_routes_rbac_quorum_status_codes_and_live_v1(tmp_path: Path) -> None:
    db_file = tmp_path / "api_phase9.db"
    rbac = WorkspaceRbacController(db_path=db_file)
    mgr = EnterpriseIdentitySiemManager(db_path=db_file)

    test_app = FastAPI()
    test_app.include_router(platform_runtime_router)
    test_app.include_router(platform_enterprise_router)
    test_app.dependency_overrides[get_rbac_controller] = lambda: rbac
    test_app.dependency_overrides[get_enterprise_identity_siem_manager] = lambda: mgr

    owner_hdrs = {"Authorization": f"Bearer {launch_token()}"}
    admin_hdrs = {**owner_hdrs, "X-Keelway-Role": "admin"}
    operator_hdrs = {**owner_hdrs, "X-Keelway-Role": "operator"}
    builder_hdrs = {**owner_hdrs, "X-Keelway-Role": "builder"}
    viewer_hdrs = {**owner_hdrs, "X-Keelway-Role": "viewer"}

    secret = "enterprise-api-oidc-secret-0123456789"
    try:
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://testserver") as client:
            # OIDC RBAC & SSRF
            assert (
                await client.put(
                    "/v1/platform/enterprise/oidc",
                    headers=operator_hdrs,
                    json={"issuer_url": "https://idp.example.com", "client_id": "cid", "signing_secret": secret},
                )
            ).status_code == 403

            assert (
                await client.put(
                    "/v1/platform/enterprise/oidc",
                    headers=admin_hdrs,
                    json={"issuer_url": "http://169.254.169.254/latest", "client_id": "cid", "signing_secret": secret},
                )
            ).status_code == 400

            put_ok = await client.put(
                "/v1/platform/enterprise/oidc",
                headers=admin_hdrs,
                json={
                    "issuer_url": "https://idp.example.com",
                    "client_id": "cid",
                    "signing_secret": secret,
                    "group_role_mapping": {"ops": "operator"},
                },
            )
            assert put_ok.status_code == 200 and put_ok.json()["signing_secret_configured"] is True
            assert (await client.get("/v1/platform/enterprise/oidc", headers=viewer_hdrs)).status_code == 200

            # OIDC Token Exchange: 200 valid, 401 tampered/alg=none, 400 empty
            good_jwt = build_hs256_id_token("https://idp.example.com", "cid", secret, subject="u-1", groups=["ops"])
            ex_ok = await client.post("/v1/platform/enterprise/oidc/exchange", headers=viewer_hdrs, json={"id_token": good_jwt})
            assert ex_ok.status_code == 200 and ex_ok.json()["mapped_role"] == "operator"

            none_jwt = build_hs256_id_token("https://idp.example.com", "cid", secret, header_overrides={"alg": "none"})
            assert (await client.post("/v1/platform/enterprise/oidc/exchange", headers=viewer_hdrs, json={"id_token": none_jwt})).status_code == 401
            assert (await client.post("/v1/platform/enterprise/oidc/exchange", headers=viewer_hdrs, json={"id_token": ""})).status_code == 400

            # SCIM 2.0 Users: 403 for viewer, 200 provision + SCIM PatchOp deactivation + 404 missing
            assert (await client.post("/v1/platform/enterprise/scim/v2/Users", headers=viewer_hdrs, json={"userName": "x@y.com"})).status_code == 403
            scim_created = await client.post(
                "/v1/platform/enterprise/scim/v2/Users",
                headers=admin_hdrs,
                json={"userName": "op1@example.com", "displayName": "Op One", "groups": ["ops"]},
            )
            assert scim_created.status_code == 200 and scim_created.json()["mapped_role"] == "operator"
            uid = scim_created.json()["id"]

            scim_patched = await client.patch(
                f"/v1/platform/enterprise/scim/v2/Users/{uid}",
                headers=admin_hdrs,
                json={"Operations": [{"op": "replace", "path": "active", "value": False}]},
            )
            assert scim_patched.status_code == 200 and scim_patched.json()["active"] is False
            assert (await client.patch("/v1/platform/enterprise/scim/v2/Users/missing-id", headers=admin_hdrs, json={"active": False})).status_code == 404
            assert (await client.get("/v1/platform/enterprise/scim/v2/Users", headers=viewer_hdrs)).json()["totalResults"] == 1

            # Dual-Human P-10 Quorum: 403 for admin/builder/viewer/self/agent-*, 409 for duplicate, 200 for 2 distinct owner/operator
            for denied_h in (admin_hdrs, builder_hdrs, viewer_hdrs):
                res_denied = await client.post(
                    "/v1/platform/enterprise/p10-quorum/approve",
                    headers=denied_h,
                    json={"proposal_id": "P10-PROD-1", "approver_id": "human-1", "initiator_id": "dev-init"},
                )
                assert res_denied.status_code == 403

            assert (
                await client.post(
                    "/v1/platform/enterprise/p10-quorum/approve",
                    headers=operator_hdrs,
                    json={"proposal_id": "P10-PROD-1", "approver_id": "agent-autopilot"},
                )
            ).status_code == 403
            assert (
                await client.post(
                    "/v1/platform/enterprise/p10-quorum/approve",
                    headers=operator_hdrs,
                    json={"proposal_id": "P10-PROD-1", "approver_id": "dev-init", "initiator_id": "dev-init"},
                )
            ).status_code == 403

            q1 = await client.post(
                "/v1/platform/enterprise/p10-quorum/approve",
                headers={**operator_hdrs, "X-Keelway-Actor": "sre-alice"},
                json={"proposal_id": "P10-PROD-1", "initiator_id": "dev-init", "reason": "Stage 1 verified"},
            )
            assert q1.status_code == 200 and q1.json()["status"] == "awaiting_quorum"

            dup_q = await client.post(
                "/v1/platform/enterprise/p10-quorum/approve",
                headers={**operator_hdrs, "X-Keelway-Actor": "sre-alice"},
                json={"proposal_id": "P10-PROD-1"},
            )
            assert dup_q.status_code == 409

            q2 = await client.post(
                "/v1/platform/enterprise/p10-quorum/approve",
                headers={**owner_hdrs, "X-Keelway-Actor": "sec-bob"},
                json={"proposal_id": "P10-PROD-1", "reason": "Stage 2 verified"},
            )
            assert q2.status_code == 200 and q2.json()["status"] == "quorum_approved"

            get_q = await client.get("/v1/platform/enterprise/p10-quorum/P10-PROD-1", headers=viewer_hdrs)
            assert get_q.status_code == 200 and get_q.json()["approval_count"] == 2
            assert (await client.get("/v1/platform/enterprise/p10-quorum/UNKNOWN", headers=viewer_hdrs)).status_code == 404

            # SIEM & Observability Metrics routes
            siem_r = await client.get("/v1/platform/enterprise/siem/export?format=cef&limit=10", headers=viewer_hdrs)
            assert siem_r.status_code == 200 and siem_r.json()["format"] == "cef"
            assert (await client.get("/v1/platform/enterprise/siem/export?format=xml", headers=viewer_hdrs)).status_code == 400

            met_r = await client.get("/v1/platform/observability/metrics?format=prometheus", headers=viewer_hdrs)
            assert met_r.status_code == 200 and "keelway_p10_quorum_approved_total" in met_r.json()["prometheus_text"]
            assert (await client.get("/v1/platform/observability/metrics?format=bad", headers=viewer_hdrs)).status_code == 400

        assert live_app.version == "1.0.0"
        live_paths = live_app.openapi()["paths"]
        for route_path in (
            "/v1/platform/enterprise/oidc", "/v1/platform/enterprise/oidc/exchange",
            "/v1/platform/enterprise/scim/v2/Users", "/v1/platform/enterprise/scim/v2/Users/{scim_user_id}",
            "/v1/platform/enterprise/p10-quorum/approve", "/v1/platform/enterprise/p10-quorum/{proposal_id}",
            "/v1/platform/enterprise/siem/export", "/v1/platform/observability/metrics",
        ):
            assert route_path in live_paths
    finally:
        mgr.close()
        rbac.close()


def test_cli_enterprise_sso_scim_siem_export_and_metrics(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    db_file = str(tmp_path / "cli_phase9.db")
    sec = "cli-enterprise-oidc-secret-0123456789"

    assert cli_main(["sso", "status", "--workspace", "default", "--db-path", db_file, "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["enabled"] is False

    assert cli_main([
        "sso", "configure", "--workspace", "default", "--issuer", "https://idp.enterprise.example",
        "--client-id", "keelway-oidc", "--secret", sec, "--map", "keelway-operators=operator",
        "--db-path", db_file, "--json",
    ]) == 0
    cfg_out = json.loads(capsys.readouterr().out)
    assert cfg_out["enabled"] is True and cfg_out["group_role_mapping"] == {"keelway-operators": "operator"}

    assert cli_main([
        "scim", "provision", "--workspace", "default", "--user", "sre@enterprise.example",
        "--display-name", "SRE Lead", "--group", "keelway-operators", "--db-path", db_file, "--json",
    ]) == 0
    prov_out = json.loads(capsys.readouterr().out)
    assert prov_out["mapped_role"] == "operator" and prov_out["active"] is True

    assert cli_main(["scim", "list", "--workspace", "default", "--db-path", db_file, "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["totalResults"] == 1

    assert cli_main(["siem-export", "--workspace", "default", "--format", "ocsf", "--db-path", db_file, "--json"]) == 0
    siem_out = json.loads(capsys.readouterr().out)
    assert siem_out["format"] == "ocsf" and siem_out["record_count"] >= 1

    assert cli_main(["metrics", "--workspace", "default", "--format", "prometheus", "--db-path", db_file, "--json"]) == 0
    met_out = json.loads(capsys.readouterr().out)
    assert met_out["counters"]["keelway_scim_active_users"] == 1
    assert met_out["counters"]["keelway_siem_exports_total"] == 1

    # Invalid SSRF issuer returns deterministic exit code 1
    assert cli_main([
        "sso", "configure", "--workspace", "default", "--issuer", "file:///etc/passwd",
        "--client-id", "bad", "--secret", sec, "--db-path", db_file, "--json",
    ]) == 1
    capsys.readouterr()
