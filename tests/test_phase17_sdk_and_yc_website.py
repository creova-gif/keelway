"""
Phase 17B/17D & Integration Verification Suite — Tri-Language SDK Parity (`Python`, `TypeScript`, `Go`)
for Formal Safety State-Machine Verifier + Federated Edge-to-Cluster Agent Mesh, Module-Size Ratchets,
`298`-Route OpenAPI Sync, and Minimalist YC / Investor Public Website Curation (`KEEL-SAFETY-024`).
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path
from typing import Any, Dict, List
import uuid

import httpx
from httpx import ASGITransport
import pytest

from core.main import app
from core.sdk import (
    AsyncKeelwayClient,
    AsyncPlatformClient,
    KeelwayClient,
    KeelwayError,
    PermissionDeniedError,
    SyncPlatformClient,
)
from core.security.auth import launch_token

REPO_ROOT = Path(__file__).resolve().parent.parent
WEBSITE_DIR = REPO_ROOT / "website"

PHASE17_PYTHON_METHODS = (
    "verify_workflow_safety",
    "list_safety_verifications",
    "register_mesh_node",
    "list_mesh_nodes",
    "dispatch_mesh_handoff",
    "list_mesh_handoffs",
)

PHASE17_TS_METHODS = (
    "verifyWorkflowSafety",
    "listSafetyVerifications",
    "registerMeshNode",
    "listMeshNodes",
    "dispatchMeshHandoff",
    "listMeshHandoffs",
)

PHASE17_GO_METHODS = (
    "VerifyWorkflowSafety",
    "ListSafetyVerifications",
    "RegisterMeshNode",
    "ListMeshNodes",
    "DispatchMeshHandoff",
    "ListMeshHandoffs",
)

FORBIDDEN_PRIVATE_TOKENS = (
    "creova-gif",
    "creovas-projects",
    "keelway.git",
    "KEEL-",
    "verify_engineering_gates.sh",
    "Antigravity",
    "gstack",
)


def _make_sync_mock_transport() -> httpx.MockTransport:
    verifications_store: List[Dict[str, Any]] = []
    nodes_store: List[Dict[str, Any]] = []
    handoffs_store: List[Dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        raw = request.content.decode("utf-8") if request.content else ""
        body = json.loads(raw) if raw else {}
        path, params = request.url.path, dict(request.url.params)

        if path == "/v1/platform/safety/verify" and request.method == "POST":
            guarded = bool(body.get("inject_p10_guards"))
            rec = {
                "verification_id": f"sver-{len(verifications_store) + 1}",
                "workspace_id": body.get("workspace_id", "default"),
                "workflow_id": body.get("workflow_id", "WF-TREASURY-01"),
                "workflow_name": body.get("workflow_name", "treasury-wire-approver"),
                "status": "VERIFIED_SAFE" if guarded else "VIOLATION_FOUND",
                "states_explored": 3,
                "invariants_checked": [
                    {"invariant_id": "no_unguarded_destructive_tool", "passed": guarded, "description": "P-10 gate check"},
                ],
                "violations": []
                if guarded
                else [
                    {
                        "invariant_id": "no_unguarded_destructive_tool",
                        "severity": "CRITICAL",
                        "offending_node": "execute_wire_transfer",
                        "counterexample_path": ["ingest_invoice", "validate_vendor", "execute_wire_transfer"],
                        "remediation": "Require P-10 gate before external_transfer.",
                    }
                ],
                "p10_guards_injected": ["execute_wire_transfer"] if guarded else [],
                "dlp_redactions": 0,
                "proof_sha256": "sha256:" + ("a" * 64),
                "created_at": "2026-11-15T00:00:00+00:00",
            }
            verifications_store.append(rec)
            return httpx.Response(200, json=rec)

        if path == "/v1/platform/safety/verifications" and request.method == "GET":
            ws = params.get("workspace_id", "default")
            matched = [v for v in verifications_store if v["workspace_id"] == ws]
            return httpx.Response(200, json={"workspace_id": ws, "count": len(matched), "verifications": matched})

        if path == "/v1/platform/mesh/nodes" and request.method == "POST":
            node = {
                "node_id": body.get("node_id") or f"node-{len(nodes_store) + 1}",
                "workspace_id": body.get("workspace_id", "default"),
                "name": body["name"],
                "tier": body["tier"],
                "hardware_hal": body["hardware_hal"],
                "region": body.get("region", "local-loopback"),
                "vram_gb": body.get("vram_gb", 32),
                "status": body.get("status", "ONLINE"),
                "attestation_sha256": "sha256:" + ("b" * 64),
                "registered_at": "2026-11-15T00:00:00+00:00",
            }
            nodes_store.append(node)
            return httpx.Response(200, json=node)

        if path == "/v1/platform/mesh/nodes" and request.method == "GET":
            ws = params.get("workspace_id", "default")
            matched = [n for n in nodes_store if n["workspace_id"] == ws]
            return httpx.Response(200, json={"workspace_id": ws, "count": len(matched), "nodes": matched})

        if path == "/v1/platform/mesh/dispatch" and request.method == "POST":
            if body.get("force_raw_cloud_burst") and body.get("data_classification") == "restricted_pii":
                return httpx.Response(422, json={"detail": "Sovereignty violation", "code": "mesh_sovereignty_violation"})
            burst = bool(body.get("allow_sanitized_burst", True))
            handoff = {
                "handoff_id": f"mhnd-{len(handoffs_store) + 1}",
                "workspace_id": body.get("workspace_id", "default"),
                "workflow_name": body.get("workflow_name", "clinical-synthesis-pipeline"),
                "data_classification": body.get("data_classification", "restricted_pii"),
                "status": "ATTESTED_COMPLETE" if burst else "PINNED_EDGE_ONLY",
                "edge_node_id": "edge-mac-m3-max",
                "burst_node_id": "cluster-h100-us-east" if burst else None,
                "stages": [],
                "total_cost_usd": 0.0042 if burst else 0.0,
                "dlp_redactions": 0,
                "attestation_sha256": "sha256:" + ("c" * 64),
                "created_at": "2026-11-15T00:00:00+00:00",
            }
            handoffs_store.append(handoff)
            return httpx.Response(200, json=handoff)

        if path == "/v1/platform/mesh/handoffs" and request.method == "GET":
            ws = params.get("workspace_id", "default")
            matched = [h for h in handoffs_store if h["workspace_id"] == ws]
            return httpx.Response(200, json={"workspace_id": ws, "count": len(matched), "handoffs": matched})

        return httpx.Response(404, json={"detail": f"Unhandled mock route {request.method} {path}"})

    return httpx.MockTransport(handler)


def test_python_sdk_phase17_sync_async_signature_and_mock_parity() -> None:
    for method_name in PHASE17_PYTHON_METHODS:
        sync_fn = getattr(SyncPlatformClient, method_name, None)
        async_fn = getattr(AsyncPlatformClient, method_name, None)
        assert callable(sync_fn), f"Missing SyncPlatformClient.{method_name}"
        assert callable(async_fn), f"Missing AsyncPlatformClient.{method_name}"
        assert inspect.iscoroutinefunction(async_fn)
        assert list(inspect.signature(sync_fn).parameters.keys()) == list(inspect.signature(async_fn).parameters.keys())

    with KeelwayClient(base_url="http://127.0.0.1:7420", token="test-token", transport=_make_sync_mock_transport()) as client:
        viol = client.platform.verify_workflow_safety(workspace_id="ws-p17")
        assert viol["status"] == "VIOLATION_FOUND" and len(viol["violations"]) == 1

        safe = client.platform.verify_workflow_safety(workspace_id="ws-p17", inject_p10_guards=True)
        assert safe["status"] == "VERIFIED_SAFE" and "execute_wire_transfer" in safe["p10_guards_injected"]

        listed_ver = client.platform.list_safety_verifications(workspace_id="ws-p17")
        assert listed_ver["count"] == 2

        reg = client.platform.register_mesh_node("Mac Studio M3 Max", tier="edge_local", workspace_id="ws-p17", vram_gb=64)
        assert reg["tier"] == "edge_local" and reg["attestation_sha256"].startswith("sha256:")

        nodes = client.platform.list_mesh_nodes(workspace_id="ws-p17")
        assert nodes["count"] == 1

        handoff = client.platform.dispatch_mesh_handoff(workspace_id="ws-p17", allow_sanitized_burst=True)
        assert handoff["status"] == "ATTESTED_COMPLETE" and handoff["total_cost_usd"] == 0.0042

        pinned = client.platform.dispatch_mesh_handoff(workspace_id="ws-p17", allow_sanitized_burst=False)
        assert pinned["status"] == "PINNED_EDGE_ONLY" and pinned["total_cost_usd"] == 0.0

        handoffs = client.platform.list_mesh_handoffs(workspace_id="ws-p17")
        assert handoffs["count"] == 2

        with pytest.raises(KeelwayError):
            client.platform.dispatch_mesh_handoff(
                workspace_id="ws-p17",
                data_classification="restricted_pii",
                force_raw_cloud_burst=True,
            )


@pytest.mark.asyncio
async def test_python_async_sdk_live_asgi_safety_verifier_and_edge_mesh() -> None:
    ws_id = f"ws-p17-asgi-{uuid.uuid4().hex[:8]}"
    token = launch_token()

    async with AsyncKeelwayClient(base_url="http://127.0.0.1:7420", token=token, transport=ASGITransport(app=app)) as client:
        viol = await client.platform.verify_workflow_safety(workspace_id=ws_id)
        assert viol["status"] == "VIOLATION_FOUND"
        assert len(viol["invariants_checked"]) == 4

        safe = await client.platform.verify_workflow_safety(workspace_id=ws_id, inject_p10_guards=True)
        assert safe["status"] == "VERIFIED_SAFE"
        assert safe["proof_sha256"].startswith("sha256:")

        ver_list = await client.platform.list_safety_verifications(workspace_id=ws_id)
        assert ver_list["count"] >= 2

        seeded_nodes = await client.platform.list_mesh_nodes(workspace_id=ws_id)
        assert seeded_nodes["count"] >= 2

        custom_node = await client.platform.register_mesh_node(
            "Linux TPM2 Workstation",
            tier="edge_local",
            hardware_hal="linux_tpm2",
            workspace_id=ws_id,
            vram_gb=48,
        )
        assert custom_node["hardware_hal"] == "linux_tpm2"

        attested = await client.platform.dispatch_mesh_handoff(
            workspace_id=ws_id,
            task_summary="Scrub intake token sk-live-1234567890abcdef and summarize",
            data_classification="restricted_pii",
            allow_sanitized_burst=True,
        )
        assert attested["status"] == "ATTESTED_COMPLETE"
        assert attested["dlp_redactions"] >= 1
        assert all(s["zero_raw_pii_egress"] is True for s in attested["stages"])

        with pytest.raises(KeelwayError):
            await client.platform.dispatch_mesh_handoff(
                workspace_id=ws_id,
                data_classification="restricted_pii",
                force_raw_cloud_burst=True,
            )

        handoff_list = await client.platform.list_mesh_handoffs(workspace_id=ws_id)
        assert handoff_list["count"] >= 1

    async with AsyncKeelwayClient(base_url="http://127.0.0.1:7420", token=token, transport=ASGITransport(app=app)) as auditor_client:
        http_attr = getattr(auditor_client, "_http", None) or auditor_client._client
        http_attr.headers["X-Keelway-Role"] = "auditor"
        http_attr.headers["X-Keelway-Actor"] = "auditor-actor"
        read_nodes = await auditor_client.platform.list_mesh_nodes(workspace_id=ws_id)
        assert read_nodes["count"] >= 2
        with pytest.raises(PermissionDeniedError):
            await auditor_client.platform.verify_workflow_safety(workspace_id=ws_id)
        with pytest.raises(PermissionDeniedError):
            await auditor_client.platform.dispatch_mesh_handoff(workspace_id=ws_id)


def test_tri_sdk_caps_298_routes_and_yc_minimal_website_curation() -> None:
    new_phase17_files = (
        REPO_ROOT / "core" / "platform" / "safety_and_mesh.py",
        REPO_ROOT / "core" / "api" / "platform_safety_mesh_routes.py",
        REPO_ROOT / "core" / "cli_safety_mesh.py",
        REPO_ROOT / "core" / "sdk" / "platform_safety_mesh_client.py",
        REPO_ROOT / "sdk" / "typescript" / "src" / "platformSafetyMesh.ts",
        REPO_ROOT / "sdk" / "go" / "platform_phase17.go",
        REPO_ROOT / "dev-app" / "src" / "lib" / "platformSafetyMeshApi.ts",
        REPO_ROOT / "dev-app" / "src" / "components" / "platform" / "FormalSafetyAndEdgeMeshPanel.tsx",
    )
    for fpath in new_phase17_files:
        assert fpath.exists(), f"Expected Phase 17 module {fpath}"
        lines = fpath.read_text(encoding="utf-8").splitlines()
        assert len(lines) < 480, f"{fpath} exceeds 480-line cap ({len(lines)} lines)"

    for shared_sdk_file in (
        REPO_ROOT / "core" / "sdk" / "platform_runtime_client.py",
        REPO_ROOT / "sdk" / "typescript" / "src" / "platform.ts",
        REPO_ROOT / "sdk" / "typescript" / "src" / "index.ts",
    ):
        assert len(shared_sdk_file.read_text(encoding="utf-8").splitlines()) < 700

    ts_src = (REPO_ROOT / "sdk" / "typescript" / "src" / "platformSafetyMesh.ts").read_text(encoding="utf-8")
    go_src = (REPO_ROOT / "sdk" / "go" / "platform_phase17.go").read_text(encoding="utf-8")
    for ts_m in PHASE17_TS_METHODS:
        assert ts_m in ts_src, f"Missing TypeScript SDK method {ts_m}"
    for go_m in PHASE17_GO_METHODS:
        assert f"func (p *PlatformService) {go_m}(" in go_src, f"Missing Go SDK method {go_m}"

    openapi_raw = (WEBSITE_DIR / "openapi.json").read_text(encoding="utf-8")
    pub_openapi_raw = (WEBSITE_DIR / "public" / "openapi.json").read_text(encoding="utf-8")
    assert openapi_raw == pub_openapi_raw
    openapi_doc = json.loads(openapi_raw)
    assert len(openapi_doc["paths"]) >= 298
    assert len(app.openapi()["paths"]) >= 298
    for route in (
        "/v1/platform/safety/verify",
        "/v1/platform/safety/verifications",
        "/v1/platform/mesh/nodes",
        "/v1/platform/mesh/dispatch",
        "/v1/platform/mesh/handoffs",
    ):
        assert route in openapi_doc["paths"], f"Missing OpenAPI route {route}"

    # Verify YC / Investor Minimalist Public Website Curation (Workstream 17D)
    # KEEL-WEB-038: the v3 "Maritime Instrument" rebuild pruned the public route
    # surface to /, /about, /product, /pricing, /changelog, /contact, /docs,
    # /sign-in. Retired pages (DocsHub, /governance, /models, /api-reference,
    # /marketplace, /brand, /playground, /search) must stay absent; the
    # no-internal-jargon / no-private-token scan binds to the live v3 surface.
    home_src = (WEBSITE_DIR / "src" / "app" / "page.tsx").read_text(encoding="utf-8")
    v3_surface_files = (
        WEBSITE_DIR / "src" / "app" / "page.tsx",
        WEBSITE_DIR / "src" / "app" / "about" / "page.tsx",
        WEBSITE_DIR / "src" / "app" / "product" / "page.tsx",
        WEBSITE_DIR / "src" / "app" / "pricing" / "page.tsx",
        WEBSITE_DIR / "src" / "app" / "changelog" / "page.tsx",
        WEBSITE_DIR / "src" / "app" / "contact" / "page.tsx",
        WEBSITE_DIR / "src" / "app" / "docs" / "page.tsx",
        WEBSITE_DIR / "src" / "app" / "sign-in" / "page.tsx",
    )

    assert len(home_src.splitlines()) < 220, "Homepage should remain concise and YC-focused (< 220 lines)"
    assert "RecordedDemosShowcase" not in home_src, "Redundant RecordedDemosShowcase should be removed from homepage"
    for yc_signal in ("ControlPlaneFigure", "#install", '"/product"'):
        assert yc_signal in home_src, f"Missing investor signal {yc_signal} on homepage"

    docs_src = (WEBSITE_DIR / "src" / "app" / "docs" / "page.tsx").read_text(encoding="utf-8")
    assert len(docs_src.splitlines()) < 350, "docs index must stay concise (< 350 lines)"

    for retired in (
        "src/components/docs/DocsHub.tsx",
        "src/components/home/CustomerJourneyGrid.tsx",
        "src/app/governance/page.tsx",
        "src/app/models/page.tsx",
        "src/app/api-reference/page.tsx",
        "src/app/marketplace/page.tsx",
        "src/app/brand/page.tsx",
        "src/app/playground/page.tsx",
    ):
        assert not (WEBSITE_DIR / retired).exists(), f"Retired v1 surface still present: {retired}"

    # The /api-reference page is gone; the OpenAPI contract must still expose
    # the public chat + governance route families it documented.
    assert any("/v1/chat/" in p for p in openapi_doc["paths"]), "Public /v1/chat/* routes missing from openapi.json"
    assert any("/v1/governance" in p for p in openapi_doc["paths"]), "Public /v1/governance* routes missing from openapi.json"

    for surface_file in v3_surface_files:
        web_text = surface_file.read_text(encoding="utf-8")
        assert '"/playground' not in web_text
        assert "allowed_providers" not in web_text, "Internal Python config syntax leaked into public site"
        assert "LAYER 4 REGISTRY" not in web_text, "Internal layer jargon leaked into public site"
        for tok in FORBIDDEN_PRIVATE_TOKENS:
            assert tok not in web_text, f"Forbidden token '{tok}' leaked in curated website source"
