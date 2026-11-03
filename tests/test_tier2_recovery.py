"""Tests for Tier 2 Customer-Owned 2-of-3 Offline Root Recovery Protocol (ADR-082 / ADR-083).
Validates 2-of-3 quorum verification, role separation (Security Lead + Platform Owner),
forward-only epoch progression, anti-replay nonces, and DENY_OLD before ENABLE_NEW state machines.
"""
import pytest
from keelway.hal.recovery import (
    CustodianSignature,
    OfflineRootRecoveryVerifier,
    RecoveryEnvelopeV1,
    RecoveryPlanV1,
)


@pytest.fixture
def sample_roster():
    return {
        "A": {
            "custodian_id": "alice_sec_custodian",
            "key_spki": "sha256:custodian_key_a_piv9a",
            "assigned_role": "Security Lead",
        },
        "B": {
            "custodian_id": "bob_platform_custodian",
            "key_spki": "sha256:custodian_key_b_piv9a",
            "assigned_role": "Platform Owner",
        },
        "C": {
            "custodian_id": "carol_alt_custodian",
            "key_spki": "sha256:custodian_key_c_piv9a",
            "assigned_role": "Platform Owner",
        },
    }


def _build_valid_envelope(plan, sig_a=True, sig_b=True, sig_c=False):
    signatures = []
    if sig_a:
        signatures.append(
            CustodianSignature(
                signer_slot="A",
                custodian_id="alice_sec_custodian",
                signer_key_spki_sha256="sha256:custodian_key_a_piv9a",
                role="Security Lead",
                hardware_held=True,
                signature="sig_piv_hardware_a",
            )
        )
    if sig_b:
        signatures.append(
            CustodianSignature(
                signer_slot="B",
                custodian_id="bob_platform_custodian",
                signer_key_spki_sha256="sha256:custodian_key_b_piv9a",
                role="Platform Owner",
                hardware_held=True,
                signature="sig_piv_hardware_b",
            )
        )
    if sig_c:
        signatures.append(
            CustodianSignature(
                signer_slot="C",
                custodian_id="carol_alt_custodian",
                signer_key_spki_sha256="sha256:custodian_key_c_piv9a",
                role="Platform Owner",
                hardware_held=True,
                signature="sig_piv_hardware_c",
            )
        )

    digest = plan.compute_canonical_digest()
    return RecoveryEnvelopeV1(
        plan=plan,
        plan_digest=digest,
        signatures=signatures,
        deny_old_proof="sha256:signed_deny_watermark_epoch_1",
    )


def test_positive_2_of_3_recovery_execution(sample_roster):
    verifier = OfflineRootRecoveryVerifier(
        realm_id="realm_cust_corp_01",
        enrolled_custodians=sample_roster,
        initial_recovery_epoch=1,
        initial_root_spki_sha256="sha256:root_gen_1",
    )

    plan = RecoveryPlanV1(
        realm_id="realm_cust_corp_01",
        operation_id="op_challenge_ceremony_901",
        old_root_spki_sha256="sha256:root_gen_1",
        next_root_spki_sha256="sha256:root_gen_2_hardware_cutover",
        old_generation=1,
        new_generation=2,
        witness_floor=100,
        affected_ca_issuers=["CN=Customer Issuing CA 1"],
    )

    # Custodians A (Security Lead) + B (Platform Owner) sign
    envelope = _build_valid_envelope(plan, sig_a=True, sig_b=True, sig_c=False)

    res = verifier.verify_recovery_envelope(envelope)
    assert res.is_valid is True
    assert res.status_code == "INFO_RECOVERY_2OF3_COMMITTED_DENY_OLD_BEFORE_ENABLE_NEW"
    assert res.new_root_enabled is True
    assert res.old_root_denied is True
    assert "sha256:root_gen_1" in verifier.denied_roots
    assert verifier.active_root_spki_sha256 == "sha256:root_gen_2_hardware_cutover"
    assert verifier.current_recovery_epoch == 2
    assert res.enforced_ack_digest is not None


def test_alternative_custodian_combination_a_and_c(sample_roster):
    """Custodians A (Security Lead) + C (Platform Owner) satisfy the 2-of-3 threshold."""
    verifier = OfflineRootRecoveryVerifier(
        realm_id="realm_cust_corp_01",
        enrolled_custodians=sample_roster,
        initial_recovery_epoch=1,
        initial_root_spki_sha256="sha256:root_gen_1",
    )

    plan = RecoveryPlanV1(
        realm_id="realm_cust_corp_01",
        operation_id="op_challenge_ceremony_902",
        old_root_spki_sha256="sha256:root_gen_1",
        next_root_spki_sha256="sha256:root_gen_2",
        old_generation=1,
        new_generation=2,
        witness_floor=100,
    )

    envelope = _build_valid_envelope(plan, sig_a=True, sig_b=False, sig_c=True)
    res = verifier.verify_recovery_envelope(envelope)
    assert res.is_valid is True
    assert res.new_root_enabled is True


