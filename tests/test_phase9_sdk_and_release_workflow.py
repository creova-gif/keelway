"""
Phase 9B Tri-SDK Parity, GitHub Release Artifacts Workflow & Website v1.0 Docs Verification Suite.
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

import httpx
import pytest

from core.sdk import (
    AsyncKeelwayClient,
    AsyncPlatformClient,
    KeelwayClient,
    PermissionDeniedError,
    QuorumRequiredError,
    SyncPlatformClient,
)
from core.security.sbom import SBOMGenerator, SBOMVerifier

REPO_ROOT = Path(__file__).resolve().parent.parent

PHASE9_PYTHON_METHODS = (
    "configure_oidc_provider",
    "list_scim_users",
    "provision_scim_user",
    "approve_p10_quorum",
    "export_siem_audit",
    "get_observability_metrics",
)


def _load_yaml_if_available(path: Path) -> Any:
    raw = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError:
        return None
    return yaml.safe_load(raw)


def _make_phase9_mock_transport() -> Tuple[httpx.MockTransport, List[Dict[str, Any]]]:
    recorded: List[Dict[str, Any]] = []
    quorum_approvals: Dict[str, List[Dict[str, str]]] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        raw = request.content.decode("utf-8") if request.content else ""
        body = json.loads(raw) if raw else None
        path, params = request.url.path, dict(request.url.params)
        recorded.append(
            {
                "method": request.method,
                "path": path,
                "params": params,
                "headers": dict(request.headers),
                "json": body,
            }
        )

        if request.headers.get("authorization") == "Bearer kw_live_viewer":
            return httpx.Response(403, json={"detail": "Forbidden for viewer role"})

        if request.method == "PUT" and path == "/v1/platform/enterprise/oidc":
            return httpx.Response(
                200,
                json={
                    "workspace_id": body["workspace_id"],
                    "issuer_url": body["issuer_url"],
                    "client_id": body["client_id"],
                    "enabled": body["enabled"],
                    "signing_secret_configured": bool(body.get("signing_secret")),
                    "signing_secret_fingerprint": "sha256:" + "1" * 64,
                    "group_role_mapping": body.get("group_role_mapping") or {},
                    "updated_at": "2026-11-15T00:00:00Z",
                },
            )

        if request.method == "POST" and path == "/v1/platform/enterprise/scim/v2/Users":
            return httpx.Response(
                200,
                json={
                    "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
                    "id": "scim-py-01",
                    "userName": body["userName"],
                    "displayName": body["displayName"],
                    "active": body["active"],
                    "groups": body["groups"],
                    "mapped_role": "admin",
                    "updated_at": "2026-11-15T00:00:01Z",
                },
            )

        if request.method == "GET" and path == "/v1/platform/enterprise/scim/v2/Users":
            return httpx.Response(
                200,
                json={
                    "schemas": ["urn:ietf:params:scim:api:messages:2.0:ListResponse"],
                    "workspace_id": params.get("workspace_id", "default"),
                    "totalResults": 1,
                    "Resources": [
                        {
                            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
                            "id": "scim-py-01",
                            "userName": "alice@keelway.dev",
                            "displayName": "Alice Security",
                            "active": True,
                            "groups": ["okta:admins"],
                            "mapped_role": "admin",
                        }
                    ],
                },
            )

        if request.method == "POST" and path == "/v1/platform/enterprise/p10-quorum/approve":
            if body.get("initiator_id") and body["approver_id"] == body["initiator_id"]:
                return httpx.Response(
                    403,
                    json={"detail": "Dual-human P-10 quorum violation: initiator cannot self-approve"},
                )
            prop_id = body["proposal_id"]
            entries = quorum_approvals.setdefault(prop_id, [])
            entries.append({"approver_id": body["approver_id"], "reason": body.get("reason", "")})
            req_count = int(body.get("required_approvals", 2))
            approved = len(entries) >= req_count
            return httpx.Response(
                200,
                json={
                    "workspace_id": body["workspace_id"],
                    "proposal_id": prop_id,
                    "initiator_id": body.get("initiator_id", ""),
                    "required_approvals": req_count,
                    "approval_count": len(entries),
                    "status": "quorum_approved" if approved else "awaiting_quorum",
                    "approvals": list(entries),
                    "quorum_receipt_sha256": "2" * 64 if approved else None,
                },
            )

        if request.method == "GET" and path == "/v1/platform/enterprise/siem/export":
            fmt = params.get("format", "ocsf")
            return httpx.Response(
                200,
                json={
                    "workspace_id": params.get("workspace_id", "default"),
                    "format": fmt,
                    "record_count": 2,
                    "batch_sha256": "3" * 64,
                    "exported_at": "2026-11-15T00:00:02Z",
                    "records": [{"class_uid": 3002}, {"class_uid": 6003}],
                },
            )

        if request.method == "GET" and path == "/v1/platform/observability/metrics":
            fmt = params.get("format", "otlp_json")
            return httpx.Response(
                200,
                json={
                    "workspace_id": params.get("workspace_id", "default"),
                    "format": fmt,
                    "generated_at": "2026-11-15T00:00:03Z",
                    "counters": {"keelway_scim_active_users": 1, "keelway_p10_quorum_approved_total": 1},
                    "prometheus_text": "keelway_scim_active_users 1\n" if fmt == "prometheus" else None,
                    "otlp_resource_metrics": {"resourceMetrics": []} if fmt == "otlp_json" else None,
                },
            )

        return httpx.Response(404, json={"detail": f"Unhandled {request.method} {path}"})

    return httpx.MockTransport(handler), recorded


def test_python_sync_sdk_phase9_enterprise_and_observability_mock_transport() -> None:
    for method_name in PHASE9_PYTHON_METHODS:
        sync_sig = inspect.signature(getattr(SyncPlatformClient, method_name))
        async_sig = inspect.signature(getattr(AsyncPlatformClient, method_name))
        assert list(sync_sig.parameters.values()) == list(async_sig.parameters.values())

    transport, recorded = _make_phase9_mock_transport()
    with KeelwayClient(token="kw_live_py9_sync", transport=transport) as client:
        oidc = client.platform.configure_oidc_provider(
            "https://idp.keelway.dev",
            "keelway-sso",
            signing_secret="oidc-hs256-super-secret-key",
            group_role_mapping={"okta:admins": "admin", "okta:builders": "builder"},
            enabled=True,
            workspace_id="ws-p9",
        )
        assert oidc["signing_secret_configured"] is True
        assert recorded[-1]["json"] == {
            "workspace_id": "ws-p9",
            "issuer_url": "https://idp.keelway.dev",
            "client_id": "keelway-sso",
            "signing_secret": "oidc-hs256-super-secret-key",
            "group_role_mapping": {"okta:admins": "admin", "okta:builders": "builder"},
            "enabled": True,
        }

        scim_user = client.platform.provision_scim_user(
            userName="alice@keelway.dev",
            displayName="Alice Security",
            groups=["okta:admins"],
            active=True,
            workspace_id="ws-p9",
        )
        assert scim_user["mapped_role"] == "admin"
        assert recorded[-1]["json"]["userName"] == "alice@keelway.dev"

        with pytest.raises(ValueError, match="user_name"):
            client.platform.provision_scim_user("")

        scim_list = client.platform.list_scim_users("ws-p9")
        assert scim_list["totalResults"] == 1
        assert recorded[-1]["params"] == {"workspace_id": "ws-p9"}

        with pytest.raises(QuorumRequiredError):
            client.platform.approve_p10_quorum(
                "PROP-01",
                "alice@keelway.dev",
                initiator_id="alice@keelway.dev",
                workspace_id="ws-p9",
            )

        q1 = client.platform.approve_p10_quorum(
            "PROP-01",
            "bob@keelway.dev",
            initiator_id="alice@keelway.dev",
            required_approvals=2,
            reason="Reviewed rollout diff",
            workspace_id="ws-p9",
        )
        assert q1["status"] == "awaiting_quorum"
        assert q1["approval_count"] == 1

        q2 = client.platform.approve_p10_quorum(
            "PROP-01",
            "carol@keelway.dev",
            initiator_id="alice@keelway.dev",
            required_approvals=2,
            reason="Independent security verification",
            workspace_id="ws-p9",
        )
        assert q2["status"] == "quorum_approved"
        assert len(q2["quorum_receipt_sha256"]) == 64

        siem = client.platform.export_siem_audit(format="cef", limit=25, workspace_id="ws-p9")
        assert siem["format"] == "cef"
        assert recorded[-1]["params"] == {"workspace_id": "ws-p9", "format": "cef", "limit": "25"}

        metrics = client.platform.get_observability_metrics(format="prometheus", workspace_id="ws-p9")
        assert metrics["format"] == "prometheus"
        assert "keelway_scim_active_users" in metrics["prometheus_text"]

    viewer_transport, _ = _make_phase9_mock_transport()
    with KeelwayClient(token="kw_live_viewer", transport=viewer_transport) as viewer:
        with pytest.raises(PermissionDeniedError):
            viewer.platform.configure_oidc_provider("https://idp.keelway.dev", "denied")


async def test_python_async_sdk_live_asgi_and_tri_sdk_symbol_parity(tmp_path: Path) -> None:
    from httpx import ASGITransport

    from core.api.platform_enterprise_routes import get_enterprise_identity_siem_manager
    from core.api.platform_runtime_routes import get_rbac_controller
    from core.main import app
    from core.platform.enterprise_identity_siem import EnterpriseIdentitySiemManager
    from core.platform.rbac_webhooks import WorkspaceRbacController
    from core.security.auth import launch_token

    db_file = tmp_path / "phase9_live_sdk.db"
    ent_mgr = EnterpriseIdentitySiemManager(db_path=db_file)
    rbac = WorkspaceRbacController(db_path=db_file)
    app.dependency_overrides[get_enterprise_identity_siem_manager] = lambda: ent_mgr
    app.dependency_overrides[get_rbac_controller] = lambda: rbac
    try:
        async with AsyncKeelwayClient(
            base_url="http://localhost",
            token=launch_token(),
            transport=ASGITransport(app=app),
        ) as client:
            oidc = await client.platform.configure_oidc_provider(
                "https://login.keelway.dev",
                "keelway-live-client",
                signing_secret="live-oidc-signing-secret-2026-key",
                group_role_mapping={"idp:admins": "admin", "idp:ops": "operator"},
                enabled=True,
                workspace_id="ws-live-9",
            )
            assert oidc["workspace_id"] == "ws-live-9"
            assert oidc["signing_secret_configured"] is True

            user = await client.platform.provision_scim_user(
                "dana@keelway.dev",
                "Dana Operator",
                groups=["idp:admins"],
                active=True,
                workspace_id="ws-live-9",
            )
            assert user["userName"] == "dana@keelway.dev"
            assert user["mapped_role"] == "admin"

            users = await client.platform.list_scim_users("ws-live-9")
            assert users["totalResults"] == 1
            assert users["Resources"][0]["userName"] == "dana@keelway.dev"

            with pytest.raises((QuorumRequiredError, PermissionDeniedError)):
                await client.platform.approve_p10_quorum(
                    "PROP-LIVE-01",
                    "initiator@keelway.dev",
                    initiator_id="initiator@keelway.dev",
                    workspace_id="ws-live-9",
                )

            first = await client.platform.approve_p10_quorum(
                "PROP-LIVE-01",
                "approver-one@keelway.dev",
                initiator_id="initiator@keelway.dev",
                required_approvals=2,
                reason="Checked Canary Gate",
                workspace_id="ws-live-9",
            )
            assert first["status"] == "awaiting_quorum"
            assert first["approval_count"] == 1

            second = await client.platform.approve_p10_quorum(
                "PROP-LIVE-01",
                "approver-two@keelway.dev",
                initiator_id="initiator@keelway.dev",
                required_approvals=2,
                reason="Checked Rollback Plan",
                workspace_id="ws-live-9",
            )
            assert second["status"] == "quorum_approved"
            assert second["approval_count"] == 2
            assert second["quorum_receipt_sha256"]

            for fmt in ("ocsf", "cef", "jsonl"):
                siem = await client.platform.export_siem_audit(
                    format=fmt, limit=20, workspace_id="ws-live-9"
                )
                assert siem["format"] == fmt
                assert siem["record_count"] >= 1
                assert siem["batch_sha256"]

            otlp = await client.platform.get_observability_metrics(
                format="otlp_json", workspace_id="ws-live-9"
            )
            assert otlp["format"] == "otlp_json"
            assert otlp["otlp_resource_metrics"] is not None

            prom = await client.platform.get_observability_metrics(
                format="prometheus", workspace_id="ws-live-9"
            )
            assert prom["format"] == "prometheus"
            assert "keelway_scim_active_users" in prom["prometheus_text"]
    finally:
        app.dependency_overrides.pop(get_enterprise_identity_siem_manager, None)
        app.dependency_overrides.pop(get_rbac_controller, None)
        close_ent = getattr(ent_mgr, "close", None)
        if callable(close_ent):
            close_ent()
        rbac.close()

    ts_src = (REPO_ROOT / "sdk" / "typescript" / "src" / "platform.ts").read_text(encoding="utf-8")
    ts_ent = (REPO_ROOT / "sdk" / "typescript" / "src" / "platformEnterprise.ts").read_text(encoding="utf-8")
    ts_dts = (REPO_ROOT / "sdk" / "typescript" / "dist" / "platform.d.ts").read_text(encoding="utf-8")
    for ts_method in (
        "configureOidcProvider",
        "listScimUsers",
        "provisionScimUser",
        "approveP10Quorum",
        "exportSiemAudit",
        "getObservabilityMetrics",
    ):
        assert ts_method in ts_src and ts_method in ts_ent and ts_method in ts_dts

    go_src = (REPO_ROOT / "sdk" / "go" / "platform_phase9.go").read_text(encoding="utf-8")
    for go_method in (
        "ConfigureOIDCProvider",
        "ListSCIMUsers",
        "ProvisionSCIMUser",
        "ApproveP10Quorum",
        "ExportSIEMAudit",
        "GetObservabilityMetrics",
    ):
        assert f"func (p *PlatformService) {go_method}(" in go_src


def test_release_artifacts_workflow_and_docs_hub_v1_sync() -> None:
    wf_path = REPO_ROOT / ".github" / "workflows" / "release-artifacts.yml"
    assert wf_path.is_file(), ".github/workflows/release-artifacts.yml must exist"
    wf_raw = wf_path.read_text(encoding="utf-8")
    assert len(wf_raw.splitlines()) < 90, "release-artifacts.yml must remain < 90 lines"

    for token in (
        'tags:\n      - "v*"',
        "workflow_dispatch:",
        "tag_name:",
        "contents: write",
        "runs-on: ubuntu-latest",
        'python-version: "3.12"',
        'TAG_NAME="${{ github.event.inputs.tag_name || github.ref_name }}"',
        "python -m build --outdir dist/",
        "dist/keelway-sbom.cdx.json",
        "SBOMGenerator.generate(Path('.')).to_dict()",
        "SBOMVerifier.verify(",
        "SHA256SUMS.txt",
        "GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}",
        'gh release view "$TAG_NAME"',
        'gh release upload "$TAG_NAME"',
        "--clobber",
        'gh release create "$TAG_NAME"',
        '--title "Keelway $TAG_NAME" --generate-notes',
    ):
        assert token in wf_raw, f"Missing '{token}' in release-artifacts.yml"

    parsed = _load_yaml_if_available(wf_path)
    if parsed is not None:
        on_block = parsed.get("on") or parsed.get(True)
        assert isinstance(on_block, dict)
        assert "push" in on_block and "workflow_dispatch" in on_block
        assert parsed["permissions"] == {"contents": "write"}

    sbom_dict = SBOMGenerator.generate(Path(REPO_ROOT)).to_dict()
    ok, status_text, _ = SBOMVerifier.verify(sbom_dict)
    assert ok is True and status_text == "VERIFIED"

    docs_hub = REPO_ROOT / "website" / "src" / "components" / "docs" / "DocsHub.tsx"
    docs_src = docs_hub.read_text(encoding="utf-8")
    assert len(docs_src.splitlines()) < 500, "DocsHub.tsx must remain < 500 lines"
    for required_doc_token in (
        "Model Context Protocol",
        "2025-06-18",
        "Golden Benchmark",
        "KFlow",
        "KSpaces",
        "CycloneDX 1.5 SBOM",
        # KEEL-SEC-037: OIDC and SAML are disclosed separately — SAML is
        # explicitly documented as not yet implemented, so no "OIDC/SAML" token.
        "OIDC",
        "SAML",
        "SCIM 2.0",
        "Dual-Human P-10 Quorum",
        "OCSF",
        "CEF",
        "JSONL",
        "OpenTelemetry OTLP",
    ):
        assert required_doc_token in docs_src, f"Missing '{required_doc_token}' in DocsHub.tsx"
