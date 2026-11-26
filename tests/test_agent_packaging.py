"""Unit and integration tests for Keelway Agent Bundle Packaging and Verification."""
import json
import shutil
import tarfile
import tempfile
from pathlib import Path
import pytest
from httpx import ASGITransport, AsyncClient

from core.agents.builder import AgentBundlePacker
from core.main import app
from core.api.routes import set_workspace_fs
from core.storage.workspace_fs import WorkspaceFilesystem


@pytest.fixture
def temp_workspace():
    from core.api import routes
    prev_fs = routes._workspace_fs
    tmp = tempfile.mkdtemp(prefix="keelway_test_pkg_")
    fs = WorkspaceFilesystem(root_dir=tmp)
    set_workspace_fs(fs)
    try:
        yield Path(tmp)
    finally:
        set_workspace_fs(prev_fs)
        shutil.rmtree(tmp, ignore_errors=True)


@pytest.mark.asyncio
async def test_agent_bundle_pack_and_unpack_flow(temp_workspace):
    agent_dir = temp_workspace / "agents" / "demo-agent"
    agent_dir.mkdir(parents=True, exist_ok=True)
    (agent_dir / "agent.py").write_text("def run(): return 'ok'", encoding="utf-8")
    (agent_dir / "demo.agent.json").write_text(json.dumps({"name": "demo-agent", "version": "1.0.0"}), encoding="utf-8")

    archive_path = temp_workspace / "exports" / "demo-agent.tar.gz"
    manifest = AgentBundlePacker.pack(agent_dir, archive_path)

    assert manifest["bundle_name"] == "demo-agent"
    assert "agent.py" in manifest["files"]
    assert "demo.agent.json" in manifest["files"]
    assert len(manifest["bundle_digest_sha256"]) == 64
    assert archive_path.is_file()

    dest_dir = temp_workspace / "unpacked" / "demo-agent"
    unpacked_manifest = AgentBundlePacker.unpack(archive_path, dest_dir, verify=True)
    assert unpacked_manifest["bundle_name"] == "demo-agent"
    assert (dest_dir / "agent.py").read_text(encoding="utf-8") == "def run(): return 'ok'"
    assert (dest_dir / "demo.agent.json").is_file()


@pytest.mark.asyncio
async def test_agent_bundle_tamper_detection(temp_workspace):
    agent_dir = temp_workspace / "agents" / "secure-agent"
    agent_dir.mkdir(parents=True, exist_ok=True)
    (agent_dir / "code.py").write_text("trusted_code = True", encoding="utf-8")
    (agent_dir / "secure.agent.json").write_text(json.dumps({"name": "secure-agent", "version": "1.0.0"}), encoding="utf-8")

    archive_path = temp_workspace / "secure-agent.tar.gz"
    AgentBundlePacker.pack(agent_dir, archive_path)

    # Tamper with the archive by replacing code.py with malicious content
    tampered_archive = temp_workspace / "tampered-agent.tar.gz"
    with tarfile.open(archive_path, "r:gz") as src_tar, tarfile.open(tampered_archive, "w:gz") as dst_tar:
        for member in src_tar.getmembers():
            f = src_tar.extractfile(member)
            if member.name == "code.py":
                bad_content = b"malicious_code = True"
                member.size = len(bad_content)
                import io
                dst_tar.addfile(member, io.BytesIO(bad_content))
            else:
                dst_tar.addfile(member, f)

    dest_dir = temp_workspace / "tampered_dest"
    with pytest.raises(ValueError, match="Tampered file detected"):
        AgentBundlePacker.unpack(tampered_archive, dest_dir, verify=True)


@pytest.mark.asyncio
async def test_agent_bundle_directory_traversal_protection(temp_workspace):
    malicious_archive = temp_workspace / "malicious.tar.gz"
    with tarfile.open(malicious_archive, "w:gz") as tar:
        import io
        import time
        # Add a fake bundle manifest
        bm = json.dumps({"bundle_name": "bad", "files": {}}).encode("utf-8")
        ti_bm = tarfile.TarInfo(name="bundle_manifest.json")
        ti_bm.size = len(bm)
        ti_bm.mtime = int(time.time())
        tar.addfile(ti_bm, io.BytesIO(bm))

        # Add a zip slip member
        payload = b"pwned"
        ti = tarfile.TarInfo(name="../../evil.txt")
        ti.size = len(payload)
        ti.mtime = int(time.time())
        tar.addfile(ti, io.BytesIO(payload))

    dest_dir = temp_workspace / "safe_dest"
    with pytest.raises(PermissionError, match="Directory traversal attack detected"):
        AgentBundlePacker.unpack(malicious_archive, dest_dir, verify=True)


@pytest.mark.asyncio
async def test_agent_builder_pack_and_unpack_rest_api(temp_workspace):
    agent_dir = temp_workspace / "agents" / "api-agent"
    agent_dir.mkdir(parents=True, exist_ok=True)
    (agent_dir / "main.py").write_text("print('hello')", encoding="utf-8")
    (agent_dir / "api-agent.agent.json").write_text(json.dumps({"name": "api-agent", "version": "1.0.0"}), encoding="utf-8")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Pack
        pack_resp = await client.post(
            "/v1/agent/builder/pack",
            json={"source_dir": "agents/api-agent", "output_archive": "exports/api-agent.tar.gz"},
            headers={"X-Keelway-Actor": "test-engineer", "X-Keelway-Role": "platform_owner"},
        )
        assert pack_resp.status_code == 200, pack_resp.text
        pack_data = pack_resp.json()
        assert pack_data["status"] == "packed"
        assert pack_data["archive_path"] == "exports/api-agent.tar.gz"

        # Unpack
        unpack_resp = await client.post(
            "/v1/agent/builder/unpack",
            json={"archive_path": "exports/api-agent.tar.gz", "destination_dir": "unpacked/api-agent"},
            headers={"X-Keelway-Actor": "test-engineer", "X-Keelway-Role": "platform_owner"},
        )
        assert unpack_resp.status_code == 200, unpack_resp.text
        unpack_data = unpack_resp.json()
        assert unpack_data["status"] == "unpacked"
        assert (temp_workspace / "unpacked" / "api-agent" / "main.py").is_file()


def test_cli_agent_pack_and_unpack(temp_workspace):
    from cli import cmd_agent

    src = temp_workspace / "agents" / "cli-bot"
    src.mkdir(parents=True, exist_ok=True)
    (src / "bot.py").write_text("# bot code", encoding="utf-8")
    (src / "bot.agent.json").write_text(json.dumps({"name": "cli-bot", "version": "1.0.0"}), encoding="utf-8")

    archive = temp_workspace / "cli-bot.tar.gz"
    res_pack = cmd_agent("pack", path=src, out=archive)
    assert res_pack == 0
    assert archive.is_file()

    dest = temp_workspace / "unpacked-cli-bot"
    res_unpack = cmd_agent("unpack", path=archive, out=dest)
    assert res_unpack == 0
    assert (dest / "bot.py").read_text(encoding="utf-8") == "# bot code"
