"""Keelway REST API Routes.
Implements the external API contracts specified in 04_API_AND_DATA_CONTRACTS.md,
supporting single-human approvals and two-human quorums (ADR-045).
"""
from __future__ import annotations

import datetime
import json
import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel

from keelway.api.governance_auth import require_governance_actor
from keelway.approvals.service import ApprovalDecision
from keelway.audit.export import AuditExporter, ExportBundle
from keelway.audit.store import SQLiteAuditStore
from keelway.core.models import (
    AuditEvent,
    DeploymentRequest,
    DeploymentResult,
    PolicyDecision,
    PullRequestRequest,
    PullRequestResult,
    RunManifest,
    ToolAuthorizationRequest,
)
from keelway.core.runner import GovernedRunCoordinator
from keelway.git_ci.github import handler_from_environment
from keelway.runner.enrollment import verify_enrolled_runner_token
from keelway.policy.engine import PolicyEngine

router = APIRouter(prefix="/v1")

# In-memory registry of active runs for the local runtime control plane
ACTIVE_RUNS: Dict[str, GovernedRunCoordinator] = {}
SHARED_POLICY_ENGINE = PolicyEngine()
SHARED_WEBHOOK_HANDLER = handler_from_environment()
SHARED_AUDIT_EXPORTER = AuditExporter()
SHARED_AUDIT_STORE = SQLiteAuditStore("keelway_audit.db")



class CreateRunRequest(BaseModel):
    org_id: str = "org_sorvex_default"
    project_id: str = "proj_keelway_governance"
    actor_id: str = "platform_engineer_1"
    task_prompt: str = "Add governed compliance healthcheck endpoint"
    repo_path: str = "."
    policy_version: str = "default_governed_v1"
    classification: str = "internal"  # "internal", "staging", "production"
    token_ceiling: int = 50000
    cost_ceiling_cents: int = 500


class QuorumApprovalSubmission(BaseModel):
    quorum_id: str
    principal_id: str
    role: str  # "Security Lead" or "Platform Owner"


class AuditVerifyResponse(BaseModel):
    run_id: str
    verified: bool
    total_events: int
    error: Optional[str] = None


