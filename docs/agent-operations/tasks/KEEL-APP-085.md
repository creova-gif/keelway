# KEEL-APP-085 — View-level congestion audit + Agents view restructure

## Status
READY_FOR_REVIEW

## Objective
Continue the enterprise decongestion program (KEEL-APP-082 → 084): audit all
10 platform views at 1440×900 for stacked sub-chrome and buried primary
content.

## Audit findings (Playwright, all 10 views)

- **Clean post-refactor**: IDE/Tasks, Project Manager, No-Code Builder
- **Dense but coherent instruments**: Product (PRD author + cards + feedback),
  Marketplace (verifier + search + grid), Documentation (KBrain + docs
  studio), Automation (KFlow DAG studio), Security (compliance + scanner +
  OIDC/P-10 quorum), Operations (BYOM + SLOs + co-harness + pricing sim)
- **Worst offender — Agents view**: the 12-agent roster (primary browse
  content) rendered ~60% down the page, buried under five developer
  instrument panels: `FlightTapeDebuggerPanel`,
  `StructuredOutputAndSelfHealingPanel`, `ShadowCacheAndDistillationPanel`,
  `StepDebuggerAndBridgePanel`, `McpInspectorPanel`.

## Change (`dev-app/src/components/platform/AgentsWorkspaceView.tsx`)

Pure JSX reorder — no behavior, prop, or test-contract change:

- **Before**: header → flight-tape debugger → self-healing → teams →
  supervisor → catalog → create → 3 more instrument panels
- **After**: header → **lifecycle agents catalog** → session supervisor
  (conditional; adjacent to the roster it inspects) → **coordinated teams**
  → live drawer → create custom agent → all five instrument panels last

Rationale: the view is named "Agents"; its roster and dispatchable squads
are the browse-first content. Trace/scrub/heal instruments are stage-03
workflow tools — still on the view, still fully functional, but no longer
blocking the roster.

## Hazard found and fixed mid-edit

The supervisor block's inner `{dryRunTrace ? … : null}` shares the
`) : null}` terminator text with the outer conditional — a naive block move
truncated the section and nested the teams grid inside the supervisor's
two-column manifest grid (valid JSX, wrong semantics: teams would render
only while the supervisor is open). Caught by reading the reordered DOM,
repaired by re-seating the leftover closers before the teams section.

## Verification

- `npx tsc --noEmit`: clean
- `npx vitest run`: 130/130 (25 files) — phase11/12/16 instrument tests all
  pass since sections keep their `aria-label`s
- `npm run build`: dist regenerated
- Playwright @1440×900 (`/tmp/v085-agents-after.png`): roster grid is the
  first content under the header

## Remaining backlog
- Record vs Paper 10.2 "Compare detail" — last open compare row.
- Optional follow-ups if usage justifies: Operations pricing-sim placement,
  Security view instrument grouping.
