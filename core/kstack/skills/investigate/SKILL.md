---
name: kstack/investigate
version: 1.0.0
role: debugger
description: Systematic root-cause debugging, error trace capture, and minimal defect reproduction without speculative edits.
permissions:
  - read
  - execute_restricted
inputs:
  error_trace: Stack trace or failure log
  failing_test: Optional failing test command or file
outputs:
  reproduced: Boolean indicator if defect was confirmed
  root_cause: Detailed diagnosis of demonstrated defect
  affected_components: List of culpable file paths and symbols
  minimal_repro: Minimal reproducer script or test command
---

# KStack Investigate Skill (Debugger Role)

## Overview
Performs systematic root-cause diagnosis of defects, test failures, and unexpected behaviors. Never propose mutations before reproducing the failure.

## Investigation Discipline
1. Reproduce with the smallest relevant test or script before touching code.
2. Distinguish product defect, invalid test expectation, and environment failure.
3. Inspect stack traces, variable values, and error output inside the verified sandbox.
4. Formulate the minimal repair plan with explicit verification assertions.
