"""
Phase 10B Tri-SDK KBrain Hybrid Memory, KHub Air-Gapped Skill Mirrors & Website Docs Sync Verification Suite.
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
    KeelwayError,
    PermissionDeniedError,
    SyncPlatformClient,
)

REPO_ROOT = Path(__file__).resolve().parent.parent

PHASE10_PYTHON_METHODS = (
    "record_kbrain_fact",
    "search_kbrain_facts",
    "resolve_kbrain_fact",
    "list_khub_skills",
    "verify_khub_mirror",
)

FORBIDDEN_PRIVATE_TOKENS = (
    "creova-gif",
    "creovas-projects",
    "kora.git",
    "KEEL-MANIFEST-",
    "KEEL-PLATFORM-",
    "KEEL-SEC-",
    "KEEL-GOV-",
    "KEEL-KBRAIN-",
    "verify_engineering_gates.sh",
    "Antigravity",
    "gstack",
)


def _make_phase10_mock_transport() -> Tuple[httpx.MockTransport, List[Dict[str, Any]]]:
    recorded: List[Dict[str, Any]] = []
    facts: Dict[str, Dict[str, Any]] = {}

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

        if request.headers.get("authorization") == "Bearer kw_live_viewer" and request.method == "POST":
            return httpx.Response(403, json={"detail": "Forbidden for viewer role"})

        if request.method == "POST" and path == "/v1/platform/kbrain/facts":
            if "sk-ant-leak" in body["statement"]:
                return httpx.Response(400, json={"detail": "DLP violation: secret pattern detected"})
            conflict_id = None
            for existing in facts.values():
                if (
                    existing["workspace_id"] == body["workspace_id"]
                    and existing["key"] == body["key"]
                    and existing["scope"] == body["scope"]
                    and existing["status"] in ("approved", "proposed")
                    and existing["statement"] != body["statement"]
                ):
                    conflict_id = existing["id"]
                    break
            fid = f"kb_py_{len(facts) + 1}"
            status = "conflict" if conflict_id else ("approved" if body["auto_approve"] else "proposed")
            rec = {
                "id": fid,
                "workspace_id": body["workspace_id"],
                "key": body["key"],
                "statement": body["statement"],
                "scope": body["scope"],
                "status": status,
                "conflict_with_fact_id": conflict_id,
                "provenance_uri": body["provenance_uri"],
                "tags": list(body.get("tags") or []),
                "created_by": "py-operator",
                "fact_sha256": "1" * 64,
                "created_at": "2026-11-15T00:00:00Z",
            }
            facts[fid] = rec
            return httpx.Response(200, json=rec)

        if request.method == "GET" and path == "/v1/platform/kbrain/search":
            ws_id = params.get("workspace_id", "default")
            q = params.get("query", "").lower()
            max_scope = params.get("max_scope", "org")
            include_conflicts = params.get("include_conflicts") == "true"
            limit = int(params.get("limit", "10"))
            matches = []
            for f in facts.values():
                if f["workspace_id"] != ws_id or f["status"] == "rejected":
                    continue
                if not include_conflicts and f["status"] == "conflict":
                    continue
                if q and q not in f["statement"].lower() and q not in f["key"].lower():
                    continue
                matches.append({**f, "score": 0.96, "bm25_score": 0.93, "ngram_score": 0.90})
            return httpx.Response(
                200,
                json={
                    "workspace_id": ws_id,
                    "query": params.get("query", ""),
                    "max_scope": max_scope,
                    "total_matches": len(matches[:limit]),
                    "results": matches[:limit],
                },
            )

        if request.method == "POST" and path.startswith("/v1/platform/kbrain/facts/") and path.endswith("/resolve"):
            fact_id = path[len("/v1/platform/kbrain/facts/") : -len("/resolve")]
            if fact_id not in facts:
                return httpx.Response(404, json={"detail": "Fact not found"})
            rec = facts[fact_id]
            rec["status"] = "approved" if body["resolution"] == "approve" else "rejected"
            rec["conflict_with_fact_id"] = None
            return httpx.Response(200, json=rec)

        if request.method == "GET" and path == "/v1/platform/khub/skills":
            return httpx.Response(
                200,
                json={
                    "workspace_id": params.get("workspace_id", "default"),
                    "total_skills": 2,
                    "air_gap_compliant": True,
                    "catalog_digest_sha256": "2" * 64,
                    "skills": [
                        {"id": "skill-ast", "name": "AST Profiler", "digest_sha256": "3" * 64},
                        {"id": "skill-sbom", "name": "SBOM Auditor", "digest_sha256": "4" * 64},
                    ],
                },
            )

        if request.method == "POST" and path == "/v1/platform/khub/mirror/verify":
            ids = body.get("skill_ids") or []
            return httpx.Response(
                200,
                json={
                    "workspace_id": body["workspace_id"],
                    "verified": True,
                    "mirror_format": "khub-skill-bundle-v1",
                    "skills_verified": len(ids) if ids else 2,
                    "catalog_digest_sha256": "2" * 64,
                    "verified_at": "2026-11-15T00:00:05Z",
                },
            )

        return httpx.Response(404, json={"detail": f"Unhandled {request.method} {path}"})

    return httpx.MockTransport(handler), recorded


def test_python_sync_sdk_phase10_kbrain_and_khub_mock_transport() -> None:
    for method_name in PHASE10_PYTHON_METHODS:
        sync_sig = inspect.signature(getattr(SyncPlatformClient, method_name))
        async_sig = inspect.signature(getattr(AsyncPlatformClient, method_name))
        assert list(sync_sig.parameters.values()) == list(async_sig.parameters.values())

    transport, recorded = _make_phase10_mock_transport()
    with KeelwayClient(token="kw_live_py10_sync", transport=transport) as client:
        with pytest.raises(ValueError, match="key"):
            client.platform.record_kbrain_fact("", "non-empty")
        with pytest.raises(ValueError, match="statement"):
            client.platform.record_kbrain_fact("valid.key", "   ")
        with pytest.raises(ValueError, match="fact_id"):
            client.platform.resolve_kbrain_fact("  ", "approve")

        f1 = client.platform.record_kbrain_fact(
            "storage.wal",
            "SQLite runs in WAL mode with foreign_keys=ON.",
            scope="project",
            provenance_uri="file://core/platform/kbrain_khub.py",
            tags=["sqlite", "wal"],
            auto_approve=True,
            workspace_id="ws-p10",
        )
        assert f1["status"] == "approved"
        assert len(f1["fact_sha256"]) == 64
        assert recorded[-1]["json"] == {
            "workspace_id": "ws-p10",
            "key": "storage.wal",
            "statement": "SQLite runs in WAL mode with foreign_keys=ON.",
            "scope": "project",
            "provenance_uri": "file://core/platform/kbrain_khub.py",
            "tags": ["sqlite", "wal"],
            "auto_approve": True,
        }

        with pytest.raises(KeelwayError, match="HTTP 400"):
            client.platform.record_kbrain_fact(
                "secret.leak",
                "Leaked sk-ant-leak-0123456789abcdef",
                workspace_id="ws-p10",
            )

        f2 = client.platform.record_kbrain_fact(
            "storage.wal",
            "SQLite runs in DELETE journal mode.",
            scope="project",
            workspace_id="ws-p10",
        )
        assert f2["status"] == "conflict"
        assert f2["conflict_with_fact_id"] == f1["id"]

        clean = client.platform.search_kbrain_facts(
            "SQLite",
            max_scope="org",
            include_conflicts=False,
            limit=5,
            workspace_id="ws-p10",
        )
        assert clean["total_matches"] == 1
        assert recorded[-1]["params"] == {
            "workspace_id": "ws-p10",
            "query": "SQLite",
            "max_scope": "org",
            "include_conflicts": "false",
            "limit": "5",
        }

        all_matches = client.platform.search_kbrain_facts(
            "SQLite",
            max_scope="org",
            include_conflicts=True,
            limit=5,
            workspace_id="ws-p10",
        )
        assert all_matches["total_matches"] == 2

        resolved = client.platform.resolve_kbrain_fact(
            f2["id"],
            resolution="reject",
            workspace_id="ws-p10",
        )
        assert resolved["status"] == "rejected"
        assert recorded[-1]["json"] == {"workspace_id": "ws-p10", "resolution": "reject"}

        skills = client.platform.list_khub_skills("ws-p10")
        assert skills["total_skills"] == 2
        assert skills["air_gap_compliant"] is True
        assert recorded[-1]["params"] == {"workspace_id": "ws-p10"}

        verified = client.platform.verify_khub_mirror(
            skill_ids=["skill-ast"],
            workspace_id="ws-p10",
        )
        assert verified["verified"] is True
        assert verified["skills_verified"] == 1
        assert recorded[-1]["json"] == {"workspace_id": "ws-p10", "skill_ids": ["skill-ast"]}

    viewer_transport, _ = _make_phase10_mock_transport()
    with KeelwayClient(token="kw_live_viewer", transport=viewer_transport) as viewer:
        with pytest.raises(PermissionDeniedError):
            viewer.platform.record_kbrain_fact("denied.key", "Viewer cannot mutate")


async def test_python_async_sdk_live_asgi_kbrain_khub_and_tri_sdk_symbols(tmp_path: Path) -> None:
    from httpx import ASGITransport

    from core.api.platform_kbrain_routes import get_kbrain_engine, get_khub_registry
    from core.api.platform_runtime_routes import get_rbac_controller
    from core.main import app
    from core.platform.kbrain_khub import SQLiteKBrainEngine, SQLiteKHubRegistry
    from core.platform.rbac_webhooks import WorkspaceRbacController
    from core.security.auth import launch_token

    db_file = tmp_path / "phase10_live_sdk.db"
    skills_dir = tmp_path / "skills"
    sample_skill = skills_dir / "sovereign-audit"
    sample_skill.mkdir(parents=True)
    (sample_skill / "SKILL.md").write_text(
        "# Sovereign Audit Skill\nOffline deterministic audit helper.\n",
        encoding="utf-8",
    )

    kbrain = SQLiteKBrainEngine(db_path=db_file)
    khub = SQLiteKHubRegistry(db_path=db_file, skills_dir=skills_dir)
    rbac = WorkspaceRbacController(db_path=db_file)
    app.dependency_overrides[get_kbrain_engine] = lambda: kbrain
    app.dependency_overrides[get_khub_registry] = lambda: khub
    app.dependency_overrides[get_rbac_controller] = lambda: rbac
    try:
        async with AsyncKeelwayClient(
            base_url="http://localhost",
            token=launch_token(),
            transport=ASGITransport(app=app),
        ) as client:
            f1 = await client.platform.record_kbrain_fact(
                "architecture.4k",
                "KBrain, KHub, KFlow, and KSpaces operate with zero mandatory cloud egress.",
                scope="project",
                provenance_uri="docs://architecture/4k",
                tags=["4k", "sovereign"],
                auto_approve=True,
                workspace_id="ws-live-10",
            )
            assert f1["workspace_id"] == "ws-live-10"
            assert f1["status"] == "approved"
            assert f1["fact_sha256"].startswith("sha256:")
            assert len(f1["fact_sha256"]) == 71

            with pytest.raises(KeelwayError, match="HTTP 400"):
                await client.platform.record_kbrain_fact(
                    "dlp.check",
                    "Never store sk-ant-0123456789abcdef0123456789 in facts.",
                    workspace_id="ws-live-10",
                )

            f2 = await client.platform.record_kbrain_fact(
                "architecture.4k",
                "KBrain requires an external cloud vector SaaS.",
                scope="project",
                workspace_id="ws-live-10",
            )
            assert f2["status"] == "conflict"
            assert f2["conflict_with_fact_id"] == f1["id"]

            clean_res = await client.platform.search_kbrain_facts(
                "zero mandatory cloud egress",
                max_scope="org",
                include_conflicts=False,
                limit=10,
                workspace_id="ws-live-10",
            )
            assert clean_res["total_matches"] == 1
            assert clean_res["results"][0]["id"] == f1["id"]

            conflict_res = await client.platform.search_kbrain_facts(
                "KBrain",
                max_scope="org",
                include_conflicts=True,
                limit=10,
                workspace_id="ws-live-10",
            )
            assert conflict_res["total_matches"] == 2

            rejected = await client.platform.resolve_kbrain_fact(
                f2["id"],
                resolution="reject",
                workspace_id="ws-live-10",
            )
            assert rejected["status"] == "rejected"

            skills = await client.platform.list_khub_skills("ws-live-10")
            assert skills["workspace_id"] == "ws-live-10"
            assert skills["total_skills"] == 1
            assert skills["air_gap_compliant"] is True
            assert skills["catalog_digest_sha256"].startswith("sha256:")
            assert len(skills["catalog_digest_sha256"]) == 71

            mirror = await client.platform.verify_khub_mirror(
                skill_ids=["sovereign-audit"],
                workspace_id="ws-live-10",
            )
            assert mirror["verified"] is True
            assert mirror["mirror_format"] == "khub-airgap-mirror-v1"
            assert mirror["skills_verified"] == 1
            assert mirror["catalog_digest_sha256"].startswith("sha256:")
            assert len(mirror["catalog_digest_sha256"]) == 71
    finally:
        app.dependency_overrides.pop(get_kbrain_engine, None)
        app.dependency_overrides.pop(get_khub_registry, None)
        app.dependency_overrides.pop(get_rbac_controller, None)
        kbrain.close()
        khub.close()
        rbac.close()

    ts_src = (REPO_ROOT / "sdk" / "typescript" / "src" / "platform.ts").read_text(encoding="utf-8")
    ts_kb = (REPO_ROOT / "sdk" / "typescript" / "src" / "platformKbrain.ts").read_text(encoding="utf-8")
    ts_dts = (REPO_ROOT / "sdk" / "typescript" / "dist" / "platform.d.ts").read_text(encoding="utf-8")
    for ts_method in (
        "recordKbrainFact",
        "searchKbrainFacts",
        "resolveKbrainFact",
        "listKhubSkills",
        "verifyKhubMirror",
    ):
        assert ts_method in ts_src and ts_method in ts_kb and ts_method in ts_dts

    go_src = (REPO_ROOT / "sdk" / "go" / "platform_phase10.go").read_text(encoding="utf-8")
    for go_method in (
        "RecordKBrainFact",
        "SearchKBrainFacts",
        "ResolveKBrainFact",
        "ListKHubSkills",
        "VerifyKHubMirror",
    ):
        assert f"func (p *PlatformService) {go_method}(" in go_src


def test_docs_hub_phase10_4k_sovereign_architecture_and_privacy() -> None:
    docs_hub = REPO_ROOT / "website" / "src" / "components" / "docs" / "DocsHub.tsx"
    docs_src = docs_hub.read_text(encoding="utf-8")
    line_count = len(docs_src.splitlines())
    assert line_count < 500, f"DocsHub.tsx has {line_count} lines (must remain < 500)"

    for required_token in (
        "4-K Sovereign Architecture",
        "KBrain",
        "BM25",
        "n-gram",
        "KHub",
        ".skill.tar.gz",
    ):
        assert required_token in docs_src, f"Missing '{required_token}' in DocsHub.tsx"

    for token in FORBIDDEN_PRIVATE_TOKENS:
        assert token not in docs_src, f"Forbidden private token '{token}' leaked in DocsHub.tsx"
