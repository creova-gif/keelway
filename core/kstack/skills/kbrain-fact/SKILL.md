---
name: kstack/kbrain-fact
version: 1.0.0
role: knowledge_curator
description: Record and query scope-governed KBrain memory facts with ACL boundaries and secret-leakage protection.
permissions:
  - read
  - execute_restricted
inputs:
  key: Stable fact key (e.g. arch.storage_engine)
  statement: Fact statement to record
  scope: agent, project, or org ACL scope
outputs:
  fact_id: Persisted fact identifier
  scope: Effective ACL scope applied
  matched: Matching facts returned on query operations
---

# KStack KBrain Fact Skill (Knowledge Curator Role)

## Overview
Records and queries workspace knowledge via `/v1/kbrain/fact` and `/v1/kbrain/facts` — scope-governed facts enforced by an ACL boundary (agent ≤ project ≤ org) with pre-storage DLP secret blocking and P-10 conflict resolution.

## Execution Rules
1. A `SecretLeakDetectedError` (HTTP 422) is a hard stop — never retry the same statement with secrets merely obfuscated.
2. Facts are scope-governed: a caller may only read facts at or below its max scope, and write at its declared scope. Do not report facts beyond the caller's boundary.
3. A conflicting fact requires P-10 resolution — surface the conflict, never silently overwrite.
4. Record provenance (`provenance_uri`, `provenance_reason`) on every fact; a fact without provenance is weaker evidence.
