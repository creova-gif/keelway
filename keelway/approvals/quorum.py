"""Keelway Two-Human Quorum Approval Engine.
Implements ADR-045 and ADR-046: Mandatory two independent customer human approvers
(Security Lead AND Platform Owner) for production-scoped software changes.
"""
from __future__ import annotations

import datetime
import hashlib
import hmac
import uuid
from typing import Dict, List, Optional, Set, Tuple
from pydantic import BaseModel, Field

from keelway.security.source_defaults import InsecureDefaultConfiguration, is_source_default

QUORUM_SECRET_KEY = b"keelway_quorum_signing_secret_v1"

REQUIRED_PRODUCTION_ROLES = {"Security Lead", "Platform Owner"}
FORBIDDEN_ACTOR_SUBSTRINGS = {"agent", "bot", "ci", "service_account", "system", "sorvex"}


class QuorumRoleError(Exception):
    pass


class SelfQuorumProhibitedError(QuorumRoleError):
    pass


class IneligibleApproverError(QuorumRoleError):
    pass


class ApprovalSignatureRecord(BaseModel):
    principal_id: str
    role: str
    patch_hash: str
    signed_at: str
    signature: str


class QuorumApprovalRequest(BaseModel):
    id: str
    run_id: str
    patch_hash: str
    environment: str = "production"
    required_roles: Set[str] = Field(default_factory=lambda: set(REQUIRED_PRODUCTION_ROLES))
    signatures: Dict[str, ApprovalSignatureRecord] = Field(default_factory=dict)
    expires_at: str
    status: str = "PENDING"  # PENDING, APPROVED, REJECTED, EXPIRED, INVALIDATED

    @property
    def is_fully_approved(self) -> bool:
        """True if and only if all required distinct roles are satisfied by distinct humans."""
        if self.status != "APPROVED":
            return False
        roles_satisfied = set(self.signatures.keys())
        if not self.required_roles.issubset(roles_satisfied):
            return False
        # Verify distinct principals
        principals = {sig.principal_id for sig in self.signatures.values()}
        return len(principals) == len(self.required_roles)


class TwoHumanQuorumService:
    """Enforces multi-human separation-of-duties approval quorums (ADR-045/ADR-046)."""

    def __init__(self, ttl_seconds: int = 1800, signing_key: bytes = QUORUM_SECRET_KEY):
        self.ttl_seconds = ttl_seconds
        self.signing_key = signing_key
        self._requests: Dict[str, QuorumApprovalRequest] = {}

    def create_quorum_request(
        self,
        run_id: str,
        patch_hash: str,
        environment: str = "production",
        required_roles: Optional[Set[str]] = None,
    ) -> QuorumApprovalRequest:
        """Creates a multi-role quorum request."""
        now = datetime.datetime.now(datetime.timezone.utc)
        expires_at = (now + datetime.timedelta(seconds=self.ttl_seconds)).isoformat()
        req_id = str(uuid.uuid4())

        req = QuorumApprovalRequest(
            id=req_id,
            run_id=run_id,
            patch_hash=patch_hash,
            environment=environment,
            required_roles=required_roles or set(REQUIRED_PRODUCTION_ROLES),
            expires_at=expires_at,
        )
        self._requests[req_id] = req
        return req

    def get_request(self, request_id: str) -> Optional[QuorumApprovalRequest]:
        return self._requests.get(request_id)

    def sign_approval(
        self,
        request_id: str,
        run_id: str,
        patch_hash: str,
        principal_id: str,
        role: str,
        environment: str,
    ) -> str:
        """Generates cryptographic proof bound to the exact patch, principal, role, and env."""
        if is_source_default(self.signing_key):
            raise InsecureDefaultConfiguration("source-default signing configuration is refused")
        msg = f"{request_id}:{run_id}:{patch_hash}:{principal_id}:{role}:{environment}"
        return hmac.new(self.signing_key, msg.encode("utf-8"), hashlib.sha256).hexdigest()

    def submit_role_approval(
        self,
        request_id: str,
        principal_id: str,
        role: str,
        current_patch_hash: str,
    ) -> Tuple[bool, str]:
        """Submits an approval from one human for one role."""
        if is_source_default(self.signing_key):
            return False, "ERR_SOURCE_DEFAULT_SIGNING_KEY_REFUSED"
        req = self._requests.get(request_id)
        if not req:
            return False, "ERR_QUORUM_REQUEST_NOT_FOUND"

        # Check expiration
        now = datetime.datetime.now(datetime.timezone.utc)
        if now > datetime.datetime.fromisoformat(req.expires_at):
            req.status = "EXPIRED"
            return False, "ERR_QUORUM_EXPIRED"

        # Check patch immutability
        if current_patch_hash != req.patch_hash:
            req.status = "INVALIDATED"
            return False, "ERR_PATCH_HASH_MUTATED_QUORUM_INVALIDATED"

        # Prohibit automated agents and bots from acting as human approvers
        norm_principal = principal_id.lower()
        for forbidden in FORBIDDEN_ACTOR_SUBSTRINGS:
            if forbidden in norm_principal:
                return False, f"ERR_INELIGIBLE_APPROVER_IDENTITY: '{principal_id}' cannot count as human"

        # Check that role is required
        if role not in req.required_roles:
            return False, f"ERR_UNEXPECTED_ROLE: '{role}' is not in required roles {req.required_roles}"

        # Prevent same human holding multiple roles (ADR-046: "person holding both roles cannot count twice")
        for existing_role, sig in req.signatures.items():
            if sig.principal_id == principal_id and existing_role != role:
                return False, (
                    f"ERR_SELF_QUORUM_PROHIBITED: Principal '{principal_id}' already approved as "
                    f"'{existing_role}' and cannot satisfy '{role}'"
                )

        # Generate cryptographic signature
        now_str = now.isoformat()
        signature = self.sign_approval(
            request_id=req.id,
            run_id=req.run_id,
            patch_hash=req.patch_hash,
            principal_id=principal_id,
            role=role,
            environment=req.environment,
        )

        req.signatures[role] = ApprovalSignatureRecord(
            principal_id=principal_id,
            role=role,
            patch_hash=req.patch_hash,
            signed_at=now_str,
            signature=signature,
        )

        # Check if quorum is fully achieved
        if req.required_roles.issubset(set(req.signatures.keys())):
            principals = {sig.principal_id for sig in self.signatures_of(req)}
            if len(principals) == len(req.required_roles):
                req.status = "APPROVED"
                return True, "INFO_QUORUM_ACHIEVED_FULLY_APPROVED"

        return True, f"INFO_ROLE_APPROVED_PENDING_REMAINING_{len(req.required_roles - set(req.signatures.keys()))}"

    def signatures_of(self, req: QuorumApprovalRequest) -> List[ApprovalSignatureRecord]:
        return list(req.signatures.values())
