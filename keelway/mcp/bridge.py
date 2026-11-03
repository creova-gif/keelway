"""Keelway Model Context Protocol (MCP) Security Governance Bridge.
Intercepts all MCP tool calls, enforces deny-by-default policy evaluations,
and maintains audit trail linkage for cross-agent tool operations (PRD-001 TB2/TB3).
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Callable, Dict, Optional, Tuple

from keelway.audit.recorder import AuditRecorder
from keelway.core.models import DecisionEnum, ToolAuthorizationRequest
from keelway.policy.engine import PolicyEngine


class MCPGovernanceError(Exception):
    pass


class MCPToolDeniedError(MCPGovernanceError):
    pass


class MCPGovernanceBridge:
    """Governs MCP JSON-RPC tool invocations with fail-closed policy checks."""

    def __init__(
        self,
        policy_engine: PolicyEngine,
        audit_recorder: Optional[AuditRecorder] = None,
        policy_version: str = "default_governed_v1",
    ):
        self.policy_engine = policy_engine
        self.audit_recorder = audit_recorder
        self.policy_version = policy_version

    def compute_action_digest(self, arguments: Dict[str, Any]) -> str:
        """Computes deterministic SHA-256 digest of tool arguments."""
        canonical = json.dumps(arguments, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def intercept_and_call(
        self,
        server_name: str,
        tool_name: str,
        arguments: Dict[str, Any],
        run_id: str,
        actor_id: str,
        target_executor: Optional[Callable[[Dict[str, Any]], Any]] = None,
    ) -> Tuple[bool, Any, Optional[str]]:
        """Intercepts an MCP tool call and evaluates it against the active policy.
        
        Returns:
            (success, result, error_reason)
        """
        scoped_tool_id = f"mcp:{server_name}:{tool_name}"
        action_digest = self.compute_action_digest(arguments)

        auth_req = ToolAuthorizationRequest(
            run_id=run_id,
            tool=scoped_tool_id,
            action_digest=action_digest,
            scope=arguments,
            actor_id=actor_id,
            policy_version=self.policy_version,
        )

        decision = self.policy_engine.evaluate(auth_req)

        # Audit policy decision
        if self.audit_recorder:
            self.audit_recorder.record_event(
                "MCP_POLICY_EVALUATED",
                {
                    "tool": scoped_tool_id,
                    "action_digest": action_digest,
                    "decision": decision.decision.value,
                    "reason_code": decision.reason_code,
                },
            )

        if decision.decision == DecisionEnum.DENY:
            if self.audit_recorder:
                self.audit_recorder.record_event(
                    "MCP_TOOL_BLOCKED",
                    {"tool": scoped_tool_id, "reason": decision.reason_code},
                )
            return False, None, f"ERR_MCP_TOOL_POLICY_DENIED: {decision.reason_code}"

        if decision.decision == DecisionEnum.REQUIRE_APPROVAL:
            return False, None, "ERR_MCP_TOOL_REQUIRES_HUMAN_APPROVAL"

        # ALLOW: Execute the actual underlying MCP tool
        try:
            if target_executor:
                result = target_executor(arguments)
            else:
                result = {"status": "success", "executed_tool": scoped_tool_id}

            if self.audit_recorder:
                self.audit_recorder.record_event(
                    "MCP_TOOL_EXECUTED",
                    {
                        "tool": scoped_tool_id,
                        "action_digest": action_digest,
                        "status": "SUCCESS",
                    },
                )
            return True, result, None
        except Exception as e:
            if self.audit_recorder:
                self.audit_recorder.record_event(
                    "MCP_TOOL_EXECUTION_FAILED",
                    {"tool": scoped_tool_id, "error": str(e)},
                )
            return False, None, f"ERR_MCP_TOOL_EXECUTION_FAILED: {e}"
