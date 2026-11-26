"""Keelway Policy Engine.
Implements FR-02: Deny-by-default rule evaluation, structured deny reasons,
approval escalation, and signed decision generation.
"""
from __future__ import annotations

import datetime
import hashlib
import hmac
import uuid
from typing import Dict, Optional, Set

from keelway.core.models import DecisionEnum, PolicyDecision, ToolAuthorizationRequest

DEFAULT_POLICY_SIGNING_KEY = b"keelway_local_policy_signing_key_secret_v1"
FORBIDDEN_FILE_PATTERNS = {
    ".env",
    ".aws/",
    ".ssh/",
    "id_rsa",
    "credentials",
    "secret",
    "password",
    "/etc/",
    "/root/",
}


class PolicyRule:
    def __init__(
        self,
        name: str,
        allowed_tools: Set[str],
        allowed_repos: Set[str],
        allow_network: bool = False,
        require_approval_tools: Optional[Set[str]] = None,
        max_tokens_per_run: int = 50000,
        max_cost_cents: int = 500,
    ):
        self.name = name
        self.allowed_tools = allowed_tools
        self.allowed_repos = allowed_repos
        self.allow_network = allow_network
        self.require_approval_tools = require_approval_tools or set()
        self.max_tokens_per_run = max_tokens_per_run
        self.max_cost_cents = max_cost_cents


class PolicyEngine:
    """Evaluates requests against fail-closed security policies."""

    def __init__(
        self,
        policy_id: str = "default_governed_v1",
        signing_key: bytes = DEFAULT_POLICY_SIGNING_KEY,
        decision_ttl_seconds: int = 600,
    ):
        self.policy_id = policy_id
        self.signing_key = signing_key
        self.decision_ttl_seconds = decision_ttl_seconds
        self.rules: Dict[str, PolicyRule] = {
            "default_governed_v1": PolicyRule(
                name="default_governed_v1",
                allowed_tools={
                    "git.read",
                    "git.diff",
                    "git.write_patch",
                    "sandbox.exec_test",
                    "eval.run",
                    "git.create_pr",
                },
                allowed_repos={"*"},
                allow_network=False,
                require_approval_tools={"git.write_patch", "git.create_pr"},
            )
        }

    def sign_decision(
        self, decision_id: str, run_id: str, tool: str, action_digest: str, expires_at: str
    ) -> str:
        """Signs the decision context to prevent tampering or forged authorizations."""
        message = f"{decision_id}:{run_id}:{tool}:{action_digest}:{expires_at}:{self.policy_id}"
        return hmac.new(self.signing_key, message.encode("utf-8"), hashlib.sha256).hexdigest()

    def verify_decision_signature(self, decision: PolicyDecision, tool: str) -> bool:
        """Verifies if a decision signature is valid and untampered."""
        expected_sig = self.sign_decision(
            decision.decision_id,
            decision.run_id,
            tool,
            decision.action_digest,
            decision.expires_at,
        )
        return hmac.compare_digest(decision.signature, expected_sig)

    def is_expired(self, expires_at: str) -> bool:
        """Checks if a decision timestamp has elapsed."""
        try:
            exp = datetime.datetime.fromisoformat(expires_at)
            now = datetime.datetime.now(datetime.timezone.utc)
            return now > exp
        except Exception:
            return True

    def evaluate(self, request: ToolAuthorizationRequest) -> PolicyDecision:
        """Evaluates an authorization request under deny-by-default invariants."""
        now = datetime.datetime.now(datetime.timezone.utc)
        expires_at = (
            now + datetime.timedelta(seconds=self.decision_ttl_seconds)
        ).isoformat()
        decision_id = str(uuid.uuid4())

        rule = self.rules.get(request.policy_version)
        if not rule:
            # Deny by default if policy version is unknown or revoked
            sig = self.sign_decision(
                decision_id, request.run_id, request.tool, request.action_digest, expires_at
            )
            return PolicyDecision(
                decision=DecisionEnum.DENY,
                reason_code="ERR_POLICY_VERSION_UNKNOWN_OR_EXPIRED",
                decision_id=decision_id,
                expires_at=expires_at,
                run_id=request.run_id,
                action_digest=request.action_digest,
                signature=sig,
            )

        # Check for forbidden sensitive file patterns in scope
        target_path = str(request.scope.get("path", "")).lower()
        for forbidden in FORBIDDEN_FILE_PATTERNS:
            if forbidden in target_path:
                sig = self.sign_decision(
                    decision_id, request.run_id, request.tool, request.action_digest, expires_at
                )
                return PolicyDecision(
                    decision=DecisionEnum.DENY,
                    reason_code="ERR_POLICY_SENSITIVE_TARGET_FORBIDDEN",
                    decision_id=decision_id,
                    expires_at=expires_at,
                    run_id=request.run_id,
                    action_digest=request.action_digest,
                    signature=sig,
                )

        # Check network access if requested
        if request.scope.get("network_egress", False) and not rule.allow_network:
            sig = self.sign_decision(
                decision_id, request.run_id, request.tool, request.action_digest, expires_at
            )
            return PolicyDecision(
                decision=DecisionEnum.DENY,
                reason_code="ERR_POLICY_EGRESS_NETWORK_BLOCKED",
                decision_id=decision_id,
                expires_at=expires_at,
                run_id=request.run_id,
                action_digest=request.action_digest,
                signature=sig,
            )

        # Check if tool is allowed at all
        if request.tool not in rule.allowed_tools:
            sig = self.sign_decision(
                decision_id, request.run_id, request.tool, request.action_digest, expires_at
            )
            return PolicyDecision(
                decision=DecisionEnum.DENY,
                reason_code="ERR_POLICY_TOOL_NOT_PERMITTED",
                decision_id=decision_id,
                expires_at=expires_at,
                run_id=request.run_id,
                action_digest=request.action_digest,
                signature=sig,
            )

        # Check if tool requires explicit human approval
        if request.tool in rule.require_approval_tools:
            sig = self.sign_decision(
                decision_id, request.run_id, request.tool, request.action_digest, expires_at
            )
            return PolicyDecision(
                decision=DecisionEnum.REQUIRE_APPROVAL,
                reason_code="INFO_POLICY_HUMAN_APPROVAL_REQUIRED",
                decision_id=decision_id,
                expires_at=expires_at,
                run_id=request.run_id,
                action_digest=request.action_digest,
                signature=sig,
            )

        # Otherwise tool is allowed
        sig = self.sign_decision(
            decision_id, request.run_id, request.tool, request.action_digest, expires_at
        )
        return PolicyDecision(
            decision=DecisionEnum.ALLOW,
            reason_code="INFO_POLICY_ALLOWED",
            decision_id=decision_id,
            expires_at=expires_at,
            run_id=request.run_id,
            action_digest=request.action_digest,
            signature=sig,
        )
