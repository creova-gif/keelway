---
name: kstack/p10-gate
version: 1.0.0
role: gatekeeper
description: Evaluate and record P-10 human approval decisions for Tier-3 agent actions through the governed approval endpoint with sealed receipts.
permissions:
  - execute_restricted
inputs:
  task_id: Identifier of the pending gated task awaiting human decision
  decision: approve, deny, or allow_always grant scope
outputs:
  receipt_id: Sealed approval receipt identifier recorded on the flight tape
  rule_id: Standing approval rule id when allow_always persisted a rule
  decision_recorded: Boolean confirming the decision reached the ledger
---

# KStack P-10 Gate Skill (Gatekeeper Role)

## Overview
Routes Tier-3 (high-risk) agent actions through the human approval gate. A P-10 decision is a governance event: it is recorded on the Merkle flight tape, produces a sealed receipt, and — when scoped — persists a standing approval rule bound to the granting model and prompt version.

## Execution Rules
1. Never auto-approve. The skill may only carry a human's explicit decision to the gate; it cannot manufacture one.
2. A missing, revoked, or model/prompt-mismatched standing rule must resolve to "requires approval" — fail closed, never fail open.
3. `allow_always` persists via `POST /v1/approval-rules` and binds the rule to the current `model_id` and `prompt_version`; drift pauses the rule until reconfirm.
4. Every decision emits an audit event and returns its receipt. If the API rejects the decision (RBAC, unsafe scope), surface the denial — do not retry as a different principal.
5. On API unavailability, report the action as still pending. Never represent an unrecorded decision as granted.
