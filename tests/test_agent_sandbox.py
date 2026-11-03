import copy
import json
import os
import shlex
import socket
import sys
import time
from pathlib import Path

import pytest

from core.agents import manifest as am
from core.agents.guard import ManifestNotRunnable, loop_from_manifest
from core.agents.sandbox import BubblewrapBackend, Sandbox, SandboxUnavailable, SeatbeltBackend, _sbpl_path, scrubbed_env
from core.storage.workspace_fs import WorkspaceFilesystem

EXAMPLE = Path(__file__).resolve().parent.parent / "docs" / "spec" / "examples" / "test-fixer.agent.json"
needs_backend = pytest.mark.skipif(not SeatbeltBackend.available(), reason="no OS sandbox backend on this platform (macOS seatbelt only)")
PY = shlex.quote(sys.executable)


def manifest(**edits):
    data = copy.deepcopy(json.loads(EXAMPLE.read_text()))
    for dotted, value in edits.items():
        node = data
        *path, last = dotted.split("__")
        for key in path:
            node = node[key]
        node[last] = value
    report = am.validate(data)
    assert report.ok, report.errors
    return report.manifest


@pytest.fixture
def ws(tmp_path_factory):
    # Under the real home, so "outside the workspace but under /Users" is a meaningful location.
    try:
        root = Path(os.path.expanduser("~")) / f".keelway-test-{os.getpid()}-{time.time_ns()}"
        (root / "ws" / ".git").mkdir(parents=True)
    except (PermissionError, OSError):
        root = tmp_path_factory.mktemp("keelway-test")
        (root / "ws" / ".git").mkdir(parents=True, exist_ok=True)
    (root / "ws" / ".keelway").mkdir(exist_ok=True)
    (root / "ws" / ".keelway" / "agent_signing.key").write_text("SIGNINGKEY")
    (root / "ws" / "src").mkdir(exist_ok=True)
    (root / "secret.txt").write_text("TOPSECRET")
    yield root
    import shutil
    shutil.rmtree(root, ignore_errors=True)


# ---- always runs, any platform ------------------------------------------------

def test_scrubbed_env_drops_every_secret_and_redirects_home(tmp_path):
    parent = {"PATH": "/usr/bin", "LANG": "en_US.UTF-8", "ANTHROPIC_API_KEY": "sk-1", "OPENAI_API_KEY": "sk-2", "AWS_SECRET_ACCESS_KEY": "x",
              "GITHUB_TOKEN": "t", "SSH_AUTH_SOCK": "/tmp/agent", "HOME": "/Users/real", "KEELWAY_API_TOKEN": "k", "CUSTOM": "keepme"}
    env = scrubbed_env(parent, tmp_path, extra_allow=("CUSTOM",))
    assert set(env) == {"PATH", "LANG", "CUSTOM", "HOME", "TMPDIR", "GIT_CONFIG_GLOBAL", "GIT_CONFIG_NOSYSTEM", "GIT_TERMINAL_PROMPT"}
    assert env["HOME"] == str(tmp_path) and "sk-" not in json.dumps(env)


def test_scrubbed_env_always_has_a_path():
    assert scrubbed_env({}, Path("/tmp"))["PATH"]


def test_profile_text_denies_network_and_protects_state_after_the_allows():
    prof = SeatbeltBackend.profile(Path("/work/ws"), Path("/tmp/t"), [Path("/opt/py")])
    assert "(deny network*)" in prof
    allow_write = prof.index('(allow file-write* (subpath "/work/ws")')
    deny_git = prof.index('(deny file-write* (subpath "/work/ws/.git")')
    assert deny_git > allow_write  # last matching rule wins, so protection must come after the allow
    assert '(deny file-read* (subpath "/work/ws/.keelway")' in prof
    assert '(subpath "/Users")' in prof


@pytest.mark.parametrize("bad", ['/a"b', "/a\\b", "/a\nb", "/a\x00b"])
def test_paths_that_could_break_out_of_the_profile_are_rejected(bad):
    with pytest.raises(ValueError):
        _sbpl_path(Path(bad))


def test_no_backend_means_refuse_not_run(tmp_path):
    sb = Sandbox(tmp_path, backend="")
    assert not sb.available
    with pytest.raises(SandboxUnavailable):
        sb.run("/bin/echo hi")
    ok, detail = sb.verify()
    assert ok is False and "no backend" in detail
    with pytest.raises(SandboxUnavailable):
        sb.require_verified()


