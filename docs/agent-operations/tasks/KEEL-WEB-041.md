# KEEL-WEB-041 — Interactive terminal session replay + copyable install (homepage)

### TASK HANDOFF RECORD
- **TASK ID**: KEEL-WEB-041
- **TASK TITLE**: Homepage session-replay demo + interactive install command
- **CURRENT STATUS**: READY_FOR_REVIEW
- **LAST AGENT**: Devin
- **DATE**: 2026-11-22
- **BRANCH**: feature/keel-web-041-terminal-demo (pushed as feature/keel-app-061-terminal-demo)

#### OBJECTIVE & ACCEPTANCE CRITERIA
- [x] Live terminal session replay on `/` — visitor runs a scripted k′ session: typewriter command, streamed step lines, mid-run P-10 gate decision (Allow once / Deny), outcome lines sealed green or denied red, replay loop.
- [x] Reduced-motion safe: `prefers-reduced-motion` renders the full pre-gate transcript instantly and lands on the gate.
- [x] a11y: `role="group"` + descriptive `aria-label`, `role="log"` transcript, `aria-live` polite only while running (off when idle/done per kit live-region doctrine).
- [x] Install command copyable: `InstallCommand` client component, `navigator.clipboard`, "✓ copied" feedback, `aria-label="Copy install command"`.
- [x] Grounded in reference-site research (capy.ai, paper.design, factory, linear, conductor, cognition — all Next.js + GSAP/Framer/Lottie live product demos); pattern adapted to Maritime Instrument tokens — no new deps.

#### WORK COMPLETED & FILES MODIFIED
- `website/src/components/site/TerminalDemo.tsx` (new): session replay — phases idle→typing→running→gate→done; PRE_GATE transcript lines land with `kw-land`; gate decision prints seal/denial receipt lines.
- `website/src/components/site/InstallCommand.tsx` (new): flex-row command card + copy button.
- `website/src/app/page.tsx`: FIG 0.2 section between principles and install; static install card replaced by `<InstallCommand/>`.

#### TESTS EXECUTED & EVIDENCE
- `npx tsc --noEmit` (website): clean.
- `npm run build` (website): all routes compile; `/` prerendered.

#### KNOWN RISKS & BLOCKERS
- Task ID reassigned from KEEL-APP-061 (taken by parallel agent's files-workspace task) to KEEL-WEB-041.

#### NEXT RECOMMENDED ACTION
- Merge after CI; optionally add a TerminalDemo variant to `/product` (FIG 1.3).
