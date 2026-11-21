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

## Remaining in this task

- [ ] 17.4 Models & 4D Routing deep-dive (VRAM meter, weights table, connector cards, dry-run simulator)
- [ ] 17.5 Network & Egress deep-dive (posture, air-gap lock, SC-7 checklist)
- [ ] 17.6 Appearance & Density + 17.7 Labs + 17.8 General/Workspace + 17.9 Keyboard — lighter panels, one combined artboard acceptable
- [ ] User review of 17.1–17.3 before the remaining artboards and any implementation

## Out of scope

- Implementation. Phase 4 wires code to `get_jsx`/`get_computed_styles` after
  artboard approval. `SettingsWorkspace.tsx` and the five `settings/*Panel.tsx`
  components are untouched.
