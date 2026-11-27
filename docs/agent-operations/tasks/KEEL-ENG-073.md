# KEEL-ENG-073 — dev-app route-level code splitting

- **Status**: COMPLETED
- **Agent**: Devin
- **Date**: 2026-11-27
- **Branch**: `feat/keel-eng-073-code-split`

## Objective & acceptance

P2 backlog: "bundle code-splitting" — the dev-app shipped as one 1.2 MB
`index-*.js` chunk. Acceptance: split per-view lazy chunks, smaller
eager bundle, tests green, dist rebuilt.

## Implementation

- `App.tsx`: `React.lazy` + `<Suspense>` boundary around the
  tasks/files/record/settings section switch. Eager imports repointed
  to leaf modules (`FilesExplorerSidebar`, `TasksDrawers`) so the lazy
  screens actually leave the main chunk.
- `useUnifiedPlatformState.tsx`: all 9 platform workspace views
  (Agents, Automation, Operations, Docs, Marketplace, Security,
  No-Code, Product, PM) lazy — the IDE stays instant.
- Extracted boot-time helpers out of the lazy graph so they stay in
  the eager chunk: `settings/navigation.tsx` (apply*ToDocument,
  isEditableKeyboardTarget, SettingsSubNav, SETTINGS_SUB_SECTIONS) and
  `settings/rules.ts` (CURRENT_PROMPT_VERSION, isRuleDrifted). Old
  modules re-export for compat — no import-path churn.
- Monaco was already lazy via self-hosted AMD loader — unchanged.

## Result

- Eager `index-*.js`: **1.2 MB → 484 KB** (~60%); ~720 KB deferred
  across 15 view chunks (Marketplace/Docs 142K, Agents 135K,
  Automation/Ops 114K, Settings 100K, LiveExecutionDrawer 39K, Tasks
  29K, Record 28K, PM/Product 23K, Files 22K, NoCode 12K, ...).
- `vite build`: green; `tsc --noEmit`: clean.
- Tests: post-view-switch sync `getBy*` queries legitimately hit the
  Suspense loading state — converted to `findBy*`/`findAllBy*` where
  needed (63 sites via script + 3 files fully converted), and
  `asyncUtilTimeout` raised 1s→4s in `src/test/setup.ts` for lazy
  chunk + hydration under parallel load. **130/130 green**.

## Residual

- `P10ApprovalCard` kept eager (safety-gate UX in the review drawer,
  outside the children Suspense boundary).
- Shared eager chunk still carries React/Radix/api libs (~480 KB);
  a vendor `manualChunks` split would improve caching but not bytes.
