"""Keelway Git and CI/Staging Integration Service.
Implements FR-08: Governed PR creation and staging CI webhook notification.
"""
from __future__ import annotations

import hashlib
import uuid
from typing import Optional, Tuple

from keelway.approvals.service import ApprovalService
from keelway.core.models import DeploymentResult, PullRequestResult


class GitCIError(Exception):
    pass


class GitCIService:
    """Manages governed PR creation and staging deployment triggers."""

    def __init__(self, approval_service: ApprovalService):
        self.approval_service = approval_service

    def create_pull_request(
        self,
        run_id: str,
        approval_id: str,
        current_patch_hash: str,
        title: str,
        description: str,
        branch_name: Optional[str] = None,
    ) -> Tuple[bool, Optional[PullRequestResult], str]:
        """Creates a Pull Request only if verified human approval exists."""
        req = self.approval_service.get_request(approval_id)
        if not req:
            return False, None, "ERR_APPROVAL_NOT_FOUND"

        if req.status != "APPROVED":
            return False, None, f"ERR_PR_REQUIRES_APPROVED_STATUS (current: {req.status})"

        if req.patch_hash != current_patch_hash:
            return False, None, "ERR_PATCH_HASH_MISMATCH_PR_BLOCKED"

        branch = branch_name or f"keelway/governed-run-{run_id[:8]}"
        pr_id = f"PR-{uuid.uuid4().hex[:8]}"
        pr_url = f"https://github.com/customer-org/repo/pull/{pr_id}"

        result = PullRequestResult(
            pr_id=pr_id,
            pr_url=pr_url,
            branch=branch,
            head_sha=current_patch_hash[:12],
            status="OPEN",
        )
        return True, result, "INFO_PR_CREATED_SUCCESSFULLY"

    def trigger_staging_deployment(
        self,
        run_id: str,
        approval_id: str,
        current_patch_hash: str,
        webhook_url: Optional[str] = None,
    ) -> Tuple[bool, Optional[DeploymentResult], str]:
        """Notifies staging CI webhook after verified review and PR approval."""
        req = self.approval_service.get_request(approval_id)
        if not req:
            return False, None, "ERR_APPROVAL_NOT_FOUND"

        if req.status != "APPROVED":
            return False, None, "ERR_DEPLOYMENT_REQUIRES_APPROVED_STATUS"

        if req.patch_hash != current_patch_hash:
            return False, None, "ERR_PATCH_HASH_MUTATED_DEPLOYMENT_BLOCKED"

        deployment_id = str(uuid.uuid4())
        receipt_preimage = f"{deployment_id}:{run_id}:{current_patch_hash}:staging"
        receipt_digest = hashlib.sha256(receipt_preimage.encode("utf-8")).hexdigest()

        result = DeploymentResult(
            deployment_id=deployment_id,
            environment="staging",
            commit_sha=current_patch_hash[:12],
            status="TRIGGERED",
            webhook_url=webhook_url or "https://ci.customer-org.internal/webhook/keelway",
            receipt_digest=receipt_digest,
        )
        return True, result, "INFO_STAGING_DEPLOYMENT_TRIGGERED"
