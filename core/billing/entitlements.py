"""
Keelway Enterprise Entitlement Management & Privacy-Preserving Metering (WP16).
Provides cryptographically signed offline entitlement certificates, grace-period policies,
feature-gating, seat limits, and replay-protected billing webhook handling.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from core.billing.licence_keys import TRUSTED_LICENCE_KEYS
from keelway.security.source_defaults import is_source_default

NO_TRUSTED_KEY = "NO_TRUSTED_KEY"
NO_TRUSTED_KEY_REFUSAL = "no trusted licence signing key is configured; licence checks are refused"


class LicenseTier(str, Enum):
    COMMUNITY = "community"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class EnterpriseFeature(str, Enum):
    LOCAL_AGENT_LOOP = "local_agent_loop"
    GUIDED_BUILDER = "guided_builder"
    MCP_PLUGINS = "mcp_plugins"
    P2P_MESH = "p2p_mesh"
    POLICY_ENGINE = "policy_engine"
    TWO_HUMAN_QUORUM = "two_human_quorum"
    CUSTOMER_VPC_RUNNER = "customer_vpc_runner"
    AIRGAP_BUNDLE_EXPORT = "airgap_bundle_export"
    TIER2_HARDWARE_SECURITY = "tier2_hardware_security"
    MULTI_WORKSPACE_REGISTRY = "multi_workspace_registry"


TIER_DEFAULT_FEATURES: Dict[LicenseTier, Set[EnterpriseFeature]] = {
    LicenseTier.COMMUNITY: {
        EnterpriseFeature.LOCAL_AGENT_LOOP,
        EnterpriseFeature.GUIDED_BUILDER,
        EnterpriseFeature.MCP_PLUGINS,
        EnterpriseFeature.MULTI_WORKSPACE_REGISTRY,
    },
    LicenseTier.PRO: {
        EnterpriseFeature.LOCAL_AGENT_LOOP,
        EnterpriseFeature.GUIDED_BUILDER,
        EnterpriseFeature.MCP_PLUGINS,
        EnterpriseFeature.MULTI_WORKSPACE_REGISTRY,
        EnterpriseFeature.P2P_MESH,
        EnterpriseFeature.POLICY_ENGINE,
    },
    LicenseTier.ENTERPRISE: {
        EnterpriseFeature.LOCAL_AGENT_LOOP,
        EnterpriseFeature.GUIDED_BUILDER,
        EnterpriseFeature.MCP_PLUGINS,
        EnterpriseFeature.MULTI_WORKSPACE_REGISTRY,
        EnterpriseFeature.P2P_MESH,
        EnterpriseFeature.POLICY_ENGINE,
        EnterpriseFeature.TWO_HUMAN_QUORUM,
        EnterpriseFeature.CUSTOMER_VPC_RUNNER,
        EnterpriseFeature.AIRGAP_BUNDLE_EXPORT,
        EnterpriseFeature.TIER2_HARDWARE_SECURITY,
    },
}

def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def generate_signing_key() -> Tuple[bytes, str]:
    """New Ed25519 licence signing key: (private key PEM, public key for TRUSTED_LICENCE_KEYS)."""
    private = Ed25519PrivateKey.generate()
    pem = private.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )
    return pem, public_key_text(private)


def public_key_text(private: Ed25519PrivateKey) -> str:
    return _b64(private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw))


def load_signing_key(pem: bytes) -> Ed25519PrivateKey:
    key = serialization.load_pem_private_key(pem, password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError("licence signing key must be Ed25519")
    return key


@dataclass
class EntitlementCertificate:
    """Ed25519-signed licence that can be checked offline with only the issuer's public key."""
    org_id: str
    org_name: str
    tier: LicenseTier
    seats: int
    allowed_features: List[str]
    issued_at: float
    expires_at: float
    grace_period_days: int = 14
    key_id: str = ""
    signature: str = ""

    def signing_payload(self) -> bytes:
        payload = {
            "org_id": self.org_id,
            "org_name": self.org_name,
            "tier": self.tier.value if isinstance(self.tier, LicenseTier) else str(self.tier),
            "seats": self.seats,
            "allowed_features": sorted(self.allowed_features),
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "grace_period_days": self.grace_period_days,
            "key_id": self.key_id,
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def sign(self, private_key: Ed25519PrivateKey, key_id: str) -> None:
        self.key_id = key_id
        self.signature = _b64(private_key.sign(self.signing_payload()))

    def is_valid(
        self, trusted_keys: Optional[Dict[str, str]] = None, now: Optional[float] = None
    ) -> Tuple[bool, str]:
        """Check the signature against `trusted_keys` (default: TRUSTED_LICENCE_KEYS), then expiry and grace."""
        keys = TRUSTED_LICENCE_KEYS if trusted_keys is None else trusted_keys
        if not keys:
            return False, NO_TRUSTED_KEY
        public = keys.get(self.key_id)
        if public is None:
            return False, "UNKNOWN_SIGNING_KEY"
        try:
            Ed25519PublicKey.from_public_bytes(_unb64(public)).verify(_unb64(self.signature), self.signing_payload())
        except (InvalidSignature, ValueError):
            return False, "INVALID_SIGNATURE"

        current_time = now if now is not None else time.time()
        if current_time < self.issued_at:
            return False, "NOT_YET_VALID"

        if current_time <= self.expires_at:
            return True, "ACTIVE"

        grace_seconds = self.grace_period_days * 86400.0
        if current_time <= (self.expires_at + grace_seconds):
            return True, "IN_GRACE_PERIOD"

        return False, "EXPIRED"

    def allows(self, feature: Any) -> bool:
        """Checks if a feature is allowed under this certificate or its tier defaults."""
        feat_str = feature.value if hasattr(feature, "value") else str(feature)
        tier_feats = {f.value for f in TIER_DEFAULT_FEATURES.get(self.tier, set())}
        return feat_str in self.allowed_features or feat_str in tier_feats

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        if isinstance(self.tier, LicenseTier):
            data["tier"] = self.tier.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> EntitlementCertificate:
        tier_str = data.get("tier", "community")
        tier = LicenseTier(tier_str) if tier_str in [t.value for t in LicenseTier] else LicenseTier.COMMUNITY
        return cls(
            org_id=data["org_id"],
            org_name=data.get("org_name", data["org_id"]),
            tier=tier,
            seats=int(data.get("seats", 1)),
            allowed_features=list(data.get("allowed_features", [])),
            issued_at=float(data["issued_at"]),
            expires_at=float(data["expires_at"]),
            grace_period_days=int(data.get("grace_period_days", 14)),
            key_id=data.get("key_id", ""),
            signature=data.get("signature", ""),
        )


class PrivacyPreservingMeter:
    """
    Collects coarse-grained compute and token accounting per organization
    strictly without persisting prompts, diffs, filenames, or sensitive source code.
    """

    def __init__(self) -> None:
        # Maps org_id -> aggregated metrics
        self.aggregates: Dict[str, Dict[str, Any]] = {}

    def record_usage(
        self,
        org_id: str,
        model_name: str,
        tokens_in: int,
        tokens_out: int,
        cost_usd: float,
        duration_ms: float,
    ) -> None:
        """Records aggregated counters without retaining payload text."""
        if org_id not in self.aggregates:
            self.aggregates[org_id] = {
                "org_id": org_id,
                "total_invocations": 0,
                "total_tokens_in": 0,
                "total_tokens_out": 0,
                "total_cost_usd": 0.0,
                "total_duration_ms": 0.0,
                "models_used": set(),
                "last_active_at": time.time(),
            }

        entry = self.aggregates[org_id]
        entry["total_invocations"] += 1
        entry["total_tokens_in"] += tokens_in
        entry["total_tokens_out"] += tokens_out
        entry["total_cost_usd"] = round(entry["total_cost_usd"] + cost_usd, 6)
        entry["total_duration_ms"] = round(entry["total_duration_ms"] + duration_ms, 2)
        entry["models_used"].add(model_name)
        entry["last_active_at"] = time.time()

    def get_org_usage(self, org_id: str) -> Dict[str, Any]:
        entry = self.aggregates.get(org_id)
        if not entry:
            return {
                "org_id": org_id,
                "total_invocations": 0,
                "total_tokens_in": 0,
                "total_tokens_out": 0,
                "total_cost_usd": 0.0,
                "total_duration_ms": 0.0,
                "models_used": [],
                "last_active_at": None,
            }
        res = dict(entry)
        res["models_used"] = sorted(list(res["models_used"]))
        return res


class BillingWebhookHandler:
    """
    Idempotent billing webhook intake.
    Prevents double-charging, duplicate seat additions, and replayed events.
    """

    def __init__(self, secret: str = "KEELWAY_BILLING_WEBHOOK_SECRET_2026") -> None:
        self.secret = secret
        self.processed_events: Set[str] = set()
        self.event_history: List[Dict[str, Any]] = []

    def verify_webhook_signature(self, payload_bytes: bytes, signature_header: str) -> bool:
        if not signature_header:
            return False
        expected = hmac.new(self.secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature_header)

    def handle_event(
        self,
        event_id: str,
        event_type: str,
        payload: Dict[str, Any],
        signature_header: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Processes billing events with strict deduplication / idempotency.
        """
        if is_source_default(self.secret):
            return {
                "status": "rejected",
                "reason": "source-default webhook secret is refused",
                "event_id": event_id,
            }
        # Signature verification if provided
        if signature_header is not None:
            raw_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
            if not self.verify_webhook_signature(raw_bytes, signature_header):
                return {"status": "rejected", "reason": "invalid_signature", "event_id": event_id}

        # Idempotency check: duplicate event rejection
        if event_id in self.processed_events:
            return {"status": "ignored", "reason": "duplicate_event_already_processed", "event_id": event_id}

        # Process valid event
        self.processed_events.add(event_id)
        record = {
            "event_id": event_id,
            "event_type": event_type,
            "received_at": time.time(),
            "payload_summary": {k: payload[k] for k in list(payload.keys())[:5]},
        }
        self.event_history.append(record)
        return {"status": "processed", "event_id": event_id, "event_type": event_type}


class EntitlementManager:
    """Manages active organization licenses, feature gating, and seat allocations."""

    def __init__(self, storage_path: Optional[Path] = None, trusted_keys: Optional[Dict[str, str]] = None) -> None:
        self.storage_path = Path(storage_path or ".keelway/entitlements.json")
        self.trusted_keys: Dict[str, str] = dict(TRUSTED_LICENCE_KEYS if trusted_keys is None else trusted_keys)
        self.active_certificates: Dict[str, EntitlementCertificate] = {}
        self.active_seats: Dict[str, Set[str]] = {}  # org_id -> set of user/actor IDs
        self.meter = PrivacyPreservingMeter()
        self.webhook_handler = BillingWebhookHandler()
        self._load()

    def _load(self) -> None:
        if self.storage_path.exists():
            try:
                data = json.loads(self.storage_path.read_text(encoding="utf-8"))
                for org_id, cert_data in data.get("certificates", {}).items():
                    cert = EntitlementCertificate.from_dict(cert_data)
                    self.active_certificates[org_id] = cert
            except Exception:
                pass

    def save(self) -> None:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "updated_at": time.time(),
            "certificates": {org_id: c.to_dict() for org_id, c in self.active_certificates.items()},
        }
        self.storage_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _locked(self) -> bool:
        return not self.trusted_keys

    def register_certificate(self, cert: EntitlementCertificate) -> Tuple[bool, str]:
        if self._locked():
            return False, NO_TRUSTED_KEY_REFUSAL
        valid, status = cert.is_valid(self.trusted_keys)
        if not valid:
            return False, f"Certificate rejected: {status}"
        self.active_certificates[cert.org_id] = cert
        self.save()
        return True, status

    def get_certificate(self, org_id: str) -> EntitlementCertificate:
        """Returns the registered certificate, or an unsigned Community certificate."""
        if org_id in self.active_certificates:
            return self.active_certificates[org_id]
        now = time.time()
        return EntitlementCertificate(
            org_id=org_id,
            org_name=f"{org_id} (Community)",
            tier=LicenseTier.COMMUNITY,
            seats=1,
            allowed_features=[f.value for f in TIER_DEFAULT_FEATURES[LicenseTier.COMMUNITY]],
            issued_at=now,
            expires_at=now + (365 * 86400),
        )

    def status(self, org_id: str) -> Tuple[EntitlementCertificate, bool, str]:
        """(certificate, valid, status). The Community fallback needs no signature once a trusted key exists."""
        cert = self.get_certificate(org_id)
        if self._locked():
            return cert, False, NO_TRUSTED_KEY
        if org_id not in self.active_certificates:
            return cert, True, "COMMUNITY"
        valid, status = cert.is_valid(self.trusted_keys)
        return cert, valid, status

    def check_feature_access(self, org_id: str, feature: Union[EnterpriseFeature, str]) -> Tuple[bool, str]:
        """
        Determines whether the given organization is entitled to run a gated feature.
        """
        if self._locked():
            return False, NO_TRUSTED_KEY_REFUSAL
        feat_str = feature.value if isinstance(feature, EnterpriseFeature) else str(feature)
        cert, valid, status = self.status(org_id)
        if not valid:
            return False, f"License invalid: {status}"

        # Combine tier defaults with certificate-granted features
        allowed: Set[str] = {f.value for f in TIER_DEFAULT_FEATURES.get(cert.tier, set())}
        allowed.update(cert.allowed_features)

        if feat_str not in allowed:
            return False, f"Feature '{feat_str}' not permitted under {cert.tier.value.upper()} tier."

        return True, "GRANTED"

    def allocate_seat(self, org_id: str, actor_id: str) -> Tuple[bool, str]:
        """Allocates an enterprise seat to a specific developer/actor."""
        if self._locked():
            return False, NO_TRUSTED_KEY_REFUSAL
        cert, valid, status = self.status(org_id)
        if not valid:
            return False, f"License invalid: {status}"

        seats_assigned = self.active_seats.setdefault(org_id, set())
        if actor_id in seats_assigned:
            return True, "SEAT_ALREADY_ALLOCATED"

        if len(seats_assigned) >= cert.seats:
            return False, f"Seat capacity reached ({len(seats_assigned)}/{cert.seats} seats utilized)."

        seats_assigned.add(actor_id)
        return True, "ALLOCATED"


_GLOBAL_ENTITLEMENT_MANAGER: Optional[EntitlementManager] = None


def get_shared_entitlement_manager() -> EntitlementManager:
    global _GLOBAL_ENTITLEMENT_MANAGER
    if _GLOBAL_ENTITLEMENT_MANAGER is None:
        _GLOBAL_ENTITLEMENT_MANAGER = EntitlementManager()
    return _GLOBAL_ENTITLEMENT_MANAGER
