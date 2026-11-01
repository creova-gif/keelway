import time

import pytest
from fastapi.testclient import TestClient

from core.main import app
from core.security.approval_rules import ApprovalRule, ApprovalRuleError, rule_matches, validate_scope


@pytest.mark.parametrize("tool,scope", [("write_file", "../x"), ("write_file", "/etc/passwd"), ("write_file", "*"), ("edit_file", "**/*"),
                                        ("write_file", ".keelway/approval_rules.json"), ("write_file", ".git/config"), ("read_file", "a.py"), ("run_command", " ")])
def test_unscoped_or_unsafe_rules_are_rejected(tool, scope):
    with pytest.raises(ApprovalRuleError):
        validate_scope(tool, scope)


def test_rules_match_path_globs_and_exact_commands_only():
    path_rule = ApprovalRule("r1", "edit_file", "src/*.py", "me", 0)
    assert rule_matches(path_rule, "edit_file", {"path": "src/a.py"})
    assert not rule_matches(path_rule, "write_file", {"path": "src/a.py"})
    assert not rule_matches(path_rule, "edit_file", {"path": "src/../.keelway/approval_rules.json"})
    assert not rule_matches(ApprovalRule("r2", "write_file", "*.json", "me", 0), "write_file", {"path": ".keelway/approval_rules.json"})
    cmd = ApprovalRule("r3", "run_command", "pytest -q", "me", 0)
    assert rule_matches(cmd, "run_command", {"command": "pytest -q"})
    assert not rule_matches(cmd, "run_command", {"command": "pytest -q; rm -rf ~"})


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from core.api import routes
    from core.storage.workspace_fs import WorkspaceFilesystem
    monkeypatch.setattr(routes, "_workspace_fs", WorkspaceFilesystem(root_dir=str(tmp_path)))
    monkeypatch.setattr(routes, "_active_agent_loops", {})
    with TestClient(app) as c:
        yield c


def _write(client, task, path, step="step_1"):
    return client.post(f"/v1/agent/step/{task}", json={"tool_name": "write_file", "arguments": {"path": path, "content": "x\n"}, "step_id": step}).json()


def test_allow_always_remembers_a_scoped_rule_until_revoked(client, tmp_path):
    client.post("/v1/agent/run", json={"task_id": "a1", "goal": "g", "steps": ["w", "w", "w"]})
    assert _write(client, "a1", "notes1.txt")["step_result"]["status"] == "paused_for_approval"
    approved = client.post("/v1/agent/approve/a1", json={"approved": True, "remember": {"scope": "notes*.txt"}}).json()
    assert approved["rule"]["scope"] == "notes*.txt" and (tmp_path / "notes1.txt").exists()

    auto = _write(client, "a1", "notes2.txt", "step_2")["step_result"]
    assert auto["status"] == "success" and auto["approved_by_rule"]["id"] == approved["rule"]["id"]
    assert _write(client, "a1", "other.txt", "step_3")["step_result"]["status"] == "paused_for_approval"
    kinds = [e["event_type"] for e in client.get("/v1/flight/tape/a1").json()["events"]]
    assert "approval_auto_granted" in kinds

    rules = client.get("/v1/approval-rules").json()["rules"]
    assert [r["id"] for r in rules] == [approved["rule"]["id"]]
    assert client.delete(f"/v1/approval-rules/{rules[0]['id']}").status_code == 200
    assert client.get("/v1/approval-rules").json()["rules"] == []
    actions = [e["action"] for e in client.get("/v1/audit?limit=50").json()]
    assert "approval_rule_create" in actions and "approval_rule_revoke" in actions


def test_rules_never_apply_to_ask_before_every_step_runs(client):
    client.post("/v1/agent/run", json={"task_id": "b1", "goal": "g", "steps": ["w", "w"]})
    _write(client, "b1", "n.txt")
    client.post("/v1/agent/approve/b1", json={"approved": True, "remember": {"scope": "*.txt"}})
    client.post("/v1/agent/run", json={"task_id": "b2", "goal": "g", "steps": ["w"], "policy": "confirm_all"})
    assert _write(client, "b2", "m.txt")["step_result"]["status"] == "paused_for_approval"


