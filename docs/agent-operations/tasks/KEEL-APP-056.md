# KEEL-APP-056 — Record ledger + onboarding modal decongestion

### TASK HANDOFF RECORD
- **TASK ID**: KEEL-APP-056
- **TASK TITLE**: Record ledger dot-status outcomes + onboarding modal badge budget
- **CURRENT STATUS**: VERIFIED_COMPLETE
- **LAST AGENT**: Devin
- **DATE**: 2026-06-29
- **BRANCH**: feature/keel-app-056-record-onboarding-decongestion
- **HEAD COMMIT**: see PR

#### OBJECTIVE & ACCEPTANCE CRITERIA
- [x] `RecordOutcomeBadge` → dot + text for all 6 outcomes (Passed/Ready/Allowed/Denied/Blocked/Failed — exact labels preserved); used in ledger rows and entry inspector header
- [x] Who column: bordered `actorKind` chip → muted `· agent` suffix
- [x] What column: bordered target code chip → unboxed muted code
- [x] `chain-verified` CalloutBanner untouched — `data-callout-variant` contract + "Chain verified · N entries · no gaps" is the integrity proof, not noise (verified by existing test)
- [x] Integrity expander button kept as the interactive affordance (aria-current/aria-expanded + row arrow-key nav intact)
- [x] Onboarding: doctor status pills → dot + text (Passed/Warning/Failed preserved); `Step N / 2` bordered chip → quiet mono text
- [x] Provenance badges (OpenCore / Locked / No counter yet) kept as SemanticBadge — epistemic honesty contract, only 3 instances
- [x] Zero a11y regressions: dark/light/`dir=rtl` axe gate on RecordAuditLedger green
- [x] Presentational only — no backend/behavior changes

#### WORK COMPLETED & FILES MODIFIED
- `dev-app/src/components/screens/RecordEntryInspector.tsx`: `RecordOutcomeBadge` switch → spec object rendering dot + label
- `dev-app/src/components/screens/RecordAuditLedger.tsx`: actorKind + target cells de-chromed
- `dev-app/src/components/shell/OnboardingModal.tsx`: `renderDoctorBadge` → dot + text; step counter de-chromed
- `core/dev_app_dist/`: rebuilt

#### TESTS EXECUTED & EVIDENCE
- `npx vitest run files-record-settings onboarding-modal`: 14 passed
- `npx vitest run` (full): 24 files, 119 passed — axe WCAG 2.2 AA across dark/light/RTL
- `npx tsc --noEmit` + `npm run build`: clean
- Live screenshot: Record ledger row + inspector drawer verified on isolated `/app` stack

#### KNOWN RISKS & BLOCKERS
- None.

#### NEXT RECOMMENDED ACTION
- Decongestion program complete across all four levels (shell chrome, persistent controls, settings content, ledger/modal). No further passes queued.
