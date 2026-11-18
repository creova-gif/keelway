---
name: kstack/flight-tape-verify
version: 1.0.0
role: auditor
description: Verify Merkle hash-chain integrity of flight recorder tapes and produce sealed verification receipts for agent executions.
permissions:
  - read
inputs:
  trace_id: Optional specific tape segment to verify; omitted verifies the full chain
outputs:
  chain_valid: Boolean Merkle-chain integrity verdict
  first_bad_seq: Sequence index of the first integrity break when invalid
  receipt_sha256: Sealed verification receipt hash
---

# KStack Flight-Tape Verify Skill (Auditor Role)

## Overview
Verifies the append-only Merkle chain backing the flight recorder via `/v1/audit/verify`, and fetches Merkle proofs for individual entries. Any truncation or mutation breaks verification — that break is the finding.

## Execution Rules
1. Verification failure is a security finding, not an error to retry: report the first bad sequence verbatim and stop.
2. Secrets, tokens, and private key material must never appear in skill output, even when present in tape records — surface redacted forms only.
3. A verification receipt is evidence of what was checked at a point in time; include chain length and timestamp so the receipt cannot be replayed as proof of a different chain.
4. If the tape store is unreachable, report UNVERIFIED rather than claiming the chain is valid.
