### TASK HANDOFF RECORD
- **TASK ID**: KEEL-APP-080
- **TASK TITLE**: Files/IDE view — compare detail vs Paper 12.1
- **CURRENT STATUS**: READY_FOR_REVIEW
- **LAST AGENT**: Devin
- **DATE**: 2025-01-01
- **BRANCH**: feature/keel-app-080-files-record-compare
- **HEAD COMMIT**: (pending)

#### OBJECTIVE & ACCEPTANCE CRITERIA
Phase-4 compare of `FilesWorkspace` against artboard 12.1 (`1D2-0`, "IDE view · desktop").
The artboard's declared rules: "13px mono, 1.9 leading, gutter numerals at 20% ink — present,
never loud. Add/remove lines get ±8% washes full-width across the editor. Tabs underline in
brass on the active file only." Footer: `tape synced · egress: local-only · ln 41, col 5 ···
keelway dev · v0.70.0`.

- [x] File tabs underline in brass on the active file only (was: bordered/filled chip — violated 10.1's active-state rule)
- [x] Footer shows real cursor `ln N, col M` — Monaco `onDidChangeCursorPosition` wired (was: `Ln N` only)
- [x] Footer shows real `egress: <mode>` from App `egress.mode` (was: absent)
- [x] Footer shows real `keelway dev · v<version>` from `dev-app/package.json` (was: absent)
- [x] Gutter numerals at dim ink, mono, tabular — already conformant (`provenance-gutter`)
- [x] ±8% add/remove washes — already conformant via Monaco diff decorations + FilesDiffView hunk rows
- [x] P-10 card is the only bordered-accent element — no new accent elements added
- [ ] `tape synced` footer marker — deferred: no tape-sync boolean reaches the Files view today (documented, not faked)
- [ ] Right-rail agent fact panel — deferred: the dev-app inspector rail lives on Tasks/Platform, not Files; wiring it is a surface-structure decision, not chrome

#### WORK COMPLETED & FILES MODIFIED
- `dev-app/src/components/screens/FilesWorkspace.tsx`:
  - `FilesWorkspaceProps.egressMode?: string` added
  - `cursorPos` state + `onDidChangeCursorPosition` subscription (disposed on editor teardown)
  - Active tab: `border-b-2 border-b-accent text-fg`; inactive: `border-b-transparent text-fg-muted` (no fill, no box border)
  - Footer: `ln {line}, col {col}` when cursor known (`ln {line}` fallback in textarea mode), `egress: {mode}`, `keelway dev · v{version}`
  - `MonacoEditorInstance` type: optional `onDidChangeCursorPosition`
- `dev-app/src/App.tsx`: `egressMode={egress.mode}` passed to `FilesWorkspace`
- `core/dev_app_dist/`: regenerated

#### TESTS EXECUTED & EVIDENCE
- `npm run typecheck` — clean
- `npx vitest run` — 24 files / 126 tests passed
- `npm run build` — clean, `dev_app_dist` regenerated

#### KNOWN RISKS & BLOCKERS
- `col` is only tracked in the Monaco path; the textarea fallback reports `ln` alone (honest absence, no fake `col 1`).
- `tape synced` and the right-rail fact panel are documented deferrals — no data source / surface decision exists to wire them without invention.

#### NEXT RECOMMENDED ACTION
- Merge after CI; then run the Record (10.2) compare as the remaining Phase-4 "Compare detail" row.
