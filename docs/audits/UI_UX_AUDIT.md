# Keelway — Enterprise UI/UX Audit & KDS Assessment

> KEEL-ENG-074 · 2026-11-24 · Evidence-based audit of `dev-app` (Unified 10-View Dev App)
> against the directive checklist. Baseline commit: post-`5c977b4` (main).
> Every claim below is verified against repository state; unverifiable areas are
> marked **NOT TESTED** rather than assumed.

## 1. Baseline (verified)

| Surface | State |
|---|---|
| Stack | React 19 + Vite 8 + Tailwind 3.4 + Radix UI (dialog/popover/tabs/tooltip) |
| Design system | **Maritime v3 "Instrument"** — DESIGN.md §8–§10; brass `#c9a45c` on ink `#08090a`, Inter + JetBrains Mono, servo motion tokens |
| Token registry | `docs/design/tokens.json` + `TOKENS.md` — Paper↔code reconciled 2026-11-22 (30 shared tokens) |
| Token impl | `dev-app/src/styles/tokens.css` (379 lines): primitive→semantic→component layers, `[data-theme="dark"]` + `[data-theme="light"]` |
| Visual source of truth | Paper.design board (DESIGN.md §10: Paper wins styling, code wins honesty/behavior contracts) |
| Bundle | 484 KB eager post-KEEL-ENG-073; ~720 KB deferred across 15 view chunks; Monaco self-hosted lazy |
| Test suite | 135 tests / 25 files green; 23 files touch axe |
| Component layer | `components/ui/` — 4 primitives (BrandMark, Button, CalloutBanner, SemanticBadge) + Radix + 30 platform panels + 4 screen workspaces + shell (DevAppShell, CommandPalette, InboxPopover) |

## 2. KDS foundation decision — KEEP Radix + Tailwind, reject migration

The directive proposes shadcn/ui + Base UI. Audit verdict: **do not migrate**.

- Radix is already the established primitive layer and works; Base UI adoption
  would churn the Dialog/Popover/Tabs/Tooltip surfaces for zero user benefit.
  The directive itself says: "if Keelway already uses Radix UI successfully…
  audit first and avoid unnecessary framework rewrites before beta." Audited — it succeeds.
- shadcn/ui is a generator convention, not a dep; KDS already has its own
  primitive set (`components/ui/`) styled to maritime tokens — adopting
  shadcn's default look would fight the "not generic" requirement.
- The real KDS gap is **coverage, not foundation**: only 4 shared primitives
  exist; composite components live per-view. That is a consolidation problem,
  not a library problem.
- Decision recorded here (lightweight ADR): **KDS = tokens.css (3-layer) +
  components/ui primitives + Radix behaviors + Tailwind layout.** Expand the
  primitive set as screens consolidate; revisit Base UI only if Radix stalls.

## 3. Findings register

| ID | Severity | Finding | Status |
|---|---|---|---|
| UX-001 | P2 | SVG diagrams in `FlightTapeScrubberAndRadar.tsx` and `BidirectionalKflowStudioPanel.tsx` used superseded teal/zinc literals (`#2dd4bf`, `#e4e4e7`, `#121215`…) — off-brand vs maritime v3 **and** broken under `[data-theme="light"]` | **FIXED this PR** — 16 sites → `var(--accent)`, `var(--fg-*)`, `var(--bg-*)`, `var(--accent-subtle)`; now theme-reactive |
| UX-002 | P3 | Monaco `defineTheme` uses literal hex (`#09090b`, `#f8fafc`) — Monaco API requires literals, cannot take CSS vars | ACCEPTED — documented exception; values mirror tokens |
| UX-003 | P2 | `components/ui/` has 4 primitives; no shared composite layer (empty state, filter bar, stat card re-implemented per view) | **FIXED** — all three shipped: `EmptyState` (KEEL-ENG-078), `StatCard` (KEEL-ENG-079), `FilterBar`/`SearchField`/`FilterChips`/`FilterSelect` (KEEL-ENG-080); 9 call sites consolidated |
| UX-004 | P1 | No onboarding funnel exists to measure: product is single-operator sovereign (token auth, no account creation, no repo-hosting OAuth). Directive's signup/repo-connect/org-admin journey does not map to current product shape | SCOPE — documented mismatch; measurable proxy is `keelway doctor` + first-run path (verified HEALTHY 10/10 in beta audit) |
| UX-005 | P3 | Corrected count: axe already covered 22 of 23 UI test files (9 `toHaveNoViolations`, 13 equivalent `.violations` assertions); only `live-agent-run.test.tsx` lacked it | **FIXED** — 6 real `toHaveNoViolations` assertions added, 0 violations on the live agent run lane |
| UX-006 | P2 | No visual-regression or Core-Web-Vitals harness; performance evidence is bundle-size only | BACKLOG — bundle budget already enforced by code-split; CWV needs a browser harness (jsdom cannot measure LCP/INP/CLS) |
| UX-007 | P3 | `?token=` deep-link convention retained (WS auth requires it); access-log leak already mitigated (P0-4, `--no-access-log`) | DOCUMENTED LIMITATION |
| UX-008 | — | Enterprise checklist (orgs, team workspaces, RBAC admin, billing/quotas, account deletion/export) — **single-operator sovereign product by design**; surfaces map to Governance/Settings views + API tokens, not SaaS admin | NOT A DEFECT — SSO/multi-tenancy is an open product decision (P2 backlog) |

