"""Adapter contract for third-party coding-agent hosts.

An adapter describes how to detect an installed agent CLI, build a scrubbed
launch specification, and normalize the host's native hook/event payloads into
the canonical `NormalizedToolCall` consumed by the Keelway co-harness policy
engine. Adapters never implement their own policy — verdicts come from
`SQLiteAgentCoharnessEngine.intercept_tool_call`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class AgentDetection:
    """Result of probing a host for an installed agent CLI."""

    agent_id: str
    installed: bool
    binary_path: Optional[str] = None
    version: Optional[str] = None
    detail: str = ""


@dataclass(frozen=True)
class LaunchSpec:
    """Environment-scrubbed subprocess specification for launching an agent."""

    agent_id: str
    argv: List[str]
    env: Dict[str, str]
    cwd: Optional[str] = None


@dataclass(frozen=True)
class NormalizedToolCall:
    """Canonical tool-call extracted from a host-native hook/event payload."""

    agent_id: str
    tool_name: str
    command: str
    ticket_id: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)


class AgentHostAdapter:
    """Base contract for a third-party coding-agent host integration."""

    agent_id: str = ""
    display_name: str = ""
    binary_name: str = ""
    hook_event: str = "PreToolUse"
    supported_modes: tuple = ("audit_only", "enforce")

    def capabilities(self) -> Dict[str, Any]:
        """Declared integration capabilities (honest, per-host)."""
        return {
            "agent_id": self.agent_id,
            "display_name": self.display_name,
            "hook_event": self.hook_event,
            "modes": list(self.supported_modes),
            "process_launch": True,
            "mcp_client": True,
        }

    def detect(self) -> AgentDetection:
        """Probe PATH for the agent binary and capture `--version` output."""
        raise NotImplementedError

    def build_launch(self, workspace_root: Optional[str] = None,
                     extra_args: Optional[List[str]] = None) -> LaunchSpec:
        """Build an env-scrubbed launch spec for the agent CLI."""
        raise NotImplementedError

    def parse_hook_payload(self, payload: Dict[str, Any]) -> NormalizedToolCall:
        """Normalize a host-native hook payload into a `NormalizedToolCall`."""
        raise NotImplementedError
