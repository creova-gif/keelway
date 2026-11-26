"""
Tests for Keelway Enterprise Workspace Registry & Multi-Workspace Manager.
"""

import pytest
from pathlib import Path
from httpx import ASGITransport, AsyncClient

from core.main import app
from core.security.auth import launch_token
from core.storage.workspace_fs import WorkspaceSecurityError
from core.storage.workspace_registry import WorkspaceRegistry


@pytest.fixture
def owner_headers():
    return {"Authorization": f"Bearer {launch_token()}"}


def test_workspace_registry_lifecycle(tmp_path):
    reg_file = tmp_path / "workspaces.json"
    reg = WorkspaceRegistry(registry_file=reg_file, auto_register_cwd=False)

    # 1. Register test repo
    repo1 = tmp_path / "repo1"
    repo1.mkdir()
    (repo1 / "package.json").write_text('{"name": "test-repo", "scripts": {"test": "vitest"}}\n')

    entry1 = reg.register(str(repo1), name="Project Alpha", make_active=True)
    assert entry1.name == "Project Alpha"
    assert entry1.is_active is True
    assert entry1.detected_framework == "node"
    assert reg.get_active().id == entry1.id

    # 2. Register second repo
    repo2 = tmp_path / "repo2"
    repo2.mkdir()
    (repo2 / "pyproject.toml").write_text('[tool.pytest.ini_options]\n')

    entry2 = reg.register(str(repo2), name="Service Beta", make_active=False)
    assert entry2.name == "Service Beta"
    assert entry2.is_active is False
    assert entry2.detected_framework == "python"

    # Active remains repo1
    assert reg.get_active().id == entry1.id

    # 3. Activate repo2
    act = reg.activate(entry2.id)
    assert act.id == entry2.id
    assert act.is_active is True
    assert reg.get_active().id == entry2.id
    assert reg.workspaces[entry1.id].is_active is False

    # 4. Persistence verification
    reg_reloaded = WorkspaceRegistry(registry_file=reg_file, auto_register_cwd=False)
    assert len(reg_reloaded.workspaces) == 2
    assert reg_reloaded.get_active().id == entry2.id

    # 5. Unregister
    ok = reg.unregister(entry2.id)
    assert ok is True
    assert entry2.id not in reg.workspaces
    # Alpha should automatically become active fallback
    assert reg.get_active().id == entry1.id


def test_workspace_registry_rejects_forbidden_and_invalid_paths(tmp_path):
    reg = WorkspaceRegistry(registry_file=tmp_path / "reg.json", auto_register_cwd=False)

    # Nonexistent path
    with pytest.raises(FileNotFoundError):
        reg.register(str(tmp_path / "does_not_exist"))

    # File instead of directory
    f_path = tmp_path / "not_a_dir.txt"
    f_path.write_text("file")
    with pytest.raises(NotADirectoryError):
        reg.register(str(f_path))

    # Forbidden system directories
    for forbidden in ["/etc", "/System", "/root"]:
        if Path(forbidden).exists():
            with pytest.raises(WorkspaceSecurityError):
                reg.register(forbidden)


@pytest.mark.asyncio
async def test_workspace_api_endpoints(tmp_path, owner_headers):
    # Setup two mock project directories
    p1 = tmp_path / "api_proj_1"
    p1.mkdir()
    p2 = tmp_path / "api_proj_2"
    p2.mkdir()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Register workspace p1
        res1 = await client.post(
            "/v1/workspaces",
            json={"path": str(p1), "name": "API Proj 1", "make_active": True},
            headers=owner_headers,
        )
        assert res1.status_code == 200
        ws1_data = res1.json()["workspace"]
        ws1_id = ws1_data["id"]
        assert ws1_data["name"] == "API Proj 1"

        # 2. Register workspace p2
        res2 = await client.post(
            "/v1/workspaces",
            json={"path": str(p2), "name": "API Proj 2", "make_active": False},
            headers=owner_headers,
        )
        assert res2.status_code == 200
        ws2_data = res2.json()["workspace"]
        ws2_id = ws2_data["id"]

        # 3. List workspaces
        res_list = await client.get("/v1/workspaces", headers=owner_headers)
        assert res_list.status_code == 200
        data_list = res_list.json()
        assert any(w["id"] == ws1_id for w in data_list["workspaces"])
        assert any(w["id"] == ws2_id for w in data_list["workspaces"])

        # 4. Switch active workspace to p2
        res_act = await client.post(f"/v1/workspaces/{ws2_id}/activate", headers=owner_headers)
        assert res_act.status_code == 200
        assert res_act.json()["workspace"]["is_active"] is True

        # Verify active workspace info endpoint reflects the switch
        res_info = await client.get("/v1/workspace", headers=owner_headers)
        assert res_info.status_code == 200
        assert res_info.json()["name"] == "api_proj_2"

        # 5. Delete workspace p1
        res_del = await client.delete(f"/v1/workspaces/{ws1_id}", headers=owner_headers)
        assert res_del.status_code == 200
        assert res_del.json()["status"] == "unregistered"
