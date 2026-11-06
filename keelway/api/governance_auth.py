"""Authentication for governance mutations.

Missing and invalid bearers are refused before a route body runs. When the
Studio settings module is importable, this follows ``settings.auth_required``
so the existing local test profile and the Studio launch token stay the
supported boundary. The governance container does not ship ``core``; there
auth stays required and only an explicit non-default operator token, or the
process token minted at startup, is accepted.

``AUTH_REQUIRED=false`` is the existing Studio flag. This module does not add
a second bypass and does not treat a well-shaped runner token as a bearer.
"""

from __future__ import annotations

import hmac
import os
import secrets
from typing import Optional

from fastapi import Header, HTTPException, status

from keelway.security.source_defaults import is_source_default

_PROCESS_TOKEN = "keelway_" + secrets.token_urlsafe(32)
_REJECTED_TOKENS = frozenset({"", "changeme", "keelway_not-a-real-token"})


def governance_auth_required() -> bool:
    try:
        from core.config import settings
    except Exception:
        return True
    return bool(getattr(settings, "auth_required", True))


def accepted_governance_tokens() -> list[str]:
    tokens: list[str] = []
    for name in ("KEELWAY_GOVERNANCE_TOKEN", "KEELWAY_API_TOKEN"):
        raw = os.environ.get(name, "").strip()
        if raw and raw not in _REJECTED_TOKENS and not is_source_default(raw):
            tokens.append(raw)
    try:
        from core.security.auth import launch_token

        launched = launch_token()
        if launched and launched not in _REJECTED_TOKENS:
            tokens.append(launched)
    except Exception:
        pass
    tokens.append(_PROCESS_TOKEN)
    return tokens


def dashboard_token() -> str:
    """Token embedded in the loopback dashboard only. Not a source constant."""
    tokens = accepted_governance_tokens()
    return tokens[0]


def bearer_is_valid(token: Optional[str]) -> bool:
    if not token or token in _REJECTED_TOKENS or is_source_default(token):
        return False
    presented = token.encode("utf-8")
    for candidate in accepted_governance_tokens():
        raw = candidate.encode("utf-8")
        if len(presented) == len(raw) and hmac.compare_digest(presented, raw):
            return True
    return False


def require_governance_actor(
    authorization: Optional[str] = Header(default=None),
    x_keelway_token: Optional[str] = Header(default=None),
) -> str:
    """Refuse missing and invalid authentication before the route body runs."""
    if not governance_auth_required():
        return "local-owner"
    token = ""
    if authorization:
        scheme, _, value = authorization.partition(" ")
        if scheme.lower() == "bearer" and value.strip():
            token = value.strip()
    if not token and x_keelway_token:
        token = x_keelway_token.strip()
    if not bearer_is_valid(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authentication.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return "authenticated"
