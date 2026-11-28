# Keelway × Paper — Unified Design Program

> **Status**: Ratified Phase 0/1 (2026-11-22, KEEL-DSN-001)
> **Canonical design workspace**: [Keelway — Brand Kit & Homepage](https://app.paper.design/file/01M7T488WTKN3AQNQ2K9DB40TN)
> **Engineering source of truth**: this repository (`DESIGN.md`, `dev-app/src/styles/tokens.css`, `web-next/src/styles/tokens.css`)

---

## 1. What this document is

The approved architecture for how Keelway's UI/UX is designed, synchronized, and
implemented. Ratified by the owner on 2026-11-22 after verification that Paper
MCP integration is real (not assumed). All screen-level design work happens in
the Paper file first; engineering implements from approved artboards.

## 2. Verified Paper integration (not assumed)

The `paper` MCP server is configured and live. Verified capabilities against the
project file `01M7T488WTKN3AQNQ2K9DB40TN`:

| Capability | Tool | Verified |
|---|---|---|
| Open file, list pages, read tokens | `open_file`, `get_tokens` | ✅ 2026-11-22 |
| Read node trees / artboard inventory | `get_tree_summary`, `get_children`, `get_node_info` | ✅ 2026-11-22 |
| Visual review checkpoints | `get_screenshot` | ✅ 2026-11-22 |
| Design → code extraction | `get_jsx`, `get_computed_styles`, `get_fill_image` | ✅ available |
| Author/edit designs | `write_html`, `update_styles`, `set_text_content`, `create_artboard`, `duplicate_nodes` | ✅ available |
| Token authoring | `create_tokens`, `set_tokens` | ✅ available |
| Pages, comments, file management | `create_page`, `list_comment_threads`, `list_resources` | ✅ available |

**Design → code rule**: implementation values are extracted via `get_jsx` /
`get_computed_styles`. Never estimate values from screenshots — screenshots are
for review checkpoints only, per the Paper operating guide.

## 3. Ratified decisions (owner, 2026-11-22)

1. **Authority split**: Paper wins on chrome, layout, and visual system.
   Code wins on honesty markers (provenance/simulated badges, sealed states),
   ARIA contracts, RBAC gates, and backend wiring. Design everything in Paper
   first, then wire it — presentation may change freely; behavioral contracts
   may not be weakened to match a design.
2. **Billing / tier management screens**: in scope, designed now (Phase 2).
   The app implements a 4-tier model (`community | pro | byom | enterprise`,
   `dev-app/src/lib/types.ts`); the retired `website/` app advertised 5 tiers (adds `team`).
   The Paper design must resolve this discrepancy — canonical tier set is a
   Phase 2 design decision that engineering then aligns to.
3. **Phase 2 order**: Settings first (biggest artboard gap, most-used surface),
   then the P-10 approval-card state family, Tasks run lane, onboarding modal,
   then remaining spec-only views (Automation, Security, Documentation,
   PM/Product), then net-new surfaces (command palette, state matrix, billing).

## 4. Current Paper coverage (inventoried 2026-11-22)

| Page | Contents | Coverage |
|---|---|---|
| 01 Homepage | Marketing homepage | Website |
| 02 Product & Components | Component exploration | Shared |
| 03 Onboarding | Marketing site pages: About/Product, Pricing/Resources, Contact/Auth/404 | Website (not in-app onboarding) |
| 04 Brand System | Logo, color (field/accent/signal-flag semantics), type, voice | Complete |
| 05 Sorvex Labs | Parent-brand material | Reference |
| 06 CLI & Terminal | CLI surfaces | Reference |
| 07 Motion & Interaction | Motion spec (codified in DESIGN.md §9) | Complete |
| 08 Mobile | Mobile artboards | Partial |
| 09 Website | Marketing site | Complete |
| 10 Product Screens | 10.1 app-shell anatomy, 10.2 Record/ledger | App — partial |
| 11 Mock Chrome | Chrome mockups | Reference |
| 12 App Interfaces | 12.1 IDE, 12.2 Operations, 12.3 dual chassis, 12.4 Agents run detail, 12.5 Marketplace, 12.6 No-Code Builder | App — 6 artboards |
| 13 Interface Specs | Website routes, utility routes (auth/blog/legal flagged as assumptions), all-10-view specs, integrated terminal spec | Specs — complete |
| 14 Accessibility | Contrast table, never-color-alone rule, focus/keyboard/motion contracts | Complete |
| 15 Iconography | Icon set | Reference |
| 16 Deck & Pitch | Pitch material | Reference |

Notable: the Paper shell rules match the shipped decongestion program exactly —
"status dots replace badges; tier shown as p-10 scope, never as chrome",
"top bar = workspace + journey + gate count only", "what never ships: decorative
buttons, badge counts that open nothing, fake live data". The code converged on
the design; Phase 4 is parity work, not a redesign.

## 5. Screen coverage matrix (summary — detail in `SCREEN_INVENTORY.md`)

Implemented and artboarded: shell anatomy, Record, IDE/Files, Operations,
Agents run detail, Marketplace, No-Code Builder, dual-chassis note.

Implemented but spec-only or missing in Paper: Tasks run lane (the flagship
working surface), Settings (8 subsections — the largest gap), Security view,
Automation, PM, Product, Documentation, in-app onboarding modal, command
palette, P-10 approval-card state family, review-changes drawer, live-execution
drawer.

Needed but not yet implemented: billing/tier management (partial in-app tier
switcher only), full state matrix (empty/error/offline/denied as a designed
system), responsive/mobile breakpoints for workspace surfaces.

## 6. Phased roadmap

| Phase | Scope | Exit criteria |
|---|---|---|
| **0 — Ratify** | This program + decisions committed to `docs/design/` | ✅ This PR |
| **1 — Tokens** | `docs/design/tokens.json` canonical registry; deltas resolved; `DESIGN.md` §10 declares Paper canonical | ✅ This PR |
| **2 — Missing screens** | Artboards in Paper: Settings (8 panels) → P-10 card states → Tasks lane → onboarding modal → Automation/Security/Docs/PM-Product → billing/tier | Every screen in `SCREEN_INVENTORY.md` has an approved Paper artboard |
| **3 — State matrix** | One Paper page: every view × {empty, loading, error, offline, permission-denied, P-10-pending} | State matrix artboarded |
| **4 — Implement** | Per-view: `get_jsx`/`get_computed_styles` → component change → verify-keelway screenshot parity + axe gates | Each view ships via its own KEEL-APP-* PR with parity evidence |
| **5 — Parity gate** | Optional CI check: exported Paper tokens vs `tokens.json` | Drift detectable like a failing test |

## 7. Working agreements

- **Honesty markers are non-negotiable.** `EXAMPLE DATA`, `[Simulated]` hatch
  badges, `Locked`, `No counter yet`, sealed/verified provenance marks, and
  `aria-*`/`role`/`data-callout-variant`/`data-testid` contracts survive every
  visual redesign. A Paper artboard that omits them is implemented *with* them.
- **No fake states.** Paper artboards must design the real state the backend
  can produce; an artboard showing data the API cannot supply is flagged in
  `SCREEN_INVENTORY.md`, not implemented.
- **Checkpoint protocol** (Paper guide): after each new artboard section —
  `get_screenshot` → evaluate spacing, typography, contrast, alignment,
  artboard fit, repetition → fix before continuing.
- **Minimalist rule** (Paper guide): restrained, purposeful, information on
  surfaces rather than cards-inside-cards, no gradients/shadow-decor/generic
  SaaS chrome — consistent with DESIGN.md §8 maritime instrument.
- **One task per branch** per AGENTS.md §5; each Phase-2/4 unit lands as its
  own KEEL-DSN-*/KEEL-APP-* task with doc + board row.
