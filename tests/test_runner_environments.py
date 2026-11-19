"""
Tests for the isolated runner environment backend (D-004, KEEL-REL-064).

Unit tests pin the docker CLI contract (create/exec/snapshot/restore argv,
name validation, fail-closed availability). The live test is a real
create -> exec -> snapshot -> mutate -> restore -> exec -> destroy journey
against the local docker daemon; it skips when docker is absent, honestly.
"""

import shutil
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from core.main import app
from core.runner.environments import (
    DockerRunnerBackend,
    EnvironmentUnavailable,
    EnvSnapshot,
    runner_environment_backend,
)
from core.security.auth import launch_token


@pytest.fixture
def backend():
    DockerRunnerBackend.reset_probe_cache()
    yield DockerRunnerBackend()
    DockerRunnerBackend.reset_probe_cache()


def _completed(args, rc=0, out="", err=""):
    return subprocess.CompletedProcess(args, rc, out, err)


def test_available_false_without_docker_binary():
    DockerRunnerBackend.reset_probe_cache()
    with patch("shutil.which", return_value=None):
        assert DockerRunnerBackend.available() is False
    assert "docker" in DockerRunnerBackend.diagnostic_reason()
    DockerRunnerBackend.reset_probe_cache()


def test_create_refuses_when_daemon_down(backend):
    with patch.object(DockerRunnerBackend, "_probe", return_value=_completed("x", 1, "", "daemon off")):
        DockerRunnerBackend.reset_probe_cache()
        with pytest.raises(EnvironmentUnavailable):
            backend.create(Path("/tmp"))


def test_create_argv_contract(backend, tmp_path):
    calls = []

    def fake_run(args, timeout=120):
        calls.append(args)
        return _completed(args)

    with patch.object(DockerRunnerBackend, "available", return_value=True), \
         patch.object(DockerRunnerBackend, "_run", staticmethod(fake_run)):
        env = backend.create(tmp_path, image="alpine:latest", env_id="keelway-env-test1")

    create = calls[0]
    assert create[0] == "create"
    assert create[create.index("--network") + 1] == "none"
    assert create[create.index("--workdir") + 1] == "/work"
    assert f"{tmp_path.resolve()}:/work" in create
    assert "--entrypoint" in create
    assert calls[1] == ["start", "keelway-env-test1"]
    assert env.backend == "docker"


def test_exec_wraps_timeout_and_captures(backend):
    captured = {}

    def fake_subprocess_run(cmd, **kw):
        captured["cmd"] = cmd
        return _completed(cmd, 0, "hello\n", "")

    with patch("subprocess.run", side_effect=fake_subprocess_run):
        res = backend.exec("keelway-env-x", ["echo", "hi"], timeout=5)

    cmd = captured["cmd"]
    assert cmd[:2] == ["docker", "exec"]
    inner = cmd[cmd.index("keelway-env-x") + 1:]
    assert inner[:3] == ["timeout", "-s", "KILL"]
    assert inner[3] == "5"
    assert inner[4:] == ["echo", "hi"]
    assert res.exit_code == 0 and res.stdout == "hello\n" and not res.timed_out


def test_exec_marks_124_timed_out(backend):
    with patch("subprocess.run", return_value=_completed("x", 124, "", "Killed")):
        res = backend.exec("keelway-env-x", ["sleep", "60"], timeout=1)
    assert res.timed_out is True


def test_name_validation_rejects_injection(backend):
    for bad in ["; rm -rf /", "../etc", "a b", "", "-v"]:
        with pytest.raises(ValueError):
            backend.exec(bad, ["true"])


def test_snapshot_commits_with_diff(backend):
    calls = []

    def fake_run(args, timeout=120):
        calls.append(args)
        if args[0] == "diff":
            return _completed(args, 0, "C /tmp\nA /tmp/marker\n")
        return _completed(args, 0, "sha256:abc123\n")

    with patch.object(DockerRunnerBackend, "_run", staticmethod(fake_run)):
        snap = backend.snapshot("keelway-env-a1", label="base")

    assert calls[0] == ["diff", "keelway-env-a1"]
    assert calls[1][0] == "commit"
    assert "A /tmp/marker" in snap.changes
    assert snap.workspace_captured is False
    assert snap.snapshot_id == "sha256:abc123"


