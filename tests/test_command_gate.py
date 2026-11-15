import json
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from core.agents import gate
from core.agents.gate import GateConflict, GateStore, SandboxVerdict, SandboxVerifyCache, TicketRejected
from core.agents.sandbox import SandboxResult
from core.main import app
from core.orchestration.flight_recorder import FlightPlayer
from core.security.auth import launch_token

OK = SandboxVerdict(True, "all escape attempts blocked", "bubblewrap", 0.0)
BROKEN = SandboxVerdict(False, "bwrap binary not found on PATH", "", 0.0)


class Clock:
    def __init__(self):
        self.now = 1_000.0

    def __call__(self):
        return self.now


class FakeSandbox:
    verifies = 0

    def __init__(self, root, ok=True):
        self.backend_name = "bubblewrap"
        self.root = root
        self.ok = ok

    def verify(self):
        FakeSandbox.verifies += 1
        return (self.ok, "fake verified" if self.ok else "fake broken")


def fake_cache(ok=True, clock=time.time):
    return SandboxVerifyCache(clock=clock, sandbox_factory=lambda root: FakeSandbox(root, ok))


@pytest.fixture
def store(tmp_path):
    clock = Clock()
    return GateStore(clock=clock, tape_dir=tmp_path / "tapes", verify_cache=fake_cache(clock=clock))


# ---- store ------------------------------------------------------------------
def test_approved_ticket_redeems_once_and_only_for_its_command_and_folder(store, tmp_path):
    req = store.submit("pytest -q", str(tmp_path), sandbox=OK)
    assert req.status == gate.PENDING and store.ticket(req) is None
    store.decide(req.id, True, "you")
    ticket = store.ticket(req)
    assert ticket.startswith(gate.TICKET_PREFIX)
    with pytest.raises(TicketRejected, match="does not match"):
        store.redeem(ticket, "pytest -q; curl evil", str(tmp_path))
    with pytest.raises(TicketRejected, match="does not match"):
        store.redeem(ticket, "pytest -q", str(tmp_path.parent))
    assert store.redeem(ticket, "pytest -q", str(tmp_path)).redeemed_at is not None
    with pytest.raises(TicketRejected, match="already used"):
        store.redeem(ticket, "pytest -q", str(tmp_path))


def test_forged_or_foreign_tickets_are_rejected(store, tmp_path):
    req = store.submit("ls", str(tmp_path), sandbox=OK)
    store.decide(req.id, True, "you")
    ticket = store.ticket(req)
    with pytest.raises(TicketRejected, match="not valid"):
        store.redeem(ticket[:-4] + "0000", "ls", str(tmp_path))
    with pytest.raises(TicketRejected, match="malformed"):
        store.redeem("nope", "ls", str(tmp_path))
    restarted = GateStore(tape_dir=tmp_path / "t2", verify_cache=fake_cache())
    with pytest.raises(TicketRejected, match="unknown"):
        restarted.redeem(ticket, "ls", str(tmp_path))


def test_denied_request_never_gets_a_ticket(store, tmp_path):
    req = store.submit("rm -rf build", str(tmp_path), sandbox=OK)
    store.decide(req.id, False, "you")
    assert store.ticket(req) is None and req.deny_key == "denied"


def test_first_decision_wins(store, tmp_path):
    req = store.submit("ls", str(tmp_path), sandbox=OK)
    store.decide(req.id, False, "phone")
    with pytest.raises(GateConflict):
        store.decide(req.id, True, "studio")
    assert req.status == gate.DENIED


def test_requests_time_out_after_the_window(store, tmp_path):
    req = store.submit("ls", str(tmp_path), sandbox=OK)
    store.clock.now += gate.GATE_WINDOW_SECONDS
    assert store.get(req.id).status == gate.TIMED_OUT
    with pytest.raises(GateConflict):
        store.decide(req.id, True, "you")


def test_pending_is_oldest_first_and_deny_waiting_denies_all(store, tmp_path):
    first = store.submit("one", str(tmp_path), sandbox=OK)
    store.clock.now += 1
    second = store.submit("two", str(tmp_path), sandbox=OK)
    assert [r.id for r in store.pending()] == [first.id, second.id]
    assert len(store.deny_waiting("you")) == 2
    assert store.pending() == []


