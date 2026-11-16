# KEEL-CLUSTER-008: Distributed Multi-Node GPU Cluster Scheduler, PostgreSQL Row-Locked Governance Adapter & Model Lifecycle Registry

- **Status**: `VERIFIED_COMPLETE`
- **Category**: `CLUSTER / MODELS / GOVERNANCE`
- **Completed**: `2026-11-14`
- **Branch**: `main`

## Delivered Scope
1. **Distributed GPU Cluster Scheduler (`core/cluster/scheduler.py`)**:
   - Deterministic multi-node placement across `vllm`, `ray_serve`, and `ollama_metal` workers enforcing VRAM fit, tensor-parallel degree, sovereign residency/privacy boundaries (`fail_closed` on `private` / `airgapped`), and node `drain` / `restore` lifecycle controls.
2. **PostgreSQL 16+ `FOR UPDATE` Governance Adapter (`core/cluster/postgres_adapter.py`)**:
   - Production PostgreSQL 16+ DDL (`keelway_tenant_policies`, `keelway_spend_counters`, `keelway_audit_chain`), row-locking `SELECT ... FOR UPDATE` SQL builders, DB-API 2.0 connection-factory injection, and local transactional SQLite WAL parity engine with SHA-256 chain tamper detection.
3. **Model Lifecycle Registry (`core/cluster/lifecycle.py`) & Control-Plane API (`core/api/cluster_routes.py`)**:
   - Canary / stable / deprecated stage management, eval-score promotion gates, automatic previous-stable rollback, and 10 `/v1/cluster/*` FastAPI routes plus Operations View telemetry (`dev-app/src/components/platform/AutomationAndOpsViews.tsx`) and `keelway cluster` CLI subcommands (`core/cli_tui.py`).

## Verification Evidence
- `tests/test_cluster_and_postgres_governance.py` (`6/6` passed)
- `tests/test_cli_init_and_banner.py` (`13/13` passed)
- `dev-app` Vitest + `axe-core` (`53/53` passed)
