# KEEL-WEB-001 — web-next scaffold (Next.js + shadcn + canonical tokens)

### TASK HANDOFF RECORD
- **TASK ID**: KEEL-WEB-001
- **TASK TITLE**: Scaffold web-next — Next.js App Router + shadcn-structured UI on canonical tokens
- **CURRENT STATUS**: READY_FOR_REVIEW
- **LAST AGENT**: Devin
- **DATE**: 2026-11-22
- **BRANCH**: feature/keel-web-001-web-next

#### OBJECTIVE & ACCEPTANCE CRITERIA
- [x] web-next/ exists as a standalone npm root (no workspace membership — parent overrides do not leak; create-next-app's installer was bypassed for this reason)
- [x] Next 15.5.6 + React 19 + Tailwind 3.4 + TypeScript strict; App Router, src/ layout
- [x] shadcn structure in place: components.json (new-york, cssVariables, lucide), lib/utils cn(), ui/button.tsx (cva + Radix Slot)
- [x] Canonical tokens wired: src/styles/tokens.css mirrors dev-app canonical --accent* (post-KEEL-APP-075); tailwind config exposes accent/accent-subtle/accent-ink + fg/border/surface/status scales
- [x] Fonts offline-safe: Inter + JetBrains Mono via next/font/local from core/studio woff2 assets
- [x] Landing page uses only honest facts (4 seat tiers + marketplace stream, P-10, Record, fail-closed egress)
- [x] npm run typecheck + npm run build green (static prerender, 102 kB first load)

#### WORK COMPLETED & FILES MODIFIED
- web-next/: full scaffold (package.json, tsconfig, next/postcss/tailwind configs, tokens.css, globals.css, layout, page, Button, cn, components.json, fonts, .gitignore)
- docs/agent-operations/tasks/KEEL-WEB-001.md, ACTIVE_TASKS.md

#### TESTS EXECUTED & EVIDENCE
- npm run typecheck: clean
- npm run build: clean — / prerendered static

#### KNOWN RISKS & BLOCKERS
- tokens.css is a copy, not a shared import — drift risk until a shared package exists; documented in tokens.json follow-ups
- Not yet wired into CI (website-devapp-and-sdks) or Vercel — follow-up when surface count grows

#### NEXT RECOMMENDED ACTION
- Port website pages or build app-shell screens per Paper inventory.
