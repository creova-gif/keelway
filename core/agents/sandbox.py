"""OS-level confinement for commands an agent runs.

What a sandboxed command can and cannot do (macOS seatbelt backend, the only one built):
  * run with a scrubbed environment: no API keys, tokens or shell secrets are inherited
  * write only inside the workspace and a private per-run temp directory; never `.git` or `.keelway`
  * read the workspace, the Python environment and PATH tools, but not other files under /Users, /Volumes
    or root's home (so no ~/.ssh, no other projects)
  * open no network connections at all (there is no per-host allowlist, so a manifest that wants one is refused)
  * run without a shell (`shell=False`), in its own process group that is killed on timeout, with capped output

What it does NOT do: it is not a container or VM. System files outside the denied areas stay readable, the kernel
is shared, and Apple marks `sandbox-exec` deprecated (it still works and is what many tools use). On any other
platform there is no backend, `Sandbox.require_verified()` raises, and callers must refuse to run commands
rather than run them unconfined.

The self-test (`Sandbox.verify()`) actually tries to escape on this machine and only passes if every attempt
fails while normal work succeeds. It is the only thing that should be trusted, not the profile text.
"""
from __future__ import annotations

import os
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

ENV_KEEP = ("PATH", "LANG", "LC_ALL", "LC_CTYPE", "TERM", "TZ", "VIRTUAL_ENV")
# Areas that hold other people's and other projects' files. The workspace is allowed back in afterwards.
DENY_READ_ROOTS = ("/Users", "/Volumes", "/private/var/root")
PROTECTED_WRITE = (".git", ".keelway", ".kora")
PROTECTED_READ = (".keelway", ".kora")


class SandboxUnavailable(RuntimeError):
    """No working confinement backend on this machine; the caller must refuse to run the command."""


@dataclass
class SandboxResult:
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool
    duration_ms: float
    backend: str

    def to_tool_result(self, command: str) -> Dict[str, object]:
        return {
            "command": command, "exit_code": self.exit_code, "stdout": self.stdout[-10000:],
            "stderr": self.stderr[-10000:], "duration_ms": round(self.duration_ms, 2),
            "timed_out": self.timed_out, "sandbox": self.backend,
        }


def _sbpl_path(path: Path) -> str:
    text = str(path)
    if any(ch in text for ch in '"\\\n\r\x00'):
        raise ValueError(f"unsupported character in sandbox path: {text!r}")
    return f'(subpath "{text}")'


def scrubbed_env(parent: Mapping[str, str], home: Path, extra_allow: Sequence[str] = ()) -> Dict[str, str]:
    """A minimal environment. Only named variables survive; everything else (keys, tokens, cloud creds) is dropped."""
    env = {k: v for k, v in parent.items() if k in ENV_KEEP or k in extra_allow}
    env.update(HOME=str(home), TMPDIR=str(home), GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_NOSYSTEM="1", GIT_TERMINAL_PROMPT="0")
    env.setdefault("PATH", "/usr/bin:/bin:/usr/sbin:/sbin")
    return env


