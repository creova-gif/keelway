"""
Comprehensive tests for KHub Universal Skill Bundle Packaging & Synchronization.
Tests pack, unpack, member digest verification, tampering detection, directory traversal protection,
REST API (/v1/khub/bundle/export & /v1/khub/bundle/import), and CLI integration.
"""

from __future__ import annotations

import io
import json
import os
import shutil
import tarfile
import tempfile
import time
from pathlib import Path
import pytest
from httpx import ASGITransport, AsyncClient

from cli import build_parser, cmd_hub
from core.api import routes
from core.khub.sync import KHubBundlePacker
from core.main import app
from core.storage.workspace_fs import WorkspaceFilesystem


@pytest.fixture
def workspace_fixture():
    """
    Temporary workspace fixture that properly saves and restores routes._workspace_fs
    in a try...finally block.
    """
    prev_fs = routes._workspace_fs
    tmp_dir = tempfile.mkdtemp(prefix="keelway_khub_test_")
    fs = WorkspaceFilesystem(root_dir=tmp_dir)
    routes.set_workspace_fs(fs)
    try:
        yield Path(tmp_dir)
    finally:
        routes.set_workspace_fs(prev_fs)
        shutil.rmtree(tmp_dir, ignore_errors=True)


# =====================================================================
# 1. Unit Tests: Pack and Unpack Flow
# =====================================================================

def test_khub_bundle_pack_and_unpack_directory(tmp_path: Path):
    """Test packing a complete skill directory with SKILL.md and assets, then unpacking with verification."""
    skill_dir = tmp_path / "skills" / "git_helper"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text("# Git Helper Skill\nAutomates branch management.", encoding="utf-8")
    (skill_dir / "helper.py").write_text("def branch_name(issue): return f'issue-{issue}'", encoding="utf-8")
    (skill_dir / "config.json").write_text(json.dumps({"timeout_sec": 30}), encoding="utf-8")

    archive_path = tmp_path / "exports" / "git_helper.skill.tar.gz"

    # Pack
    pack_res = KHubBundlePacker.pack_skill(skill_dir, archive_path)
    assert pack_res["status"] == "packed"
    assert pack_res["skill_name"] == "Git Helper Skill"
    assert "SKILL.md" in pack_res["files"]
    assert "helper.py" in pack_res["files"]
    assert "config.json" in pack_res["files"]
    assert len(pack_res["bundle_digest_sha256"]) == 64
    assert archive_path.is_file()

    # Unpack with verification
    dest_dir = tmp_path / "imported" / "git_helper"
    unpack_res = KHubBundlePacker.unpack_skill(archive_path, dest_dir, verify=True)
    assert unpack_res["status"] == "unpacked"
    assert unpack_res["verified"] is True
    assert (dest_dir / "SKILL.md").read_text(encoding="utf-8") == "# Git Helper Skill\nAutomates branch management."
    assert (dest_dir / "helper.py").is_file()
    assert (dest_dir / "config.json").is_file()
    assert (dest_dir / "skill_manifest.json").is_file()


def test_khub_bundle_pack_single_file(tmp_path: Path):
    """Test packing a standalone markdown skill file."""
    skill_file = tmp_path / "prompt_optimizer.md"
    skill_file.write_text("# Prompt Optimizer\nRefines system prompts.", encoding="utf-8")

    archive_path = tmp_path / "prompt_optimizer.skill.tar.gz"
    pack_res = KHubBundlePacker.pack_skill(skill_file, archive_path)

    assert pack_res["status"] == "packed"
    assert archive_path.is_file()
    assert "SKILL.md" in pack_res["files"]

    dest_dir = tmp_path / "unpacked_single"
    unpack_res = KHubBundlePacker.unpack_skill(archive_path, dest_dir, verify=True)
    assert unpack_res["status"] == "unpacked"
    assert (dest_dir / "SKILL.md").is_file()


# =====================================================================
# 2. Security Tests: Tampering & Traversal Rejection
# =====================================================================

