"""Bounded public error disclosure for gateway / API failure surfaces.

Package E: never echo raw exception text (may contain prompts, bodies, or
credentials) to HTTP clients or Studio terminals. Callers may log the original
exception server-side; public payloads stay allowlisted.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

# Allowlisted categories returned to clients. Keep short and stable.
PUBLIC_ERROR_CATEGORIES = frozenset(
    {
        "routing_failure",
        "model_unavailable",
        "provider_error",
        "timeout",
        "invalid_request",
        "airgap_blocked",
        "unknown",
    }
)

_FIXED_MESSAGES: Mapping[str, str] = {
    "routing_failure": "Model routing failed before a provider completed this request.",
    "model_unavailable": "No model is available to complete this request.",
    "provider_error": "The model provider failed before completing this request.",
    "timeout": "The model provider timed out before completing this request.",
    "invalid_request": "The request was rejected before inference ran.",
    "airgap_blocked": "Air-gap policy blocked outbound model providers for this request.",
    "unknown": "Inference failed before a usable response was produced.",
}


def classify_inference_error(exc: BaseException) -> str:
    """Map an exception to one allowlisted public category. Never returns raw text."""
    text = str(exc)
    lower = text.lower()
    if "air-gap" in lower or "air gap" in lower or "zero-egress" in lower:
        return "airgap_blocked"
    if "no model provider allowed" in lower:
        return "routing_failure"
    if lower.startswith("all model providers failed or unavailable"):
        return "model_unavailable"
    if "timeout" in lower or "timed out" in lower:
        return "timeout"
    if "invalid" in lower and "request" in lower:
        return "invalid_request"
    if "provider" in lower or "inference" in lower or "adapter" in lower:
        return "provider_error"
    return "unknown"


def public_inference_error(
    exc: BaseException,
    *,
    provider: Optional[str] = None,
    http_status: int = 502,
) -> Dict[str, Any]:
    """Build a fixed client-safe error object for gateway/API sinks.

    Includes only allowlisted category, fixed message, optional validated
    provider id, and HTTP status. Never includes ``str(exc)``.
    """
    category = classify_inference_error(exc)
    if category not in PUBLIC_ERROR_CATEGORIES:
        category = "unknown"
    body: Dict[str, Any] = {
        "code": category,
        "message": _FIXED_MESSAGES[category],
        "status": http_status,
    }
    if provider is not None:
        # Provider enums are short stable tokens (local, openai, …); reject junk.
        token = str(provider).strip().lower()[:32]
        if token and token.replace("_", "").replace("-", "").isalnum():
            body["provider"] = token
    return body


def public_inference_detail(exc: BaseException, *, provider: Optional[str] = None) -> str:
    """Single-line HTTP ``detail`` string using only allowlisted fields."""
    err = public_inference_error(exc, provider=provider)
    if "provider" in err:
        return f"Inference failure ({err['code']}, provider={err['provider']}): {err['message']}"
    return f"Inference failure ({err['code']}): {err['message']}"