class SeatbeltBackend:
    name = "seatbelt"
    _available: Optional[bool] = None

    @classmethod
    def available(cls) -> bool:
        if cls._available is not None:
            return cls._available
        if sys.platform != "darwin" or shutil.which("sandbox-exec") is None:
            cls._available = False
            return False
        try:
            res = subprocess.run(
                ["/usr/bin/sandbox-exec", "-p", "(version 1)(allow default)", "/usr/bin/true"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=2,
            )
            cls._available = (res.returncode == 0)
        except Exception:
            cls._available = False
        return cls._available

    @staticmethod
    def profile(workspace: Path, tmp: Path, read_roots: Sequence[Path]) -> str:
        ws = workspace
        lines = [
            "(version 1)",
            "(allow default)",
            "(deny network*)",
            "(deny file-write*)",
            f"(allow file-write* {_sbpl_path(ws)} {_sbpl_path(tmp)} (literal \"/dev/null\") (literal \"/dev/dtracehelper\"))",
            "(deny file-read* " + " ".join(_sbpl_path(Path(p)) for p in DENY_READ_ROOTS) + ")",
            "(allow file-read-metadata)",  # path existence only, so interpreters can resolve their own location
            f"(allow file-read* {_sbpl_path(ws)} {_sbpl_path(tmp)} " + " ".join(_sbpl_path(p) for p in read_roots) + ")",
        ]
        # Last matching rule wins: protect Keelway state and git internals even inside the workspace.
        lines.append("(deny file-write* " + " ".join(_sbpl_path(ws / p) for p in PROTECTED_WRITE) + ")")
        lines.append("(deny file-read* " + " ".join(_sbpl_path(ws / p) for p in PROTECTED_READ) + ")")
        return "\n".join(lines) + "\n"

    @staticmethod
    def wrap(argv: List[str], profile_path: Path) -> List[str]:
        return ["sandbox-exec", "-f", str(profile_path), *argv]


class BubblewrapBackend:
    name = "bubblewrap"
    _available: Optional[bool] = None

    @classmethod
    def available(cls) -> bool:
        if cls._available is not None:
            return cls._available
        if sys.platform != "linux" or shutil.which("bwrap") is None:
            cls._available = False
            return False
        try:
            res = subprocess.run(
                ["bwrap", "--ro-bind", "/", "/", "--dev", "/dev", "--proc", "/proc", "--unshare-net", "--", "/bin/true"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=2,
            )
            cls._available = (res.returncode == 0)
        except Exception:
            cls._available = False
        return cls._available

    @staticmethod
    def wrap(argv: List[str], workspace: Path, tmp: Path, read_roots: Sequence[Path]) -> List[str]:
        cmd = [
            "bwrap",
            "--ro-bind", "/", "/",
            "--dev", "/dev",
            "--proc", "/proc",
            "--tmpfs", "/tmp",
            "--bind", str(workspace), str(workspace),
            "--bind", str(tmp), str(tmp),
            "--unshare-net",
            "--unshare-pid",
            "--die-with-parent",
        ]
        for p in PROTECTED_WRITE:
            prot = workspace / p
            if prot.exists():
                cmd.extend(["--tmpfs", str(prot)])
        return [*cmd, "--", *argv]


def _default_read_roots() -> List[Path]:
    roots = {Path(sys.prefix).resolve(), Path(sys.base_prefix).resolve()}
    home = Path.home().resolve()
    for entry in os.environ.get("PATH", "").split(os.pathsep):
        if entry:
            p = Path(entry)
            if p.is_dir() and (home in p.resolve().parents or p.resolve() == home):
                roots.add(p.resolve())  # tools the user put on PATH under their home (venv, ~/.local/bin)
    return sorted(roots)


class Sandbox:
    def __init__(self, workspace_root: Path, *, backend: Optional[str] = None, extra_read_roots: Sequence[Path] = (), env_allow: Sequence[str] = ()):
        self.workspace = Path(workspace_root).resolve()
        self.read_roots = sorted({*_default_read_roots(), *(Path(p).resolve() for p in extra_read_roots)})
        self.env_allow = tuple(env_allow)
        if backend is not None:
            self.backend_name = backend
        elif SeatbeltBackend.available():
            self.backend_name = SeatbeltBackend.name
        elif BubblewrapBackend.available():
            self.backend_name = BubblewrapBackend.name
        else:
            self.backend_name = ""
        self._verified: Optional[Tuple[bool, str]] = None

    @property
    def available(self) -> bool:
        if self.backend_name == SeatbeltBackend.name:
            return SeatbeltBackend.available()
        if self.backend_name == BubblewrapBackend.name:
            return BubblewrapBackend.available()
        return False

    # ---- running -----------------------------------------------------
    def run(self, command: str, timeout: int = 30, max_output: int = 200_000) -> SandboxResult:
        if not self.available:
            raise SandboxUnavailable("no confinement backend on this platform (macOS seatbelt or Linux bubblewrap required)")
        try:
            argv = shlex.split(command)
        except ValueError as exc:
            raise ValueError(f"cannot parse command: {exc}") from exc
        if not argv:
            raise ValueError("empty command")
        tmp = Path(tempfile.mkdtemp(prefix="keelway-sbx-")).resolve()
        try:
            if self.backend_name == SeatbeltBackend.name:
                profile_path = tmp / "profile.sb"
                profile_path.write_text(SeatbeltBackend.profile(self.workspace, tmp, self.read_roots), encoding="utf-8")
                wrapped_cmd = SeatbeltBackend.wrap(argv, profile_path)
            elif self.backend_name == BubblewrapBackend.name:
                wrapped_cmd = BubblewrapBackend.wrap(argv, self.workspace, tmp, self.read_roots)
            else:
                raise SandboxUnavailable(f"unsupported sandbox backend: {self.backend_name}")

            env = scrubbed_env(os.environ, tmp, self.env_allow)
            start = time.perf_counter()
            proc = subprocess.Popen(
                wrapped_cmd, cwd=str(self.workspace), env=env, shell=False,
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                start_new_session=True,
            )
            timed_out = False
            try:
                out, err = proc.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                out, err = proc.communicate()
            code = proc.returncode
            if code == 71 and "execvp()" in (err or ""):  # sandbox-exec could not start the program
                code, err = 127, f"command not found or not executable inside the sandbox: {argv[0]}"
            return SandboxResult(code, (out or "")[-max_output:], (err or "")[-max_output:], timed_out, (time.perf_counter() - start) * 1000.0, self.backend_name)
        except FileNotFoundError as exc:
            return SandboxResult(127, "", f"command not found or not readable inside the sandbox: {exc.filename}", False, 0.0, self.backend_name)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    # ---- trust -------------------------------------------------------
    def verify(self) -> Tuple[bool, str]:
        """Try to escape, in a throwaway workspace. Passes only if normal work succeeds AND every escape fails."""
        if self._verified is not None:
            return self._verified
        if not self.available:
            self._verified = (False, "no backend on this platform")
            return self._verified
        probe_root = None
        for parent in (Path.home(), self.workspace.parent):
            try:
                probe_root = Path(tempfile.mkdtemp(prefix=".keelway-probe-", dir=parent)).resolve()
                break
            except OSError:
                continue
        if probe_root is None:
            self._verified = (False, "could not create a probe directory")
            return self._verified
        listener = socket.socket()
        try:
            ws = probe_root / "ws"
            (ws / ".git").mkdir(parents=True)
            (ws / ".keelway").mkdir()
            (ws / ".keelway" / "key").write_text("SIGNINGKEY")
            (probe_root / "secret.txt").write_text("TOPSECRET")
            probe = Sandbox(ws, backend=self.backend_name, extra_read_roots=self.read_roots, env_allow=self.env_allow)
            listener.bind(("127.0.0.1", 0))
            listener.listen(1)
            listener.settimeout(0.5)
            port = listener.getsockname()[1]
            py = shlex.quote(sys.executable)
            checks = [
                ("write inside workspace", f"{py} -c \"open('ok.txt','w').write('ok')\"", True),
                ("read a file outside the workspace", f"{py} -c \"open('{probe_root}/secret.txt').read()\"", False),
                ("write outside the workspace", f"{py} -c \"open('{probe_root}/escaped.txt','w').write('x')\"", False),
                ("open a network connection", f"{py} -c \"import socket;socket.create_connection(('127.0.0.1',{port}),2)\"", False),
                ("write into .git", f"{py} -c \"open('.git/x','w').write('x')\"", False),
                ("write into .keelway", f"{py} -c \"open('.keelway/x','w').write('x')\"", False),
                ("read .keelway", f"{py} -c \"open('.keelway/key').read()\"", False),
            ]
            problems = []
            for label, cmd, should_succeed in checks:
                res = probe.run(cmd, timeout=15)
                if (res.exit_code == 0) != should_succeed:
                    problems.append(f"{label}: {'failed' if should_succeed else 'was NOT blocked'}")
            leaked = probe.run(f"{py} -c \"print(open('{probe_root}/secret.txt').read())\"", timeout=15)
            if "TOPSECRET" in leaked.stdout:
                problems.append("secret contents leaked")
            if (probe_root / "escaped.txt").exists() or (ws / ".git" / "x").exists() or (ws / ".keelway" / "x").exists():
                problems.append("a protected file was written")
            try:
                listener.accept()
                problems.append("a network connection reached the listener")
            except socket.timeout:
                pass
            self._verified = (not problems, "; ".join(problems) or "all escape attempts blocked, normal work succeeded")
            return self._verified
        finally:
            listener.close()
            shutil.rmtree(probe_root, ignore_errors=True)

    def require_verified(self) -> None:
        ok, detail = self.verify()
        if not ok:
            raise SandboxUnavailable(f"sandbox could not be verified on this machine: {detail}")
