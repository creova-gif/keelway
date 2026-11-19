---
name: kstack/finops-forecast
version: 1.0.0
role: finops_analyst
description: Forecast OpenCore local-inference savings versus BYOM external API spend using the platform cost ledger and quota simulator.
permissions:
  - read
inputs:
  window_days: Lookback window for usage aggregation
  projected_tokens: Optional forward token volume to price
outputs:
  local_spend_usd: OpenCore spend for the window
  external_spend_usd: BYOM/vendor spend for the window
  savings_usd: Quantified delta between the two paths
  projection: Forward cost estimate at the projected volume
---

# KStack FinOps Forecast Skill (FinOps Analyst Role)

## Overview
Reads `/v1/usage` economics — total billed cloud expenditure, entries recorded, and per-model cost accounting — plus the quota/pricing simulator to quantify the savings of OpenCore local inference versus BYOM external API spend, and to project forward cost at a given token volume.

## Execution Rules
1. Report ledger figures verbatim — billed expenditure and entry counts come from the cost ledger, never estimated.
2. When usage data is empty or the ledger is unavailable, report spend as unmeasured — never fabricate a savings figure.
3. Paid-tier token markup is 0% — a projection that assumes markup contradicts the published commercial model and must not be emitted.
4. Local inference is costed honestly: $0.00 vendor spend is real for OpenCore weights, but note hardware amortization is out of ledger scope.
