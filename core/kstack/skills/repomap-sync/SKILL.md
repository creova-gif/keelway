---
name: kstack/repomap-sync
version: 1.0.0
role: general
description: Incremental AST symbol extraction, call hierarchy indexing, and KBrain project fact synchronization with zero cloud egress.
permissions:
  - read
inputs:
  max_tokens: Context budget limit for condensed repository map
outputs:
  repo_map: Condensed AST symbol map for prompt augmentation
  total_files: Count of scanned and indexed files
  symbols_indexed: Count of extracted class, function, and method symbols
---

# KStack RepoMap Sync Skill (General Role)

## Overview
Maintains an up-to-date semantic symbol index and condensed repository map using pure-Python AST parsing and deterministic vector projection.

## Execution Rules
1. Never invoke external network sockets or third-party embeddings services.
2. Scrub all credentials and tokens from scanned documentation and source comments before storing in KBrain.
3. Cache symbol digests incrementally to minimize re-indexing latency.
3. Extracted symbols and call hierarchies sync to KBrain only — no extracted repository content leaves the local boundary.
4. Sync records the workspace and index version so stale maps cannot be mistaken for current state.
