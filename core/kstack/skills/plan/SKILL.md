---
name: kstack/plan
version: 1.0.0
role: architect
description: Architectural decomposition, file path planning, and risk blast radius estimation.
permissions:
  - draft
inputs:
  goal: Engineering goal or intent description
  repo_context: Repository structure and recent commits
outputs:
  plan_steps: List of ordered mutation steps
  files_affected: List of target file paths
  blast_radius: Low, Medium, or High
---

# KStack Plan Skill (Architect Role)

## Overview
Decomposes an engineering objective into minimal, deterministic file-level steps without applying mutations.

## Workflow
1. Read the target workspace and examine symbols and imports related to `goal`.
2. Formulate ordered steps: target path, purpose, constraints, and test commands.
3. Compute blast radius based on import graph depth and shared library touched.
4. Output structured plan JSON adhering to `outputs`.
