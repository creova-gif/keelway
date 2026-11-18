# TASK: KEEL-P0-063 — Permissions Depth: Grant-from-Settings Flow, Scope Preview, Rule Lifecycle

## 1. METADATA
- **TASK ID**: KEEL-P0-063
- **CATEGORY**: UI / SECURITY / PRODUCT-TRUTH
- **CREATOR**: Devin
- **ASSIGNED AGENT**: Devin
- **STATUS**: VERIFIED_COMPLETE
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

- [x] **Grant-from-settings**: "Grant a standing rule" disclosure in the rules
      card — capability picker (edit/write/run_command), scope input, TTL
      select, live scope preview, submit → real `POST /v1/approval-rules`.
      Server-reconciled (created rule prepends from the response body),
      busy-locked, `role="alert"` on failure. Binding is auto-captured from the
      active model + current prompt version — shown in the form copy.
- [x] **Scope preview**: `previewGrantScope()` mirrors `validate_scope`
      semantics — absolute/`..`/empty paths, all-wildcard patterns
      (`*`, `**/*`), and `.keelway`/`.kora`/`.git` segments are rejected with
      the backend's own plain-language reasons, live under `aria-live`. Valid
      scopes preview "Matches files under \"X\" inside this workspace" /
      "Matches only the exact command". Server remains the authority.
- [x] **Optional expiry**: `ApprovalRule.expires_at` persisted;
      `add()` accepts `expires_at`/`ttl_seconds` (mutually exclusive,
      must be future). `is_expired()` evaluates only that field —
      `match()` skips expired rules → step pauses (fail closed).
      List response exposes `expired`; UI renders an "Expired" badge,
      "dormant, kept for audit" detail, and expired rules are excluded
      from the drift/reconfirm computation.
- [x] **Workspace attribution**: `GET /v1/approval-rules` returns
      `workspace` (the workspace fs root name). The card states "Rules govern
      the {name} workspace only — stored in that workspace's .keelway/ folder";
      controlled mode uses the real `workspacePath` prop.
- [x] **Revoke-all scoping**: armed label reads "Confirm revoke all (this
      workspace)".
- [x] Tests: backend — TTL grant → live match → dormant after clock advance →
      listed `expired: true` with `workspace`; past/conflicting expiry 400s;
      hand-edited file with unknown fields loads and matches. Frontend —
      grant happy path + TTL select + preview, `**/*` and `../` rejection,
      workspace attribution, expired-row rendering, axe-clean.
- [x] Zero security regressions: create/revoke/reconfirm still gate on
      `APPROVE_TIER3`; expiry is evaluated only from persisted `expires_at`
      (hand-edited `expires_in_days`-style annotations are ignored by both
      the loader and `is_expired`).

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

---

## HANDOFF — 2026-11-18 (Devin)

- **STATUS**: VERIFIED_COMPLETE
- **BRANCH**: `feature/KEEL-P0-063-permissions-depth` (stacked on `fix/KEEL-P0-029-demo-free-settings`)

### FILES MODIFIED
- `core/security/approval_rules.py`: `ApprovalRule.expires_at`, `is_expired()`, `add()` ttl/expires_at validation, `match()` skips expired rules.
- `core/api/routes.py`: GET returns `{workspace, rules[].expired}`; POST accepts `ttl_seconds`/`expires_at`.
- `dev-app/src/lib/types.ts`: `expiresAtEpoch`, `expired`, `ApprovalRulesListResponse`.
- `dev-app/src/lib/apiDecoders.ts`, `api.ts`, `apiFallbacks.ts`: decode/serve new fields; `fetchApprovalRules` returns `{rules, workspace}`; `CreateApprovalRuleInput.ttlSeconds`.
- `dev-app/src/components/screens/settings/SettingsPermissionsPanel.tsx`: `previewGrantScope()` validator mirror, grant form (capability/scope/TTL + live preview), workspace attribution line, Expired badge, real expiry in provenance, workspace-scoped revoke-all copy.
- `dev-app/src/components/screens/SettingsWorkspace.tsx`, `App.tsx`: workspaceName threading, `{rules}` unwrap.
- `tests/test_approval_rules.py`, `dev-app/src/__tests__/settings-and-app.test.tsx`: new coverage.

### TESTS EXECUTED
- `pytest tests/test_approval_rules.py -q`: **29 passed**
- dev-app `vitest run`: **111 passed (23 files)**
- `tsc --noEmit` + `vite build`: clean; `core/dev_app_dist` rebuilt (`index-Bug_tSZl.js`)
- `py_compile` on touched modules: clean; ruff unavailable on this host

### KNOWN LIMITS
- Expiry is evaluated per `match()` call — a rule that expires mid-run stays usable for steps already approved.
- Workspace attribution shows the workspace fs root name + configured path; cross-workspace aggregation remains out of scope (storage-model ADR).
