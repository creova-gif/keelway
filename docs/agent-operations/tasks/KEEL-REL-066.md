# KEEL-REL-066 — Owner Decisions OD-3/4/5 Ratification

| Field | Value |
|---|---|
| **Status** | `VERIFIED_COMPLETE` |
| **Category** | `RELEASE / DECISIONS / DOCS` |
| **Agent** | Devin |
| **Date** | 2026-11-18 |
| **Branch** | `docs/KEEL-REL-066-owner-decisions` |

## Objective
Record the three remaining owner decisions (OD-3, OD-4, OD-5) in
`18-owner-decisions.md` — the file still listed all five as
`BLOCKED ON OWNER` despite OD-1/OD-2 being decided weeks ago.

## Decisions recorded (owner-ratified 2026-11-18)

- **OD-3** — bless mixed persistence: file-JSON for ephemeral/small state;
  SQLite WAL mandatory for tenant-data/audit/queryable state; no new
  storage layer. Carve-out flagged: `approval_rules` file-JSON → evaluate
  SQLite migration using the startup-rename precedent.
- **OD-4** — adapter order **LangGraph → OpenAI Agents SDK → ADK**
  (langgraph_migrator.py already exists; sequence by leverage + market).
- **OD-5** — **OIDC + SCIM Users in-scope for vNext**; org-directory sync
  deferred. Surface already built; gap is IdP interop validation.

## Follow-on tasks queued
- `KEEL-REL-067` — complete + verify LangGraph adapter end-to-end.
- `KEEL-REL-068` — IdP interop validation (Okta/Entra) + setup runbook.

## Evidence
`docs/release-readiness/2026-11-17/18-owner-decisions.md` rewritten with
per-decision records (decision, rationale, follow-on work). OD-1/OD-2
marked decided with their existing evidence refs.
