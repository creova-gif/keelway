"""Crash-safe SQLite WAL backing store for multi-tenant governance, spend ledger, and audit chain."""
from __future__ import annotations

import hashlib
import json
import re
import secrets
import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

GENESIS_GOVERNANCE_HASH = "0" * 64
META_KEY_HMAC_SALT = "key_hmac_salt"
META_AUDIT_CHAIN_HEAD = "audit_chain_head"
META_AUDIT_CHAIN_COUNT = "audit_chain_count"

_RAW_KEELWAY_KEY_RE = re.compile(r"kw_live_[0-9a-f]{6}_[0-9a-f]{32}")


def compute_audit_event_hash(
    *,
    seq: int,
    event_id: str,
    timestamp: str,
    tenant_id: str,
    action: str,
    outcome: str,
    model_id: Optional[str],
    provider: Optional[str],
    cost_usd: float,
    detail: str,
    redacted_prompt_preview: Optional[str],
    prev_hash: str,
) -> str:
    """Compute canonical deterministic SHA-256 digest over a governance audit event."""
    payload = {
        "seq": seq,
        "event_id": event_id,
        "timestamp": timestamp,
        "tenant_id": tenant_id,
        "action": action,
        "outcome": outcome,
        "model_id": model_id,
        "provider": provider,
        "cost_usd": round(float(cost_usd), 8),
        "detail": detail,
        "redacted_prompt_preview": redacted_prompt_preview,
        "prev_hash": prev_hash,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class PersistedAuditRow:
    """Typed representation of a row in `governance_audit_chain`."""

    seq: int
    event_id: str
    timestamp: str
    tenant_id: str
    action: str
    outcome: str
    model_id: Optional[str]
    provider: Optional[str]
    cost_usd: float
    detail: str
    redacted_prompt_preview: Optional[str]
    prev_hash: str
    event_hash: str


@dataclass(frozen=True)
class PersistedSpendRow:
    """Typed representation of a row in `tenant_spend_events`."""

    id: int
    tenant_id: str
    amount_usd: float
    model_id: str
    provider: str
    recorded_at: str
    tokens: int = 0


class SQLiteGovernanceStore:
    """Thread-safe SQLite WAL backing store for Keelway Layer 6 Tenant Governance."""

    def __init__(self, db_path: Path | str) -> None:
        self._lock = threading.RLock()
        raw_path = str(db_path).strip()
        if not raw_path:
            raise ValueError("db_path must be a non-empty path.")
        if raw_path == ":memory:":
            self._db_path: Path | str = ":memory:"
            connect_target = ":memory:"
        else:
            resolved = Path(raw_path).expanduser().resolve()
            resolved.parent.mkdir(parents=True, exist_ok=True)
            self._db_path = resolved
            connect_target = str(resolved)

        self._conn = sqlite3.connect(connect_target, check_same_thread=False, timeout=30.0)
        self._conn.row_factory = sqlite3.Row
        self._closed = False
        with self._lock:
            mode_row = self._conn.execute("PRAGMA journal_mode=WAL").fetchone()
            self._journal_mode = str(mode_row[0]).lower() if mode_row else "unknown"
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._init_schema_locked()

    @property
    def db_path(self) -> Path | str:
        """Return resolved database path (internal diagnostic property; never expose via HTTP)."""
        return self._db_path

    @property
    def journal_mode(self) -> str:
        """Return active SQLite journal mode (e.g. 'wal')."""
        return self._journal_mode

    def _init_schema_locked(self) -> None:
        with self._conn:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS governance_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS tenant_policies (
                    tenant_id TEXT PRIMARY KEY,
                    policy_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS scoped_api_keys (
                    key_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    key_prefix TEXT NOT NULL,
                    secret_sha256 TEXT NOT NULL,
                    scopes_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT,
                    revoked INTEGER NOT NULL DEFAULT 0,
                    last_used_at TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_scoped_api_keys_tenant
                    ON scoped_api_keys(tenant_id);
                CREATE INDEX IF NOT EXISTS idx_scoped_api_keys_prefix
                    ON scoped_api_keys(key_prefix);

                CREATE TABLE IF NOT EXISTS tenant_spend_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tenant_id TEXT NOT NULL,
                    amount_usd REAL NOT NULL,
                    model_id TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    recorded_at TEXT NOT NULL,
                    tokens INTEGER NOT NULL DEFAULT 0
                );

                CREATE INDEX IF NOT EXISTS idx_tenant_spend_tenant_recorded
                    ON tenant_spend_events(tenant_id, recorded_at);

                CREATE TABLE IF NOT EXISTS governance_audit_chain (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT UNIQUE NOT NULL,
                    timestamp TEXT NOT NULL,
                    tenant_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    model_id TEXT,
                    provider TEXT,
                    cost_usd REAL NOT NULL,
                    detail TEXT NOT NULL,
                    redacted_prompt_preview TEXT,
                    prev_hash TEXT NOT NULL,
                    event_hash TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_governance_audit_tenant
                    ON governance_audit_chain(tenant_id, seq);
                """
            )

    def close(self) -> None:
        """Checkpoint WAL if applicable and close the underlying SQLite connection."""
        with self._lock:
            if not self._closed:
                try:
                    if self._db_path != ":memory:":
                        self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                except sqlite3.Error:
                    pass
                self._conn.close()
                self._closed = True

    def __enter__(self) -> SQLiteGovernanceStore:
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Metadata & Persistent HMAC/Salted Digest Key Salt
    # ------------------------------------------------------------------
    def get_meta(self, key: str) -> Optional[str]:
        with self._lock:
            row = self._conn.execute(
                "SELECT value FROM governance_meta WHERE key = ?",
                (key,),
            ).fetchone()
            return str(row["value"]) if row is not None else None

    def set_meta(self, key: str, value: str) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO governance_meta (key, value)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, value),
            )

    def get_or_create_salt(self, fallback_salt: Optional[str] = None) -> str:
        """Load persistent key salt from `governance_meta` or initialize atomically once."""
        with self._lock:
            existing = self.get_meta(META_KEY_HMAC_SALT)
            if existing:
                return existing
            chosen = fallback_salt or secrets.token_hex(32)
            self.set_meta(META_KEY_HMAC_SALT, chosen)
            return chosen

    # ------------------------------------------------------------------
    # Tenant Policies CRUD
    # ------------------------------------------------------------------
    def upsert_policy(self, tenant_id: str, policy_json: str, updated_at: str) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO tenant_policies (tenant_id, policy_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(tenant_id) DO UPDATE SET
                    policy_json = excluded.policy_json,
                    updated_at = excluded.updated_at
                """,
                (tenant_id, policy_json, updated_at),
            )

    def get_policy_json(self, tenant_id: str) -> Optional[str]:
        with self._lock:
            row = self._conn.execute(
                "SELECT policy_json FROM tenant_policies WHERE tenant_id = ?",
                (tenant_id,),
            ).fetchone()
            return str(row["policy_json"]) if row is not None else None

    def list_policies(self) -> List[Tuple[str, str, str]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT tenant_id, policy_json, updated_at FROM tenant_policies ORDER BY rowid ASC"
            ).fetchall()
            return [(str(r["tenant_id"]), str(r["policy_json"]), str(r["updated_at"])) for r in rows]

    def count_policies(self) -> int:
        with self._lock:
            row = self._conn.execute("SELECT COUNT(*) AS cnt FROM tenant_policies").fetchone()
            return int(row["cnt"]) if row is not None else 0

    # ------------------------------------------------------------------
    # Scoped API Keys CRUD (Zero Raw Key Storage)
    # ------------------------------------------------------------------
    def insert_scoped_key(
        self,
        *,
        key_id: str,
        tenant_id: str,
        name: str,
        key_prefix: str,
        secret_sha256: str,
        scopes: List[str],
        created_at: str,
        expires_at: Optional[str] = None,
        revoked: bool = False,
        last_used_at: Optional[str] = None,
    ) -> None:
        if _RAW_KEELWAY_KEY_RE.search(secret_sha256) or len(secret_sha256) != 64:
            raise ValueError("Refusing to persist invalid or unhashed scoped API key secret.")
        if _RAW_KEELWAY_KEY_RE.search(key_prefix):
            raise ValueError("key_prefix must never contain the full raw API key.")
        scopes_json = json.dumps(list(scopes), separators=(",", ":"))
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO scoped_api_keys (
                    key_id, tenant_id, name, key_prefix, secret_sha256,
                    scopes_json, created_at, expires_at, revoked, last_used_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    key_id,
                    tenant_id,
                    name,
                    key_prefix,
                    secret_sha256,
                    scopes_json,
                    created_at,
                    expires_at,
                    1 if revoked else 0,
                    last_used_at,
                ),
            )

    def update_key_revoked(self, key_id: str, revoked: bool = True) -> bool:
        with self._lock, self._conn:
            cur = self._conn.execute(
                "UPDATE scoped_api_keys SET revoked = ? WHERE key_id = ?",
                (1 if revoked else 0, key_id),
            )
            return cur.rowcount > 0

    def update_key_last_used(self, key_id: str, last_used_at: str) -> bool:
        with self._lock, self._conn:
            cur = self._conn.execute(
                "UPDATE scoped_api_keys SET last_used_at = ? WHERE key_id = ?",
                (last_used_at, key_id),
            )
            return cur.rowcount > 0

    def list_scoped_keys(self) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT key_id, tenant_id, name, key_prefix, secret_sha256,
                       scopes_json, created_at, expires_at, revoked, last_used_at
                FROM scoped_api_keys
                ORDER BY created_at ASC, rowid ASC
                """
            ).fetchall()
            return [
                {
                    "key_id": str(r["key_id"]),
                    "tenant_id": str(r["tenant_id"]),
                    "name": str(r["name"]),
                    "key_prefix": str(r["key_prefix"]),
                    "secret_sha256": str(r["secret_sha256"]),
                    "scopes": json.loads(str(r["scopes_json"])),
                    "created_at": str(r["created_at"]),
                    "expires_at": str(r["expires_at"]) if r["expires_at"] is not None else None,
                    "revoked": bool(r["revoked"]),
                    "last_used_at": str(r["last_used_at"]) if r["last_used_at"] is not None else None,
                }
                for r in rows
            ]

    def count_scoped_keys(self) -> int:
        with self._lock:
            row = self._conn.execute("SELECT COUNT(*) AS cnt FROM scoped_api_keys").fetchone()
            return int(row["cnt"]) if row is not None else 0

    # ------------------------------------------------------------------
    # Tenant Spend Ledger Events
    # ------------------------------------------------------------------
    def append_spend_event(
        self,
        *,
        tenant_id: str,
        amount_usd: float,
        model_id: str,
        provider: str,
        recorded_at: str,
        tokens: int = 0,
    ) -> int:
        with self._lock, self._conn:
            cur = self._conn.execute(
                """
                INSERT INTO tenant_spend_events (
                    tenant_id, amount_usd, model_id, provider, recorded_at, tokens
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (tenant_id, float(amount_usd), model_id, provider, recorded_at, int(tokens)),
            )
            return int(cur.lastrowid or 0)

    def list_spend_events(self, tenant_id: Optional[str] = None) -> List[PersistedSpendRow]:
        with self._lock:
            if tenant_id is None:
                rows = self._conn.execute(
                    """
                    SELECT id, tenant_id, amount_usd, model_id, provider, recorded_at, tokens
                    FROM tenant_spend_events
                    ORDER BY id ASC
                    """
                ).fetchall()
            else:
                rows = self._conn.execute(
                    """
                    SELECT id, tenant_id, amount_usd, model_id, provider, recorded_at, tokens
                    FROM tenant_spend_events
                    WHERE tenant_id = ?
                    ORDER BY id ASC
                    """,
                    (tenant_id,),
                ).fetchall()
            return [
                PersistedSpendRow(
                    id=int(r["id"]),
                    tenant_id=str(r["tenant_id"]),
                    amount_usd=float(r["amount_usd"]),
                    model_id=str(r["model_id"]),
                    provider=str(r["provider"]),
                    recorded_at=str(r["recorded_at"]),
                    tokens=int(r["tokens"]),
                )
                for r in rows
            ]

    # ------------------------------------------------------------------
    # Hash-Chained Governance Audit Log
    # ------------------------------------------------------------------
    def append_audit_event(
        self,
        *,
        seq: int,
        event_id: str,
        timestamp: str,
        tenant_id: str,
        action: str,
        outcome: str,
        model_id: Optional[str],
        provider: Optional[str],
        cost_usd: float,
        detail: str,
        redacted_prompt_preview: Optional[str],
        prev_hash: str,
        event_hash: str,
    ) -> PersistedAuditRow:
        if _RAW_KEELWAY_KEY_RE.search(detail) or (
            redacted_prompt_preview is not None and _RAW_KEELWAY_KEY_RE.search(redacted_prompt_preview)
        ):
            raise ValueError("Refusing to persist unredacted kw_live_* key in governance audit log.")

        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO governance_audit_chain (
                    seq, event_id, timestamp, tenant_id, action, outcome,
                    model_id, provider, cost_usd, detail, redacted_prompt_preview,
                    prev_hash, event_hash
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    seq,
                    event_id,
                    timestamp,
                    tenant_id,
                    action,
                    outcome,
                    model_id,
                    provider,
                    round(float(cost_usd), 8),
                    detail,
                    redacted_prompt_preview,
                    prev_hash,
                    event_hash,
                ),
            )
            self._conn.execute(
                """
                INSERT INTO governance_meta (key, value)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (META_AUDIT_CHAIN_HEAD, event_hash),
            )
            self._conn.execute(
                """
                INSERT INTO governance_meta (key, value)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (META_AUDIT_CHAIN_COUNT, str(seq)),
            )

        return PersistedAuditRow(
            seq=seq,
            event_id=event_id,
            timestamp=timestamp,
            tenant_id=tenant_id,
            action=action,
            outcome=outcome,
            model_id=model_id,
            provider=provider,
            cost_usd=round(float(cost_usd), 8),
            detail=detail,
            redacted_prompt_preview=redacted_prompt_preview,
            prev_hash=prev_hash,
            event_hash=event_hash,
        )

    def list_audit_events(self) -> List[PersistedAuditRow]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT seq, event_id, timestamp, tenant_id, action, outcome,
                       model_id, provider, cost_usd, detail, redacted_prompt_preview,
                       prev_hash, event_hash
                FROM governance_audit_chain
                ORDER BY seq ASC
                """
            ).fetchall()
            return [
                PersistedAuditRow(
                    seq=int(r["seq"]),
                    event_id=str(r["event_id"]),
                    timestamp=str(r["timestamp"]),
                    tenant_id=str(r["tenant_id"]),
                    action=str(r["action"]),
                    outcome=str(r["outcome"]),
                    model_id=str(r["model_id"]) if r["model_id"] is not None else None,
                    provider=str(r["provider"]) if r["provider"] is not None else None,
                    cost_usd=float(r["cost_usd"]),
                    detail=str(r["detail"]),
                    redacted_prompt_preview=(
                        str(r["redacted_prompt_preview"]) if r["redacted_prompt_preview"] is not None else None
                    ),
                    prev_hash=str(r["prev_hash"]),
                    event_hash=str(r["event_hash"]),
                )
                for r in rows
            ]

    def count_audit_events(self) -> int:
        with self._lock:
            row = self._conn.execute("SELECT COUNT(*) AS cnt FROM governance_audit_chain").fetchone()
            return int(row["cnt"]) if row is not None else 0

    def get_chain_head(self) -> str:
        with self._lock:
            row = self._conn.execute(
                "SELECT event_hash FROM governance_audit_chain ORDER BY seq DESC LIMIT 1"
            ).fetchone()
            return str(row["event_hash"]) if row is not None else GENESIS_GOVERNANCE_HASH

    def verify_persisted_chain(self) -> Tuple[bool, int, Optional[str]]:
        """Read rows directly from SQLite in `seq` order and verify cryptographic linkage from Genesis.

        Returns:
            `(True, verified_count, None)` when intact.
            `(False, broken_seq, error_detail)` when any row is mutated, out-of-sequence, deleted, or truncated.
        """
        with self._lock:
            rows = self.list_audit_events()
            prev = GENESIS_GOVERNANCE_HASH
            for expected_seq, row in enumerate(rows, start=1):
                if row.seq != expected_seq:
                    return (
                        False,
                        expected_seq,
                        f"Missing or out-of-order audit sequence: expected seq={expected_seq}, found seq={row.seq}.",
                    )
                if row.prev_hash != prev:
                    return (
                        False,
                        row.seq,
                        f"Broken prev_hash link at seq={row.seq}: expected {prev}, found {row.prev_hash}.",
                    )
                expected_hash = compute_audit_event_hash(
                    seq=row.seq,
                    event_id=row.event_id,
                    timestamp=row.timestamp,
                    tenant_id=row.tenant_id,
                    action=row.action,
                    outcome=row.outcome,
                    model_id=row.model_id,
                    provider=row.provider,
                    cost_usd=row.cost_usd,
                    detail=row.detail,
                    redacted_prompt_preview=row.redacted_prompt_preview,
                    prev_hash=prev,
                )
                if row.event_hash != expected_hash:
                    return (
                        False,
                        row.seq,
                        f"Tampered event_hash at seq={row.seq}: expected {expected_hash}, found {row.event_hash}.",
                    )
                prev = row.event_hash

            meta_count = self.get_meta(META_AUDIT_CHAIN_COUNT)
            if meta_count is not None and len(rows) != int(meta_count):
                broken_seq = len(rows) + 1
                return (
                    False,
                    broken_seq,
                    f"Audit chain truncation detected: persisted {len(rows)} rows, expected {meta_count}.",
                )

            meta_head = self.get_meta(META_AUDIT_CHAIN_HEAD)
            if meta_head is not None and prev != meta_head:
                broken_seq = max(1, len(rows))
                return (
                    False,
                    broken_seq,
                    f"Audit chain head mismatch: computed {prev}, expected {meta_head}.",
                )

            return True, len(rows), None
