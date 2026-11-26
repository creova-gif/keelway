"""Keelway Governed Run Coordinator and Runtime Supervisor.
Implements the end-to-end golden path workflow from PRD-001,
supporting single approval and two-human quorum (ADR-045/ADR-046).
"""
from __future__ import annotations

import datetime
import uuid
from typing import Optional, Tuple

from keelway.approvals.quorum import QUORUM_SECRET_KEY, TwoHumanQuorumService
from keelway.approvals.service import APPROVAL_SECRET_KEY, ApprovalDecision, ApprovalService
from keelway.security.source_defaults import configured_signing_key
from keelway.audit.recorder import AuditRecorder
from keelway.audit.store import SQLiteAuditStore
from keelway.core.models import (
    DecisionEnum,
    DeploymentResult,
    PullRequestResult,
    RunManifest,
    RunStatus,
    ToolAuthorizationRequest,
)
from keelway.evals.engine import EvalEngine
from keelway.git_ci.service import GitCIService
from keelway.mcp.bridge import MCPGovernanceBridge
from keelway.models.gateway import ModelGateway
from keelway.policy.engine import PolicyEngine
from keelway.sandbox.workspace import WorkspaceManager


class GovernedRunCoordinator:
    """Coordinates a governed run through all policy, MCP, and approval gates."""

    def __init__(
        self,
        run_id: Optional[str] = None,
        org_id: str = "org_sorvex_demo",
        project_id: str = "proj_keelway_core",
        actor_id: str = "platform_engineer_1",
        repo_path: str = ".",
        policy_version: str = "default_governed_v1",
        classification: str = "internal",
        token_ceiling: int = 50000,
        cost_ceiling_cents: int = 500,
        audit_store: Optional[SQLiteAuditStore] = None,
    ):
        self.run_id = run_id or str(uuid.uuid4())
        self.org_id = org_id
        self.project_id = project_id
        self.actor_id = actor_id
        self.repo_path = repo_path
        self.policy_version = policy_version
        self.classification = classification

        # Initialize subsystems
        self.audit_store = audit_store
        self.audit = AuditRecorder(self.run_id, store=self.audit_store)
        self.policy = PolicyEngine(policy_id=policy_version)
        self.mcp = MCPGovernanceBridge(self.policy, self.audit, self.policy_version)
        self.workspace = WorkspaceManager(repo_path=self.repo_path)
        self.models = ModelGateway()
        self.evals = EvalEngine()
        self.approvals = ApprovalService(
            signing_key=configured_signing_key("KEELWAY_APPROVAL_SIGNING_KEY", APPROVAL_SECRET_KEY)
        )
        self.quorum = TwoHumanQuorumService(
            signing_key=configured_signing_key("KEELWAY_QUORUM_SIGNING_KEY", QUORUM_SECRET_KEY)
        )
        self.git_ci = GitCIService(self.approvals)

        # Track active quorum request if applicable
        self.active_quorum_id: Optional[str] = None

        # Initialize manifest
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self.manifest = RunManifest(
            run_id=self.run_id,
            org_id=self.org_id,
            project_id=self.project_id,
            actor_id=self.actor_id,
            agent_kind="coding",
            source_commit_sha=self.workspace.base_commit_sha,
            policy_id=self.policy_version,
            model_route_id=self.models.model_name,
            dataset_digest=self.evals.get_dataset_digest(),
            toolchain_digest="sha256:python3.14-standard-toolchain",
            status=RunStatus.CREATED,
            created_at=now,
            classification=self.classification,
            budget_token_limit=token_ceiling,
            cost_cents_limit=cost_ceiling_cents,
        )

        # Record run creation event
        self.audit.record_event("RUN_CREATED", self.manifest.model_dump())

    def start_run(self, task_prompt: str) -> Tuple[bool, str]:
        """Initiates the governed workflow: policy authorization, workspace setup, code gen."""
        self.manifest.status = RunStatus.POLICY_CHECK

        # 1. Authorize workspace write via policy engine
        auth_req = ToolAuthorizationRequest(
            run_id=self.run_id,
            tool="git.write_patch",
            action_digest="sha256:initiate_patch_generation",
            scope={"repo": self.project_id, "path": "governed_module.py"},
            actor_id=self.actor_id,
            policy_version=self.policy_version,
        )
        decision = self.policy.evaluate(auth_req)
        self.audit.record_event("POLICY_DECISION", decision.model_dump())

        if decision.decision == DecisionEnum.DENY:
            self.manifest.status = RunStatus.FAILED
            self.audit.record_event("RUN_FAILED", {"reason": decision.reason_code})
            return False, f"Policy Denied: {decision.reason_code}"

        # 2. Setup isolated worktree
        self.manifest.status = RunStatus.EXECUTING
        try:
            self.workspace.create_worktree(self.run_id)
        except Exception as e:
            self.manifest.status = RunStatus.FAILED
            self.audit.record_event("RUN_FAILED", {"reason": f"Workspace setup failed: {e}"})
            return False, f"Workspace setup failed: {e}"

        # 3. Model generation within budget
        try:
            proposal = self.models.generate_patch_proposal(
                task_prompt=task_prompt,
                file_tree=["README.md"],
                token_ceiling=self.manifest.budget_token_limit,
                tokens_used_so_far=self.manifest.tokens_used,
            )
            self.manifest.tokens_used += proposal["tokens_consumed"]
            self.manifest.cost_cents_used += proposal["cost_cents"]

            # Write patch into isolated sandbox worktree
            self.workspace.write_file(proposal["file_path"], proposal["content"])
            diff_text = self.workspace.get_diff()
            patch_hash = self.workspace.get_patch_hash()

            self.audit.record_event(
                "PATCH_GENERATED",
                {
                    "patch_hash": patch_hash,
                    "file_path": proposal["file_path"],
                    "tokens_consumed": proposal["tokens_consumed"],
                    "cost_cents": proposal["cost_cents"],
                },
            )
        except Exception as e:
            self.manifest.status = RunStatus.FAILED
            self.audit.record_event("RUN_FAILED", {"reason": f"Patch generation failed: {e}"})
            return False, f"Patch generation failed: {e}"

        # 4. Paired Evaluation
        self.manifest.status = RunStatus.EVALUATING
        eval_result = self.evals.evaluate(self.run_id)
        self.audit.record_event("EVAL_COMPLETED", eval_result.model_dump())

        if not eval_result.passed:
            self.manifest.status = RunStatus.FAILED
            self.audit.record_event("RUN_FAILED", {"reason": "Evaluation threshold not met"})
            return False, "Evaluation failed to meet threshold"

        # 5. Escalate to Approval Gate
        self.manifest.status = RunStatus.AWAITING_APPROVAL

        # If production classification, enforce ADR-045 Two-Human Quorum
        if self.classification == "production":
            q_req = self.quorum.create_quorum_request(
                run_id=self.run_id,
                patch_hash=patch_hash,
                environment="production",
            )
            self.active_quorum_id = q_req.id
            self.audit.record_event(
                "TWO_HUMAN_QUORUM_REQUESTED",
                {
                    "quorum_id": q_req.id,
                    "required_roles": list(q_req.required_roles),
                    "patch_hash": patch_hash,
                    "environment": "production",
                },
            )
            # Also create backing standard approval request for PR compatibility
            self.approvals.create_request(
                run_id=self.run_id,
                patch_hash=patch_hash,
                diff_content=diff_text,
                eval_score=eval_result.candidate_score,
                eval_passed=eval_result.passed,
                estimated_cost_cents=self.manifest.cost_cents_used,
            )
            return True, q_req.id

        # Standard single approval for non-production
        approval_req = self.approvals.create_request(
            run_id=self.run_id,
            patch_hash=patch_hash,
            diff_content=diff_text,
            eval_score=eval_result.candidate_score,
            eval_passed=eval_result.passed,
            estimated_cost_cents=self.manifest.cost_cents_used,
        )
        self.audit.record_event("APPROVAL_REQUESTED", approval_req.model_dump())
        return True, approval_req.id

    def submit_human_approval(
        self, approval_id: str, approver_id: str, decision: str = "APPROVED"
    ) -> Tuple[bool, str]:
        """Records human approval decision with cryptographic binding (standard single approval)."""
        current_patch_hash = self.workspace.get_patch_hash()
        dec = ApprovalDecision(
            approval_id=approval_id,
            decision=decision,
            approver_id=approver_id,
            patch_hash=current_patch_hash,
        )
        ok, msg = self.approvals.submit_decision(dec, current_patch_hash=current_patch_hash)
        if not ok:
            self.audit.record_event("APPROVAL_FAILED", {"reason": msg})
            return False, msg

        if decision == "APPROVED":
            self.manifest.status = RunStatus.APPROVED
            self.audit.record_event(
                "APPROVAL_GRANTED",
                {"approval_id": approval_id, "approver_id": approver_id, "patch_hash": current_patch_hash},
            )
        else:
            self.manifest.status = RunStatus.REJECTED
            self.audit.record_event(
                "APPROVAL_REJECTED",
                {"approval_id": approval_id, "approver_id": approver_id},
            )
        return True, msg

    def submit_quorum_approval(
        self, quorum_id: str, principal_id: str, role: str
    ) -> Tuple[bool, str]:
        """Submits an approval from one human for one role in a two-human quorum (ADR-045)."""
        current_patch_hash = self.workspace.get_patch_hash()
        ok, msg = self.quorum.submit_role_approval(
            request_id=quorum_id,
            principal_id=principal_id,
            role=role,
            current_patch_hash=current_patch_hash,
        )
        if not ok:
            self.audit.record_event("QUORUM_APPROVAL_DENIED", {"reason": msg, "principal": principal_id, "role": role})
            return False, msg

        self.audit.record_event(
            "QUORUM_ROLE_APPROVED",
            {"quorum_id": quorum_id, "principal": principal_id, "role": role, "patch_hash": current_patch_hash},
        )

        q_req = self.quorum.get_request(quorum_id)
        if q_req and q_req.is_fully_approved:
            self.manifest.status = RunStatus.APPROVED
            self.audit.record_event(
                "TWO_HUMAN_QUORUM_ACHIEVED",
                {
                    "quorum_id": quorum_id,
                    "signatures": [s.model_dump() for s in q_req.signatures.values()],
                },
            )
            # Sync base approval request status to allow PR promotion
            for base_app in self.approvals._requests.values():
                if base_app.run_id == self.run_id:
                    base_app.status = "APPROVED"
                    base_app.approver_id = f"quorum:{principal_id}"
            return True, "INFO_QUORUM_ACHIEVED_FULLY_APPROVED"

        return True, msg

    def promote_to_pr(
        self, approval_id: str, title: str, description: str
    ) -> Tuple[bool, Optional[PullRequestResult], str]:
        """Creates governed PR."""
        current_patch_hash = self.workspace.get_patch_hash()
        ok, res, msg = self.git_ci.create_pull_request(
            run_id=self.run_id,
            approval_id=approval_id,
            current_patch_hash=current_patch_hash,
            title=title,
            description=description,
        )
        if not ok:
            self.audit.record_event("PR_CREATION_FAILED", {"reason": msg})
            return False, None, msg

        self.manifest.status = RunStatus.PR_READY
        self.audit.record_event("PR_CREATED", res.model_dump())
        return True, res, msg

    def deploy_to_staging(
        self, approval_id: str, webhook_url: Optional[str] = None
    ) -> Tuple[bool, Optional[DeploymentResult], str]:
        """Triggers deployment to staging via customer CI webhook."""
        current_patch_hash = self.workspace.get_patch_hash()
        ok, res, msg = self.git_ci.trigger_staging_deployment(
            run_id=self.run_id,
            approval_id=approval_id,
            current_patch_hash=current_patch_hash,
            webhook_url=webhook_url,
        )
        if not ok:
            self.audit.record_event("DEPLOYMENT_FAILED", {"reason": msg})
            return False, None, msg

        self.manifest.status = RunStatus.DEPLOYED
        self.audit.record_event("DEPLOYMENT_TRIGGERED", res.model_dump())
        return True, res, msg

    def cancel(self, reason: str = "User requested cancellation") -> None:
        """Idempotently cancels the run."""
        self.manifest.status = RunStatus.CANCELLED
        self.audit.record_event("RUN_CANCELLED", {"reason": reason})

    def teardown(self) -> None:
        """Cleans up workspace resources."""
        self.workspace.cleanup()
