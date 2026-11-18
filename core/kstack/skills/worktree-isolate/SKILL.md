---
name: kstack/worktree-isolate
version: 1.0.0
role: operator
description: Create isolated git worktrees and checkpoints so agent edits land in a disposable boundary with a real rollback path.
permissions:
  - execute_restricted
inputs:
  task_name: Slug identifying the agent task for branch and worktree naming
  goal: Summary recorded against the checkpoint
outputs:
  worktree_id: Created worktree identifier under .keelway/worktrees
  branch: Dedicated task branch for the agent's edits
  checkpoint_id: Pre-edit snapshot usable for restore
---

# KStack Worktree Isolate Skill (Operator Role)

## Overview
Provisions the isolated execution boundary for agent edits: `POST /v1/worktrees` creates a detached worktree plus task branch, and `POST /v1/checkpoints` snapshots pre-edit state — including untracked files — so rollback is real, not aspirational.

## Execution Rules
1. Agent edits must land in the isolated worktree, never directly on the primary checkout. If isolation provisioning fails, do not begin edits.
2. Capture a checkpoint before the first agent mutation; report its id so the caller can restore via `POST /v1/checkpoints/{id}/restore`.
3. Worktree removal is restricted to agent-managed paths; never delete a worktree that contains uncommitted human changes without an explicit instruction.
4. If the workspace is not a git repository or worktree creation is denied, report the boundary as absent — do not simulate isolation by editing in place.
