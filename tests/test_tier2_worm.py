"""Tests for Tier 2 Hardware WORM Storage Protocol & Dual-Receipt Validator (ADR-076).
Validates dual-receipt verification, publication cert generation, and emulator rejection.
"""
from keelway.hal.worm import DualWormReceiptValidator, SignedWormDurableReceipt


def test_dual_worm_positive_verification_and_publication_cert():
    validator = DualWormReceiptValidator()
    base_sha = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

    receipt_a = SignedWormDurableReceipt(
        realm_id="realm_prod_cust_01",
        replica_id="A",
        custodian_principal_id="custodian_site_east",
        storage_device_or_account_id="worm_device_serial_1001",
        object_key="checkpoints/run_01_final.cbor",
        base_final_sha256=base_sha,
        object_size_bytes=1024,
        object_generation_or_version="gen_a1",
        immutable_retention_policy_digest="sha256:policy_7yr",
        retention_until_utc="2033-11-03T00:00:00Z",
        write_operation_id="op_uuid_101",
        write_committed_at="2026-11-03T18:00:00Z",
        readback_sha256=base_sha,
        durability_claim="DURABLE_IMMUTABLE_AFTER_READBACK",
        signer_cert_fingerprint="fingerprint_key_a_site_east",
        signature="sig_a",
        is_physical_hardware=True,
    )

    receipt_b = SignedWormDurableReceipt(
        realm_id="realm_prod_cust_01",
        replica_id="B",
        custodian_principal_id="custodian_site_west",
        storage_device_or_account_id="worm_device_serial_2002",
        object_key="checkpoints/run_01_final.cbor",
        base_final_sha256=base_sha,
        object_size_bytes=1024,
        object_generation_or_version="gen_b1",
        immutable_retention_policy_digest="sha256:policy_7yr",
        retention_until_utc="2033-11-03T00:00:00Z",
        write_operation_id="op_uuid_101",
        write_committed_at="2026-11-03T18:00:00Z",
        readback_sha256=base_sha,
        durability_claim="DURABLE_IMMUTABLE_AFTER_READBACK",
        signer_cert_fingerprint="fingerprint_key_b_site_west",
        signature="sig_b",
        is_physical_hardware=True,
    )

    res = validator.validate_dual_receipts(base_sha, receipt_a, receipt_b, require_physical_hardware=True)
    assert res.is_valid is True
    assert res.status_code == "INFO_WORM_DUAL_RECEIPTS_VERIFIED"
    assert res.publication_cert is not None
    assert len(res.publication_cert) == 64
    assert res.hardware_qualified is True


def test_dual_worm_rejects_duplicate_replica_or_shared_signer():
    validator = DualWormReceiptValidator()
    base_sha = "sha256:base"

    # Both report replica A
    rec_a1 = SignedWormDurableReceipt(
        realm_id="r", replica_id="A", custodian_principal_id="c1", storage_device_or_account_id="d1",
        object_key="k", base_final_sha256=base_sha, object_size_bytes=100, object_generation_or_version="v1",
        immutable_retention_policy_digest="p", retention_until_utc="2033", write_operation_id="o",
        write_committed_at="2026", readback_sha256=base_sha, signer_cert_fingerprint="k1", signature="s",
        is_physical_hardware=True
    )
    rec_a2 = rec_a1.model_copy(update={"storage_device_or_account_id": "d2", "signer_cert_fingerprint": "k2"})

    res = validator.validate_dual_receipts(base_sha, rec_a1, rec_a2)
    assert res.is_valid is False
    assert res.status_code == "ERR_WORM_DUPLICATE_REPLICA_ID"


def test_dual_worm_rejects_emulator_in_production():
    validator = DualWormReceiptValidator()
    base_sha = "sha256:base"

    rec_a = SignedWormDurableReceipt(
        realm_id="r", replica_id="A", custodian_principal_id="c1", storage_device_or_account_id="emu1",
        object_key="k", base_final_sha256=base_sha, object_size_bytes=100, object_generation_or_version="v1",
        immutable_retention_policy_digest="p", retention_until_utc="2033", write_operation_id="o",
        write_committed_at="2026", readback_sha256=base_sha, signer_cert_fingerprint="k1", signature="s",
        is_physical_hardware=False  # Emulator!
    )
    rec_b = rec_a.model_copy(update={"replica_id": "B", "signer_cert_fingerprint": "k2", "is_physical_hardware": False})

    res = validator.validate_dual_receipts(base_sha, rec_a, rec_b, require_physical_hardware=True)
    assert res.is_valid is False
    assert res.status_code == "ERR_WORM_UNQUALIFIED_EMULATOR_PROHIBITED_IN_PROD"
