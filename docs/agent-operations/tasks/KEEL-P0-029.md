# TASK: KEEL-P0-029 — Replace Demo-Like Settings With Real, Trustworthy State

## 1. METADATA
- **TASK ID**: KEEL-P0-029
- **CATEGORY**: UI / SECURITY / DEV-APP
- **CREATOR**: Owner directive (P0)
- **ASSIGNED AGENT**: Devin
- **STATUS**: READY_FOR_REVIEW
- **TARGET BRANCH**: `fix/KEEL-P0-029-demo-free-settings`
- **BASE COMMIT**: `1be4ead` (main @ PR #60 merge)

---

## 2. OBJECTIVE & MOTIVATION

The `/app` dev tool presented fabricated state as real: `requestSameOriginDecoded`
silently substituted bundled fixture data whenever a live API call failed, so a
disconnected or erroring backend rendered as a healthy, populated product. A
`hipaa-intake` demo workspace was seeded into the runtime registry on every fresh
install. The P0 requirement: production must never fabricate successful
operations — API failures surface as explicit, actionable errors; bundled
fixtures may only serve explicitly-marked test environments.

---

## 3. BASELINE DEFECTS (documented before editing)

| ID | Severity | Defect |
|---|---|---|
| D-A | P0 | `requestSameOriginDecoded` in `dev-app/src/lib/api.ts` caught *all* failures (network, HTTP 4xx/5xx, decode errors) and returned hard-coded fixture objects in production — indistinguishable from live data. |
| D-B | P0 | `core/platform/rbac_webhooks.py` seeded a `hipaa-intake` example workspace into the runtime registry on startup — presented as real user state. |
| D-C | P1 | API failures were invisible to the user — no error surface existed; consumers `.catch(() => {})`-swallowed rejections by design of the fallback contract. |
| D-D | P2 | `.cursor/skills/verify-keelway/SKILL.md` and `tests/test_phase5_runtime_vault_rbac_webhooks.py` asserted the demo workspace existed — the verification harness itself depended on fake data. |

---

## 4. WORK COMPLETED & FILES MODIFIED

- `dev-app/src/lib/api.ts`: `requestSameOriginDecoded` now throws a typed
  `ApiRequestError` (path, status, message) on non-OK responses, decode
  failures, or network errors. Fixture fallback is gated by
  `shouldUseOfflineFallbackInTest()` — only in test mode *and* only when the
  global `fetch` has not been replaced by a test mock. Every fallback served
  is counted via a listener so the shell can report "offline fixture"
  responses explicitly.
- `dev-app/src/components/shell/DevAppShell.tsx`: tracks the latest
  `ApiRequestError` + fallback-response count; passes both to the status bar.
- `dev-app/src/components/shell/StatusBarEgress.tsx`: persistent
  `role="status"` indicator — `API error: <path> (<status>)` with a title
  directing the user to check the local API and retry. `role="status"` (not
  `alert`) chosen deliberately: it is a persistent indicator, and an alert
  role collided with component-level `getByRole("alert")` assertions.
- `core/platform/rbac_webhooks.py`: removed the `hipaa-intake` workspace seed.
  `default` remains — a real first-run home workspace, not fake data.
- `tests/test_phase5_runtime_vault_rbac_webhooks.py`: expectations updated —
  fresh registry contains `default`, not `hipaa-intake` (23 passed).
- `.cursor/skills/verify-keelway/SKILL.md`: harness no longer asserts the demo
  workspace.
- `dev-app/src/__tests__/settings-and-app.test.tsx`: the Record-ledger test
  now mocks `/v1/audit/verify` and `/v1/audit/merkle/proof/` — it previously
  relied on fabricated fallback data to render entry #1301 (exactly the
  defect this task removes).
- `core/dev_app_dist/`: rebuilt via `npm run build` (Vite outDir).

### Second commit — real permission persistence & enforcement (this round)

