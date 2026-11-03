"""End-to-End Golden Path Workflow and API Integration Tests (PRD-001).
Tests the complete governed lifecycle from creation through PR and staging deployment.
"""
import os
from starlette.testclient import TestClient

from keelway.api.app import app
from keelway.core.models import RunStatus
from keelway.core.runner import GovernedRunCoordinator


def test_end_to_end_governed_run_coordinator():
    # Run the coordinator against current directory
    coord = GovernedRunCoordinator(
        org_id="org_sorvex_e2e",
        project_id="proj_governance",
        actor_id="eng_lead_01",
        repo_path=".",
    )

    try:
        # Step 1: Start run (policy, worktree, code gen, eval, approval request)
        ok, approval_id = coord.start_run("Add telemetry endpoint")
        assert ok is True, f"Failed to start run: {approval_id}"
        assert coord.manifest.status == RunStatus.AWAITING_APPROVAL

        # Verify patch hash and diff exist in worktree
        patch_hash = coord.workspace.get_patch_hash()
        assert len(patch_hash) == 64
        diff = coord.workspace.get_diff()
        assert "governed_module.py" in diff

        # Step 2: Submit Human Approval
        ok_appr, msg_appr = coord.submit_human_approval(
            approval_id=approval_id,
            approver_id="human_principal_reviewer",
            decision="APPROVED",
        )
        assert ok_appr is True
        assert coord.manifest.status == RunStatus.APPROVED

        # Step 3: Promote to Pull Request
        ok_pr, pr_res, msg_pr = coord.promote_to_pr(
            approval_id=approval_id,
            title="feat: Governed telemetry update",
            description="Verified by Keelway audit chain",
        )
        assert ok_pr is True
        assert pr_res.status == "OPEN"
        assert coord.manifest.status == RunStatus.PR_READY

        # Step 4: Trigger Staging CI Deployment
        ok_dep, dep_res, msg_dep = coord.deploy_to_staging(approval_id=approval_id)
        assert ok_dep is True
        assert dep_res.status == "TRIGGERED"
        assert coord.manifest.status == RunStatus.DEPLOYED

        # Step 5: Verify Entire Hash-Chained Audit Log
        valid_chain, err = coord.audit.verify_chain()
        assert valid_chain is True
        assert err is None
        assert len(coord.audit.events) >= 6

    finally:
        coord.teardown()


def test_fastapi_rest_endpoints():
    client = TestClient(app)

    # 1. Health/Index dashboard check
    res = client.get("/")
    assert res.status_code == 200
    assert "Keelway | Sorvex Labs" in res.text

    # 2. Policy decide check
    policy_res = client.post(
        "/v1/policy/decide",
        json={
            "run_id": "api_test_run",
            "tool": "git.diff",
            "action_digest": "sha256:1111",
            "scope": {"repo": "test/repo"},
            "actor_id": "tester",
            "policy_version": "default_governed_v1",
        },
    )
    assert policy_res.status_code == 200
    pdata = policy_res.json()
    assert pdata["decision"] == "ALLOW"
    assert "signature" in pdata

    # 3. Deny sensitive file via API
    policy_deny = client.post(
        "/v1/policy/decide",
        json={
            "run_id": "api_test_run",
            "tool": "git.write_patch",
            "action_digest": "sha256:2222",
            "scope": {"path": ".env"},
            "actor_id": "tester",
            "policy_version": "default_governed_v1",
        },
    )
    assert policy_deny.status_code == 200
    assert policy_deny.json()["decision"] == "DENY"

    # 4. Create and start a governed run via API
    run_res = client.post(
        "/v1/runs",
        json={
            "task_prompt": "API integration verification run",
            "repo_path": ".",
        },
    )
    assert run_res.status_code == 200
    run_data = run_res.json()
    run_id = run_data["run_id"]
    approval_id = run_data["approval_id"]
    assert run_data["status"] == "awaiting_approval"

    # 5. Get run status
    status_res = client.get(f"/v1/runs/{run_id}")
    assert status_res.status_code == 200
    assert status_res.json()["status"] == "awaiting_approval"

    # 6. Verify audit trail via API
    verify_res = client.get(f"/v1/audit/verify?run_id={run_id}")
    assert verify_res.status_code == 200
    assert verify_res.json()["verified"] is True
    assert verify_res.json()["total_events"] >= 4

    # 7. Approve via API
    appr_res = client.post(
        f"/v1/approvals/{approval_id}/decision",
        json={
            "approval_id": approval_id,
            "decision": "APPROVED",
            "approver_id": "human_api_lead",
            "patch_hash": "auto",
        },
    )
    assert appr_res.status_code == 200
    assert appr_res.json()["status"] == "APPROVED"

    # 8. Create PR via API
    pr_res = client.post(
        f"/v1/runs/{run_id}/pull-request",
        json={
            "run_id": run_id,
            "approval_id": approval_id,
            "title": "feat: API test pr",
            "description": "API test desc",
        },
    )
    assert pr_res.status_code == 200
    assert pr_res.json()["status"] == "OPEN"

    # 9. Clean up worktree from active coordinator
    from keelway.api.routes import ACTIVE_RUNS
    if run_id in ACTIVE_RUNS:
        ACTIVE_RUNS[run_id].teardown()


def test_hardware_status_api_endpoint():
    client = TestClient(app)
    res = client.get("/v1/system/hardware-status")
    assert res.status_code == 200
    data = res.json()["tier2_hardware_abstraction_layer"]

    assert "worm_storage" in data
    assert data["worm_storage"]["production_ready_physical_hardware"] is False
    assert data["worm_storage"]["qualification"] == "EMULATOR_PROTOTYPE_UNQUALIFIED_FOR_PROD"

    assert "tpm_attestation" in data
    assert data["tpm_attestation"]["golden_profile_matching"] == "Active"

    assert "piv_smartcard" in data
    assert data["piv_smartcard"]["max_crl_age_seconds"] == 259200
    assert data["piv_smartcard"]["software_keys_prohibited"] is True

