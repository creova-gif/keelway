"""
Command gate for coding agents (Claude Code first): a person allows or denies each shell command before it runs,
the command runs in a verified sandbox, and every step is sealed into a flight tape.

1. The PreToolUse hook submits the command with a gate-role token (it can submit and redeem, nothing else).
2. A person allows or denies it in Studio or on a paired phone within GATE_WINDOW_SECONDS; the first decision wins.
3. On allow the hook rewrites the command to `keelway exec --ticket <ticket> -- '<command>'`.
4. `keelway exec` redeems the ticket here. It is single use and bound to sha256(command) and the working folder.

The ticket key exists only in this process's memory, so restarting the API invalidates every outstanding ticket.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import shutil
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from core.orchestration.flight_recorder import FlightRecorder

GATE_WINDOW_SECONDS = 300
SANDBOX_VERIFY_TTL_SECONDS = 600
TICKET_PREFIX = "kwt_"
MAX_COMMAND_CHARS = 32_000

PENDING = "pending"
APPROVED = "approved"
DENIED = "denied"
TIMED_OUT = "timed_out"
TERMINAL = (APPROVED, DENIED, TIMED_OUT)


@dataclass(frozen=True)
class DenyReason:
    code: str
    reason: str
    fix: str = ""

    def message(self, **values: Any) -> str:
        text = f"Keelway blocked [{self.code}]: {self.reason.format(**values)}."
        fix = self.fix.format(**values)
        return f"{text} {fix}" if fix else text


# One table for the hook, `keelway exec`, doctor and tests. The agent reads these too, so each names one next step.
DENY_REASONS: Dict[str, DenyReason] = {
    "timed_out": DenyReason("KW-G01", "approval timed out after {minutes} min", "Ask again, or approve in Studio ({studio_url})."),
    "denied": DenyReason("KW-G02", "{actor} denied this command", "Do not retry it; ask the person what to do instead."),
    "not_running": DenyReason("KW-G03", "Keelway is not running", "Start it with: keelway dev"),
    "sandbox": DenyReason("KW-G04", "sandbox not verified ({detail})", "Fix: keelway doctor"),
    "network": DenyReason("KW-G05", "network is off inside the sandbox; this command needs network", "Run it yourself outside Keelway."),
    "protected": DenyReason("KW-G06", "editing {path} is not allowed (protects the Keelway gate)", "Recorded."),
    "ticket": DenyReason("KW-G07", "approval ticket {problem}", "Ask for the command again to get a fresh approval."),
    "hook_error": DenyReason("KW-G08", "the gate hook failed ({detail})", "Check it with: keelway hook status"),
    "not_installed": DenyReason(
        "KW-G09", "keelway is not installed but its Claude Code hook is",
        "Fix: pipx install keelway, or remove the hook from .claude/settings.json",
    ),
    "unauthorized": DenyReason("KW-G10", "the gate token was rejected", "Reinstall the hook: keelway hook install --claude-code"),
    "too_long": DenyReason("KW-G11", "the command is longer than {limit} characters", "Split it into smaller commands."),
    "unsupported_tool": DenyReason("KW-G12", "{tool} commands are not gated in this beta", "Use the Bash tool instead."),
}


def deny_message(key: str, **values: Any) -> str:
    return DENY_REASONS[key].message(**values)


def command_sha256(command: str) -> str:
    return hashlib.sha256(command.encode("utf-8")).hexdigest()


def normalize_dir(path: str) -> str:
    return os.path.realpath(os.path.expanduser(path))


@dataclass(frozen=True)
class SandboxVerdict:
    ok: bool
    detail: str
    backend: str
    verified_at: float

    def to_dict(self) -> Dict[str, Any]:
        return {"verified": self.ok, "detail": self.detail, "backend": self.backend, "verified_at": self.verified_at}


def _backend_binary(backend: str) -> Tuple[str, float]:
    if backend == "seatbelt":
        path = "/usr/bin/sandbox-exec"
    elif backend == "bubblewrap":
        path = shutil.which("bwrap") or ""
    else:
        return "", 0.0
    try:
        return path, os.stat(path).st_mtime
    except OSError:
        return path, 0.0


class SandboxVerifyCache:
    """Sandbox self-test results held in API memory (~700 ms each), keyed so a changed backend binary re-verifies."""

    def __init__(self, ttl: float = SANDBOX_VERIFY_TTL_SECONDS, clock: Callable[[], float] = time.time, sandbox_factory=None):
        self.ttl = ttl
        self.clock = clock
        self._factory = sandbox_factory
        self._lock = threading.Lock()
        self._entries: Dict[Tuple[str, str, float, str], SandboxVerdict] = {}

    def _sandbox(self, root: Path):
        if self._factory is not None:
            return self._factory(root)
        from core.agents.sandbox import Sandbox
        return Sandbox(root)

    def get(self, workspace_root: str) -> SandboxVerdict:
        root = Path(normalize_dir(workspace_root))
        sandbox = self._sandbox(root)
        backend = sandbox.backend_name or ""
        binary, mtime = _backend_binary(backend)
        key = (backend, binary, mtime, str(root))
        now = self.clock()
        with self._lock:
            hit = self._entries.get(key)
            if hit is not None and now - hit.verified_at < self.ttl:
                return hit
        ok, detail = sandbox.verify()
        verdict = SandboxVerdict(bool(ok), detail, backend, self.clock())
        with self._lock:
            if verdict.ok:
                self._entries[key] = verdict
            else:
                self._entries.pop(key, None)
        return verdict

    def invalidate(self, workspace_root: Optional[str] = None) -> None:
        with self._lock:
            if workspace_root is None:
                self._entries.clear()
                return
            root = normalize_dir(workspace_root)
            for key in [k for k in self._entries if k[3] == root]:
                del self._entries[key]


@dataclass
class GateRequest:
    id: str
    command: str
    cwd: str
    workspace_root: str
    requester: str
    tool: str
    session_id: str
    created_at: float
    expires_at: float
    sandbox: SandboxVerdict
    status: str = PENDING
    decided_by: Optional[str] = None
    decided_at: Optional[float] = None
    deny_key: Optional[str] = None
    redeemed_at: Optional[float] = None
    result: Optional[Dict[str, Any]] = None
    tape_path: Optional[str] = None
    _ticket: Optional[str] = field(default=None, repr=False)

    @property
    def command_sha256(self) -> str:
        return command_sha256(self.command)

    def public(self, now: float) -> Dict[str, Any]:
        return {
            "id": self.id,
            "command": self.command,
            "command_sha256": self.command_sha256,
            "cwd": self.cwd,
            "workspace_root": self.workspace_root,
            "requester": self.requester,
            "tool": self.tool,
            "session_id": self.session_id,
            "status": self.status,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "seconds_left": max(0, int(self.expires_at - now)) if self.status == PENDING else 0,
            "sandbox": self.sandbox.to_dict(),
            "decided_by": self.decided_by,
            "decided_at": self.decided_at,
            "redeemed": self.redeemed_at is not None,
            "result": self.result,
            "tape_path": self.tape_path,
        }


class GateConflict(Exception):
    """The request was already decided or timed out; the first decision stands."""


class TicketRejected(Exception):
    def __init__(self, problem: str, request: Optional[GateRequest] = None):
        super().__init__(problem)
        self.problem = problem
        self.request = request


class GateStore:
    def __init__(
        self,
        window: float = GATE_WINDOW_SECONDS,
        clock: Callable[[], float] = time.time,
        tape_dir: Optional[Path] = None,
        verify_cache: Optional[SandboxVerifyCache] = None,
    ):
        self.window = window
        self.clock = clock
        self.tape_dir = tape_dir
        self.verify_cache = verify_cache or SandboxVerifyCache(clock=clock)
        self._key = secrets.token_bytes(32)
        self._lock = threading.RLock()
        self._requests: Dict[str, GateRequest] = {}
        self._tapes: Dict[str, FlightRecorder] = {}

    # ---- tape -----------------------------------------------------------
    def _record(self, req: GateRequest, event_type: str, payload: Dict[str, Any]) -> bool:
        recorder = self._tapes.get(req.id)
        if recorder is None:
            tape_dir = self.tape_dir or Path(req.workspace_root) / ".keelway" / "recordings"
            recorder = FlightRecorder(task_id=f"gate-{req.id}", recordings_dir=tape_dir)
            self._tapes[req.id] = recorder
        recorder.record_event(event_type, {"request_id": req.id, **payload})
        try:
            req.tape_path = str(recorder.save_tape())
        except OSError:
            req.tape_path = None
            return False
        return True

    # ---- lifecycle ------------------------------------------------------
    def _expire(self, req: GateRequest) -> None:
        if req.status == PENDING and self.clock() >= req.expires_at:
            req.status, req.deny_key, req.decided_by, req.decided_at = TIMED_OUT, "timed_out", "timeout", req.expires_at
            self._record(req, "gate_decided", {"decision": TIMED_OUT, "by": "timeout"})

    def submit(
        self, command: str, cwd: str, *, workspace_root: Optional[str] = None, requester: str = "Claude Code",
        tool: str = "Bash", session_id: str = "", sandbox: Optional[SandboxVerdict] = None,
    ) -> GateRequest:
        cwd = normalize_dir(cwd)
        root = normalize_dir(workspace_root) if workspace_root else cwd
        if not (cwd == root or cwd.startswith(root.rstrip(os.sep) + os.sep)):
            root = cwd
        verdict = sandbox or self.verify_cache.get(root)
        now = self.clock()
        req = GateRequest(
            id=uuid.uuid4().hex[:16], command=command, cwd=cwd, workspace_root=root, requester=requester[:60],
            tool=tool[:40], session_id=session_id[:120], created_at=now, expires_at=now + self.window, sandbox=verdict,
        )
        with self._lock:
            self._requests[req.id] = req
            self._record(req, "gate_requested", {
                "command": command, "command_sha256": req.command_sha256, "cwd": cwd, "workspace_root": root,
                "requester": req.requester, "tool": req.tool, "sandbox": verdict.to_dict(),
            })
            if not verdict.ok:
                # Approving would be pointless: exec refuses to run unconfined, so fail before asking anyone.
                req.status, req.deny_key, req.decided_by, req.decided_at = DENIED, "sandbox", "keelway", now
                self._record(req, "gate_decided", {"decision": DENIED, "by": "keelway", "reason": "sandbox"})
        return req

    def get(self, request_id: str) -> Optional[GateRequest]:
        with self._lock:
            req = self._requests.get(request_id)
            if req is not None:
                self._expire(req)
            return req

    def pending(self) -> List[GateRequest]:
        """Oldest first: the request closest to timing out is the one shown."""
        with self._lock:
            for req in self._requests.values():
                self._expire(req)
            return sorted((r for r in self._requests.values() if r.status == PENDING), key=lambda r: r.created_at)

    def decide(self, request_id: str, allow: bool, actor: str) -> GateRequest:
        with self._lock:
            req = self.get(request_id)
            if req is None:
                raise KeyError(request_id)
            if req.status != PENDING:
                raise GateConflict(req.status)
            req.status = APPROVED if allow else DENIED
            req.decided_by, req.decided_at = actor, self.clock()
            if allow:
                req._ticket = self._mint_ticket(req)
            else:
                req.deny_key = "denied"
            self._record(req, "gate_decided", {"decision": req.status, "by": actor})
            return req

    def deny_waiting(self, actor: str) -> List[GateRequest]:
        with self._lock:
            return [self.decide(req.id, False, actor) for req in self.pending()]

    def ticket(self, req: GateRequest) -> Optional[str]:
        return req._ticket if req.status == APPROVED and req.redeemed_at is None else None

    # ---- tickets --------------------------------------------------------
    def _signature(self, request_id: str, sha: str, cwd: str) -> str:
        msg = f"{request_id}\n{sha}\n{cwd}".encode("utf-8")
        return hmac.new(self._key, msg, hashlib.sha256).hexdigest()

    def _mint_ticket(self, req: GateRequest) -> str:
        return f"{TICKET_PREFIX}{req.id}.{self._signature(req.id, req.command_sha256, req.cwd)}"

    def redeem(self, ticket: str, command: str, cwd: str) -> GateRequest:
        if not ticket.startswith(TICKET_PREFIX) or "." not in ticket:
            raise TicketRejected("is malformed")
        request_id, _, signature = ticket[len(TICKET_PREFIX):].partition(".")
        cwd = normalize_dir(cwd)
        with self._lock:
            req = self.get(request_id)
            if req is None:
                raise TicketRejected("is unknown (Keelway may have restarted)")
            expected = self._signature(req.id, req.command_sha256, req.cwd)
            if not hmac.compare_digest(signature, expected):
                self._record(req, "gate_ticket_rejected", {"problem": "bad signature"})
                raise TicketRejected("is not valid", req)
            if req.status != APPROVED:
                raise TicketRejected(f"is not approved ({req.status})", req)
            if req.redeemed_at is not None:
                self._record(req, "gate_ticket_rejected", {"problem": "already used"})
                raise TicketRejected("was already used", req)
            if command_sha256(command) != req.command_sha256 or cwd != req.cwd:
                self._record(req, "gate_ticket_rejected", {
                    "problem": "binding mismatch", "command_sha256": command_sha256(command), "cwd": cwd,
                })
                raise TicketRejected("does not match this command or folder", req)
            req.redeemed_at = self.clock()
            req._ticket = None
            if not self._record(req, "gate_redeemed", {"command_sha256": req.command_sha256, "cwd": cwd}):
                raise TicketRejected("could not be recorded (the flight tape is not writable)", req)
            return req

    def record_result(self, request_id: str, result: Dict[str, Any]) -> GateRequest:
        with self._lock:
            req = self.get(request_id)
            if req is None or req.redeemed_at is None:
                raise KeyError(request_id)
            if req.result is not None:
                raise GateConflict("result already recorded")
            req.result = result
            if result.get("sandbox_failure"):
                self.verify_cache.invalidate(req.workspace_root)
            self._record(req, "gate_executed", result)
            if req.tape_path:
                recorder = self._tapes.pop(req.id, None)
                if recorder is not None:
                    recorder.seal_tape()
            return req

    def record_tamper(self, tool: str, path: str, cwd: str, session_id: str = "") -> GateRequest:
        """A blocked attempt to edit the hook or Keelway's own state, kept on the tape (D10)."""
        cwd = normalize_dir(cwd)
        now = self.clock()
        verdict = SandboxVerdict(False, "not applicable", "", now)
        req = GateRequest(
            id=uuid.uuid4().hex[:16], command=f"{tool} {path}", cwd=cwd, workspace_root=cwd, requester="Claude Code",
            tool=tool[:40], session_id=session_id[:120], created_at=now, expires_at=now, sandbox=verdict,
            status=DENIED, decided_by="keelway", decided_at=now, deny_key="protected",
        )
        with self._lock:
            self._requests[req.id] = req
            self._record(req, "gate_tamper_denied", {"tool": tool, "path": path, "cwd": cwd})
        return req

    def history(self, limit: int = 50) -> List[GateRequest]:
        with self._lock:
            for req in self._requests.values():
                self._expire(req)
            return sorted(self._requests.values(), key=lambda r: r.created_at, reverse=True)[:limit]


