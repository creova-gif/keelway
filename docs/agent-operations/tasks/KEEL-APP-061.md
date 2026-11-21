# KEEL-APP-061 — Files workspace: honest empty state (no phantom `core/main.py`)

### TASK HANDOFF RECORD
- **TASK ID**: KEEL-APP-061
- **TASK TITLE**: Files workspace renders honest empty state instead of fetching a hardcoded default path
- **CURRENT STATUS**: READY_FOR_REVIEW
- **LAST AGENT**: Devin
- **DATE**: 2026-11-22
- **BRANCH**: `fix/keel-app-061-files-empty-workspace`
- **HEAD COMMIT**: (pending)

#### OBJECTIVE & ACCEPTANCE CRITERIA
- [x] Empty workspace (zero files) renders "No file open" empty state — verified live on isolated verify-keelway stack (port 58388), ARIA snapshot + PNG in `/tmp/keelway-qa-evidence/09-ide-fixed.*`
- [x] No `fetchContentFn` call for the seeded `core/main.py` default before the workspace tree resolves — new vitest case asserts `fetchContentFn` is never called on an empty tree
- [x] No raw `API error: /v1/files/content?path=... (404)` leak into the status bar on fresh workspaces — zero `API error|main.py` hits in post-fix ARIA snapshot (was 2 pre-fix)
- [x] Non-empty workspaces still open the real first file when the seeded path is absent — existing behavior preserved via `files[0]?.path ?? ""`
- [x] `Open in VS Code` disabled with no file open; `Ln`/`language` footer segments suppressed when `activePath` is empty

#### ROOT CAUSE
Found during live UI verification of the decongestion program (KEEL-APP-052/053/055/056/057). `FilesWorkspace` defaulted `initialActivePath` to `core/main.py` — a Keelway-repo-specific path — and the mount effect issued `fetchContentFn` immediately, before the workspace tree resolved. On an empty workspace, nothing corrected the seed path, so the app opened a dead `main.py` tab and surfaced a raw `HTTP 404` + `API error: /v1/files/content?...` in the status bar. On any workspace lacking that path it produced a spurious 404 before switching to the first real file.

#### WORK COMPLETED & FILES MODIFIED
- `dev-app/src/components/screens/FilesWorkspace.tsx`: added `treeResolved` gate so content fetch waits for the tree attempt; empty-tree branch clears `activePath`/`openPaths`/`seedErrorPath` to `""`/`[]`; empty-state view when `!activePath`; footer shows `No file open` and hides `Ln`/language segments; `Open in VS Code` disabled without an active file
- `dev-app/src/App.tsx`: sidebar `activePath` default `core/main.py` → `""`
- `dev-app/src/__tests__/files-record-settings.test.tsx`: +1 regression test (empty workspace → empty state, zero tabs, editor absent, VS Code button disabled, `fetchContentFn` never called)
- `core/dev_app_dist/`: rebuilt bundle

#### TESTS EXECUTED & EVIDENCE
- `npx tsc --noEmit`: clean
- `npx vitest run src/__tests__/files-record-settings.test.tsx`: 12 passed
- `npx vitest run`: 120 passed (24 files) incl. all axe WCAG 2.2 AA gates
- `npm run build`: green, `dev_app_dist` regenerated
- Live verify-keelway (fresh instance): IDE → Files shows `No file open — select a file in the workspace tree.`; ARIA snapshot zero `API error`/`main.py` hits; `/tmp/keelway-qa-evidence/09-ide-fixed.{png,aria.txt}`

#### KNOWN RISKS & BLOCKERS
- None. Explicit navigation to a path not in the tree still fetches (backend answers honestly) — only the pre-resolution phantom fetch is suppressed.

#### NEXT RECOMMENDED ACTION
- Merge after CI; no follow-up required.
