"""Tests for Tier 2 PIV/PKI Smartcard Verifier and Strict 72-Hour CRL Engine.
Implements ADR-051 and ADR-053: Hardware-held PIV signature verification
and strict 72-hour maximum CRL staleness cap from thisUpdate.
"""
import datetime
from keelway.hal.piv import (
    MAX_CRL_AGE_SECONDS,
    PIVCertificate,
    PIVSmartcardVerifier,
    SignedCRL,
)


def _base_datetime():
    return datetime.datetime(2026, 11, 3, 12, 0, 0, tzinfo=datetime.timezone.utc)


def test_piv_positive_verification():
    now = _base_datetime()
    verifier = PIVSmartcardVerifier()

    cert = PIVCertificate(
        serial_number="CERT_SN_9001",
        subject_dn="CN=Cust Security Custodian 1, OU=Security, O=Customer Corp",
        issuer_dn=verifier.trusted_issuer_dn,
        not_before=(now - datetime.timedelta(days=30)).isoformat(),
        not_after=(now + datetime.timedelta(days=365)).isoformat(),
        hardware_held=True,
        public_key_fingerprint="sha256:fingerprint_key_piv_9001",
    )

    crl = SignedCRL(
        issuer_dn=verifier.trusted_issuer_dn,
        this_update=(now - datetime.timedelta(hours=24)).isoformat(),  # 24 hours old (< 72h cap)
        next_update=(now + datetime.timedelta(hours=48)).isoformat(),
        revoked_serials={"CERT_SN_9999", "CERT_SN_8888"},
        crl_signature="crl_sig_valid",
    )

    res = verifier.verify_piv_certificate_and_signature(
        cert=cert,
        crl=crl,
        signed_data=b"custodian_recovery_payload_01",
        signature="sig_piv_custodian_01",
        trusted_now=now,
    )

    assert res.is_valid is True
    assert res.status_code == "INFO_PIV_CREDENTIAL_VERIFIED"
    assert res.crl_age_seconds == 24 * 3600


def test_piv_strict_72_hour_crl_staleness_rejection():
    """ADR-053: CRLs strictly older than 72 hours from thisUpdate must be rejected,
    regardless of nextUpdate.
    """
    now = _base_datetime()
    verifier = PIVSmartcardVerifier()

    cert = PIVCertificate(
        serial_number="CERT_SN_9001",
        subject_dn="CN=Cust Security Custodian 1",
        issuer_dn=verifier.trusted_issuer_dn,
        not_before=(now - datetime.timedelta(days=30)).isoformat(),
        not_after=(now + datetime.timedelta(days=365)).isoformat(),
        hardware_held=True,
        public_key_fingerprint="sha256:key_9001",
    )

    # Stale CRL: issued 72 hours and 5 minutes ago, even if CA set next_update 7 days ahead
    stale_crl = SignedCRL(
        issuer_dn=verifier.trusted_issuer_dn,
        this_update=(now - datetime.timedelta(hours=72, minutes=5)).isoformat(),
        next_update=(now + datetime.timedelta(days=7)).isoformat(),  # Future next_update does NOT bypass 72h limit
        revoked_serials=set(),
        crl_signature="crl_sig",
    )

    res = verifier.verify_piv_certificate_and_signature(
        cert=cert, crl=stale_crl, signed_data=b"data", signature="sig", trusted_now=now
    )

    assert res.is_valid is False
    assert "ERR_CRL_STALE_EXCEEDS_72_HOURS" in res.status_code
    assert res.crl_age_seconds > MAX_CRL_AGE_SECONDS


def test_piv_expired_crl_past_next_update_rejected():
    now = _base_datetime()
    verifier = PIVSmartcardVerifier()

    cert = PIVCertificate(
        serial_number="CERT_SN_9001",
        subject_dn="CN=Cust Security Custodian 1",
        issuer_dn=verifier.trusted_issuer_dn,
        not_before=(now - datetime.timedelta(days=30)).isoformat(),
        not_after=(now + datetime.timedelta(days=365)).isoformat(),
        hardware_held=True,
        public_key_fingerprint="sha256:key_9001",
    )

    # CRL issued 10h ago, but next_update was 1h ago
    expired_crl = SignedCRL(
        issuer_dn=verifier.trusted_issuer_dn,
        this_update=(now - datetime.timedelta(hours=10)).isoformat(),
        next_update=(now - datetime.timedelta(hours=1)).isoformat(),
        revoked_serials=set(),
        crl_signature="crl_sig",
    )

    res = verifier.verify_piv_certificate_and_signature(
        cert=cert, crl=expired_crl, signed_data=b"data", signature="sig", trusted_now=now
    )

    assert res.is_valid is False
    assert "ERR_CRL_EXPIRED" in res.status_code


