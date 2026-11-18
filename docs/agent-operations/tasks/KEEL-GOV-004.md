# TASK: KEEL-GOV-004 — Persistent SQLite-Backed Multi-Tenant Governance, Spend Ledger & Hash-Chained Audit Store

## 1. METADATA
- **TASK ID**: KEEL-GOV-004
- **CATEGORY**: SECURITY / GOVERNANCE
- **CREATOR**: Keelway Platform Engineering
- **LAST ASSIGNED AGENT**: Google Antigravity (Durable Governance Store Lead)
- **CURRENT STATUS**: COMPLETED
- **TARGET BRANCH**: `main`
- **BASE COMMIT**: `5b2fbc3`

---

## 2. OBJECTIVE & MOTIVATION
Upgrade Keelway Layer 6 Multi-Tenant Governance (`TenantGovernanceController` / `TenantGovernanceEngine`, `ScopedAPIKeyManager`, `TenantSpendMeter`, `HashChainedGovernanceAuditLog`, and `/v1/governance/*` FastAPI control-plane endpoints) from purely ephemeral in-memory state to a crash-safe, thread-safe SQLite WAL backing store (`SQLiteGovernanceStore`), while preserving 100% zero-latency in-memory backward compatibility when `db_path=None`.

---

## 3. ACCEPTANCE CRITERIA
- [x] **Criterion 1**: Implemented `SQLiteGovernanceStore(db_path)` in `core/security/governance_store.py` using Python stdlib `sqlite3` with `PRAGMA journal_mode=WAL`, `PRAGMA synchronous=NORMAL`, `PRAGMA foreign_keys=ON`, and `threading.RLock`, creating `governance_meta`, `tenant_policies`, `scoped_api_keys`, `tenant_spend_events` (indexed on `(tenant_id, recorded_at)`), and `governance_audit_chain`.
- [x] **Criterion 2**: Implemented `verify_persisted_chain() -> Tuple[bool, int, Optional[str]]` verifying cryptographic linkage from `GENESIS_GOVERNANCE_HASH` through every SQLite row in `seq` order plus persisted chain metadata, detecting direct SQLite row edits, middle-row deletions, and tail truncations.
- [x] **Criterion 3**: Integrated optional `db_path` / `store` into `TenantGovernanceController` (`TenantGovernanceEngine`), `ScopedAPIKeyManager`, `TenantSpendMeter`, and `HashChainedGovernanceAuditLog`, plus `KEELWAY_GOVERNANCE_DB_PATH` support via `get_governance_controller()`, hydrating salt, policies, scoped key digests/revocations/expirations, daily/monthly spend totals, and audit chain state on startup with atomic write-through.
- [x] **Criterion 4**: Enforced strict secret hygiene: zero raw `kw_live_*` secrets or unredacted prompt credentials (`sk-...`, `AIza...`, `ghp_...`) ever written to SQLite `.db`, `.db-wal`, or `.db-shm` files (`redact_text` + inline `kw_live_*` scrubbing before persistence when `log_redacted_prompts=True`, and `None` when `False`).
- [x] **Criterion 5**: Added `GET /v1/governance/persistence` in `core/api/governance_routes.py` returning `{ "persistent", "backend", "tenants_count", "keys_count", "audit_events_count", "chain_verified", "chain_head" }` without leaking filesystem paths or secrets.
- [x] **Criterion 6**: Verified 100% pass rate across all existing tests in `tests/test_tenant_governance.py` (unmodified) and comprehensive durability, restart, tampering, concurrency, secret-hygiene, and API tests in `tests/test_persistent_governance.py`.

---

## 4. AFFECTED FILES & COMPONENTS
- `core/security/governance_store.py` (New: `SQLiteGovernanceStore`, `compute_audit_event_hash`, WAL schema, CRUD & `verify_persisted_chain`)
- `core/security/tenant_governance.py` (Modified: `TenantGovernanceController` alias & `db_path`/`store` hydration + write-through, `upsert_policy`, `authenticate`, `verify_audit_chain`, `get_persistence_telemetry`, `get_governance_controller`)
- `core/api/governance_routes.py` (Modified: Added `GET /v1/governance/persistence`, wired `get_governance_controller`, and bound `/v1/governance/audit` to `verify_audit_chain()`)
- `tests/test_persistent_governance.py` (New: 9 end-to-end durability, restart, direct SQLite tampering, raw disk byte hygiene, multithreaded WAL, and FastAPI telemetry tests)
- `docs/agent-operations/tasks/KEEL-GOV-004.md` (New: Task specification, verification evidence, and cross-agent handoff record)

