### TASK HANDOFF RECORD
- **TASK ID**: KEEL-APP-044
- **TASK TITLE**: P4 per-view badge/noise audit & targeted de-noising
- **CURRENT STATUS**: VERIFIED_COMPLETE
- **LAST AGENT**: Devin
- **DATE**: 2025-11-19
- **BRANCH**: feature/keel-app-044-badge-denoise
- **HEAD COMMIT**: 7a5b300 (merge of ddfd9d0)

#### OBJECTIVE & ACCEPTANCE CRITERIA
- [x] Post-P3 live survey of all 10 platform views (isolated stack, screenshots in /tmp/keelway-evidence-p4/view-*.png)
- [x] Distinguish meaningful state badges (P-10, PASS, running, approval, provenance counts) from redundant decorative labels
- [x] Remove redundant per-card `kstack_builtin` chip in KHubAirgapMirrorPanel (header badge already declares `kstack_builtin · N Verified`); chip now renders only for non-builtin source_type exceptions
- [x] Flatten KHub skill cards from bordered `bg-chrome` to recessed `bg-canvas` wells (P3 surface pattern)
- [x] Remove duplicated `Antigravity · Claude Code · Devin · gstack` accent chip in DocumentationWorkspaceView (identical text already in subtitle)
- [x] 111/111 vitest + axe gate green with zero test edits; live screenshots confirm (after-*.png)

#### WORK COMPLETED & FILES MODIFIED
- `dev-app/src/components/platform/KHubAirgapMirrorPanel.tsx`: conditional source_type chip (exception signal only); skill cards flattened to bg-canvas wells
- `dev-app/src/components/platform/DocumentationWorkspaceView.tsx`: removed duplicated agent-name accent chip
- `core/dev_app_dist`: rebuilt bundle

#### TESTS EXECUTED & EVIDENCE
- `npm run test` (dev-app): `Test Files 23 passed, Tests 111 passed` incl. 0 axe violations
- `npm run build`: tsc --noEmit + vite build clean
- Live stack /tmp/keelway-verify-p6 (port 55746): after-Marketplace.png shows 14 wells without repeated source chips; after-Documentation.png shows clean header

#### KNOWN RISKS & BLOCKERS
- None. Badges retained for all real states (P-10 gates, verification, PASS/FAIL, provenance counts, epistemic badges).

#### NEXT RECOMMENDED ACTION
- Merge; larger parked item remains the Conductor-style sidebar-as-primary-surface IA pass.
