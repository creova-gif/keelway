"""
Multi-Workspace 5-Role RBAC Controller & `HMAC-SHA256` Signed Webhook Bus with SSRF Defense.

Persists workspaces (`platform_workspaces_dir`), workspace role assignments (`platform_rbac_members`),
registered webhooks (`platform_webhooks`), and signed delivery receipts (`platform_webhook_deliveries`)
in crash-safe SQLite WAL mode.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import hmac
import ipaddress
import json
from pathlib import Path
import re
import secrets
import sqlite3
import threading
import time
from typing import Any, Dict, FrozenSet, List, Optional, Sequence, Union
from urllib.parse import urlparse
import uuid

from core.platform.vault import _resolve_sqlite_target, mask_secret

VALID_ROLES = ("owner", "admin", "builder", "operator", "viewer")
VALID_ISOLATION_MODES = frozenset({
    "seatbelt_local", "airgap_strict", "container_isolated", "dedicated_vpc",
    "sqlite_wal_local", "airgap_seatbelt", "vpc_tenant",
})
_WORKSPACE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")

ROLE_PERMISSION_MATRIX: Dict[str, FrozenSet[str]] = {
    "owner": frozenset({"*"}),
    "admin": frozenset({
        "workspace:manage", "rbac:manage", "secrets:write", "secrets:read_meta", "webhooks:manage",
        "agents:dispatch", "workflows:run", "p10:approve", "docs:write", "issues:write",
        "marketplace:publish", "read:all",
    }),
    "builder": frozenset({
        "secrets:read_meta", "agents:dispatch", "workflows:run", "docs:write", "issues:write",
        "marketplace:publish", "read:all",
    }),
    "operator": frozenset({
        "secrets:read_meta", "workflows:run", "p10:approve", "issues:write", "read:all",
    }),
    "viewer": frozenset({"read:all"}),
}

_BLOCKED_SSRF_HOSTS = frozenset({
    "169.254.169.254", "169.254.170.2", "metadata.google.internal",
    "metadata.goog", "metadata", "100.100.100.200", "0.0.0.0",
})
_ALLOWED_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


class WebhookValidationError(ValueError):
    """Raised when a webhook URL or registration payload violates SSRF or schema rules."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_json(payload: Any) -> str:
    return payload if isinstance(payload, str) else json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def validate_webhook_url(url: str) -> str:
    """Strictly validates webhook destination URLs and blocks cloud metadata / SSRF targets."""
    clean = str(url or "").strip()
    if not clean or len(clean) > 2048:
        raise WebhookValidationError("Webhook 'url' must be a non-empty URL.")
    parsed = urlparse(clean)
    scheme = (parsed.scheme or "").lower()
    if scheme not in {"https", "http"}:
        raise WebhookValidationError(f"Unsupported scheme '{scheme or 'empty'}'; only https:// or loopback http:// allowed.")
    if parsed.username or parsed.password:
        raise WebhookValidationError("Webhook URL must not embed user credentials.")
    host = (parsed.hostname or "").strip().lower().rstrip(".")
    if not host:
        raise WebhookValidationError("Webhook URL is missing a valid hostname.")
    if host in _BLOCKED_SSRF_HOSTS or host.startswith("169.254.") or host.endswith(".internal"):
        raise WebhookValidationError(f"Blocked SSRF destination host '{host}'.")

    try:
        ip_obj = ipaddress.ip_address(host)
        check_ips = [ip_obj] + ([ip_obj.ipv4_mapped] if isinstance(ip_obj, ipaddress.IPv6Address) and ip_obj.ipv4_mapped else [])
        for ip_item in check_ips:
            if ip_item.is_unspecified or ip_item.is_link_local or ip_item.is_multicast or str(ip_item) == "100.100.100.200":
                raise WebhookValidationError(f"Blocked SSRF IP address '{host}'.")
            if ip_item.is_private and not ip_item.is_loopback:
                raise WebhookValidationError(f"Blocked private network IP address '{host}'.")
    except ValueError as exc:
        if isinstance(exc, WebhookValidationError):
            raise

    if scheme == "http" and host not in _ALLOWED_LOOPBACK_HOSTS:
        raise WebhookValidationError("Plaintext http:// webhooks are restricted to loopback (127.0.0.1 / localhost).")
    return clean


