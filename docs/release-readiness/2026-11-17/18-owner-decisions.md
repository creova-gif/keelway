# Owner Decisions

All five release-readiness owner decisions are now resolved. Records below
carry the decision, evidence, and follow-on work each implies.

---

## OD-1 — Product naming — DECIDED (2026-11-17, ADR-001)

**Decision:** Option 1 — **Keelway canonical**. Repo renamed
`creova-gif/kora → creova-gif/keelway`; package/binary/API/docs migrated in
KEEL-REL-061 (PRs #67–#70). `kora-sable.vercel.app` and the Vercel project
name remain (owner-paused). `kora_*` → `keelway_*` SQLite tables renamed
with a startup migration; `.kora/` state dirs + `kora.db` fallback kept via
`legacy_aware()`; `Kora Technologies` legal attribution preserved.

## OD-2 — API authority — DECIDED (2026-11-17, ADR-0045 + PR #66)

**Decision:** single public contract — `core.main:app` is the authoritative
`/v1` surface; the shadow `/v1` on the governance app removed.
`keelway/api/app.py` remains the operator control plane on `:8000` (not a
second public API authority).

## OD-3 — Persistence strategy — DECIDED (2026-11-18)

**Decision:** **Bless the current mixed model, with a codified rule** —
file-JSON is acceptable for ephemeral/small state; anything
tenant-data-bearing or audit-relevant must live on the SQLite WAL layer.

**Rationale:** the codebase already runs a working split, and each side
degrades honestly:
- SQLite WAL backs `SQLitePlatformStore` (marketplace, workspace,
  enterprise collections), governance store (tamper-detecting salted-key
  tables), `keelway_audit.db` hash chain, enterprise identity DB,
  SQLAlchemy async `database.py`.
- File-JSON backs `schedules.json` (atomic tmp+rename, corruption-tolerant,
  in-memory fallback — KEEL-REL-062), runner spool (intentionally
  filesystem for offline-runner semantics), workspace registry, signing
  seeds, sync-engine state.

**The codified rule (binding for future work):**
1. Ephemeral/small/queue state → file-JSON is fine; must keep atomic-write +
   corruption-tolerant load + honest-degradation conventions.
2. Tenant data, permissions, approvals, audit/evidence, and anything
   queried relationally → SQLite WAL only; no new file-JSON stores.
3. No new storage layer or migration program — the existing SQLite WAL
   infrastructure is the standard.

**Carve-out flagged for evaluation (not automatic migration):**
`core/security/approval_rules.py` stores approval policy as file-JSON;
approval policy is security-relevant and arguably belongs under rule 2.
Evaluation task queued — if it migrates, use the `init_db()`-style startup
rename precedent, not a new migration framework.

## OD-4 — Framework-adapter roadmap — DECIDED (2026-11-18)

**Decision:** **LangGraph → OpenAI Agents SDK → Google ADK**, sequenced by
existing-code leverage plus market size.

**Rationale:** `core/platform/langgraph_migrator.py` (645 LOC) already
implements LangGraph→Keelway import — finishing and proving it is the
fastest path to a *verified* framework-adapter story. OpenAI Agents SDK is
the next-largest user base; ADK last. The original order (Agents SDK →
ADK → LangGraph) predates the migrator.

**Follow-on:** `KEEL-REL-067` queued — complete + verify the LangGraph
adapter (evidence: end-to-end import of a real LangGraph agent into a
Keelway governed run, with tests).

## OD-5 — Enterprise scope — DECIDED (2026-11-18)

**Decision:** **In-scope for vNext, but scoped** — OIDC + SCIM Users only;
full org-directory sync is deferred.

**Rationale:** the surface is substantially built, not aspirational:
`/enterprise/oidc` + `/exchange` (config, HS256 id-token validation,
group→role mapping), `/enterprise/scim/v2/Users` list + provision,
`enterprise_identity_siem.py` (701 LOC, encrypted DB), 2-of-2 P-10 quorum.
The gap is IdP interop validation, not features.

**Follow-on:** `KEEL-REL-068` queued — IdP interop validation for OIDC +
SCIM Users (real Okta/Entra token round-trips, edge-case suite, setup
runbook). Out of scope for vNext: group/role-directory sync, provisioning
beyond Users, SCIM schema extensions.
