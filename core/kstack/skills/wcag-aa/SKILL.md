---
name: kstack/wcag-aa
version: 1.0.0
role: accessibility_auditor
description: Enforce WCAG 2.2 AA on rendered surfaces — semantic landmarks, keyboard reachability, focus visibility, zero axe-core violations.
permissions:
  - read
  - execute_restricted
inputs:
  surface: Route or view identifier to audit (e.g. /app, a platform view id)
  mode: audit or remediate
outputs:
  verdict: PASS or FAIL against the zero-violation gate
  violations: axe-core violation list with rule ids and affected nodes
  remediations: Ordered fix list when mode is remediate
---

# KStack WCAG AA Skill (Accessibility Auditor Role)

## Overview
Audits rendered surfaces for WCAG 2.2 AA conformance using the same axe-core gate the dev-app test suite enforces: semantic landmarks, name-role-value, keyboard reachability, focus visibility, live regions, and color contrast. Optionally produces a remediation list.

## Execution Rules
1. The gate is zero axe-core violations — one violation is a FAIL, never a warning.
2. Audit the rendered DOM, not source code; decorative text must not be flagged, and interactive elements must expose an accessible name.
3. Remediation must preserve existing accessible names and live-region behavior — shortening a visible label without updating `aria-label` regresses the contract.
4. Report violations with their axe rule id and node selector verbatim. Never paraphrase a violation into a pass.
5. RTL/bidirectional text and reduced-motion states are part of the audit surface, not optional extras.
