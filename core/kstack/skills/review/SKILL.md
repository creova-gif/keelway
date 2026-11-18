---
name: kstack/review
version: 1.0.0
role: reviewer
description: AST diff analysis, secret leakage detection, and gate integrity auditing.
permissions:
  - read
inputs:
  diff: Unified diff content or patch
  files: Modified file paths list
outputs:
  verdict: APPROVED, CHANGES_REQUESTED, or BLOCKED
  findings: List of security or logic warnings
  gate_integrity_pass: Boolean check on permission gates
---

# KStack Review Skill (Reviewer Role)

## Overview
Inspects proposed unified diffs for security regressions, accidental secret commits, syntax breakage, and policy compliance.

## Verification Gates
1. Secret Scan: Assert no tokens, keys, passwords, or credentials appear in additions.
2. Scope Check: Verify all touched files reside strictly within permitted workspace boundaries.
3. Gate Integrity: Confirm all elevated actions obtained human quorum or approval.
4. Fail-Closed Invariants: verify air-gap classification, secret redaction in tapes/errors, sandboxed execution, and append-only audit writes were not weakened.
5. Standing approval rules are policy: diffs that widen rule scope, remove model/prompt binding, or skip the runtime match are security regressions, not refactors.
