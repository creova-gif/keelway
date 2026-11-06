"""Tests for Keelway GitHub App Webhooks and CI Status Reconciliation (Milestone 2).
Validates HMAC signature verification, PR event normalization, and CI check processing.
"""
import hashlib
import hmac
import json
from starlette.testclient import TestClient

from keelway.api.app import app
from keelway.git_ci.github import GitHubAppWebhookHandler


def test_github_webhook_signature_verification():
    secret = "test_webhook_secret_key"
    handler = GitHubAppWebhookHandler(webhook_secret=secret)

    payload = json.dumps({"action": "opened", "pull_request": {"number": 42}}).encode("utf-8")
    valid_sig = "sha256=" + hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    invalid_sig = "sha256=" + "0" * 64

    assert handler.verify_signature(payload, valid_sig) is True
    assert handler.verify_signature(payload, invalid_sig) is False
    assert handler.verify_signature(payload, None) is False


def test_github_webhook_event_processing():
    handler = GitHubAppWebhookHandler(webhook_secret="package-c-explicit-webhook-fixture")

    # 1. PR Merged Event
    pr_payload = {
        "action": "closed",
        "pull_request": {
            "number": 101,
            "head": {"sha": "c0ffee123456"},
            "merged": True,
            "merged_at": "2026-11-03T18:00:00Z",
        },
    }
    ok, kind, data = handler.process_event("pull_request", pr_payload)
    assert ok is True
    assert kind == "PR_MERGED"
    assert data["pr_number"] == 101
    assert data["merged"] is True

    # 2. CI Check Run Completed
    check_payload = {
        "check_run": {
            "name": "keelway-staging-smoke-tests",
            "status": "completed",
            "conclusion": "success",
            "head_sha": "c0ffee123456",
        }
    }
    ok_ci, kind_ci, data_ci = handler.process_event("check_run", check_payload)
    assert ok_ci is True
    assert kind_ci == "CI_STATUS_RECONCILED"
    assert data_ci["passed"] is True


def test_github_webhook_api_endpoint():
    client = TestClient(app)
    secret = "keelway_github_webhook_secret_v1"  # Matches default in router

    payload_dict = {
        "action": "closed",
        "pull_request": {"number": 202, "merged": True, "head": {"sha": "deadbeef1234"}},
    }
    payload_bytes = json.dumps(payload_dict).encode("utf-8")
    sig = "sha256=" + hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()

    # The published source-default secret must not verify, even with a matching HMAC.
    res = client.post(
        "/v1/webhooks/github",
        content=payload_bytes,
        headers={"X-Hub-Signature-256": sig, "X-GitHub-Event": "pull_request"},
    )
    assert res.status_code == 401
    assert res.json()["detail"] == "Invalid HMAC-SHA256 signature"

    # 2. Invalid signature
    res_bad = client.post(
        "/v1/webhooks/github",
        content=payload_bytes,
        headers={"X-Hub-Signature-256": "sha256:bad_sig", "X-GitHub-Event": "pull_request"},
    )
    assert res_bad.status_code == 401
