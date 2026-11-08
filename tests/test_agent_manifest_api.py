import copy
import json
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from core.agents import manifest as am
from core.agents.sandbox import SeatbeltBackend
from core.config import settings
from core.main import app
from core.security.auth import launch_token

EXAMPLE = Path(__file__).resolve().parent.parent / "docs" / "spec" / "examples" / "test-fixer.agent.json"


def base(**edits):
    """A read/edit agent with no run_command, so it is runnable on every platform."""
    data = copy.deepcopy(json.loads(EXAMPLE.read_text()))
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
    (tmp_path / "src" / "app.py").write_text("print('hi')\n")
    (tmp_path / "secret.txt").write_text("TOPSECRET\n")
    monkeypatch.setattr(routes, "_workspace_fs", WorkspaceFilesystem(root_dir=str(tmp_path)))
    monkeypatch.setattr(routes, "_active_agent_loops", {})
    monkeypatch.setattr(settings, "require_signed_manifests", False)
    with TestClient(app) as c:
        yield c


def audit(client, action):
    return [e for e in client.get("/v1/audit?limit=200").json() if e["action"] == action]


def run(client, manifest, task="m1", **extra):
    return client.post("/v1/agent/run", json={"task_id": task, "goal": "g", "steps": ["a", "b", "c"], "manifest": manifest, **extra})


def step(client, task, tool, args, step_id="step_1"):
    return client.post(f"/v1/agent/step/{task}", json={"tool_name": tool, "arguments": args, "step_id": step_id})


def test_manifest_run_binds_the_agent_and_audits_the_start_with_the_digest(client):
    res = run(client, base())
    assert res.status_code == 200, res.text
    body = res.json()
    digest = am.digest(am.validate(base()).manifest)
    assert body["manifest"]["digest"] == digest and body["manifest"]["signed"] is False
    assert body["manifest"]["max_steps"] == 40 and body["manifest"]["steps_used"] == 0
    assert any("max_usd_per_run" in n for n in body["not_enforced"])
    assert body["state"]["manifest"]["name"] == "test-fixer"
    started = audit(client, "agent_run_manifest")
    assert started and started[0]["allowed"] is True and digest in started[0]["resource"]
    assert client.get(f"/v1/agent/status/m1").json()["manifest"]["digest"] == digest
    assert client.get("/v1/audit/verify").json()["valid"] is True


def test_runs_without_a_manifest_are_unchanged(client):
    body = client.post("/v1/agent/run", json={"task_id": "plain", "goal": "g", "policy": "confirm_all"}).json()
    assert body["policy"] == "confirm_all" and "manifest" not in body
    assert client.get("/v1/agent/status/plain").json()["manifest"] is None


@pytest.mark.parametrize("bad", ["not an object", {"schema": "keelway.agent/v1"}, base(surprise=1), base(tools=["rm_rf"]), base(permissions__write_paths=["../x"])])
def test_invalid_manifests_are_rejected_audited_and_never_registered(client, bad):
    res = run(client, bad, task="bad1")
    assert res.status_code == 422
    assert res.json()["detail"]["errors"]
    assert client.get("/v1/agent/runs").json()["runs"] == []
    denied = audit(client, "agent_run_manifest")
    assert denied and denied[0]["allowed"] is False


def test_policy_must_agree_with_the_manifest(client):
    assert run(client, base(), policy="autonomous").status_code == 400
    assert run(client, base(), task="ok", policy="confirm_mutation").status_code == 200
    assert client.get("/v1/agent/status/ok").json()["policy"] == "confirm_mutation"


def test_duplicate_task_ids_still_conflict(client):
    assert run(client, base()).status_code == 200
    assert run(client, base()).status_code == 409


def test_a_run_that_cannot_run_here_is_refused_and_audited(client):
    data = base(sandbox="container")
    data["tools"].append("run_command")
    data["permissions"]["commands"] = ["pytest -q"]
    res = run(client, data, task="c1")
    assert res.status_code == 422 and "'container' is not built" in res.json()["detail"]
    assert audit(client, "agent_run_manifest")[0]["allowed"] is False
    assert client.get("/v1/agent/runs").json()["runs"] == []


