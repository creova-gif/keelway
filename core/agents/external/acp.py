"""Agent Client Protocol (ACP) session bridge.

ACP agents (e.g. `claude-code-acp`, `gemini --experimental-acp`) speak
newline-delimited JSON-RPC 2.0 over stdio. The agent sends
`session/request_permission` requests for tool calls; as the ACP *client*
we answer them — routing each request through the same Keelway co-harness
verdict authority (`intercept_tool_call`) used by hook-based hosts.

Scope (KEEL-ENG-051): transport + handshake + permission bridge +
session/update evidence. No claim of compatibility with any specific
agent until contract-tested against a pinned binary.
"""

from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

ACP_PROTOCOL_VERSION = 1
_MAX_EVALUATED_CHARS = 262_144  # cap evaluated payload at 256 KiB


@dataclass
class AcpPermissionDecision:
    """Outcome returned to the agent for a session/request_permission call."""

    outcome: str = ""  # "selected" | "cancelled"
    option_id: Optional[str] = None
    verdict: str = ""
    reason_code: str = ""
    ticket_id: Optional[str] = None


@dataclass
class AcpSessionResult:
    """Summary of a completed (or failed) ACP prompt session."""

    agent_id: str
    returncode: Optional[int]
    stop_reason: Optional[str] = None
    events: List[Dict[str, Any]] = field(default_factory=list)
    permission_decisions: List[AcpPermissionDecision] = field(default_factory=list)
    error: Optional[str] = None


PermissionEvaluator = Callable[[str, str, Optional[str]], Dict[str, Any]]
"""(tool_name, command, ticket_id) -> intercept record dict."""


def _reader(stream, lines: "queue.Queue[Optional[str]]") -> None:
    try:
        for line in iter(stream.readline, ""):
            lines.put(line)
    finally:
        lines.put(None)