def test_khub_bundle_tamper_rejection(tmp_path: Path):
    """Test that modifying any file content inside the archive causes verification failure."""
    skill_dir = tmp_path / "tamper_src"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text("# Trusted Skill\nSafe instructions.", encoding="utf-8")
    (skill_dir / "payload.py").write_text("SAFE_FLAG = True", encoding="utf-8")

    archive_path = tmp_path / "trusted.skill.tar.gz"
    KHubBundlePacker.pack_skill(skill_dir, archive_path)

    # Tamper with payload.py in archive
    tampered_archive = tmp_path / "tampered.skill.tar.gz"
    with tarfile.open(archive_path, "r:gz") as src_tar, tarfile.open(tampered_archive, "w:gz") as dst_tar:
        for member in src_tar.getmembers():
            f = src_tar.extractfile(member)
            if member.name == "payload.py":
                bad_content = b"SAFE_FLAG = False  # Tampered!"
                member.size = len(bad_content)
                dst_tar.addfile(member, io.BytesIO(bad_content))
            else:
                dst_tar.addfile(member, f)

    dest_dir = tmp_path / "tamper_dest"
    with pytest.raises(ValueError, match="Tampered file detected"):
        KHubBundlePacker.unpack_skill(tampered_archive, dest_dir, verify=True)


def test_khub_bundle_manifest_digest_tamper_rejection(tmp_path: Path):
    """Test that modifying file hashes or bundle digest in skill_manifest.json is rejected."""
    skill_dir = tmp_path / "digest_src"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text("# Integrity Test", encoding="utf-8")

    archive_path = tmp_path / "orig.skill.tar.gz"
    KHubBundlePacker.pack_skill(skill_dir, archive_path)

    # Corrupt bundle digest in manifest
    corrupted_archive = tmp_path / "corrupted_manifest.skill.tar.gz"
    with tarfile.open(archive_path, "r:gz") as src_tar, tarfile.open(corrupted_archive, "w:gz") as dst_tar:
        for member in src_tar.getmembers():
            f = src_tar.extractfile(member)
            if member.name == "skill_manifest.json":
                data = json.loads(f.read().decode("utf-8"))
                data["bundle_digest_sha256"] = "0" * 64
                corrupted_bytes = json.dumps(data).encode("utf-8")
                member.size = len(corrupted_bytes)
                dst_tar.addfile(member, io.BytesIO(corrupted_bytes))
            else:
                dst_tar.addfile(member, f)

    dest_dir = tmp_path / "corrupted_dest"
    with pytest.raises(ValueError, match="Tampered manifest detected"):
        KHubBundlePacker.unpack_skill(corrupted_archive, dest_dir, verify=True)


def test_khub_bundle_directory_traversal_attack_rejection(tmp_path: Path):
    """Test that malicious archives with path traversal elements are rejected with PermissionError."""
    malicious_archive = tmp_path / "zip_slip.skill.tar.gz"
    with tarfile.open(malicious_archive, "w:gz") as tar:
        # Valid manifest
        manifest_data = {
            "bundle_format": "khub-skill-bundle-v1",
            "skill_name": "malicious",
            "files": {"../../evil.txt": "dummy_hash"},
            "bundle_digest_sha256": "dummy",
        }
        mb = json.dumps(manifest_data).encode("utf-8")
        ti_m = tarfile.TarInfo(name="skill_manifest.json")
        ti_m.size = len(mb)
        ti_m.mtime = int(time.time())
        tar.addfile(ti_m, io.BytesIO(mb))

        # Malicious traversal member
        payload = b"unauthorized_system_file_write"
        ti = tarfile.TarInfo(name="../../evil.txt")
        ti.size = len(payload)
        ti.mtime = int(time.time())
        tar.addfile(ti, io.BytesIO(payload))

    dest_dir = tmp_path / "safe_sandbox"
    with pytest.raises(PermissionError, match="Directory traversal attack detected"):
        KHubBundlePacker.unpack_skill(malicious_archive, dest_dir, verify=True)


# =====================================================================
# 3. REST API Tests (/v1/khub/bundle/export & /v1/khub/bundle/import)
# =====================================================================

