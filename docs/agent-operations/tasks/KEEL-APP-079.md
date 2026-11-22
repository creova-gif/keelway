# KEEL-APP-079 — Agent composer deep-dive impl (Paper 19.2)

**Status**: READY_FOR_REVIEW
**Branch**: feature/keel-app-079-composer-deep-dive
**Paper source**: `Keelway — Brand Kit & Homepage` page 19, artboard 19.2
(`35J-0` — "Agent composer deep-dive")

## Scope

The 19.2 board was marked "designed — pending impl review" in
`SCREEN_INVENTORY.md`. This pass wires the composer's real deltas.
The board's footnote: *"visible model/route selector, pre-flight
simulation strip, inline P-10 request inside the thread. Tool calls
always render their scope — no hidden permissions."*

## Changes

- `AgentComposer.tsx`
  - Placeholder → spec copy: *"Describe the change. The agent plans,
    simulates, then asks before anything Tier-3."*
  - Toolbar chips per artboard: `+ Attach files` and `@ file / symbol`
    both open the @-citation flow (the agent reads the workspace FS
    directly — there is no upload endpoint; attach = cite-by-path);
    `/ command` opens the existing slash listbox.
  - New `@` listbox mirroring the slash pattern: lazy
    `fetchCodebaseSymbols`, filters name/path, inserts `@<path>`,
    keyboard nav + Escape parity with the slash menu.
  - Route indicator `local · {activeModelLabel}` + real `Model ▾`
    listbox: lazy `fetchOpenCoreWeights`, selecting calls the existing
    `onSelectActiveModel(modelId, label)` path (same source as
    Settings → Models). Hidden when the handler isn't provided —
    never a dead selector.
  - `Send` → `Plan run` per artboard.
  - Pre-flight strip inside the composer card: heading +
    `simulated, zero tokens`, route line (`local (sovereign)` /
    `cloud (provider)` / `blocked — fail-closed` + model + est.
    cost/latency from the real `explainRouting` result), and the spec
    footnote verbatim. Unavailable state is honest: *"Routing
    simulation unavailable — the run still starts; no estimates
    shown."*
- `TasksWorkspace.tsx`
  - `submitComposerPrompt` is now async: echoes the message, then
    awaits `explainRouting({ taskKind: "agent_run", privacy, bounds })`
    and populates the strip **before** `runAgentTask` fires — pre-flight
    honesty shown before launch, never after.
  - New `onSelectActiveModel` prop threaded to the composer.
  - `airGapEnabled` feeds the sim's privacy level (`private` when
    air-gapped).
- `App.tsx`: passes `handleSelectActiveModel` through — the composer's
  Model picker mutates the same `activeModelId/Label` the workspace
  bar and Settings use.
- `p10-approval-safety.test.tsx`: `/Plan/i` → `/^Plan ·/i` (the plan
  toggle's real name) and `/^Send/i` → `/^Plan run/i` for the new
  spec label.

## Already-conformant (verified, unchanged)

- **Inline P-10 in the thread** — `P10ApprovalCard` renders inside the
  "Conversation and human approvals" column; tool + scope render via
  `pendingToProposal`. The artboard's compact row is the same card.
- **P-10 scope count on the strip** — deliberately omitted: no
  pre-launch API exposes required scopes, and the strip's own footnote
  forbids guessing. Scopes appear on the gate card once planned.

## Verification

- `npm run typecheck` — clean.
- `npx vitest run` — 24 files / 126 tests pass.
- `npm run build` — `core/dev_app_dist` regenerated.
- Two test updates were matcher fixes, not behavior changes:
  `Plan` toggle name was ambiguous once `Plan run` existed.

## Follow-ups

- `+ Attach files` currently aliases the `@` cite flow; if a real
  prompt-context attachment endpoint ships, rewire the chip to it.
- Simulation bounds (`30s`/`$1.00`) are conservative request caps for
  the sim, not tenant policy; thread `fetchGovernancePolicy` caps in
  if the strip should reflect the tenant budget.
