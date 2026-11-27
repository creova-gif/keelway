"""OS-level confinement for commands an agent runs.

What a sandboxed command can and cannot do (macOS seatbelt and Linux bubblewrap backends):
  * run with a scrubbed environment: no API keys, tokens or shell secrets are inherited
  * write only inside the workspace and a private per-run temp directory; never `.git` or `.keelway`
  * read the workspace, the Python environment and PATH tools, but not other files under /Users, /Volumes
    or root's home (so no ~/.ssh, no other projects)
  * open no network connections at all (there is no per-host allowlist, so a manifest that wants one is refused)
  * run without a shell (`shell=False`), in its own process group that is killed on timeout, with capped output

What it does NOT do: it is not a container or VM. System files outside the denied areas stay readable, the kernel
is shared, and Apple marks `sandbox-exec` deprecated (it still works and is what many tools use). On Linux, bubblewrap
hides /home, /root, /mnt and /media except the workspace and PATH tools. Elsewhere there is no backend, `Sandbox.require_verified()` raises, and callers must refuse to run commands
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
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

ENV_KEEP = ("PATH", "LANG", "LC_ALL", "LC_CTYPE", "TERM", "TZ", "VIRTUAL_ENV")
# Areas that hold other people's and other projects' files. The workspace is allowed back in afterwards.
DENY_READ_ROOTS = ("/Users", "/Volumes", "/private/var/root")
PROTECTED_WRITE = (".git", ".keelway", ".kora")
PROTECTED_READ = (".keelway", ".kora")


class SandboxUnavailable(RuntimeError):
    """No working confinement backend on this machine; the caller must refuse to run the command."""


class CommandExecutionUnavailable(SandboxUnavailable):
    """Product command execution refused because no verified isolation boundary is configured.

    Callers must surface this as unavailable. They must not catch it and run the
    command on the host shell. A test double may be installed only by an explicit
    caller that labels it as a fake boundary; that double is not OS verification.
    """


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


def _bwrap_path(path: Path) -> str:
    text = str(path)
    if not text or any(ord(ch) < 32 or ord(ch) == 127 for ch in text):
        raise ValueError(f"unsupported control character in sandbox path: {text!r}")
    return text


def _safe_is_dir(path: Path) -> bool:
    try:
        return path.is_dir()
    except OSError:
        return False


def _safe_is_file(path: Path) -> bool:
    try:
        return path.is_file()
    except OSError:
        return False


def _is_within(child: Path, parent: Path) -> bool:
    return child == parent or parent in child.parents


def _read_sysctl(path: Path) -> Optional[str]:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return None


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
    _last_probe_error: Optional[str] = None
    _SYSCTL_APPARMOR_USERNS = Path("/proc/sys/kernel/apparmor_restrict_unprivileged_userns")
    _SYSCTL_USERNS_CLONE = Path("/proc/sys/kernel/unprivileged_userns_clone")
    _SYSCTL_MAX_USERNS = Path("/proc/sys/user/max_user_namespaces")

    @staticmethod
    def _probe_command(bwrap_bin: str = "bwrap") -> List[str]:
        true_bin = shutil.which("true") or "/bin/true"
        return [
            bwrap_bin,
            "--ro-bind", "/", "/",
            "--dev", "/dev",
            "--proc", "/proc",
            "--tmpfs", "/tmp",
            "--unshare-net",
            "--unshare-pid",
            "--unshare-ipc",
            "--unshare-uts",
            "--die-with-parent",
            "--new-session",
            "--",
            true_bin,
        ]

    @classmethod
    def available(cls) -> bool:
        if cls._available is not None:
            return cls._available
        this_platform = sys.platform
        bwrap_bin = shutil.which("bwrap") if this_platform == "linux" else None
        if this_platform != "linux" or bwrap_bin is None:
            cls._available = False
            return False
        try:
            res = subprocess.run(
                cls._probe_command(bwrap_bin),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                timeout=2,
            )
            cls._available = (res.returncode == 0)
            cls._last_probe_error = None if cls._available else (res.stderr or f"exit code {res.returncode}").strip()
        except Exception as exc:
            cls._available = False
            cls._last_probe_error = str(exc)
        return cls._available

    @classmethod
    def diagnostic_reason(cls) -> str:
        """Return a root-cause diagnostic string explaining bubblewrap availability or failure."""
        this_platform = sys.platform
        if this_platform != "linux":
            return f"unsupported platform for bubblewrap: {this_platform} (linux required)"
        bwrap_bin = shutil.which("bwrap")
        if bwrap_bin is None:
            return "bwrap binary not found on PATH (install package 'bubblewrap')"
        notes: List[str] = []
        apparmor_val = _read_sysctl(cls._SYSCTL_APPARMOR_USERNS)
        if apparmor_val == "1":
            notes.append(
                "kernel.apparmor_restrict_unprivileged_userns=1 "
                "(Ubuntu 24.04+ AppArmor blocks unprivileged user namespaces; "
                "set kernel.apparmor_restrict_unprivileged_userns=0 or load an AppArmor profile for bwrap)"
            )
        clone_val = _read_sysctl(cls._SYSCTL_USERNS_CLONE)
        if clone_val == "0":
            notes.append("kernel.unprivileged_userns_clone=0 (unprivileged user namespaces disabled)")
        max_ns_val = _read_sysctl(cls._SYSCTL_MAX_USERNS)
        if max_ns_val == "0":
            notes.append("user.max_user_namespaces=0 (user namespaces disabled)")
        try:
            res = subprocess.run(
                cls._probe_command(bwrap_bin),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                timeout=2,
            )
            if res.returncode == 0:
                return "ok"
            stderr = (res.stderr or "").strip()
            detail = f"bwrap probe exited {res.returncode}" + (f": {stderr}" if stderr else "")
        except Exception as exc:
            detail = f"bwrap probe failed: {exc}"
        if notes:
            return f"{detail} [{' ; '.join(notes)}]"
        return detail

    @staticmethod
    def _hidden_roots() -> List[str]:
        candidates = {"/home", "/root", "/mnt", "/media"}
        try:
            home = Path.home().resolve()
            if home.parent != Path("/") and str(home.parent) != "/tmp":
                candidates.add(str(home.parent))
            elif home != Path("/") and str(home) != "/tmp":
                candidates.add(str(home))
        except OSError:
            pass
        return [h for h in sorted(candidates) if h not in ("/", "/tmp") and _safe_is_dir(Path(h))]

    @staticmethod
    def wrap(
        argv: List[str],
        workspace: Path,
        tmp: Path,
        read_roots: Sequence[Path],
        env: Optional[Mapping[str, str]] = None,
    ) -> List[str]:
        if not argv:
            raise ValueError("empty argv for bubblewrap")
        ws_str = _bwrap_path(workspace)
        tmp_str = _bwrap_path(tmp)
        validated_roots: List[Tuple[Path, str]] = [(r, _bwrap_path(r)) for r in read_roots]

        cmd = [
            "bwrap",
            "--ro-bind", "/", "/",
            "--dev", "/dev",
            "--proc", "/proc",
            "--tmpfs", "/tmp",
        ]
        # Hide every home/user directory (other projects, ~/.ssh, keys), then mount back only what commands need.
        hidden = [
            h for h in BubblewrapBackend._hidden_roots()
            if Path(h) != workspace and Path(h) != tmp
        ]
        for h in hidden:
            cmd.extend(["--tmpfs", h])

        masked_tmpfs_roots = [Path("/tmp"), *(Path(h) for h in hidden)]
        ro_mounted: List[Path] = []

        def _needs_mkdir(target: Path) -> bool:
            in_masked = [m for m in masked_tmpfs_roots if _is_within(target, m) and target != m]
            if not in_masked:
                return False
            deepest_mask = max(in_masked, key=lambda p: len(p.parts))
            for ro in ro_mounted:
                if _is_within(target, ro) and len(ro.parts) > len(deepest_mask.parts):
                    return False
            return True

        hidden_set = set(hidden) | {"/", "/tmp"}
        for root, root_str in validated_roots:
            if root_str in hidden_set or not _safe_is_dir(root):
                continue
            if _is_within(root, workspace) or _is_within(root, tmp):
                continue
            if any(_is_within(root, prev) for prev in ro_mounted):
                continue
            if _needs_mkdir(root):
                cmd.extend(["--dir", root_str])
            cmd.extend(["--ro-bind", root_str, root_str])
            ro_mounted.append(root)

        if _needs_mkdir(workspace):
            cmd.extend(["--dir", ws_str])
        cmd.extend(["--bind", ws_str, ws_str])

        if tmp != workspace:
            if _needs_mkdir(tmp):
                cmd.extend(["--dir", tmp_str])
            cmd.extend(["--bind", tmp_str, tmp_str])

        for p in PROTECTED_WRITE:
            prot = workspace / p
            prot_str = _bwrap_path(prot)
            if _safe_is_dir(prot):
                if p in PROTECTED_READ:
                    cmd.extend(["--tmpfs", prot_str, "--remount-ro", prot_str])
                else:
                    cmd.extend(["--ro-bind", prot_str, prot_str])
            elif _safe_is_file(prot):
                if p in PROTECTED_READ:
                    cmd.extend(["--ro-bind", "/dev/null", prot_str])
                else:
                    cmd.extend(["--ro-bind", prot_str, prot_str])

        # Remount masked parent tmpfs superblocks read-only AFTER all child mounts are attached.
        # In bwrap, --remount-ro is non-recursive, so child --bind mounts (workspace, tmp) stay rw.
        for h in hidden:
            cmd.extend(["--remount-ro", h])

        cmd.extend([
            "--chdir", ws_str,
            "--unshare-net",
            "--unshare-pid",
            "--unshare-ipc",
            "--unshare-uts",
            "--die-with-parent",
            "--new-session",
        ])
        if env is not None:
            cmd.append("--clearenv")
            for key, val in sorted(env.items()):
                if not key or "=" in key or "\x00" in key or "\x00" in val:
                    raise ValueError(f"unsupported character in sandbox environment variable: {key!r}")
                cmd.extend(["--setenv", key, val])
        return [*cmd, "--", *argv]


def _default_read_roots() -> List[Path]:
    roots = {Path(sys.prefix).resolve(), Path(sys.base_prefix).resolve()}
    try:
        roots.add(Path(sys.executable).resolve().parent)
    except OSError:
        pass
    home = Path.home().resolve()
    for entry in os.environ.get("PATH", "").split(os.pathsep):
        if entry:
            try:
                p = Path(entry)
                if p.is_dir():
                    rp = p.resolve()
                    if home in rp.parents:
                        roots.add(rp)  # tools the user put on PATH under their home (venv, ~/.local/bin)
            except (OSError, PermissionError):
                continue
    roots.discard(home)
    roots.discard(Path("/"))
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

    def diagnose(self) -> Dict[str, Any]:
        """Return structured diagnostics for sandbox backend selection and live escape verification."""
        seatbelt_avail = bool(SeatbeltBackend.available())
        bubblewrap_avail = bool(BubblewrapBackend.available())
        verified, detail = self.verify()
        return {
            "platform": sys.platform,
            "selected_backend": self.backend_name,
            "seatbelt_available": seatbelt_avail,
            "bubblewrap_available": bubblewrap_avail,
            "bubblewrap_diagnostic": BubblewrapBackend.diagnostic_reason(),
            "verified": verified,
            "detail": detail,
        }

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
            env = scrubbed_env(os.environ, tmp, self.env_allow)
            if self.backend_name == SeatbeltBackend.name:
                profile_path = tmp / "profile.sb"
                profile_path.write_text(SeatbeltBackend.profile(self.workspace, tmp, self.read_roots), encoding="utf-8")
                wrapped_cmd = SeatbeltBackend.wrap(argv, profile_path)
            elif self.backend_name == BubblewrapBackend.name:
                wrapped_cmd = BubblewrapBackend.wrap(argv, self.workspace, tmp, self.read_roots, env=env)
            else:
                raise SandboxUnavailable(f"unsupported sandbox backend: {self.backend_name}")

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
            if (code == 71 and "execvp()" in (err or "")) or (
                self.backend_name == BubblewrapBackend.name and code == 1 and f"bwrap: execvp {argv[0]}:" in (err or "")
            ):
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
            if sys.platform == "linux" and self.backend_name in ("", BubblewrapBackend.name):
                self._verified = (False, f"no backend on this platform ({BubblewrapBackend.diagnostic_reason()})")
            else:
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
            (ws / ".kora").mkdir()
            (ws / ".kora" / "key").write_text("KORASIGNINGKEY")
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
                    if should_succeed:
                        err_lines = (res.stderr or "").strip().splitlines()
                        snippet = err_lines[-1][:200] if err_lines else f"exit={res.exit_code}"
                        problems.append(f"{label}: failed ({snippet})")
                    else:
                        problems.append(f"{label}: was NOT blocked")
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


_verified_sandboxes: Dict[Path, Sandbox] = {}


def verified_command_runner(workspace_root: Path) -> Tuple[Optional[Callable[[str, int], Dict[str, Any]]], str]:
    """An agent `command_runner` confined to the workspace, or (None, reason) when no backend passes the self-test.

    The self-test runs once per workspace per process; later agents reuse the verified sandbox.
    """
    root = Path(workspace_root).resolve()
    sandbox = _verified_sandboxes.get(root) or Sandbox(root)
    ok, detail = sandbox.verify()
    if not ok:
        return None, detail
    _verified_sandboxes[root] = sandbox
    return (lambda command, timeout: sandbox.run(command, timeout).to_tool_result(command)), detail
