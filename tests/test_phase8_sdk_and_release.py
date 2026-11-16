"""
Phase 8B Tri-SDK Parity, Container/CI Release Hardening & v1.0.0 Documentation Verification Suite.
"""

from __future__ import annotations

import inspect
import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Tuple

import httpx
import pytest

from core.sdk import (
    AsyncKeelwayClient,
    AsyncPlatformClient,
    KeelwayClient,
    KeelwayError,
    PermissionDeniedError,
    SyncPlatformClient,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_yaml_if_available(path: Path) -> Any:
    raw = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError:
        return None
    return yaml.safe_load(raw)


def _make_phase8_mock_transport() -> Tuple[httpx.MockTransport, List[Dict[str, Any]]]:
    recorded: List[Dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        raw = request.content.decode("utf-8") if request.content else ""
        body = json.loads(raw) if raw else None
        path, params = request.url.path, dict(request.url.params)
        recorded.append({"method": request.method, "path": path, "params": params, "headers": dict(request.headers), "json": body})

        if request.method == "POST" and path == "/v1/platform/automation/workflows/execute":
            if request.headers.get("authorization") == "Bearer kw_live_viewer":
                return httpx.Response(403, json={"detail": "Forbidden for viewer role"})
            if body["workflow_id"] == "WF-CYCLE":
                return httpx.Response(400, json={"detail": "Cycle detected in KFlow DAG"})
            approved = set(body.get("approved_node_ids") or [])
            nodes = body.get("nodes") or []
            gated = next((n["id"] for n in nodes if n.get("requires_p10") and n["id"] not in approved), None)
            return httpx.Response(
                200,
                json={
                    "run_id": "kflow-py-01",
                    "workspace_id": body["workspace_id"],
                    "workflow_id": body["workflow_id"],
                    "trigger": body["trigger"],
                    "status": "awaiting_p10" if gated else "completed",
                    "held_node_id": gated,
                    "topological_order": [n["id"] for n in nodes],
                    "token_budget": body["token_budget"],
                    "receipt_sha256": "sha256:" + "a" * 64,
                },
            )

        if request.method == "GET" and path == "/v1/platform/automation/runs":
            return httpx.Response(
                200,
                json={
                    "workspace_id": params.get("workspace_id", "default"),
                    "count": 1,
                    "runs": [{"run_id": "kflow-py-01", "workflow_id": params.get("workflow_id") or "WF-01", "status": "completed"}],
                },
            )

        if request.method == "POST" and path == "/v1/platform/kspaces/sync":
            ops = body.get("operations") or []
            return httpx.Response(
                200,
                json={
                    "workspace_id": body["workspace_id"],
                    "peer_id": body["peer_id"],
                    "applied_count": len(ops),
                    "active_keys_count": len(ops),
                    "state_digest_sha256": "sha256:" + "b" * 64,
                    "entries": [],
                },
            )

        if request.method == "GET" and path == "/v1/platform/kspaces/state":
            ns = params.get("namespace") or "workspace"
            return httpx.Response(
                200,
                json={
                    "workspace_id": params.get("workspace_id", "default"),
                    "active_keys_count": 1,
                    "state_digest_sha256": "sha256:" + "b" * 64,
                    "entries": [{"namespace": ns, "key": "active_doc", "value": "README.md", "lamport_ts": 11, "peer_id": "p1", "tombstone": False}],
                },
            )

        if request.method == "GET" and path == "/v1/platform/security/sbom":
            return httpx.Response(
                200,
                json={
                    "workspace_id": params.get("workspace_id", "default"),
                    "verified": True,
                    "verification_status": "VERIFIED",
                    "bom_format": "CycloneDX",
                    "spec_version": "1.5",
                    "component_count": 2,
                    "root_digest_sha256": "c" * 64,
                    "provenance_signature": "d" * 64,
                },
            )

        return httpx.Response(404, json={"detail": f"Unhandled {request.method} {path}"})

    return httpx.MockTransport(handler), recorded


def test_python_sync_sdk_phase8_kflow_kspaces_and_sbom_parity() -> None:
    for name in ("execute_kflow_dag", "list_kflow_runs", "sync_kspaces_crdt", "get_kspaces_state", "get_platform_sbom"):
        sync_sig = inspect.signature(getattr(SyncPlatformClient, name))
        async_sig = inspect.signature(getattr(AsyncPlatformClient, name))
        assert list(sync_sig.parameters.values()) == list(async_sig.parameters.values())

    transport, recorded = _make_phase8_mock_transport()
    with KeelwayClient(token="kw_live_py8_sync", transport=transport) as client:
        nodes = [
            {"id": "lint", "kind": "agent"},
            {"id": "prod_gate", "kind": "p10_gate", "depends_on": ["lint"], "requires_p10": True},
        ]
        gated = client.platform.execute_kflow_dag("WF-01", nodes=nodes, workspace_id="ws-p8")
        assert gated["status"] == "awaiting_p10"
        assert gated["held_node_id"] == "prod_gate"
        assert recorded[-1]["json"] == {
            "workspace_id": "ws-p8",
            "workflow_id": "WF-01",
            "nodes": nodes,
            "trigger": "manual",
            "token_budget": 25000,
            "approved_node_ids": [],
        }

        resumed = client.platform.execute_kflow_dag(
            "WF-01", nodes=nodes, trigger="webhook", token_budget=4096, approved_node_ids=["prod_gate"], workspace_id="ws-p8"
        )
        assert resumed["status"] == "completed"

        with pytest.raises(KeelwayError):
            client.platform.execute_kflow_dag("WF-CYCLE", nodes=[{"id": "x", "depends_on": ["x"]}])

        runs = client.platform.list_kflow_runs(workspace_id="ws-p8", workflow_id="WF-01", limit=5)
        assert runs["count"] == 1
        assert recorded[-1]["params"] == {"workspace_id": "ws-p8", "workflow_id": "WF-01", "limit": "5"}

        sync_res = client.platform.sync_kspaces_crdt(
            "peer-sync-01",
            [{"namespace": "editor", "key": "active_doc", "value": "README.md", "lamport_ts": 11}],
            workspace_id="ws-p8",
        )
        assert sync_res["applied_count"] == 1

        state = client.platform.get_kspaces_state(workspace_id="ws-p8", namespace="editor")
        assert state["entries"][0]["value"] == "README.md"
        assert recorded[-1]["params"] == {"workspace_id": "ws-p8", "namespace": "editor"}

        sbom = client.platform.get_platform_sbom("ws-p8")
        assert sbom["verified"] is True
        assert sbom["bom_format"] == "CycloneDX"


async def test_python_async_sdk_live_asgi_and_tri_sdk_symbol_parity(tmp_path: Path) -> None:
    from httpx import ASGITransport

    from core.api.platform_kflow_routes import get_kflow_engine, get_kspaces_crdt_engine
    from core.api.platform_runtime_routes import get_rbac_controller
    from core.main import app
    from core.platform.kflow_crdt import KFlowDagEngine, KSpacesCrdtEngine
    from core.platform.rbac_webhooks import WorkspaceRbacController
    from core.security.auth import launch_token

    viewer_transport, _ = _make_phase8_mock_transport()
    async with AsyncKeelwayClient(token="kw_live_viewer", transport=viewer_transport) as viewer:
        with pytest.raises(PermissionDeniedError):
            await viewer.platform.execute_kflow_dag("WF-DENY", nodes=[{"id": "n1"}])

    db_file = tmp_path / "phase8_live_sdk.db"
    kflow = KFlowDagEngine(db_path=db_file)
    crdt = KSpacesCrdtEngine(db_path=db_file)
    rbac = WorkspaceRbacController(db_path=db_file)
    app.dependency_overrides[get_kflow_engine] = lambda: kflow
    app.dependency_overrides[get_kspaces_crdt_engine] = lambda: crdt
    app.dependency_overrides[get_rbac_controller] = lambda: rbac
    try:
        async with AsyncKeelwayClient(
            base_url="http://localhost", token=launch_token(), transport=ASGITransport(app=app)
        ) as client:
            nodes = [
                {"id": "scan", "label": "Security Scan"},
                {"id": "gate", "label": "Prod Gate", "depends_on": ["scan"], "requires_p10": True},
            ]
            held = await client.platform.execute_kflow_dag("WF-LIVE", nodes=nodes, workspace_id="ws-live")
            assert held["status"] == "awaiting_p10"
            assert held["held_node_id"] == "gate"

            done = await client.platform.execute_kflow_dag(
                "WF-LIVE", nodes=nodes, approved_node_ids=["gate"], workspace_id="ws-live"
            )
            assert done["status"] == "completed"

            runs = await client.platform.list_kflow_runs(workspace_id="ws-live", workflow_id="WF-LIVE", limit=2)
            assert runs["count"] == 2

            synced = await client.platform.sync_kspaces_crdt(
                "peer-live", [{"namespace": "presence", "key": "u1", "value": "online", "lamport_ts": 5}], workspace_id="ws-live"
            )
            assert synced["applied_count"] == 1
            assert synced["active_keys_count"] == 1

            state = await client.platform.get_kspaces_state(workspace_id="ws-live", namespace="presence")
            assert state["entries"][0]["value"] == "online"

            sbom = await client.platform.get_platform_sbom("ws-live")
            assert sbom["verified"] is True
            assert sbom["verification_status"] == "VERIFIED"
            assert sbom["bom_format"] == "CycloneDX"
    finally:
        app.dependency_overrides.pop(get_kflow_engine, None)
        app.dependency_overrides.pop(get_kspaces_crdt_engine, None)
        app.dependency_overrides.pop(get_rbac_controller, None)
        kflow.close()
        crdt.close()
        rbac.close()

    ts_src = (REPO_ROOT / "sdk" / "typescript" / "src" / "platform.ts").read_text(encoding="utf-8")
    ts_dts = (REPO_ROOT / "sdk" / "typescript" / "dist" / "platform.d.ts").read_text(encoding="utf-8")
    for ts_method in ("executeKflowDag", "listKflowRuns", "syncKspacesCrdt", "getKspacesState", "getPlatformSbom"):
        assert ts_method in ts_src and ts_method in ts_dts

    go_src = (REPO_ROOT / "sdk" / "go" / "platform_phase8.go").read_text(encoding="utf-8")
    for go_method in ("ExecuteKflowDag", "ListKflowRuns", "SyncKspacesCrdt", "GetKspacesState", "GetPlatformSbom"):
        assert f"func (p *PlatformService) {go_method}(" in go_src


def test_dockerfile_compose_and_github_actions_release_hardening() -> None:
    dockerfile = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")
    for required in (
        "README.md",
        "cli.py",
        "COPY core core/",
        "COPY keelway keelway/",
        "COPY research research/",
        "COPY evaluations evaluations/",
        "chown -R 10001:10001 /app /data",
        "HOME=/data",
        "KEELWAY_STATE_DIR=/data/.keelway",
        "KEELWAY_DB_PATH=/data/keelway_audit.db",
        'VOLUME ["/data"]',
        "EXPOSE 7420 8000",
        "USER 10001:10001",
    ):
        assert required in dockerfile, f"Missing '{required}' in Dockerfile"

    compose_path = REPO_ROOT / "docker-compose.yml"
    compose_raw = compose_path.read_text(encoding="utf-8")
    assert not compose_raw.lstrip().startswith("version:")
    for svc in ("keelway-control-plane:", "keelway-platform:", "keelway-runner:", "ollama:", "7420:7420", "8000:8000"):
        assert svc in compose_raw
    parsed_compose = _load_yaml_if_available(compose_path)
    if parsed_compose is not None:
        assert "version" not in parsed_compose
        assert {"keelway-control-plane", "keelway-platform", "keelway-runner", "ollama"} <= set(parsed_compose["services"])

    ci_path = REPO_ROOT / ".github" / "workflows" / "ci.yml"
    ci_raw = ci_path.read_text(encoding="utf-8")
    assert "python -m tests.release_live_gate" not in ci_raw
    for required in (
        "website-devapp-and-sdks:",
        "wheel-and-sbom-verification:",
        'node-version: "22"',
        'go-version: "1.23"',
        "npm --prefix sdk/typescript test",
        "go test ./... -race",
        "npm --prefix dev-app test",
        "python -m build --wheel --outdir dist/",
        "/tmp/wheel-venv/bin/keelway eval-suite --category all --json",
        "SBOMGenerator",
        "SBOMVerifier",
    ):
        assert required in ci_raw

    macos_raw = (REPO_ROOT / ".github" / "workflows" / "release-gate-macos.yml").read_text(encoding="utf-8")
    assert "runs-on: macos-latest" in macos_raw
    assert "python -m tests.release_live_gate" in macos_raw

    deploy_raw = (REPO_ROOT / ".github" / "workflows" / "deploy.yml").read_text(encoding="utf-8")
    assert "docker run --rm" not in deploy_raw
    for required in (
        "KEELWAY_POLICY_SIGNING_KEY=",
        "docker logs test-keelway",
        "curl -fsS http://127.0.0.1:8000/",
        "docker exec test-keelway keelway eval-suite --category all --json",
        "docker rm -f test-keelway",
    ):
        assert required in deploy_raw


def test_public_install_sh_dry_run_and_v1_docs_integrity(tmp_path: Path) -> None:
    pub_install = REPO_ROOT / "website" / "public" / "install.sh"
    assert subprocess.run(["sh", "-n", str(pub_install)], capture_output=True, text=True, check=False).returncode == 0

    help_res = subprocess.run(["sh", str(pub_install), "--help"], capture_output=True, text=True, check=False)
    assert help_res.returncode == 0 and "--dry-run" in help_res.stdout and "--help" in help_res.stdout

    target_runtime, target_bin = tmp_path / "keelway-runtime", tmp_path / "keelway-bin"
    dry_res = subprocess.run(
        ["sh", str(pub_install), "--dry-run", "--install-dir", str(target_runtime), "--bin-dir", str(target_bin)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert dry_res.returncode == 0, dry_res.stderr
    assert "[dry-run]" in dry_res.stdout
    assert not target_runtime.exists() and not target_bin.exists()

    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    changelog = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    # KEEL-DOC-034 errata: README tracks v1.1.0; the P-10 gate is implemented
    # in code (specs/tla/P10HumanGate.tla was never committed — do not re-assert it).
    for token in ("v1.1.0", "127.0.0.1:7420/app", "@keelway/sdk", "keelway-go", "P-10", "eval-suite"):
        assert token in readme
    assert "P10HumanGate.tla" not in readme
    assert "## [1.1.0]" in changelog and "## [1.0.0]" in changelog and "CycloneDX" in changelog and "KFlow" in changelog
