---
name: kstack/airgap-verify
version: 1.0.0
role: compliance_auditor
description: Run the air-gap compliance audit and enforce zero unauthorized cloud egress before classified or private workloads execute.
permissions:
  - execute_restricted
inputs:
  workspace_id: Workspace to audit
  scope: Optional check subset to run
outputs:
  verdict: COMPLIANT or NON_COMPLIANT audit outcome
  checks: Per-check results with severity and detail
  attestation_sha256: Sealed attestation hash of the audit record
---

# KStack Air-Gap Verify Skill (Compliance Auditor Role)

## Overview
Executes the `/v1/airgap/audit` boundary check: loopback socket inventory, environment egress surface, and per-check verdicts that gate whether classified payloads may run at all.

## Execution Rules
1. When the audit is unavailable or fails, the verdict is UNVERIFIED — treat as non-compliant and block egress-dependent work. Never infer compliance from a prior pass.
2. Any request flagged `private`, `air_gap`, or classified must not proceed to a cloud model until a current COMPLIANT verdict exists.
3. The audit record is append-only evidence: expose the attestation hash verbatim, never paraphrase or regenerate it.
4. Report per-check results honestly, including skipped or failed checks — a partial audit is not a passing audit.
