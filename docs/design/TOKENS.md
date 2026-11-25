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
