# KEEL-REL-070 — Inspectable Agent Execution: TasksWorkspace Wired to `/v1/agent/*`

| Field | Value |
|---|---|
| **Status** | `VERIFIED_COMPLETE` |
| **Category** | `RELEASE / DEV-APP / PRODUCT-TRUTH` |
| **Agent** | Devin |
| **Date** | 2026-11-19 |
| **Branch** | `feature/KEEL-REL-070-live-agent-run` |

## Objective

Close the last demo-state gap in the dev-app: the Tasks workspace rendered
hardcoded execution receipts (`INITIAL_STEP_RECEIPTS` for `task-csp-gate`),
the composer never started a backend run, and P-10 decisions produced local
receipts without calling the approval endpoint. This task wires the
workspace to the governed Autonomous Agent Loop so every visible plan,
receipt, approval, and cancellation is backed by real backend state.

## Implementation

### `dev-app/src/lib/agentLoopApi.ts` (new)
- Typed same-origin client for `POST /v1/agent/run`,
  `GET /v1/agent/status/{id}`, `POST /v1/agent/step/{id}`,
  `POST /v1/agent/approve/{id}`, `POST /v1/agent/cancel/{id}`.
- Preserves the studio auth path (`?token=`, `Authorization: Bearer`,
  `X-Studio-Token`, `credentials: "same-origin"`) and restricts paths to
  `/v1/agent/*` — matching the `platformRuntimeApi` pattern.
- `mapEventsToReceipts` — agent-loop `tool_call`/`tool_success`/`tool_error`
  events → `StepReceiptItem` rows.
- `pendingToProposal` — backend `pending_approval` → `P10ApprovalProposal`
  so live gates flow through the existing approval card (shortcuts,
  announcements, scoped-rule popover) with honest `unbound` model defaults.
- `STEPABLE_TOOLS` + `defaultStepArgs` mirror Studio's operator stepping.

### `dev-app/src/components/screens/TasksWorkspace.tsx`
- Live-run lane (`data-testid="live-agent-run"`): run status, task id,
  event count, policy disclosure, Cancel button, tool-step bar
  (select + JSON args input + Run step), quorum-required notice.
- Composer submit → `runAgentTask`; the agent reply discloses that the plan
  is **keyword-planned, not model-driven**.
- When a live run exists, plan steps, execution receipts, and pending
  proposals derive from `agent_state` (synchronous — no polling).
- `handleProposalDecision` intercepts `live-*` proposals:
  `POST /v1/agent/approve` with explicit `approved` boolean
  (`allow_*` → `true`, `deny` → `false`); scoped-rule decisions pass
  `remember` (scope + model/prompt binding) to the real rules path.
  Backend rejection logs honestly and the card is not marked decided.
- Quorum-gated pending approvals render a notice instead of a
  single-approver card (2-human quorum can't be satisfied by one click).

### `dev-app/src/App.tsx` / `dev-app/src/lib/appStateHelpers.ts`
- `INITIAL_STEP_RECEIPTS` fixture and the `task-csp-gate` injection
  removed — no fabricated execution state ships.

## Honest limits (disclosed, not hidden)

- `/v1/agent/run` builds a **keyword-heuristic plan**; the UI says so in
  the run banner and agent reply.
- `get_state()` returns the latest `recent_events` window; long runs may
  exceed the rendered receipt count (tail-20 cap).
- Quorum approvals surface as a notice only; the quorum-approve endpoint
  remains in Studio for this slice.
- `runtimeReachable=false` still soft-disables send and preserves drafts —
  unchanged, per `p10-approval-safety` gates.

## Tests Executed & Evidence

- `npx vitest run src/__tests__/live-agent-run.test.tsx`:
  **6 passed** — run→hydrate, step→receipts, approve→`approved:true`,
  deny→`approved:false`, cancel→cancelled status, 403→no fabricated lane.
- `npx vitest run` (full dev-app): **117 passed / 24 files** — zero
  regressions including all P-10 safety gates.
- `npx tsc --noEmit`: clean.

## Security notes

- No new endpoint or auth surface; the client reuses the existing
  studio-token path and stays inside `/v1/agent/*`.
- Live approve/deny requires the backend's `APPROVE_AGENT_STEPS` RBAC —
  the UI sends the decision; the backend enforces.
- `remember` payloads flow to the real standing-approval store (audited);
  phone/viewer roles still cannot create them (server-side check).
