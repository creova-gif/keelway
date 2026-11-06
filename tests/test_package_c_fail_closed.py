"""Package C fail-closed checks.

These are Sam's provisional tests for the paths package C owns. They are not
package A's harness and they do not replace ``tests/test_package_a_safety_negatives.py``.
A fake command runner below is an explicit test double. It is not an OS sandbox
and it is not verification of macOS seatbelt or Linux bubblewrap.
"""

from __future__ import annotations

import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient

from core.billing.entitlements import (
    DEFAULT_ENTITLEMENT_KEY,
    BillingWebhookHandler,
    EntitlementCertificate,
    EntitlementManager,
    EnterpriseFeature,
    LicenseTier,
)
from core.orchestration.agent_loop import AutonomousAgentLoop, AutonomyPolicy
from core.storage.payment_broker import GlobalPaymentBroker, GlobalRail
from core.storage.workspace_fs import WorkspaceFilesystem
from keelway.api.app import app as governance_app
from keelway.api.app import governance_origin_allowed
from keelway.approvals.quorum import QUORUM_SECRET_KEY, TwoHumanQuorumService
from keelway.approvals.service import APPROVAL_SECRET_KEY, ApprovalDecision, ApprovalService
from keelway.git_ci.github import GitHubAppWebhookHandler
from keelway.runner.daemon import CustomerRunnerDaemon
from keelway.runner.enrollment import clear_enrollments, enroll_runner
from keelway.security.source_defaults import InsecureDefaultConfiguration

_APPROVAL_FIXTURE = b"package-c-explicit-approval-fixture-key"
_QUORUM_FIXTURE = b"package-c-explicit-quorum-fixture-key"
_PAYMENT_FIXTURE = "package-c-explicit-payment-fixture-secret"
_WEBHOOK_FIXTURE = "package-c-explicit-webhook-fixture"
_BILLING_FIXTURE = "package-c-explicit-billing-fixture-secret"
_ENTITLEMENT_FIXTURE = b"package-c-explicit-entitlement-fixture-key"
_RUNNER_SECRET = b"package-c-explicit-runner-fixture-secret"


def test_explicit_source_default_approval_key_cannot_record_an_approval():
    service = ApprovalService(signing_key=APPROVAL_SECRET_KEY)
    request = service.create_request(
        run_id="pkg_c",
        patch_hash="sha256:abc",
        diff_content="diff",
        eval_score=1.0,
        eval_passed=True,
        estimated_cost_cents=1,
    )
    decision = ApprovalDecision(
        approval_id=request.id,
        decision="APPROVED",
        approver_id="human_reviewer",
        patch_hash=request.patch_hash,
    )
    ok, _message = service.submit_decision(decision, request.patch_hash)
    assert ok is False
    assert request.status != "APPROVED"
    assert request.id not in service._consumed
    with pytest.raises(InsecureDefaultConfiguration):
        service.sign_decision(request.id, "human_reviewer", "APPROVED", request.patch_hash)


def test_explicit_fixture_approval_key_can_record_an_approval():
    service = ApprovalService(signing_key=_APPROVAL_FIXTURE)
    request = service.create_request(
        run_id="pkg_c",
        patch_hash="sha256:abc",
        diff_content="diff",
        eval_score=1.0,
        eval_passed=True,
        estimated_cost_cents=1,
    )
    decision = ApprovalDecision(
        approval_id=request.id,
        decision="APPROVED",
        approver_id="human_reviewer",
        patch_hash=request.patch_hash,
    )
    ok, message = service.submit_decision(decision, request.patch_hash)
    assert ok is True and message == "INFO_APPROVAL_RECORDED"
    assert request.status == "APPROVED"


def test_explicit_source_default_quorum_key_cannot_approve():
    service = TwoHumanQuorumService(signing_key=QUORUM_SECRET_KEY)
    request = service.create_quorum_request("pkg_c", "sha256:abc", "production")
    ok, _message = service.submit_role_approval(
        request.id, "ada_reviewer", "Security Lead", request.patch_hash
    )
    assert ok is False
    assert request.signatures == {}
    assert request.status != "APPROVED"