---

## 5. EXECUTION & HANDOFF RECORD

### TASK HANDOFF RECORD
- **TASK ID**: KEEL-GOV-004
- **TASK TITLE**: Persistent SQLite-Backed Multi-Tenant Governance, Spend Ledger & Hash-Chained Audit Store
- **CURRENT STATUS**: COMPLETED
- **LAST AGENT**: Antigravity
- **DATE**: 2026-11-13
- **BRANCH**: `main`
- **HEAD COMMIT**: `5b2fbc3` (working tree updated within strict KEEL-GOV-004 file ownership)

#### OBJECTIVE & ACCEPTANCE CRITERIA
- [x] `SQLiteGovernanceStore` WAL schema (`governance_meta`, `tenant_policies`, `scoped_api_keys`, `tenant_spend_events`, `governance_audit_chain`) & thread-safe `RLock` CRUD implemented and verified.
- [x] Full cold-restart durability verified for HMAC/salted `kw_live_*` API keys, revocations, expirations, tenant policies, daily/monthly USD spend caps (`402` & OpenCore auto-downgrade), and continuous SHA-256 audit hash chaining without Genesis reset.
- [x] Out-of-band SQLite tampering (`UPDATE` detail mutation, middle-row `DELETE`, tail truncation) deterministically detected by `verify_persisted_chain()`, `verify_audit_chain()`, `GET /v1/governance/audit`, and `GET /v1/governance/persistence`.
- [x] Raw byte inspection across `.db`, `.db-wal`, and `.db-shm` verified zero raw `kw_live_*`, `sk-...`, `AIza...`, or `ghp_...` secret persistence.
- [x] 100% backward compatibility maintained with `tests/test_tenant_governance.py`, `tests/test_cli_ai.py`, and `tests/test_platform_v1_e2e.py`.

#### WORK COMPLETED & FILES MODIFIED
- `core/security/governance_store.py`: Implemented crash-safe SQLite WAL backing store with atomic metadata/audit head tracking, defense-in-depth raw-key rejection guards, and `verify_persisted_chain()`.
- `core/security/tenant_governance.py`: Added seamless optional SQLite hydration and write-through across `TenantGovernanceController` (`TenantGovernanceEngine`), `ScopedAPIKeyManager`, `TenantSpendMeter`, and `HashChainedGovernanceAuditLog`, plus `KEELWAY_GOVERNANCE_DB_PATH` singleton binding.
- `core/api/governance_routes.py`: Exposed `GET /v1/governance/persistence` with sanitized telemetry (`sqlite_wal` | `memory`) and unified chain verification.
- `tests/test_persistent_governance.py`: Authored 9 comprehensive durability, tampering, secret-hygiene, concurrency, and FastAPI endpoint tests.
- `docs/agent-operations/tasks/KEEL-GOV-004.md`: Recorded full task documentation and verification output.

#### TESTS EXECUTED & EVIDENCE
- `PYTHONPATH=. /Users/justinmafie/Documents/antigravity/mysterious-brahmagupta/kora-ai.nosync/.venv/bin/pytest tests/test_tenant_governance.py tests/test_persistent_governance.py -v`: `25 passed, 1 warning in 0.30s`
- `PYTHONPATH=. /Users/justinmafie/Documents/antigravity/mysterious-brahmagupta/kora-ai.nosync/.venv/bin/pytest tests/test_tenant_governance.py tests/test_persistent_governance.py tests/test_cli_ai.py tests/test_platform_v1_e2e.py -v`: `31 passed, 1 warning in 3.66s`
- `/Users/justinmafie/Documents/antigravity/mysterious-brahmagupta/kora-ai.nosync/.venv/bin/python -m py_compile core/security/governance_store.py core/security/tenant_governance.py core/api/governance_routes.py tests/test_persistent_governance.py`: `0 errors`

#### KNOWN RISKS & BLOCKERS
- None. Single-node crash-safe durability is backed by SQLite WAL; horizontal multi-node shared state remains tracked on the platform roadmap (PostgreSQL/Redis). `TokenBucketRateLimiter` intentionally remains fast in-memory per replica while policies, keys, spend ledgers, and hash-chained audit logs persist durably.

#### NEXT RECOMMENDED ACTION
- Coordinator agent can integrate `KEEL-GOV-004` alongside parallel workstreams, update `docs/agent-operations/ACTIVE_TASKS.md` & `docs/architecture/KEELWAY_V1_PLATFORM_REFERENCE.md` if desired, and run full repository engineering gates (`./scripts/verify_engineering_gates.sh`) prior to commit.
