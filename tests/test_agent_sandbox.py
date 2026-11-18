import copy
import json
import os
import shlex
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import warnings
from pathlib import Path

import pytest

from core.agents import manifest as am
from core.agents.guard import ManifestNotRunnable, loop_from_manifest
from core.agents.sandbox import BubblewrapBackend, Sandbox, SandboxUnavailable, SeatbeltBackend, _sbpl_path, scrubbed_env
from core.storage.workspace_fs import WorkspaceFilesystem

warnings.filterwarnings("ignore", message=".*live_bubblewrap.*", category=pytest.PytestUnknownMarkWarning)

EXAMPLE = Path(__file__).resolve().parent.parent / "docs" / "spec" / "examples" / "test-fixer.agent.json"
def needs_backend(fn):
    """Seatbelt-only proof. Bubblewrap does not satisfy this marker.

    Profile A skips the test when sandbox-exec is absent. The release live
    gate still requires the live_seatbelt result and treats that skip as
    unavailable, not as a pass.
    """
    fn = pytest.mark.live_seatbelt(fn)
    return pytest.mark.skipif(
        not SeatbeltBackend.available(),
        reason="no OS sandbox backend on this platform (macOS seatbelt only)",
    )(fn)


def needs_any_os_sandbox(fn):
    """Runs on any host with a working OS sandbox (macOS seatbelt or Linux bubblewrap)."""
    fn = pytest.mark.live_os_isolation(fn)
    return pytest.mark.skipif(
        not (SeatbeltBackend.available() or BubblewrapBackend.available()),
        reason="no OS sandbox backend available (macOS seatbelt or Linux bubblewrap required)",
    )(fn)


def needs_bubblewrap(fn):
    """Linux bubblewrap live confinement proof."""
    fn = pytest.mark.live_bubblewrap(fn)
    return pytest.mark.skipif(
        not BubblewrapBackend.available(),
        reason=f"bubblewrap not usable on this machine ({BubblewrapBackend.diagnostic_reason()})",
    )(fn)


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
    monkeypatch.setattr(BubblewrapBackend, "available", classmethod(lambda cls: False))
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
async def test_workspace_sandbox_cannot_fall_back_to_a_host_command(ws):
    m = manifest(sandbox="workspace", permissions__commands=["/bin/echo hi"])
    agent = loop_from_manifest(m, "t", WorkspaceFilesystem(str(ws / "ws")), record_flight=False)
    assert agent.command_runner is None
    pending = await agent.execute_tool("run_command", {"command": "/bin/echo hi"})
    assert pending["status"] == "paused_for_approval"
    done = await agent.approve_pending(True)
    assert done["status"] == "error"
    assert "unavailable" in done["error"].lower()


def test_bubblewrap_backend_structure(tmp_path):
    assert isinstance(BubblewrapBackend.available(), bool)
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / ".git").mkdir()
    (ws / ".keelway").mkdir()
    (ws / ".kora").mkdir()
    broken_link = tmp_path / "broken-link"
    broken_link.symlink_to(tmp_path / "does-not-exist")
    tmp = tmp_path / "tmp"
    tmp.mkdir()
    env = scrubbed_env({"PATH": "/usr/bin:/bin", "ANTHROPIC_API_KEY": "sk-secret"}, tmp)
    wrapped = BubblewrapBackend.wrap(
        ["/bin/echo", "hello"],
        ws,
        tmp,
        [Path("/usr/lib"), broken_link, tmp_path / "missing-dir"],
        env=env,
    )
    assert wrapped[:3] == ["bwrap", "--ro-bind", "/"]
    assert wrapped[:4] == ["bwrap", "--ro-bind", "/", "/"]
    assert "--unshare-net" in wrapped
    assert "--unshare-pid" in wrapped
    assert "--die-with-parent" in wrapped
    assert "--new-session" in wrapped
    assert "--clearenv" in wrapped
    assert str(broken_link) not in wrapped and str(tmp_path / "missing-dir") not in wrapped
    assert "sk-secret" not in " ".join(wrapped)
    assert "--setenv" in wrapped
    assert "--" in wrapped
    sep = wrapped.index("--")
    assert wrapped[sep + 1 :] == ["/bin/echo", "hello"]


