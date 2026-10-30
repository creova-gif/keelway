# ADR-003: Universal Model Context Protocol (MCP), OpenTelemetry GenAI Semantic Tracing, and Ephemeral Git Worktree Isolation

**Status:** Approved  
**Date:** 2026-10-30  
**Deciders:** Kora Core Engineering & Research Team  
**Consulted:** Linux Foundation Agentic AI Working Group, OpenTelemetry `gen_ai.*` Standard, Anthropic MCP 2026 Spec

---

## 1. Context & Missing Integrations Landscape

To position Kora as an open-core standard alongside tools like Cursor, Devin, and Claude Code, we must address three critical architectural frontiers:

1. **The $N \times M$ Tool Integration Trap:** Building custom integrations for every database, issue tracker (Linear, Jira), and repository is a dead end. The industry has converged on **Anthropic's Model Context Protocol (MCP)**—now governed under the Linux Foundation's Agentic AI Foundation. Kora must natively consume and serve MCP tools and resources without locking users into proprietary APIs.
2. **Enterprise Observability & Tracing Vacuum:** Enterprise IT and DevOps cannot deploy black-box agents. They require industry-standard **OpenTelemetry GenAI (`gen_ai.*`)** traces capturing input/output token usage, model fallbacks, latency, and tool invocations without leaking private source code or PII.
3. **Multi-Agent Collision in Parallel Work:** When multiple agents run concurrently (e.g., one analyzing PR #42, another fixing a test failure), they stomp on the same working branch and dirty the `.git` HEAD. The solution is **Ephemeral Git Worktree Isolation**, allowing parallel agents to branch and execute without duplicating disk space.

---

## 2. Decision & Architectural Implementations

### Pillar I: Model Context Protocol (MCP) Server & Tool Bridge
* **Native MCP Client (`core/orchestration/mcp.py`):**
  - Connects to any local or remote MCP server via JSON-RPC.
  - Exposes Kora's local Hybrid Memory (`kora-memory://`) and Security Firewall as discoverable MCP Resources and Tools.
  - Allows Kora to instantly interface with any external tool in the ecosystem (PostgreSQL, GitHub, Linear, Figma, Filesystem) through one standardized protocol.

### Pillar II: OpenTelemetry `gen_ai.*` Observability Engine
* **Semantic Trace Provider (`core/security/telemetry.py`):**
  - Generates standardized W3C trace context and spans following OpenTelemetry GenAI conventions:
    - `gen_ai.system`: `qwen` / `anthropic` / `openai` / `google`
    - `gen_ai.request.model` & `gen_ai.response.model`
    - `gen_ai.usage.input_tokens` & `gen_ai.usage.output_tokens`
    - `gen_ai.client.operation.duration_ms`
    - `gen_ai.air_gapped`: boolean flag
  - Prevents data leakage by omitting raw prompt payloads from trace attributes unless explicitly opted-in.

### Pillar III: Ephemeral Git Worktree Isolation Engine
* **Concurrent Agent Sandboxing (`core/orchestration/worktree.py`):**
  - Dynamically provisions disposable Git worktrees (`.kora/worktrees/<task-id>`) attached to the same `.git` storage.
  - Grants each agent a clean, isolated branch (`kora/agent/<task-id>`) to edit files, run tests, and stage commits without colliding with the developer's active workspace.
  - Automatically merges approved changes and prunes the worktree directory upon task completion.

---

## 3. Consequences

### Positive
- **Instant Tool Interoperability:** Zero-code integration with hundreds of enterprise tools via standard MCP servers.
- **Enterprise Observability:** Direct compatibility with Datadog, Dynatrace, Honeycomb, and Splunk without custom collector logic.
- **True Multi-Agent Concurrency:** Multiple autonomous agents can fix bugs, generate PRs, and run test suites simultaneously on one machine without git lockouts.