def test_explicit_fixture_quorum_key_can_collect_a_role():
    service = TwoHumanQuorumService(signing_key=_QUORUM_FIXTURE)
    request = service.create_quorum_request("pkg_c", "sha256:abc", "production")
    ok, message = service.submit_role_approval(
        request.id, "ada_reviewer", "Security Lead", request.patch_hash
    )
    assert ok is True
    assert "PENDING_REMAINING" in message
    assert "Security Lead" in request.signatures


def test_explicit_source_default_payment_secret_creates_no_intent():
    broker = GlobalPaymentBroker(broker_secret="KORA_SOVEREIGN_PAYMENT_SECRET_2026")
    with pytest.raises(InsecureDefaultConfiguration):
        broker.create_intent(GlobalRail.OFFLINE_VOUCHER, 10, "USD", "safety-recipient")
    assert broker.intents == {}


def test_explicit_fixture_payment_secret_can_create_an_intent():
    broker = GlobalPaymentBroker(broker_secret=_PAYMENT_FIXTURE)
    intent = broker.create_intent(GlobalRail.OFFLINE_VOUCHER, 10, "USD", "safety-recipient")
    assert intent.status == "pending"
    assert intent.intent_id in broker.intents


def test_explicit_source_default_billing_secret_rejects_its_own_signature():
    handler = BillingWebhookHandler(secret="KEELWAY_BILLING_WEBHOOK_SECRET_2026")
    payload = {"org_id": "org_safety", "seat_delta": 1}
    raw = json.dumps(payload, sort_keys=True).encode("utf-8")
    signature = hmac.new(handler.secret.encode("utf-8"), raw, hashlib.sha256).hexdigest()
    result = handler.handle_event("evt_c", "seat.added", payload, signature_header=signature)
    assert result["status"] != "processed"
    assert handler.processed_events == set()
    assert handler.event_history == []


def test_explicit_fixture_billing_secret_accepts_a_matching_signature():
    handler = BillingWebhookHandler(secret=_BILLING_FIXTURE)
    payload = {"org_id": "org_safety", "seat_delta": 1}
    raw = json.dumps(payload, sort_keys=True).encode("utf-8")
    signature = hmac.new(_BILLING_FIXTURE.encode("utf-8"), raw, hashlib.sha256).hexdigest()
    result = handler.handle_event("evt_c_ok", "seat.added", payload, signature_header=signature)
    assert result["status"] == "processed"


def test_explicit_source_default_entitlement_key_cannot_register_or_grant(tmp_path):
    manager = EntitlementManager(storage_path=tmp_path / "entitlements.json", secret_key=DEFAULT_ENTITLEMENT_KEY)
    now = __import__("time").time()
    certificate = EntitlementCertificate(
        org_id="org_safety",
        org_name="Safety",
        tier=LicenseTier.ENTERPRISE,
        seats=1,
        allowed_features=["local_agent_loop"],
        issued_at=now,
        expires_at=now + 3600,
    )
    certificate.sign(DEFAULT_ENTITLEMENT_KEY)
    ok, _status = manager.register_certificate(certificate)
    granted, _reason = manager.check_feature_access("org_safety", EnterpriseFeature.LOCAL_AGENT_LOOP)
    assert ok is False and granted is False
    assert manager.active_certificates == {}
    assert not (tmp_path / "entitlements.json").exists()


def test_explicit_fixture_entitlement_key_can_register(tmp_path):
    manager = EntitlementManager(storage_path=tmp_path / "entitlements.json", secret_key=_ENTITLEMENT_FIXTURE)
    now = __import__("time").time()
    certificate = EntitlementCertificate(
        org_id="org_safety",
        org_name="Safety",
        tier=LicenseTier.ENTERPRISE,
        seats=1,
        allowed_features=["local_agent_loop"],
        issued_at=now,
        expires_at=now + 3600,
    )
    certificate.sign(_ENTITLEMENT_FIXTURE)
    ok, _status = manager.register_certificate(certificate)
    assert ok is True
    assert "org_safety" in manager.active_certificates


