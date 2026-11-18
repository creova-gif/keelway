---
name: kstack/security
version: 1.0.0
role: sec_lead
description: STRIDE threat modeling, NIST SP 800-53 SC-7 air-gap auditing, and SCA vulnerability scanning.
permissions:
  - read
inputs:
  manifest_path: Path to project manifest or code tree
  threat_scope: Target attack surface
outputs:
  threats_identified: Count of identified risk vectors
  airgap_compliant: Boolean compliance with zero-egress policy
  sca_risk_level: LOW, MEDIUM, or HIGH
---

# KStack Security Skill (Security Lead Role)

## Overview
Evaluates the repository against NIST SP 800-53 SC-7 boundaries, STRIDE threat categories, and software supply chain components.

## Audit Checks
1. Zero egress socket verification.
2. Malicious package script inspection.
3. Trust boundary and permission escalation detection.
4. Air-gap and privacy classification are fail-closed: absence of an explicit COMPLIANT audit means non-compliant for gating purposes.
5. RBAC denials must name the required permission; a denial that does not name what was required is a finding.
6. Webhook, token, and quorum surfaces require positive verification — assert rejection of unsigned, replayed, and cross-role requests.