def test_bubblewrap_simulated_ubuntu_mount_ordering_and_protections(monkeypatch):
    import core.agents.sandbox as sbx

    ws = Path("/home/runner/work/keelway/keelway")
    tmp = Path("/tmp/keelway-sbx-ubuntu")
    py_root = Path("/opt/hostedtoolcache/Python/3.12.8/x64")
    user_bin = Path("/home/runner/.local/bin")
    existing_dirs = {
        Path("/home"),
        Path("/root"),
        Path("/mnt"),
        py_root,
        user_bin,
        ws,
        ws / ".git",
        ws / ".keelway",
        ws / ".kora",
        tmp,
    }
    monkeypatch.setattr(sbx, "_safe_is_dir", lambda p: p in existing_dirs)
    monkeypatch.setattr(sbx, "_safe_is_file", lambda p: False)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: Path("/home/runner")))

    wrapped = BubblewrapBackend.wrap(["/usr/bin/python3", "-V"], ws, tmp, [py_root, user_bin])

    def pair_idx(flag: str, val: str) -> int:
        for idx in range(len(wrapped) - 1):
            if wrapped[idx] == flag and wrapped[idx + 1] == val:
                return idx
        raise AssertionError(f"({flag!r}, {val!r}) not found in {wrapped}")

    def triple_idx(flag: str, src: str, dst: str) -> int:
        for idx in range(len(wrapped) - 2):
            if wrapped[idx] == flag and wrapped[idx + 1] == src and wrapped[idx + 2] == dst:
                return idx
        raise AssertionError(f"({flag!r}, {src!r}, {dst!r}) not found in {wrapped}")

    assert wrapped[:4] == ["bwrap", "--ro-bind", "/", "/"]
    tmpfs_home = pair_idx("--tmpfs", "/home")
    tmpfs_root = pair_idx("--tmpfs", "/root")
    tmpfs_tmp = pair_idx("--tmpfs", "/tmp")

    dir_user_bin = pair_idx("--dir", str(user_bin))
    ro_user_bin = triple_idx("--ro-bind", str(user_bin), str(user_bin))
    ro_py = triple_idx("--ro-bind", str(py_root), str(py_root))

    dir_ws = pair_idx("--dir", str(ws))
    bind_ws = triple_idx("--bind", str(ws), str(ws))
    dir_tmp = pair_idx("--dir", str(tmp))
    bind_tmp = triple_idx("--bind", str(tmp), str(tmp))

    ro_git = triple_idx("--ro-bind", str(ws / ".git"), str(ws / ".git"))
    tmpfs_keelway = pair_idx("--tmpfs", str(ws / ".keelway"))
    remount_keelway = pair_idx("--remount-ro", str(ws / ".keelway"))
    tmpfs_kora = pair_idx("--tmpfs", str(ws / ".kora"))
    remount_kora = pair_idx("--remount-ro", str(ws / ".kora"))

    remount_home = pair_idx("--remount-ro", "/home")
    remount_root = pair_idx("--remount-ro", "/root")

    # Critical ordering invariants on Ubuntu 24.04 (/home/runner/...):
    # 1. Masked tmpfs roots mount before --dir and child binds.
    assert tmpfs_home < dir_user_bin < ro_user_bin
    assert tmpfs_home < dir_ws < bind_ws
    assert tmpfs_tmp < dir_tmp < bind_tmp
    assert ro_py > 0
    # 2. Protected .git, .keelway, and .kora masks apply AFTER workspace --bind.
    assert bind_ws < ro_git
    assert bind_ws < tmpfs_keelway < remount_keelway
    assert bind_ws < tmpfs_kora < remount_kora
    # 3. Parent --remount-ro on /home and /root occurs AFTER all child mounts so mkdir/bind never hit EROFS.
    assert max(ro_user_bin, bind_ws, remount_keelway, remount_kora) < remount_home
    assert tmpfs_root < remount_root
    # 4. Namespace, session, and command arguments follow cleanly.
    for required_flag in ("--unshare-net", "--unshare-pid", "--die-with-parent", "--new-session"):
        assert required_flag in wrapped
    sep = wrapped.index("--")
    assert wrapped[sep + 1 :] == ["/usr/bin/python3", "-V"]


def test_bubblewrap_root_home_never_masks_filesystem_root(monkeypatch):
    import core.agents.sandbox as sbx

    monkeypatch.setattr(Path, "home", classmethod(lambda cls: Path("/root")))
    monkeypatch.setattr(sbx, "_safe_is_dir", lambda p: p in {Path("/"), Path("/home"), Path("/root"), Path("/tmp/ws"), Path("/tmp/t")})
    monkeypatch.setattr(sbx, "_safe_is_file", lambda p: False)
    wrapped = BubblewrapBackend.wrap(["/bin/true"], Path("/tmp/ws"), Path("/tmp/t"), [])
    for idx in range(len(wrapped) - 1):
        assert not (wrapped[idx] == "--tmpfs" and wrapped[idx + 1] == "/")
        assert not (wrapped[idx] == "--remount-ro" and wrapped[idx + 1] == "/")


