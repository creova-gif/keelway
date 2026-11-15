# KEEL-SEC-021 — Replace Derivable First-Party Manifest Signing Key

- **Status:** `READY_FOR_REVIEW`
- **Category:** `SECURITY / PLATFORM`
- **Branch:** `fix/KEEL-SEC-021-first-party-manifest-key`
- **Updated:** `2026-11-15`

## Problem

`get_sorvex_first_party_keypair()` derived the `sorvex-labs-ed25519-v1` private key from
`sha256(b"keelway.manifest.sorvex-labs.first-party.ed25519.v1")`, so anyone with the source could sign
manifests that every default `Ed25519ManifestSigner` accepted as Sorvex Labs first-party. In addition,
`MarketplaceRegistry.publish_package` auto-signed any payload claiming `publisher_tier: "first_party"`,
including payloads sent to `POST /v1/platform/marketplace/publish`.

## Change

- `core/platform/manifest_keys.py`: `TRUSTED_FIRST_PARTY_MANIFEST_KEYS` — public keys only, empty until
  Sorvex Labs generates a real key (same fail-closed pattern as `core/billing/licence_keys.py`).
- `core/platform/signing.py`: removed the derived keypair. `load_first_party_signing_key()` reads a PKCS#8
  PEM from `KEELWAY_FIRST_PARTY_MANIFEST_SIGNING_KEY`; the default signer trusts the committed public keys
  plus the configured key's public half.
- `core/platform/marketplace.py`: only curated seed packages are signed, and only when the key is set.
  Publishing a `first_party` package now requires a signature from a trusted key.

## Acceptance Criteria

- [x] The legacy derived key is rejected (`UNKNOWN_PUBLISHER_KEY`).
- [x] Seed packages are signed and verify when the key is configured.
- [x] Seed packages are unsigned (`UNSIGNED_MANIFEST`) when no key is configured.
- [x] Unsigned `first_party` publish attempts are rejected.

## Operator Action

1. On a Sorvex Labs signing machine: `python -c "from core.platform import generate_publisher_keypair as g; k,p=g(); print(p)"`
   (keep the private PEM offline / in the secret store).
2. Add the public key to `TRUSTED_FIRST_PARTY_MANIFEST_KEYS["sorvex-labs-ed25519-v1"]`.
3. Set `KEELWAY_FIRST_PARTY_MANIFEST_SIGNING_KEY` only where curated seed packages are published.

Packages persisted in an existing SQLite platform store were signed with the old key and will fail
verification until re-seeded.
