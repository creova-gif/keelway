"""Tests for Tier 2 TPM 2.0 Quote Verifier, Event-Log Replay & Monotonic NV Counter.
Implements ADR-061, ADR-062, ADR-064, and Document 309 normative attestation algorithms.
"""
import hashlib
import hmac
import pytest
from keelway.hal.tpm import (
    TPMEventLogEntry,
    TPMQuotePayload,
    TPMQuoteVerifier,
)


def _compute_expected_pcr(event_log, pcr_index):
    current = "0" * 64
    for entry in event_log:
        if entry.pcr_index == pcr_index:
            preimage = bytes.fromhex(current) + bytes.fromhex(entry.digest_sha256)
            current = hashlib.sha256(preimage).hexdigest()
    return current


def _build_valid_quote(verifier, nonce, ak_key=b"customer_enrolled_tpm_ak_secret_key"):
    event_log = [
        TPMEventLogEntry(
            pcr_index=0,
            event_type="EV_S_CRTM_VERSION",
            digest_sha256="aa" * 32,
            event_description="Core Root of Trust for Measurement firmware",
        ),
        TPMEventLogEntry(
            pcr_index=0,
            event_type="EV_POST_CODE",
            digest_sha256="bb" * 32,
            event_description="Secure Bootloader Stage 1",
        ),
        TPMEventLogEntry(
            pcr_index=7,
            event_type="EV_EFI_VARIABLE_DRIVER_CONFIG",
            digest_sha256="cc" * 32,
            event_description="Secure Boot Keys & Policy",
        ),
    ]

    pcr_0 = _compute_expected_pcr(event_log, 0)
    pcr_7 = _compute_expected_pcr(event_log, 7)

    # Replayed digest for sorted pcr_selection [0, 7]
    concat = pcr_0 + pcr_7
    quoted_pcr_digest = hashlib.sha256(concat.encode("utf-8")).hexdigest()

    station_id = "station-node-west-01"
    ak_id = "ak-cert-rsa2048-cust"

    msg = f"{station_id}:{ak_id}:{nonce}:{quoted_pcr_digest}"
    sig = hmac.new(ak_key, msg.encode("utf-8"), hashlib.sha256).hexdigest()

    quote = TPMQuotePayload(
        station_id=station_id,
        attestation_key_id=ak_id,
        nonce=nonce,
        pcr_selection=[0, 7],
        quoted_pcr_digest=quoted_pcr_digest,
        event_log=event_log,
        signature=sig,
    )
    return quote, pcr_0, pcr_7


def test_tpm_quote_positive_verification():
    ak_key = b"customer_enrolled_tpm_ak_secret_key"
    temp_verifier = TPMQuoteVerifier(customer_golden_boot_profile={}, active_ak_key=ak_key)
    nonce = temp_verifier.generate_attestation_nonce()
    quote, pcr_0, pcr_7 = _build_valid_quote(temp_verifier, nonce, ak_key)

    golden_profile = {0: pcr_0, 7: pcr_7}
    verifier = TPMQuoteVerifier(customer_golden_boot_profile=golden_profile, active_ak_key=ak_key)

    res = verifier.verify_quote(quote, expected_nonce=nonce)
    assert res.is_valid is True
    assert res.status_code == "INFO_TPM_QUOTE_VERIFIED_GOLDEN_MATCH"
    assert res.golden_profile_matched is True
    assert res.recomputed_pcr_digest == quote.quoted_pcr_digest


