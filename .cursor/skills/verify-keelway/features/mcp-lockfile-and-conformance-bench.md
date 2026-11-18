# Feature Verification: Cryptographic MCP Lockfile, Rug-Pull Firewall & Conformance Benchmark (`KEEL-LOCK-027`)

## Scope
Verifies Phase 20 end-to-end across `:7420/app` (`Marketplace` workspace -> `McpLockfileAndBenchPanel`), Sovereign CLI (`keelway lock` & `keelway bench`), and SQLite WAL persistence (`mcp_merkle_lockfiles`, `mcp_lock_verifications`, `skill_conformance_benchmarks`).

## Cold Headless Chromium + CLI + SQLite WAL Flow
1. Launch isolated `:7420/app` instance via `node .cursor/skills/verify-keelway/scripts/control-keelway.mjs launch --state-dir /tmp/keelway-verify-p20`.
2. Switch to **Marketplace** workspace (`Marketplace`), pin workspace MCP tools (`PINNED`, `merkle_root_sha256`), verify clean lockfile (`LOCK_VERIFIED`), then trigger a Rug-Pull / Poisoning check (`DRIFT_RUG_PULL_BLOCKED` / `POISONING_BLOCKED`), capturing `01-marketplace-mcp-lockfile-firewall.png` + `.aria.txt`.
3. Switch to **Agent & Skill Conformance Benchmark** tab, execute a benchmark run (`PASS_CERTIFIED`, `cert_sha256`), capturing `02-marketplace-conformance-bench-certified.png` + `.aria.txt`.
4. Query CLI `keelway lock list --json` and `keelway bench runs --json` against the same isolated `platform_runtime.db` and inspect SQLite WAL tables (`mcp_merkle_lockfiles`, `mcp_lock_verifications`, `skill_conformance_benchmarks`) to confirm Merkle hashes, zero unredacted secrets, and conformance receipts.
5. Shut down cleanly via `control-keelway.mjs cleanup`.