def test_unverified_sandbox_is_denied_before_anyone_is_asked(store, tmp_path):
    req = store.submit("ls", str(tmp_path), sandbox=BROKEN)
    assert req.status == gate.DENIED and req.deny_key == "sandbox"
    assert store.pending() == []


def test_every_step_lands_in_a_sealed_tape(store, tmp_path):
    req = store.submit("echo hi", str(tmp_path), sandbox=OK)
    store.decide(req.id, True, "you")
    store.redeem(store.ticket(req), "echo hi", str(tmp_path))
    store.record_result(req.id, {"exit_code": 0})
    player = FlightPlayer(Path(req.tape_path))
    assert player.verify_integrity()[0]
    assert [e["event_type"] for e in player.events] == ["gate_requested", "gate_decided", "gate_redeemed", "gate_executed"]


def test_workspace_root_outside_cwd_falls_back_to_cwd(store, tmp_path):
    inner = tmp_path / "a"
    inner.mkdir()
    req = store.submit("ls", str(tmp_path), workspace_root=str(inner), sandbox=OK)
    assert req.workspace_root == str(tmp_path.resolve())


# ---- sandbox verify cache (U3) ------------------------------------------------
def test_verify_cache_reuses_until_ttl_and_clears_on_failure(tmp_path):
    clock = Clock()
    cache = fake_cache(clock=clock)
    FakeSandbox.verifies = 0
    assert cache.get(str(tmp_path)).ok
    cache.get(str(tmp_path))
    assert FakeSandbox.verifies == 1
    clock.now += gate.SANDBOX_VERIFY_TTL_SECONDS
    cache.get(str(tmp_path))
    assert FakeSandbox.verifies == 2
    cache.invalidate(str(tmp_path))
    cache.get(str(tmp_path))
    assert FakeSandbox.verifies == 3
    other = tmp_path / "other"
    other.mkdir()
    cache.get(str(other))
    assert FakeSandbox.verifies == 4


def test_failed_verification_is_not_cached(tmp_path):
    FakeSandbox.verifies = 0
    cache = fake_cache(ok=False)
    assert not cache.get(str(tmp_path)).ok
    cache.get(str(tmp_path))
    assert FakeSandbox.verifies == 2


# ---- API ----------------------------------------------------------------------
@pytest.fixture
def api(tmp_path, monkeypatch):
    test_store = GateStore(tape_dir=tmp_path / "tapes", verify_cache=fake_cache())
    monkeypatch.setattr(gate, "gate_store", test_store)
    with TestClient(app) as client:
        yield client, test_store


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def mint(client, role):
    resp = client.post("/v1/auth/tokens", json={"name": f"{role}-test", "role": role}, headers=bearer(launch_token()))
    assert resp.status_code == 201, resp.text
    return bearer(resp.json()["token"])


@pytest.mark.auth
def test_gate_token_can_ask_but_never_decide(api, tmp_path):
    client, _ = api
    g = mint(client, "gate")
    resp = client.post("/v1/gate/requests", json={"command": "pytest -q", "cwd": str(tmp_path)}, headers=g)
    assert resp.status_code == 201, resp.text
    rid = resp.json()["id"]
    assert resp.json()["sandbox"]["verified"] is True
    assert client.post(f"/v1/gate/requests/{rid}/decision", json={"allow": True}, headers=g).status_code == 403
    assert client.get("/v1/gate/pending", headers=g).status_code == 403
    assert client.get("/v1/tasks", headers=g).status_code == 403
    eng = mint(client, "engineer")
    assert client.post(f"/v1/gate/requests/{rid}/decision", json={"allow": True}, headers=eng).status_code == 403


