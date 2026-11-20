"""
Phase 21 Tri-SDK KStack Execute & Agent Manifest Registry Parity Verification Suite.
"""

from __future__ import annotations

import asyncio
import inspect
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

import httpx
import pytest

from core.sdk import AsyncKeelwayClient, KeelwayClient

REPO_ROOT = Path(__file__).resolve().parent.parent

PHASE21_PYTHON_METHODS = (
    "kstack_execute",
    "list_agent_registry",
    "toggle_agent_manifest",
)


def _make_phase21_mock_transport() -> Tuple[httpx.MockTransport, List[Dict[str, Any]]]:
    recorded: List[Dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        raw = request.content.decode("utf-8") if request.content else ""
        body = json.loads(raw) if raw else None
        path = request.url.path
        recorded.append(
            {
                "method": request.method,
                "path": path,
                "params": dict(request.url.params),
                "headers": dict(request.headers),
                "json": body,
            }
        )

        if request.method == "POST" and path == "/v1/kstack/execute":
            if body["name"] == "kstack/nope":
                return httpx.Response(404, json={"detail": "Skill 'kstack/nope' not found"})
            return httpx.Response(
                200,
                json={
                    "proof": {
                        "execution_id": "exec-py-1",
                        "skill_name": body["name"],
                        "skill_digest_sha256": "a" * 64,
                        "actor": "py-client",
                        "inputs": body["inputs"],
                        "outputs": {"pass_rate_pct": 90.0},
                        "permissions_used": ["execute_restricted"],
                        "success": True,
                        "duration_ms": 11.0,
                        "timestamp_utc": "2026-11-19T00:00:00Z",
                        "signature_sha256": "b" * 64,
                    }
                },
            )
        if request.method == "GET" and path == "/v1/agents/registry":
            return httpx.Response(
                200,
                json={
                    "manifests": [
                        {
                            "id": 1,
                            "name": "devops-sre",
                            "version": "1.0.0",
                            "owner": "system",
                            "digest": "d1",
                            "enabled": True,
                            "created_at": "2026-11-19T00:00:00Z",
                            "updated_at": "2026-11-19T00:00:00Z",
                        }
                    ]
                },
            )
        if request.method == "POST" and path == "/v1/agents/registry/devops-sre/1.0.0/toggle":
            return httpx.Response(
                200, json={"id": 1, "enabled": body["enabled"], "updated_at": "2026-11-19T00:00:00Z"}
            )
        return httpx.Response(404, json={"detail": "not found"})

    return httpx.MockTransport(handler), recorded


def test_python_sync_sdk_phase21_kstack_and_registry_mock_transport() -> None:
    for method_name in PHASE21_PYTHON_METHODS:
        sync_sig = inspect.signature(getattr(KeelwayClient, method_name))
        async_sig = inspect.signature(getattr(AsyncKeelwayClient, method_name))
        assert list(sync_sig.parameters.values()) == list(async_sig.parameters.values())

    transport, recorded = _make_phase21_mock_transport()
    with KeelwayClient(token="kw_live_py21_sync", transport=transport) as client:
        proof = client.kstack_execute(
            "kstack/golden-eval", inputs={"model_name": "m1", "compare_to": "latest"}
        )
        assert proof["success"] is True
        assert proof["skill_name"] == "kstack/golden-eval"
        assert recorded[-1]["json"] == {
            "name": "kstack/golden-eval",
            "inputs": {"model_name": "m1", "compare_to": "latest"},
        }
        assert recorded[-1]["headers"]["authorization"] == "Bearer kw_live_py21_sync"

        # inputs defaults to {} — never omitted from the wire body
        client.kstack_execute("kstack/sbom-audit")
        assert recorded[-1]["json"] == {"name": "kstack/sbom-audit", "inputs": {}}

        registry = client.list_agent_registry()
        assert registry["manifests"][0]["name"] == "devops-sre"
        assert recorded[-1]["method"] == "GET"

        toggled = client.toggle_agent_manifest("devops-sre", "1.0.0", False)
        assert toggled["enabled"] is False
        assert recorded[-1]["path"] == "/v1/agents/registry/devops-sre/1.0.0/toggle"
        assert recorded[-1]["json"] == {"enabled": False}


def test_python_async_sdk_live_asgi_kstack_execute_and_registry() -> None:
    from httpx import ASGITransport

    from core.main import app
    from core.security.auth import launch_token

    async def _run() -> None:
        async with AsyncKeelwayClient(
            base_url="http://localhost",
            token=launch_token(),
            transport=ASGITransport(app=app),
        ) as client:
            proof = await client.kstack_execute(
                "kstack/golden-eval", inputs={"save_receipt": False}
            )
            assert proof["success"] is True
            assert proof["outputs"]["total_tasks"] == 10
            assert proof["signature_sha256"]

            registry = await client.list_agent_registry()
            assert isinstance(registry["manifests"], list)

            from core.sdk import KeelwayError

            with pytest.raises(KeelwayError):
                await client.kstack_execute("kstack/definitely-not-a-skill")

    asyncio.run(_run())


def test_phase21_ts_and_go_sdk_source_symbols() -> None:
    ts_client = (REPO_ROOT / "sdk" / "typescript" / "src" / "client.ts").read_text(encoding="utf-8")
    ts_types = (REPO_ROOT / "sdk" / "typescript" / "src" / "types.ts").read_text(encoding="utf-8")
    ts_dts = (REPO_ROOT / "sdk" / "typescript" / "dist" / "client.d.ts").read_text(encoding="utf-8")
    ts_dts_types = (REPO_ROOT / "sdk" / "typescript" / "dist" / "types.d.ts").read_text(
        encoding="utf-8"
    )

    for symbol in ("kstack", "agents", "listRegistry", "toggleManifest"):
        assert symbol in ts_client
    for symbol in ("KStackExecuteRequest", "SkillExecutionProof", "AgentRegistryRecord"):
        assert symbol in ts_types
    for symbol in ("kstack", "agents", "listRegistry", "toggleManifest"):
        assert symbol in ts_dts
    for symbol in ("KStackExecuteRequest", "SkillExecutionProof", "AgentRegistryRecord"):
        assert symbol in ts_dts_types

    go_kstack = (REPO_ROOT / "sdk" / "go" / "kstack.go").read_text(encoding="utf-8")
    go_registry = (REPO_ROOT / "sdk" / "go" / "agents_registry.go").read_text(encoding="utf-8")
    go_client = (REPO_ROOT / "sdk" / "go" / "client.go").read_text(encoding="utf-8")

    for symbol in ("KStackService", "Execute", "KStackExecuteRequest", "SkillExecutionProof"):
        assert symbol in go_kstack
    for symbol in ("AgentsService", "ListRegistry", "ToggleManifest", "AgentRegistryRecord"):
        assert symbol in go_registry
    for symbol in ("KStack", "Agents"):
        assert symbol in go_client
