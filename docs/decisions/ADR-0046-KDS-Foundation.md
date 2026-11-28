# ADR-0046: Keelway Design System Foundation — Radix + Tailwind + Maritime Tokens

**Status:** Approved
**Date:** 2026-11-27
**Deciders:** Keelway Engineering (audit KEEL-ENG-074)

## Context

An enterprise UI/UX directive proposed building the Keelway Design System on
shadcn/ui + Base UI, with Radix listed as "an alternative where already
established," and explicitly cautioned: audit the existing implementation
first; do not migrate a working Radix setup merely because a library is newer.

## Audit findings (verified)

- The dev-app already runs Radix primitives (dialog, popover, tabs, tooltip)
  + Tailwind 3.4 + a three-layer token system (`styles/tokens.css` ↔
  `docs/design/tokens.json` ↔ Paper.design board, reconciled KEEL-DSN-001).
- Maritime v3 "Instrument" is the canonical visual system; `--teal-*` and
  `--attn-ochre` are compatibility aliases to `var(--accent)`.
- Only 4 shared primitives exist in `components/ui/` — the coverage gap is
  real, but it is a consolidation problem, not a foundation problem.

## Decision

**KDS foundation = `tokens.css` (primitive→semantic→component) +
`components/ui/` primitives + Radix behaviors + Tailwind layout.**

- Do NOT adopt Base UI or rewrite to shadcn conventions. shadcn/ui is a
  generator pattern whose default look conflicts with the maritime system;
  Base UI duplicates Radix coverage we already have.
- Grow `components/ui/` opportunistically as composite patterns (empty
  states, filter bars, stat cards) recur across views — no big-bang
  migration; screen work extracts shared primitives as it touches them.
- Revisit the decision only if Radix development stalls or a required
  primitive (e.g., combobox virtualization) lands Base-UI-only.

## Consequences

- Zero dependency churn, zero visual regression risk before beta.
- Token layer remains the single source of styling truth; new components
  must consume tokens, never literals (audit UX-001 class of defect).
- Cons: we own our composite components — Radix ships behaviors, not
  styled composites. Accepted: per-view consolidation keeps diffs small.
