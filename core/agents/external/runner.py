"""Agent process runner for third-party coding-agent CLIs (KEEL-ENG-047).

Launches an adapter's `LaunchSpec` as a real subprocess with streamed
stdout/stderr capture, bounded output, timeout enforcement, and DLP-scrubbed
summaries suitable for flight-tape evidence.

Policy boundary (honest): the runner does NOT interpose on the agent's own
tool calls — enforcement for hook-capable hosts happens through the installed
PreToolUse hook config (`harness hooks` / `agents intercept`). This module
provides launch + observability + evidence, which is what the conformance
criterion "launch produces a normalized event stream" requires.
"""

from __future__ import annotations

import json
import queue
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from core.agents.external.base import AgentHostAdapter, LaunchSpec
from core.security.redact import redact_text

DEFAULT_TIMEOUT_S = 120.0
_MAX_EVENTS = 5000
_MAX_EVENT_BYTES = 64 * 1024
_TAIL_PREVIEW_CHARS = 4000


class AgentRunError(RuntimeError):
    """Raised when an agent process cannot be launched or exceeds bounds."""


@dataclass
class AgentRunEvent:
    """One normalized output event from the agent process."""

    stream: str  # "stdout" | "stderr"
    line: str
    line_no: int
    ts_ms: float

    def to_dict(self) -> Dict[str, Any]:
        return {"stream": self.stream, "line": self.line,
                "line_no": self.line_no, "ts_ms": self.ts_ms}


@dataclass
class AgentRunResult:
    """Outcome of a bounded agent process run."""

    agent_id: str
    argv: List[str]
    exit_code: Optional[int]
    timed_out: bool
    duration_ms: float
    events: List[AgentRunEvent] = field(default_factory=list)
    stdout_lines: int = 0
    stderr_lines: int = 0
    truncated: bool = False

    def preview(self, stream: str = "stdout", tail: int = 20) -> List[str]:
        lines = [e.line for e in self.events if e.stream == stream]
        return lines[-tail:]

    def scrubbed_summary(self) -> Dict[str, Any]:
        """DLP-scrubbed summary safe for flight tapes / logs."""
        preview_lines = self.preview("stdout", tail=10) + self.preview("stderr", tail=5)
        scrubbed: List[str] = []
        redactions = 0
        for line in preview_lines:
            clean, n = redact_text(str(line))
            redactions += n
            scrubbed.append(clean[:_TAIL_PREVIEW_CHARS])
        return {
            "agent_id": self.agent_id,
            "exit_code": self.exit_code,
            "timed_out": self.timed_out,
            "duration_ms": round(self.duration_ms, 3),
            "stdout_lines": self.stdout_lines,
            "stderr_lines": self.stderr_lines,
            "truncated": self.truncated,
            "dlp_redactions": redactions,
            "output_preview": scrubbed,
        }


def _drain_stream(stream: Any, name: str, events: List[AgentRunEvent],
                  counters: Dict[str, int], state: Dict[str, Any]) -> None:
    """Reader thread: append normalized events until EOF or caps hit."""
    while True:
        try:
            raw = stream.readline(_MAX_EVENT_BYTES + 1)
        except (OSError, ValueError):
            break
        if not raw:
            break
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="replace")
        counters[name] += 1
        line = raw.rstrip("\n").rstrip("\r")
        if len(events) < _MAX_EVENTS:
            events.append(AgentRunEvent(stream=name, line=line[:_MAX_EVENT_BYTES],
                                        line_no=counters[name], ts_ms=round(time.monotonic() * 1000, 3)))
        else:
            state["truncated"] = True


def run_agent_process(
    adapter: AgentHostAdapter,
    spec: Optional[LaunchSpec] = None,
    workspace_root: Optional[str] = None,
    extra_args: Optional[List[str]] = None,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    on_event: Optional[Callable[[AgentRunEvent], None]] = None,
) -> AgentRunResult:
    """Launch the agent CLI and stream its output into normalized events.

    Uses the adapter's `LaunchSpec` (env-scrubbed). Times out by terminating
    the process; never returns a partial success as exit_code=None without
    `timed_out=True`.
    """
    launch = spec or adapter.build_launch(workspace_root=workspace_root, extra_args=extra_args)
    argv = list(launch.argv)
    try:
        proc = subprocess.Popen(
            argv,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=launch.cwd,
            env=launch.env,
            bufsize=0,
        )
    except OSError as exc:
        raise AgentRunError(f"Failed to launch '{adapter.agent_id}': {exc}") from exc

    events: List[AgentRunEvent] = []
    counters = {"stdout": 0, "stderr": 0}
    state: Dict[str, Any] = {"truncated": False}
    readers = [
        threading.Thread(target=_drain_stream,
                         args=(proc.stdout, "stdout", events, counters, state), daemon=True),
        threading.Thread(target=_drain_stream,
                         args=(proc.stderr, "stderr", events, counters, state), daemon=True),
    ]
    for t in readers:
        t.start()

    t0 = time.monotonic()
    timed_out = False
    try:
        proc.wait(timeout=timeout_s)
        exit_code: Optional[int] = proc.returncode
    except subprocess.TimeoutExpired:
        timed_out = True
        proc.kill()
        proc.wait(timeout=5)
        exit_code = proc.returncode
    finally:
        for t in readers:
            t.join(timeout=2)

    duration_ms = (time.monotonic() - t0) * 1000.0
    result = AgentRunResult(
        agent_id=adapter.agent_id, argv=argv, exit_code=exit_code,
        timed_out=timed_out, duration_ms=duration_ms, events=events,
        stdout_lines=counters["stdout"], stderr_lines=counters["stderr"],
        truncated=bool(state["truncated"]),
    )
    if on_event is not None:
        for ev in events:
            on_event(ev)
    return result


def run_result_to_tape_span(result: AgentRunResult) -> Dict[str, Any]:
    """Convert an `AgentRunResult` into a flight-tape span dict."""
    summary = result.scrubbed_summary()
    return {
        "span_kind": "agent",
        "node_name": f"external-run:{result.agent_id}",
        "model_id": f"external-agent:{result.agent_id}",
        "prompt": " ".join(result.argv)[:2000],
        "output": summary,
        "state": {"timed_out": result.timed_out, "truncated": result.truncated,
                  "exit_code": result.exit_code},
    }