def test_explicit_source_default_github_webhook_cannot_process_or_verify():
    handler = GitHubAppWebhookHandler(webhook_secret="keelway_github_webhook_secret_v1")
    payload = {"action": "closed", "pull_request": {"number": 1, "merged": True, "head": {"sha": "abc"}}}
    raw = json.dumps(payload).encode("utf-8")
    signature = "sha256=" + hmac.new(handler.webhook_secret, raw, hashlib.sha256).hexdigest()
    assert handler.verify_signature(raw, signature) is False
    ok, kind, _data = handler.process_event("pull_request", payload)
    assert ok is False and kind is None


def test_explicit_fixture_github_webhook_verifies():
    handler = GitHubAppWebhookHandler(webhook_secret=_WEBHOOK_FIXTURE)
    raw = b'{"ok":true}'
    signature = "sha256=" + hmac.new(_WEBHOOK_FIXTURE.encode("utf-8"), raw, hashlib.sha256).hexdigest()
    assert handler.verify_signature(raw, signature) is True
    ok, kind, _data = handler.process_event(
        "pull_request",
        {"action": "closed", "pull_request": {"number": 4, "merged": True, "head": {"sha": "abc"}}},
    )
    assert ok is True and kind == "PR_MERGED"


def test_governance_origin_policy_rejects_wildcard_and_hostile_origins():
    assert governance_origin_allowed(None, "127.0.0.1:8000") is True
    assert governance_origin_allowed("*", "127.0.0.1:8000") is False
    assert governance_origin_allowed("null", "127.0.0.1:8000") is False
    assert governance_origin_allowed("https://evil.example", "127.0.0.1:8000") is False
    assert governance_origin_allowed("http://127.0.0.1:8000", "127.0.0.1:8000") is True
    assert governance_origin_allowed("http://127.0.0.1:8000", "evil.example") is False


def test_hostile_origin_cannot_create_a_governance_run(monkeypatch):
    monkeypatch.setenv("KEELWAY_GOVERNANCE_ALLOWED_ORIGINS", "*")
    from keelway.api import routes as governance_routes

    before = set(governance_routes.ACTIVE_RUNS)
    with TestClient(governance_app) as client:
        response = client.post(
            "/v1/runs",
            headers={"Origin": "https://evil.example"},
            json={"task_prompt": "should not start", "repo_path": "."},
        )
    assert response.status_code == 403
    assert response.json()["detail"] == "Origin not allowed."
    assert "Access-Control-Allow-Origin" not in response.headers
    assert set(governance_routes.ACTIVE_RUNS) == before


def test_explicit_allowed_origin_is_echoed_and_not_a_wildcard(monkeypatch):
    monkeypatch.setenv("KEELWAY_GOVERNANCE_ALLOWED_ORIGINS", "https://tools.example")
    with TestClient(governance_app) as client:
        response = client.get("/", headers={"Origin": "https://tools.example"})
    assert response.status_code == 200
    assert response.headers["Access-Control-Allow-Origin"] == "https://tools.example"
    assert response.headers["Access-Control-Allow-Credentials"] == "true"
    assert response.headers["Access-Control-Allow-Origin"] != "*"