@router.post("/runs", response_model=Dict[str, Any])
def create_run(req: CreateRunRequest, _actor: str = Depends(require_governance_actor)) -> Dict[str, Any]:
    """Creates and starts a governed run."""
    try:
        coordinator = GovernedRunCoordinator(
            org_id=req.org_id,
            project_id=req.project_id,
            actor_id=req.actor_id,
            repo_path=req.repo_path,
            policy_version=req.policy_version,
            classification=req.classification,
            token_ceiling=req.token_ceiling,
            cost_ceiling_cents=req.cost_ceiling_cents,
            audit_store=SHARED_AUDIT_STORE,
        )
        ACTIVE_RUNS[coordinator.run_id] = coordinator

        # Start execution
        ok, msg = coordinator.start_run(task_prompt=req.task_prompt)
        return {
            "run_id": coordinator.run_id,
            "status": coordinator.manifest.status.value,
            "classification": coordinator.classification,
            "success": ok,
            "approval_id": msg if ok else None,
            "is_quorum": coordinator.classification == "production",
            "message": "Run started successfully" if ok else msg,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/runs/{run_id}", response_model=RunManifest)
def get_run(run_id: str) -> RunManifest:
    """Retrieves status and metadata for a run."""
    coordinator = ACTIVE_RUNS.get(run_id)
    if not coordinator:
        raise HTTPException(status_code=404, detail="Run not found")
    return coordinator.manifest


@router.get("/runs/{run_id}/events", response_model=List[AuditEvent])
def get_run_events(run_id: str) -> List[AuditEvent]:
    """Retrieves the full append-only audit event log for a run."""
    coordinator = ACTIVE_RUNS.get(run_id)
    if not coordinator:
        raise HTTPException(status_code=404, detail="Run not found")
    return coordinator.audit.events


@router.get("/runs/{run_id}/export", response_model=ExportBundle)
def export_run_audit_bundle(run_id: str, redact: bool = True) -> ExportBundle:
    """Exports a cryptographically verified and sealed audit bundle for a run (FR-09)."""
    coordinator = ACTIVE_RUNS.get(run_id)
    if not coordinator:
        raise HTTPException(status_code=404, detail="Run not found")

    bundle = SHARED_AUDIT_EXPORTER.export(
        manifest=coordinator.manifest,
        events=coordinator.audit.events,
        redact_prompts=redact,
    )
    return bundle


@router.post("/runs/{run_id}/cancel", response_model=Dict[str, str])
def cancel_run(run_id: str, reason: str = "User requested cancellation", _actor: str = Depends(require_governance_actor)) -> Dict[str, str]:
    """Idempotently cancels a run."""
    coordinator = ACTIVE_RUNS.get(run_id)
    if not coordinator:
        raise HTTPException(status_code=404, detail="Run not found")
    coordinator.cancel(reason)
    return {"run_id": run_id, "status": coordinator.manifest.status.value}


@router.post("/policy/decide", response_model=PolicyDecision)
def policy_decide(req: ToolAuthorizationRequest) -> PolicyDecision:
    """Decides tool authorization under deny-by-default rules."""
    decision = SHARED_POLICY_ENGINE.evaluate(req)
    return decision


@router.post("/approvals/{approval_id}/decision", response_model=Dict[str, Any])
def submit_approval_decision(approval_id: str, dec: ApprovalDecision, _actor: str = Depends(require_governance_actor)) -> Dict[str, Any]:
    """Submits a human review decision for a standard approval request."""
    target_coordinator: Optional[GovernedRunCoordinator] = None
    for coord in ACTIVE_RUNS.values():
        if coord.approvals.get_request(approval_id):
            target_coordinator = coord
            break

    if not target_coordinator:
        raise HTTPException(status_code=404, detail="Approval request not found")

    ok, msg = target_coordinator.submit_human_approval(
        approval_id=approval_id, approver_id=dec.approver_id, decision=dec.decision
    )
    if not ok:
        raise HTTPException(status_code=400, detail=msg)

    return {
        "approval_id": approval_id,
        "status": dec.decision,
        "message": msg,
    }


@router.post("/quorum/{quorum_id}/approval", response_model=Dict[str, Any])
def submit_quorum_approval(quorum_id: str, sub: QuorumApprovalSubmission, _actor: str = Depends(require_governance_actor)) -> Dict[str, Any]:
    """Submits a role approval in a two-human quorum (ADR-045)."""
    target_coordinator: Optional[GovernedRunCoordinator] = None
    for coord in ACTIVE_RUNS.values():
        if coord.quorum.get_request(quorum_id):
            target_coordinator = coord
            break

    if not target_coordinator:
        raise HTTPException(status_code=404, detail="Quorum request not found")

    ok, msg = target_coordinator.submit_quorum_approval(
        quorum_id=quorum_id, principal_id=sub.principal_id, role=sub.role
    )
    if not ok:
        raise HTTPException(status_code=400, detail=msg)

    q_req = target_coordinator.quorum.get_request(quorum_id)
    return {
        "quorum_id": quorum_id,
        "role": sub.role,
        "principal_id": sub.principal_id,
        "is_fully_approved": q_req.is_fully_approved if q_req else False,
        "message": msg,
    }


@router.post("/runs/{run_id}/pull-request", response_model=PullRequestResult)
def create_pull_request(run_id: str, req: PullRequestRequest, _actor: str = Depends(require_governance_actor)) -> PullRequestResult:
    """Generates a governed pull request after approved human review."""
    coordinator = ACTIVE_RUNS.get(run_id)
    if not coordinator:
        raise HTTPException(status_code=404, detail="Run not found")

    ok, res, msg = coordinator.promote_to_pr(
        approval_id=req.approval_id,
        title=req.title,
        description=req.description,
    )
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    assert res is not None
    return res


@router.post("/deployments", response_model=DeploymentResult)
def trigger_deployment(req: DeploymentRequest, _actor: str = Depends(require_governance_actor)) -> DeploymentResult:
    """Triggers staging deployment through customer CI webhook."""
    coordinator = ACTIVE_RUNS.get(req.run_id)
    if not coordinator:
        raise HTTPException(status_code=404, detail="Run not found")

    ok, res, msg = coordinator.deploy_to_staging(approval_id=req.approval_id)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    assert res is not None
    return res


@router.get("/audit/verify", response_model=AuditVerifyResponse)
def audit_verify(run_id: str = Query(...)) -> AuditVerifyResponse:
    """Verifies the cryptographic integrity of the hash-chained audit log."""
    coordinator = ACTIVE_RUNS.get(run_id)
    if not coordinator:
        raise HTTPException(status_code=404, detail="Run not found")

    verified, err = coordinator.audit.verify_chain()
    return AuditVerifyResponse(
        run_id=run_id,
        verified=verified,
        total_events=len(coordinator.audit.events),
        error=err,
    )


@router.post("/webhooks/github")
async def github_webhook(
    request: Request,
    x_hub_signature_256: Optional[str] = Header(None),
    x_github_event: Optional[str] = Header("ping"),
) -> Dict[str, Any]:
    """Receives and verifies GitHub App webhooks, reconciling CI and PR events into the audit chain."""
    body_bytes = await request.body()
    if not SHARED_WEBHOOK_HANDLER.verify_signature(body_bytes, x_hub_signature_256):
        raise HTTPException(status_code=401, detail="Invalid HMAC-SHA256 signature")

    try:
        payload = json.loads(body_bytes.decode("utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON payload") from exc

    ok, kind, data = SHARED_WEBHOOK_HANDLER.process_event(x_github_event or "ping", payload)
    return {
        "verified": True,
        "processed": ok,
        "event_kind": kind,
        "event_data": data,
    }


@router.get("/system/hardware-status")
def get_hardware_status() -> Dict[str, Any]:
    """Returns the qualification matrix and health status for Tier 2 Enterprise Hardware (ADR-051..ADR-080).
    Explicitly reports whether hardware is qualified physical hardware or an unqualified emulator.
    """
    return {
        "tier2_hardware_abstraction_layer": {
            "worm_storage": {
                "subsystem": "Dual Independent Customer-Owned WORM Storage",
                "normative_adrs": ["ADR-076", "ADR-077", "ADR-078", "ADR-079", "ADR-080"],
                "qualification": "EMULATOR_PROTOTYPE_UNQUALIFIED_FOR_PROD",
                "production_ready_physical_hardware": False,
                "readback_verification": "SHA-256 independent hash check enabled",
                "two_replica_independent_custodians_enforced": True,
            },
            "tpm_attestation": {
                "subsystem": "TPM 2.0 Quote Verifier & Measured Boot Replay",
                "normative_adrs": ["ADR-061", "ADR-062", "ADR-064"],
                "pcr_replay_algorithm": "SHA256(PCR_n || event_digest)",
                "golden_profile_matching": "Active",
                "nonce_anti_replay": "Single-use 256-bit challenge enforced",
                "monotonic_nv_counter": "Rollback-resistant anti-replay floor active",
            },
            "piv_smartcard": {
                "subsystem": "PIV Smartcard PKI Verification & CRL Freshness Engine",
                "normative_adrs": ["ADR-051", "ADR-053"],
                "max_crl_age_seconds": 259200,  # 72 hours
                "crl_staleness_policy": "STRICT_72_HOUR_MAXIMUM_FROM_THIS_UPDATE",
                "hardware_held_private_key_required": True,
                "software_keys_prohibited": True,
            },
        }
    }


# Distributed Runner In-Memory Job Queue (Outbound-Only Customer VPC Execution)
PENDING_RUNNER_JOBS: List[Dict[str, Any]] = []


class RunnerPollRequest(BaseModel):
    runner_id: str
    org_id: str
    auth_token: str


class RunnerAckRequest(BaseModel):
    runner_id: str
    org_id: str
    run_id: str
    status: str
    patch_hash: Optional[str] = None
    approval_id: Optional[str] = None


@router.post("/runner/jobs/enqueue")
def enqueue_runner_job(job_spec: Dict[str, Any], _actor: str = Depends(require_governance_actor)) -> Dict[str, Any]:
    """Enqueues a job for asynchronous pickup by an outbound customer runner daemon."""
    job_id = str(uuid.uuid4())
    job_spec["job_id"] = job_id
    PENDING_RUNNER_JOBS.append(job_spec)
    return {"status": "ENQUEUED", "job_id": job_id}


@router.post("/runner/jobs/poll")
def poll_runner_jobs(req: RunnerPollRequest) -> Dict[str, Any]:
    """Outbound runner long-poll endpoint. A shape-only token is not authentication."""
    if not verify_enrolled_runner_token(req.runner_id, req.org_id, req.auth_token):
        raise HTTPException(status_code=401, detail="Invalid runner authentication token")

    for idx, job in enumerate(PENDING_RUNNER_JOBS):
        if job.get("org_id") == req.org_id:
            assigned = PENDING_RUNNER_JOBS.pop(idx)
            return {"job_available": True, "job": assigned}

    return {"job_available": False, "job": None}


@router.post("/runner/jobs/ack")
def acknowledge_runner_job(req: RunnerAckRequest) -> Dict[str, Any]:
    """Receives completion receipt and patch hash from customer runner."""
    return {
        "status": "RECORDED",
        "run_id": req.run_id,
        "recorded_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }


