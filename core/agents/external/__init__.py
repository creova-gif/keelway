"""Third-party coding-agent adapters (KEEL-ENG-043 / THIRD_PARTY_AGENT_INTEGRATION Phase C).

Adapters govern external agent hosts (Claude Code, Codex CLI, ...) without
replacing `AutonomousAgentLoop`: detection, env-scrubbed launch specs, host
hook-payload normalization, and policy evaluation delegated to the existing
`SQLiteAgentCoharnessEngine.intercept_tool_call` verdict authority.
"""

from core.agents.external.base import (
    AgentDetection,
    AgentHostAdapter,
    LaunchSpec,
    NormalizedToolCall,
)
from core.agents.external.hosts import (
    ClaudeCodeAdapter,
    CodexCliAdapter,
    CursorAgentAdapter,
    GeminiCliAdapter,
    HermesAcpAdapter,
    OpenCodeAdapter,
    EXTERNAL_AGENT_ADAPTERS,
    detect_external_agents,
    get_adapter,
)
from core.agents.external.policy import evaluate_hook_payload
from core.agents.external.events import record_agent_event, VALID_AGENT_EVENTS

__all__ = [
    "AgentDetection",
    "AgentHostAdapter",
    "ClaudeCodeAdapter",
    "CodexCliAdapter",
    "CursorAgentAdapter",
    "GeminiCliAdapter",
    "HermesAcpAdapter",
    "OpenCodeAdapter",
    "EXTERNAL_AGENT_ADAPTERS",
    "LaunchSpec",
    "NormalizedToolCall",
    "VALID_AGENT_EVENTS",
    "detect_external_agents",
    "evaluate_hook_payload",
    "get_adapter",
    "record_agent_event",
]
