# KEEL-MANIFEST-007 — Phase 2: Ed25519 Signing, SQLite WAL Platform Store, Enterprise Governance, SDK Parity & `/marketplace`

- **Status:** `VERIFIED_COMPLETE`
- **Category:** `SECURITY / PLATFORM / SDK / WEBSITE`
- **Branch:** `main`
- **Updated:** `2026-11-14`
- **Plan Reference:** `docs/superpowers/plans/2026-11-14-unified-platform-phase2.md`

## Scope Delivered

1. **Asymmetric Ed25519 Manifest Signing (`core/platform/signing.py`):**
   - Publisher keypair generation (`generate_publisher_keypair()`), first-party Sorvex keypair (`sorvex-labs-ed25519-v1`), and `Ed25519ManifestSigner` verifying canonical payload signatures (`VERIFIED_ED25519`, `UNSIGNED_MANIFEST`, `UNKNOWN_PUBLISHER_KEY`, `INVALID_ED25519_SIGNATURE`).
2. **Crash-Safe SQLite WAL Platform Persistence (`core/platform/persistence.py`):**
   - `SQLitePlatformStore` (`PRAGMA journal_mode=WAL`) backing `MarketplaceRegistry`, `ExtensionRegistry`, and `UnifiedWorkspaceHub` across restarts without duplicate seeding.
3. **Enterprise Governance & Compliance (`core/platform/enterprise.py`):**
   - `EnterpriseGovernanceManager` enforcing tenant-isolated data retention (`ephemeral_0d`, `standard_30d`, `regulated_365d`, `worm_7y`), deployment topology, PII redaction, custom branding, SSO/SAML, and `SOC2`/`HIPAA`/`ISO27001`/`GDPR` compliance posture evaluation.
4. **Python & Zero-Dependency TypeScript SDK Parity (`core/sdk/platform_client.py`, `sdk/typescript/src/platform.ts`):**
   - Full 20-method `client.platform` coverage in both `core.sdk` (sync + async) and `@keelway/sdk` (zero runtime npm dependencies) with structured HTTP 422 `PolicyViolationError` security findings preserved.
5. **Dev App Full-Stack `/v1/platform/*` Sync & Dedicated `/marketplace` Website Route:**
   - Same-origin `/v1/platform/*` hydration and live package/issue/team/blueprint mutations in `dev-app/src/lib/platformApi.ts` (rebuilt into `core/dev_app_dist/`), plus the searchable 7-category, 3-publisher-tier `/marketplace` explorer on the Next.js 15 website.
