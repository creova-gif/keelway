### TASK HANDOFF RECORD
- **TASK ID**: KEEL-ENG-055
- **TASK TITLE**: dev-app grouped toolchain upgrade — vite 8 + @vitejs/plugin-react 6 + jsdom 31 (supersedes dependabot #144/#145/#147)
- **CURRENT STATUS**: READY_FOR_REVIEW
- **LAST AGENT**: Devin
- **DATE**: 2026-11-22
- **BRANCH**: feature/keel-eng-055-vite8-stack

#### OBJECTIVE & ACCEPTANCE CRITERIA
- [x] vite ^8.3.8 + @vitejs/plugin-react ^6.3.0 resolved together (individually ERESOLVE-blocked: plugin-react@6 needs vite ^7+, plugin-react@4 caps at vite ^6)
- [x] jsdom ^31 — fixed the real test break dependabot hit: jsdom 31 drops trailing whitespace in inline elements from accessible-name computation (`"Chain broken ·#1279"` not `"Chain broken · #1279"`); updated two test regexes to `\s*` tolerance. Real-browser AT unaffected.
- [x] vite.config.ts `__dirname` → `import.meta.dirname` (vite 8 deprecation warning)

#### WORK COMPLETED & FILES MODIFIED
- `dev-app/package.json` + `package-lock.json`: vite ^8.3.8, @vitejs/plugin-react ^6.3.0, jsdom ^31.0.1
- `dev-app/vite.config.ts`: `import.meta.dirname`
- `dev-app/src/__tests__/files-record-settings.test.tsx`: whitespace-tolerant name regexes

#### TESTS EXECUTED & EVIDENCE
- `npm run typecheck`: clean
- `npx vitest run`: **24 files / 126 tests passed** (18.3s)

#### NEXT RECOMMENDED ACTION
- Merge; close dependabot PRs #144, #145, #147 as superseded.