# ---- signatures --------------------------------------------------------------

def signed_manifest(tmp_path, **edits):
    key = am.load_or_create_key(tmp_path)
    return json.loads(am.to_json(am.sign(am.validate(base(**edits)).manifest, key, "justin"))), key


def test_valid_signature_is_accepted_and_reported(client, tmp_path):
    data, _ = signed_manifest(tmp_path)
    res = run(client, data)
    assert res.status_code == 200 and res.json()["manifest"]["signed"] is True


def test_tampered_or_foreign_signatures_are_rejected(client, tmp_path):
    uid = uuid.uuid4().hex[:8]  # the audit log persists across runs, so identify this test's entries uniquely
    data, _ = signed_manifest(tmp_path)
    tampered = copy.deepcopy(data)
    tampered["budget"]["max_steps"] = 500
    res = run(client, tampered, task=f"t1-{uid}")
    assert res.status_code == 400 and "content_changed_since_signing" in res.json()["detail"]
    foreign = json.loads(am.to_json(am.sign(am.validate(base()).manifest, b"x" * 32, "mallory")))
    res = run(client, foreign, task=f"t2-{uid}")
    assert res.status_code == 400 and "wrong_key" in res.json()["detail"]
    assert client.get("/v1/agent/runs").json()["runs"] == []
    mine = [e for e in audit(client, "agent_run_manifest") if f"-{uid} " in e["resource"]]
    assert len(mine) == 2 and all(e["allowed"] is False for e in mine)


def test_signed_manifest_with_no_workspace_key_cannot_be_checked(client):
    data = json.loads(am.to_json(am.sign(am.validate(base()).manifest, b"k" * 32, "me")))
    res = run(client, data)
    assert res.status_code == 400 and "no signing key" in res.json()["detail"]


def test_require_signed_manifests_rejects_unsigned_ones(client, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "require_signed_manifests", True)
    assert run(client, base(), task="u1").status_code == 400
    data, _ = signed_manifest(tmp_path)
    assert run(client, data, task="s1").status_code == 200


# ---- enforcement through the API ----------------------------------------------

def test_out_of_scope_step_is_denied_audited_and_changes_nothing(client, tmp_path):
    run(client, base())
    res = step(client, "m1", "edit_file", {"path": "secret.txt", "target": "TOPSECRET", "replacement": "PWNED"}).json()
    assert res["step_result"]["status"] == "denied_by_manifest" and res["step_result"]["code"] == "path_not_in_scope"
    assert (tmp_path / "secret.txt").read_text() == "TOPSECRET\n"
    assert res["agent_state"]["pending_approval"] is None
    denied = audit(client, "manifest_denied")
    assert denied and denied[0]["allowed"] is False and "path_not_in_scope" in denied[0]["resource"]
    assert am.digest(am.validate(base()).manifest)[:19] in denied[0]["resource"]
    assert client.get("/v1/audit/verify").json()["valid"] is True


def test_in_scope_step_still_needs_human_approval_then_runs(client, tmp_path):
    run(client, base())
    res = step(client, "m1", "edit_file", {"path": "src/app.py", "target": "hi", "replacement": "yo"}).json()
    assert res["step_result"]["status"] == "paused_for_approval"
    done = client.post("/v1/agent/approve/m1", json={"approved": True}).json()
    assert done["approval_result"]["status"] == "success" and "yo" in (tmp_path / "src" / "app.py").read_text()
    assert client.get("/v1/agent/status/m1").json()["manifest"]["steps_used"] == 1


def test_step_budget_is_enforced_through_the_api(client):
    run(client, base(budget__max_steps=1))
    assert step(client, "m1", "read_file", {"path": "src/app.py"}).json()["step_result"]["status"] == "success"
    second = step(client, "m1", "read_file", {"path": "src/app.py"}, "step_2").json()["step_result"]
    assert second["code"] == "step_budget_exhausted"
    assert audit(client, "manifest_denied")


# ---- roles -------------------------------------------------------------------

