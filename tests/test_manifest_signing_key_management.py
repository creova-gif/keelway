"""KEEL-SEC-030 — managed first-party manifest signing key resolution.

Verifies that ``get_sorvex_first_party_keypair`` no longer hands out the
publicly derivable deterministic key unless ``KEELWAY_DEV_INSECURE_KEY=1`` is
set, and that managed key sources (env seed/PEM, key file) resolve correctly.
"""

from __future__ import annotations

import base64
import hashlib
import os
import stat

import pytest

from core.platform.marketplace import MarketplaceRegistry
from core.platform.signing import (
    SORVEX_FIRST_PARTY_KEY_ID,
    Ed25519ManifestSigner,
    FirstPartySigningKeyUnavailable,
    _seed_to_keypair,
    generate_publisher_keypair,
    get_sorvex_first_party_keypair,
)

_KEY_ENVS = (
    "KEELWAY_MANIFEST_SIGNING_KEY",
    "KEELWAY_MANIFEST_SIGNING_SEED",
    "KEELWAY_MANIFEST_KEY_FILE",
    "KEELWAY_STATE_DIR",
    "KEELWAY_DEV_INSECURE_KEY",
)


@pytest.fixture()
def clear_key_env(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    for name in _KEY_ENVS:
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


def test_fail_closed_without_managed_key(clear_key_env: pytest.MonkeyPatch) -> None:
    with pytest.raises(FirstPartySigningKeyUnavailable):
        get_sorvex_first_party_keypair()


def test_default_signer_has_no_trusted_keys_when_unconfigured(
    clear_key_env: pytest.MonkeyPatch,
) -> None:
    assert Ed25519ManifestSigner().list_trusted_keys() == {}


def test_env_seed_hex_resolves_and_signs(clear_key_env: pytest.MonkeyPatch) -> None:
    seed = hashlib.sha256(b"test-managed-seed").digest()
    clear_key_env.setenv("KEELWAY_MANIFEST_SIGNING_SEED", seed.hex())
    pem, pub = get_sorvex_first_party_keypair()
    expected_pem, expected_pub = _seed_to_keypair(seed)
    assert pub == expected_pub

    signer = Ed25519ManifestSigner(trusted_keys={SORVEX_FIRST_PARTY_KEY_ID: pub})
    manifest = {"id": "pkg-1", "kind": "agent_skill", "name": "T", "version": "1.0.0"}
    signed = signer.sign_manifest(manifest, pem, SORVEX_FIRST_PARTY_KEY_ID)
    ok, reason = signer.verify_manifest(signed)
    assert ok, reason


def test_env_seed_base64_and_pem_forms(clear_key_env: pytest.MonkeyPatch) -> None:
    seed = os.urandom(32)
    clear_key_env.setenv("KEELWAY_MANIFEST_SIGNING_SEED", base64.b64encode(seed).decode())
    _, pub_b64 = get_sorvex_first_party_keypair()
    assert pub_b64 == _seed_to_keypair(seed)[1]

    pem, pub_from_pem = generate_publisher_keypair()
    clear_key_env.setenv("KEELWAY_MANIFEST_SIGNING_KEY", pem.decode("utf-8"))
    clear_key_env.delenv("KEELWAY_MANIFEST_SIGNING_SEED")
    assert get_sorvex_first_party_keypair()[1] == pub_from_pem


def test_key_file_load_or_generate(clear_key_env: pytest.MonkeyPatch, tmp_path) -> None:
    key_file = tmp_path / "nested" / "manifest-signing.seed"
    clear_key_env.setenv("KEELWAY_MANIFEST_KEY_FILE", str(key_file))

    _, pub1 = get_sorvex_first_party_keypair()
    assert key_file.exists()
    mode = stat.S_IMODE(key_file.stat().st_mode)
    assert mode == 0o600

    _, pub2 = get_sorvex_first_party_keypair()
    assert pub1 == pub2


def test_state_dir_default_key_file(clear_key_env: pytest.MonkeyPatch, tmp_path) -> None:
    clear_key_env.setenv("KEELWAY_STATE_DIR", str(tmp_path))
    _, pub = get_sorvex_first_party_keypair()
    assert (tmp_path / "manifest-signing.seed").exists()
    assert pub


def test_dev_insecure_gate_restores_deterministic_key(clear_key_env: pytest.MonkeyPatch) -> None:
    clear_key_env.setenv("KEELWAY_DEV_INSECURE_KEY", "1")
    pem, pub = get_sorvex_first_party_keypair()
    legacy_seed = hashlib.sha256(
        b"keelway.manifest.sorvex-labs.first-party.ed25519.v1"
    ).digest()
    assert pub == _seed_to_keypair(legacy_seed)[1]
    assert pem


def test_marketplace_first_party_unsigned_when_unconfigured(
    clear_key_env: pytest.MonkeyPatch,
) -> None:
    registry = MarketplaceRegistry()
    first_party = registry.list_packages(publisher_tier="first_party")
    assert first_party, "expected curated first-party seed packages"
    for pkg in first_party:
        assert not pkg.get("ed25519_signature")
        assert not pkg.get("signer_key_id")
        ok, reason = Ed25519ManifestSigner().verify_manifest(pkg)
        assert not ok
        assert reason == "UNSIGNED_MANIFEST"


def test_marketplace_first_party_signed_with_managed_key(
    clear_key_env: pytest.MonkeyPatch, tmp_path
) -> None:
    clear_key_env.setenv("KEELWAY_MANIFEST_KEY_FILE", str(tmp_path / "signing.seed"))
    registry = MarketplaceRegistry()
    first_party = registry.list_packages(publisher_tier="first_party")
    assert first_party
    _, pub = get_sorvex_first_party_keypair()
    signer = Ed25519ManifestSigner(trusted_keys={SORVEX_FIRST_PARTY_KEY_ID: pub})
    for pkg in first_party:
        ok, reason = signer.verify_manifest(pkg)
        assert ok, f"{pkg.get('id')}: {reason}"


def test_marketplace_rejects_unsigned_first_party_publish(
    clear_key_env: pytest.MonkeyPatch, tmp_path
) -> None:
    """Unsigned ``first_party`` payloads must not be auto-signed server-side.

    The managed key is configured here on purpose: even when the server can
    sign, a caller-supplied unsigned first-party manifest must be rejected so
    authenticated publishers cannot mint Sorvex Labs signatures.
    """
    from core.platform.marketplace import MarketplaceSecurityError

    clear_key_env.setenv("KEELWAY_MANIFEST_KEY_FILE", str(tmp_path / "signing.seed"))
    registry = MarketplaceRegistry()

    payload = {
        "id": "forged-first-party-skill",
        "name": "Forged Sorvex Skill",
        "kind": "agent_skill",
        "publisher": "Attacker",
        "publisher_tier": "first_party",
        "description": "Should never become first-party signed.",
    }
    with pytest.raises(MarketplaceSecurityError) as excinfo:
        registry.publish_package(payload)
    categories = {f["category"] for f in excinfo.value.report["findings"]}
    assert "unsigned_first_party" in categories
    assert registry.get_package("forged-first-party-skill") is None


def test_marketplace_rejects_self_signed_first_party_publish(
    clear_key_env: pytest.MonkeyPatch,
) -> None:
    """A ``first_party`` manifest signed by an untrusted key is rejected."""
    from core.platform.marketplace import MarketplaceSecurityError

    registry = MarketplaceRegistry()
    attacker_pem, attacker_pub = generate_publisher_keypair()
    payload = {
        "id": "self-signed-first-party-skill",
        "name": "Self Signed Sorvex Skill",
        "kind": "agent_skill",
        "publisher": "Attacker",
        "publisher_tier": "first_party",
        "description": "Signed by an untrusted publisher key.",
    }
    signed = Ed25519ManifestSigner(trusted_keys={"attacker-key": attacker_pub}).sign_manifest(
        payload, attacker_pem, "attacker-key"
    )
    with pytest.raises(MarketplaceSecurityError) as excinfo:
        registry.publish_package(signed)
    categories = {f["category"] for f in excinfo.value.report["findings"]}
    assert "invalid_signature" in categories
    assert registry.get_package("self-signed-first-party-skill") is None