def test_enrolled_runner_can_poll_only_its_org():
    from keelway.api import routes as governance_routes

    clear_enrollments()
    governance_routes.PENDING_RUNNER_JOBS.clear()
    secret = _RUNNER_SECRET
    enroll_runner("runner-a", "org_safety", secret)
    own = {"job_id": "own", "org_id": "org_safety", "repo_path": "."}
    other = {"job_id": "other", "org_id": "org_other", "repo_path": "."}
    governance_routes.PENDING_RUNNER_JOBS.extend([other, own])
    daemon = CustomerRunnerDaemon(runner_id="runner-a", org_id="org_safety", secret_key=secret)
    forged = "runner-a:org_safety:1:forged"
    try:
        with TestClient(governance_app) as client:
            stolen = client.post(
                "/v1/runner/jobs/poll",
                json={"runner_id": "runner-a", "org_id": "org_other", "auth_token": daemon.generate_auth_token()},
            )
            assert stolen.status_code == 401
            assert other in governance_routes.PENDING_RUNNER_JOBS
            shape = client.post(
                "/v1/runner/jobs/poll",
                json={"runner_id": "runner-a", "org_id": "org_safety", "auth_token": forged},
            )
            assert shape.status_code == 401
            assert own in governance_routes.PENDING_RUNNER_JOBS
            accepted = client.post(
                "/v1/runner/jobs/poll",
                json={
                    "runner_id": "runner-a",
                    "org_id": "org_safety",
                    "auth_token": daemon.generate_auth_token(),
                },
            )
        assert accepted.status_code == 200
        assert accepted.json()["job"]["job_id"] == "own"
        assert other in governance_routes.PENDING_RUNNER_JOBS
        assert own not in governance_routes.PENDING_RUNNER_JOBS
    finally:
        governance_routes.PENDING_RUNNER_JOBS.clear()
        clear_enrollments()


@pytest.mark.asyncio
async def test_default_loop_and_approved_resume_do_not_start_a_host_shell(tmp_path, monkeypatch):
    calls = []

    def explode(*_args, **_kwargs):
        calls.append("popen")
        raise AssertionError("host shell was started")

    monkeypatch.setattr("core.orchestration.agent_loop.subprocess.Popen", explode)
    workspace = WorkspaceFilesystem(root_dir=str(tmp_path))
    loop = AutonomousAgentLoop(
        task_id="pkg_c_isolation",
        workspace_fs=workspace,
        policy=AutonomyPolicy.CONFIRM_MUTATION,
        record_flight=False,
    )
    paused = await loop.execute_tool("run_command", {"command": "echo hi"})
    assert paused["status"] == "paused_for_approval"
    resumed = await loop.approve_pending(True)
    assert resumed["status"] == "error"
    assert "unavailable" in resumed["error"].lower()
    malformed_loop = AutonomousAgentLoop(
        task_id="pkg_c_malformed",
        workspace_fs=workspace,
        policy=AutonomyPolicy.AUTONOMOUS,
        record_flight=False,
    )
    malformed = await malformed_loop.execute_tool("run_command", None)
    assert malformed["status"] == "error"
    assert "unavailable" in malformed["error"].lower()
    assert calls == []


@pytest.mark.asyncio
async def test_explicit_fake_command_boundary_is_used_and_is_not_os_verification(tmp_path):
    """Labeled test double. This does not claim seatbelt or bubblewrap verification."""
    seen = {}

    def fake_runner(command, timeout):
        seen["command"] = command
        seen["timeout"] = timeout
        return {"command": command, "exit_code": 0, "stdout": "fake-boundary", "sandbox": "explicit-test-double"}

    loop = AutonomousAgentLoop(
        task_id="pkg_c_fake_boundary",
        workspace_fs=WorkspaceFilesystem(root_dir=str(tmp_path)),
        policy=AutonomyPolicy.AUTONOMOUS,
        record_flight=False,
    )
    loop.command_runner = fake_runner
    result = await loop.execute_tool("run_command", {"command": "echo hi", "timeout": 5})
    assert result["status"] == "success"
    assert result["result"]["sandbox"] == "explicit-test-double"
    assert seen["command"] == "echo hi"
    bare = AutonomousAgentLoop(
        task_id="pkg_c_no_boundary",
        workspace_fs=WorkspaceFilesystem(root_dir=str(tmp_path)),
        policy=AutonomyPolicy.AUTONOMOUS,
        record_flight=False,
    )
    refused = await bare.execute_tool("run_command", {"command": "echo hi"})
    assert refused["status"] == "error"
    assert "unavailable" in refused["error"].lower()
