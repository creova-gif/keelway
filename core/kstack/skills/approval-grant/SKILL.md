---
name: kstack/approval-grant
version: 1.0.0
role: policy_admin
description: Manage standing approval rules — scoped, model-and-prompt-bound grants that let matching agent actions run without re-asking.
permissions:
  - execute_restricted
inputs:
  tool_name: Tool the grant covers (edit_file, write_file, run_command)
  scope: Exact command or relative path glob the grant is limited to
  model_id: Model the grant is bound to
  prompt_version: Prompt version the grant is bound to
outputs:
  rule_id: Persisted standing rule identifier
  revoked: Boolean outcome for revoke operations
  drifted: Boolean flag when a rule's binding no longer matches the active model/prompt
---

# KStack Approval Grant Skill (Policy Admin Role)

## Overview
Manages durable standing approvals via `/v1/approval-rules`. A grant is persisted policy — it survives restarts, is recorded in `.keelway/approval_rules.json`, and is enforced at runtime by exact tool and scope match.

## Execution Rules
1. Scopes must be explicit and safe: unscoped grants and patterns reaching `.keelway`, `.kora`, or `.git` are rejected by the store — do not attempt to work around the rejection.
2. Every grant binds to the granting model and prompt version. When either drifts, the rule pauses; reconfirm via `POST /v1/approval-rules/{id}/reconfirm` rather than recreating it.
3. Revocation is durable (`DELETE /v1/approval-rules/{id}`) and takes effect at the next runtime match — a revoked rule must cause the action to return to the approval queue.
4. List state reflects the store only. Never present a locally assumed or cached rule as granted when the API is unreachable.
5. All create, reconfirm, and revoke operations carry an audit event; unauthorized principals must receive the denial, not a silent no-op.
