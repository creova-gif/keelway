# Component Inventory — Keelway Design System (KDS)

> KEEL-ENG-077 · 2026-11-27 · Companion to `UI_UX_AUDIT.md` and ADR-0046.
> Census of `dev-app/src/components/` mapped to the KDS architecture
> (foundations → primitives → composites → dev-specific → app patterns).
> Status: SHARED = canonical reusable in `components/ui/`; LOCAL = lives in
> its view/screen, single-consumer or not yet generalized; GAP = needed but
> not yet built.

## Foundations (shared)
| Item | Where | Status |
|---|---|---|
| 3-layer tokens (primitive→semantic→component) | `styles/tokens.css` + `docs/design/tokens.json` | SHARED |
| Motion (`--dur-*`, `--ease-*`, `kw-*` anims, reduced-motion guard) | `tokens.css` | SHARED |
| Focus-visible + programmatic focus | `tokens.css` | SHARED |
| Iconography | inline SVG per component (no icon lib — zero-dep posture) | LOCAL per site |

## Primitives
| Component | Where | Status |
|---|---|---|
| BrandMark | `components/ui/BrandMark.tsx` | SHARED |
| Button | `components/ui/Button.tsx` | SHARED |
| CalloutBanner | `components/ui/CalloutBanner.tsx` | SHARED |
| SemanticBadge | `components/ui/SemanticBadge.tsx` | SHARED |
| Dialog / Popover / Tabs / Tooltip | `@radix-ui/*` (behaviors; styled per call site) | SHARED lib |
| EmptyState | `components/ui/EmptyState.tsx` (title + body + optional action; `role="status"`) | SHARED — debuted KEEL-ENG-078, wired in RecordAuditLedger |
| Skeleton block | `.kw-skeleton` CSS only | SHARED (CSS) |
| StatCard | `components/ui/StatCard.tsx` (label + mono value + optional delta; `framed` knob for cells inside an already-framed `<dl>`) | SHARED — debuted KEEL-ENG-079, wired in QuotaAndPricingSimulator/SettingsModels/SettingsBilling |
| FilterBar / sortable table | per-view | **GAP** |

## Composites
| Component | Where | Status |
|---|---|---|
| CommandPalette | `shell/CommandPalette.tsx` | SHARED (single instance) |
| ToastViewport | `shell/ToastViewport.tsx` | SHARED |
| InboxPopover | `shell/InboxPopover.tsx` | LOCAL (shell-scoped) |
| StatusBarEgress | `shell/StatusBarEgress.tsx` | LOCAL |
| OnboardingModal | `shell/OnboardingModal.tsx` | LOCAL |

## Developer-specific
| Component | Where | Status |
|---|---|---|
| Agent task composer | `screens/AgentComposer.tsx` | LOCAL |
| P-10 human approval card | `screens/P10ApprovalCard.tsx` | LOCAL |
| Live execution drawer/console | `platform/LiveExecutionDrawer.tsx` | LOCAL |
| File explorer sidebar | `screens/FilesExplorerSidebar.tsx` | LOCAL |
| Code editor (Monaco, lazy) | `screens/FilesWorkspace.tsx` | LOCAL |
| Diff + commit panel | `screens/FilesDiffAndCommit.tsx` | LOCAL |
| Task drawers (build logs, review changes) | `screens/TasksDrawers.tsx` | LOCAL |
| Record/audit ledger + inspector | `screens/RecordAuditLedger.tsx`, `RecordEntryInspector.tsx` | LOCAL |
| Flight tape scrubber + radar | `platform/FlightTapeScrubberAndRadar.tsx` | LOCAL |
| Step debugger / bridge | `platform/StepDebuggerAndBridgePanel.tsx` | LOCAL |
| Model/quota panels | `platform/QuotaAndPricingSimulatorPanel.tsx`, `settings/SettingsModelsPanel.tsx` | LOCAL |

## App patterns
| Pattern | Where | Status |
|---|---|---|
| Engineering shell (rail + sidebar + statusbar) | `shell/DevAppShell.tsx` | SHARED |
| Platform view host (10 views, lazy) | `platform/useUnifiedPlatformState.tsx` + 33 `platform/*.tsx` panels | LOCAL per view |
| Settings workspace (sub-nav, permissions, billing, governance, models, system, key-mint) | `screens/settings/*` | LOCAL group |
| Tasks / Files / Records workspaces | `screens/*` (lazy) | LOCAL group |

## Consolidation targets (UX-003 order)
1. `EmptyState` — props: title, body, optional CTA; `role="status"` +
   honest copy per DESIGN.md §4. Highest recurrence.
2. `StatCard` — label + mono value + optional delta; recurs in quota,
   governance, observability panels. **DONE** (KEEL-ENG-079).
3. `FilterBar` — search input + filter chips + sort; recurs in list views.
Extract when next touching each consuming view; never a sweeping rewrite.
