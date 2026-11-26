"""Isolated execution environments for the Keelway Runner (release defect D-004).

Implements the create/exec/snapshot/restore contract on top of the `docker`
CLI — the same zero-extra-dependency subprocess approach the OS sandbox
backends (`core/agents/sandbox.py`) use for seatbelt/bubblewrap.

Confinement model (parity with the OS sandbox invariants):
  * the container runs with `--network none` (no egress; there is no per-host
    allowlist, matching the sandbox network rule)
  * the workspace is the only host path mounted, read-write, at /work
  * the environment inside the container is scrubbed: a minimal PATH plus
    caller-approved variables only — no host secrets can leak through env
  * commands run without a shell (argv passthrough), with in-container
    `timeout -s KILL` enforcement and capped output

What this backend is NOT: `docker commit` snapshots cover only the
container's own writable layer. The bind-mounted /work directory is host
state and is NOT captured in a snapshot — workspace rollback stays the job
of /v1/checkpoints (git-stash snapshots). `snapshot()` reports this boundary
explicitly; callers must not assume workspace files are rolled back by
`restore()`.

Fail-closed contract: when the docker daemon is unavailable, `available()`
is False, `diagnostic_reason()` explains why, and `create()` raises
EnvironmentUnavailable rather than degrading to host execution.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

_WORK_MOUNT = "/work"
_ENV_PREFIX = "keelway-env-"
_SNAP_PREFIX = "keelway-env-snap-"
_DEFAULT_IMAGE = "alpine:latest"
_MINIMAL_ENV: Dict[str, str] = {
    "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
    "HOME": "/tmp",
    "TMPDIR": "/tmp",
}
_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.\-/:@]*$")
_MAX_ENV_NAME = 64
_TIMEOUT_BUFFER_S = 10


class EnvironmentUnavailable(RuntimeError):
    """No isolation backend usable for runner environments; refuse to run."""


class EnvironmentError(RuntimeError):
    """A docker operation failed; the detail carries the honest stderr."""


@dataclass
class RunnerEnvironment:
    """A live isolated environment created by `create()`."""

    env_id: str
    backend: str
    image: str
    workspace: str
    network: str
    created_at: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "env_id": self.env_id,
            "backend": self.backend,
            "image": self.image,
            "workspace": self.workspace,
            "network": self.network,
            "created_at": self.created_at,
        }


@dataclass
class EnvExecResult:
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool
    duration_ms: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "exit_code": self.exit_code,
            "stdout": self.stdout[-10000:],
            "stderr": self.stderr[-10000:],
            "timed_out": self.timed_out,
            "duration_ms": round(self.duration_ms, 2),
        }


@dataclass
class EnvSnapshot:
    """A container-layer snapshot. workspace_captured is always False:

    the bind-mounted /work directory is host state and `docker commit` does
    not include it — see the module docstring."""
    snapshot_id: str
    image_ref: str
    env_id: str
    label: str
    changes: List[str] = field(default_factory=list)
    workspace_captured: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "image_ref": self.image_ref,
            "env_id": self.env_id,
            "label": self.label,
            "changes": self.changes,
            "workspace_captured": self.workspace_captured,
        }


def _validate_name(value: str, kind: str) -> str:
    if not value or len(value) > _MAX_ENV_NAME or not _NAME_RE.match(value):
        raise ValueError(f"invalid {kind}: {value!r}")
    if ".." in value:
        raise ValueError(f"invalid {kind} (traversal): {value!r}")
    return value


class DockerRunnerBackend:
    """create/exec/snapshot/restore over the docker CLI."""

    name = "docker"
    _available: Optional[bool] = None
    _last_error: str = ""

    # ---- availability -------------------------------------------------
    @classmethod
    def _probe(cls) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["docker", "info", "--format", "{{.ServerVersion}}"],
            capture_output=True, text=True, timeout=10,
        )

    @classmethod
    def available(cls) -> bool:
        if cls._available is not None:
            return cls._available
        if shutil.which("docker") is None:
            cls._available = False
            cls._last_error = "docker binary not found on PATH"
            return False
        try:
            res = cls._probe()
            cls._available = res.returncode == 0
            cls._last_error = "" if cls._available else (res.stderr or f"docker info exited {res.returncode}").strip()
        except Exception as exc:
            cls._available = False
            cls._last_error = str(exc)
        return cls._available

    @classmethod
    def reset_probe_cache(cls) -> None:
        cls._available = None
        cls._last_error = ""

    @classmethod
    def diagnostic_reason(cls) -> str:
        if shutil.which("docker") is None:
            return "docker binary not found on PATH"
        if cls.available():
            return "ok"
        return cls._last_error or "docker daemon unreachable"

    # ---- low-level ----------------------------------------------------
    @staticmethod
    def _run(args: Sequence[str], timeout: int = 120) -> subprocess.CompletedProcess:
        res = subprocess.run(["docker", *args], capture_output=True, text=True, timeout=timeout)
        return res

    @classmethod
    def _must(cls, args: Sequence[str], timeout: int = 120, what: str = "docker") -> subprocess.CompletedProcess:
        res = cls._run(args, timeout=timeout)
        if res.returncode != 0:
            detail = (res.stderr or res.stdout or "").strip()
            raise EnvironmentError(f"{what} failed ({res.returncode}): {detail}")
        return res

    @staticmethod
    def new_env_id() -> str:
        return f"{_ENV_PREFIX}{uuid.uuid4().hex[:12]}"

    # ---- contract ------------------------------------------------------
    def create(
        self,
        workspace: Path,
        image: str = _DEFAULT_IMAGE,
        *,
        env_id: Optional[str] = None,
        env_allow: Sequence[str] = (),
        network: str = "none",
    ) -> RunnerEnvironment:
        """Create + start an isolated container.

        `docker create --network none` + bind-mounted workspace only, then
        `docker start`. The image must already be present locally — the
        backend does not pull implicitly (a failed create reports honestly).
        """
        if not self.available():
            raise EnvironmentUnavailable(f"docker backend unavailable: {self.diagnostic_reason()}")
        env_id = _validate_name(env_id or self.new_env_id(), "env_id")
        image = _validate_name(image, "image")
        ws = Path(workspace).resolve()
        if not ws.is_dir():
            raise ValueError(f"workspace is not a directory: {ws}")
        env_args: List[str] = []
        merged_env = dict(_MINIMAL_ENV)
        for key in env_allow:
            if key in merged_env:
                continue
            merged_env[key] = ""
        for key, val in merged_env.items():
            env_args += ["-e", f"{key}={val}"] if val else ["-e", key]
        create = self._must(
            [
                "create", "--name", env_id,
                "--network", network,
                "--workdir", _WORK_MOUNT,
                "-v", f"{ws}:{_WORK_MOUNT}",
                "-i", *env_args,
                "--entrypoint", "sleep",
                image, "infinity",
            ],
            what=f"docker create {env_id}",
        )
        self._must(["start", env_id], what=f"docker start {env_id}")
        _ = create
        return RunnerEnvironment(
            env_id=env_id, backend=self.name, image=image,
            workspace=str(ws), network=network, created_at=time.time(),
        )

    def exec(
        self,
        env_id: str,
        argv: Sequence[str],
        *,
        timeout: int = 30,
        max_output: int = 200_000,
        workdir: Optional[str] = None,
    ) -> EnvExecResult:
        """Run argv inside the environment. `timeout -s KILL` inside the
        container enforces the bound; the client-side wait adds a buffer so a
        wedged exec is still reported timed_out rather than hanging."""
        env_id = _validate_name(env_id, "env_id")
        if not argv:
            raise ValueError("empty argv")
        inner = ["timeout", "-s", "KILL", str(timeout), *argv]
        cmd = ["exec", "-i"]
        if workdir:
            cmd += ["-w", workdir]
        cmd += [env_id, *inner]
        start = time.perf_counter()
        try:
            res = subprocess.run(
                ["docker", *cmd], capture_output=True, text=True,
                timeout=timeout + _TIMEOUT_BUFFER_S,
            )
            timed_out = res.returncode == 124 or res.returncode == 137
            return EnvExecResult(
                exit_code=res.returncode,
                stdout=(res.stdout or "")[-max_output:],
                stderr=(res.stderr or "")[-max_output:],
                timed_out=timed_out,
                duration_ms=(time.perf_counter() - start) * 1000.0,
            )
        except subprocess.TimeoutExpired:
            try:
                self._run(["exec", env_id, "sh", "-c",
                           "kill -KILL -1 2>/dev/null || true"], timeout=10)
            except Exception:
                pass
            return EnvExecResult(
                exit_code=-1, stdout="", stderr="exec client timed out",
                timed_out=True, duration_ms=(time.perf_counter() - start) * 1000.0,
            )

    def snapshot(self, env_id: str, label: str = "") -> EnvSnapshot:
        """Commit the container layer to a snapshot image + diff listing.

        The mounted workspace is NOT captured (workspace_captured=False —
        see the module docstring)."""
        env_id = _validate_name(env_id, "env_id")
        if label and not _NAME_RE.match(label):
            raise ValueError(f"invalid snapshot label: {label!r}")
        tag = re.sub(r"[^a-zA-Z0-9_.-]", "-", (label or "snap").lower())[:32] or "snap"
        image_ref = f"{_SNAP_PREFIX}{env_id.removeprefix(_ENV_PREFIX)}:{tag}-{uuid.uuid4().hex[:8]}"
        diff = self._run(["diff", env_id], timeout=30)
        changes = [ln.strip() for ln in diff.stdout.splitlines() if ln.strip()] if diff.returncode == 0 else []
        commit = self._must(["commit", env_id, image_ref], timeout=300, what="docker commit")
        return EnvSnapshot(
            snapshot_id=commit.stdout.strip(),
            image_ref=image_ref,
            env_id=env_id, label=label or tag,
            changes=changes,
        )

    def restore(self, env_id: str, snapshot: EnvSnapshot) -> RunnerEnvironment:
        """Recreate the environment from a snapshot image.

        Docker cannot mutate a running container's layer in place, so
        restore = remove + recreate from the committed snapshot image with
        the same workspace mount and `--network none`, preserving env_id."""
        env_id = _validate_name(env_id, "env_id")
        image_ref = _validate_name(snapshot.image_ref, "image_ref")
        inspect = self._run(["inspect", env_id, "--format", "{{json .Mounts}}"], timeout=15)
        workspace = ""
        if inspect.returncode == 0:
            try:
                for m in json.loads(inspect.stdout):
                    if m.get("Destination") == _WORK_MOUNT:
                        workspace = m.get("Source", "")
            except Exception:
                workspace = ""
        self._must(["rm", "-f", env_id], what=f"docker rm {env_id}")
        env_args: List[str] = []
        for key, val in _MINIMAL_ENV.items():
            env_args += ["-e", f"{key}={val}"]
        create_args = [
            "create", "--name", env_id, "--network", "none",
            "--workdir", _WORK_MOUNT,
        ]
        if workspace:
            create_args += ["-v", f"{workspace}:{_WORK_MOUNT}"]
        create_args += ["-i", *env_args, "--entrypoint", "sleep", image_ref, "infinity"]
        self._must(create_args, what=f"docker create from {image_ref}")
        self._must(["start", env_id], what=f"docker start {env_id}")
        return RunnerEnvironment(
            env_id=env_id, backend=self.name, image=image_ref,
            workspace=workspace, network="none", created_at=time.time(),
        )

    def destroy(self, env_id: str, *, remove_snapshots: bool = True) -> Dict[str, Any]:
        """Remove the container and (optionally) its snapshot images."""
        env_id = _validate_name(env_id, "env_id")
        self._run(["rm", "-f", env_id], timeout=30)
        removed_images: List[str] = []
        if remove_snapshots:
            ls = self._run(
                ["images", "--format", "{{.Repository}}:{{.Tag}}", "--filter",
                 f"reference={_SNAP_PREFIX}{env_id.removeprefix(_ENV_PREFIX)}:*"],
                timeout=15,
            )
            for ref in ls.stdout.splitlines():
                ref = ref.strip()
                if ref and self._run(["rmi", ref], timeout=60).returncode == 0:
                    removed_images.append(ref)
        return {"env_id": env_id, "removed": True, "removed_snapshots": removed_images}

    def list_environments(self) -> List[Dict[str, Any]]:
        """Live keelway-env-* containers (running or stopped)."""
        res = self._run(
            ["ps", "-a", "--filter", f"name={_ENV_PREFIX}",
             "--format", "{{.Names}}\t{{.Image}}\t{{.Status}}"],
            timeout=15,
        )
        envs = []
        for line in res.stdout.splitlines():
            parts = line.split("\t")
            if len(parts) >= 3:
                envs.append({"env_id": parts[0], "image": parts[1], "status": parts[2]})
        return envs


def runner_environment_backend(name: Optional[str] = None):
    """Select an isolation backend for runner environments.

    `None` → docker when usable; raises EnvironmentUnavailable otherwise.
    Callers must refuse rather than fall back to unconfined host execution —
    the same fail-closed rule as core/agents/sandbox.py."""
    choice = name or "docker"
    if choice != DockerRunnerBackend.name:
        raise EnvironmentUnavailable(f"unknown runner backend: {choice!r}")
    if not DockerRunnerBackend.available():
        raise EnvironmentUnavailable(
            f"docker runner backend unavailable: {DockerRunnerBackend.diagnostic_reason()}"
        )
    return DockerRunnerBackend()