@pytest.mark.parametrize("bad", ["/a\x00b", "/a\nb", "/a\rb", "/a\tb", "/a\x7fb"])
def test_bubblewrap_rejects_unsafe_control_characters_in_paths(bad, tmp_path):
    ok_ws = tmp_path / "ws"
    ok_tmp = tmp_path / "tmp"
    with pytest.raises(ValueError):
        BubblewrapBackend.wrap(["/bin/true"], Path(bad), ok_tmp, [])
    with pytest.raises(ValueError):
        BubblewrapBackend.wrap(["/bin/true"], ok_ws, Path(bad), [])
    with pytest.raises(ValueError):
        BubblewrapBackend.wrap(["/bin/true"], ok_ws, ok_tmp, [Path(bad)])


def test_sandbox_diagnose_and_bubblewrap_diagnostics(tmp_path, monkeypatch):
    import core.agents.sandbox as sbx

    diag = Sandbox(tmp_path).diagnose()
    assert set(diag) >= {
        "platform",
        "selected_backend",
        "seatbelt_available",
        "bubblewrap_available",
        "verified",
        "detail",
    }
    assert diag["platform"] == sys.platform
    assert isinstance(diag["seatbelt_available"], bool)
    assert isinstance(diag["bubblewrap_available"], bool)
    assert isinstance(diag["verified"], bool)

    # Simulate Linux AppArmor unprivileged userns restriction (Ubuntu 24.04 failure mode)
    monkeypatch.setattr(sbx.sys, "platform", "linux")
    monkeypatch.setattr(sbx.shutil, "which", lambda name: "/usr/bin/bwrap" if name == "bwrap" else "/bin/true")
    monkeypatch.setattr(
        sbx,
        "_read_sysctl",
        lambda p: "1" if "apparmor_restrict_unprivileged_userns" in str(p) else ("0" if "unprivileged_userns_clone" in str(p) else None),
    )
    monkeypatch.setattr(
        sbx.subprocess,
        "run",
        lambda *a, **kw: subprocess.CompletedProcess(a[0], 1, stdout="", stderr="bwrap: setting up uid map: Permission denied\n"),
    )
    reason = BubblewrapBackend.diagnostic_reason()
    assert "Permission denied" in reason
    assert "apparmor_restrict_unprivileged_userns=1" in reason
    assert "unprivileged_userns_clone=0" in reason

    # Simulate missing bwrap binary on Linux
    monkeypatch.setattr(sbx.shutil, "which", lambda name: None)
    assert "not found" in BubblewrapBackend.diagnostic_reason()


def test_a_bubblewrap_sandbox_that_leaks_is_rejected_by_the_self_test(tmp_path, monkeypatch):
    monkeypatch.setattr(BubblewrapBackend, "available", classmethod(lambda cls: True))
    monkeypatch.setattr(BubblewrapBackend, "wrap", staticmethod(lambda argv, ws, tmp, roots, env=None: argv))
    sb = Sandbox(tmp_path, backend="bubblewrap")
    ok, detail = sb.verify()
    assert ok is False and "NOT blocked" in detail
    with pytest.raises(SandboxUnavailable):
        sb.require_verified()


# ---- cross-platform OS confinement (macOS Seatbelt AND Linux Bubblewrap) ----

@needs_any_os_sandbox
def test_cross_platform_sandbox_confinement_and_diagnostics(ws, monkeypatch):
    (ws / "ws" / ".kora").mkdir(exist_ok=True)
    (ws / "ws" / ".kora" / "token").write_text("KORATOKEN")
    (ws / "ws" / ".git" / "HEAD").write_text("ref: refs/heads/main\n")

    monkeypatch.setenv("OPENAI_API_KEY", "sk-cross-platform-secret")
    monkeypatch.setenv("KEELWAY_API_TOKEN", "kw-cross-platform-secret")

    sb = Sandbox(ws / "ws")
    assert sb.backend_name in ("seatbelt", "bubblewrap")
    diag = sb.diagnose()
    assert diag["verified"] is True, diag
    assert diag["selected_backend"] == sb.backend_name

    # Normal workspace read/write and .git read succeed
    ok_rw = sb.run(f"{PY} -c \"open('src/check.txt','w').write('ok');print(open('.git/HEAD').read().strip())\"")
    assert ok_rw.exit_code == 0 and "refs/heads/main" in ok_rw.stdout
    assert (ws / "ws" / "src" / "check.txt").read_text() == "ok"

    # Outside-workspace read & write blocked
    outside_read = sb.run(f"{PY} -c \"print(open('{ws}/secret.txt').read())\"")
    assert outside_read.exit_code != 0 and "TOPSECRET" not in outside_read.stdout
    outside_write = sb.run(f"{PY} -c \"open('{ws}/escaped.txt','w').write('x')\"")
    assert outside_write.exit_code != 0 and not (ws / "escaped.txt").exists()

    # Protected .git write and .keelway / .kora read & write blocked
    assert sb.run(f"{PY} -c \"open('.git/pwn','w').write('x')\"").exit_code != 0
    assert sb.run(f"{PY} -c \"open('.keelway/agent_signing.key').read()\"").exit_code != 0
    assert sb.run(f"{PY} -c \"open('.keelway/pwn','w').write('x')\"").exit_code != 0
    assert sb.run(f"{PY} -c \"open('.kora/token').read()\"").exit_code != 0
    assert sb.run(f"{PY} -c \"open('.kora/pwn','w').write('x')\"").exit_code != 0

    # Scrubbed environment drops secrets
    env_res = sb.run("/usr/bin/env")
    assert env_res.exit_code == 0
    assert "cross-platform-secret" not in env_res.stdout

    # Missing binary normalized to 127 across both Seatbelt and Bubblewrap
    missing = sb.run("/no/such/keelway_binary")
    assert missing.exit_code == 127 and "not found" in missing.stderr

    # Loopback network blocked
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    listener.settimeout(0.4)
    port = listener.getsockname()[1]
    try:
        net_res = sb.run(f"{PY} -c \"import socket;socket.create_connection(('127.0.0.1',{port}),1)\"")
        assert net_res.exit_code != 0
        with pytest.raises(socket.timeout):
            listener.accept()
    finally:
        listener.close()