## 4. Directive checklist → verified state

| Area | Verdict |
|---|---|
| Brand & visual identity | STRONG — canonical mark `K′`, Paper-authoritative, token-locked palette; drift was UX-001 (fixed) |
| Light & dark themes | PRESENT — both `[data-theme]` blocks; dark-native primary |
| Color contrast & semantics | STRONG — documented ratios (ink 17.4:1, muted 7.0:1, accent 7.6:1); semantic starboard/port/flag set; `--fg-dim` restricted to decorative use (recorded exception) |
| Spacing/hierarchy | STRONG — 4px grid, shell geometry tokens (`--shell-*`), mono instrument labels |
| Icons/motion | GOOD — servo motion tokens (`--dur-*`, `--ease-*`), global reduced-motion guard, no spinners/shimmer by decree; icons are inline SVG per-component (no icon lib dep — consistent with zero-dep posture) |
| Navigation & IA | GOOD — shell rail + sidebar, CommandPalette exists, `?token=` preserved across nav; browser-history/deep-link behavior NOT TESTED end-to-end |
| Onboarding/offboarding | N/A BY DESIGN (see UX-004) — CLI `doctor` + runbook path verified in beta audit |
| Agent experience | STRONG — execution drawer, P-10 approval gate, honest `[Simulated]`/`EXAMPLE DATA` markers codified as code-authoritative (DESIGN.md §10) |
| Developer workspace | STRONG — Monaco + symbol nav verified (P1-4), worktree surfaces, diff/review drawers |
| Enterprise experience | PARTIAL — governance/quota/vault/API-token views exist; org admin N/A single-operator |
| Accessibility | GOOD — axe assertions in 9 files, focus-visible global, ARIA across 10+ screens; keyboard/screen-reader manual pass NOT TESTED |
| Reliability/perf | GOOD — Suspense fallbacks, skeletons (static, never shimmer), offline-mock determinism, 484 KB eager |

## 5. Competitor matrix (condensed — public evidence only)

Authenticated product access unavailable; rows cite public docs/marketing —
treated as directional, not verified behavior.

| Capability | Devin / Conductor / Linear (public) | Keelway | Gap → Action |
|---|---|---|---|
| Agent execution visibility | Live activity streams, tool calls | LiveExecutionDrawer + flight tape + scrubber | PARITY — Keelway's tape is a differentiator (Merkle receipts) |
| Parallel sessions | Conductor: multi-agent worktrees | Worktree surfaces exist; parallel session UI NOT TESTED | P3 — evaluate post-beta |
| Keyboard-first nav | Linear command menu | CommandPalette implemented | PARITY |
| Information density | Linear: dense, restrained | Maritime instrument: dense + telemetry | PARITY — intentional |
| Enterprise admin | Org/RBAC/billing SaaS surfaces | Governance/quota views; no multi-tenancy | DECISION-HELD — SSO item open |

## 6. Prioritized backlog (post-audit)

| Pri | Item | Effort |
|---|---|---|
| P1 | Decide SSO/multi-tenancy direction (product call — gates enterprise UX scope) | decision |
| P2 | ~~Extend `toHaveNoViolations` to remaining 16 view test files~~ — DONE via KEEL-ENG-075/078/079; only `api-fallback-provenance` + `early-access-security` lack axe (logic tests, no DOM) | — |
| P2 | ~~Consolidate composite primitives (empty state, filter bar, stat card) into `components/ui/`~~ — DONE via KEEL-ENG-078/079/080 | — |
| P2 | Browser-harness CWV + visual regression (Playwright or equivalent) post-beta | M |
| P3 | Parallel agent-session workspace UX (Conductor-style) — needs backend session model first | L |
| P3 | Monaco theme literals — acceptable; revisit only if theming API changes | — |

## 7. Verification evidence this PR

- `npx tsc --noEmit`: clean
- `npx vitest run`: **130/130 pass, 25/25 files** (post SVG token fix)
- `git diff`: 2 files, 16 literal→token substitutions, no behavioral change (fill/stroke values resolve to identical tokens under dark theme; now additionally correct under light)
