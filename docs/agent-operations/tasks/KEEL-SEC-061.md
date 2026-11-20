# KEEL-SEC-061 — Marketplace Unsigned First-Party Publish Forgery Fix

| Field | Value |
|---|---|
| **Status** | `VERIFIED_COMPLETE` |
| **Category** | `SECURITY / SUPPLY-CHAIN / MARKETPLACE` |
| **Agent** | Devin |
| **Date** | 2026-11-20 |
| **Branch** | `fix/keel-sec-061-marketplace-first-party-forgery` |

## Objective
Close the residual forgery vector left after KEEL-SEC-030: `MarketplaceRegistry.publish_package`
still auto-signed any caller-supplied `publisher_tier: "first_party"` manifest that carried **no**
signature. Because `POST /v1/platform/marketplace/publish` is gated only by `current_principal`
(authentication, no publisher role check), any authenticated caller could mint a Sorvex Labs
first-party-signed package whenever the server's managed signing key was configured — exactly the
environment production seeds require.

This is the un-merged second half of the stale PR #56 (KEEL-SEC-021); the key-management half was
superseded by KEEL-SEC-030 and is not re-landed here.

## Acceptance Criteria
- [x] Unsigned `first_party` payloads via the public publish path → `MarketplaceSecurityError`
      (HTTP 422) with `unsigned_first_party` finding
- [x] `first_party` payloads signed by an untrusted key still fail `UNKNOWN_PUBLISHER_KEY`
      verification → `MarketplaceSecurityError` (`invalid_signature` finding) — pre-existing
      behavior, now covered by an explicit regression test
- [x] Curated seed publishing retains server-side auto-signing behind a private
      `_curated_seed` flag (only reachable from `MarketplaceRegistry.__init__` seed loading)
- [x] Unsigned `first_party` + unconfigured key still fails closed (rejected before signing)
- [x] All existing marketplace/settlement/persistence/unified-platform tests pass unmodified

## Files Modified
- `core/platform/marketplace.py` — `publish_package(payload, *, _curated_seed=False)`;
  unsigned `first_party` rejected unless `_curated_seed=True`; `__init__` seed loop opts in
- `tests/test_manifest_signing_key_management.py` — two new regression tests:
  unsigned `first_party` rejected *with managed key configured* (proves the hole is closed even
  when the server can sign); self-signed `first_party` by untrusted key rejected

## Tests Executed
- `pytest tests/test_manifest_signing_key_management.py tests/test_platform_persistence_and_enterprise.py tests/test_marketplace_settlement_and_cluster_sdk.py -q`: **33 passed**
- `pytest tests/test_unified_platform.py tests/test_sdk_platform.py -q`: **29 passed**
- `uvx ruff check core/platform/marketplace.py tests/test_manifest_signing_key_management.py`: **clean**
- `python3 -m py_compile` on both touched files: **OK**

## Known Risks & Blockers
- `POST /v1/platform/marketplace/publish` still requires only an authenticated principal; tier
  elevation to `first_party` is now signature-gated, but a role/RBAC gate on publish remains a
  separate hardening candidate (tracked as follow-up).
- `build/lib/**` contains a stale vendored copy of `marketplace.py`; not updated (generated).

## Next Recommended Action
- Evaluate an RBAC publisher-role check on `/marketplace/publish` so tier claims are also
  authorization-gated, not just cryptographic.
- Triage remaining stale PRs: #26 (README fix), #44 (flaky CI test fix), #55 (Claude Code gate),
  #57 (Dependabot config), #58 (checkout webhook issuer), #59 (community docs). PR #56 can be
  closed — its key-management half was superseded by KEEL-SEC-030 and the publish-forgery half is
  landed by this task.
