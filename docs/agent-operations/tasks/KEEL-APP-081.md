# KEEL-APP-081 — Chat first-class rail view (artboard 12.11)

## Status: COMPLETED

Implements the owner-signed-off 2026-11-23 decision: Chat as its own rail
entry beside Agents (not nested).

- `PlatformViewId` += `"chat"` (11th view); PLATFORM_VIEWS, CommandPalette
  command, GoldenThreadJourneyBar stage map, `resolveMainAriaLabel` updated
- `ChatWorkspaceView.tsx`: session rail (listbox/options, per-status badges)
  over `tasks` + the shared `TasksWorkspace` thread/P-10/composer surface —
  12.11's "pre-flight/P-10 grammar carried over unchanged" literally preserved
- README "Unified 10-View" → "11-View" (all product-facing mentions) +
  platformData fixture copy
- Bonus fix: `test/setup.ts` `Assertion<R,T>` → `Assertion<T>` — pre-existing
  tsc break on main from the jest-dom 8 bump (#272)
- Axe caught and fixed real violations during dev (option↔listbox DOM
  contract) — gate works

Evidence: tsc clean; unified-10view suite 10/10 (incl. axe on Chat view);
full dev-app suite 135/135.
