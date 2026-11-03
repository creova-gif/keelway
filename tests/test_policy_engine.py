"""Tests for Keelway Policy Engine (FR-02).
Validates deny-by-default rules, sensitive target denial, and signed decision verification.
"""
from keelway.core.models import DecisionEnum, ToolAuthorizationRequest
from keelway.policy.engine import PolicyEngine


def test_policy_denies_unknown_tool_by_default():
    engine = PolicyEngine()
    req = ToolAuthorizationRequest(
        run_id="run_101",
        tool="unregistered_malicious_tool",
        action_digest="sha256:abcd",
        scope={"repo": "sorvex/demo"},
        actor_id="user_1",
        policy_version="default_governed_v1",
    )
    decision = engine.evaluate(req)
    assert decision.decision == DecisionEnum.DENY
    assert decision.reason_code == "ERR_POLICY_TOOL_NOT_PERMITTED"
    assert engine.verify_decision_signature(decision, req.tool) is True


def test_policy_denies_sensitive_file_targets():
    engine = PolicyEngine()
    sensitive_targets = [".env", "config/credentials.json", "id_rsa", "/etc/shadow"]

    for path in sensitive_targets:
        req = ToolAuthorizationRequest(
            run_id="run_102",
            tool="git.write_patch",
            action_digest="sha256:1234",
            scope={"repo": "sorvex/demo", "path": path},
            actor_id="user_1",
            policy_version="default_governed_v1",
        )
        decision = engine.evaluate(req)
        assert decision.decision == DecisionEnum.DENY
        assert decision.reason_code == "ERR_POLICY_SENSITIVE_TARGET_FORBIDDEN"


def test_policy_denies_unauthorized_network_egress():
    engine = PolicyEngine()
    req = ToolAuthorizationRequest(
        run_id="run_103",
        tool="sandbox.exec_test",
        action_digest="sha256:5678",
        scope={"network_egress": True},
        actor_id="user_1",
        policy_version="default_governed_v1",
    )
    decision = engine.evaluate(req)
    assert decision.decision == DecisionEnum.DENY
    assert decision.reason_code == "ERR_POLICY_EGRESS_NETWORK_BLOCKED"


def test_policy_requires_human_approval_for_patch_writing():
    engine = PolicyEngine()
    req = ToolAuthorizationRequest(
        run_id="run_104",
        tool="git.write_patch",
        action_digest="sha256:9999",
        scope={"repo": "sorvex/demo", "path": "src/app.py"},
        actor_id="user_1",
        policy_version="default_governed_v1",
    )
    decision = engine.evaluate(req)
    assert decision.decision == DecisionEnum.REQUIRE_APPROVAL
    assert decision.reason_code == "INFO_POLICY_HUMAN_APPROVAL_REQUIRED"


def test_policy_rejects_forged_decision_signature():
    engine = PolicyEngine()
    req = ToolAuthorizationRequest(
        run_id="run_105",
        tool="git.read",
        action_digest="sha256:0000",
        scope={},
        actor_id="user_1",
        policy_version="default_governed_v1",
    )
    decision = engine.evaluate(req)
    assert decision.decision == DecisionEnum.ALLOW

    # Forged signature
    decision.signature = "forged_signature_000000000000000000000000000000"
    assert engine.verify_decision_signature(decision, req.tool) is False