- `core/security/approval_rules.py`: `ApprovalRule` gains `bound_model_id` /
  `bound_prompt_version`; `list()` tolerates legacy JSON lacking the new
  fields; new `reconfirm()` persists re-binding.
- `core/api/routes.py`: agent approve path records binding from `remember`;
  new `POST /v1/approval-rules` (Studio grant path) and
  `POST /v1/approval-rules/{id}/reconfirm`, both `APPROVE_TIER3` + audited.
- `dev-app/src/lib/api.ts` / `apiDecoders.ts` / `apiFallbacks.ts`:
  `fetchApprovalRules`, `createApprovalRule`, `reconfirmApprovalRule`,
  `revokeApprovalRule` with real decoders + test-only fallbacks.
- `SettingsPermissionsPanel.tsx`: rules render the persisted backend model;
  drift derived via `isRuleDrifted()`; mutations are async with busy locks,
  server-reconciled state, and inline `role="alert"` errors on failure;
  manifest load/toggle failures surface; inspector starts empty with an
  explicit "Insert example manifest".
- `SettingsWorkspace.tsx` / `App.tsx`: `DEFAULT_SCOPED_RULES` and
  `ScopedPermissionRule` deleted; rules fetched from the API on mount;
  `handleCreateScopedRule` POSTs a real rule; drift badge derived, not
  flagged.
- `tests/test_approval_rules.py`: +2 tests — create/reconfirm/audit coverage
  and legacy-JSON deserialization tolerance.

---

## 5. TESTS EXECUTED & EVIDENCE

- `cd dev-app && npm test`: **23 files / 108 tests passed**
- `cd dev-app && npm run build`: ✓ built in 1.15s (dist freshness gate)
- `pytest tests/test_phase5_runtime_vault_rbac_webhooks.py -q`: **23 passed**
- `ruff check .`: clean (previous run after `rbac_webhooks.py` edit)

---

## 6. ACCEPTANCE CRITERIA

- [x] Production API failure produces a typed error and a visible, actionable
      status — never silent fixture data (`requestSameOriginDecoded` throws;
      status bar shows `API error: <path> (<status>)`).
- [x] Fixtures confined to explicit test environments
      (`shouldUseOfflineFallbackInTest()`; fallback responses counted and
      surfaced, not hidden).
- [x] Fresh install shows no `hipaa-intake` demo workspace; `default` retained
      as legitimate first-run state.
- [x] **Prepopulated permission rules removed.** `DEFAULT_SCOPED_RULES` and the
      fictional `ScopedPermissionRule` model are gone; the panel renders real
      rules from `GET /v1/approval-rules` (persisted in
      `.keelway/approval_rules.json`, durable across restart).
- [x] **Revoke / revoke-all / reconfirm are durable and authorized.** Wired to
      `DELETE /v1/approval-rules/{id}`, and new
      `POST /v1/approval-rules` + `POST /v1/approval-rules/{id}/reconfirm` —
      all gated `APPROVE_TIER3` + audit events; no optimistic state (server
      response reconciled; partial failures keep surviving rules and surface
      an inline `role="alert"`).
- [x] **Drift is real, not a UI flag.** `ApprovalRule` persists
      `bound_model_id`/`bound_prompt_version` captured at grant; drift is
      derived from binding-vs-current mismatch, so a model switch pauses
      standing rules automatically.
- [x] **Sample manifest is an explicit option.** Inspector starts empty with
      a labeled "Insert example manifest" button.
