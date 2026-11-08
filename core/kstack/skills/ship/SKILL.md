---
name: kstack/ship
version: 1.0.0
role: release_lead
description: Release qualification, test gate verification, signed flight tape sealing, and release receipt generation.
permissions:
  - read
  - execute_restricted
inputs:
  target_ref: Git commit or branch to qualify
  required_gates: List of verification gates (unit, e2e, security, live_model)
outputs:
  qualified: Boolean release readiness decision
  passed_gates: List of successfully completed verification gates
  flight_tape_sha256: Cryptographic hash of sealed flight tape
  receipt_id: Unique signed release receipt ID
---

# KStack Ship Skill (Release Lead Role)

## Overview
Validates release readiness against fail-closed engineering gates, seals cryptographic flight tapes, and generates signed release receipts.

## Release Gates
1. Full test suite execution in verified OS sandbox.
2. Zero-secret and zero-leakage DLP audit across modified files.
3. Flight tape tamper detection and SHA-256 seal verification.
4. Gate integrity check: verify all mutating actions obtained human approval.