@pytest.mark.auth
def test_autonomous_manifests_need_approve_tier3(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from core.api import routes
    from core.storage.workspace_fs import WorkspaceFilesystem
    monkeypatch.setattr(routes, "_workspace_fs", WorkspaceFilesystem(root_dir=str(tmp_path)))
    monkeypatch.setattr(routes, "_active_agent_loops", {})
    data = base(permissions__autonomy="autonomous", tools=["read_file", "list_dir"], permissions__write_paths=[])
    with TestClient(app) as c:
        owner = {"Authorization": f"Bearer {launch_token()}"}
        eng = c.post("/v1/auth/tokens", json={"name": "eng", "role": "engineer"}, headers=owner).json()
        eng_h = {"Authorization": f"Bearer {eng['token']}"}
        denied = c.post("/v1/agent/run", json={"task_id": "a1", "manifest": data}, headers=eng_h)
        assert denied.status_code == 403
        ok = c.post("/v1/agent/run", json={"task_id": "a2", "manifest": data}, headers=owner)
        assert ok.status_code == 200 and ok.json()["policy"] == "autonomous"
        assert c.get("/v1/audit/verify", headers=owner).json()["valid"] is True


# ---- dry run -----------------------------------------------------------------

def test_validate_endpoint_reports_without_starting_anything(client, tmp_path):
    out = client.post("/v1/agents/validate", json={"manifest": base()}).json()
    assert out["valid"] and out["runnable"] is True and out["signature"]["state"] == "unsigned"
    assert out["digest"] == am.digest(am.validate(base()).manifest) and out["not_enforced"]
    assert client.post("/v1/agents/validate", json=base()).json()["valid"]  # bare manifest also accepted
    assert client.get("/v1/agent/runs").json()["runs"] == []

    bad = client.post("/v1/agents/validate", json={"manifest": base(tools=["nope"])}).json()
    assert bad["valid"] is False and bad["errors"] and "runnable" not in bad

    container = base(sandbox="container")
    container["tools"].append("run_command")
    container["permissions"]["commands"] = ["pytest -q"]
    out = client.post("/v1/agents/validate", json={"manifest": container}).json()
    assert out["valid"] and out["runnable"] is False and "'container' is not built" in out["runnable_reason"]

    worktree = base()
    worktree["tools"].append("run_command")
    worktree["permissions"]["commands"] = ["pytest -q"]
    out = client.post("/v1/agents/validate", json={"manifest": worktree}).json()
    from core.agents.sandbox import Sandbox
    can_run = Sandbox(tmp_path).verify()[0]
    assert out["runnable"] is can_run  # true on a machine that passes the self-test, false elsewhere
    if not out["runnable"]:
        assert "verified sandbox" in out["runnable_reason"]


def test_validate_flags_a_bad_signature_as_not_runnable(client, tmp_path):
    data, _ = signed_manifest(tmp_path)
    data["budget"]["max_steps"] = 99
    out = client.post("/v1/agents/validate", json={"manifest": data}).json()
    assert out["signature"]["state"] == "invalid" and out["runnable"] is False


def test_plain_studio_runs_get_commands_only_through_a_verified_sandbox(client):
    from core.agents.sandbox import Sandbox
    from core.api import routes

    assert client.post("/v1/agent/run", json={"task_id": "plain", "goal": "g", "steps": ["a"], "policy": "autonomous"}).status_code == 200
    agent = routes._active_agent_loops["plain"]
    res = step(client, "plain", "run_command", {"command": "/bin/echo confined-hello"}).json()["step_result"]
    if Sandbox(agent.fs.root).verify()[0]:
        assert agent.command_runner is not None
        assert res["status"] == "success" and "confined-hello" in json.dumps(res)
        leak = step(client, "plain", "run_command", {"command": f"/bin/cat {Path.home() / '.bashrc'}"}, "step_2").json()["step_result"]
        assert "PS1" not in json.dumps(leak)
    else:
        assert agent.command_runner is None and res["status"] != "success"
        assert "command execution is unavailable" in json.dumps(res)
