---
name: kstack/qa
version: 1.0.0
role: qa_lead
description: Test execution, failure reproduction, and regression verification in restricted sandboxes.
permissions:
  - execute_restricted
inputs:
  test_command: Command line string for test runner
  expected_outcome: PASS or FAIL reproduction
outputs:
  passed: Boolean test outcome
  exit_code: Process return status
  duration_ms: Wall-clock test execution time
  stdout_summary: Truncated test output
---

# KStack QA Skill (QA Lead Role)

## Overview
Executes test suites within restricted workspace sandboxes, captures exit status, and certifies reproduction or resolution.

## Execution Rules
1. Never invoke network egress unless explicitly configured.
2. Terminate immediately upon test failure when in fail-fast mode.
3. Record duration, exit code, and test stdout in sealed execution proof.