def test_loop_fails_closed_when_the_sandbox_cannot_be_verified(tmp_path, monkeypatch):
    monkeypatch.setattr(SeatbeltBackend, "available", staticmethod(lambda: False))
    with pytest.raises(ManifestNotRunnable, match="verified sandbox"):
        loop_from_manifest(manifest(), "t", WorkspaceFilesystem(str(tmp_path)), record_flight=False)


def test_a_sandbox_that_leaks_is_rejected_by_the_self_test(tmp_path, monkeypatch):
    # Simulate a broken backend: confinement does nothing. verify() must catch it.
    monkeypatch.setattr(SeatbeltBackend, "available", staticmethod(lambda: True))
    monkeypatch.setattr(SeatbeltBackend, "wrap", staticmethod(lambda argv, profile: argv))
    ok, detail = Sandbox(tmp_path, backend="seatbelt").verify()
    assert ok is False and "NOT blocked" in detail


def test_network_allowlist_with_commands_is_refused_before_anything_runs(tmp_path):
    m = manifest(permissions__network="allowlist", permissions__network_allow=["pypi.org"])
    with pytest.raises(ManifestNotRunnable, match="network"):
        loop_from_manifest(m, "t", WorkspaceFilesystem(str(tmp_path)), record_flight=False)


# ---- real confinement, macOS ------------------------------------------------

@needs_backend
def test_self_test_passes_on_this_machine(ws):
    ok, detail = Sandbox(ws / "ws").verify()
    assert ok, detail


