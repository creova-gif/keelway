# SSO / Multi-Tenancy Direction — Decision Brief (DRAFT)

> **Status**: DRAFT — for founder decision. Not an ADR; nothing here is
> committed direction until accepted.
> **Context**: UI_UX_AUDIT UX-008 marked the enterprise checklist (orgs,
> team workspaces, RBAC admin, billing/quotas, account deletion/export)
> as *NOT A DEFECT* — Keelway ships single-operator sovereign by design —
> but flagged SSO/multi-tenancy as an open product decision (P1 priority,
> "decision-held") that gates how far enterprise UX surfaces should go.

## Verified current state (what already exists)

- **RBAC**: 5 roles in `core/security/rbac.py` — `OWNER`, `ADMIN`,
  `ENGINEER`, `AUDITOR`, `PHONE` — mapped to a fixed `Permission` enum.
- **Principals**: API tokens with roles + expiry (`core/security/auth.py`);
  `LOCAL_OWNER` implicit principal; paired phones get scoped `phone`
  tokens (single-use pairing code, 30-day TTL, revocable).
- **Tenant scaffolding**: `core/cluster/postgres_adapter.py` already has
  `keelway_tenant_budgets` (monthly_limit_usd) and a tenant-scoped audit
  chain (`tenant_id, seq`) — the multi-tenant cost/isolation spine was
  designed in, not bolted on.
- **KSpaces**: `SpaceRole.OWNER` / `AGENT_MANAGER` membership model in
  `core/kspaces/manager.py` — workspace-level sharing already exists.
- **No external IdP anywhere**: auth is local-token only; no OIDC/SAML,
  no session cookies, no org model exposed in API or UI.

## Options

### A — Hold: single-operator sovereign (status quo, documented)

Keep local tokens + 5-role RBAC; publish the boundary explicitly in docs
(roles exist for *capability scoping*, not org administration). UX stays
as today: Governance/Settings views cover it; no org/team/billing admin
surfaces.

- **Cost**: none. Enterprise UX scope stays closed — UX-008 stays
  "not a defect" permanently.
- **Trade-off**: enterprise teams share one install by sharing tokens —
  fine for sovereign single-tenant deployment, no audit-identity per
  human.

### B — Local multi-user principals (no external IdP)

Named principals per human on one install: `keelway user add`, each with
their own token + role; audit tape attributes actor identity per person.

- **Unlocks**: per-human audit attribution (currently `actor` is the
  token name), team deployments of a single sovereign instance.
- **Cost**: small — token store already keys per-principal; add a users
  table + admin CLI/UI. No federation.
- **UX delta**: a "Team" settings panel (list/invite/revoke users).

### C — OIDC SSO for sovereign installs

Accept OIDC tokens from a customer IdP (Keycloak/Authentik/Okta/Entra) at
the FastAPI layer; map `groups`/`roles` claims onto the existing
`Role`/`Permission` matrix. Install stays self-hosted — SSO is an
*auth front door*, not a control plane.

- **Unlocks**: enterprise compliance checkboxes (SSO, SCIM later),
  central offboarding, MFA via IdP. Fits the sovereignty story: Keelway
  never phones home; the customer's own IdP issues tokens.
- **Cost**: medium — OIDC token validation (JWKS), claim→role mapping,
  config surface, revocation semantics. SAML deliberately out of scope
  (OIDC covers the modern IdP set).
- **UX delta**: login screen when `oidc` configured; role display
  sourced from IdP claims; audit `actor` becomes the IdP `sub`.

### D — Multi-tenant SaaS control plane (Keelway Cloud)

Orgs, tenant-isolated data planes, billing/quotas, invites, deletion/
export — the full SaaS checklist. `keelway_tenant_budgets` is the seed,
but this is a hosted product, not an install feature.

- **Unlocks**: commercial SaaS motion; per-tenant metering already
  scaffolded.
- **Cost**: large — control plane service, tenant isolation boundaries,
  billing integration, org admin UX (the whole UX-008 surface).
- **Explicitly separable**: A/B/C are all compatible with D later; D
  does not require C inside the sovereign install (cloud can own its
  own auth).

## Decision points for the founder

1. **Is Keelway's enterprise story "sovereign install" or "hosted
   service" first?** If sovereign-first: C is the highest-value option —
   SSO is the #1 enterprise procurement checkbox and it preserves the
   sovereignty narrative. D becomes a separate product decision.
2. **Is per-human audit attribution needed now?** If compliance
   reviewers ask "who approved this step" and tokens are shared, B is a
   cheap answer independent of SSO.
3. **Sequencing if B+C**: B (named principals) makes C trivially better —
   IdP claims map onto real user rows rather than implicit principals.
   But C alone is shippable without B (claim → role → ephemeral
   principal per request).
4. **What to tell UX**: if the answer is A or B, enterprise admin
   surfaces stay closed and UX-008 resolves permanently. If C or D,
   the enterprise checklist reopens as real scope.

## Non-goals (all options)

- SAML 2.0 — OIDC suffices for the modern IdP set; revisit only on
  named customer demand.
- SCIM provisioning — follow-on to C, not bundled.
- Public signup/account lifecycle — belongs to D only.

## Recommendation (draft)

**B → C → (D later, separate product)** if the enterprise motion is
real: B is days not weeks and immediately improves audit honesty; C is
the enterprise checkbox that fits sovereignty; D is a business decision
that shouldn't block either. If the product stays single-operator by
intent, **A** and the honest posture is to close UX-008 for good and say
so publicly.
