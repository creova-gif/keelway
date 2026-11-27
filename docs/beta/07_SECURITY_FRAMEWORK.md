# 07 — Security Framework

Canonical sources: `docs/security/`, `SECURITY.md`,
`docs/release-readiness/2026-11-17/09-security-threat-model.md` +
`10-security-test-matrix.csv` (still accurate — re-verify entries
marked UNVERIFIED there).

## Verified mechanisms

| Mechanism | Location | State |
| --------- | -------- | ----- |
| Launch + role tokens (SHA-256 at rest) | `core/security/auth.py` | VERIFIED |
| Phone pairing codes (expiring, one-shot) | `core/security/auth.py` | VERIFIED |
| RBAC `Principal.can()` + PHONE_ROUTES allowlist | auth.py + routes | VERIFIED |
| Air-gap fail-closed | model gateway | VERIFIED |
| OS sandbox (seatbelt/bwrap) + fail-closed exec | `core/agents/sandbox.py` | VERIFIED (6 live Linux tests) |
| Merkle flight tapes + receipts | `core/platform/` | VERIFIED |
| Secret scanning | gitleaks in CI | VERIFIED |
| Dependency audit | pip-audit on lock | VERIFIED |

## Findings / residuals for beta

1. **`?token=` URL param** (P0-4) — bearer in query string hits
   browser history + access logs. Localhost-tolerable; must be
   documented or header-only before any remote deploy.
2. **HAL-verifier routes rewired** in KEEL-ENG-062 — previously dead
   code now live against real verifier APIs with zero direct test
   coverage; schedule a targeted pass (Security lane).
3. **`verify_manifest`/wire-input boundaries** intentionally widened
   to `Any` in KEEL-ENG-065 — guards are real; do not re-narrow.
4. Token TTL/rotation story exists (`expires_at`) — document in
   onboarding.