gate_store = GateStore()


# ---------------------------------------------------------------------------
# Client side: the Claude Code hook, `keelway exec`, and the hook's settings entry.
# ---------------------------------------------------------------------------

import json  # noqa: E402
import re  # noqa: E402
import shlex  # noqa: E402
import sys  # noqa: E402

DEFAULT_API_URL = "http://127.0.0.1:7420"
HOOK_TIMEOUT_SECONDS = 600
COMMAND_MATCHER = "Bash|PowerShell|Monitor"
EDIT_MATCHER = "Edit|Write|MultiEdit|NotebookEdit"
GATED_TOOLS = ("Bash", "Monitor")
EDIT_TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit")
HOOK_MARKER = "hook gate"
NETWORK_ERROR_RE = re.compile(
    r"could not resolve host|temporary failure in name resolution|network is unreachable|getaddrinfo|"
    r"name or service not known|failed to establish a new connection|ENOTFOUND|EAI_AGAIN",
    re.IGNORECASE,
)


def keelway_home() -> Path:
    return Path(os.environ.get("KEELWAY_HOME") or Path.home() / ".keelway")


def gate_config_path() -> Path:
    return keelway_home() / "gate.json"


def load_gate_config() -> Dict[str, Any]:
    try:
        return json.loads(gate_config_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_gate_config(config: Dict[str, Any]) -> Path:
    path = gate_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(config, fh, indent=2, sort_keys=True)
    os.replace(tmp, path)
    return path


def api_url(config: Optional[Dict[str, Any]] = None) -> str:
    return (os.environ.get("KEELWAY_API_URL") or (config or {}).get("api_url") or DEFAULT_API_URL).rstrip("/")


def gate_token(config: Optional[Dict[str, Any]] = None) -> str:
    return os.environ.get("KEELWAY_GATE_TOKEN") or (config or {}).get("token") or ""


def _debug(message: str) -> None:
    if os.environ.get("KEELWAY_DEBUG"):
        print(f"[keelway debug] {message}", file=sys.stderr)


# ---- protected paths (D10) -------------------------------------------------
def is_protected_path(file_path: str, cwd: str) -> bool:
    """The hook config, Keelway's own state and its tapes: an agent edit here could switch the gate off."""
    if not file_path:
        return False
    raw = Path(os.path.expanduser(file_path))
    absolute = raw if raw.is_absolute() else Path(cwd) / raw
    # Check the path as named and as resolved, so a symlinked settings file is still protected.
    return any(_is_protected(Path(p)) for p in {os.path.normpath(absolute), os.path.realpath(absolute)})


def _is_protected(path: Path) -> bool:
    parts = path.parts
    if ".keelway" in parts or ".kora" in parts:
        return True
    home = Path(os.path.realpath(keelway_home()))
    if path == home or home in path.parents:
        return True
    for i, part in enumerate(parts[:-1]):
        if part != ".claude":
            continue
        rest = parts[i + 1:]
        if rest[0] == "hooks":
            return True
        if len(rest) == 1 and re.fullmatch(r"settings(\.[\w-]+)*\.json", rest[0]):
            return True
    return False


# ---- Claude Code settings entry ---------------------------------------------
def hook_shell_command(keelway_bin: str) -> str:
    """Self-guarding: if keelway is gone the hook still blocks (exit 2) instead of letting commands run unchecked."""
    guard = deny_message("not_installed")
    return (
        f"K={shlex.quote(keelway_bin)}; [ -x \"$K\" ] || K=$(command -v keelway 2>/dev/null); "
        f"if [ -z \"$K\" ]; then echo {shlex.quote(guard)} >&2; exit 2; fi; exec \"$K\" {HOOK_MARKER}"
    )


def hook_entries(keelway_bin: str) -> List[Dict[str, Any]]:
    hook = {"type": "command", "command": hook_shell_command(keelway_bin), "timeout": HOOK_TIMEOUT_SECONDS}
    return [{"matcher": COMMAND_MATCHER, "hooks": [dict(hook)]}, {"matcher": EDIT_MATCHER, "hooks": [dict(hook)]}]


def _is_keelway_entry(entry: Any) -> bool:
    return isinstance(entry, dict) and any(
        isinstance(h, dict) and HOOK_MARKER in str(h.get("command", "")) and "keelway" in str(h.get("command", ""))
        for h in entry.get("hooks", []) or []
    )


def entries_sha256(entries: List[Dict[str, Any]]) -> str:
    return hashlib.sha256(json.dumps(entries, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def settings_path_for(scope: str, project_dir: Path) -> Path:
    if scope == "user":
        return Path.home() / ".claude" / "settings.json"
    if scope == "project":
        return project_dir / ".claude" / "settings.json"
    return project_dir / ".claude" / "settings.local.json"


def _read_settings(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8") or "{}")
    if not isinstance(data, dict):
        raise ValueError(f"{path} is not a JSON object")
    return data


def install_settings(path: Path, keelway_bin: str) -> str:
    """Add Keelway's PreToolUse entries next to any existing hooks (never overwrite them). Returns the entries hash."""
    data = _read_settings(path)
    hooks = data.setdefault("hooks", {})
    pre = [e for e in hooks.get("PreToolUse", []) or [] if not _is_keelway_entry(e)]
    entries = hook_entries(keelway_bin)
    hooks["PreToolUse"] = pre + entries
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return entries_sha256(entries)


def uninstall_settings(path: Path) -> int:
    if not path.exists():
        return 0
    data = _read_settings(path)
    hooks = data.get("hooks") or {}
    pre = hooks.get("PreToolUse") or []
    kept = [e for e in pre if not _is_keelway_entry(e)]
    removed = len(pre) - len(kept)
    if removed:
        if kept:
            hooks["PreToolUse"] = kept
        else:
            hooks.pop("PreToolUse", None)
        if not hooks:
            data.pop("hooks", None)
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return removed


def installed_entries_sha256(path: Path) -> Optional[str]:
    """Hash of the Keelway entries currently in a settings file, or None when there are none."""
    try:
        data = _read_settings(path)
    except (OSError, ValueError):
        return None
    entries = [e for e in (data.get("hooks") or {}).get("PreToolUse", []) or [] if _is_keelway_entry(e)]
    return entries_sha256(entries) if entries else None


# ---- the hook ---------------------------------------------------------------
def _decision(decision: str, reason: str, updated_input: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    out: Dict[str, Any] = {"hookEventName": "PreToolUse", "permissionDecision": decision, "permissionDecisionReason": reason}
    if updated_input is not None:
        out["updatedInput"] = updated_input
    return {"hookSpecificOutput": out}


def deny(reason: str) -> Dict[str, Any]:
    return _decision("deny", reason)


def exec_command_line(keelway_bin: str, ticket: str, command: str) -> str:
    return shlex.join([keelway_bin, "exec", "--ticket", ticket, "--", command])


class GateClient:
    """Talks to the local Keelway API with the gate-role token."""

    def __init__(self, base_url: str, token: str, http=None):
        import httpx

        self.base_url = base_url
        self._http = http or httpx.Client(base_url=base_url, timeout=httpx.Timeout(70.0, connect=3.0))
        self._headers = {"Authorization": f"Bearer {token}"} if token else {}

    def post(self, path: str, body: Dict[str, Any]):
        return self._http.post(path, json=body, headers=self._headers)

    def get(self, path: str, params: Optional[Dict[str, Any]] = None):
        return self._http.get(path, params=params, headers=self._headers)


def _detail(resp) -> str:
    try:
        return str(resp.json().get("detail") or resp.text)
    except ValueError:
        return resp.text


def handle_hook_event(event: Dict[str, Any], client: GateClient, keelway_bin: str, clock: Callable[[], float] = time.time) -> Dict[str, Any]:
    """One PreToolUse event in, one hook decision out. Anything unexpected becomes a deny, never an allow."""
    tool = str(event.get("tool_name") or "")
    tool_input = event.get("tool_input") or {}
    cwd = str(event.get("cwd") or os.getcwd())
    session_id = str(event.get("session_id") or "")
    _debug(f"event tool={tool} cwd={cwd}")

    if tool in EDIT_TOOLS:
        path = str(tool_input.get("file_path") or tool_input.get("notebook_path") or "")
        if not is_protected_path(path, cwd):
            return {}
        try:
            client.post("/v1/gate/tamper", {"tool": tool, "path": path, "cwd": cwd, "session_id": session_id})
        except Exception as exc:  # the denial stands even if it can't be recorded
            _debug(f"tamper record failed: {exc}")
        return deny(deny_message("protected", path=path))

    if tool not in GATED_TOOLS:
        if tool == "PowerShell":
            return deny(deny_message("unsupported_tool", tool=tool))
        return {}

    command = str(tool_input.get("command") or "")
    if not command.strip():
        return deny(deny_message("hook_error", detail="no command in the tool input"))
    if len(command) > MAX_COMMAND_CHARS:
        return deny(deny_message("too_long", limit=MAX_COMMAND_CHARS))

    import httpx

    body = {
        "command": command, "cwd": cwd, "workspace_root": os.environ.get("CLAUDE_PROJECT_DIR") or None,
        "tool": tool, "requester": "Claude Code", "session_id": session_id,
    }
    try:
        resp = client.post("/v1/gate/requests", body)
    except httpx.TransportError:
        return deny(deny_message("not_running"))
    if resp.status_code in (401, 403):
        return deny(deny_message("unauthorized"))
    if resp.status_code != 201:
        return deny(deny_message("hook_error", detail=_detail(resp)))
    req = resp.json()
    _debug(f"submitted {req['id']} status={req['status']}")

    deadline = clock() + GATE_WINDOW_SECONDS + 30
    while req.get("status") == PENDING and clock() < deadline:
        try:
            resp = client.get(f"/v1/gate/requests/{req['id']}/wait", {"timeout": 25})
        except httpx.TransportError:
            return deny(deny_message("not_running"))
        if resp.status_code != 200:
            return deny(deny_message("hook_error", detail=_detail(resp)))
        req = resp.json()

    if req.get("status") == APPROVED and req.get("ticket"):
        rewritten = exec_command_line(keelway_bin, req["ticket"], command)
        who = req.get("decided_by") or "you"
        return _decision(
            "allow", f"Approved in Keelway by {who}; runs in the verified sandbox ({req['sandbox']['backend']}).",
            {**tool_input, "command": rewritten},
        )
    if req.get("status") == PENDING:
        return deny(deny_message("timed_out", minutes=GATE_WINDOW_SECONDS // 60, studio_url=client.base_url))
    return deny(req.get("deny_message") or deny_message("hook_error", detail=f"status {req.get('status')}"))


# ---- keelway exec -------------------------------------------------------------
def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()


def run_exec(ticket: str, command: str, client: GateClient, cwd: Optional[str] = None, timeout: int = 120, sandbox_factory=None) -> int:
    """Redeem the ticket at the API, then run exactly the approved command in the sandbox. Every failure refuses to run."""
    import httpx

    from core.agents.sandbox import Sandbox, SandboxUnavailable

    cwd = normalize_dir(cwd or os.getcwd())
    try:
        resp = client.post("/v1/gate/redeem", {"ticket": ticket, "command": command, "cwd": cwd})
    except httpx.TransportError:
        print(deny_message("not_running"), file=sys.stderr)
        return 126
    if resp.status_code != 200:
        print(_detail(resp) if resp.status_code in (403, 409) else deny_message("unauthorized"), file=sys.stderr)
        return 126
    grant = resp.json()
    root = grant["workspace_root"]
    inner = command if cwd == root else f"cd {shlex.quote(cwd)} && {command}"
    factory = sandbox_factory or (lambda r, b: Sandbox(Path(r), backend=b))
    sandbox = factory(root, grant["sandbox"]["backend"])
    result: Dict[str, Any]
    try:
        run = sandbox.run(shlex.join(["bash" if shutil.which("bash") else "sh", "-c", inner]), timeout=timeout)
    except (SandboxUnavailable, ValueError, OSError) as exc:
        result = {"exit_code": 126, "sandbox_failure": isinstance(exc, (SandboxUnavailable, OSError)), "backend": grant["sandbox"]["backend"]}
        _report(client, grant["id"], result)
        print(deny_message("sandbox", detail=str(exc)), file=sys.stderr)
        return 126
    if run.stdout:
        sys.stdout.write(run.stdout)
    if run.stderr:
        sys.stderr.write(run.stderr)
    sandbox_failure = run.exit_code != 0 and run.stderr.lstrip().startswith("bwrap:")
    result = {
        "exit_code": run.exit_code, "duration_ms": round(run.duration_ms, 1), "timed_out": run.timed_out,
        "sandbox_failure": sandbox_failure, "backend": run.backend,
        "stdout_sha256": _sha(run.stdout), "stderr_sha256": _sha(run.stderr),
    }
    _report(client, grant["id"], result)
    if run.timed_out:
        print(f"Keelway: command timed out after {timeout}s inside the sandbox.", file=sys.stderr)
    elif run.exit_code != 0 and NETWORK_ERROR_RE.search(run.stderr or ""):
        print(deny_message("network"), file=sys.stderr)
    return run.exit_code if run.exit_code >= 0 else 1


def _report(client: GateClient, request_id: str, result: Dict[str, Any]) -> None:
    try:
        client.post(f"/v1/gate/requests/{request_id}/result", result)
    except Exception as exc:
        _debug(f"result report failed: {exc}")
