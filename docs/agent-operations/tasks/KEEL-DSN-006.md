# KEEL-DSN-006 — Paper 13.3 gated-state conformance: toasts, pinned P-10 rows, /ide inspector gate

- **Status**: READY_FOR_REVIEW
- **Agent**: Devin
- **Date**: 2026-11-23
- **Branch**: `feature/keel-dsn-006-workspace-gates`
- **Paper source**: file `01M7T488WTKN3AQNQ2K9DB40TN`, page `13 - Interface Specs` (p-D-0, frame 13.3; token contentHash `f8e761be`)

## Objective

Ship the three 13.3 workspace-spec clauses flagged in KEEL-DSN-005: the toast system, the `/agents` pinned decision row, and the `/ide` gated state (P-10 card pinned in inspector + editor dims 60%).

## What changed

| Spec clause | Change |
|---|---|
| 13.3 dialogs/notifications — "toasts land top-right, 220ms entrance, never stack more than 3" | New `dev-app/src/lib/toasts.ts` store (module-level external store: `pushToast`/`dismissToast`/`useToasts` via `useSyncExternalStore`, `MAX_VISIBLE = 3` cap with newest-wins eviction, 6s auto-dismiss) + `ToastViewport.tsx` (fixed top-right `z-50`, `kw-fade-fast` entrance = `--dur-base` 220ms, per-tone glyphs from the DSN-004 alphabet: `✓` ok / `✗` danger / `●` gated-accent / `ⓘ` info). Mounted once in `App.tsx`; wired triggers: P-10 decision submit (`handleProposalDecision` → "P-10 approved — receipt sealed" / "P-10 denied — run aborted" with `seq N · decision` detail) and docs save (`Doc sealed to record`) |
| 13.3 `/agents` run detail — "decision row pinned, never scrolls away" | `LiveExecutionDrawer.tsx`: the `awaiting_p10_approval` gate block (ochre card with Approve/Deny + RBAC tooltip) moved ABOVE the unbounded `role="log"` SSE event tape and made `sticky top-0 z-10` — previously it rendered below the log and scrolled away as events accumulated |
| 13.3 `/ide` gated — "P-10 card pinned in inspector, editor dims 60%" | `App.tsx`: new `pendingGateProposal` (first `activeTaskProposals` entry with no receipt) + `ideGateActive` (`platformView === "ide" && activeSection === "files"`). When gated: the shell review drawer force-opens pinned (`reviewDrawerOpen` OR'd with gate; `onToggleReviewDrawer` refuses close while gated) with `P10ApprovalCard` sticky at top above `ReviewChangesContent`, title switches to "P-10 gate — decision required", and the `FilesWorkspace` wrapper dims `opacity-60` with `data-ide-gated` marker |

## Design decisions

- **Dim is visual-only** — spec wording is "editor dims 60%"; no `pointer-events-none`, so the default `task-csp-gate` gated state doesn't break files-section interactions/tests. Mutation blocking stays enforced by the P-10 decision flow itself.
- **Drawer pin guards close** — "pinned in inspector" is honored by refusing the drawer close while `ideGateActive`; the card is also `sticky top-0` inside the drawer content so it survives scroll.
- **Gate condition is receipt-based** — pending = proposal without an entry in `receiptsByProposalId`; resolving the P-10 from either the tasks workspace or the inspector un-dims and un-pins automatically.
- **Toast tone map** — `info` maps to `running` (flag blue) since no `info` tailwind alias exists; glyphs follow the canonical DSN-004 alphabet (`●` reserved for gated/brass only).
- **No test changes needed** — 130/130 pass; the gate defaults to firing on `task-csp-gate` (the shipped `needs_approval` task) which is the intended spec state.

## Verification

- `npx tsc --noEmit` — clean
- `npx vitest run` — 130/130 passed (25 files)
- `npm run build` — `core/dev_app_dist` regenerated (hash change)

## Files

- `dev-app/src/lib/toasts.ts` (new)
- `dev-app/src/components/shell/ToastViewport.tsx` (new)
- `dev-app/src/App.tsx`
- `dev-app/src/components/platform/LiveExecutionDrawer.tsx`
- `dev-app/src/components/platform/DocumentationWorkspaceView.tsx`
- `core/dev_app_dist/` (regenerated)

## Still open (Paper-bound or separate lanes)

- **Website utility routes** (`legal`, `blog`, `signup`, `offline`) — separate website task (KEEL-WEB lane).
- **13.4 embedded terminal** — Paper self-flags "spec — not shipped"; sanctioned deferral.
- **"5-tier" pricing in 13.1** — spec drift vs canonical 4 tiers (KEEL-APP-081); Paper needs the correction.