def test_restore_recreates_from_snapshot(backend, tmp_path):
    calls = []

    def fake_run(args, timeout=120):
        calls.append(args)
        if args[0] == "inspect":
            return _completed(args, 0, '[{"Destination":"/work","Source":"%s"}]' % tmp_path)
        return _completed(args)

    snap = EnvSnapshot(snapshot_id="sha256:x", image_ref="keelway-env-snap-a1:base-deadbeef",
                       env_id="keelway-env-a1", label="base")
    with patch.object(DockerRunnerBackend, "_run", staticmethod(fake_run)):
        env = backend.restore("keelway-env-a1", snap)

    assert calls[1] == ["rm", "-f", "keelway-env-a1"]
    create = calls[2]
    assert create[0] == "create"
    assert "keelway-env-snap-a1:base-deadbeef" in create
    assert f"{tmp_path}:/work" in create
    assert env.workspace == str(tmp_path)


def test_backend_selector_fails_closed():
    with pytest.raises(EnvironmentUnavailable):
        runner_environment_backend("nonexistent")
    with patch.object(DockerRunnerBackend, "available", return_value=False):
        with pytest.raises(EnvironmentUnavailable):
            runner_environment_backend()


def test_environment_status_route_honest():
    with TestClient(app) as c:
        owner = {"Authorization": f"Bearer {launch_token()}"}
        res = c.get("/v1/runner/environment/status", headers=owner)
    assert res.status_code == 200
    body = res.json()
    assert body["backend"] == "docker"
    assert body["contract"] == "create/exec/snapshot/restore"
    assert body["available"] == DockerRunnerBackend.available()
    assert isinstance(body["diagnostic"], str)


def test_environment_status_route_unavailable_honest():
    with patch.object(DockerRunnerBackend, "available", return_value=False), \
         patch.object(DockerRunnerBackend, "diagnostic_reason", return_value="docker binary not found on PATH"):
        with TestClient(app) as c:
            owner = {"Authorization": f"Bearer {launch_token()}"}
            res = c.get("/v1/runner/environment/status", headers=owner)
    body = res.json()
    assert res.status_code == 200
    assert body["available"] is False
    assert body["diagnostic"] == "docker binary not found on PATH"


def needs_docker(fn):
    """Live docker daemon required; skips honestly when absent."""
    fn = pytest.mark.live_docker(fn)
    return pytest.mark.skipif(
        shutil.which("docker") is None or not DockerRunnerBackend.available(),
        reason=f"docker daemon unavailable ({DockerRunnerBackend.diagnostic_reason()})",
    )(fn)


@needs_docker
def test_live_docker_create_exec_snapshot_restore(tmp_path):
    """Real journey: create -> exec writes inside both layers -> snapshot ->
    mutate -> restore -> container layer rolled back, mounted workspace not
    (documented boundary) -> destroy."""
    backend = DockerRunnerBackend()
    env = backend.create(tmp_path, image="alpine:latest")
    try:
        # exec: write inside the container layer (/tmp) and the mount (/work)
        r1 = backend.exec(env.env_id, ["sh", "-c", "echo layer > /tmp/layer.txt && echo one > /work/marker.txt"])
        assert r1.exit_code == 0, r1.stderr
        assert (tmp_path / "marker.txt").read_text().strip() == "one"

        # scrubbed env: no host secrets
        renv = backend.exec(env.env_id, ["env"])
        assert "OPENAI_API_KEY" not in renv.stdout

        # snapshot the container layer
        snap = backend.snapshot(env.env_id, label="v1")
        assert snap.snapshot_id.startswith("sha256:")

        # mutate both layers
        r2 = backend.exec(env.env_id, ["sh", "-c", "echo changed > /tmp/layer.txt && echo two > /work/marker.txt"])
        assert r2.exit_code == 0
        assert (tmp_path / "marker.txt").read_text().strip() == "two"

        # restore: container layer rolls back, mounted workspace does not
        env2 = backend.restore(env.env_id, snap)
        assert env2.env_id == env.env_id
        r3 = backend.exec(env2.env_id, ["cat", "/tmp/layer.txt"])
        assert r3.stdout.strip() == "layer"
        r4 = backend.exec(env2.env_id, ["cat", "/work/marker.txt"])
        assert r4.stdout.strip() == "two"  # mount is host state — documented, not snapshotted

        # timeout enforcement: a sleeping exec is killed inside the container
        r5 = backend.exec(env2.env_id, ["sleep", "30"], timeout=1)
        assert r5.timed_out is True

        # listing shows the env
        names = [e["env_id"] for e in backend.list_environments()]
        assert env.env_id in names
    finally:
        out = backend.destroy(env.env_id)
        assert out["removed"] is True
    assert env.env_id not in [e["env_id"] for e in backend.list_environments()]
