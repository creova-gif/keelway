# KEEL-REL-068 — Enterprise IdP Interop Validation (OD-5): OIDC + SCIM Users

| Field | Value |
|---|---|
| **Status** | `QUEUED` |
| **Category** | `RELEASE / ENTERPRISE / IDENTITY` |
| **Agent** | unassigned |
| **Date** | 2026-11-18 |

## Objective
Per OD-5, OIDC + SCIM Users are in-scope for vNext. The routes exist;
the gap is interop validation against real IdPs plus an operator runbook.

## Acceptance criteria
1. OIDC: token-exchange round-trip proven against a real IdP (Okta and/or
   Entra) — issuer validation, HS256 id-token verification, group→role
   mapping — plus a sandboxed/deterministic replay suite for CI.
2. SCIM Users: list/provision/patch flows verified against IdP payloads;
   negative paths (bad filter, unsupported ops) fail honestly.
3. Setup runbook: end-to-end Okta or Entra configuration for one org
   (redirect URIs, claims, group mapping, enabling the integration).
4. Security review: no token/id_token material in logs, tapes, or audit
   events beyond the existing `redact_secrets` contract.

## Context
`core/platform/enterprise_identity_siem.py`,
`core/api/platform_enterprise_routes.py` (routes under
`/enterprise/oidc`, `/enterprise/scim/v2/Users`). Explicitly out of scope
for vNext: org-directory/group sync, non-Users provisioning.
