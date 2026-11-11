# Keelway — Security Standards & Invariants

> **Status**: Enforced Specification  
> **Security Classification**: Enterprise Sovereign Standard

---

## 1. The 13 Keelway Security Invariants

All agents, developers, and pull requests must verify compliance with the following thirteen non-negotiable security invariants:

### Invariant 1: Authentication & Authorization (RBAC)
All public and internal endpoints (except public documentation and health probes) require authenticated Principals (`Bearer <token>`). Tokens are stored as one-way SHA-256 hashes with constant-time comparison. Permissions (`EXECUTE_AGENT`, `READ_WORKSPACE`, `APPROVE_TIER3`, etc.) are evaluated before route execution.

### Invariant 2: Privacy Fail-Closed
When a request is marked `is_private=True`, `air_gap=True`, or is originated from an air-gapped tenant space, cloud egress is structurally blocked. Any attempt to route private tokens to external proprietary APIs must raise `AirGapViolationError` (HTTP 403). Fallback to external cloud models is strictly prohibited.

### Invariant 3: Credential Redaction at Ingestion & Persistence
API keys (`sk-...`, `ghp_...`, Bearer tokens), private certificates, passwords, and `.env` variables are systematically scrubbed by `core.security.redact` before write operations to flight recorder tapes, audit records, or telemetry streams.

### Invariant 4: Command Sandbox Isolation
Subprocess and tool execution (`run_command`) must run inside OS-confined sandboxes:
- **macOS**: Seatbelt sandbox profiles restricting write access strictly to designated worktree directories.
- **Linux**: Bubblewrap (`bwrap`) unprivileged user namespaces with mounted read-only system roots and isolated temporary filesystems.
Unconfined root execution is refused.

### Invariant 5: Three-Tier Autonomy Gate
- **Tier 1 (Safe / Autonomous)**: Read-only workspace analysis, code search, AST linting, local inference.
- **Tier 2 (Governed / Monitored)**: File modifications, test runs within designated branch worktrees.
- **Tier 3 (High-Risk / Blocked)**: Network requests outside local network, git commits/pushes to remote repositories, shell execution with elevated permissions, production deployments. Requires signed human cryptographic approval nonce.

### Invariant 6: Merkle Audit Trail Integrity
All audit entries are chained using SHA-256 hashes (`previous_hash`, `entry_hash`). Any modification, insertion, or deletion of past entries invalidates the cryptographic chain.

### Invariant 7: Safe Error Disclosure
Public API responses must never leak internal stack traces, local filesystem paths, environment variables, or SQL queries. All exceptions must be normalized via `core.security.error_disclosure.public_inference_detail`.

### Invariant 8: Least-Privilege Service Credentials
External provider credentials (OpenAI, Anthropic, Google) are never passed down to sandboxed child commands or agent execution environments.

### Invariant 9: No Unsandboxed Code Execution from LLM Outputs
Untrusted model outputs (code blocks, shell commands, scripts) must never be passed to `eval()`, `exec()`, or executed in the host process. Execution is permitted only through the sandboxed runner.

### Invariant 10: Path Traversal Prevention
All file reads, writes, and workspace operations are validated against worktree boundaries using `os.path.realpath`. Path escapes (`../../etc/passwd`) are rejected with HTTP 400.

### Invariant 11: Rate Limiting & Resource Exhaustion Protection
Streaming connections and LLM completions have enforced `max_output_tokens` bounds, idle socket timeouts, and memory limits to prevent Denial of Service (DoS).

### Invariant 12: Tool Execution Authorization & Manifest Validation
Agents can only execute tools explicitly declared and authorized in their signed Agent Manifest (`docs/spec/agent-manifest-v1.md`). Undeclared tool calls are refused and audited.

### Invariant 13: Sealed Release Packaging & SBOM Integrity
Production binaries and container images must include a verified Software Bill of Materials (`keelway-sbom.json`) with pinned dependencies and zero known critical CVEs.

---

## 2. Security Incident Severity & Remediation SLA

- **CRITICAL (SLA: < 4 hours)**: Active credential leak, sandbox breakout, or privacy fail-closed bypass. Code freeze enacted immediately.
- **HIGH (SLA: < 24 hours)**: Authentication bypass or path traversal risk.
- **MEDIUM (SLA: < 7 days)**: Non-exploitable logic flaw or missing audit event.
- **LOW (SLA: Next sprint)**: Minor hardening improvement.
