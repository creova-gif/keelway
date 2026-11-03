"""Keelway Signed Policy Bundle Distribution and Verification.
Implements central signed policy bundles, anti-rollback monotonic epochs,
and local cryptographic signature verification (PRD-001 / ADR-061).
"""
from __future__ import annotations

import datetime
import hashlib
import hmac
import json
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

BUNDLE_AUTHORITY_KEY = b"keelway_enterprise_policy_authority_key_2026_v1"


class PolicyBundleValidationError(Exception):
    pass


class PolicyBundlePayload(BaseModel):
    bundle_id: str
    org_id: str
    version: int  # Monotonic integer epoch
    issued_at: str
    expires_at: str
    allowed_tools: List[str]
    allowed_repos: List[str]
    sensitive_patterns: List[str]
    allow_network: bool = False
    require_two_human_quorum: bool = True
    max_tokens_per_run: int = 50000
    max_cost_cents: int = 500


class SignedPolicyBundle(BaseModel):
    payload: PolicyBundlePayload
    signature: str


def canonical_serialize(data: Dict[str, Any]) -> bytes:
    """Deterministic canonical JSON serialization for signing."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


class PolicyBundleAuthority:
    """Signs policy bundles on behalf of the customer security authority."""

    def __init__(self, authority_key: bytes = BUNDLE_AUTHORITY_KEY):
        self.authority_key = authority_key

    def create_and_sign_bundle(
        self,
        bundle_id: str,
        org_id: str,
        version: int,
        allowed_tools: List[str],
        allowed_repos: List[str],
        sensitive_patterns: List[str],
        allow_network: bool = False,
        require_two_human_quorum: bool = True,
        ttl_days: int = 30,
    ) -> SignedPolicyBundle:
        """Authors and cryptographically seals a versioned policy bundle."""
        now = datetime.datetime.now(datetime.timezone.utc)
        expires = now + datetime.timedelta(days=ttl_days)

        payload = PolicyBundlePayload(
            bundle_id=bundle_id,
            org_id=org_id,
            version=version,
            issued_at=now.isoformat(),
            expires_at=expires.isoformat(),
            allowed_tools=allowed_tools,
            allowed_repos=allowed_repos,
            sensitive_patterns=sensitive_patterns,
            allow_network=allow_network,
            require_two_human_quorum=require_two_human_quorum,
        )

        canonical_bytes = canonical_serialize(payload.model_dump())
        signature = hmac.new(self.authority_key, canonical_bytes, hashlib.sha256).hexdigest()

        return SignedPolicyBundle(payload=payload, signature=signature)


class LocalPolicyBundleVerifier:
    """Verifies signed policy bundles and enforces anti-rollback monotonic high-watermarks."""

    def __init__(self, authority_key: bytes = BUNDLE_AUTHORITY_KEY):
        self.authority_key = authority_key
        self.highest_accepted_epoch: int = 0

    def verify_and_load(self, bundle: SignedPolicyBundle, target_org_id: str) -> Tuple[bool, str]:
        """Validates bundle signature, tenancy, expiration, and monotonicity."""
        payload_dict = bundle.payload.model_dump()
        canonical_bytes = canonical_serialize(payload_dict)

        # 1. Cryptographic signature check
        expected_sig = hmac.new(self.authority_key, canonical_bytes, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(bundle.signature, expected_sig):
            return False, "ERR_INVALID_POLICY_BUNDLE_SIGNATURE"

        # 2. Tenancy check
        if bundle.payload.org_id != target_org_id:
            return False, (
                f"ERR_ORG_MISMATCH: Bundle scoped for '{bundle.payload.org_id}', "
                f"target is '{target_org_id}'"
            )

        # 3. Expiration check
        now = datetime.datetime.now(datetime.timezone.utc)
        if now > datetime.datetime.fromisoformat(bundle.payload.expires_at):
            return False, f"ERR_POLICY_BUNDLE_EXPIRED: Expired at {bundle.payload.expires_at}"

        # 4. Anti-rollback protection (Monotonic epoch enforcement per ADR-061)
        if bundle.payload.version < self.highest_accepted_epoch:
            return False, (
                f"ERR_POLICY_ROLLBACK_ATTEMPT: Attempted version {bundle.payload.version} "
                f"below highest accepted epoch {self.highest_accepted_epoch}"
            )

        self.highest_accepted_epoch = bundle.payload.version
        return True, "INFO_POLICY_BUNDLE_VERIFIED_AND_ACCEPTED"
