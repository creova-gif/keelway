"""Mandatory Profile A safety negatives. Owned by foundation-repair package A.

Accountable author of record: Dr Mafie. Independent reviewer: Milo.
The author of this harness cannot self-certify it. Milo must review the
final SHA, including these tests. A red result is development evidence that
package C has not landed. It is not a pass, not merge evidence, and not a
release.

These tests call the production constructors and routes with no auth bypass
and with no explicit signing key, webhook secret, or broker secret. They
assert refusal and the absence of the side effect. A status code alone is
not the assertion. Nothing here is marked skip, xfail, or optional.

Package C dependencies (do not "fix" these by editing that behavior in A):

- ``keelway/api/routes.py`` ``create_run``, ``enqueue_runner_job``, and
  ``poll_runner_jobs`` must reject missing and invalid authentication before
  any run, queue item, audit row, worktree, or repository change.
- ``core/orchestration/agent_loop.py`` host ``shell=True`` fallback and
  ``core/api/routes.py`` ``execute_terminal_command`` must not run a command
  when this execution has no verified isolation. The response must say the
  command path is unavailable or disabled.
- Source-default HMAC and webhook material in ``keelway/approvals/service.py``,
  ``keelway/approvals/quorum.py``, ``core/billing/entitlements.py``,
  ``core/storage/payment_broker.py``, and ``keelway/git_ci/github.py`` must
  not produce a runnable approval or billing configuration. An explicit
  non-default key belongs only in a future test fixture and is not installed
  by this module.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from core.api import routes as studio_routes
from core.config import settings
from core.main import app as studio_app
from core.orchestration.agent_loop import AutonomousAgentLoop, AutonomyPolicy
from core.security.auth import launch_token
from core.storage.workspace_fs import WorkspaceFilesystem
from keelway.api.app import app as governance_app
from keelway.api import routes as governance_routes
from keelway.approvals.quorum import TwoHumanQuorumService
from keelway.approvals.service import ApprovalService
from keelway.audit.store import SQLiteAuditStore
from keelway.core.models import ApprovalDecision
from keelway.git_ci.github import GitHubAppWebhookHandler

pytestmark = [pytest.mark.auth, pytest.mark.safety_negative]

_REFUSAL_WORDS = ("unavailable", "disabled", "refus")


def _git_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "--local", "user.email", "package-a@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "--local", "user.name", "Package A"], cwd=path, check=True)
    (path / "README.md").write_text("baseline\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-m", "baseline"], cwd=path, check=True, capture_output=True)
    return path


def _snapshot(root: Path) -> dict[str, bytes]:
    found: dict[str, bytes] = {}
    for item in root.rglob("*"):
        if ".git" in item.parts or not item.is_file():
            continue
        found[str(item.relative_to(root))] = item.read_bytes()
    return found


def _head(repo: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()


def _audit_count(db_path: Path) -> int:
    if not db_path.exists():
        return 0
    with sqlite3.connect(db_path) as conn:
        return int(conn.execute("select count(*) from audit_events").fetchone()[0])


def _sentinel_command(sentinel: Path) -> str:
    code = "open(%r, 'w').write('ran')" % str(sentinel)
    return f"{sys.executable} -c {json.dumps(code)}"


def _assert_no_host_effect(sentinel: Path, payload: object, where: str) -> None:
    text = json.dumps(payload, default=str).lower()
    assert not sentinel.exists(), (
        f"{where} wrote a host-command sentinel. Package C must make unverified "
        "isolation refuse instead of falling back to a host command."
    )
    assert any(word in text for word in _REFUSAL_WORDS), (
        f"{where} did not refuse with an unavailable/disabled result. "
        f"Observed: {text[:800]}"
    )
    assert "success" not in text or "unavailable" in text or "disabled" in text


def _fail_closed(problems: list[str], dependency: str) -> None:
    assert not problems, dependency + " " + "; ".join(problems)


def _close_worktrees(run_ids: list[str]) -> None:
    for run_id in run_ids:
        coordinator = governance_routes.ACTIVE_RUNS.pop(run_id, None)
        workspace = getattr(coordinator, "workspace", None)
        worktree = getattr(workspace, "worktree_path", None)
        if worktree:
            shutil.rmtree(worktree, ignore_errors=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    return _git_repo(tmp_path / "repo")


@pytest.fixture
def governance_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    audit_path = tmp_path / "safety-audit.db"
    monkeypatch.setattr(governance_routes, "SHARED_AUDIT_STORE", SQLiteAuditStore(str(audit_path)))
    with TestClient(governance_app) as client:
        yield client, audit_path


@pytest.fixture
def studio_client(repo: Path, monkeypatch: pytest.MonkeyPatch):
    assert settings.auth_required is True
    monkeypatch.setattr(studio_routes, "_workspace_fs", WorkspaceFilesystem(root_dir=str(repo)))
    with TestClient(studio_app) as client:
        yield client


def _auth_cases():
    return [
        pytest.param({}, id="missing"),
        pytest.param({"Authorization": "Bearer keelway_not-a-real-token"}, id="invalid"),
    ]


@pytest.mark.parametrize("headers", _auth_cases())
def test_missing_or_invalid_auth_cannot_create_a_run_or_mutate_a_repo(governance_client, repo: Path, headers):
    client, audit_path = governance_client
    before_ids = set(governance_routes.ACTIVE_RUNS)
    before_files = _snapshot(repo)
    before_head = _head(repo)
    before_audit = _audit_count(audit_path)
    created: list[str] = []
    try:
        response = client.post(
            "/v1/runs",
            headers=headers,
            json={"repo_path": str(repo), "task_prompt": "package A safety negative"},
        )
        created = [run_id for run_id in governance_routes.ACTIVE_RUNS if run_id not in before_ids]
        worktrees = []
        for run_id in created:
            workspace = getattr(governance_routes.ACTIVE_RUNS[run_id], "workspace", None)
            worktree = getattr(workspace, "worktree_path", None)
            if worktree:
                worktrees.append(worktree)
        problems = []
        if response.status_code not in (401, 403):
            problems.append(f"refused={response.status_code} body={response.text[:300]}")
        if created:
            problems.append(f"registered runs={created}")
        if worktrees:
            problems.append(f"worktrees={worktrees}")
        if _snapshot(repo) != before_files:
            problems.append("repository files changed")
        if _head(repo) != before_head:
            problems.append("repository HEAD changed")
        if _audit_count(audit_path) != before_audit:
            problems.append(
                f"audit rows {_audit_count(audit_path)} != {before_audit}"
            )
        _fail_closed(
            problems,
            "Package C dependency: keelway/api/routes.py create_run must refuse missing/invalid authentication with no run, worktree, audit row, or repository change.",
        )
    finally:
        _close_worktrees(created)


@pytest.mark.parametrize("headers", _auth_cases())
def test_missing_or_invalid_auth_cannot_enqueue_a_job(governance_client, repo: Path, headers):
    client, _audit_path = governance_client
    sentinel = repo / "enqueued-side-effect.txt"
    before = list(governance_routes.PENDING_RUNNER_JOBS)
    try:
        response = client.post(
            "/v1/runner/jobs/enqueue",
            headers=headers,
            json={"org_id": "org_safety", "repo_path": str(repo), "command": _sentinel_command(sentinel)},
        )
        problems = []
        if response.status_code not in (401, 403):
            problems.append(f"refused={response.status_code} body={response.text[:300]}")
        if governance_routes.PENDING_RUNNER_JOBS != before:
            problems.append(
                f"queue grew by {len(governance_routes.PENDING_RUNNER_JOBS) - len(before)}"
            )
        if sentinel.exists():
            problems.append("enqueue command wrote a repository file")
        body = response.json()
        if body.get("status") == "ENQUEUED" or "job_id" in body:
            problems.append(f"enqueue receipt={body}")
        _fail_closed(
            problems,
            "Package C dependency: keelway/api/routes.py enqueue_runner_job must refuse missing/invalid authentication and leave the job queue unchanged.",
        )
    finally:
        governance_routes.PENDING_RUNNER_JOBS[:] = before


@pytest.mark.parametrize(
    "token",
    [
        pytest.param("", id="missing"),
        pytest.param("runner-a:org_safety:1:forged", id="shape-only"),
    ],
)
def test_missing_or_invalid_auth_cannot_poll_a_job(governance_client, repo: Path, token: str):
    client, _audit_path = governance_client
    job = {
        "job_id": "pkg-a-safety-job",
        "org_id": "org_safety",
        "runner_id": "runner-a",
        "repo_path": str(repo),
    }
    before = list(governance_routes.PENDING_RUNNER_JOBS)
    governance_routes.PENDING_RUNNER_JOBS.append(job)
    try:
        response = client.post(
            "/v1/runner/jobs/poll",
            json={"runner_id": "runner-a", "org_id": "org_safety", "auth_token": token},
        )
        problems = []
        if response.status_code not in (401, 403):
            problems.append(f"refused={response.status_code} body={response.text[:300]}")
        if job not in governance_routes.PENDING_RUNNER_JOBS:
            problems.append("poll removed the queued job")
        body = response.json()
        if body.get("job_available") is True or body.get("job") not in (None,):
            problems.append(f"poll returned a job={body.get('job')}")
        if job["job_id"] in response.text and response.status_code == 200:
            problems.append("poll response included the job id")
        _fail_closed(
            problems,
            "Package C dependency: keelway/api/routes.py poll_runner_jobs must reject a missing token and a shape-only token (runner:org:stamp:forged). The shape check is not authentication, and the queued job must stay queued.",
        )
    finally:
        governance_routes.PENDING_RUNNER_JOBS[:] = before


def test_shape_only_token_cannot_poll_a_studio_runner_job(studio_client, repo: Path):
    """Studio poll does not use the API-token dependency. A forged body token must not dequeue."""
    job = {
        "job_id": "pkg-a-studio-job",
        "org_id": "org_safety",
        "repo_path": str(repo),
    }
    before = list(studio_routes.RUNNER_JOBS_QUEUE)
    studio_routes.RUNNER_JOBS_QUEUE.append(job)
    try:
        response = studio_client.post(
            "/v1/runner/jobs/poll",
            json={
                "runner_id": "runner-a",
                "org_id": "org_safety",
                "auth_token": "runner-a:org_safety:1:forged",
            },
        )
        problems = []
        if response.status_code not in (401, 403):
            problems.append(f"refused={response.status_code} body={response.text[:300]}")
        if job not in studio_routes.RUNNER_JOBS_QUEUE:
            problems.append("poll removed the studio job")
        if job["job_id"] in response.text and response.status_code == 200:
            problems.append("poll response included the studio job id")
        _fail_closed(
            problems,
            "Package C dependency: core/api/routes.py poll_customer_runner_jobs must reject a shape-only token. Existing tests/test_core_runner_routes.py still expects that shape to succeed; C must replace that expectation when this negative goes green.",
        )
    finally:
        studio_routes.RUNNER_JOBS_QUEUE[:] = before


@pytest.mark.parametrize("headers", _auth_cases())
def test_missing_or_invalid_auth_cannot_write_a_workspace_file(studio_client, repo: Path, headers):
    target = repo / "mutated.txt"
    response = studio_client.post(
        "/v1/files/save",
        headers=headers,
        json={"path": "mutated.txt", "content": "unauthenticated write"},
    )
    assert response.status_code in (401, 403)
    assert not target.exists()
    assert _snapshot(repo) == {"README.md": b"baseline\n"}


@pytest.mark.parametrize("headers", _auth_cases())
def test_missing_or_invalid_auth_cannot_commit_or_run_a_terminal(studio_client, repo: Path, headers):
    sentinel = repo / "terminal-sentinel.txt"
    before_head = _head(repo)
    commit = studio_client.post("/v1/git/commit", headers=headers, json={"message": "unauth"})
    terminal = studio_client.post(
        "/v1/terminal/exec",
        headers=headers,
        json={"command": _sentinel_command(sentinel)},
    )
    assert commit.status_code in (401, 403)
    assert terminal.status_code in (401, 403)
    assert _head(repo) == before_head
    assert not sentinel.exists()
    assert "stdout" not in terminal.text


@pytest.mark.asyncio
async def test_unverified_isolation_cannot_fall_back_to_a_host_command(tmp_path: Path):
    sentinel = tmp_path / "host-fallback-sentinel.txt"
    workspace = WorkspaceFilesystem(root_dir=str(tmp_path))
    loop = AutonomousAgentLoop(
        task_id="pkg_a_isolation",
        workspace_fs=workspace,
        policy=AutonomyPolicy.CONFIRM_MUTATION,
        record_flight=False,
    )
    assert loop.command_runner is None
    command = _sentinel_command(sentinel)
    result = await loop.execute_tool("run_command", {"command": command})
    if result.get("status") == "paused_for_approval":
        assert not sentinel.exists()
        result = await loop.approve_pending(True)
    _assert_no_host_effect(
        sentinel,
        result,
        "Package C dependency: core/orchestration/agent_loop.py run_command",
    )


def test_authenticated_terminal_cannot_fall_back_to_a_host_command(studio_client, repo: Path):
    sentinel = repo / "terminal-sentinel.txt"
    before_head = _head(repo)
    before_files = _snapshot(repo)
    response = studio_client.post(
        "/v1/terminal/exec",
        headers={"Authorization": f"Bearer {launch_token()}"},
        json={"command": _sentinel_command(sentinel)},
    )
    _assert_no_host_effect(
        sentinel,
        {"status_code": response.status_code, "body": response.text},
        "Package C dependency: core/api/routes.py execute_terminal_command",
    )
    assert _head(repo) == before_head
    assert _snapshot(repo) == before_files


def test_manifest_without_verified_isolation_does_not_run_a_host_command(tmp_path: Path):
    from core.agents.guard import ManifestNotRunnable, loop_from_manifest
    from core.agents.sandbox import Sandbox, SandboxUnavailable

    sentinel = tmp_path / "manifest-host-sentinel.txt"
    example = Path(__file__).resolve().parent.parent / "docs" / "spec" / "examples" / "test-fixer.agent.json"
    manifest = json.loads(example.read_text(encoding="utf-8"))
    verified, detail = Sandbox(tmp_path).verify()
    if verified:
        bare = Sandbox(tmp_path, backend="")
        with pytest.raises(SandboxUnavailable):
            bare.run(_sentinel_command(sentinel))
    else:
        with pytest.raises(ManifestNotRunnable, match="verified sandbox"):
            loop_from_manifest(
                manifest,
                "pkg_a_manifest",
                WorkspaceFilesystem(root_dir=str(tmp_path)),
                record_flight=False,
            )
        assert detail
    assert not sentinel.exists()


def _source_default_closed(factory, label: str):
    try:
        return factory(), None
    except Exception as exc:
        text = f"{type(exc).__name__}: {exc}".lower()
        assert any(word in text for word in _REFUSAL_WORDS + ("default", "explicit", "not configured")), (
            f"{label} raised {type(exc).__name__}: {exc} without stating that the source default is refused"
        )
        return None, exc


def test_source_default_approval_key_cannot_record_an_approval():
    service, refused = _source_default_closed(ApprovalService, "ApprovalService()")
    if service is None:
        assert refused is not None
        return
    request = service.create_request(
        run_id="pkg_a_safety",
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
    assert ok is False, (
        "Package C dependency: keelway/approvals/service.py ApprovalService() uses the "
        f"source-default HMAC key and recorded an approval ({message})."
    )
    assert request.id not in service._consumed
    assert request.status != "APPROVED"


def test_source_default_quorum_key_cannot_approve_a_quorum():
    service, refused = _source_default_closed(TwoHumanQuorumService, "TwoHumanQuorumService()")
    if service is None:
        assert refused is not None
        return
    request = service.create_quorum_request(
        run_id="pkg_a_safety",
        patch_hash="sha256:abc",
        environment="production",
    )
    first_ok, first_message = service.submit_role_approval(
        request.id, "ada_reviewer", "Security Lead", request.patch_hash
    )
    second_ok, second_message = service.submit_role_approval(
        request.id, "ben_reviewer", "Platform Owner", request.patch_hash
    )
    assert first_ok is False and second_ok is False, (
        "Package C dependency: keelway/approvals/quorum.py TwoHumanQuorumService() uses the "
        f"source-default HMAC key and accepted approvals ({first_message}, {second_message})."
    )
    assert request.signatures == {}
    assert request.status != "APPROVED"


def test_source_default_billing_webhook_rejects_its_own_signature(tmp_path: Path):
    from core.billing.entitlements import BillingWebhookHandler

    handler, refused = _source_default_closed(BillingWebhookHandler, "BillingWebhookHandler()")
    if handler is None:
        assert refused is not None
        return
    payload = {"org_id": "org_safety", "seat_delta": 5}
    raw = json.dumps(payload, sort_keys=True).encode("utf-8")
    import hashlib
    import hmac

    signature = hmac.new(handler.secret.encode("utf-8"), raw, hashlib.sha256).hexdigest()
    result = handler.handle_event("evt_safety_default", "seat.added", payload, signature_header=signature)
    assert result.get("status") != "processed", (
        "Package C dependency: core/billing/entitlements.py BillingWebhookHandler() accepted an "
        "event signed with its source-default webhook secret."
    )
    assert handler.processed_events == set()
    assert handler.event_history == []
    assert not list(tmp_path.iterdir())


def test_source_default_billing_webhook_rejects_an_unsigned_event():
    from core.billing.entitlements import BillingWebhookHandler

    handler, refused = _source_default_closed(BillingWebhookHandler, "BillingWebhookHandler()")
    if handler is None:
        assert refused is not None
        return
    result = handler.handle_event(
        "evt_safety_unsigned",
        "seat.added",
        {"org_id": "org_safety", "seat_delta": 5},
        signature_header=None,
    )
    assert result.get("status") != "processed", (
        "Package C dependency: core/billing/entitlements.py BillingWebhookHandler() processed "
        "an unsigned billing event constructed from the source default."
    )
    assert handler.processed_events == set()
    assert handler.event_history == []


def test_source_default_entitlement_key_cannot_register_a_certificate(tmp_path: Path):
    from core.billing.entitlements import (
        DEFAULT_ENTITLEMENT_KEY,
        EntitlementCertificate,
        EntitlementManager,
        EnterpriseFeature,
        LicenseTier,
        TIER_DEFAULT_FEATURES,
    )
    import time

    storage = tmp_path / "entitlements.json"
    manager, refused = _source_default_closed(
        lambda: EntitlementManager(storage_path=storage),
        "EntitlementManager()",
    )
    if manager is None:
        assert refused is not None
        assert not storage.exists()
        return
    assert manager.secret_key == DEFAULT_ENTITLEMENT_KEY
    now = time.time()
    certificate = EntitlementCertificate(
        org_id="org_safety",
        org_name="Safety",
        tier=LicenseTier.ENTERPRISE,
        seats=10,
        allowed_features=[feature.value for feature in TIER_DEFAULT_FEATURES[LicenseTier.ENTERPRISE]],
        issued_at=now,
        expires_at=now + 86400,
    )
    certificate.sign()
    ok, status = manager.register_certificate(certificate)
    assert ok is False, (
        "Package C dependency: core/billing/entitlements.py EntitlementManager() accepted a "
        f"certificate signed with the source-default HMAC key ({status})."
    )
    assert manager.active_certificates == {}
    assert not storage.exists()
    assert EnterpriseFeature.CUSTOMER_VPC_RUNNER.value not in {
        item for cert in manager.active_certificates.values() for item in cert.allowed_features
    }


def test_source_default_entitlement_key_cannot_grant_features(tmp_path: Path):
    from core.billing.entitlements import EntitlementManager, EnterpriseFeature

    storage = tmp_path / "entitlements.json"
    manager, refused = _source_default_closed(
        lambda: EntitlementManager(storage_path=storage),
        "EntitlementManager()",
    )
    if manager is None:
        assert refused is not None
        assert not storage.exists()
        return
    granted, reason = manager.check_feature_access("org_safety", EnterpriseFeature.LOCAL_AGENT_LOOP)
    assert granted is False, (
        "Package C dependency: core/billing/entitlements.py granted a feature from a certificate "
        f"signed with the source-default key ({reason})."
    )
    assert manager.active_certificates == {}
    assert not storage.exists()


def test_source_default_payment_secret_cannot_create_a_runnable_intent():
    from core.storage.payment_broker import GlobalPaymentBroker, GlobalRail

    broker, refused = _source_default_closed(GlobalPaymentBroker, "GlobalPaymentBroker()")
    if broker is None:
        assert refused is not None
        return
    intent = None
    try:
        intent = broker.create_intent(GlobalRail.OFFLINE_VOUCHER, 10, "USD", "safety-recipient")
    except Exception as exc:
        text = f"{type(exc).__name__}: {exc}".lower()
        assert any(word in text for word in _REFUSAL_WORDS + ("default", "explicit"))
        intent = None
    assert broker.intents == {}, (
        "Package C dependency: core/storage/payment_broker.py GlobalPaymentBroker() created a "
        "runnable payment intent from the source-default broker secret."
    )
    assert intent is None or getattr(intent, "status", None) in {"unavailable", "disabled", "refused"}


def test_source_default_github_webhook_cannot_process_an_event():
    handler, refused = _source_default_closed(GitHubAppWebhookHandler, "GitHubAppWebhookHandler()")
    if handler is None:
        assert refused is not None
        return
    payload = {
        "action": "closed",
        "pull_request": {"number": 1, "merged": True, "head": {"sha": "abc"}, "merged_at": None},
    }
    ok, kind, _data = handler.process_event("pull_request", payload)
    assert ok is False and kind is None, (
        "Package C dependency: keelway/git_ci/github.py GitHubAppWebhookHandler() processed a "
        "pull-request event with the source-default webhook secret and no verified signature."
    )
