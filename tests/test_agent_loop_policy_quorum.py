"""
Tests for AutonomousAgentLoop integration with PolicyEngine (FR-02)
and TwoHumanQuorumService (ADR-045/ADR-046).
"""

import pytest
from core.orchestration.agent_loop import AutonomousAgentLoop, AgentLoopStatus, AutonomyPolicy
from core.storage.workspace_fs import WorkspaceFilesystem
from keelway.policy.engine import PolicyEngine
from keelway.approvals.quorum import TwoHumanQuorumService


@pytest.mark.asyncio
async def test_agent_loop_policy_denies_sensitive_target(tmp_path):
    fs = WorkspaceFilesystem(root_dir=str(tmp_path))
    policy_engine = PolicyEngine()
    agent = AutonomousAgentLoop(
        task_id="task_policy_deny_sensitive",
        workspace_fs=fs,
        policy=AutonomyPolicy.AUTONOMOUS,
        policy_engine=policy_engine,
    )

    # Attempt to read forbidden .env file
    res = await agent.execute_tool(tool_name="read_file", arguments={"path": ".env"})
    assert res["status"] == "denied_by_policy"
    assert res["reason_code"] == "ERR_POLICY_SENSITIVE_TARGET_FORBIDDEN"
    assert "signature" in res


@pytest.mark.asyncio
async def test_agent_loop_policy_denies_unpermitted_tool(tmp_path):
    fs = WorkspaceFilesystem(root_dir=str(tmp_path))
    policy_engine = PolicyEngine()
    agent = AutonomousAgentLoop(
        task_id="task_policy_deny_unregistered",
        workspace_fs=fs,
        policy=AutonomyPolicy.AUTONOMOUS,
        policy_engine=policy_engine,
    )

    # Register an untrusted custom tool on the agent
    async def _dummy(args):
        return {"done": True}

    from core.orchestration.agent_loop import AgentTool
    agent.tools["unauthorized_network_dump"] = AgentTool(
        name="unauthorized_network_dump",
        description="unauthorized",
        parameters={},
        is_mutation=False,
        handler=_dummy,
    )

    res = await agent.execute_tool(tool_name="unauthorized_network_dump", arguments={})
    assert res["status"] == "denied_by_policy"
    assert res["reason_code"] == "ERR_POLICY_TOOL_NOT_PERMITTED"


@pytest.mark.asyncio
async def test_agent_loop_two_human_quorum_lifecycle(tmp_path):
    fs = WorkspaceFilesystem(root_dir=str(tmp_path))
    # Create test file
    fs.write_file("main.py", "print('hello v1')\n")

    policy_engine = PolicyEngine()
    quorum_service = TwoHumanQuorumService(signing_key=b"package-c-explicit-quorum-fixture-key")

    agent = AutonomousAgentLoop(
        task_id="task_prod_quorum_01",
        workspace_fs=fs,
        policy=AutonomyPolicy.CONFIRM_MUTATION,
        policy_engine=policy_engine,
        quorum_service=quorum_service,
        environment="production",
    )

    # Trigger mutating write_file on production environment
    res = await agent.execute_tool(
        tool_name="write_file",
        arguments={"path": "main.py", "content": "print('production update')\n"},
    )

    # Agent must pause for quorum!
    assert res["status"] == "paused_for_quorum"
    assert agent.status == AgentLoopStatus.AWAITING_APPROVAL
    pending = res["pending"]
    assert pending["requires_quorum"] is True
    quorum_id = pending["quorum_id"]
    assert quorum_id is not None
    assert set(pending["required_roles"]) == {"Security Lead", "Platform Owner"}

    # Premature approval must fail because quorum is not yet satisfied
    premature_res = await agent.approve_pending(approved=True)
    assert premature_res["status"] == "quorum_not_satisfied"
    assert agent.status == AgentLoopStatus.AWAITING_APPROVAL

    # 1. Security Lead signs
    sec_res = agent.submit_quorum_approval(
        principal_id="alice_sec_lead",
        role="Security Lead",
    )
    assert sec_res["status"] == "pending_remaining_approvers"
    assert "Security Lead" in sec_res["signatures_collected"]
    assert "Platform Owner" in sec_res["signatures_remaining"]

    # Self-quorum attempt must fail (same human signing as Platform Owner)
    self_res = agent.submit_quorum_approval(
        principal_id="alice_sec_lead",
        role="Platform Owner",
    )
    assert self_res["status"] == "error"

    # 2. Distinct Platform Owner signs
    plat_res = agent.submit_quorum_approval(
        principal_id="bob_plat_owner",
        role="Platform Owner",
    )
    assert plat_res["status"] == "fully_approved"

    # Now that quorum is achieved, approve_pending executes the mutating tool!
    exec_res = await agent.approve_pending(approved=True)
    assert exec_res["status"] == "success"
    assert exec_res["tool"] == "write_file"

    # Verify workspace was mutated under quorum authority
    read_back = fs.read_file("main.py")
    assert "production update" in read_back["content"]
