# KEEL-DSN-002 — Settings design in Paper (Phase 2, first unit)

**Status**: `IN_PROGRESS`
**Owner**: Devin
**Date**: 2026-11-22
**Branch**: `feature/keel-dsn-002-settings-design`
**Paper**: `Keelway — Brand Kit & Homepage` → page `17 - Settings` (`p-H-0`)
**File**: `https://app.paper.design/file/01M7T488WTKN3AQNQ2K9DB40TN/p-H-0`

## Objective

Design the full Settings surface in Paper before any implementation, per the ratified
Phase-2 order (Settings first — biggest gap, most-used) from KEEL-DSN-001.

Settings is the largest under-designed surface: eight subsections, several dense
tables, one modal, and a subsection rail — none previously artboarded.

## Artboards produced (this increment)

| Artboard | Node | Covers |
|---|---|---|
| `17.1 — Settings anatomy & IA` | `2AQ-0` | Shared panel grammar every subsection inherits: subsection rail (brass leading rule on active, never a filled chip), sentence-case section header + one-line purpose + right-side quiet status, hairline rows, dot+text status, disclosures for detail, action row (primary/secondary/tertiary). Includes the eight-subsection spec strip mapping each panel's payload. |
| `17.2 — Permissions & Manifests` | `2CG-0` | Deep-dive 01. Sections in authority order: Standing Allow-always rules table (capability · scope · grant meta · Revoke) → immutable P-10 invariants band on `--surface` (always-P-10 scopes, 2-of-2 quorum, ledger contract) → manifest registry table (signature dot+text, autonomy text, kill-switch toggle) → validator disclosure with collapsed `keelway.agent/v1` preview. |
| `17.3 — Governance & Keys` | `2EL-0` | Deep-dive 02. Honesty-first ordering: live persistence read banner → DLP policy checkboxes → daily/monthly USD spend meters (measured-vs-cap, cap-hit fail-closed note) → scoped key table (prefix only, never full secret) → mint-key modal preview + "shown once at mint" contract note. |

## Design decisions to review

1. **One nav system** — the left rail is the only entry into subsections; no tabs.
   Active = brass leading rule + `--ink` text (matches the app-shell view rail).
2. **Authority-ordered sections** — Permissions orders content by who can change it:
   operator grants, then immutable invariants, then registry, then tooling.
3. **Honesty markers are first-class** — `read live from disk`, `prefixes only`,
   `fail-closed to local`, `No counter yet`-style honesty copy is designed *into*
   the panels, not appended.
4. **Status vocabulary unchanged** — dot + muted text everywhere; a `Revoked` row
   uses `--error` text + dimmed name, no banner.
5. **Kill-switch is a real toggle** in the registry table (right-aligned), matching
   the shipped `KillSwitch` control's semantics; the artboard shows on/off states.
6. **Spend meters** use `--accent` fill on `--surface-elevated` track — meters read
   as instruments, not decorations. The 91% example intentionally shows near-cap.

## Paper ops evidence

- `create_page` → `p-H-0` (page `17 - Settings`)
- `create_artboard` ×3 → `2AQ-0`, `2CG-0`, `2EL-0`
- `write_html` ×4 incremental writes; `update_styles` for `height: fit-content` fix
- `get_screenshot` checkpoints after each artboard (rendered clean, no clipping)
- `finish_working_on_nodes` called on all three artboards
- Token hash remains `3cc7b891` — no token changes needed; new artboards consumed
  existing tokens (`--surface-elevated`, `--accent-ring`, `--r-panel` from Phase 1).

## Completed increment 2 — full Settings coverage + Missing Surfaces page

Owner directive: "design all our keelway screens on paper". Scope expanded from
Settings-only to the full remaining screen inventory.

- [x] 17.4 Models & 4D Routing (`2H0-0`) — OpenCore runtime, VRAM meter, pinned
  weights table, cloud/VPC connectors, dry-run simulator
- [x] 17.5 Network & Egress (`2JZ-0`) — posture, air-gap lock, SC-7 boundary
  checklist, unmeasured-network honesty copy, egress audit preview
- [x] 17.6 Light panels (`2LS-0`) — Appearance / Labs / General / Keyboard in one
  2×2 board (the four lighter panels share one grammar)
- [x] 18.1 P-10 approval card + Tasks run lane (`2O0-0`) — pending (brass ring,
  the one loud state), approved 2-of-2, denied w/ reason, expired; scope +
  quorum + inspect-payload + gate id + expiry; every outcome writes a receipt
- [x] 18.2 Billing & tiers (`2PV-0`) — plan/usage/settlement; tier entitlements
  mapped to governance ceilings; measured-vs-projected labeling; verified-split
  ledger. Open: 4-tier (app) vs 5-tier (website) canonical set
- [x] 18.3 Overlays (`2RP-0`) — onboarding modal (provenance markers kept) +
  command palette (P-10 actions ranked first)
- [x] 18.4 Workspace views + state matrix (`2TC-0`) — Automation / Security /
  Documentation / PM boards + the cross-view state render contract
  (empty/loading/error/offline/denied/P-10-pending × never-rules)

## Paper ops evidence (increment 2)

- `create_page` → `p-I-0` (page `18 - Missing Surfaces`)
- `create_artboard` ×7 → `2H0-0`, `2JZ-0`, `2LS-0`, `2O0-0`, `2PV-0`, `2RP-0`, `2TC-0`
- `write_html` ×7; `get_screenshot` checkpoints (P-10 board verified: brass ring
  pending card reads unmissably; all four outcomes carry receipt copy)
- `finish_working_on_nodes` on all seven
- Token hash unchanged `3cc7b891` — Phase-1 tokens covered all new surfaces
- `SCREEN_INVENTORY.md` updated: every shipped screen now maps to an artboard id
- Increment 3: `18.5` drawers (`2WD-0`) — review-changes (keep/revert receipt)
  + live-execution (SSE lens on the same ledger). The last undesigned surface.

## Remaining gaps (post-Phase-2)

- [ ] 4-tier vs 5-tier billing canonical-set decision (before implementation)
- [ ] Agents registry grid artboard (run detail already covered by 12.4) — optional
- [ ] Owner review of pages 17–18 before Phase 4 wiring — owner approved via proceed

## Out of scope

- Implementation. Phase 4 wires code to `get_jsx`/`get_computed_styles` after
  artboard approval. `SettingsWorkspace.tsx` and the five `settings/*Panel.tsx`
  components are untouched.