@needs_backend
def test_secrets_in_the_parent_environment_do_not_reach_commands(ws, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-must-not-leak")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "aws-must-not-leak")
    res = Sandbox(ws / "ws").run("/usr/bin/env")
    assert res.exit_code == 0
    assert "must-not-leak" not in res.stdout and "must-not-leak" not in res.stderr
    assert "ANTHROPIC" not in res.stdout


@needs_backend
def test_cannot_read_or_write_outside_the_workspace(ws):
    sb = Sandbox(ws / "ws")
    read = sb.run(f"{PY} -c \"print(open('{ws}/secret.txt').read())\"")
    assert read.exit_code != 0 and "TOPSECRET" not in read.stdout
    write = sb.run(f"{PY} -c \"open('{ws}/escaped.txt','w').write('x')\"")
    assert write.exit_code != 0 and not (ws / "escaped.txt").exists()
    # HOME inside the sandbox is a private temp dir, so use the REAL home path to test an escape.
    target = Path.home() / f".keelway-escape-{os.getpid()}"
    assert sb.run(f"{PY} -c \"open('{target}','w').write('x')\"").exit_code != 0
    assert not target.exists()


@needs_backend
def test_can_do_normal_work_inside_the_workspace(ws):
    sb = Sandbox(ws / "ws")
    res = sb.run(f"{PY} -c \"open('src/out.txt','w').write('hello');print(open('src/out.txt').read())\"")
    assert res.exit_code == 0 and res.stdout.strip() == "hello"
    assert (ws / "ws" / "src" / "out.txt").read_text() == "hello"
    assert res.to_tool_result("x")["sandbox"] == "seatbelt"


@needs_backend
def test_keelway_state_and_git_internals_are_protected_inside_the_workspace(ws):
    sb = Sandbox(ws / "ws")
    assert sb.run(f"{PY} -c \"print(open('.keelway/agent_signing.key').read())\"").stdout.strip() == ""
    assert sb.run(f"{PY} -c \"open('.keelway/agent_signing.key','w').write('pwned')\"").exit_code != 0
    assert (ws / "ws" / ".keelway" / "agent_signing.key").read_text() == "SIGNINGKEY"
    assert sb.run(f"{PY} -c \"open('.git/config','w').write('x')\"").exit_code != 0
    assert not (ws / "ws" / ".git" / "config").exists()


@needs_backend
def test_no_network_even_to_loopback(ws):
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    listener.settimeout(0.5)
    port = listener.getsockname()[1]
    try:
        res = Sandbox(ws / "ws").run(f"{PY} -c \"import socket;socket.create_connection(('127.0.0.1',{port}),2)\"")
        assert res.exit_code != 0
        with pytest.raises(socket.timeout):
            listener.accept()
    finally:
        listener.close()


@needs_backend
def test_subprocesses_stay_confined(ws):
    code = f"import subprocess;r=subprocess.run(['/bin/cat','{ws}/secret.txt'],capture_output=True,text=True);print('OUT:'+r.stdout);print('RC:'+str(r.returncode))"
    res = Sandbox(ws / "ws").run(f"{PY} -c \"{code}\"")
    assert "TOPSECRET" not in res.stdout and "RC:0" not in res.stdout


@needs_backend
def test_commands_are_not_run_through_a_shell(ws):
    res = Sandbox(ws / "ws").run("/bin/echo a; touch pwned.txt")
    assert res.exit_code == 0 and res.stdout.strip() == "a; touch pwned.txt"
    assert not (ws / "ws" / "pwned.txt").exists()
    res = Sandbox(ws / "ws").run("/bin/echo $HOME")
    assert res.stdout.strip() == "$HOME"


@needs_backend
def test_timeout_kills_the_whole_process_group(ws):
    sb = Sandbox(ws / "ws")
    marker = ws / "ws" / "still_running.txt"
    code = f"import subprocess,time;subprocess.Popen(['/bin/sh','-c','sleep 3; echo x > still_running.txt']);time.sleep(30)"
    start = time.time()
    res = sb.run(f"{PY} -c \"{code}\"", timeout=1)
    assert res.timed_out and time.time() - start < 10
    time.sleep(3.5)
    assert not marker.exists()  # the grandchild was killed too


@needs_backend
def test_output_is_capped_and_missing_commands_are_reported(ws):
    res = Sandbox(ws / "ws").run(f"{PY} -c \"print('x'*500000)\"")
    assert len(res.stdout) <= 200_000
    res = Sandbox(ws / "ws").run("/no/such/binary")
    assert res.exit_code == 127 and "not found" in res.stderr


# ---- through the agent loop -------------------------------------------------

@needs_backend
@pytest.mark.asyncio
async def test_loop_runs_allowed_commands_in_the_sandbox_with_a_scrubbed_env(ws, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-must-not-leak")
    m = manifest(permissions__commands=["/usr/bin/env"])
    agent = loop_from_manifest(m, "t", WorkspaceFilesystem(str(ws / "ws")), record_flight=False)
    pending = await agent.execute_tool("run_command", {"command": "/usr/bin/env"})
    assert pending["status"] == "paused_for_approval"  # confined AND still human-approved
    done = await agent.approve_pending(True)
    assert done["status"] == "success" and done["result"]["sandbox"] == "seatbelt"
    assert "must-not-leak" not in done["result"]["stdout"]


@needs_backend
@pytest.mark.asyncio
async def test_autonomous_agent_may_run_commands_only_because_the_sandbox_is_verified(ws):
    data = json.loads(EXAMPLE.read_text())
    data["tools"] = ["read_file", "run_command"]
    data["permissions"].update(autonomy="autonomous", write_paths=[], commands=["/bin/echo hello"])
    report = am.validate(data)
    assert report.ok, report.errors
    agent = loop_from_manifest(report.manifest, "t", WorkspaceFilesystem(str(ws / "ws")), record_flight=False)
    res = await agent.execute_tool("run_command", {"command": "/bin/echo hello"})
    assert res["status"] == "success" and res["result"]["stdout"].strip() == "hello" and res["result"]["sandbox"] == "seatbelt"
    denied = await agent.execute_tool("run_command", {"command": "/bin/echo hello; cat secret.txt"})
    assert denied["status"] == "denied_by_manifest"


@needs_backend
@pytest.mark.asyncio
async def test_sandbox_workspace_manifests_keep_the_old_unconfined_path(ws):
    m = manifest(sandbox="workspace", permissions__commands=["/bin/echo hi"])
    agent = loop_from_manifest(m, "t", WorkspaceFilesystem(str(ws / "ws")), record_flight=False)
    assert agent.command_runner is None
    await agent.execute_tool("run_command", {"command": "/bin/echo hi"})
    done = await agent.approve_pending(True)
    assert done["status"] == "success" and "sandbox" not in done["result"]


def test_bubblewrap_backend_structure(tmp_path):
    assert isinstance(BubblewrapBackend.available(), bool)
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / ".git").mkdir()
    tmp = tmp_path / "tmp"
    tmp.mkdir()
    wrapped = BubblewrapBackend.wrap(["/bin/echo", "hello"], ws, tmp, [Path("/usr/lib")])
    assert wrapped[0] == "bwrap"
    assert "--unshare-net" in wrapped
    assert "--ro-bind" in wrapped
    assert str(ws) in wrapped
    assert str(tmp) in wrapped
    assert "--" in wrapped
    assert wrapped[-2:] == ["/bin/echo", "hello"]

