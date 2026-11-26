"""Keelway Hardware WORM Storage Adapter Protocol & Dual-Receipt Validator.
Implements ADR-076 through ADR-080, and the normative schema defined in
397_SIGNED_WORM_DURABILITY_RECEIPT_WIRE_SCHEMA_AND_VALIDATION.md.
"""
from __future__ import annotations

import hashlib
from typing import Optional
from pydantic import BaseModel


class SignedWormDurableReceipt(BaseModel):
    receipt_schema: str = "keelway.worm-durable-receipt.v1"
    realm_id: str
    replica_id: str  # Must be "A" or "B"
    custodian_principal_id: str
    storage_device_or_account_id: str
    object_key: str
    base_final_sha256: str
    object_size_bytes: int
    object_generation_or_version: str
    immutable_retention_policy_digest: str
    retention_until_utc: str
    write_operation_id: str
    write_committed_at: str
    readback_sha256: str
    durability_claim: str = "DURABLE_IMMUTABLE_AFTER_READBACK"
    signer_cert_fingerprint: str
    signature: str
    is_physical_hardware: bool = False  # Must be True for production FINAL


class DualWormValidationResult(BaseModel):
    is_valid: bool
    status_code: str
    error_message: Optional[str] = None
    publication_cert: Optional[str] = None
    receipt_a_digest: Optional[str] = None
    receipt_b_digest: Optional[str] = None
    hardware_qualified: bool = False


class DualWormReceiptValidator:
    """Validates two independent hardware WORM durable readback receipts before witness FINAL."""

    @staticmethod
    def compute_receipt_digest(receipt: SignedWormDurableReceipt) -> str:
        """Deterministic canonical digest of a signed WORM receipt."""
        dumped = receipt.model_dump_json()
        return hashlib.sha256(dumped.encode("utf-8")).hexdigest()

    def validate_dual_receipts(
        self,
        base_final_sha256: str,
        receipt_a: SignedWormDurableReceipt,
        receipt_b: SignedWormDurableReceipt,
        require_physical_hardware: bool = True,
    ) -> DualWormValidationResult:
        """Strict deterministic validation per ADR-075/ADR-076 specification."""
        # 1. Distinct replicas check
        if receipt_a.replica_id == receipt_b.replica_id:
            return DualWormValidationResult(
                is_valid=False,
                status_code="ERR_WORM_DUPLICATE_REPLICA_ID",
                error_message=f"Both receipts report replica '{receipt_a.replica_id}'; independent A/B required",
            )

        # 2. Distinct signing key fingerprints (independent custody failure domains)
        if receipt_a.signer_cert_fingerprint == receipt_b.signer_cert_fingerprint:
            return DualWormValidationResult(
                is_valid=False,
                status_code="ERR_WORM_SHARED_SIGNER_KEY",
                error_message="Replicas A and B must not share the same signing key or certificate fingerprint",
            )

        # 3. Base digest and readback equality
        if receipt_a.base_final_sha256 != base_final_sha256 or receipt_b.base_final_sha256 != base_final_sha256:
            return DualWormValidationResult(
                is_valid=False,
                status_code="ERR_WORM_BASE_DIGEST_MISMATCH",
                error_message="Receipt base digests do not match the expected canonical base object SHA-256",
            )

        if receipt_a.readback_sha256 != base_final_sha256 or receipt_b.readback_sha256 != base_final_sha256:
            return DualWormValidationResult(
                is_valid=False,
                status_code="ERR_WORM_READBACK_DIGEST_MISMATCH",
                error_message="Durable readback digest differs from base object digest; data corruption detected",
            )

        # 4. Strict durability claim check (never allow buffered write or ACCEPTED_FOR_UPLOAD)
        if (
            receipt_a.durability_claim != "DURABLE_IMMUTABLE_AFTER_READBACK"
            or receipt_b.durability_claim != "DURABLE_IMMUTABLE_AFTER_READBACK"
        ):
            return DualWormValidationResult(
                is_valid=False,
                status_code="ERR_WORM_INSUFFICIENT_DURABILITY_CLAIM",
                error_message="Durability claim must be DURABLE_IMMUTABLE_AFTER_READBACK; buffered writes prohibited",
            )

        # 5. Check physical hardware vs emulator qualification
        is_hardware = receipt_a.is_physical_hardware and receipt_b.is_physical_hardware
        if require_physical_hardware and not is_hardware:
            return DualWormValidationResult(
                is_valid=False,
                status_code="ERR_WORM_UNQUALIFIED_EMULATOR_PROHIBITED_IN_PROD",
                error_message="Production FINAL requires live qualified physical WORM appliances (ADR-076); emulator rejected",
                hardware_qualified=False,
            )

        # 6. Generate canonical witness Publication Certificate:
        # PUBLICATION_CERT = H('keelway.final.v63' || base_digest || receipt_A_digest || receipt_B_digest)
        digest_a = self.compute_receipt_digest(receipt_a)
        digest_b = self.compute_receipt_digest(receipt_b)
        cert_preimage = f"keelway.final.v63:{base_final_sha256}:{digest_a}:{digest_b}"
        pub_cert = hashlib.sha256(cert_preimage.encode("utf-8")).hexdigest()

        return DualWormValidationResult(
            is_valid=True,
            status_code="INFO_WORM_DUAL_RECEIPTS_VERIFIED",
            publication_cert=pub_cert,
            receipt_a_digest=digest_a,
            receipt_b_digest=digest_b,
            hardware_qualified=is_hardware,
        )