class WorkspaceRbacController:
    """Multi-workspace registry & 5-role RBAC controller backed by SQLite WAL."""

    def __init__(self, db_path: Optional[Union[str, Path]] = None) -> None:
        self._lock = threading.RLock()
        self._db_path, connect_target = _resolve_sqlite_target(db_path)
        self._conn = sqlite3.connect(connect_target, check_same_thread=False, timeout=30.0)
        self._conn.row_factory = sqlite3.Row
        self._closed = False
        now = _utc_now()
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            with self._conn:
                self._conn.executescript(
                    "CREATE TABLE IF NOT EXISTS platform_workspaces_dir ("
                    "id TEXT PRIMARY KEY, name TEXT NOT NULL, branch TEXT NOT NULL, "
                    "isolation_mode TEXT NOT NULL, created_at TEXT NOT NULL); "
                    "CREATE TABLE IF NOT EXISTS platform_rbac_members ("
                    "workspace_id TEXT NOT NULL, actor_id TEXT NOT NULL, role TEXT NOT NULL, "
                    "updated_at TEXT NOT NULL, PRIMARY KEY(workspace_id, actor_id)); "
                    "CREATE INDEX IF NOT EXISTS idx_platform_rbac_ws ON platform_rbac_members(workspace_id);"
                )
                seeds = (
                    ("default", "Sovereign Core Workspace", "main", "seatbelt_local", now),
                )
                for ws_id, name, branch, iso, ts in seeds:
                    self._conn.execute("INSERT OR IGNORE INTO platform_workspaces_dir VALUES (?, ?, ?, ?, ?)", (ws_id, name, branch, iso, ts))
                    self._conn.execute("INSERT OR IGNORE INTO platform_rbac_members VALUES (?, ?, ?, ?)", (ws_id, "local-operator", "owner", ts))

    def close(self) -> None:
        with self._lock:
            if not self._closed:
                self._conn.close()
                self._closed = True

    def list_workspaces(self) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute("SELECT id, name, branch, isolation_mode, created_at FROM platform_workspaces_dir ORDER BY rowid ASC").fetchall()
            return [{"id": str(r[0]), "name": str(r[1]), "branch": str(r[2]), "isolation_mode": str(r[3]), "created_at": str(r[4])} for r in rows]

    def create_workspace(self, workspace_id: str, name: str, branch: str = "main", isolation_mode: str = "seatbelt_local") -> Dict[str, Any]:
        clean_id, clean_name = str(workspace_id or "").strip(), str(name or "").strip()
        clean_branch, clean_iso = str(branch or "main").strip() or "main", str(isolation_mode or "seatbelt_local").strip()
        if not _WORKSPACE_ID_RE.match(clean_id) or not clean_name:
            raise ValueError("Workspace 'id' (1..128 alphanumeric/hyphen/underscore) and 'name' must be valid.")
        if clean_iso not in VALID_ISOLATION_MODES:
            raise ValueError(f"Unsupported isolation_mode '{clean_iso}'. Expected {sorted(VALID_ISOLATION_MODES)}.")
        now = _utc_now()
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO platform_workspaces_dir VALUES (?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET name=excluded.name, branch=excluded.branch, isolation_mode=excluded.isolation_mode",
                (clean_id, clean_name, clean_branch, clean_iso, now),
            )
            self._conn.execute("INSERT OR IGNORE INTO platform_rbac_members VALUES (?, ?, ?, ?)", (clean_id, "local-operator", "owner", now))
            r = self._conn.execute("SELECT id, name, branch, isolation_mode, created_at FROM platform_workspaces_dir WHERE id=?", (clean_id,)).fetchone()
            return {"id": str(r[0]), "name": str(r[1]), "branch": str(r[2]), "isolation_mode": str(r[3]), "created_at": str(r[4])}

    @staticmethod
    def list_roles() -> List[Dict[str, Any]]:
        return [{"role": r, "permissions": sorted(ROLE_PERMISSION_MATRIX[r])} for r in VALID_ROLES]

    def list_members(self, workspace_id: str = "default") -> List[Dict[str, Any]]:
        ws = str(workspace_id or "").strip()
        if not ws:
            raise ValueError("RBAC 'workspace_id' must be non-empty.")
        with self._lock:
            rows = self._conn.execute("SELECT workspace_id, actor_id, role, updated_at FROM platform_rbac_members WHERE workspace_id=? ORDER BY actor_id ASC", (ws,)).fetchall()
            return [{"workspace_id": str(r[0]), "actor_id": str(r[1]), "role": str(r[2]), "permissions": sorted(ROLE_PERMISSION_MATRIX.get(str(r[2]), frozenset())), "updated_at": str(r[3])} for r in rows]

    def upsert_member(self, workspace_id: str, actor_id: str, role: str) -> Dict[str, Any]:
        ws, clean_actor, clean_role = str(workspace_id or "").strip(), str(actor_id or "").strip(), str(role or "").strip().lower()
        if not ws or not clean_actor:
            raise ValueError("RBAC 'workspace_id' and 'actor_id' must be non-empty.")
        if clean_role not in ROLE_PERMISSION_MATRIX:
            raise ValueError(f"Unsupported role '{clean_role}'. Expected {list(VALID_ROLES)}.")
        now = _utc_now()
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO platform_rbac_members VALUES (?, ?, ?, ?) "
                "ON CONFLICT(workspace_id, actor_id) DO UPDATE SET role=excluded.role, updated_at=excluded.updated_at",
                (ws, clean_actor, clean_role, now),
            )
            return {
                "workspace_id": ws, "actor_id": clean_actor, "role": clean_role,
                "permissions": sorted(ROLE_PERMISSION_MATRIX[clean_role]), "updated_at": now,
            }

    def check_permission(
        self, workspace_id: str, actor_id: str, permission: str, explicit_role: Optional[str] = None
    ) -> Dict[str, Any]:
        ws = str(workspace_id or "").strip()
        clean_actor = str(actor_id or "anonymous").strip() or "anonymous"
        clean_perm = str(permission or "").strip()
        if not ws or not clean_perm:
            raise ValueError("RBAC 'workspace_id' and 'permission' must be non-empty.")

        if explicit_role is not None and str(explicit_role).strip():
            role = str(explicit_role).strip().lower()
            if role not in ROLE_PERMISSION_MATRIX:
                raise ValueError(f"Unsupported role '{role}'. Expected {list(VALID_ROLES)}.")
        else:
            with self._lock:
                row = self._conn.execute(
                    "SELECT role FROM platform_rbac_members WHERE workspace_id=? AND actor_id=?", (ws, clean_actor)
                ).fetchone()
                role = str(row["role"]) if row is not None else "viewer"

        perms = ROLE_PERMISSION_MATRIX[role]
        allowed = ("*" in perms) or (clean_perm in perms)
        reason = (
            f"Role '{role}' grants '{clean_perm}' in workspace '{ws}'."
            if allowed
            else f"Role '{role}' lacks permission '{clean_perm}' in workspace '{ws}'."
        )
        return {"workspace_id": ws, "actor_id": clean_actor, "allowed": allowed, "role": role, "permission": clean_perm, "reason": reason}


