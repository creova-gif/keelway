# Keelway — Active Task Registry

> **Purpose**: Centralized, version-controlled index of all engineering tasks across all AI agents and human contributors.  
> **Source of Truth**: Individual task documents reside in `docs/agent-operations/tasks/<TASK_ID>.md`.

---

## 1. Task State Overview

| Task ID | Title | Category | Current Status | Assigned Agent | Last Updated | Branch |
|---|---|---|---|---|---|---|
| **KEEL-HYBRID-001** | Unified Hybrid Model Gateway & Inference API | `MODELS / API` | `READY_FOR_REVIEW` | Google Antigravity (Completed from prior Agent) | 2026-11-11 | `main` (Verified) |
| **KEEL-ENG-001** | Repository-Native Universal Multi-Agent System | `ARCH / GOV` | `COMPLETED` | Google Antigravity | 2026-11-11 | `main` |
| **KEEL-SEC-002** | Linux Command Sandbox Bubblewrap CI Hardening | `SECURITY` | `QUEUED` | Unassigned | 2026-11-08 | `feature/KEEL-SEC-002-bwrap-ci` |
| **KEEL-STUDIO-003** | Manifest Inspection Panel in Web Developer Studio | `UI / STUDIO` | `QUEUED` | Unassigned | 2026-11-08 | `feature/KEEL-STUDIO-003-manifest-view` |

---

## 2. Completed Milestones

- **KEEL-HYBRID-001**: Model Registry, Open-Weight & OpenAI Adapters, Gateway Routing, `/v1/models`, `/v1/chat/completions` (streaming & non-streaming), `/v1/usage` cost accounting, and privacy fail-closed enforcement verified (16/16 tests passing).
- **KEEL-ENG-001**: Canonical `AGENTS.md`, Claude/Antigravity/Devin adapters, unified engineering standards, quality gates, and cross-agent handoff protocol established.

---

## 3. How to Pick Up a Task

1. Review the table above for tasks marked `QUEUED`.
2. Open `docs/agent-operations/tasks/<TASK_ID>.md`.
3. Update status to `IN_PROGRESS` and set your agent name.
4. Follow the Universal Task Execution Protocol in `AGENTS.md`.