def test_tpm_nonce_anti_replay_enforcement():
    ak_key = b"customer_enrolled_tpm_ak_secret_key"
    verifier = TPMQuoteVerifier(customer_golden_boot_profile={}, active_ak_key=ak_key)
    nonce = verifier.generate_attestation_nonce()
    quote, _, _ = _build_valid_quote(verifier, nonce, ak_key)

    # 1. Nonce mismatch
    res_mismatch = verifier.verify_quote(quote, expected_nonce="wrong-nonce-value")
    assert res_mismatch.is_valid is False
    assert res_mismatch.status_code == "ERR_TPM_NONCE_MISMATCH"

    # 2. First verification consumes nonce
    verifier.customer_golden_boot_profile = {}
    res_valid = verifier.verify_quote(quote, expected_nonce=nonce)
    assert res_valid.is_valid is True

    # 3. Second verification fails due to nonce reuse (anti-replay)
    res_replayed = verifier.verify_quote(quote, expected_nonce=nonce)
    assert res_replayed.is_valid is False
    assert res_replayed.status_code == "ERR_TPM_NONCE_REPLAYED"


def test_tpm_invalid_ak_signature_rejected():
    ak_key = b"customer_enrolled_tpm_ak_secret_key"
    verifier = TPMQuoteVerifier(customer_golden_boot_profile={}, active_ak_key=ak_key)
    nonce = verifier.generate_attestation_nonce()
    quote, _, _ = _build_valid_quote(verifier, nonce, ak_key)

    tampered_quote = quote.model_copy(update={"signature": "forged_ak_signature_hex"})
    res = verifier.verify_quote(tampered_quote, expected_nonce=nonce)
    assert res.is_valid is False
    assert res.status_code == "ERR_TPM_INVALID_AK_SIGNATURE"


def test_tpm_event_log_tampering_detected():
    ak_key = b"customer_enrolled_tpm_ak_secret_key"
    verifier = TPMQuoteVerifier(customer_golden_boot_profile={}, active_ak_key=ak_key)
    nonce = verifier.generate_attestation_nonce()
    quote, _, _ = _build_valid_quote(verifier, nonce, ak_key)

    # Attacker injected an extra event into the log without hardware quote matching
    tampered_log = list(quote.event_log) + [
        TPMEventLogEntry(
            pcr_index=0,
            event_type="EV_ACTION",
            digest_sha256="99" * 32,
            event_description="Injected untrusted binary",
        )
    ]
    tampered_quote = quote.model_copy(update={"event_log": tampered_log})

    res = verifier.verify_quote(tampered_quote, expected_nonce=nonce)
    assert res.is_valid is False
    assert res.status_code == "ERR_TPM_EVENT_LOG_REPLAY_MISMATCH"


def test_tpm_golden_boot_profile_mismatch_detected():
    ak_key = b"customer_enrolled_tpm_ak_secret_key"
    verifier = TPMQuoteVerifier(customer_golden_boot_profile={}, active_ak_key=ak_key)
    nonce = verifier.generate_attestation_nonce()
    quote, pcr_0, _ = _build_valid_quote(verifier, nonce, ak_key)

    # Golden profile expects a different PCR 0 (e.g. different firmware hash)
    verifier.customer_golden_boot_profile = {0: "wrong_golden_firmware_sha256"}

    res = verifier.verify_quote(quote, expected_nonce=nonce)
    assert res.is_valid is False
    assert res.status_code == "ERR_TPM_GOLDEN_BOOT_MISMATCH"
    assert res.golden_profile_matched is False


def test_tpm_monotonic_nv_counter_rollback_prevention():
    verifier = TPMQuoteVerifier(customer_golden_boot_profile={})
    assert verifier.monotonic_counter_floor == 0

    # Advance counter monotonically
    assert verifier.advance_monotonic_nv_counter(10) is True
    assert verifier.monotonic_counter_floor == 10

    assert verifier.advance_monotonic_nv_counter(25) is True
    assert verifier.monotonic_counter_floor == 25

    # Replaying same value must fail
    assert verifier.advance_monotonic_nv_counter(25) is False

    # Attempting rollback to older state must fail
    assert verifier.advance_monotonic_nv_counter(15) is False
    assert verifier.advance_monotonic_nv_counter(1) is False
    assert verifier.monotonic_counter_floor == 25
