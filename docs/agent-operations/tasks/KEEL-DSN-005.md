# KEEL-DSN-005 — Paper Page 13 "Interface Specs" conformance pass

- **Status**: READY_FOR_REVIEW
- **Agent**: Devin
- **Date**: 2026-11-23
- **Branch**: `feature/keel-dsn-005-interface-specs`
- **Paper source**: file `01M7T488WTKN3AQNQ2K9DB40TN`, page `13 - Interface Specs` (p-D-0, 4 frames; token contentHash `f8e761be`)

## Objective

User completed the Paper kit; audit found the new content is page 13 — a 4-frame spec covering website routes (13.1/13.2), the 10-view workspace state grammar (13.3), and an embedded terminal (13.4). Ship the smallest honest conformance deltas; flag the rest.

## What changed

| Spec clause | Change |
|---|---|
| 13.3 `/marketplace` — "fail-closed: unsigned card shows finding + inert install" | `MarketplaceAndDocsViews.tsx` now renders a `Unsigned — scan finding open` danger chip when `securityVerified` is false (was: hardcoded "SHA-256 + Prompt-Injection Verified" badge regardless), and the Install button renders inert (`disabled`, label `Install (inert)`) for unsigned packages |
| 13.3 `/docs` — "active: dirty-dot on edited doc until sealed" | `DocumentationWorkspaceView.tsx` adds a per-doc `dirtyDocIds` set: `●` (accent) next to the doc title on any edit or new unsaved doc, cleared on save |
| 13.3 global — "API unreachable → status bar turns --error + 'offline — read-only' badge" | `StatusBarEgress.tsx` now renders an `offline — read-only` danger chip when `apiError.kind === "network"` (the existing `API error:` text covers http/decode kinds) |

## Audit — already compliant / flagged, not fixed

- **10 view IDs exist** (`ide, agents, pm, product, automation, marketplace, security, docs, operations, nocode`); ledger outcome cells, denied/error danger tones, `InboxPopover` with ochre unread dot — all compliant.
- **`/ide` gated state** — spec wants "P-10 card pinned in inspector, brass border, editor dims 60%". `P10ApprovalCard` mounts only in `TasksWorkspace.tsx`, not the `/ide` inspector. Structural gap — needs a real inspector gate state, not a cosmetic dim. **Flagged.**
- **`/agents` pinned decision row** — "step washes brass + decision row pinned, never scrolls away" not found. **Flagged.**
- **Toasts** — spec: "land top-right, 220ms, never stack more than 3". No toast system exists; `InboxPopover` covers the notification-center clause. **Flagged.**
- **13.4 embedded terminal** — self-flagged in Paper as "spec — not shipped". Sanctioned deferral, no action.
- **13.1/13.2 website routes** — web-next already has `changelog`, `contact`, `sign-in`; missing `legal`, `blog`, `signup`, `/offline`. Route additions are a separate website task. **Flagged.**
- **Pricing "5-tier" in 13.1** — spec drift vs canonical 4 tiers (KEEL-APP-081 correction, `SUBSCRIPTION_TIERS` backs 4). Code kept at 4; Paper needs the correction, not the code.

## Verification

- `npx tsc --noEmit` — clean
- `npx vitest run` — 130/130 passed (25 files)
- `npm run build` — `core/dev_app_dist` regenerated (hash change)

## Files

- `dev-app/src/components/platform/MarketplaceAndDocsViews.tsx`
- `dev-app/src/components/platform/DocumentationWorkspaceView.tsx`
- `dev-app/src/components/shell/StatusBarEgress.tsx`
- `core/dev_app_dist/` (rebuilt)
