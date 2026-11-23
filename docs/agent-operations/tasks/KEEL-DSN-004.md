# KEEL-DSN-004 — Paper 15 iconography conformance (semantic glyphs + Lucide chrome)

- **Status**: IN_REVIEW
- **Owner**: Devin
- **Date**: 2026-11-23
- **Branch**: `feature/keel-dsn-004-iconography`
- **Source of truth**: Paper `Keelway — Brand Kit & Homepage`, page `p-F-0`
  (`15.1 — Semantic glyph alphabet`, `15.2 — Chrome icons (Lucide)`)

## Doctrine (Paper 15)

**15.1 — semantic glyphs carry state** (tables, tapes, terminals; always with the
word; mono face):

| Glyph | Codepoint | State | Rule |
|---|---|---|---|
| `✓` | U+2713 | SEALED | receipt landed on the tape; starboard green, always with the word |
| `●` | U+25CF | GATED | P-10 human gate; **the only brass-filled state** |
| `✗` | U+2717 | DENIED | refusal is a record; port red, with the word |
| `ⓘ` | U+24D8 | RUNNING | execution in flight; flag blue |
| `○` | U+25CB | QUEUED | intent registered, no action; dim hollow ring |
| `k′` | — | mark/prompt | only glyph allowed to stand alone |
| `#` `↳` `±` `↻` | — | receipt id / hash chain / diff / replay | typographic connectors |

**15.2 — interface chrome = Lucide only**: `terminal`, `shield-check`,
`shield-alert`, `refresh-cw`, `git-branch`, `copy`, `arrow-right`, `check`;
16px default, 1.5px stroke, currentColor/`--muted`; never filled, never
two-tone, never above 24px; decorative icons `aria-hidden`.

## Audit findings

| Surface | Finding |
|---|---|
| website `lucide-react` set | **already canonical** — imports are exactly the 15.2 set |
| website `Header.tsx` hamburger/close | **violation fixed** — hand-authored SVG replaced with Lucide `Menu`/`X`, `aria-hidden`, button keeps `aria-label="Toggle navigation"` |
| website `GoldenThreadStudioShowcase.tsx` | dead code — no imports; also uses stale `--teal-*`/`--bg-*`/`--fg-*`/`--border-*` vars that don't exist in `globals.css` (would render black/broken if ever mounted). Flagged, not wired |
| dev-app `SemanticBadge` | five alphabet violations fixed (below) |
| dev-app `Button` loading glyph | `↻` (replay) → `ⓘ` (running) |
| dev-app egress audit line | `●` → `✓` (verified claim, not a gate) |
| mobile `MissionControlScreen` | `●` sealed/denied → `✓`/`✗` per alphabet |
| `↻ Cycle (Bounded)` (kflow panel) | correct — replay/bounded-cycle semantics |
| ledger `✓` rows, `aria-hidden` glyph spans | already compliant |

### `SemanticBadge` corrections

| Kind | Was | Now | Paper rule |
|---|---|---|---|
| `needs-approval` | `◆` | `●` (ochre→accent classes) | GATED is the only brass-filled state |
| `running` | `↻` | `ⓘ` | `↻` is REPLAY; RUNNING is `ⓘ` on flag blue (`--status-running` #6f87a3) |
| `queued` | `⋯` | `○` | QUEUED is the dim hollow ring |
| `failed` | `✕` (U+2715) | `✗` (U+2717) | DENIED codepoint |
| `done` | `●` | `✓` | `●` is reserved for the brass gate |
| `live` | `●` | `✓` | same — last non-gated `●` removed |

## Flagged — alphabet extensions needed in Paper (not invented here)

Epistemic-honesty marks have no 15.1 entries and were left as-is pending a
Paper update: `▨` simulated, `◇` prototype, `∅` no-counter, `✦` AI,
`▣` OpenCore, `↗` frontier, `⚿` locked, `≈` estimated, `!` reconfirm,
`▲` not-saved. All are typographic/geometric text marks (not drawn icons),
`aria-hidden` + visible-word compliant — but they are invented marks and the
alphabet should be extended in Paper to legitimize or replace them.

## Verified

- `dev-app`: `vitest run` 25 files / 130 tests green; `tsc --noEmit` clean;
  `npm run build` → `core/dev_app_dist` regenerated and committed.
- `mobile`: `tsc --noEmit` clean; `bun test` 12/12 green.
- `website`: `tsc --noEmit` clean.

## Out of scope / follow-ups

- `GoldenThreadStudioShowcase.tsx`: delete or re-port with current token
  namespace when a product surface adopts it.
- `dev-app/tailwind.config.ts` `teal.*` compat map: harmless aliases resolving
  to `var(--accent)`; retire after remaining call sites migrate.
- Paper alphabet extension for epistemic-honesty marks (see above).