def test_piv_revoked_serial_rejected():
    now = _base_datetime()
    verifier = PIVSmartcardVerifier()

    revoked_cert = PIVCertificate(
        serial_number="CERT_REVOKED_404",
        subject_dn="CN=Compromised Custodian",
        issuer_dn=verifier.trusted_issuer_dn,
        not_before=(now - datetime.timedelta(days=10)).isoformat(),
        not_after=(now + datetime.timedelta(days=100)).isoformat(),
        hardware_held=True,
        public_key_fingerprint="sha256:compromised_key",
    )

    fresh_crl = SignedCRL(
        issuer_dn=verifier.trusted_issuer_dn,
        this_update=(now - datetime.timedelta(hours=2)).isoformat(),
        next_update=(now + datetime.timedelta(hours=22)).isoformat(),
        revoked_serials={"CERT_REVOKED_404"},
        crl_signature="crl_sig",
    )

    res = verifier.verify_piv_certificate_and_signature(
        cert=revoked_cert, crl=fresh_crl, signed_data=b"data", signature="sig", trusted_now=now
    )

    assert res.is_valid is False
    assert res.status_code == "ERR_PIV_CERTIFICATE_REVOKED"


def test_piv_software_held_key_rejected():
    """ADR-051: Software-held private keys are strictly prohibited for PIV custody."""
    now = _base_datetime()
    verifier = PIVSmartcardVerifier()

    software_cert = PIVCertificate(
        serial_number="CERT_SN_SOFT_01",
        subject_dn="CN=Software File Key User",
        issuer_dn=verifier.trusted_issuer_dn,
        not_before=(now - datetime.timedelta(days=5)).isoformat(),
        not_after=(now + datetime.timedelta(days=30)).isoformat(),
        hardware_held=False,  # Software exportable key!
        public_key_fingerprint="sha256:soft_key",
    )

    crl = SignedCRL(
        issuer_dn=verifier.trusted_issuer_dn,
        this_update=(now - datetime.timedelta(hours=1)).isoformat(),
        next_update=(now + datetime.timedelta(hours=23)).isoformat(),
        revoked_serials=set(),
        crl_signature="crl_sig",
    )

    res = verifier.verify_piv_certificate_and_signature(
        cert=software_cert, crl=crl, signed_data=b"data", signature="sig", trusted_now=now
    )

    assert res.is_valid is False
    assert res.status_code == "ERR_PIV_SOFTWARE_KEY_PROHIBITED"


def test_piv_untrusted_issuer_rejected():
    now = _base_datetime()
    verifier = PIVSmartcardVerifier(trusted_issuer_dn="CN=Customer Trusted CA")

    rogue_cert = PIVCertificate(
        serial_number="CERT_SN_ROGUE",
        subject_dn="CN=Rogue User",
        issuer_dn="CN=Untrusted External CA",  # Untrusted!
        not_before=(now - datetime.timedelta(days=1)).isoformat(),
        not_after=(now + datetime.timedelta(days=30)).isoformat(),
        hardware_held=True,
        public_key_fingerprint="sha256:rogue",
    )

    crl = SignedCRL(
        issuer_dn="CN=Untrusted External CA",
        this_update=(now - datetime.timedelta(hours=1)).isoformat(),
        next_update=(now + datetime.timedelta(hours=23)).isoformat(),
        revoked_serials=set(),
        crl_signature="crl_sig",
    )

    res = verifier.verify_piv_certificate_and_signature(
        cert=rogue_cert, crl=crl, signed_data=b"data", signature="sig", trusted_now=now
    )

    assert res.is_valid is False
    assert res.status_code == "ERR_PIV_UNTRUSTED_ISSUER"
