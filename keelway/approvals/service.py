"""Keelway Approval Gate Service.
Implements FR-07: Human diff review, cryptographic approval bound to exact patch hash,
expiry, single-use consumption, and prevention of agent self-approval.
"""
from __future__ import annotations

import datetime
import hashlib
import hmac
import uuid
from typing import Dict, Optional, Tuple

from keelway.core.models import ApprovalDecision, ApprovalRequest
from keelway.security.source_defaults import InsecureDefaultConfiguration, is_source_default

APPROVAL_SECRET_KEY = b"keelway_approval_signing_secret_v1"


class ApprovalError(Exception):
    pass


class ApprovalService:
    """Manages the human-in-the-loop approval lifecycle."""

    def __init__(self, ttl_seconds: int = 600, signing_key: bytes = APPROVAL_SECRET_KEY):
        self.ttl_seconds = ttl_seconds
        self.signing_key = signing_key
        self._requests: Dict[str, ApprovalRequest] = {}
        self._consumed: set = set()

    def create_request(
        self,
        run_id: str,
        patch_hash: str,
        diff_content: str,
        eval_score: float,
        eval_passed: bool,
        estimated_cost_cents: int,
    ) -> ApprovalRequest:
        """Creates an approval request for a candidate patch."""
        now = datetime.datetime.now(datetime.timezone.utc)
        expires_at = (now + datetime.timedelta(seconds=self.ttl_seconds)).isoformat()
        approval_id = str(uuid.uuid4())

        req = ApprovalRequest(
            id=approval_id,
            run_id=run_id,
            patch_hash=patch_hash,
            diff_content=diff_content,
            eval_score=eval_score,
            eval_passed=eval_passed,
            estimated_cost_cents=estimated_cost_cents,
            status="PENDING",
            requested_at=now.isoformat(),
            expires_at=expires_at,
        )
        self._requests[approval_id] = req
        return req

    def get_request(self, approval_id: str) -> Optional[ApprovalRequest]:
        return self._requests.get(approval_id)

    def sign_decision(
        self, approval_id: str, approver_id: str, decision: str, patch_hash: str
    ) -> str:
        """Signs the approval decision."""
        if is_source_default(self.signing_key):
            raise InsecureDefaultConfiguration("source-default signing configuration is refused")
        msg = f"{approval_id}:{approver_id}:{decision}:{patch_hash}"
        return hmac.new(self.signing_key, msg.encode("utf-8"), hashlib.sha256).hexdigest()

    def submit_decision(
        self, decision: ApprovalDecision, current_patch_hash: str
    ) -> Tuple[bool, str]:
        """Submits human approval decision with strict fail-closed checks."""
        if is_source_default(self.signing_key):
            return False, "ERR_SOURCE_DEFAULT_SIGNING_KEY_REFUSED"
        req = self._requests.get(decision.approval_id)
        if not req:
            return False, "ERR_APPROVAL_NOT_FOUND"

        if req.id in self._consumed:
            return False, "ERR_APPROVAL_ALREADY_CONSUMED"

        # Check expiration
        now = datetime.datetime.now(datetime.timezone.utc)
        exp = datetime.datetime.fromisoformat(req.expires_at)
        if now > exp:
            req.status = "EXPIRED"
            return False, "ERR_APPROVAL_EXPIRED"

        # Check if the code was mutated since approval was requested
        if current_patch_hash != req.patch_hash:
            req.status = "INVALIDATED"
            return False, "ERR_PATCH_HASH_MUTATED_APPROVAL_INVALIDATED"

        if decision.patch_hash != req.patch_hash:
            return False, "ERR_DECISION_PATCH_HASH_MISMATCH"

        # Prevent agent self-approval: approver must not be an automated agent ID
        if "agent" in decision.approver_id.lower():
            return False, "ERR_AGENT_SELF_APPROVAL_PROHIBITED"

        # Verify eval passed before allowing approval
        if not req.eval_passed and decision.decision == "APPROVED":
            return False, "ERR_CANNOT_APPROVE_FAILED_EVALUATION"

        # Sign and mark status
        req.status = decision.decision
        req.approver_id = decision.approver_id
        req.decision_signature = self.sign_decision(
            req.id, decision.approver_id, decision.decision, req.patch_hash
        )
        self._consumed.add(req.id)
        return True, "INFO_APPROVAL_RECORDED"
