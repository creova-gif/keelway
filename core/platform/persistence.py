"""
Crash-Safe SQLite WAL Backing Store for the Keelway Unified Agent Platform (`SQLitePlatformStore`).

Persists published Marketplace packages (`marketplace_packages`), workspace package installations
(`workspace_installs`), and unified workspace/enterprise collections (`workspace_records`) using
`PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL; PRAGMA foreign_keys=ON;`.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import threading
from typing import Any, Dict, List, Optional, Union

VALID_WORKSPACE_COLLECTIONS = frozenset(
    {
        "issues",
        "prds",
        "workflows",
        "extensions",
        "enterprise_policies",
    }
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SQLitePlatformStore:
    """Thread-safe SQLite WAL backing store for Marketplace, Workspace Hub, and Enterprise Governance."""

    def __init__(self, db_path: Union[str, Path]) -> None:
        self._lock = threading.RLock()
        raw_path = str(db_path).strip()
        if not raw_path:
            raise ValueError("db_path must be a non-empty path.")
        if raw_path == ":memory:":
            self._db_path: Union[str, Path] = ":memory:"
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
    def db_path(self) -> Union[str, Path]:
        return self._db_path

    @property
    def journal_mode(self) -> str:
        return self._journal_mode

    def _init_schema_locked(self) -> None:
        with self._conn:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS marketplace_packages (
                    id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_marketplace_packages_kind
                    ON marketplace_packages(kind);

                CREATE TABLE IF NOT EXISTS workspace_installs (
                    workspace_id TEXT NOT NULL,
                    package_id TEXT NOT NULL,
                    config_json TEXT NOT NULL,
                    installed_at TEXT NOT NULL,
                    PRIMARY KEY (workspace_id, package_id)
                );

                CREATE INDEX IF NOT EXISTS idx_workspace_installs_ws
                    ON workspace_installs(workspace_id);

                CREATE TABLE IF NOT EXISTS workspace_records (
                    workspace_id TEXT NOT NULL,
                    collection TEXT NOT NULL CHECK (
                        collection IN ('issues', 'prds', 'workflows', 'extensions', 'enterprise_policies')
                    ),
                    record_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (workspace_id, collection, record_id)
                );

                CREATE INDEX IF NOT EXISTS idx_workspace_records_lookup
                    ON workspace_records(workspace_id, collection);

                CREATE TABLE IF NOT EXISTS workspace_meta (
                    workspace_id TEXT PRIMARY KEY,
                    meta_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS marketplace_settlements (
                    settlement_id TEXT PRIMARY KEY,
                    package_id TEXT NOT NULL,
                    buyer_tenant_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_marketplace_settlements_tenant
                    ON marketplace_settlements(buyer_tenant_id);
                """
            )

    def close(self) -> None:
        with self._lock:
            if not self._closed:
                try:
                    if self._db_path != ":memory:":
                        self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                except sqlite3.Error:
                    pass
                self._conn.close()
                self._closed = True

    def __enter__(self) -> SQLitePlatformStore:
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Marketplace Packages CRUD (`marketplace_packages`)
    # ------------------------------------------------------------------
    def upsert_package(
        self,
        package_id: str,
        kind: str,
        payload: Dict[str, Any],
        updated_at: Optional[str] = None,
    ) -> None:
        ts = updated_at or _utc_now()
        encoded = json.dumps(payload, separators=(",", ":"), default=str)
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO marketplace_packages (id, kind, payload_json, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    kind = excluded.kind,
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """,
                (package_id, kind, encoded, ts),
            )

    def get_package(self, package_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            row = self._conn.execute(
                "SELECT payload_json FROM marketplace_packages WHERE id = ?",
                (package_id,),
            ).fetchone()
            return json.loads(str(row["payload_json"])) if row is not None else None

    def list_packages(self, kind: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._lock:
            if kind:
                rows = self._conn.execute(
                    "SELECT payload_json FROM marketplace_packages WHERE kind = ? ORDER BY rowid ASC",
                    (kind,),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT payload_json FROM marketplace_packages ORDER BY rowid ASC"
                ).fetchall()
            return [json.loads(str(r["payload_json"])) for r in rows]

    def delete_package(self, package_id: str) -> bool:
        with self._lock, self._conn:
            cur = self._conn.execute(
                "DELETE FROM marketplace_packages WHERE id = ?",
                (package_id,),
            )
            return cur.rowcount > 0

    # ------------------------------------------------------------------
    # Workspace Package Installations CRUD (`workspace_installs`)
    # ------------------------------------------------------------------
    def upsert_install(
        self,
        workspace_id: str,
        package_id: str,
        config: Optional[Dict[str, Any]] = None,
        installed_at: Optional[str] = None,
    ) -> None:
        ts = installed_at or _utc_now()
        encoded_cfg = json.dumps(dict(config or {}), separators=(",", ":"), default=str)
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO workspace_installs (workspace_id, package_id, config_json, installed_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(workspace_id, package_id) DO UPDATE SET
                    config_json = excluded.config_json,
                    installed_at = excluded.installed_at
                """,
                (workspace_id, package_id, encoded_cfg, ts),
            )

    def remove_install(self, workspace_id: str, package_id: str) -> bool:
        with self._lock, self._conn:
            cur = self._conn.execute(
                "DELETE FROM workspace_installs WHERE workspace_id = ? AND package_id = ?",
                (workspace_id, package_id),
            )
            return cur.rowcount > 0

    def list_installs(self, workspace_id: str) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT workspace_id, package_id, config_json, installed_at
                FROM workspace_installs
                WHERE workspace_id = ?
                ORDER BY rowid ASC
                """,
                (workspace_id,),
            ).fetchall()
            return [
                {
                    "workspace_id": str(r["workspace_id"]),
                    "package_id": str(r["package_id"]),
                    "config": json.loads(str(r["config_json"])),
                    "installed_at": str(r["installed_at"]),
                }
                for r in rows
            ]

    def list_all_installs(self) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT workspace_id, package_id, config_json, installed_at
                FROM workspace_installs
                ORDER BY rowid ASC
                """
            ).fetchall()
            return [
                {
                    "workspace_id": str(r["workspace_id"]),
                    "package_id": str(r["package_id"]),
                    "config": json.loads(str(r["config_json"])),
                    "installed_at": str(r["installed_at"]),
                }
                for r in rows
            ]

    # ------------------------------------------------------------------
    # Workspace & Enterprise Records CRUD (`workspace_records`)
    # ------------------------------------------------------------------
    @staticmethod
    def _validate_collection(collection: str) -> str:
        clean = str(collection or "").strip()
        if clean not in VALID_WORKSPACE_COLLECTIONS:
            raise ValueError(
                f"Unsupported workspace_records collection '{clean}'. "
                f"Expected one of {sorted(VALID_WORKSPACE_COLLECTIONS)}."
            )
        return clean

    def upsert_record(
        self,
        workspace_id: str,
        collection: str,
        record_id: str,
        payload: Dict[str, Any],
        updated_at: Optional[str] = None,
    ) -> None:
        col = self._validate_collection(collection)
        ts = updated_at or _utc_now()
        encoded = json.dumps(payload, separators=(",", ":"), default=str)
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO workspace_records (workspace_id, collection, record_id, payload_json, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(workspace_id, collection, record_id) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """,
                (workspace_id, col, record_id, encoded, ts),
            )

    def get_record(self, workspace_id: str, collection: str, record_id: str) -> Optional[Dict[str, Any]]:
        col = self._validate_collection(collection)
        with self._lock:
            row = self._conn.execute(
                """
                SELECT payload_json FROM workspace_records
                WHERE workspace_id = ? AND collection = ? AND record_id = ?
                """,
                (workspace_id, col, record_id),
            ).fetchone()
            return json.loads(str(row["payload_json"])) if row is not None else None

    def list_records(self, workspace_id: str, collection: str) -> List[Dict[str, Any]]:
        col = self._validate_collection(collection)
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT payload_json FROM workspace_records
                WHERE workspace_id = ? AND collection = ?
                ORDER BY rowid ASC
                """,
                (workspace_id, col),
            ).fetchall()
            return [json.loads(str(r["payload_json"])) for r in rows]

    def list_records_by_collection(self, collection: str) -> List[Dict[str, Any]]:
        col = self._validate_collection(collection)
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT payload_json FROM workspace_records
                WHERE collection = ?
                ORDER BY rowid ASC
                """,
                (col,),
            ).fetchall()
            return [json.loads(str(r["payload_json"])) for r in rows]

    def delete_record(self, workspace_id: str, collection: str, record_id: str) -> bool:
        col = self._validate_collection(collection)
        with self._lock, self._conn:
            cur = self._conn.execute(
                """
                DELETE FROM workspace_records
                WHERE workspace_id = ? AND collection = ? AND record_id = ?
                """,
                (workspace_id, col, record_id),
            )
            return cur.rowcount > 0

    def list_workspaces(self) -> List[str]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT DISTINCT workspace_id FROM (
                    SELECT workspace_id FROM workspace_records
                    WHERE collection IN ('issues', 'prds', 'workflows')
                    UNION
                    SELECT workspace_id FROM workspace_meta
                )
                ORDER BY workspace_id ASC
                """
            ).fetchall()
            return [str(r["workspace_id"]) for r in rows]

    def upsert_workspace_meta(self, workspace_id: str, meta: Dict[str, Any]) -> None:
        encoded = json.dumps(meta, separators=(",", ":"), default=str)
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO workspace_meta (workspace_id, meta_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(workspace_id) DO UPDATE SET
                    meta_json = excluded.meta_json,
                    updated_at = excluded.updated_at
                """,
                (workspace_id, encoded, _utc_now()),
            )

    def get_workspace_meta(self, workspace_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            row = self._conn.execute(
                "SELECT meta_json FROM workspace_meta WHERE workspace_id = ?",
                (workspace_id,),
            ).fetchone()
            return json.loads(str(row["meta_json"])) if row is not None else None

    # ------------------------------------------------------------------
    # Marketplace Commercial Settlements CRUD (`marketplace_settlements`)
    # ------------------------------------------------------------------
    def upsert_settlement(
        self,
        settlement_id: str,
        package_id: str,
        buyer_tenant_id: str,
        payload: Dict[str, Any],
        created_at: Optional[str] = None,
    ) -> None:
        ts = created_at or _utc_now()
        encoded = json.dumps(payload, separators=(",", ":"), default=str)
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO marketplace_settlements (
                    settlement_id, package_id, buyer_tenant_id, payload_json, created_at
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(settlement_id) DO UPDATE SET
                    package_id = excluded.package_id,
                    buyer_tenant_id = excluded.buyer_tenant_id,
                    payload_json = excluded.payload_json,
                    created_at = excluded.created_at
                """,
                (settlement_id, package_id, buyer_tenant_id, encoded, ts),
            )

    def get_settlement(self, settlement_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            row = self._conn.execute(
                "SELECT payload_json FROM marketplace_settlements WHERE settlement_id = ?",
                (settlement_id,),
            ).fetchone()
            return json.loads(str(row["payload_json"])) if row is not None else None

    def list_settlements(self, buyer_tenant_id: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._lock:
            if buyer_tenant_id:
                rows = self._conn.execute(
                    """
                    SELECT payload_json FROM marketplace_settlements
                    WHERE buyer_tenant_id = ?
                    ORDER BY rowid ASC
                    """,
                    (buyer_tenant_id,),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT payload_json FROM marketplace_settlements ORDER BY rowid ASC"
                ).fetchall()
            return [json.loads(str(r["payload_json"])) for r in rows]
