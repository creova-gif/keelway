"""Package E: bounded gateway/API error disclosure (offline, no live providers)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from core.main import app
from core.security.auth import launch_token
from core.security.error_disclosure import (
    classify_inference_error,
    public_inference_detail,
    public_inference_error,
)


def bearer():
    return {"Authorization": f"Bearer {launch_token()}"}


@pytest.mark.parametrize(
    "exc,expected",
    [
        (RuntimeError("No model provider allowed for this request."), "routing_failure"),
        (RuntimeError("All model providers failed or unavailable."), "model_unavailable"),
        (TimeoutError("provider timed out after 30s"), "timeout"),
        (RuntimeError("secret=sk-live-SHOULD-NOT-LEAK body={...}"), "unknown"),
    ],
)
def test_classify_inference_error_categories(exc, expected):
    assert classify_inference_error(exc) == expected


def test_public_inference_error_never_echoes_exception_text():
    secret = "sk-live-LEAKED-CREDENTIAL-xyz"
    err = public_inference_error(RuntimeError(f"upstream said {secret}"))
    blob = str(err)
    assert secret not in blob
    assert "upstream said" not in blob
    assert err["code"] in {
        "routing_failure",
        "model_unavailable",
        "provider_error",
        "timeout",
        "invalid_request",
        "airgap_blocked",
        "unknown",
    }
    assert err["message"]
    detail = public_inference_detail(RuntimeError(f"adapter blew up: {secret}"))
    assert secret not in detail
    assert "adapter blew up" not in detail
    assert detail.startswith("Inference failure (")


def test_completions_502_uses_allowlisted_detail_not_raw_exception():
    secret = "AKIA_SHOULD_NOT_APPEAR_IN_HTTP"
    with TestClient(app) as client:
        with patch(
            "core.api.routes.gateway.complete",
            new=AsyncMock(side_effect=RuntimeError(f"provider dump {secret}")),
        ):
            resp = client.post(
                "/v1/completions",
                headers=bearer(),
                json={"messages": [{"role": "user", "content": "ping"}]},
            )
    assert resp.status_code == 502
    detail = resp.json().get("detail", "")
    assert secret not in detail
    assert "provider dump" not in detail
    assert "Inference failure (" in detail
