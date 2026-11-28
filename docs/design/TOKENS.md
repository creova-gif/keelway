# Token Reconciliation — Paper ↔ Code

> KEEL-DSN-001 · 2026-11-22 · Companion to `tokens.json` (machine-readable registry).

## Verdict

The three token systems are **already the same system**. Paper's token export
and the code surfaces agree on every core value — Paper was the design source
for maritime v3 (DESIGN.md §8/§9), and the code implemented from it. Phase 1
needed reconciliation, not migration.

| Layer | Paper | dev-app `tokens.css` | website `globals.css` |
|---|---|---|---|
| Canvas | `#08090A` | `--bg-canvas #08090a` ✅ | `--canvas #08090a` ✅ |
| Ink / muted | `#F4F5F5` / `#9BA1A6` | ✅ / ✅ | ✅ / ✅ |
| Accent | `--accent #C9A45C` | `--accent` canonical; `--teal-*`/`--attn-ochre`/`--status-warning` = `var(--accent)` aliases ✅ | `--accent #c9a45c` ✅ (renamed from --brass, KEEL-WEB-004) |
| Accent deep | `#A8854A` | light-theme accent `#a8854a` ✅ | `--brass-deep` ✅ |
| Success / error / info | `#6FAE8E` / `#B0564E` / `#6F87A3` | `--status-ok` / `--red-danger` / `--status-running` ✅ | starboard / port / flag ✅ |
| Fonts | Inter + JetBrains Mono | ✅ | ✅ |
| Control radius | `6px` | `--radius-sm 6px` ✅ | ✅ |
| Warning = accent | `var(--accent)` | `--status-warning #c9a45c` ✅ | shares `--brass` ✅ |

## Deltas found and resolved (2026-11-22, all via live Paper MCP)

| Token | Was (Paper) | Resolution | Paper change |
|---|---|---|---|
| `--rule` | `7%` | Code's `6%` adopted | ✅ `set_tokens` → `rgb(255 255 255 / 6%)` |
| `--surface` | `4.5%` | Code's `4%` adopted | ✅ `set_tokens` → `rgb(255 255 255 / 4%)` |
| `--accent-wash` | `14%` | Code's `12%` adopted | ✅ `set_tokens` → `rgb(201 164 92 / 12%)` |
| `--surface-elevated` | absent | Added `8%` | ✅ `create_tokens` |
| `--rule-strong` | absent | Added `12%` | ✅ `create_tokens` |
| `--accent-ring` | absent | Added `35%` (website focus-ring role) | ✅ `create_tokens` |
| `--r-panel` | absent | Added `10px` — product panels; `--r-tile 14px` now marketing-only | ✅ `create_tokens` |
| `--dim` | `#5D6268` | **Exception recorded** — website keeps `#8a9096`: `--dim` there colors content-bearing captions (dates, prices, placeholders) where 3.5:1 decorative-only dim would fail AA | — |
| `--fs-body` | `17px` | **Resolved** — website `.kw-body` adopted 17px (`1.0625rem`), 2026-11-23 | — |
| `--fs-heading`/`--fs-display` | `28/44px` | Resolved by convention — fluid `clamp()` wins; Paper values are 1440-grid reference points | — |

New Paper token hash: `3cc7b891` (was `7101589d`). Paper now carries the full
shared vocabulary — 30 tokens.

## 2026-11-23 update (KEEL-DSN-004) — spacing scale + density pass

A follow-on session added a 6-step spacing scale to Paper (`create_tokens`) to
fix a density/congestion finding: several product and marketing screens read
as cluttered because of uniform thin spacing, border-overuse on cards, and
unrelated views combined onto single boards.

| Token | Value | Role |
|---|---|---|
| `--space-xs` | `8px` | tight control padding |
| `--space-sm` | `14px` | inline/list gaps |
| `--space-md` | `24px` | section padding, card gaps |
| `--space-lg` | `40px` | dashboard/billing outer padding |
| `--space-xl` | `56px` | artboard-level breathing room |
| `--space-2xl` | `80px` | hero/landing sections |

