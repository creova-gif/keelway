# Security Threat Model (baseline)

Trust boundaries: Studio/web-console → REST API (token auth + RBAC); agent execution → host FS (fail-closed terminal when isolation unverified); MCP/plugins → agent permissions; webhooks (GitHub secret); model providers (BYOK env keys).

Controls present: RBAC 5-role matrix, MANAGE_KEYS-gated token admin, quorum approvals, entitlements gating, hash-only token storage, CSP headers (frame-ancestors moved to HTTP header), XSS-safe DOM rendering (verified with injected payloads), air-gap audit, fail-closed exec.

Abuse suite per master prompt (IDOR/SSRF/traversal/prompt-injection/MCP spoofing/replay/etc.): NOT YET EXECUTED — see 10-security-test-matrix.csv.