class SignedWebhookBus:
    """`HMAC-SHA256` signed webhook registry & local-first delivery receipt bus."""

    def __init__(self, db_path: Optional[Union[str, Path]] = None) -> None:
        self._lock = threading.RLock()
        self._db_path, connect_target = _resolve_sqlite_target(db_path)
        self._conn = sqlite3.connect(connect_target, check_same_thread=False, timeout=30.0)
        self._conn.row_factory = sqlite3.Row
        self._closed = False
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            with self._conn:
                self._conn.executescript(
                    "CREATE TABLE IF NOT EXISTS platform_webhooks ("
                    "id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, url TEXT NOT NULL, events_json TEXT NOT NULL, "
                    "description TEXT NOT NULL, secret TEXT NOT NULL, secret_preview TEXT NOT NULL, "
                    "active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL); "
                    "CREATE INDEX IF NOT EXISTS idx_platform_webhooks_ws ON platform_webhooks(workspace_id); "
                    "CREATE TABLE IF NOT EXISTS platform_webhook_deliveries ("
                    "delivery_id TEXT PRIMARY KEY, webhook_id TEXT NOT NULL, workspace_id TEXT NOT NULL, "
                    "event_type TEXT NOT NULL, timestamp TEXT NOT NULL, signature TEXT NOT NULL, "
                    "payload_json TEXT NOT NULL, headers_json TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL); "
                    "CREATE INDEX IF NOT EXISTS idx_platform_wh_deliv_ws ON platform_webhook_deliveries(workspace_id);"
                )

    def close(self) -> None:
        with self._lock:
            if not self._closed:
                self._conn.close()
                self._closed = True

    @staticmethod
    def _event_matches(patterns: Sequence[str], event_type: str) -> bool:
        return any(p == "*" or p == event_type or (p.endswith(".*") and event_type.startswith(p[:-1])) for p in patterns)

    def get_webhook_workspace(self, webhook_id: str) -> str:
        with self._lock:
            row = self._conn.execute("SELECT workspace_id FROM platform_webhooks WHERE id=?", (str(webhook_id or "").strip(),)).fetchone()
            if row is None:
                raise KeyError(f"Webhook '{webhook_id}' not found.")
            return str(row["workspace_id"])

    def list_webhooks(self, workspace_id: str = "default") -> List[Dict[str, Any]]:
        ws = str(workspace_id or "default").strip() or "default"
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, workspace_id, url, events_json, description, secret_preview, active, created_at FROM platform_webhooks WHERE workspace_id=? ORDER BY rowid ASC",
                (ws,),
            ).fetchall()
            return [
                {"id": str(r[0]), "workspace_id": str(r[1]), "url": str(r[2]), "events": json.loads(str(r[3])), "description": str(r[4]), "secret_preview": str(r[5]), "active": bool(r[6]), "created_at": str(r[7])}
                for r in rows
            ]

    def list_deliveries(self, workspace_id: str = "default", limit: int = 25) -> List[Dict[str, Any]]:
        ws = str(workspace_id or "default").strip() or "default"
        with self._lock:
            rows = self._conn.execute(
                "SELECT delivery_id, webhook_id, workspace_id, event_type, timestamp, signature, payload_json, headers_json, status, created_at FROM platform_webhook_deliveries WHERE workspace_id=? ORDER BY rowid DESC LIMIT ?",
                (ws, max(1, int(limit))),
            ).fetchall()
            return [
                {"delivery_id": str(r[0]), "webhook_id": str(r[1]), "workspace_id": str(r[2]), "event_type": str(r[3]), "timestamp": str(r[4]), "signature": str(r[5]), "payload": json.loads(str(r[6])), "headers": json.loads(str(r[7])), "status": str(r[8]), "created_at": str(r[9])}
                for r in rows
            ]

    def create_webhook(self, workspace_id: str, url: str, events: Sequence[str], description: str = "", secret: Optional[str] = None) -> Dict[str, Any]:
        ws = str(workspace_id or "").strip()
        if not ws:
            raise WebhookValidationError("Webhook 'workspace_id' must be non-empty.")
        clean_url = validate_webhook_url(url)
        clean_events = [str(e).strip() for e in (events or []) if str(e).strip()]
        if not clean_events:
            raise WebhookValidationError("Webhook 'events' must include at least one event pattern.")
        signing_secret = str(secret).strip() if secret and str(secret).strip() else f"whsec_{secrets.token_hex(16)}"
        preview, wh_id, now, desc = mask_secret(signing_secret), f"wh-{uuid.uuid4().hex[:10]}", _utc_now(), str(description or "").strip()
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO platform_webhooks VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)",
                (wh_id, ws, clean_url, json.dumps(clean_events, separators=(",", ":")), desc, signing_secret, preview, now),
            )
        return {"id": wh_id, "workspace_id": ws, "url": clean_url, "events": clean_events, "description": desc, "secret_preview": preview, "active": True, "created_at": now}

    def delete_webhook(self, workspace_id: Optional[str], webhook_id: str) -> Dict[str, Any]:
        clean_id = str(webhook_id or "").strip()
        with self._lock, self._conn:
            row = self._conn.execute("SELECT workspace_id FROM platform_webhooks WHERE id=?", (clean_id,)).fetchone()
            if row is None:
                raise KeyError(f"Webhook '{clean_id}' not found.")
            actual_ws = str(row["workspace_id"])
            if workspace_id and str(workspace_id).strip() not in {"", "default", actual_ws}:
                raise KeyError(f"Webhook '{clean_id}' not found in workspace '{workspace_id}'.")
            self._conn.execute("DELETE FROM platform_webhooks WHERE id=?", (clean_id,))
            return {"deleted": True, "revoked": True, "webhook_id": clean_id, "workspace_id": actual_ws}

    def emit_event(
        self, workspace_id: str, event_type: str, payload: Dict[str, Any], webhook_id: Optional[str] = None, deliver_http: bool = False
    ) -> List[Dict[str, Any]]:
        ws, clean_event = str(workspace_id or "default").strip() or "default", str(event_type or "").strip()
        if not clean_event:
            raise WebhookValidationError("Webhook 'event_type' must be non-empty.")

        with self._lock:
            if webhook_id is not None:
                row = self._conn.execute("SELECT * FROM platform_webhooks WHERE id=?", (str(webhook_id).strip(),)).fetchone()
                if row is None:
                    raise KeyError(f"Webhook '{webhook_id}' not found.")
                targets = [row]
            else:
                rows = self._conn.execute("SELECT * FROM platform_webhooks WHERE workspace_id=? AND active=1 ORDER BY rowid ASC", (ws,)).fetchall()
                targets = [r for r in rows if self._event_matches(json.loads(str(r["events_json"])), clean_event)]

        deliveries: List[Dict[str, Any]] = []
        for target in targets:
            delivery_id, timestamp, target_ws = f"whd-{uuid.uuid4().hex[:12]}", str(int(time.time())), str(target["workspace_id"])
            envelope = {"event_id": delivery_id, "event_type": clean_event, "workspace_id": target_ws, "data": payload}
            canonical = _canonical_json(envelope)
            sig_hex = hmac.new(str(target["secret"]).encode("utf-8"), f"{timestamp}.{canonical}".encode("utf-8"), hashlib.sha256).hexdigest()
            sig_header = f"sha256={sig_hex}"
            headers = {
                "Content-Type": "application/json", "X-Keelway-Signature-256": sig_header,
                "X-Keelway-Timestamp": timestamp, "X-Keelway-Event-Id": delivery_id,
            }
            delivery_status = "recorded_local"
            if deliver_http:
                safe_url = validate_webhook_url(str(target["url"]))
                import httpx

                try:
                    with httpx.Client(timeout=5.0, follow_redirects=False) as http_client:
                        resp = http_client.post(safe_url, content=canonical.encode("utf-8"), headers=headers)
                        delivery_status = f"http_{resp.status_code}"
                except httpx.HTTPError:
                    delivery_status = "delivery_failed"

            now = _utc_now()
            with self._lock, self._conn:
                self._conn.execute(
                    "INSERT INTO platform_webhook_deliveries VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (delivery_id, str(target["id"]), target_ws, clean_event, timestamp, sig_header, canonical, json.dumps(headers, separators=(",", ":")), delivery_status, now),
                )
            deliveries.append({
                "delivery_id": delivery_id, "event_id": delivery_id, "webhook_id": str(target["id"]), "workspace_id": target_ws,
                "event_type": clean_event, "timestamp": timestamp, "signature": sig_header, "delivered": delivery_status != "delivery_failed",
                "headers": headers, "payload": envelope, "status": delivery_status, "created_at": now,
            })
        return deliveries

    @staticmethod
    def verify_signature(
        payload: Any, signature: str, secret: str, timestamp: Union[str, int, float], tolerance_seconds: int = 300
    ) -> Dict[str, Any]:
        clean_sig, clean_secret = str(signature or "").strip(), str(secret or "").strip()
        ts_str = str(timestamp if timestamp is not None else "").strip()
        if not clean_secret:
            return {"valid": False, "reason": "missing_secret"}
        if not clean_sig.startswith("sha256="):
            return {"valid": False, "reason": "invalid_signature_format"}
        if not ts_str:
            return {"valid": False, "reason": "invalid_timestamp"}
        try:
            parsed_ts = float(ts_str)
        except ValueError:
            try:
                parsed_ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00")).timestamp()
            except ValueError:
                return {"valid": False, "reason": "invalid_timestamp"}

        if abs(time.time() - parsed_ts) > max(1, int(tolerance_seconds)):
            return {"valid": False, "reason": "timestamp_expired"}
        canonical = _canonical_json(payload)
        expected = hmac.new(clean_secret.encode("utf-8"), f"{ts_str}.{canonical}".encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(clean_sig, f"sha256={expected}"):
            return {"valid": False, "reason": "signature_mismatch"}
        return {"valid": True, "reason": "verified"}


workspace_rbac_controller = WorkspaceRbacController()
signed_webhook_bus = SignedWebhookBus()
