# KEEL-REL-068 — Enterprise IdP Interop Validation (OD-5): OIDC + SCIM Users

| Field | Value |
|---|---|
| **Status** | `VERIFIED_COMPLETE` |
| **Category** | `RELEASE / ENTERPRISE / IDENTITY` |
| **Agent** | Devin |
| **Date** | 2026-11-18 |
| **Branch** | merged `main` (PR #82) |

## Objective
Per OD-5, OIDC + SCIM Users are in-scope for vNext. The routes existed but
the OIDC exchange was **HS256 self-issued only** — real Okta/Entra id_tokens
are signed **RS256 + JWKS**, so a real IdP round-trip was impossible. This
task adds the RS256/JWKS verification path, SCIM interop hardening, a
deterministic replay suite, and the operator runbook.

## Implementation

### `core/platform/enterprise_identity_siem.py`
- `platform_oidc_providers` gains `jwks_uri` + `jwks_json` columns
  (`PRAGMA table_info` migration, expand-compatible).
- `configure_oidc(..., jwks_uri, jwks_json)` — `jwks_uri` validated through
  the same `validate_oidc_issuer_url` SSRF checks; `jwks_json` = pinned JWKS
  document (no egress — sovereign + CI path). New providers require secret
  OR JWKS; existing values preserved on partial reconfigure.
- `exchange_oidc_token` dispatches on header `alg`: `HS256` → decrypted
  secret HMAC (unchanged); `RS256` → `_resolve_jwks_keys` (pinned
  `jwks_json` first, else `_fetch_jwks_keys` via urllib with 10s timeout,
  256KB cap, 300s in-memory TTL cache) → `kid` selection → RSA PKCS1v15 +
  SHA-256 via `cryptography` (existing dep — no new packages). Other algs
  (`none`/`ES256`/…) rejected honestly.
- `federation_profile`: `external_idp_rs256` when JWKS-configured, else
  `self_issued_hs256` — disclosed in `configure_oidc`, `get_oidc`, and every
  exchange response.
- `_normalize_groups` prefers SCIM `display` over `value` so dict-shaped
  group refs match the same `group_role_mapping` used for OIDC claims.
- `list_scim_users` gains `filter` (`userName eq "x"`, case-insensitive —
  other filters → `400`), `startIndex`/`count` pagination, `itemsPerPage`.
- `build_rs256_id_token` + `rsa_public_jwk` helpers for replay suites.

### `core/api/platform_enterprise_routes.py`
- `OidcConfigureRequest` gains `jwks_uri`/`jwks_json`; `PUT /enterprise/oidc`
  passes them through.
- `GET /enterprise/scim/v2/Users` accepts `filter`/`startIndex`/`count`.
- `_extract_scim_patch_fields` → 4-tuple with `ignored` ops; PATCH responses
  surface `warnings.ignored_operations` (unmodelled Entra/Okta attrs are
  applied-then-reported, never silently dropped). Accepts string booleans
  (`"False"`) and composes `displayName` from `name.givenName`/`familyName`.
- Provision request accepts `name`/`emails`; `displayName` falls back to
  name composition.

## Acceptance criteria — evidence
- [x] **AC1 — OIDC round-trip**: RS256 mint→verify proven for Okta-shaped
  (`iss=...okta.com/oauth2/default`) and Entra-shaped
  (`iss=...login.microsoftonline.com/<tid>/v2.0`, group object IDs) tokens;
  issuer/aud/exp/nbf/kid/alg-confusion negatives all fail closed.
  `tests/test_enterprise_idp_interop.py` — **17 passed**.
  ⚠️ **Live IdP note**: a real Okta/Entra tenant round-trip requires the
  customer's tenant credentials and is an operator step — the runbook defines
  the contract; CI replay does not claim live-IdP proof.
- [x] **AC2 — SCIM Users**: Okta-shaped provision payload, Entra-shaped PATCH
  `Operations` (string booleans), `userName eq` filter + pagination, bad
  filters → `400`, unsupported paths → `warnings.ignored_operations`.
- [x] **AC3 — Runbook**: `docs/runbooks/ENTERPRISE_SSO.md` — Okta + Entra
  app creation, redirect URIs, `groups` claim config, group→role mapping,
  JWKS values, SCIM provisioning connector, validation calls.
- [x] **AC4 — Security review**: exchange response + stored DB bytes contain
  no `id_token`/secret material (tested); `signing_secret` AES-256-GCM at
  rest, `sha256:` fingerprint only; JWKS URIs SSRF-validated; JWKS is public
  key material stored plaintext by design.

## Tests executed & evidence
- `pytest tests/test_enterprise_idp_interop.py` — **17 passed**
- `pytest tests/test_phase9_enterprise_identity_siem_metrics.py
  tests/test_phase9_sdk_and_release_workflow.py` — **7 passed** (no regressions)
- `ruff check` on all touched files — **clean**

## Known limits (documented in runbook)
- No OIDC discovery doc fetch — `issuer_url`/`client_id`/`jwks_*` configured
  explicitly. No ES256/EdDSA, no auth-code redirect leg, no SCIM group sync,
  no org-directory sync (OD-5 deferral).
- `jwks_uri` fetch is outbound HTTPS at exchange time (300s cache);
  air-gapped deployments should pin `jwks_json` instead.