These are **Paper-only** — no `dev-app/tokens.css` or `web-next` globals
equivalent exists yet. Record the sync task when adopted; do not treat the
absence as a drift bug.

New Paper token hash: `f8e761be` (was `3cc7b891`). Paper now carries 33
shared tokens (27 color/type/radius + 6 spacing).

Boards re-spaced in this pass (all applied in Paper, not yet re-exported to
code): Home · Overview (12.8), Agents registry grid (12.7), Agent profile
(12.9), Agent builder (12.10), Billing & tiers (18.2 — also fixed a
3-vs-4-tier content bug, see below), and the former combined board
"18.4 — Remaining views" (split into 18.4a–e: Automation, Security,
Documentation, Project Manager, state matrix — each now a standalone,
spacious board). `12.4 — Agents view · run detail` deliberately kept its
dense IDE-style row heights; only its outer artboard padding was widened.

### Billing tier content fix (same pass)

The pre-existing Billing board (`18.2`) showed 3 tiers ("Solo / Pro /
Enterprise") with no BYOM tier — stale relative to the real 4-tier model in
the marketing site (then `website/src/data/pricing.ts`; now inline in
`web-next/src/app/pricing/page.tsx` post-WEB-055)
(Community / BYOM / Pro / Enterprise). Fixed by renaming Solo → Community and
cloning in a BYOM card. See the `COMPLETENESS_AUDIT.md` correction — the
README (not the website) was the actual source of a false "5-tier" claim,
fixed separately in PR #218.

### Type-system correction (same pass)

52 headline/stat text nodes created across this and the prior session used
`font-weight: 700`, which violates this file's own documented type system
(`--font-sans` is Inter, weights 400–640 only — "precision, not force," per
DESIGN.md §8/§9 and the `--fs-display` token note). All 52 corrected to
`640` via a batched `update_styles` call. No code-side audit was run; if
`dev-app` or `website` use `font-weight: 700` on Inter anywhere, flag it the
same way.

## Naming debt (tracked, not yet renamed)

- dev-app `--accent` is canonical (KEEL-APP-075). `--teal-*` and
  `--attn-ochre` survive only as CSS-var aliases; the Tailwind `teal` scale
  was removed and all call sites migrated to `accent` / `accent-subtle` /
  `accent-ink`.
  zero visual gain.
- website `--brass` — documented alias of `--accent`. Kept: brass is the
  material metaphor in the v3 spec.

## Code-authoritative regions (Paper does not define)

- **Shell geometry**: rail 48 / sidebar 240 / review 520 / inspector 360 /
  statusbar 24 px
- **Density system**: default / compact / comfortable row + control heights,
  coarse-pointer 44px floor
- **Motion**: snap 80 / fast 140 / base 220 / slow 380 ms + three easings
  (codified in DESIGN.md §9, approved on Paper page 07 — the values live in
  code, not as Paper tokens)
- **Diff colors, shadows, control borders, `--fg-disabled`**
- **Light theme**: full parallel token set in `tokens.css` `[data-theme="light"]`
  — Paper is dark-native; light values derive from this mapping. Paper page 04
  board `02.5 — Light-theme reference` (added 2026-11-23) now records the six
  core light values (canvas `#fafafa`, surface `#ffffff`, ink `#09090b`,
  muted `#52525b`, rule `rgba(9,9,11,0.08)`, accent `#a8854a`) — verified
  1:1 against shipped `tokens.css`; the board is documentation of shipped
  reality, not a new design decision. Extended light roles (chrome, dim,
  status colors) remain code-authoritative.

## Sync workflow going forward

1. Design tokens change in **Paper first** (or code-first for code-only regions).
2. Update `docs/design/tokens.json` in the same PR that lands the visual change;
   the `paperContentHash` field records the snapshot reconciled against.
3. `get_tokens` on the Paper file is the export; `tokens.json` is the registry;
   `tokens.css` / `globals.css` are the runtime. Drift = a diff in this file.