# ---- Linux Bubblewrap live confinement proofs --------------------------------

@needs_bubblewrap
def test_bubblewrap_passes_the_escape_self_test_and_hides_home(tmp_path):
    sb = Sandbox(tmp_path, backend="bubblewrap")
    ok, detail = sb.verify()
    assert ok, detail
    diag = sb.diagnose()
    assert diag["selected_backend"] == "bubblewrap" and diag["verified"] is True
    secret = Path(tempfile.mkdtemp(prefix=".keelway-home-secret-", dir=Path.home())) / "id_ed25519"
    try:
        secret.write_text("PRIVATEKEY")
        res = sb.run(f"{PY} -c \"print(open('{secret}').read())\"")
        assert res.exit_code != 0 and "PRIVATEKEY" not in res.stdout
    finally:
        shutil.rmtree(secret.parent, ignore_errors=True)


@needs_bubblewrap
def test_live_bubblewrap_confinement_under_home_workspace(ws, monkeypatch):
    (ws / "ws" / ".kora").mkdir(exist_ok=True)
    (ws / "ws" / ".kora" / "secret").write_text("KORASECRET")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-bwrap-secret")

    sb = Sandbox(ws / "ws", backend="bubblewrap")
    sb.require_verified()

    # Normal work succeeds inside workspace under $HOME (/home/runner/... on Linux CI)
    ok_res = sb.run(f"{PY} -c \"open('src/bwrap_ok.txt','w').write('bwrap');print(open('src/bwrap_ok.txt').read())\"")
    assert ok_res.exit_code == 0 and ok_res.stdout.strip() == "bwrap"
    assert ok_res.to_tool_result("x")["sandbox"] == "bubblewrap"

    # Outside-workspace reads/writes under $HOME fail
    assert sb.run(f"{PY} -c \"open('{ws}/secret.txt').read()\"").exit_code != 0
    assert sb.run(f"{PY} -c \"open('{ws}/escaped.txt','w').write('x')\"").exit_code != 0
    assert not (ws / "escaped.txt").exists()

    # Protected .git write and .keelway/.kora read & write fail
    assert sb.run(f"{PY} -c \"open('.git/config','w').write('x')\"").exit_code != 0
    assert sb.run(f"{PY} -c \"open('.keelway/agent_signing.key').read()\"").exit_code != 0
    assert sb.run(f"{PY} -c \"open('.keelway/x','w').write('x')\"").exit_code != 0
    assert sb.run(f"{PY} -c \"open('.kora/secret').read()\"").exit_code != 0
    assert sb.run(f"{PY} -c \"open('.kora/x','w').write('x')\"").exit_code != 0

    # Secrets scrubbed via --clearenv + --setenv
    env_res = sb.run("/usr/bin/env")
    assert env_res.exit_code == 0 and "sk-bwrap-secret" not in env_res.stdout

    # Network socket connect blocked via --unshare-net
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    listener.settimeout(0.4)
    port = listener.getsockname()[1]
    try:
        assert sb.run(f"{PY} -c \"import socket;socket.create_connection(('127.0.0.1',{port}),1)\"").exit_code != 0
        with pytest.raises(socket.timeout):
            listener.accept()
    finally:
        listener.close()


def test_verified_command_runner_refuses_without_a_backend(tmp_path, monkeypatch):
    import core.agents.sandbox as sbx

    monkeypatch.setattr(sbx, "_verified_sandboxes", {})
    monkeypatch.setattr(SeatbeltBackend, "available", staticmethod(lambda: False))
    monkeypatch.setattr(BubblewrapBackend, "available", staticmethod(lambda: False))
    runner, detail = sbx.verified_command_runner(tmp_path)
    assert runner is None and detail
