"""Tests for Keelway Model Context Protocol (MCP) Governance Bridge (PRD-001).
Validates MCP tool call interception, fail-closed policy checks, and audit logging.
"""
from keelway.audit.recorder import AuditRecorder
from keelway.mcp.bridge import MCPGovernanceBridge
from keelway.policy.engine import PolicyEngine, PolicyRule


def test_mcp_bridge_blocks_unauthorized_tool():
    policy = PolicyEngine()
    audit = AuditRecorder(run_id="run_mcp_01")
    bridge = MCPGovernanceBridge(policy_engine=policy, audit_recorder=audit)

    # Calling an unauthorized MCP tool (e.g., arbitrary shell execution)
    ok, res, err = bridge.intercept_and_call(
        server_name="terminal",
        tool_name="bash_exec",
        arguments={"command": "rm -rf /"},
        run_id="run_mcp_01",
        actor_id="coding_agent",
    )
    assert ok is False
    assert res is None
    assert "ERR_MCP_TOOL_POLICY_DENIED" in err
    assert "ERR_POLICY_TOOL_NOT_PERMITTED" in err

    # Verify audit events
    assert len(audit.events) == 2
    assert audit.events[0].kind == "MCP_POLICY_EVALUATED"
    assert audit.events[1].kind == "MCP_TOOL_BLOCKED"


def test_mcp_bridge_blocks_sensitive_file_targets():
    policy = PolicyEngine()
    audit = AuditRecorder(run_id="run_mcp_02")
    bridge = MCPGovernanceBridge(policy_engine=policy, audit_recorder=audit)

    # Calling a tool targeting .env or credentials
    ok, res, err = bridge.intercept_and_call(
        server_name="filesystem",
        tool_name="read_file",
        arguments={"path": "/app/.env"},
        run_id="run_mcp_02",
        actor_id="coding_agent",
    )
    assert ok is False
    assert "ERR_POLICY_SENSITIVE_TARGET_FORBIDDEN" in err


def test_mcp_bridge_permits_authorized_tool():
    policy = PolicyEngine()
    # Add an allowed MCP tool to the policy rule
    policy.rules["default_governed_v1"].allowed_tools.add("mcp:git:diff")

    audit = AuditRecorder(run_id="run_mcp_03")
    bridge = MCPGovernanceBridge(policy_engine=policy, audit_recorder=audit)

    def mock_executor(args):
        return {"diff": "+ code", "repo": args["repo"]}

    ok, res, err = bridge.intercept_and_call(
        server_name="git",
        tool_name="diff",
        arguments={"repo": "sorvex/core"},
        run_id="run_mcp_03",
        actor_id="coding_agent",
        target_executor=mock_executor,
    )
    assert ok is True
    assert err is None
    assert res["diff"] == "+ code"
    assert audit.events[-1].kind == "MCP_TOOL_EXECUTED"