@pytest.mark.auth
def test_phone_approves_and_gate_redeems_once(api, tmp_path):
    client, _ = api
    g, phone = mint(client, "gate"), mint(client, "phone")
    assert client.post("/v1/gate/requests", json={"command": "x", "cwd": str(tmp_path)}, headers=phone).status_code == 403
    rid = client.post("/v1/gate/requests", json={"command": "pytest -q", "cwd": str(tmp_path)}, headers=g).json()["id"]
    pending = client.get("/v1/gate/pending", headers=phone).json()
    assert pending["waiting"] == 1 and pending["requests"][0]["command"] == "pytest -q"
    assert "ticket" not in pending["requests"][0]
    decided = client.post(f"/v1/gate/requests/{rid}/decision", json={"allow": True}, headers=phone)
    assert decided.status_code == 200 and "ticket" not in decided.json()
    assert client.post(f"/v1/gate/requests/{rid}/decision", json={"allow": False}, headers=bearer(launch_token())).status_code == 409
    waited = client.get(f"/v1/gate/requests/{rid}/wait", params={"timeout": 0}, headers=g).json()
    assert waited["status"] == "approved" and waited["ticket"]
    body = {"ticket": waited["ticket"], "command": "pytest -q", "cwd": str(tmp_path)}
    redeemed = client.post("/v1/gate/redeem", json=body, headers=g)
    assert redeemed.status_code == 200 and redeemed.json()["sandbox"]["backend"] == "bubblewrap"
    again = client.post("/v1/gate/redeem", json=body, headers=g)
    assert again.status_code == 403 and "KW-G07" in again.json()["detail"]
    assert client.get(f"/v1/gate/requests/{rid}/wait", params={"timeout": 0}, headers=g).json()["ticket"] is None


@pytest.mark.auth
def test_timed_out_request_carries_the_fixed_reason(api, tmp_path):
    client, store = api
    store.window = 0
    g = mint(client, "gate")
    rid = client.post("/v1/gate/requests", json={"command": "ls", "cwd": str(tmp_path)}, headers=g).json()["id"]
    waited = client.get(f"/v1/gate/requests/{rid}/wait", params={"timeout": 0}, headers=g).json()
    assert waited["status"] == "timed_out" and waited["deny_code"] == "KW-G01"
    assert waited["deny_message"].startswith("Keelway blocked [KW-G01]: approval timed out after 5 min.")


# ---- hook ---------------------------------------------------------------------
def _approve_when_pending(store, allow=True):
    def run():
        for _ in range(200):
            pending = store.pending()
            if pending:
                store.decide(pending[0].id, allow, "you")
                return
            time.sleep(0.02)
    t = threading.Thread(target=run, daemon=True)
    t.start()
    return t


def test_hook_allow_rewrites_to_keelway_exec_and_exec_runs_in_the_sandbox(api, tmp_path, capfd):
    client, store = api
    gc = gate.GateClient("http://testserver", "", http=client)
    event = {"tool_name": "Bash", "tool_input": {"command": "echo 'hi' && echo two", "description": "d"}, "cwd": str(tmp_path)}
    _approve_when_pending(store)
    out = gate.handle_hook_event(event, gc, "/opt/keelway")["hookSpecificOutput"]
    assert out["permissionDecision"] == "allow"
    rewritten = out["updatedInput"]["command"]
    assert out["updatedInput"]["description"] == "d"
    argv = __import__("shlex").split(rewritten)
    assert argv[:3] == ["/opt/keelway", "exec", "--ticket"] and argv[4:] == ["--", "echo 'hi' && echo two"]

    ran = []

    class Box:
        def __init__(self, root, backend):
            self.root, self.backend = root, backend

        def run(self, command, timeout):
            ran.append((self.root, self.backend, command))
            return SandboxResult(0, "hi\ntwo\n", "", False, 4.0, "bubblewrap")

    assert gate.run_exec(argv[3], argv[5], gc, cwd=str(tmp_path), sandbox_factory=Box) == 0
    assert ran == [(str(tmp_path.resolve()), "bubblewrap", ("bash" if shutil.which("bash") else "sh") + " -c 'echo '\"'\"'hi'\"'\"' && echo two'")]
    assert "hi\ntwo" in capfd.readouterr().out
    assert gate.run_exec(argv[3], argv[5], gc, cwd=str(tmp_path), sandbox_factory=Box) == 126
    assert "KW-G07" in capfd.readouterr().err
    assert len(ran) == 1
    req = store.history()[0]
    assert req.result["exit_code"] == 0


