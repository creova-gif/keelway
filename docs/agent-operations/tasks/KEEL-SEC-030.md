# KEEL-SEC-030 — Managed First-Party Manifest Signing Key

| Field | Value |
|---|---|
| **Status** | `VERIFIED_COMPLETE` |
| **Category** | `SECURITY / SUPPLY-CHAIN / MARKETPLACE` |
| **Agent** | Devin |
| **Date** | 2026-11-16 |
| **Branch** | `fix/KEEL-SEC-030-managed-signing-key` |

## Objective
Remediate the post-merge review High finding: `get_sorvex_first_party_keypair()` derived the "Sorvex Labs" Ed25519 private key from a public constant, so anyone could forge first-party marketplace manifests. Replace with managed key resolution and fail-closed behavior.

## Acceptance Criteria
- [x] Private key sourced from `KEELWAY_MANIFEST_SIGNING_KEY` (PEM) / `KEELWAY_MANIFEST_SIGNING_SEED` (hex/base64), `KEELWAY_MANIFEST_KEY_FILE`, or `$KEELWAY_STATE_DIR/manifest-signing.seed` (load-or-generate, mode 0600)
- [x] Deterministic legacy key available only behind `KEELWAY_DEV_INSECURE_KEY=1`
- [x] Unconfigured → `FirstPartySigningKeyUnavailable`; default `Ed25519ManifestSigner` trusts no keys (verify fails closed)
- [x] `MarketplaceRegistry` publishes first-party packages unsigned when no key is configured (no crash, verification fails closed)
- [x] Tests opt into dev gate via `tests/conftest.py`; env documented in `env.example`

## Files Modified
- `core/platform/signing.py` — key resolution chain, `FirstPartySigningKeyUnavailable`, fail-closed default signer
- `core/platform/marketplace.py` — unsigned first-party publish fallback
- `core/platform/__init__.py` — export new exception
- `tests/conftest.py` — `KEELWAY_DEV_INSECURE_KEY=1` for test suite
- `tests/test_manifest_signing_key_management.py` — 9 new tests (both paths)
- `env.example` — documented all five env vars

## Tests Executed
- `pytest tests/test_manifest_signing_key_management.py -q`: 9 passed
- `pytest tests/test_platform_persistence_and_enterprise.py tests/test_unified_platform.py tests/test_marketplace_settlement_and_cluster_sdk.py tests/test_sdk_platform.py -q`: 51 passed

## Known Risks & Blockers
- Key ID remains `sorvex-labs-ed25519-v1`; rotating to a managed key invalidates signatures produced under the legacy deterministic key (intended — they were forgeable). Packages signed under the legacy key should be re-signed after provisioning.
- `docker-compose.yml` platform service already sets `KEELWAY_STATE_DIR=/data/.keelway`, so the key file persists on the `keelway-data` volume automatically.

## Next Recommended Action
Merge to `main`; proceed to KEEL-SEC-031 (payment broker secret).
