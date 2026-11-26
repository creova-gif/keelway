"""Tests for Agent Manifest Registry and Cost Metering enforcement.
Verifies manifest publication, listing, retrieval, kill-switch toggle,
manifest_ref binding in /v1/agent/run, and budget.max_usd_per_run enforcement.
"""
import copy
import json
import uuid
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from core.main import app
from core.config import settings

EXAMPLE = Path(__file__).resolve().parent.parent / "docs" / "spec" / "examples" / "test-fixer.agent.json"


def base_manifest(**edits):
    data = copy.deepcopy(json.loads(EXAMPLE.read_text()))
    data["name"] = f"agent-{uuid.uuid4().hex[:6]}"
    data["version"] = "1.0.0"
    data["tools"] = ["read_file", "edit_file", "list_dir"]
    data["permissions"]["commands"] = []
    for dotted, value in edits.items():
        node = data
        *path, last = dotted.split("__")
        for key in path:
            node = node[key]
        node[last] = value
    return data


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from core.api import routes
    from core.storage.workspace_fs import WorkspaceFilesystem
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('test')\n")
    monkeypatch.setattr(routes, "_workspace_fs", WorkspaceFilesystem(root_dir=str(tmp_path)))
    monkeypatch.setattr(routes, "_active_agent_loops", {})
    monkeypatch.setattr(settings, "require_signed_manifests", False)
    with TestClient(app) as c:
        yield c


def test_manifest_registry_crud_and_kill_switch(client):
    manifest = base_manifest()
    agent_id = f"{manifest['name']}@1.0.0"

    # 1. Register manifest
    reg_res = client.post("/v1/agents/registry", json={"manifest": manifest})
    assert reg_res.status_code == 200, reg_res.text
    reg_data = reg_res.json()
    assert reg_data["registered"] is True
    assert reg_data["id"] == agent_id
    assert reg_data["enabled"] is True

    # Duplicate registration rejected
    dup_res = client.post("/v1/agents/registry", json={"manifest": manifest})
    assert dup_res.status_code == 400

    # 2. List manifests
    list_res = client.get("/v1/agents/registry")
    assert list_res.status_code == 200
    manifests = list_res.json()["manifests"]
    assert any(m["id"] == agent_id for m in manifests)

    # 3. Get single manifest
    get_res = client.get(f"/v1/agents/registry/{manifest['name']}/1.0.0")
    assert get_res.status_code == 200
    assert get_res.json()["name"] == manifest["name"]
    assert get_res.json()["version"] == "1.0.0"

    # 4. Kill-switch disable
    toggle_res = client.post(f"/v1/agents/registry/{manifest['name']}/1.0.0/toggle", json={"enabled": False})
    assert toggle_res.status_code == 200
    assert toggle_res.json()["enabled"] is False

    # 5. Run using disabled manifest_ref fails
    run_disabled = client.post("/v1/agent/run", json={"task_id": "task_dis", "manifest_ref": agent_id})
    assert run_disabled.status_code == 400
    assert "kill-switch" in run_disabled.json()["detail"]

    # 6. Re-enable via kill-switch and run succeeds
    toggle_on = client.post(f"/v1/agents/registry/{manifest['name']}/1.0.0/toggle", json={"enabled": True})
    assert toggle_on.status_code == 200
    assert toggle_on.json()["enabled"] is True

    run_ok = client.post("/v1/agent/run", json={"task_id": "task_en", "manifest_ref": agent_id})
    assert run_ok.status_code == 200
    assert run_ok.json()["manifest"]["name"] == manifest["name"]
    assert run_ok.json()["manifest"]["version"] == "1.0.0"


def test_cost_budget_metering_enforcement(client):
    manifest = base_manifest(budget__max_usd_per_run=0.05)
    run_res = client.post("/v1/agent/run", json={"task_id": "task_cost", "manifest": manifest})
    assert run_res.status_code == 200

    from core.api import routes
    agent = routes._active_agent_loops["task_cost"]
    assert agent.guard is not None
    assert agent.guard.usd_spent == 0.0

    # Step 1: within budget
    step1 = client.post("/v1/agent/step/task_cost", json={"tool_name": "read_file", "arguments": {"path": "src/app.py"}}).json()
    assert step1["step_result"]["status"] == "success"

    # Simulate model cost accumulation reaching and exceeding $0.05 cap
    agent.guard.record_cost(0.06)
    assert agent.guard.usd_spent == 0.06

    # Step 2: blocked due to cost_budget_exhausted
    step2 = client.post("/v1/agent/step/task_cost", json={"tool_name": "read_file", "arguments": {"path": "src/app.py"}}).json()
    assert step2["step_result"]["status"] == "denied_by_manifest"
    assert step2["step_result"]["code"] == "cost_budget_exhausted"
    assert "budget of $0.05 is exhausted" in step2["step_result"]["reason"]
