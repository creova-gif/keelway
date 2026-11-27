# 02 — Product Requirements (verified against repository)

Plan's module table mapped to verified implementation. States:
`VERIFIED` (tests+code), `PARTIAL` (exists, gaps), `MISSING` (absent),
`N/A` (out of scope for sovereign beta).

| Module | Plan ask | Verified state | Beta decision |
| ------ | -------- | -------------- | ------------- |
| Authentication | login, registration, logout, sessions | PARTIAL — launch/role tokens + pairing, no user accounts | Ship token auth; document no-registration as sovereign invariant |
| Dashboard | functional nav + overview | VERIFIED — dev-app 10+ views, status bar, command palette | Ship |
| AI workspace | conversations + model interaction | VERIFIED chat modes + agent loop; PARTIAL persistence | Ship + close persistence gap (P0-1) |
| Model gateway | providers + error handling | VERIFIED — adapters, air-gap, routing_reason disclosure | Ship |
| Conversations | history, persistence, retrieval | PARTIAL — in-memory `InteractiveChatSession.history` | P0 — persist to SQLite |
| Settings | profile + preferences | VERIFIED — settings workspace panels | Ship |
| Security | authorization + data isolation | VERIFIED — RBAC, sandbox, air-gap, token isolation | Ship |
| Error handling | graceful recovery, actionable messages | VERIFIED — error surfaces + honest-state UI labels | Ship |
| Agent workspace | controlled agent execution | VERIFIED — sandboxed loop, P-10 human gate | Ship (P1 scope) |
| File intelligence | secure uploads + doc processing | PARTIAL — workspace FS + ingest routes exist | P1 verify or flag |
| Usage analytics | tokens, requests, consumption | VERIFIED — cost ledger, quota simulator | P1 — expose in UI |
| Team management | orgs + invitations | MISSING — by design | N/A — document limitation |
| Personal AI memory | persistent intelligence | PARTIAL — kbrain memory graph exists | P2 |
| Model training | fine-tuning | PARTIAL — distill pipeline exists (research) | P2 |

## Beta promise (honest scope)

A single-operator sovereign AI studio: local model gateway with
optional signed cloud escalation, sandboxed agent execution with
cryptographic receipts, persistent conversations (post P0-1), and a
self-hostable control plane. No multi-user accounts in beta.

## Non-negotiables (from AGENTS.md invariants)

- Privacy fail-closed for `private`/`air_gap` payloads
- Zero credential material in tapes/logs/commits
- Sandboxed agent execution (no unconfined root)
- Merkle audit integrity
- Every exposed action produces a real outcome — no placeholder UI