@pytest.mark.asyncio
async def test_khub_bundle_rest_api_export_and_import(workspace_fixture: Path):
    """Test REST API endpoints /v1/khub/bundle/export and /v1/khub/bundle/import."""
    # Setup skill inside workspace
    skill_dir = workspace_fixture / "skills" / "api_skill"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text("# API Skill\nExported via REST API.", encoding="utf-8")
    (skill_dir / "run.sh").write_text("echo 'hello'", encoding="utf-8")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Export
        export_resp = await client.post(
            "/v1/khub/bundle/export",
            json={
                "skill_path": "skills/api_skill",
                "output_archive": "exports/api_skill.skill.tar.gz",
            },
            headers={"X-Keelway-Actor": "test-dev", "X-Keelway-Role": "platform_owner"},
        )
        assert export_resp.status_code == 200, export_resp.text
        data = export_resp.json()
        assert data["status"] == "packed"
        assert data["archive_path"] == "exports/api_skill.skill.tar.gz"
        assert (workspace_fixture / "exports" / "api_skill.skill.tar.gz").is_file()

        # 2. Import
        import_resp = await client.post(
            "/v1/khub/bundle/import",
            json={
                "archive_path": "exports/api_skill.skill.tar.gz",
                "destination_dir": "imported/api_skill",
                "verify": True,
            },
            headers={"X-Keelway-Actor": "test-dev", "X-Keelway-Role": "platform_owner"},
        )
        assert import_resp.status_code == 200, import_resp.text
        idata = import_resp.json()
        assert idata["status"] == "unpacked"
        assert idata["verified"] is True
        assert (workspace_fixture / "imported" / "api_skill" / "SKILL.md").is_file()


@pytest.mark.asyncio
async def test_khub_bundle_rest_api_errors(workspace_fixture: Path):
    """Test error handling in /v1/khub/bundle REST endpoints."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Missing skill_path
        resp_missing = await client.post(
            "/v1/khub/bundle/export",
            json={},
            headers={"X-Keelway-Actor": "test-dev", "X-Keelway-Role": "platform_owner"},
        )
        assert resp_missing.status_code == 400

        # Non-existent skill_path
        resp_404 = await client.post(
            "/v1/khub/bundle/export",
            json={"skill_path": "nonexistent/dir"},
            headers={"X-Keelway-Actor": "test-dev", "X-Keelway-Role": "platform_owner"},
        )
        assert resp_404.status_code == 404

        # Non-existent archive for import
        resp_import_404 = await client.post(
            "/v1/khub/bundle/import",
            json={"archive_path": "nonexistent.tar.gz"},
            headers={"X-Keelway-Actor": "test-dev", "X-Keelway-Role": "platform_owner"},
        )
        assert resp_import_404.status_code == 404


# =====================================================================
# 4. CLI Tests (keelway hub pack & keelway hub unpack)
# =====================================================================

def test_khub_bundle_cli_parser():
    """Verify build_parser registers hub pack and unpack with expected arguments."""
    parser = build_parser()

    # Test hub pack
    args_pack = parser.parse_args(["hub", "pack", "path/to/skill", "--out", "bundle.skill.tar.gz"])
    assert args_pack.command == "hub"
    assert args_pack.hub_command == "pack"
    assert args_pack.skill_path == Path("path/to/skill")
    assert args_pack.out == Path("bundle.skill.tar.gz")

    # Test hub unpack
    args_unpack = parser.parse_args(["hub", "unpack", "bundle.skill.tar.gz", "--dest", "target/dir"])
    assert args_unpack.command == "hub"
    assert args_unpack.hub_command == "unpack"
    assert args_unpack.archive == Path("bundle.skill.tar.gz")
    assert args_unpack.dest == Path("target/dir")


def test_khub_bundle_cli_execution(tmp_path: Path):
    """Test cmd_hub pack and unpack execution."""
    src = tmp_path / "cli_skill"
    src.mkdir(parents=True, exist_ok=True)
    (src / "SKILL.md").write_text("# CLI Skill\nCLI packed skill.", encoding="utf-8")
    (src / "code.py").write_text("print('cli')", encoding="utf-8")

    archive = tmp_path / "cli_skill.skill.tar.gz"
    rc_pack = cmd_hub("pack", skill_path=src, out=archive)
    assert rc_pack == 0
    assert archive.is_file()

    dest = tmp_path / "cli_unpacked"
    rc_unpack = cmd_hub("unpack", archive=archive, dest=dest)
    assert rc_unpack == 0
    assert (dest / "SKILL.md").is_file()
    assert (dest / "code.py").read_text(encoding="utf-8") == "print('cli')"
