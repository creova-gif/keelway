---
name: kstack/cost-ledger
version: 1.0.0
role: economics_auditor
description: Read the platform cost ledger for exact per-model token, spend, and OpenCore-versus-cloud savings accounting.
permissions:
  - read
inputs:
  model_id: Optional model filter
  window: Optional aggregation window
outputs:
  total_cost_usd: Aggregate billed cloud expenditure
  entries_recorded: Number of ledger entries
  per_model: Per-model cost breakdown
  savings_usd: Quantified open-weight savings versus cloud spend
---

# KStack Cost Ledger Skill (Economics Auditor Role)

## Overview
Reads `/v1/usage` — the aggregate economics report over the cost ledger: billed cloud expenditure, entries recorded, per-model accounting, and the quantified savings of open-weight inference over cloud models.

## Execution Rules
1. Figures come from the ledger verbatim — cost is an audit surface, not a marketing claim.
2. `entries_recorded` of zero means no measured spend; report it as such rather than implying free operation.
3. Distinguish billed external expenditure from local $0.00 OpenCore spend — conflating the two fabricates savings.
4. The ledger is append-only evidence; a gap in coverage is disclosed, not interpolated.
