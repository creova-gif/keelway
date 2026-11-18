---
name: kstack/modernize
version: 1.0.0
role: engineer
description: Dependency upgrade analysis, deprecated API call site detection, and safe migration path planning.
permissions:
  - read
  - draft
inputs:
  dependency_name: Target package or library name
  target_version: Desired version constraint or semver tag
outputs:
  breaking_changes: List of breaking syntax or behavior modifications
  deprecated_apis: List of culpable call sites in the repository
  migration_steps: Ordered steps to update imports and invocations
---

# KStack Modernize Skill (Engineer Role)

## Overview
Analyzes package and library dependencies, identifies deprecated AST call sites across the codebase, and drafts an atomic migration path.

## Workflow
1. Inspect `pyproject.toml`, `package.json`, or requirements files for current pinned version.
2. Analyze AST call sites and import statements using the target library.
3. Compare against target version breaking changes and deprecations.
4. Draft the minimal, backward-compatible migration plan adhering to `outputs`.
4. Migration plans must preserve durable state: approval rules, governance policy, flight tapes, and vault records survive dependency changes.
5. Version drift that invalidates model/prompt-bound approval rules must trigger reconfirm steps in the migration plan.
