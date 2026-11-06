"""Explicit runner enrollment for governance and Studio poll authentication.

A token shaped as ``runner_id:org_id:timestamp:hmac`` is not authentication.
Poll accepts it only when that runner was enrolled with an explicit secret
and the HMAC matches. Source-default secrets cannot be enrolled. The
predictable hash of org and runner id is not enrolled automatically.
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Dict, Optional, Tuple

from keelway.security.source_defaults import InsecureDefaultConfiguration, is_source_default

_ENROLLED: Dict[Tuple[str, str], bytes] = {}


def enroll_runner(runner_id: str, org_id: str, secret: bytes) -> None:
    """Register the only secret that may authenticate this runner for this org."""
    if not runner_id or not org_id:
        raise InsecureDefaultConfiguration("runner enrollment requires an explicit runner and org")
    if is_source_default(secret):
        raise InsecureDefaultConfiguration(
            "source-default signing configuration is refused; runner enrollment needs an explicit secret"
        )
    _ENROLLED[(runner_id, org_id)] = bytes(secret)


def enrolled_secret(runner_id: str, org_id: str) -> Optional[bytes]:
    return _ENROLLED.get((runner_id, org_id))


def clear_enrollments() -> None:
    """Test helper. Production poll has no enrollment until ``enroll_runner`` is called."""
    _ENROLLED.clear()


def verify_enrolled_runner_token(runner_id: str, org_id: str, token: str) -> bool:
    """True only for an enrolled runner whose HMAC binds runner, org, and timestamp."""
    secret = _ENROLLED.get((runner_id, org_id))
    if secret is None or not runner_id or not org_id or not token:
        return False
    try:
        parts = token.split(":")
        if len(parts) < 4:
            return False
        token_runner, token_org = parts[0], parts[1]
        timestamp = ":".join(parts[2:-1])
        received_sig = parts[-1]
        if token_runner != runner_id or token_org != org_id or not timestamp or not received_sig:
            return False
        expected = hmac.new(
            secret,
            f"{token_runner}:{token_org}:{timestamp}".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        if len(received_sig) != len(expected):
            return False
        return hmac.compare_digest(received_sig, expected)
    except Exception:
        return False