def test_hook_deny_and_unsupported_and_protected(api, tmp_path):
    client, store = api
    gc = gate.GateClient("http://testserver", "", http=client)
    _approve_when_pending(store, allow=False)
    out = gate.handle_hook_event({"tool_name": "Bash", "tool_input": {"command": "rm -rf /"}, "cwd": str(tmp_path)}, gc, "keelway")
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "KW-G02" in out["hookSpecificOutput"]["permissionDecisionReason"]
    out = gate.handle_hook_event({"tool_name": "PowerShell", "tool_input": {"command": "dir"}, "cwd": str(tmp_path)}, gc, "keelway")
    assert "KW-G12" in out["hookSpecificOutput"]["permissionDecisionReason"]
    edit = {"tool_name": "Edit", "tool_input": {"file_path": ".claude/settings.local.json"}, "cwd": str(tmp_path)}
    out = gate.handle_hook_event(edit, gc, "keelway")
    assert "KW-G06" in out["hookSpecificOutput"]["permissionDecisionReason"]
    assert store.history()[0].deny_key == "protected"
    assert gate.handle_hook_event({"tool_name": "Edit", "tool_input": {"file_path": "src/app.py"}, "cwd": str(tmp_path)}, gc, "k") == {}
    assert gate.handle_hook_event({"tool_name": "Read", "tool_input": {}, "cwd": str(tmp_path)}, gc, "k") == {}


def test_hook_denies_when_keelway_is_not_running(tmp_path):
    gc = gate.GateClient("http://127.0.0.1:9", "")
    out = gate.handle_hook_event({"tool_name": "Bash", "tool_input": {"command": "ls"}, "cwd": str(tmp_path)}, gc, "keelway")
    assert "KW-G03" in out["hookSpecificOutput"]["permissionDecisionReason"]


def test_hook_cli_turns_garbage_input_into_a_deny(tmp_path):
    res = subprocess.run(
        [sys.executable, "-c", "import sys, cli; sys.exit(cli.main(['hook', 'gate']))"],
        input="not json", capture_output=True, text=True, cwd=Path(__file__).resolve().parents[1],
        env={"PATH": "/usr/bin:/bin", "KEELWAY_HOME": str(tmp_path), "HOME": str(tmp_path)},
    )
    assert res.returncode == 0, res.stderr
    assert json.loads(res.stdout.strip().splitlines()[-1])["hookSpecificOutput"]["permissionDecision"] == "deny"


@pytest.mark.parametrize("path,protected", [
    (".claude/settings.json", True), (".claude/settings.local.json", True), (".claude/hooks/check.cjs", True),
    (".keelway/recordings/x.json", True), ("sub/.keelway/x", True), (".claude/commands/x.md", False),
    ("src/settings.json", False), ("README.md", False),
])
def test_protected_paths(path, protected, tmp_path):
    assert gate.is_protected_path(path, str(tmp_path)) is protected


def test_keelway_home_is_protected(tmp_path, monkeypatch):
    monkeypatch.setenv("KEELWAY_HOME", str(tmp_path / "kh"))
    assert gate.is_protected_path(str(tmp_path / "kh" / "gate.json"), "/")


# ---- settings ------------------------------------------------------------------
def test_install_merges_with_existing_hooks_and_uninstall_restores(tmp_path):
    settings = tmp_path / ".claude" / "settings.json"
    settings.parent.mkdir()
    existing = {"hooks": {"PreToolUse": [{"matcher": "Skill", "hooks": [{"type": "command", "command": "node check.cjs"}]}]}, "model": "x"}
    settings.write_text(json.dumps(existing))
    digest = gate.install_settings(settings, "/opt/keelway")
    data = json.loads(settings.read_text())
    assert data["model"] == "x"
    matchers = [e["matcher"] for e in data["hooks"]["PreToolUse"]]
    assert matchers == ["Skill", gate.COMMAND_MATCHER, gate.EDIT_MATCHER]
    assert data["hooks"]["PreToolUse"][1]["hooks"][0]["timeout"] == 600
    assert gate.installed_entries_sha256(settings) == digest
    assert gate.install_settings(settings, "/opt/keelway") == digest
    assert len(json.loads(settings.read_text())["hooks"]["PreToolUse"]) == 3
    data["hooks"]["PreToolUse"][1]["matcher"] = "Nothing"
    settings.write_text(json.dumps(data))
    assert gate.installed_entries_sha256(settings) != digest
    assert gate.uninstall_settings(settings) == 2
    assert json.loads(settings.read_text()) == existing


@pytest.mark.skipif(shutil.which("sh") is None, reason="needs a POSIX shell")
def test_orphaned_hook_blocks_with_exit_2(tmp_path):
    command = gate.hook_shell_command(str(tmp_path / "gone" / "keelway"))
    res = subprocess.run([shutil.which("sh"), "-c", command], input="{}", capture_output=True, text=True, env={"PATH": str(tmp_path)})
    assert res.returncode == 2
    assert "KW-G09" in res.stderr and "pipx install keelway" in res.stderr


