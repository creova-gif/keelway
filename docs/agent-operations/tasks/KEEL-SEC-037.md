# KEEL-SEC-037 — OIDC Federation Profile Disclosure & Claim Correction

| Field | Value |
|---|---|
| **Status** | `VERIFIED_COMPLETE` |
| **Category** | `SECURITY / PRODUCT-TRUTH / ENTERPRISE-IDENTITY` |
| **Agent** | Devin |
| **Date** | 2026-11-16 |
| **Branch** | `fix/KEEL-SEC-037-oidc-profile` |

## Objective
Resolve the post-review finding that the "Enterprise OIDC/SAML Federation" surface is actually a self-issued HS256 shared-secret token profile — no OIDC discovery/JWKS and no SAML exist — while website and changelog copy implied standards federation.

## Decision
Rather than silently relabeling, every OIDC API response now discloses `"federation_profile": "self_issued_hs256"` so SDK/CLI/API consumers see the true capability at runtime. Real external-IdP federation (discovery + JWKS + RS256/ES256/EdDSA) remains a defined future task; SAML remains unimplemented.

## Changes
- `core/platform/enterprise_identity_siem.py`:
  - Module docstring documents the self-issued HS256 scope and non-goals.
  - `configure_oidc`, `get_oidc`, and `exchange_oidc_token` responses include `federation_profile: "self_issued_hs256"`.
- `tests/test_phase9_enterprise_identity_siem_metrics.py`: exchange-response equality updated for the new field.
- Website claim corrections (no unsupported claims remain):
  - `page.tsx`: "OIDC/SAML" → "enterprise SSO (OIDC)"
  - `DocsHub.tsx`: card retitled "Enterprise SSO, SCIM 2.0 & Dual-Human P-10 Quorum"; summary now states the HS256 profile and that IdP discovery/JWKS federation and SAML are not yet implemented; spec line "OIDC/SAML" → "OIDC HS256"
  - `PricingTiers.tsx`: "SAML/SSO" → "Enterprise SSO (OIDC)"
- `CHANGELOG.md`: "OIDC/SAML federation" → "OIDC federation" + erratum noting the self-issued HS256 profile.

## Acceptance Criteria
- [x] API responses self-disclose the token profile
- [x] No website/docs surface claims SAML or external IdP federation
- [x] Existing OIDC behavior (SSRF guard, AES-256-GCM secret at rest, group→role mapping, exp/nbf/aud/iss checks) unchanged

## Tests Executed
- `pytest tests/test_phase9_enterprise_identity_siem_metrics.py tests/test_platform_persistence_and_enterprise.py tests/test_config_fallback.py -q`: **11 passed**
- `website`: `npm run typecheck` (tsc --noEmit): clean

## Known Risks & Blockers
- Customers needing real IdP federation (Entra ID, Okta, Keycloak) still cannot use it — tracked as future work. The `sso_saml_required` enterprise-policy checklist flag remains a policy marker only; SAML itself is unimplemented.
- `federation_profile` is additive; older SDKs ignore unknown fields (verify per-SDK tolerance if strict parsing is added later).

## Next Recommended Action
Merge to `main`. Remaining backlog: ADR-0042 Phase 2 consolidation planning (founder scheduling), payment-processor integration (when commerce is in scope), real OIDC discovery/JWKS federation (new task if enterprise SSO demand materializes).
