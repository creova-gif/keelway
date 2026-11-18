# TASK: KEEL-P0-063 — Permissions Depth: Grant-from-Settings Flow, Scope Preview, Rule Lifecycle

## 1. METADATA
- **TASK ID**: KEEL-P0-063
- **CATEGORY**: UI / SECURITY / PRODUCT-TRUTH
- **CREATOR**: Devin
- **ASSIGNED AGENT**: Unassigned (queued)
- **STATUS**: QUEUED
- **TARGET BRANCH**: `feature/KEEL-P0-063-permissions-depth`
- **BASE COMMIT**: `5b0a23e` (tip of `fix/KEEL-P0-029-demo-free-settings`)
- **PARENT**: KEEL-P0-029 — PR #63

---

## 2. OBJECTIVE & MOTIVATION

KEEL-P0-029 made the Permissions surface honest: rules load from the real
backend, binding is enforced at runtime, categories and provenance are plain
language, and destructive changes confirm. What remains is **completeness of
the permission lifecycle as a user-facing product surface** — today a person
can only create a standing rule reactively (approve-with-remember during a
paused step) or via raw API. A new user cannot proactively grant a scoped
permission from Settings, cannot see what a scope pattern will match before
granting, cannot time-box a grant, and cannot tell which workspace a rule
applies to when multiple workspaces exist.

This task closes that lifecycle gap. It is deliberately separate from P0-029
so that PR stays reviewable.

---

## 3. ACCEPTANCE CRITERIA

- [ ] **Grant-from-settings**: a "Create rule" flow in `SettingsPermissionsPanel`
      produces a real `POST /v1/approval-rules` call with tool picker, scope
      input, and binding capture (active model + current prompt version
      prefilled, editable). Server-reconciled, busy-locked, `role="alert"` on
      failure. No optimistic grant.
- [ ] **Scope preview**: before granting, the UI shows — in plain language —
      what the scope will match (e.g., "files matching `src/*.py` in this
      workspace") and rejects the same unsafe scopes the backend validator
      rejects (`*`, `**/*`, protected paths, `..` traversal). Client-side
      check mirrors `validate_scope`; server remains the authority.
- [ ] **Optional expiry**: `POST /v1/approval-rules` accepts an optional
      `expires_at`/`ttl_seconds`; expired rules are treated as dormant at
      `match()` time (fail closed → paused), rendered "Expired" in the UI,
      and are excluded from auto-grant. If owners decide against TTL, the
      decision is recorded as an ADR and the UI's "No expiry" copy stays.
- [ ] **Workspace attribution**: each rule row names the workspace it governs
      (rules live in `<workspace>/.keelway/approval_rules.json`); multi-workspace
      installs show the correct workspace, never a fabricated global view.
- [ ] **Revoke-all scoping**: "Revoke all" copy states it revokes rules for
      *this* workspace only.
- [ ] Tests: backend — TTL expiry pauses match, expired rule listed as expired;
      frontend — create-rule happy path, unsafe-scope rejection, workspace label,
      axe-clean in armed/expanded/create-dialog states.
- [ ] Zero security regressions: all mutations stay gated `APPROVE_TIER3`;
      expired rules cannot match even if the file is hand-edited to a future
      timestamp in another field (expiry evaluated from `expires_at` only).

---

## 4. AFFECTED FILES & COMPONENTS
- Primary:
  - `dev-app/src/components/screens/settings/SettingsPermissionsPanel.tsx`
  - `dev-app/src/lib/api.ts`, `dev-app/src/lib/apiDecoders.ts`, `dev-app/src/lib/types.ts`
  - `core/security/approval_rules.py` (optional `expires_at` + dormant-at-match)
  - `core/api/routes.py` (accept/return expiry on create)
- Tests:
  - `dev-app/src/__tests__/settings-and-app.test.tsx`
  - `tests/test_approval_rules.py`

---

## 5. SECURITY & PRIVACY CONSIDERATIONS
- Privacy Fail-Closed: expired or malformed-expiry rules must not match.
- Credential handling: none beyond existing token auth.
- Autonomy Tier: Tier 2 (writes) governed by existing `APPROVE_TIER3` + P-10.
- New attack surface to reason about: a user-granted TTL must not be extendable
  by editing the rules file without re-confirmation (expiry is evaluated at
  match time from persisted `expires_at`; a hand-edit extends it — same trust
  model as the existing file, documented, not a new hole).

---

## 6. VALIDATION & TEST PLAN
```bash
pytest tests/test_approval_rules.py -v
cd dev-app && npm test -- --run && npm run build
# live stack:
./.cursor/skills/verify-keelway/scripts/control-keelway launch --state-dir /tmp/keelway-p063
```

## 7. OUT OF SCOPE
- Full WCAG manual screen-reader pass (separate a11y task).
- Ubuntu/Docker clean-install matrix (release-readiness Phase work).
- Cross-workspace rule aggregation view (would need a new storage model —
  note as ADR candidate if owners want it).
