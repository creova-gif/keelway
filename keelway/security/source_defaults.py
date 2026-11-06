"""Source-default signing material is not a runnable configuration.

The byte strings below are published in the repository. They are identifiers
for refusal, not credentials to copy into an operator environment. A runnable
approval, quorum, entitlement, billing webhook, payment broker, or GitHub
webhook requires an explicit non-default secret supplied by the caller or by
an operator environment variable that is not one of these values.

Nothing in this module reads the environment in a way that turns a source
default back on. ``configured_signing_key`` returns the source default when
the operator variable is missing or still set to that default, and callers
must refuse that result.
"""

from __future__ import annotations

import os

SOURCE_DEFAULT_SECRETS = frozenset(
    {
        b"keelway_approval_signing_secret_v1",
        b"keelway_quorum_signing_secret_v1",
        b"KEELWAY_ENTERPRISE_ENTITLEMENT_SIGNING_KEY_2026",
        b"KEELWAY_BILLING_WEBHOOK_SECRET_2026",
        b"KORA_SOVEREIGN_PAYMENT_SECRET_2026",
        b"keelway_github_webhook_secret_v1",
    }
)

REFUSAL = "source-default signing configuration is refused; set an explicit non-default secret"


class InsecureDefaultConfiguration(RuntimeError):
    """Raised when an operation would become runnable from source-default material."""


def as_secret_bytes(secret: bytes | str) -> bytes:
    if isinstance(secret, str):
        return secret.encode("utf-8")
    return bytes(secret)


def is_source_default(secret: bytes | str | None) -> bool:
    if secret is None:
        return True
    raw = as_secret_bytes(secret)
    return raw == b"" or raw in SOURCE_DEFAULT_SECRETS


def configured_signing_key(env_name: str, source_default: bytes) -> bytes:
    """Operator material, or the source default when nothing explicit is configured.

    The source default is returned unchanged so the caller refuses it. Setting
    the environment variable to the published default does not enable signing.
    """
    raw = os.environ.get(env_name, "")
    if not raw:
        return source_default
    key = raw.encode("utf-8")
    if is_source_default(key):
        return source_default
    return key
