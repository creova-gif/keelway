---
name: kstack/kflow-orchestrate
version: 1.0.0
role: orchestrator
description: Execute KFlow DAG workflows and multi-agent team plans, returning sealed proof packets for every run.
permissions:
  - execute_restricted
inputs:
  goal: Natural-language objective to plan or execute
  workflow_id: Optional registered KFlow workflow to run directly
outputs:
  run_id: Execution run identifier recorded on the flight tape
  nodes_executed: Count of DAG nodes that ran to completion
  proof_packet_sha256: Sealed proof packet hash attesting to the run
  duration_ms: Wall-clock execution time
---

# KStack KFlow Orchestrate Skill (Orchestrator Role)

## Overview
Drives the KFlow execution engine — `/v1/orchestration/team/plan` decomposes a goal into a role-specialized agent DAG, and `/execute` runs it through the governed pipeline with per-node approvals and sealed proof output.

## Execution Rules
1. Every run must produce a sealed proof packet; a run that cannot seal is reported as unverified, not successful.
2. Long-running executions (multi-minute node work, real test suites) are normal — poll to completion rather than declaring a timeout failure early.
3. Node-level gates still apply: a DAG may pause for P-10 approval mid-run, and that pause is expected orchestration behavior, not a stall.
4. Multi-agent plans never bypass individual human approval — role-specialized nodes inherit the principal's permission envelope.
5. Schedule state is process-scoped; represent intervals and run counts as live registry state, not durable history.
