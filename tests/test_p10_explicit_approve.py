"""P-10: /v1/agent/approve requires an explicit boolean approved value."""

from __future__ import annotations

from fastapi.testclient import TestClient

from core.main import app
from core.security.auth import launch_token


def bearer():
    return {"Authorization": f"Bearer {launch_token()}"}


def test_approve_without_approved_field_is_rejected():
    with TestClient(app) as client:
        resp = client.post("/v1/agent/approve/missing-task", json={}, headers=bearer())
    assert resp.status_code == 400
    assert "approved" in resp.json()["detail"].lower()


def test_approve_with_non_boolean_approved_is_rejected():
    with TestClient(app) as client:
        resp = client.post(
            "/v1/agent/approve/missing-task",
            json={"approved": "yes"},
            headers=bearer(),
        )
    assert resp.status_code == 400
    assert "approved" in resp.json()["detail"].lower()


def test_approve_omission_does_not_default_to_true_via_query_sim():
    """Empty body must not be treated as approved=True."""
    with TestClient(app) as client:
        resp = client.post(
            "/v1/agent/approve/missing-task",
            headers={**bearer(), "Content-Type": "application/json"},
            content=b"{}",
        )
    assert resp.status_code == 400
    detail = resp.json()["detail"].lower()
    assert "approved" in detail
    assert "omitting" in detail or "required" in detail


def test_approve_with_explicit_bool_reaches_missing_task_404():
    with TestClient(app) as client:
        resp = client.post(
            "/v1/agent/approve/missing-task",
            json={"approved": False},
            headers=bearer(),
        )
    assert resp.status_code == 404
