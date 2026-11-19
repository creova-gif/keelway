---
name: kstack/mesh-verify
version: 1.0.0
role: mesh_operator
description: Inspect edge-mesh peer health and delegation state, and verify delegated executions against their sealed proofs.
permissions:
  - read
  - execute_restricted
inputs:
  action: status, peers, delegate, heartbeat, or prune
  peer_id: Target peer for delegate or heartbeat actions
outputs:
  peers: Live peer inventory with health state
  delegation: Delegation outcome and proof reference for delegate actions
  pruned: Stale peers removed for prune actions
---

# KStack Mesh Verify Skill (Mesh Operator Role)

## Overview
Operates the `/v1/mesh/*` surface: `/v1/mesh/status` and `/v1/mesh/peers` for fleet visibility, `/v1/mesh/delegate` for peer execution, `/v1/mesh/heartbeat` for liveness, and `/v1/mesh/prune` for stale-peer eviction.

## Execution Rules
1. Delegation is a governance event — carry the delegation proof reference back verbatim.
2. A peer missing heartbeats is stale evidence, not dead capacity: report last-seen state honestly before pruning.
3. Prune is destructive within the mesh view — confirm the peer is actually stale per the heartbeat window first.
4. Never represent a locally simulated mesh as real remote peers; state the boundary when the mesh runs in simulation.
