---
name: kstack/golden-eval
version: 1.0.0
role: eval_engineer
description: Run the golden evaluation benchmark, seal evaluation receipts, and compare drift between candidate and reference runs.
permissions:
  - execute_restricted
inputs:
  model_name: Model identifier to evaluate
  save_receipt: Persist the cryptographic evaluation receipt
  compare_to: Optional prior receipt or model to drift-compare against
outputs:
  receipt_id: Sealed evaluation receipt identifier
  pass_at_1: Pass@1 rate across the benchmark tasks
  drift: Drift comparison outcome when a reference is supplied
---

# KStack Golden Eval Skill (Eval Engineer Role)

## Overview
Executes `/v1/evals/run` — the golden benchmark producing a cryptographic `EvaluationReceipt` — reads `/v1/evals/history` for prior receipts, and uses `/v1/evals/drift/compare` to measure drift between a candidate and a reference run.

## Execution Rules
1. A regression gate reads the sealed receipt, not a verbal summary — quote `pass_at_1` and the receipt id verbatim.
2. `save_receipt=false` produces an unsealed estimate; label it as such and never promote it to a gate input.
3. Drift comparison is evidence, not verdict: report the measured delta and the gate threshold side by side.
4. On evaluator unavailability the run is UNMEASURED — do not carry a prior pass forward as proof.