class AcpClient:
    """Minimal ACP stdio client: initialize → session/new → session/prompt.

    Answers `session/request_permission` via `permission_evaluator`;
    collects `session/update` notifications as normalized events.
    """

    def __init__(self, argv: List[str], cwd: Optional[str] = None,
                 env: Optional[Dict[str, str]] = None,
                 permission_evaluator: Optional[PermissionEvaluator] = None,
                 event_sink: Optional[Callable[[Dict[str, Any]], None]] = None,
                 rpc_timeout: float = 30.0) -> None:
        self.argv = list(argv)
        self.cwd = cwd
        self.env = env if env is not None else dict(os.environ)
        self.permission_evaluator = permission_evaluator
        self.event_sink = event_sink
        self.rpc_timeout = rpc_timeout
        self._proc: Optional[subprocess.Popen] = None
        self._lines: "queue.Queue[Optional[str]]" = queue.Queue()
        self._next_id = 0
        self._session_id: Optional[str] = None
        self.events: List[Dict[str, Any]] = []
        self.permission_decisions: List[AcpPermissionDecision] = []
        self._stop_reason: Optional[str] = None

    # -- transport ------------------------------------------------------

    def start(self) -> None:
        self._proc = subprocess.Popen(
            self.argv, cwd=self.cwd, env=self.env,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, bufsize=1,
        )
        threading.Thread(target=_reader, args=(self._proc.stdout, self._lines), daemon=True).start()

    def _send(self, msg: Dict[str, Any]) -> None:
        assert self._proc is not None and self._proc.stdin is not None
        self._proc.stdin.write(json.dumps(msg) + "\n")
        self._proc.stdin.flush()

    def _request(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        self._next_id += 1
        rid = self._next_id
        self._send({"jsonrpc": "2.0", "id": rid, "method": method, "params": params})
        return self._await_response(rid)

    def _await_response(self, rid: int) -> Dict[str, Any]:
        """Read messages until response `id` arrives; dispatch others."""
        import time
        deadline = time.monotonic() + self.rpc_timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f"ACP request {rid} timed out after {self.rpc_timeout}s")
            try:
                line = self._lines.get(timeout=remaining)
            except queue.Empty:
                raise TimeoutError(f"ACP request {rid} timed out")
            if line is None:
                raise EOFError("ACP agent closed stdout")
            if not line.strip():
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(msg, dict):
                continue
            if msg.get("id") == rid and ("result" in msg or "error" in msg):
                if "error" in msg:
                    raise RuntimeError(f"ACP error on id={rid}: {msg['error']}")
                return msg.get("result") or {}
            self._dispatch(msg)

    def _dispatch(self, msg: Dict[str, Any]) -> None:
        method = msg.get("method")
        if method == "session/update":
            params = msg.get("params") or {}
            update = params.get("update") or {}
            kind = update.get("sessionUpdate") or update.get("session_update") or "unknown"
            event = {"type": "session_update", "kind": kind, "update": update}
            self.events.append(event)
            if self.event_sink:
                self.event_sink(event)
        elif method == "session/request_permission":
            self._handle_permission_request(msg)
        # notifications/other requests are ignored (no response sent)

    # -- permission bridge ----------------------------------------------

    @staticmethod
    def _extract_tool_call(params: Dict[str, Any]) -> tuple:
        tc = params.get("toolCall") or params.get("tool_call") or {}
        title = str(tc.get("title") or "")
        kind = str(tc.get("kind") or "")
        # ACP toolCall may carry rawInput with command-like fields.
        raw = tc.get("rawInput") or tc.get("raw_input") or {}
        command = ""
        content_parts: List[str] = []
        if isinstance(raw, dict):
            for key in ("command", "cmd"):
                val = raw.get(key)
                if isinstance(val, str) and val.strip():
                    command = val.strip()
                    break
            # Edit/write tool calls carry the proposed body, not a command —
            # fold path + body into the evaluated string so content-DLP and
            # sensitive-path checks see them (KEEL-ENG-053).
            for key in ("path", "file_path", "filePath", "target_file", "filename"):
                val = raw.get(key)
                if isinstance(val, str) and val.strip():
                    content_parts.append(f"path={val.strip()}")
                    break
            for key in ("content", "contents", "new_string", "newString",
                        "text", "diff", "patch", "body", "edits"):
                val = raw.get(key)
                if isinstance(val, str) and val.strip():
                    content_parts.append(val.strip()[:_MAX_EVALUATED_CHARS])
                    break
        tool_name = kind or ("bash" if command else "tool")
        evaluated = command or title
        if content_parts:
            base = evaluated or f"{tool_name} call"
            evaluated = base + "\n" + "\n".join(content_parts)
        return tool_name, evaluated[:_MAX_EVALUATED_CHARS]

    @staticmethod
    def _pick_option(options: List[Dict[str, Any]], want_kinds: tuple) -> Optional[str]:
        for opt in options:
            if str(opt.get("kind") or "") in want_kinds:
                oid = opt.get("optionId") or opt.get("option_id") or opt.get("id")
                if oid:
                    return str(oid)
        return None

    def _handle_permission_request(self, msg: Dict[str, Any]) -> None:
        params = msg.get("params") or {}
        options = params.get("options") or []
        tool_name, command = self._extract_tool_call(params)
        ticket_id = params.get("ticket_id") or params.get("ticketId")

        verdict_record: Dict[str, Any] = {}
        if self.permission_evaluator is not None:
            try:
                verdict_record = self.permission_evaluator(tool_name, command, ticket_id) or {}
            except Exception as exc:  # fail closed
                verdict_record = {"verdict": "DENY_POLICY_ERROR", "reason_code": "evaluator_error",
                                  "explanation": str(exc)[:200]}
        else:
            verdict_record = {"verdict": "ALLOW", "reason_code": "no_policy_evaluator"}

        verdict = str(verdict_record.get("verdict") or "ALLOW")
        decision = AcpPermissionDecision(verdict=verdict,
                                         reason_code=str(verdict_record.get("reason_code") or ""),
                                         ticket_id=verdict_record.get("ticket_id"))

        if verdict.startswith("ALLOW"):
            oid = self._pick_option(options, ("allow_once", "allow_always"))
            if oid is None and options:
                oid = str(options[0].get("optionId") or options[0].get("id") or "")
            decision.outcome, decision.option_id = "selected", oid or None
        elif verdict.startswith("HOLD"):
            # No native "ask" in ACP permission reply — reject with ticket info.
            decision.outcome = "cancelled"
        else:  # DENY or unknown → fail closed
            oid = self._pick_option(options, ("reject_once", "reject_always"))
            if oid is not None:
                decision.outcome, decision.option_id = "selected", oid
            else:
                decision.outcome = "cancelled"
        self.permission_decisions.append(decision)
        self._send({"jsonrpc": "2.0", "id": msg.get("id"),
                    "result": {"outcome": {"outcome": decision.outcome,
                                           **({"optionId": decision.option_id} if decision.option_id else {})}}})

    # -- session lifecycle -----------------------------------------------

    def initialize(self) -> Dict[str, Any]:
        return self._request("initialize", {
            "protocolVersion": ACP_PROTOCOL_VERSION,
            "clientCapabilities": {"fs": {"readTextFile": False, "writeTextFile": False},
                                   "terminal": False},
            "clientInfo": {"name": "keelway", "version": "1.1.0"},
        })

    def session_new(self, cwd: Optional[str] = None) -> str:
        params: Dict[str, Any] = {"cwd": cwd or self.cwd or os.getcwd(), "mcpServers": []}
        result = self._request("session/new", params)
        sid = result.get("sessionId") or result.get("session_id")
        if not sid:
            raise RuntimeError(f"ACP session/new returned no sessionId: {result}")
        self._session_id = str(sid)
        return self._session_id

    def prompt(self, text: str) -> str:
        """Send session/prompt and drain until the prompt response arrives."""
        assert self._session_id is not None
        self._next_id += 1
        rid = self._next_id
        self._send({"jsonrpc": "2.0", "id": rid, "method": "session/prompt",
                    "params": {"sessionId": self._session_id,
                               "prompt": [{"type": "text", "text": text}]}})
        result = self._await_response(rid)
        self._stop_reason = str(result.get("stopReason") or result.get("stop_reason") or "")
        return self._stop_reason

    def run_prompt(self, text: str, cwd: Optional[str] = None) -> AcpSessionResult:
        """Full lifecycle: initialize → session/new → prompt."""
        try:
            self.start()
            self.initialize()
            self.session_new(cwd=cwd)
            stop = self.prompt(text)
            return AcpSessionResult(agent_id=os.path.basename(self.argv[0]),
                                    returncode=self._proc.poll() if self._proc else None,
                                    stop_reason=stop, events=list(self.events),
                                    permission_decisions=list(self.permission_decisions))
        except Exception as exc:
            return AcpSessionResult(agent_id=os.path.basename(self.argv[0]),
                                    returncode=self._proc.poll() if self._proc else None,
                                    events=list(self.events),
                                    permission_decisions=list(self.permission_decisions),
                                    error=str(exc)[:300])
        finally:
            self.close()

    def close(self) -> None:
        if self._proc is not None:
            try:
                if self._proc.stdin:
                    self._proc.stdin.close()
            except OSError:
                pass
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
            self._proc = None


def run_acp_session(argv: List[str], prompt_text: str, *,
                    agent_id: str = "acp",
                    workspace_id: str = "default",
                    permission_evaluator: Optional[PermissionEvaluator] = None,
                    cwd: Optional[str] = None,
                    env: Optional[Dict[str, str]] = None,
                    event_sink: Optional[Callable[[Dict[str, Any]], None]] = None,
                    rpc_timeout: float = 30.0) -> AcpSessionResult:
    """Spawn an ACP agent and run one governed prompt session.

    `permission_evaluator` receives (tool_name, command, ticket_id) and must
    return an intercept record; wire it to `intercept_tool_call` for the
    full P-10/DLP/destructive-command policy path.
    """
    client = AcpClient(argv, cwd=cwd, env=env,
                       permission_evaluator=permission_evaluator,
                       event_sink=event_sink, rpc_timeout=rpc_timeout)
    result = client.run_prompt(prompt_text, cwd=cwd)
    result.agent_id = agent_id
    return result
