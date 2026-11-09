"""Ed25519 licences: only the private key can issue them, the public key checks them offline."""

import base64
import json
import stat
import time

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import cli
from core.billing import entitlements as ent
from core.billing.entitlements import (
    EnterpriseFeature, EntitlementCertificate, EntitlementManager, LicenseTier, public_key_text,
)

SIGNER = Ed25519PrivateKey.generate()
TRUSTED = {"sorvex-1": public_key_text(SIGNER)}


def _cert(**kw):
    now = time.time()
    data = dict(org_id="acme", org_name="Acme", tier=LicenseTier.ENTERPRISE, seats=3,
                allowed_features=["two_human_quorum"], issued_at=now - 5, expires_at=now + 3600)
    data.update(kw)
    return EntitlementCertificate(**data)


def test_signed_licence_round_trips_through_json():
    cert = _cert()
    cert.sign(SIGNER, "sorvex-1")
    again = EntitlementCertificate.from_dict(json.loads(json.dumps(cert.to_dict())))
    assert again.is_valid(TRUSTED) == (True, "ACTIVE")


def test_any_field_change_breaks_the_signature():
    cert = _cert()
    cert.sign(SIGNER, "sorvex-1")
    for field, value in [("seats", 300), ("tier", LicenseTier.PRO), ("expires_at", cert.expires_at + 1e9),
                         ("allowed_features", ["two_human_quorum", "p2p_mesh"]), ("org_id", "other")]:
        forged = EntitlementCertificate.from_dict(cert.to_dict())
        setattr(forged, field, value)
        assert forged.is_valid(TRUSTED) == (False, "INVALID_SIGNATURE"), field


def test_licence_from_another_key_is_refused():
    cert = _cert()
    cert.sign(Ed25519PrivateKey.generate(), "sorvex-1")
    assert cert.is_valid(TRUSTED) == (False, "INVALID_SIGNATURE")
    cert.sign(Ed25519PrivateKey.generate(), "mine")
    assert cert.is_valid(TRUSTED) == (False, "UNKNOWN_SIGNING_KEY")


def test_old_hmac_style_licence_is_refused():
    cert = _cert(signature="ab" * 32)
    assert cert.is_valid(TRUSTED)[0] is False
    cert.key_id = "sorvex-1"
    cert.signature = "not base64 !!"
    assert cert.is_valid(TRUSTED) == (False, "INVALID_SIGNATURE")


def test_verifier_holds_no_signing_material():
    raw = base64.urlsafe_b64decode(TRUSTED["sorvex-1"] + "=")
    assert len(raw) == 32
    assert ent.TRUSTED_LICENCE_KEYS == {}


def test_community_fallback_works_once_a_key_is_trusted(tmp_path):
    mgr = EntitlementManager(storage_path=tmp_path / "e.json", trusted_keys=TRUSTED)
    assert mgr.status("nobody")[1:] == (True, "COMMUNITY")
    assert mgr.check_feature_access("nobody", EnterpriseFeature.LOCAL_AGENT_LOOP) == (True, "GRANTED")
    assert mgr.check_feature_access("nobody", EnterpriseFeature.TWO_HUMAN_QUORUM)[0] is False


def _run(argv):
    with pytest.raises(SystemExit) as exc:
        cli.main(argv)
    return exc.value.code


def test_cli_keygen_issue_install(tmp_path, monkeypatch, capsys):
    key = tmp_path / "signing.pem"
    assert _run(["entitlements", "keygen", "--out", str(key)]) == 0
    assert stat.S_IMODE(key.stat().st_mode) == 0o600
    public = capsys.readouterr().out.split('"sorvex-1": "')[1].split('"')[0]
    assert _run(["entitlements", "keygen", "--out", str(key)]) == 1

    lic = tmp_path / "acme.json"
    assert _run(["entitlements", "issue", "--key", str(key), "--org", "acme", "--tier", "pro",
                 "--seats", "4", "--days", "30", "--out", str(lic)]) == 0
    assert "PRIVATE KEY" not in lic.read_text()

    monkeypatch.setattr(ent, "_GLOBAL_ENTITLEMENT_MANAGER", EntitlementManager(storage_path=tmp_path / "e.json"))
    assert _run(["entitlements", "install", str(lic)]) == 1
    assert "no trusted licence signing key" in capsys.readouterr().out

    mgr = EntitlementManager(storage_path=tmp_path / "e.json", trusted_keys={"sorvex-1": public})
    monkeypatch.setattr(ent, "_GLOBAL_ENTITLEMENT_MANAGER", mgr)
    assert _run(["entitlements", "install", str(lic)]) == 0
    assert mgr.check_feature_access("acme", EnterpriseFeature.P2P_MESH) == (True, "GRANTED")
    assert mgr.active_certificates["acme"].seats == 4
