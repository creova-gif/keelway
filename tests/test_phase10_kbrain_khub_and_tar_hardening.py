"""
Phase 10A Verification Suite — KBrain Hybrid BM25 + 3-Gram Memory Engine, Fail-Closed DLP,
Scope Hierarchy & `runs:approve_p10` (`owner`/`operator` ONLY) Conflict Resolution,
KHub Air-Gapped `.tar.gz` Mirror Verification, Tarfile Hardening, and Sovereign CLI Parity.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
import sqlite3
import tarfile
import time
import warnings

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
import pytest

from cli import main as cli_main
from core.api.platform_kbrain_routes import (
    get_kbrain_engine,
    get_khub_registry,
    router as platform_kbrain_router,
)
from core.api.platform_runtime_routes import (
    get_rbac_controller,
    router as platform_runtime_router,
)
from core.khub.sync import KHubBundlePacker, KHubMirror
from core.main import app as live_app
from core.platform.kbrain_khub import (
    SQLiteKBrainEngine,
    SQLiteKHubRegistry,
    SecretLeakDetectedError,
)
from core.platform.rbac_webhooks import WorkspaceRbacController
from core.security.auth import launch_token


def _write_malicious_tar(archive_path: Path, member_info: tarfile.TarInfo, payload: bytes = b"") -> None:
    manifest = {
        "bundle_format": "khub-skill-bundle-v1",
        "skill_name": "untrusted",
        "files": {},
        "bundle_digest_sha256": "0" * 64,
    }
    mb = json.dumps(manifest).encode("utf-8")
    with tarfile.open(archive_path, "w:gz") as tar:
        ti_m = tarfile.TarInfo(name="skill_manifest.json")
        ti_m.size = len(mb)
        ti_m.mtime = int(time.time())
        tar.addfile(ti_m, io.BytesIO(mb))
        if member_info.isfile():
            member_info.size = len(payload)
            tar.addfile(member_info, io.BytesIO(payload))
        else:
            tar.addfile(member_info)


def test_khub_tarfile_hardening_symlinks_hardlinks_prefix_escape_and_zero_deprecation_warnings(
    tmp_path: Path,
) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)

        # 1. Valid bundle pack/unpack & mirror export/import emit zero Python 3.14 DeprecationWarnings
        skill_src = tmp_path / "skills_src" / "safe_skill"
        skill_src.mkdir(parents=True)
        (skill_src / "SKILL.md").write_text("# Safe Skill\nDeterministic offline skill.\n", encoding="utf-8")
        (skill_src / "runner.py").write_text("VALUE = 42\n", encoding="utf-8")

        bundle_tar = tmp_path / "safe.skill.tar.gz"
        KHubBundlePacker.pack_skill(skill_src, bundle_tar)
        unpack_dest = tmp_path / "dest"
        res = KHubBundlePacker.unpack_skill(bundle_tar, unpack_dest, verify=True)
        assert res["verified"] is True and (unpack_dest / "SKILL.md").is_file()

        mirror_tar = tmp_path / "safe_mirror.tar.gz"
        KHubMirror.export_mirror(mirror_tar, skills_dir=tmp_path / "skills_src", as_archive=True)
        mirror_dest = tmp_path / "mirror_imported"
        m_res = KHubMirror.import_mirror(mirror_tar, destination_dir=mirror_dest, verify=True)
        assert m_res["verified"] is True and m_res["total_imported"] == 1

        # 2. Symlink & hardlink rejection in KHubBundlePacker.unpack_skill
        sym_tar = tmp_path / "symlink.skill.tar.gz"
        sym_info = tarfile.TarInfo(name="evil_symlink")
        sym_info.type = tarfile.SYMTYPE
        sym_info.linkname = "/etc/passwd"
        _write_malicious_tar(sym_tar, sym_info)
        with pytest.raises(PermissionError, match="Symlink or hardlink rejected"):
            KHubBundlePacker.unpack_skill(sym_tar, tmp_path / "sym_dest", verify=True)

        lnk_tar = tmp_path / "hardlink.skill.tar.gz"
        lnk_info = tarfile.TarInfo(name="evil_hardlink")
        lnk_info.type = tarfile.LNKTYPE
        lnk_info.linkname = "/etc/hosts"
        _write_malicious_tar(lnk_tar, lnk_info)
        with pytest.raises(PermissionError, match="Symlink or hardlink rejected"):
            KHubBundlePacker.unpack_skill(lnk_tar, tmp_path / "lnk_dest", verify=True)

        # 3. Sibling-prefix traversal (`../target_evil/pwn.txt` from `target`) in unpack_skill
        sib_tar = tmp_path / "sibling_escape.skill.tar.gz"
        sib_info = tarfile.TarInfo(name="sub/../../target_evil/pwn.txt")
        _write_malicious_tar(sib_tar, sib_info, b"escaped")
        with pytest.raises(PermissionError, match="Directory traversal"):
            KHubBundlePacker.unpack_skill(sib_tar, tmp_path / "target", verify=True)
        assert not (tmp_path / "target_evil" / "pwn.txt").exists()

        # 4. Symlink, hardlink, and zip-slip rejection in KHubMirror.import_mirror
        mirror_sym_tar = tmp_path / "mirror_sym.tar.gz"
        with tarfile.open(mirror_sym_tar, "w:gz") as tar:
            m_sym = tarfile.TarInfo(name="bundles/escape_link")
            m_sym.type = tarfile.SYMTYPE
            m_sym.linkname = "/etc/passwd"
            tar.addfile(m_sym)
        with pytest.raises(PermissionError, match="Symlink or hardlink rejected"):
            KHubMirror.import_mirror(mirror_sym_tar, destination_dir=tmp_path / "m_sym_dest")

        mirror_lnk_tar = tmp_path / "mirror_lnk.tar.gz"
        with tarfile.open(mirror_lnk_tar, "w:gz") as tar:
            m_lnk = tarfile.TarInfo(name="bundles/escape_hardlink")
            m_lnk.type = tarfile.LNKTYPE
            m_lnk.linkname = "../outside"
            tar.addfile(m_lnk)
        with pytest.raises(PermissionError, match="Symlink or hardlink rejected"):
            KHubMirror.import_mirror(mirror_lnk_tar, destination_dir=tmp_path / "m_lnk_dest")

        mirror_slip_tar = tmp_path / "mirror_slip.tar.gz"
        with tarfile.open(mirror_slip_tar, "w:gz") as tar:
            m_slip = tarfile.TarInfo(name="../../escaped_mirror.txt")
            m_slip.size = 4
            tar.addfile(m_slip, io.BytesIO(b"nope"))
        with pytest.raises(PermissionError, match="Directory traversal"):
            KHubMirror.import_mirror(mirror_slip_tar, destination_dir=tmp_path / "m_slip_dest")


def test_kbrain_dlp_scope_hierarchy_conflict_resolution_and_hybrid_ranking(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dyn_db = tmp_path / "dynamic_state" / "platform_runtime.db"
    monkeypatch.setenv("KEELWAY_RUNTIME_DB_PATH", str(dyn_db))
    engine = SQLiteKBrainEngine()
    try:
        assert Path(engine.db_path) == dyn_db

        # 1. Fail-closed DLP secret rejection across key, statement, provenance_uri, and tags
        leaked_samples = [
            ("arch.llm", "Use OpenAI key sk-proj-AbCdEfGhIjKlMnOpQrStUv123456", "workspace", []),
            ("arch.vcs", "GitHub PAT ghp_1234567890abcdefABCDEF1234567890", "workspace", []),
            ("arch.aws", "Deploy via AKIAIOSFODNN7EXAMPLE", "workspace", []),
            ("arch.auth", "Header Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9", "workspace", []),
            ("arch.tls", "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA...", "workspace", []),
            ("arch.db_pw", "Connect using password=SuperSecretProdPass99!", "workspace", []),
            ("arch.uri", "Safe text", "postgres://admin:Hunter2Secret@db.example:5432/app", []),
            ("arch.tag", "Safe text", "workspace", ["token=my_secret_api_token_value"]),
        ]
        for k, stmt, prov, tgs in leaked_samples:
            with pytest.raises(SecretLeakDetectedError) as exc_info:
                engine.record_fact("ws-sec", k, stmt, provenance_uri=prov, tags=tgs)
            assert "sk-proj-" not in str(exc_info.value) and "ghp_" not in str(exc_info.value)

        raw_bytes = dyn_db.read_bytes()
        assert b"sk-proj-" not in raw_bytes and b"ghp_" not in raw_bytes and b"AKIAIOSFODNN7EXAMPLE" not in raw_bytes

        # 2. Scope hierarchy filtering (`local_session` < `project` < `team` < `org`)
        engine.record_fact("ws-sec", "note.local", "Temporary scratchpad sqlite wal note", scope="local_session")
        engine.record_fact("ws-sec", "arch.db", "SQLite WAL crash-safe local runtime storage", scope="project", tags=["sqlite", "storage"])
        engine.record_fact("ws-sec", "arch.cache", "Redis cluster prohibited in air-gap mode", scope="team", tags=["airgap"])
        engine.record_fact("ws-sec", "policy.p10", "Dual-human P-10 approval required for org policy", scope="org", tags=["governance"])

        with pytest.raises(ValueError, match="Unsupported KBrain scope"):
            engine.record_fact("ws-sec", "bad.scope", "Invalid", scope="global")
        with pytest.raises(ValueError, match="Unsupported KBrain max_scope"):
            engine.search_facts("ws-sec", query="", max_scope="universe")

        s_local = engine.search_facts("ws-sec", query="", max_scope="local_session")
        assert [r["key"] for r in s_local["results"]] == ["note.local"]
        assert s_local["results"][0]["hybrid_score"] == 1.0

        s_proj = engine.search_facts("ws-sec", query="", max_scope="project")
        assert {r["key"] for r in s_proj["results"]} == {"note.local", "arch.db"}

        s_org = engine.search_facts("ws-sec", query="", max_scope="org")
        assert s_org["total_matches"] == 4

        # 3. Hybrid BM25 + Character 3-Gram Cosine Similarity ranking
        exact = engine.search_facts("ws-sec", query="SQLite WAL storage", max_scope="org")
        assert exact["total_matches"] >= 2
        top = exact["results"][0]
        assert top["key"] == "arch.db"
        assert top["bm25_score"] == 1.0
        assert 0.0 < top["ngram_cosine_score"] <= 1.0
        assert top["hybrid_score"] == round(0.65 * top["bm25_score"] + 0.35 * top["ngram_cosine_score"], 4)
        assert exact["results"][0]["hybrid_score"] > exact["results"][1]["hybrid_score"]

        # Typo query with zero exact BM25 token overlap still matches via 3-gram cosine similarity
        typo = engine.search_facts("ws-sec", query="sqllite crashsafe", max_scope="project")
        assert typo["total_matches"] >= 1
        assert typo["results"][0]["key"] == "arch.db"
        assert typo["results"][0]["bm25_score"] == 0.0
        assert typo["results"][0]["ngram_cosine_score"] > 0.0

        # 4. Deterministic conflict detection & resolution superseding
        orig_db_fact = [r for r in s_proj["results"] if r["key"] == "arch.db"][0]
        conflicting = engine.record_fact("ws-sec", "arch.db", "DuckDB 1.1 columnar engine", scope="project")
        assert conflicting["status"] == "conflict"
        assert conflicting["conflict_with_fact_id"] == orig_db_fact["id"]

        # Hidden from standard search unless include_conflicts=True
        clean_search = engine.search_facts("ws-sec", query="DuckDB", max_scope="project", include_conflicts=False)
        assert clean_search["total_matches"] == 0
        with_conf = engine.search_facts("ws-sec", query="DuckDB", max_scope="project", include_conflicts=True)
        assert with_conf["total_matches"] == 1 and with_conf["results"][0]["id"] == conflicting["id"]

        # Approving conflicting fact supersedes original fact
        approved = engine.resolve_fact("ws-sec", conflicting["id"], "approve", approver_id="operator-alice")
        assert approved["status"] == "approved" and approved["conflict_with_fact_id"] is None

        after = engine.search_facts("ws-sec", query="", max_scope="project", include_conflicts=True)
        active_arch_db = [r for r in after["results"] if r["key"] == "arch.db"]
        assert len(active_arch_db) == 1 and active_arch_db[0]["id"] == conflicting["id"]

        # Rejecting a second conflict keeps approved fact intact
        bad_conflict = engine.record_fact("ws-sec", "arch.db", "Unverified MongoDB shard", scope="project")
        assert bad_conflict["status"] == "conflict"
        rejected = engine.resolve_fact("ws-sec", bad_conflict["id"], "reject", approver_id="owner")
        assert rejected["status"] == "rejected"
    finally:
        engine.close()


def test_khub_registry_catalog_and_airgap_mirror_roundtrip(tmp_path: Path) -> None:
    db_file = tmp_path / "khub_reg.db"
    registry = SQLiteKHubRegistry(db_path=db_file)
    try:
        catalog = registry.list_skills("ws-airgap")
        assert catalog["workspace_id"] == "ws-airgap"
        assert catalog["air_gap_compliant"] is True
        assert catalog["total_skills"] >= 8
        assert catalog["catalog_digest_sha256"].startswith("sha256:")
        skill_ids = {s["skill_id"] for s in catalog["skills"]}
        assert {"plan", "review", "security", "qa"}.issubset(skill_ids)
        for item in catalog["skills"]:
            assert item["source"] == "kstack_builtin"
            assert item["bundle_digest_sha256"].startswith("sha256:")
            assert item["files_count"] >= 1 and item["air_gap_compliant"] is True

        with warnings.catch_warnings():
            warnings.simplefilter("error", DeprecationWarning)
            subset_receipt = registry.verify_airgap_mirror("ws-airgap", skill_ids=["plan", "security"])
            full_receipt = registry.verify_airgap_mirror("ws-airgap")

        assert subset_receipt["verified"] is True
        assert subset_receipt["mirror_format"] == "khub-airgap-mirror-v1"
        assert subset_receipt["skills_verified"] == 2
        assert subset_receipt["catalog_digest_sha256"].startswith("sha256:")
        assert full_receipt["skills_verified"] == catalog["total_skills"]

        with pytest.raises(ValueError, match="Unknown skill_id"):
            registry.verify_airgap_mirror("ws-airgap", skill_ids=["nonexistent-skill"])

        with sqlite3.connect(db_file) as conn:
            cnt = conn.execute("SELECT COUNT(*) FROM platform_khub_mirrors WHERE workspace_id='ws-airgap'").fetchone()[0]
            assert cnt == 2
    finally:
        registry.close()


@pytest.mark.asyncio
async def test_fastapi_kbrain_khub_routes_and_5_role_p10_rbac(tmp_path: Path) -> None:
    db_file = tmp_path / "api_phase10.db"
    engine = SQLiteKBrainEngine(db_path=db_file)
    registry = SQLiteKHubRegistry(db_path=db_file)
    rbac = WorkspaceRbacController(db_path=db_file)

    test_app = FastAPI()
    test_app.include_router(platform_runtime_router)
    test_app.include_router(platform_kbrain_router)
    test_app.dependency_overrides[get_kbrain_engine] = lambda: engine
    test_app.dependency_overrides[get_khub_registry] = lambda: registry
    test_app.dependency_overrides[get_rbac_controller] = lambda: rbac

    token = launch_token()
    role_headers = {
        r: {"Authorization": f"Bearer {token}", "X-Keelway-Role": r, "X-Keelway-Actor": f"{r}-user"}
        for r in ("owner", "admin", "builder", "operator", "viewer")
    }

    try:
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            # 1. Record fact RBAC (`agents:dispatch` -> owner/admin/builder allowed; operator/viewer 403)
            for denied_role in ("viewer", "operator"):
                r_den = await client.post(
                    "/v1/platform/kbrain/facts",
                    headers=role_headers[denied_role],
                    json={"workspace_id": "default", "key": "k1", "statement": "s1"},
                )
                assert r_den.status_code == 403

            # Secret leak returns 400 Bad Request
            r_leak = await client.post(
                "/v1/platform/kbrain/facts",
                headers=role_headers["builder"],
                json={"workspace_id": "default", "key": "llm.key", "statement": "sk-live-SecretKeyValue1234567890"},
            )
            assert r_leak.status_code == 400

            f1 = await client.post(
                "/v1/platform/kbrain/facts",
                headers=role_headers["builder"],
                json={"workspace_id": "default", "key": "arch.db", "statement": "SQLite WAL mode", "scope": "project"},
            )
            assert f1.status_code == 200 and f1.json()["status"] == "approved"
            f1_id = f1.json()["id"]

            f2 = await client.post(
                "/v1/platform/kbrain/facts",
                headers=role_headers["admin"],
                json={"workspace_id": "default", "key": "arch.db", "statement": "DuckDB analytical store", "scope": "project"},
            )
            assert f2.status_code == 200 and f2.json()["status"] == "conflict"
            assert f2.json()["conflict_with_fact_id"] == f1_id
            f2_id = f2.json()["id"]

            # 2. Search route (`workspace:read` -> viewer 200)
            sr = await client.get(
                "/v1/platform/kbrain/search?workspace_id=default&query=SQLite+WAL&max_scope=org",
                headers=role_headers["viewer"],
            )
            assert sr.status_code == 200 and sr.json()["results"][0]["id"] == f1_id

            # 3. Resolve fact (`runs:approve_p10` -> strictly owner/operator ONLY; builder/admin/viewer 403!)
            for forbidden_resolver in ("viewer", "builder", "admin"):
                res_403 = await client.post(
                    f"/v1/platform/kbrain/facts/{f2_id}/resolve",
                    headers=role_headers[forbidden_resolver],
                    json={"workspace_id": "default", "resolution": "approve"},
                )
                assert res_403.status_code == 403, f"Expected 403 for role={forbidden_resolver}, got {res_403.status_code}"

            res_op = await client.post(
                f"/v1/platform/kbrain/facts/{f2_id}/resolve",
                headers=role_headers["operator"],
                json={"workspace_id": "default", "resolution": "approve"},
            )
            assert res_op.status_code == 200 and res_op.json()["status"] == "approved"

            # Missing fact -> 404; invalid resolution -> 400
            assert (
                await client.post(
                    "/v1/platform/kbrain/facts/fact-missing/resolve",
                    headers=role_headers["owner"],
                    json={"workspace_id": "default", "resolution": "approve"},
                )
            ).status_code == 404
            assert (
                await client.post(
                    f"/v1/platform/kbrain/facts/{f2_id}/resolve",
                    headers=role_headers["owner"],
                    json={"workspace_id": "default", "resolution": "maybe"},
                )
            ).status_code == 400

            # 4. KHub catalog & mirror verify routes
            kh_list = await client.get("/v1/platform/khub/skills?workspace_id=default", headers=role_headers["viewer"])
            assert kh_list.status_code == 200 and kh_list.json()["total_skills"] >= 8

            assert (
                await client.post(
                    "/v1/platform/khub/mirror/verify",
                    headers=role_headers["viewer"],
                    json={"workspace_id": "default", "skill_ids": ["plan"]},
                )
            ).status_code == 403

            kh_ver = await client.post(
                "/v1/platform/khub/mirror/verify",
                headers=role_headers["builder"],
                json={"workspace_id": "default", "skill_ids": ["plan"]},
            )
            assert kh_ver.status_code == 200 and kh_ver.json()["verified"] is True and kh_ver.json()["skills_verified"] == 1

            assert (
                await client.post(
                    "/v1/platform/khub/mirror/verify",
                    headers=role_headers["owner"],
                    json={"workspace_id": "default", "skill_ids": ["unknown_skill"]},
                )
            ).status_code == 400

        live_paths = live_app.openapi()["paths"]
        for expected_path in (
            "/v1/platform/kbrain/facts",
            "/v1/platform/kbrain/search",
            "/v1/platform/kbrain/facts/{fact_id}/resolve",
            "/v1/platform/khub/skills",
            "/v1/platform/khub/mirror/verify",
        ):
            assert expected_path in live_paths
    finally:
        engine.close()
        registry.close()
        rbac.close()


def test_cli_kbrain_and_khub_json_parity(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    db_file = str(tmp_path / "cli_phase10.db")

    assert cli_main([
        "kbrain", "record", "--workspace", "default", "--key", "arch.db",
        "--statement", "SQLite WAL", "--scope", "project", "--db-path", db_file, "--json",
    ]) == 0
    rec1 = json.loads(capsys.readouterr().out)
    assert rec1["status"] == "approved" and rec1["key"] == "arch.db"

    assert cli_main([
        "kbrain", "record", "--workspace", "default", "--key", "arch.db",
        "--statement", "SQLite WAL v2", "--scope", "project", "--db-path", db_file, "--json",
    ]) == 0
    rec2 = json.loads(capsys.readouterr().out)
    assert rec2["status"] == "conflict" and rec2["conflict_with_fact_id"] == rec1["id"]

    assert cli_main([
        "kbrain", "resolve", "--workspace", "default", "--fact-id", rec2["id"],
        "--resolution", "approve", "--db-path", db_file, "--json",
    ]) == 0
    res_out = json.loads(capsys.readouterr().out)
    assert res_out["status"] == "approved"

    assert cli_main([
        "kbrain", "search", "--workspace", "default", "--query", "SQLite WAL",
        "--max-scope", "org", "--db-path", db_file, "--json",
    ]) == 0
    search_out = json.loads(capsys.readouterr().out)
    assert search_out["total_matches"] == 1 and search_out["results"][0]["id"] == rec2["id"]

    # DLP rejection via CLI returns exit code 1
    assert cli_main([
        "kbrain", "record", "--workspace", "default", "--key", "leak.gh",
        "--statement", "ghp_abcdefghijklmnopqrstuvwxyz123456", "--db-path", db_file, "--json",
    ]) == 1
    capsys.readouterr()

    assert cli_main(["khub", "skills", "--workspace", "default", "--db-path", db_file, "--json"]) == 0
    skills_out = json.loads(capsys.readouterr().out)
    assert skills_out["total_skills"] >= 8 and skills_out["air_gap_compliant"] is True

    assert cli_main([
        "khub", "verify-mirror", "--workspace", "default", "--skill-id", "plan", "--db-path", db_file, "--json",
    ]) == 0
    mirror_out = json.loads(capsys.readouterr().out)
    assert mirror_out["verified"] is True and mirror_out["skills_verified"] == 1