def test_unsafe_remember_scope_is_rejected_before_the_tool_runs(client, tmp_path):
    client.post("/v1/agent/run", json={"task_id": "c1", "goal": "g", "steps": ["w"]})
    _write(client, "c1", "keep.txt")
    assert client.post("/v1/agent/approve/c1", json={"approved": True, "remember": {"scope": "*"}}).status_code == 400
    assert not (tmp_path / "keep.txt").exists()
    assert client.get("/v1/agent/status/c1").json()["pending_approval"]["tool_name"] == "write_file"


def test_star_stays_in_one_directory_and_double_star_spans_them():
    one = ApprovalRule("r", "edit_file", "src/*.py", "me", 0)
    assert rule_matches(one, "edit_file", {"path": "src/a.py"})
    assert not rule_matches(one, "edit_file", {"path": "src/private/config.py"})
    deep = ApprovalRule("r", "edit_file", "src/**/*.py", "me", 0)
    assert rule_matches(deep, "edit_file", {"path": "src/a.py"}) and rule_matches(deep, "edit_file", {"path": "src/x/y/a.py"})


def test_symlinks_into_protected_state_never_match(tmp_path):
    from core.security.approval_rules import ApprovalRuleStore
    store = ApprovalRuleStore(tmp_path)
    store.add("write_file", "alias/*", "me")
    (tmp_path / ".keelway").mkdir(exist_ok=True)
    (tmp_path / "alias").symlink_to(tmp_path / ".keelway")
    assert store.match("write_file", {"path": "alias/approval_rules.json"}) is None
    (tmp_path / "real").mkdir()
    store.add("write_file", "real/*", "me")
    assert store.match("write_file", {"path": "real/a.txt"}) is not None


@pytest.mark.parametrize("content", ['{"rules": null}', '{"rules": [1, "x", null]}', "[]", "not json"])
def test_malformed_rule_files_mean_no_rules(tmp_path, content):
    from core.security.approval_rules import ApprovalRuleStore
    store = ApprovalRuleStore(tmp_path)
    store.path.parent.mkdir(parents=True)
    store.path.write_text(content)
    assert store.list() == [] and store.match("write_file", {"path": "a.txt"}) is None


def test_reapproving_an_existing_scope_does_not_log_a_second_creation(client):
    before = max((e["seq"] for e in client.get("/v1/audit?limit=1").json()), default=0)
    for task in ("d1", "d2"):
        client.post("/v1/agent/run", json={"task_id": task, "goal": "g", "steps": ["w"], "policy": "confirm_all"})
        _write(client, task, "same.txt")
        client.post(f"/v1/agent/approve/{task}", json={"approved": True, "remember": {"scope": "same.txt"}})
    creations = [e for e in client.get("/v1/audit?limit=200").json()
                 if e["seq"] > before and e["action"] == "approval_rule_create" and e["resource"] == "write_file:same.txt"]
    assert len(creations) == 1


def test_blank_remembered_scope_is_rejected_not_a_silent_one_time_approval(client, tmp_path):
    client.post("/v1/agent/run", json={"task_id": "b1", "goal": "g", "steps": ["w"]})
    _write(client, "b1", "blank.txt")
    r = client.post("/v1/agent/approve/b1", json={"approved": True, "remember": {"scope": "   "}})
    assert r.status_code == 400 and not (tmp_path / "blank.txt").exists()
    assert client.get("/v1/approval-rules").json()["rules"] == []


def test_recursive_glob_never_reaches_nested_protected_dirs():
    rule = ApprovalRule("r", "write_file", "src/**/*.json", "t", 0.0)
    assert rule_matches(rule, "write_file", {"path": "src/a/b.json"})
    for p in ("src/.keelway/approval_rules.json", "src/vendor/.git/config.json", "src/.kora/x.json"):
        assert not rule_matches(rule, "write_file", {"path": p})
    with pytest.raises(ApprovalRuleError):
        validate_scope("write_file", "src/.git/*")


def test_many_recursive_segments_match_in_polynomial_time():
    rule = ApprovalRule("r", "write_file", "/".join(["**"] * 5 + ["a", "**"] * 5) + "/z.py", "t", 0.0)
    start = time.monotonic()
    assert not rule_matches(rule, "write_file", {"path": "/".join(["a"] * 20) + "/y.py"})
    assert time.monotonic() - start < 1
