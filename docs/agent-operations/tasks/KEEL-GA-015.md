# KEEL-GA-015 — Phase 8: v1.0.0 General Availability — KFlow Topological DAG Engine, KSpaces CRDT Sync, CycloneDX 1.5 SBOM, Container/CI Release Hardening & Tri-SDK Parity

- **Status**: `VERIFIED_COMPLETE`
- **Assigned Agent**: Google Antigravity (3-Agent Parallel Wave: `8A`, `8B`, `8C` + Cold `verify-keelway` Proof + Live GitHub Actions CI)
- **Date**: 2026-11-15
- **Branch**: `main` / Tag `v1.0.0`

## Summary

Completed Keelway `v1.0.0` General Availability across topological KFlow DAG execution with P-10 human-only checkpoints, commutative Lamport/vector-clock KSpaces CRDT state replication, CycloneDX 1.5 SBOM supply-chain attestation, 5-method Tri-SDK (`Python`, `TypeScript`, `Go`) parity, Local Dev Tool (`:7420/app`) `Automation` & `Security` panels, multi-stage `Dockerfile` / `docker-compose.yml` / GitHub Actions CI release hardening, and `v1.0.0` documentation (`README.md`, `CHANGELOG.md`).

## Key Deliverables

1. **KFlow Topological DAG Engine, KSpaces LWW-Element-Set CRDT Sync & CycloneDX 1.5 SBOM (`core/platform/kflow_crdt.py`, `core/api/platform_kflow_routes.py`, `core/cli_kflow_crdt.py`)**:
   - `KFlowDagEngine`: Kahn multi-wave topological sort (`waves`, `topological_order`), cycle & missing-dependency rejection (`400 Bad Request`), token-budget enforcement, P-10 human gate holds (`status="awaiting_p10"` with strict `runs:approve_p10` RBAC enforcement restricting `approved_node_ids` to `owner`/`operator`), chained upstream SHA-256 step digests, and SQLite WAL (`platform_kflow_runs`) persistence.
   - `KSpacesCrdtEngine`: Commutative, associative, idempotent Lamport + Peer-ID LWW-Element-Set CRDT (`platform_crdt_entries`) with vector clocks, tombstones, pre-storage DLP secret scrubbing, and `state_digest_sha256`.
   - Live `GET /v1/platform/security/sbom` and `cli.py sbom --verify --json`, `cli.py kflow`, and `cli.py kspaces-sync`, plus `AgentBundlePacker.unpack` `is_relative_to` + Python 3.12+ `tarfile` `filter="data"` zip-slip hardening.
2. **Tri-SDK Parity, Container/CI Release Hardening & `v1.0.0` Docs (`core/sdk/`, `sdk/typescript/`, `sdk/go/`, `Dockerfile`, `.github/workflows/`, `README.md`, `CHANGELOG.md`)**:
   - Added `execute_kflow_dag`, `list_kflow_runs`, `sync_kspaces_crdt`, `get_kspaces_state`, and `get_platform_sbom` across Python, TypeScript (`@keelway/sdk`), and Go (`keelway-go`).
   - Hardened `Dockerfile`, `docker-compose.yml`, `.github/workflows/deploy.yml`, and `.github/workflows/ci.yml` (testing Python `3.11`/`3.12`/`3.14` + `bubblewrap`, Next.js 15, all `@keelway/sdk` suites, `keelway-go -race`, `dev-app` Vitest + `axe-core`, and standalone `.whl` + CycloneDX SBOM verification while keeping `release-gate-macos.yml` fail-closed on `v*` tags).
3. **Local Dev Tool (`:7420/app`) Panels & Cold E2E Proof (`dev-app/src/components/platform/`)**:
   - Mounted `KSpacesCrdtAndKflowPanel.tsx` in `AutomationWorkspaceView` and `CycloneDxSbomPanel.tsx` in `SecurityWorkspaceView` (`65/65` Vitest tests, `0` `axe-core` WCAG 2.2 AA violations), exported `249`-path OpenAPI 3.1 schema, and proved cold end-to-end with `control-keelway`.