def test_rejection_of_duplicate_custodian_signature(sample_roster):
    """One person / key cannot sign twice to manufacture a 2-of-3 quorum."""
    verifier = OfflineRootRecoveryVerifier(
        realm_id="realm_cust_corp_01",
        enrolled_custodians=sample_roster,
        initial_recovery_epoch=1,
        initial_root_spki_sha256="sha256:root_gen_1",
    )

    plan = RecoveryPlanV1(
        realm_id="realm_cust_corp_01",
        operation_id="op_challenge_ceremony_903",
        old_root_spki_sha256="sha256:root_gen_1",
        next_root_spki_sha256="sha256:root_gen_2",
        old_generation=1,
        new_generation=2,
        witness_floor=100,
    )

    # Custodian A signs twice
    sig_a = CustodianSignature(
        signer_slot="A",
        custodian_id="alice_sec_custodian",
        signer_key_spki_sha256="sha256:custodian_key_a_piv9a",
        role="Security Lead",
        hardware_held=True,
        signature="sig_1",
    )
    sig_a_dup = sig_a.model_copy()

    envelope = RecoveryEnvelopeV1(
        plan=plan,
        plan_digest=plan.compute_canonical_digest(),
        signatures=[sig_a, sig_a_dup],
        deny_old_proof="proof",
    )

    res = verifier.verify_recovery_envelope(envelope)
    assert res.is_valid is False
    assert res.status_code == "ERR_RECOVERY_DUPLICATE_CUSTODIAN"


def test_rejection_of_missing_mandatory_role(sample_roster):
    """Custodians B and C sign, but both are Platform Owners (missing Security Lead)."""
    verifier = OfflineRootRecoveryVerifier(
        realm_id="realm_cust_corp_01",
        enrolled_custodians=sample_roster,
        initial_recovery_epoch=1,
        initial_root_spki_sha256="sha256:root_gen_1",
    )

    plan = RecoveryPlanV1(
        realm_id="realm_cust_corp_01",
        operation_id="op_challenge_ceremony_904",
        old_root_spki_sha256="sha256:root_gen_1",
        next_root_spki_sha256="sha256:root_gen_2",
        old_generation=1,
        new_generation=2,
        witness_floor=100,
    )

    envelope = _build_valid_envelope(plan, sig_a=False, sig_b=True, sig_c=True)
    res = verifier.verify_recovery_envelope(envelope)
    assert res.is_valid is False
    assert res.status_code == "ERR_RECOVERY_MISSING_MANDATORY_ROLE"


def test_rejection_of_software_held_key(sample_roster):
    """ADR-083: Software keys are strictly prohibited for root recovery."""
    verifier = OfflineRootRecoveryVerifier(
        realm_id="realm_cust_corp_01",
        enrolled_custodians=sample_roster,
        initial_recovery_epoch=1,
        initial_root_spki_sha256="sha256:root_gen_1",
    )

    plan = RecoveryPlanV1(
        realm_id="realm_cust_corp_01",
        operation_id="op_challenge_ceremony_905",
        old_root_spki_sha256="sha256:root_gen_1",
        next_root_spki_sha256="sha256:root_gen_2",
        old_generation=1,
        new_generation=2,
        witness_floor=100,
    )

    envelope = _build_valid_envelope(plan, sig_a=True, sig_b=True)
    # Tamper signature B to software-held
    envelope.signatures[1] = envelope.signatures[1].model_copy(update={"hardware_held": False})

    res = verifier.verify_recovery_envelope(envelope)
    assert res.is_valid is False
    assert res.status_code == "ERR_RECOVERY_SOFTWARE_KEY_PROHIBITED"


def test_rejection_of_epoch_rollback(sample_roster):
    verifier = OfflineRootRecoveryVerifier(
        realm_id="realm_cust_corp_01",
        enrolled_custodians=sample_roster,
        initial_recovery_epoch=5,
        initial_root_spki_sha256="sha256:root_gen_5",
    )

    # Attempting to replay an older generation 4
    plan = RecoveryPlanV1(
        realm_id="realm_cust_corp_01",
        operation_id="op_challenge_ceremony_906",
        old_root_spki_sha256="sha256:root_gen_5",
        next_root_spki_sha256="sha256:root_gen_6",
        old_generation=4,  # Stale!
        new_generation=5,
        witness_floor=100,
    )

    envelope = _build_valid_envelope(plan, sig_a=True, sig_b=True)
    res = verifier.verify_recovery_envelope(envelope)
    assert res.is_valid is False
    assert res.status_code == "ERR_RECOVERY_STALE_OLD_GENERATION"


def test_rejection_of_nonce_replay(sample_roster):
    verifier = OfflineRootRecoveryVerifier(
        realm_id="realm_cust_corp_01",
        enrolled_custodians=sample_roster,
        initial_recovery_epoch=1,
        initial_root_spki_sha256="sha256:root_gen_1",
    )

    plan = RecoveryPlanV1(
        realm_id="realm_cust_corp_01",
        operation_id="replayed_op_100",
        old_root_spki_sha256="sha256:root_gen_1",
        next_root_spki_sha256="sha256:root_gen_2",
        old_generation=1,
        new_generation=2,
        witness_floor=100,
    )

    envelope = _build_valid_envelope(plan, sig_a=True, sig_b=True)

    # First attempt succeeds
    res1 = verifier.verify_recovery_envelope(envelope)
    assert res1.is_valid is True

    # Replay attempt fails closed
    res2 = verifier.verify_recovery_envelope(envelope)
    assert res2.is_valid is False
    assert res2.status_code == "ERR_RECOVERY_NONCE_REPLAYED"
