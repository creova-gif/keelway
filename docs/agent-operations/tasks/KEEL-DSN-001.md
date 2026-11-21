# TASK: KEEL-DSN-001 — Paper Design program ratification + token registry

## 1. METADATA
- **TASK ID**: KEEL-DSN-001
- **CATEGORY**: UI / DESIGN-SYSTEM
- **CREATOR**: Devin
- **ASSIGNED AGENT**: Devin
- **STATUS**: READY_FOR_REVIEW
- **TARGET BRANCH**: `feature/keel-dsn-001-paper-design-system`
- **BASE COMMIT**: `ae07061` (main)

---

## 2. OBJECTIVE & MOTIVATION

Owner directive (2026-11-22): make Paper Design Keelway's central UI/UX
workspace before further frontend work. Phase 0/1 = verify Paper MCP
integration is real (not assumed), commit the gap analysis + screen inventory
+ design architecture into `docs/design/`, reconcile Paper tokens against the
code token layers, and declare Paper canonical in `DESIGN.md`.

Owner-ratified decisions encoded in the program doc:

1. Paper wins on chrome/layout; code wins on honesty markers, ARIA contracts,
   RBAC gates, backend wiring. Design-first in Paper, then wire.
2. Billing/tier management screens are in scope for Phase 2 (must resolve the
   4-tier app model vs 5-tier website discrepancy).
3. Phase-2 order: Settings (8 subsections) first, then P-10 card states,
   Tasks run lane, onboarding modal, then spec-only views.

---

## 3. ACCEPTANCE CRITERIA

- [x] Paper MCP verified live: file `01M7T488WTKN3AQNQ2K9DB40TN` opened via
  `open_file`; 16 pages, 26 tokens, artboards inventoried via
  `get_tree_summary`; `get_screenshot` confirmed working (10.1 shell anatomy
  reviewed)
- [x] `docs/design/DESIGN_PROGRAM.md` — program doc with verified-capability
  table, ratified decisions, Paper coverage inventory, phased roadmap
- [x] `docs/design/SCREEN_INVENTORY.md` — every implemented screen mapped to
  component path, backend deps, Paper status, gap, phase
- [x] `docs/design/tokens.json` + `docs/design/TOKENS.md` — canonical registry;
  all core values confirmed matching; 7 deltas recorded with resolutions;
  naming debt + code-authoritative regions documented
- [x] `DESIGN.md` §10 — Paper declared canonical with authority split
- [x] No code, test, or behavioral changes — docs-only task

---

## 4. AFFECTED FILES & COMPONENTS

- `docs/design/DESIGN_PROGRAM.md` (new)
- `docs/design/SCREEN_INVENTORY.md` (new)
- `docs/design/tokens.json` (new)
- `docs/design/TOKENS.md` (new)
- `docs/agent-operations/tasks/KEEL-DSN-001.md` (new)
- `docs/agent-operations/ACTIVE_TASKS.md` (row)
- `DESIGN.md` (§10 appended)

---

## 5. SECURITY & PRIVACY CONSIDERATIONS

- Privacy Fail-Closed verification required? No (docs-only)
- Credential handling / secret redaction involved? No
- Autonomy Tier Level: Tier 1 Safe (documentation)

---

## 6. VALIDATION & TEST PLAN

Docs-only — no testable code. Verification = the live Paper MCP calls executed
during the audit (file open, page inventory, token export, screenshot) and the
diff review of the four committed files.

---

## 7. IMPLEMENTATION NOTES

### Paper file inventory (verified 2026-11-22)

16 pages. App coverage: 10.1 shell anatomy + 10.2 Record (page 10); IDE,
Operations, dual chassis, Agents run detail, Marketplace, No-Code Builder
(page 12); all-10-view specs + terminal spec (page 13); brand system (04),
motion (07, codified in DESIGN.md §9), accessibility contracts (14).

### Token reconciliation verdict

Paper tokens and both code token layers (`dev-app/src/styles/tokens.css`,
`website/src/app/globals.css`) already implement the same maritime v3 system —
identical canvas, ink, muted, brass accent, semantic signal colors, fonts,
control radius. Deltas recorded with resolutions in `TOKENS.md`: rule 6% vs 7%
and surface 4% vs 4.5% (code wins, both surfaces agree), `--dim` website
divergence `#8a9096` vs `#5d6268` (flagged), `--r-tile` split (10px product /
14px marketing), `--fs-body` 16 vs 17 (flagged), type-scale fluid-vs-static
(harmonized). Naming debt `--teal-accent`→`--accent` documented as alias
pending Phase-4 call-site migration.

### Largest gap discovered

Settings — 8 subsections shipped (`permissions`, `models`, `governance`,
`network`, `appearance`, `labs`, `general`, `keyboard` in
`dev-app/src/lib/types.ts`) with **zero** dedicated artboards; spec rows only.
Also missing entirely: Tasks run lane artboard, P-10 approval-card state
family, in-app onboarding modal, command palette, review/live-execution
drawers, state matrix, billing/tier screens.

---

## 8. NEXT RECOMMENDED ACTION

**KEEL-DSN-002 — Settings in Paper**: artboard the 8 Settings subsections +
overview + key-mint modal in the Paper file using `write_html`/`create_artboard`
against the existing token system, with `get_screenshot` checkpoints per the
Paper operating guide. Reference `SCREEN_INVENTORY.md` §B for component/backend
context. Then KEEL-DSN-003 (P-10 card state family), KEEL-DSN-004 (Tasks lane),
KEEL-DSN-005 (onboarding modal), KEEL-DSN-006 (spec-only views batch),
KEEL-DSN-007 (billing/tier), KEEL-DSN-008 (state matrix).
