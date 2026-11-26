"""
PostgreSQL 16+ Row-Locked Governance Adapter & Local Transactional Parity Engine (`KEEL-CLUSTER-008`).

Provides canonical PostgreSQL DDL (`POSTGRES_GOVERNANCE_DDL`), parameterized `SELECT ... FOR UPDATE`
SQL builders, injectable DB-API 2.0 execution, and thread-safe SQLite `BEGIN IMMEDIATE` WAL parity
when `POSTGRES_DSN` is unset.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import threading
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple, Union

from pydantic import BaseModel, Field

GENESIS_AUDIT_HASH = "0" * 64
DEFAULT_MONTHLY_LIMIT_USD = 100.0
OPENCORE_FALLBACK_MODEL_ID = "keelway-core:7b"

POSTGRES_GOVERNANCE_DDL = """
CREATE TABLE IF NOT EXISTS keelway_tenant_budgets (
    tenant_id TEXT PRIMARY KEY,
    monthly_limit_usd NUMERIC(14, 6) NOT NULL CHECK (monthly_limit_usd >= 0),
    spent_usd NUMERIC(14, 6) NOT NULL DEFAULT 0 CHECK (spent_usd >= 0),
    fallback_to_opencore BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS keelway_cluster_audit_chain (
    seq BIGINT PRIMARY KEY CHECK (seq >= 1),
    tenant_id TEXT NOT NULL REFERENCES keelway_tenant_budgets(tenant_id) ON DELETE RESTRICT,
    actor TEXT NOT NULL,
    capability TEXT NOT NULL,
    amount_usd NUMERIC(14, 6) NOT NULL CHECK (amount_usd >= 0),
    action TEXT NOT NULL,
    allowed BOOLEAN NOT NULL,
    prev_hash CHAR(64) NOT NULL,
    entry_hash CHAR(64) NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_keelway_cluster_genesis_anchor CHECK (
        (seq = 1 AND prev_hash = '0000000000000000000000000000000000000000000000000000000000000000')
        OR (seq > 1 AND prev_hash <> '0000000000000000000000000000000000000000000000000000000000000000')
    ),
    CONSTRAINT chk_keelway_cluster_hash_progress CHECK (entry_hash <> prev_hash)
);
CREATE INDEX IF NOT EXISTS idx_keelway_cluster_audit_tenant_seq
    ON keelway_cluster_audit_chain (tenant_id, seq DESC);
""".strip()

_SQLITE_PARITY_DDL = """
CREATE TABLE IF NOT EXISTS keelway_tenant_budgets (
    tenant_id TEXT PRIMARY KEY, monthly_limit_usd REAL NOT NULL,
    spent_usd REAL NOT NULL DEFAULT 0, fallback_to_opencore INTEGER NOT NULL DEFAULT 1, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS keelway_cluster_audit_chain (
    seq INTEGER PRIMARY KEY, tenant_id TEXT NOT NULL, actor TEXT NOT NULL, capability TEXT NOT NULL,
    amount_usd REAL NOT NULL, action TEXT NOT NULL, allowed INTEGER NOT NULL,
    prev_hash TEXT NOT NULL, entry_hash TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL
);
"""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_select_budget_for_update_sql() -> str:
    """Return parameterized PostgreSQL row-locking SELECT FOR UPDATE statement for tenant budgets."""
    return (
        "SELECT tenant_id, monthly_limit_usd, spent_usd, fallback_to_opencore "
        "FROM keelway_tenant_budgets WHERE tenant_id = %s FOR UPDATE"
    )


def build_append_audit_chain_sql() -> str:
    """Return parameterized PostgreSQL statement locking chain head FOR UPDATE and inserting chained hashes."""
    return (
        "WITH locked_head AS ("
        "SELECT seq, entry_hash FROM keelway_cluster_audit_chain ORDER BY seq DESC LIMIT 1 FOR UPDATE"
        ") "
        "INSERT INTO keelway_cluster_audit_chain "
        "(seq, tenant_id, actor, capability, amount_usd, action, allowed, prev_hash, entry_hash, created_at) "
        "SELECT COALESCE((SELECT seq FROM locked_head), 0) + 1, "
        "%s, %s, %s, %s, %s, %s, %s, %s, %s "
        f"WHERE COALESCE((SELECT entry_hash FROM locked_head), '{GENESIS_AUDIT_HASH}') = %s"
    )


def compute_cluster_audit_hash(
    *, seq: int, tenant_id: str, actor: str, capability: str, amount_usd: float,
    action: str, allowed: bool, created_at: str, prev_hash: str,
) -> str:
    """Compute canonical SHA-256 digest linking prev_hash -> entry_hash."""
    payload = {
        "action": action, "actor": actor, "allowed": bool(allowed),
        "amount_usd": round(float(amount_usd), 6), "capability": capability,
        "created_at": created_at, "prev_hash": prev_hash, "seq": int(seq), "tenant_id": tenant_id,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


class _SubscriptableModel(BaseModel):
    def __getitem__(self, key: str) -> Any:
        try:
            return getattr(self, key)
        except AttributeError as exc:
            raise KeyError(key) from exc

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)


class TenantBudgetRecord(_SubscriptableModel):
    tenant_id: str
    monthly_limit_usd: float
    spent_usd: float
    remaining_usd: float
    fallback_to_opencore: bool
    updated_at: str


class BudgetReservationResult(_SubscriptableModel):
    tenant_id: str
    allowed: bool
    action: Literal["reserved", "fallback_opencore", "deny_http_402"]
    status_code: int
    amount_usd: float
    monthly_limit_usd: float
    spent_usd: float
    remaining_usd: float
    fallback_model_id: Optional[str] = None
    audit_seq: int
    prev_hash: str
    entry_hash: str


class AuditChainVerification(_SubscriptableModel):
    valid: bool
    entries_checked: int
    tenant_entries_count: int
    chain_head: str = Field(default=GENESIS_AUDIT_HASH)
    broken_at_seq: Optional[int] = None
    reason: Optional[str] = None

    def __bool__(self) -> bool:
        return self.valid


class PostgresGovernanceAdapter:
    """Transactional tenant budget reservation & Genesis-anchored SHA-256 audit chain adapter."""

    def __init__(self, dsn: Optional[str] = None, connection_factory: Optional[Callable[[], Any]] = None, sqlite_path: Optional[Union[str, Path]] = None) -> None:
        self._lock = threading.Lock()
        resolved_dsn = dsn if dsn is not None else (os.environ.get("POSTGRES_DSN") or None)
        if sqlite_path is not None and connection_factory is None and dsn is None:
            resolved_dsn = None
        self.dsn = resolved_dsn
        self._connection_factory = connection_factory
        self._use_postgres = bool(connection_factory is not None or (self.dsn and self.dsn.startswith("postgres")))
        self.sqlite_path: Optional[Path] = Path(sqlite_path) if sqlite_path is not None else None
        self._sqlite_conn: Optional[sqlite3.Connection] = None

        if not self._use_postgres:
            if self.sqlite_path is not None:
                self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
            target = str(self.sqlite_path) if self.sqlite_path is not None else ":memory:"
            conn = sqlite3.connect(target, check_same_thread=False, isolation_level=None)
            if self.sqlite_path is not None:
                conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.executescript(_SQLITE_PARITY_DDL)
            self._sqlite_conn = conn
            self.configure_tenant_budget("default", monthly_limit_usd=DEFAULT_MONTHLY_LIMIT_USD, fallback_to_opencore=True)

    def _open_pg_conn(self) -> Any:
        if self._connection_factory is not None:
            return self._connection_factory()
        if not self.dsn:
            raise RuntimeError("POSTGRES_DSN is not configured.")
        try:
            import psycopg
            return psycopg.connect(self.dsn)
        except ImportError:
            import psycopg2
            return psycopg2.connect(self.dsn)

    def configure_tenant_budget(
        self, tenant_id: str, monthly_limit_usd: float, fallback_to_opencore: bool = True, spent_usd: Optional[float] = None,
    ) -> TenantBudgetRecord:
        """Create or update a tenant's monthly USD cap and OpenCore fallback policy."""
        clean_tenant = tenant_id.strip()
        if not clean_tenant or monthly_limit_usd < 0 or (spent_usd is not None and spent_usd < 0):
            raise ValueError("Non-empty tenant_id and non-negative budget values are required.")
        now_iso, limit_val = _utc_now_iso(), round(float(monthly_limit_usd), 6)

        if self._use_postgres:
            conn = self._open_pg_conn()
            cur = conn.cursor()
            try:
                cur.execute(build_select_budget_for_update_sql(), (clean_tenant,))
                existing = cur.fetchone()
                eff_spent = round(float(spent_usd if spent_usd is not None else (existing[2] if existing else 0.0)), 6)
                if existing is None:
                    cur.execute("INSERT INTO keelway_tenant_budgets (tenant_id, monthly_limit_usd, spent_usd, fallback_to_opencore, updated_at) VALUES (%s, %s, %s, %s, %s)", (clean_tenant, limit_val, eff_spent, bool(fallback_to_opencore), now_iso))
                else:
                    cur.execute("UPDATE keelway_tenant_budgets SET monthly_limit_usd = %s, spent_usd = %s, fallback_to_opencore = %s, updated_at = %s WHERE tenant_id = %s", (limit_val, eff_spent, bool(fallback_to_opencore), now_iso, clean_tenant))
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                cur.close()
        else:
            assert self._sqlite_conn is not None
            with self._lock:
                self._sqlite_conn.execute("BEGIN IMMEDIATE")
                try:
                    row = self._sqlite_conn.execute("SELECT spent_usd FROM keelway_tenant_budgets WHERE tenant_id = ?", (clean_tenant,)).fetchone()
                    eff_spent = round(float(spent_usd if spent_usd is not None else (row[0] if row else 0.0)), 6)
                    self._sqlite_conn.execute(
                        "INSERT INTO keelway_tenant_budgets (tenant_id, monthly_limit_usd, spent_usd, fallback_to_opencore, updated_at) VALUES (?, ?, ?, ?, ?) "
                        "ON CONFLICT(tenant_id) DO UPDATE SET monthly_limit_usd=excluded.monthly_limit_usd, spent_usd=excluded.spent_usd, fallback_to_opencore=excluded.fallback_to_opencore, updated_at=excluded.updated_at",
                        (clean_tenant, limit_val, eff_spent, int(bool(fallback_to_opencore)), now_iso),
                    )
                    self._sqlite_conn.execute("COMMIT")
                except Exception:
                    self._sqlite_conn.execute("ROLLBACK")
                    raise
        return TenantBudgetRecord(
            tenant_id=clean_tenant, monthly_limit_usd=limit_val, spent_usd=eff_spent,
            remaining_usd=round(max(0.0, limit_val - eff_spent), 6), fallback_to_opencore=bool(fallback_to_opencore), updated_at=now_iso,
        )

    def reserve_spend_atomic(
        self, tenant_id: str, amount_usd: float, actor: str = "system", capability: str = "cluster.inference",
    ) -> BudgetReservationResult:
        """Atomically lock tenant budget, enforce hard USD cap, and append SHA-256 chained audit record."""
        clean_tenant = tenant_id.strip()
        if not clean_tenant or amount_usd < 0:
            raise ValueError("Valid tenant_id and non-negative amount_usd are required.")
        clean_actor, clean_cap, amt, now_iso = actor.strip() or "system", capability.strip() or "cluster.inference", round(float(amount_usd), 6), _utc_now_iso()
        runner = self._reserve_pg if self._use_postgres else self._reserve_sqlite
        limit_val, next_spent, allowed, action, code, seq, prev_h, entry_h = runner(clean_tenant, amt, clean_actor, clean_cap, now_iso)
        return BudgetReservationResult(
            tenant_id=clean_tenant, allowed=allowed, action=action, status_code=code, amount_usd=amt,
            monthly_limit_usd=limit_val, spent_usd=next_spent, remaining_usd=round(max(0.0, limit_val - next_spent), 6),
            fallback_model_id=OPENCORE_FALLBACK_MODEL_ID if action == "fallback_opencore" else None,
            audit_seq=seq, prev_hash=prev_h, entry_hash=entry_h,
        )

    def _reserve_pg(self, tenant: str, amt: float, actor: str, cap: str, now_iso: str) -> Tuple[Any, ...]:
        conn = self._open_pg_conn()
        cur = conn.cursor()
        try:
            cur.execute(build_select_budget_for_update_sql(), (tenant,))
            row = cur.fetchone()
            if row is None:
                cur.execute("INSERT INTO keelway_tenant_budgets (tenant_id, monthly_limit_usd, spent_usd, fallback_to_opencore, updated_at) VALUES (%s, %s, %s, %s, %s)", (tenant, DEFAULT_MONTHLY_LIMIT_USD, 0.0, True, now_iso))
                cur.execute(build_select_budget_for_update_sql(), (tenant,))
                row = cur.fetchone()
            limit_val, cur_spent, fb_flag = round(float(row[1]), 6), round(float(row[2]), 6), bool(row[3])
            allowed, action, code, next_spent = self._decide(limit_val, cur_spent, amt, fb_flag)
            if allowed:
                cur.execute("UPDATE keelway_tenant_budgets SET spent_usd = %s, updated_at = %s WHERE tenant_id = %s", (next_spent, now_iso, tenant))
            cur.execute("SELECT seq, entry_hash FROM keelway_cluster_audit_chain ORDER BY seq DESC LIMIT 1 FOR UPDATE")
            head = cur.fetchone()
            seq, prev_h = ((int(head[0]) + 1), str(head[1])) if head else (1, GENESIS_AUDIT_HASH)
            entry_h = compute_cluster_audit_hash(seq=seq, tenant_id=tenant, actor=actor, capability=cap, amount_usd=amt, action=action, allowed=allowed, created_at=now_iso, prev_hash=prev_h)
            cur.execute(build_append_audit_chain_sql(), (tenant, actor, cap, amt, action, allowed, prev_h, entry_h, now_iso, prev_h))
            conn.commit()
            return limit_val, next_spent, allowed, action, code, seq, prev_h, entry_h
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()

    def _reserve_sqlite(self, tenant: str, amt: float, actor: str, cap: str, now_iso: str) -> Tuple[Any, ...]:
        assert self._sqlite_conn is not None
        with self._lock:
            self._sqlite_conn.execute("BEGIN IMMEDIATE")
            try:
                row = self._sqlite_conn.execute("SELECT tenant_id, monthly_limit_usd, spent_usd, fallback_to_opencore FROM keelway_tenant_budgets WHERE tenant_id = ?", (tenant,)).fetchone()
                if row is None:
                    self._sqlite_conn.execute("INSERT INTO keelway_tenant_budgets (tenant_id, monthly_limit_usd, spent_usd, fallback_to_opencore, updated_at) VALUES (?, ?, ?, ?, ?)", (tenant, DEFAULT_MONTHLY_LIMIT_USD, 0.0, 1, now_iso))
                    limit_val, cur_spent, fb_flag = DEFAULT_MONTHLY_LIMIT_USD, 0.0, True
                else:
                    limit_val, cur_spent, fb_flag = round(float(row[1]), 6), round(float(row[2]), 6), bool(row[3])
                allowed, action, code, next_spent = self._decide(limit_val, cur_spent, amt, fb_flag)
                if allowed:
                    self._sqlite_conn.execute("UPDATE keelway_tenant_budgets SET spent_usd = ?, updated_at = ? WHERE tenant_id = ?", (next_spent, now_iso, tenant))
                head = self._sqlite_conn.execute("SELECT seq, entry_hash FROM keelway_cluster_audit_chain ORDER BY seq DESC LIMIT 1").fetchone()
                seq, prev_h = ((int(head[0]) + 1), str(head[1])) if head else (1, GENESIS_AUDIT_HASH)
                entry_h = compute_cluster_audit_hash(seq=seq, tenant_id=tenant, actor=actor, capability=cap, amount_usd=amt, action=action, allowed=allowed, created_at=now_iso, prev_hash=prev_h)
                self._sqlite_conn.execute("INSERT INTO keelway_cluster_audit_chain (seq, tenant_id, actor, capability, amount_usd, action, allowed, prev_hash, entry_hash, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (seq, tenant, actor, cap, amt, action, int(allowed), prev_h, entry_h, now_iso))
                self._sqlite_conn.execute("COMMIT")
                return limit_val, next_spent, allowed, action, code, seq, prev_h, entry_h
            except Exception:
                self._sqlite_conn.execute("ROLLBACK")
                raise

    @staticmethod
    def _decide(limit_val: float, cur_spent: float, amt: float, fallback: bool) -> Tuple[bool, Literal["reserved", "fallback_opencore", "deny_http_402"], int, float]:
        candidate = round(cur_spent + amt, 6)
        if candidate <= limit_val + 1e-9:
            return True, "reserved", 200, candidate
        if fallback:
            return False, "fallback_opencore", 200, cur_spent
        return False, "deny_http_402", 402, cur_spent

    def verify_audit_chain(self, tenant_id: Optional[str] = None) -> AuditChainVerification:
        """Verify Genesis-anchored SHA-256 hash chain continuity and tamper resistance."""
        rows = self._fetch_audit_rows()
        expected_prev, tenant_count = GENESIS_AUDIT_HASH, 0
        for idx, row in enumerate(rows, start=1):
            seq, r_tenant, actor, cap, amt, action, allowed, prev_h, entry_h, created_at = row
            if r_tenant == tenant_id:
                tenant_count += 1
            if int(seq) != idx or prev_h != expected_prev:
                return AuditChainVerification(valid=False, entries_checked=idx, tenant_entries_count=tenant_count, chain_head=expected_prev, broken_at_seq=int(seq), reason="PREV_HASH_OR_SEQ_MISMATCH")
            recomputed = compute_cluster_audit_hash(seq=int(seq), tenant_id=str(r_tenant), actor=str(actor), capability=str(cap), amount_usd=float(amt), action=str(action), allowed=bool(allowed), created_at=str(created_at), prev_hash=str(prev_h))
            if recomputed != entry_h:
                return AuditChainVerification(valid=False, entries_checked=idx, tenant_entries_count=tenant_count, chain_head=expected_prev, broken_at_seq=int(seq), reason="ENTRY_HASH_TAMPERED")
            expected_prev = str(entry_h)
        return AuditChainVerification(valid=True, entries_checked=len(rows), tenant_entries_count=len(rows) if tenant_id is None else tenant_count, chain_head=expected_prev)

    def _fetch_audit_rows(self) -> List[Tuple[Any, ...]]:
        sql = "SELECT seq, tenant_id, actor, capability, amount_usd, action, allowed, prev_hash, entry_hash, created_at FROM keelway_cluster_audit_chain ORDER BY seq ASC"
        if self._use_postgres:
            conn = self._open_pg_conn()
            cur = conn.cursor()
            try:
                cur.execute(sql)
                return list(cur.fetchall())
            finally:
                cur.close()
        assert self._sqlite_conn is not None
        with self._lock:
            return list(self._sqlite_conn.execute(sql).fetchall())

    def get_adapter_status(self) -> Dict[str, Any]:
        """Return operational telemetry, locking guarantees, and audit chain integrity status."""
        ver = self.verify_audit_chain()
        count_sql = "SELECT COUNT(*) FROM keelway_tenant_budgets"
        if self._use_postgres:
            conn = self._open_pg_conn()
            cur = conn.cursor()
            try:
                cur.execute(count_sql)
                t_row = cur.fetchone()
                tenants_count = int(t_row[0]) if t_row else 0
            finally:
                cur.close()
            mode, backend = "postgres", "postgres_dbapi"
        else:
            assert self._sqlite_conn is not None
            with self._lock:
                row = self._sqlite_conn.execute(count_sql).fetchone()
                tenants_count = int(row[0]) if row else 0
            mode, backend = "local_parity", ("sqlite_wal" if self.sqlite_path is not None else "sqlite_transactional_parity")
        return {
            "mode": mode, "backend": backend, "dsn_configured": bool(self.dsn),
            "row_locking_sql": build_select_budget_for_update_sql(), "local_locking": "threading.Lock + BEGIN IMMEDIATE",
            "ddl_tables": ["keelway_tenant_budgets", "keelway_cluster_audit_chain"],
            "tenants_count": tenants_count, "audit_entries_count": ver.entries_checked,
            "chain_valid": ver.valid, "chain_head": ver.chain_head, "broken_at_seq": ver.broken_at_seq,
        }


postgres_governance_adapter = PostgresGovernanceAdapter()