def test_deny_reasons_have_unique_codes_and_one_fix():
    codes = [r.code for r in gate.DENY_REASONS.values()]
    assert len(codes) == len(set(codes))
    assert all(r.reason and not r.reason.endswith(".") for r in gate.DENY_REASONS.values())


# ---- doctor (T4) -----------------------------------------------------------------
def _report(status):
    from core.system.doctor import SystemDoctorReport
    return SystemDoctorReport("t", status, "dev", "3", "Linux", [])


def test_doctor_exit_codes_follow_the_verdict():
    assert [_report(s).exit_code for s in ("HEALTHY", "DEGRADED", "BLOCKED")] == [0, 1, 2]


@pytest.mark.asyncio
async def test_doctor_blocks_on_tampered_hook_and_never_claims_unchecked_hardware(tmp_path, monkeypatch):
    from core.system.doctor import SystemDoctor
    monkeypatch.setenv("KEELWAY_HOME", str(tmp_path / "kh"))
    settings_file = tmp_path / ".claude" / "settings.local.json"
    digest = gate.install_settings(settings_file, "/opt/keelway")
    gate.save_gate_config({"settings_path": str(settings_file), "entries_sha256": digest, "api_url": "http://127.0.0.1:9"})
    settings_file.write_text(json.dumps({"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "keelway hook gate"}]}]}}))
    report = await SystemDoctor.run_diagnostics()
    sections = {s.name: s for s in report.sections}
    assert sections["Claude Code Command Gate"].status == "FAIL" and report.overall_status == "BLOCKED"
    assert "VERIFIED" not in json.dumps(sections["Tier 2 Hardware Security HAL"].details)


def test_symlinked_settings_stay_protected(tmp_path):
    outside = tmp_path / "elsewhere.json"
    outside.write_text("{}")
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "settings.local.json").symlink_to(outside)
    assert gate.is_protected_path(".claude/settings.local.json", str(tmp_path))


def test_redeem_refuses_when_the_tape_cannot_be_written(store, tmp_path, monkeypatch):
    req = store.submit("pytest -q", str(tmp_path), sandbox=OK)
    store.decide(req.id, True, "you")
    ticket = store.ticket(req)
    monkeypatch.setattr(store._tapes[req.id], "save_tape", lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")))
    with pytest.raises(TicketRejected, match="could not be recorded"):
        store.redeem(ticket, "pytest -q", str(tmp_path))


def test_sandbox_keeps_claude_settings_read_only():
    from core.agents.sandbox import PROTECTED_WRITE
    assert ".claude" in PROTECTED_WRITE


def test_uninstall_one_project_keeps_the_others(tmp_path, monkeypatch):
    import core.cli_gate as cli_gate

    monkeypatch.setenv("KEELWAY_HOME", str(tmp_path / "kh"))
    monkeypatch.setenv("KEELWAY_API_URL", "http://127.0.0.1:9")
    revoked, n = [], iter(range(10))

    async def mint(label):
        i = next(n)
        return f"id{i}", f"tok{i}"

    async def revoke(token_id):
        revoked.append(token_id)

    monkeypatch.setattr(cli_gate, "_mint_gate_token", mint)
    monkeypatch.setattr(cli_gate, "_revoke_token", revoke)
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    (b / ".claude").mkdir()
    (b / ".claude" / "settings.local.json").write_text("{not json")
    assert cli_gate.cmd_hook_install(project_dir=str(a), start=False, open_browser=False) == 0
    assert cli_gate.cmd_hook_install(project_dir=str(b), start=False, open_browser=False) == 1
    assert gate.load_gate_config()["token"] == "tok0" and revoked == []
    (b / ".claude" / "settings.local.json").write_text("{}")
    assert cli_gate.cmd_hook_install(project_dir=str(b), start=False, open_browser=False) == 0
    assert revoked == ["id0"]
    assert cli_gate.cmd_hook_uninstall(project_dir=str(a)) == 0
    config = gate.load_gate_config()
    assert config["token"] == "tok1" and config["settings_path"] == str(b / ".claude" / "settings.local.json")
    assert cli_gate.cmd_hook_uninstall(project_dir=str(b)) == 0
    assert not gate.gate_config_path().exists() and revoked == ["id0", "id1"]