- [x] **Plain-language capability labels** (`run_command` → "Run sandboxed
      command", `edit_file`/`write_file` → file-access wording); unbound
      grants honestly shown as "no model binding recorded".
- [x] Automated tests updated and passing (108 dev-app, 46 backend focused
      incl. new create/reconfirm/legacy-JSON coverage).
- [ ] **Remaining scope (explicitly not claimed)**: first-run onboarding,
      full keyboard/SR accessibility pass on this screen, clean-install E2E,
      per-view error states for the ~60 platform panels that still
      `.catch(() => {})` (they now fail visibly in the status bar rather
      than fabricating, but lack panel-level error UI).

---

## 7. KNOWN RISKS & BLOCKERS

- Tests that mock `fetch` now see real errors for any unmocked endpoint — this
  is intentional (the previous behavior was the defect), but future test
  authors must mock every endpoint a view consumes.
- Several consumers still `.catch(() => {})` — with the typed-error contract
  this yields empty panels rather than fabricated ones; per-view explicit
  error states are follow-up work, not this PR's scope.

---

## 8. NEXT RECOMMENDED ACTION

1. Review/merge this branch; then continue the P0 with the permissions UX
   redesign (plain-language categories, progressive disclosure) on a new
   `feature/` branch.
2. Add per-view error/empty states for the consumers that still silently
   catch (App.tsx, SettingsGovernancePanel.tsx data loaders).

## Round 3 — Per-view error states + mission-aligned kskills (commit 451429f, 36b1e3f)

- All 68 production `.catch(() => {})` sites eliminated: platform panels write to their
  existing `errorAlert`/`errorBanner`, FilesWorkspace to its status line, shell loads and
  mutations to the activity log, settings panels to new `role="alert"` blocks.
- Fabricated `SEED_RADAR_AUDIT` blast-radius record removed — the radar shows UNAUDITED
  with an honest empty state until a real audit runs.
- Clipboard "Copied" no longer claims success on write failure; governance policy is
  labeled unsaved defaults when the server fetch fails.
- kstack catalog expanded 8→14 with mission-mapped skills (p10-gate, airgap-verify,
  flight-tape-verify, worktree-isolate, approval-grant, kflow-orchestrate); existing
  eight enriched with Keelway invariants; manifest regenerated; doctor verifies all 14.
- Verified: tsc clean, 108/108 dev-app tests, manifest VALID, kstack suite 8 passed.

## Round 4 — Runtime binding enforcement + first-run onboarding (commits 088e752, a07459e)

- First-run onboarding now auto-opens when `keelway.onboarded` is absent and persists
  the flag on dismissal/completion (previously reachable only via `?onboarding=1`).
- Platform surfaces disclose when they render example data because the API did not
  hydrate — the example chip distinguishes live state from bundled records.
- **Runtime binding enforcement (the P0's deepest gap):** `ApprovalRule` stored
  `bound_model_id`/`bound_prompt_version` at grant time but
  `ApprovalRuleStore.match()` never checked them — a model switch showed "paused"
  in the permissions UI while the agent loop kept auto-approving. Now `match()`
  takes the run's declared `model_id`/`prompt_version`; a bound field must equal
  the run's declared context or the rule stays dormant (fail closed → step pauses
  for human approval). Unbound fields remain wildcards so legacy rules keep working.
  `AutonomousAgentLoop` carries the context from the run payload; the manifest
  path passes it through when the manifest declares one.
- Honest semantics note: binding is *declared* run context (drift protection),
  not verified identity — a caller can claim any context. That matches the
  existing scope-matching trust model: rules narrow grants, they are not a
  principal-authentication boundary.
- New tests: bound rule pauses on model mismatch, auto-approves on exact binding,
  pauses on prompt drift alone, unbound rule matches any declared context.
- Verified: 26/26 approval-rule tests; 85 passed / 10 skipped across
  approval-rules + agent-loop + guard + manifest suites; py_compile clean.
  ruff unavailable on this host (noted for the record).

## Round 5 — Permissions comprehension redesign (commit adbd640)

- Rules table now shows plain-language categories (File access / Command execution /
  Agent access) plus a per-rule sentence stating what the grant allows in this workspace.
- Grant provenance surfaced: bound model, bound prompt, granted-by, granted-on, and an
  honest "No expiry — stays until revoked" (no expiry concept exists in the backend)
  behind a per-row `<details>` progressive-disclosure element.
- Destructive confirms: Revoke and Revoke all arm on first click, execute on second.
- Verified: 109/109 dev-app tests, tsc clean, bundle rebuilt into `core/dev_app_dist`.
