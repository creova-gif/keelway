"""
Enterprise OIDC/SAML Federation, SCIM 2.0 Directory Sync, Dual-Human P-10 Quorum,
Tamper-Evident SIEM Audit Exporter & Prometheus/OTLP Observability (`core.platform.enterprise_identity_siem`).
"""

from __future__ import annotations

import base64
from datetime import datetime, timezone
import hashlib
import hmac
import ipaddress
import json
import os
from pathlib import Path
import re
import sqlite3
import threading
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union
from urllib.parse import urlparse
import uuid

from core.platform.mcp_registry import redact_sensitive_text
from core.platform.rbac_webhooks import WorkspaceRbacController
from core.platform.vault import (
    _HAS_CRYPTOGRAPHY,
    _StdlibAESGCM,
    _derive_aes256_key,
    _load_or_create_master_key,
    _resolve_sqlite_target,
)
from core.security.redact import redact_payload

if _HAS_CRYPTOGRAPHY:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

VALID_ENTERPRISE_ROLES: Dict[str, int] = {"viewer": 0, "builder": 1, "operator": 2, "admin": 3, "owner": 4}
VALID_SIEM_FORMATS = frozenset({"ocsf", "cef", "jsonl"})
VALID_METRICS_FORMATS = frozenset({"prometheus", "otlp_json"})
_ALLOWED_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
_BLOCKED_SSRF_HOSTS = frozenset({
    "169.254.169.254", "169.254.170.2", "metadata.google.internal",
    "metadata.goog", "metadata", "100.100.100.200", "0.0.0.0",
})
_AUTONOMOUS_PRINCIPAL_PREFIXES = (
    "agent-", "bot-", "system-", "agent:", "bot:", "system:", "service-agent-", "service-agent:",
)
_SHORT_OPENAI_KEY_RE = re.compile(r"\bsk-(?:proj-|live-|test-)?[A-Za-z0-9_-]{12,}")
_CGNAT_NET = ipaddress.ip_network("100.64.0.0/10")

_SCHEMA_SQL = (
    "CREATE TABLE IF NOT EXISTS platform_oidc_providers ("
    "workspace_id TEXT PRIMARY KEY, issuer_url TEXT NOT NULL, client_id TEXT NOT NULL, "
    "secret_nonce BLOB NOT NULL, secret_ciphertext BLOB NOT NULL, secret_fingerprint TEXT NOT NULL, "
    "group_role_mapping_json TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1, updated_at TEXT NOT NULL); "
    "CREATE TABLE IF NOT EXISTS platform_scim_users ("
    "id TEXT NOT NULL, workspace_id TEXT NOT NULL, user_name TEXT NOT NULL, display_name TEXT NOT NULL, "
    "active INTEGER NOT NULL DEFAULT 1, groups_json TEXT NOT NULL, mapped_role TEXT NOT NULL, "
    "updated_at TEXT NOT NULL, PRIMARY KEY(workspace_id, id), UNIQUE(workspace_id, user_name)); "
    "CREATE INDEX IF NOT EXISTS idx_platform_scim_users_ws ON platform_scim_users(workspace_id); "
    "CREATE TABLE IF NOT EXISTS platform_p10_quorums ("
    "workspace_id TEXT NOT NULL, proposal_id TEXT NOT NULL, initiator_id TEXT NOT NULL, "
    "required_approvals INTEGER NOT NULL, approval_count INTEGER NOT NULL, status TEXT NOT NULL, "
    "approvals_json TEXT NOT NULL, quorum_receipt_sha256 TEXT NOT NULL, updated_at TEXT NOT NULL, "
    "PRIMARY KEY(workspace_id, proposal_id)); "
    "CREATE INDEX IF NOT EXISTS idx_platform_p10_quorums_ws ON platform_p10_quorums(workspace_id, status); "
    "CREATE TABLE IF NOT EXISTS platform_siem_exports ("
    "export_id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, export_format TEXT NOT NULL, "
    "record_count INTEGER NOT NULL, batch_sha256 TEXT NOT NULL, exported_at TEXT NOT NULL); "
    "CREATE INDEX IF NOT EXISTS idx_platform_siem_exports_ws ON platform_siem_exports(workspace_id);"
)

_METRIC_SPECS: Tuple[Tuple[str, str, str], ...] = (
    ("keelway_kflow_runs_total", "counter", "Total KFlow topological DAG workflow runs recorded for workspace."),
    ("keelway_crdt_entries_total", "gauge", "Total KSpaces LWW-Element-Set CRDT entries stored for workspace."),
    ("keelway_mcp_servers_total", "gauge", "Total external MCP servers registered in workspace."),
    ("keelway_scim_active_users", "gauge", "Active SCIM 2.0 provisioned enterprise users in workspace."),
    ("keelway_p10_quorum_approved_total", "counter", "Total Dual-Human P-10 proposals that achieved quorum approval."),
    ("keelway_siem_exports_total", "counter", "Total tamper-evident SIEM audit export batches generated."),
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(segment: str) -> bytes:
    if not segment or any(ch.isspace() for ch in segment):
        raise PermissionError("Malformed JWT base64url segment.")
    pad = "=" * ((4 - (len(segment) % 4)) % 4)
    try:
        return base64.urlsafe_b64decode((segment + pad).encode("ascii"))
    except Exception as exc:
        raise PermissionError("Invalid base64url encoding in OIDC token.") from exc


def _scrub_strings(obj: Any) -> Any:
    if isinstance(obj, str):
        clean, _ = redact_sensitive_text(obj)
        for match in reversed(list(_SHORT_OPENAI_KEY_RE.finditer(clean))):
            s_idx, e_idx = match.span()
            if not clean[s_idx:e_idx].startswith("[REDACTED"):
                clean = clean[:s_idx] + "[REDACTED_OPENAI_KEY]" + clean[e_idx:]
        return clean
    if isinstance(obj, dict):
        return {str(k): _scrub_strings(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_scrub_strings(v) for v in obj]
    if isinstance(obj, tuple):
        return tuple(_scrub_strings(v) for v in obj)
    return obj


def redact_secrets(value: Any) -> Any:
    """Scrub secrets and credentials across strings, dicts, and lists before persistence or SIEM export."""
    redacted_obj, _ = redact_payload(value)
    return _scrub_strings(redacted_obj)


def validate_oidc_issuer_url(issuer_url: str) -> str:
    """Validate OIDC/SAML issuer URL and reject SSRF targets, metadata IPs, private RFC1918, and file://."""
    clean = str(issuer_url or "").strip()
    if not clean or len(clean) > 2048:
        raise ValueError("OIDC 'issuer_url' must be a non-empty URL.")
    parsed = urlparse(clean)
    scheme = (parsed.scheme or "").lower()
    if scheme not in {"https", "http"}:
        raise ValueError(f"Unsupported OIDC issuer scheme '{scheme or 'empty'}'; expected https:// or loopback http://.")
    if parsed.username or parsed.password:
        raise ValueError("OIDC 'issuer_url' must not embed credentials.")
    host = (parsed.hostname or "").strip().lower().rstrip(".")
    if not host:
        raise ValueError("OIDC 'issuer_url' is missing a valid hostname.")
    if host in _BLOCKED_SSRF_HOSTS or host.startswith("169.254.") or host.endswith(".internal"):
        raise ValueError(f"Blocked SSRF OIDC issuer host '{host}'.")

    try:
        ip_obj = ipaddress.ip_address(host)
        candidates = [ip_obj] + ([ip_obj.ipv4_mapped] if isinstance(ip_obj, ipaddress.IPv6Address) and ip_obj.ipv4_mapped else [])
        for ip_item in candidates:
            if ip_item.is_unspecified or ip_item.is_link_local or ip_item.is_multicast or (isinstance(ip_item, ipaddress.IPv4Address) and ip_item in _CGNAT_NET):
                raise ValueError(f"Blocked SSRF/link-local OIDC issuer IP '{host}'.")
            if ip_item.is_private and not ip_item.is_loopback:
                raise ValueError(f"Blocked private RFC1918 OIDC issuer IP '{host}'.")
    except ValueError as exc:
        if "Blocked " in str(exc):
            raise

    if scheme == "http" and host not in _ALLOWED_LOOPBACK_HOSTS:
        raise ValueError("Plaintext http:// OIDC issuers are restricted to loopback (127.0.0.1 / localhost).")
    return clean


def resolve_enterprise_db_target(db_path: Optional[Union[str, Path]] = None) -> Tuple[Union[str, Path], str]:
    """Resolve SQLite WAL target honoring explicit `db_path`, `KEELWAY_RUNTIME_DB_PATH`, `KEELWAY_STATE_DIR`, or `HOME`."""
    if db_path is not None:
        return _resolve_sqlite_target(db_path)
    runtime_override = os.environ.get("KEELWAY_RUNTIME_DB_PATH", "").strip()
    if runtime_override:
        return _resolve_sqlite_target(runtime_override)
    state_dir = os.environ.get("KEELWAY_STATE_DIR", "").strip()
    if state_dir:
        return _resolve_sqlite_target(Path(state_dir).expanduser() / "platform_runtime.db")
    return _resolve_sqlite_target(None)


def build_hs256_id_token(
    issuer: str,
    client_id: Union[str, List[str]],
    signing_secret: str,
    subject: str = "enterprise-user",
    email: str = "",
    groups: Optional[Sequence[str]] = None,
    exp_offset_seconds: int = 3600,
    nbf_offset_seconds: Optional[int] = None,
    extra_claims: Optional[Dict[str, Any]] = None,
    header_overrides: Optional[Dict[str, Any]] = None,
) -> str:
    """Deterministically mint an HS256 OIDC ID token for enterprise CLI and test verification."""
    now = int(time.time())
    header: Dict[str, Any] = {"alg": "HS256", "typ": "JWT", **(header_overrides or {})}
    claims: Dict[str, Any] = {"iss": issuer, "aud": client_id, "sub": subject, "iat": now, "exp": now + int(exp_offset_seconds)}
    if email:
        claims["email"] = email
    if groups is not None:
        claims["groups"] = [str(g) for g in groups]
    if nbf_offset_seconds is not None:
        claims["nbf"] = now + int(nbf_offset_seconds)
    if extra_claims:
        claims.update(extra_claims)
    signing_input = f"{_b64url_encode(_canonical_json(header).encode('utf-8'))}.{_b64url_encode(_canonical_json(claims).encode('utf-8'))}"
    if header.get("alg") == "none":
        return f"{signing_input}."
    sig = hmac.new(signing_secret.encode("utf-8"), signing_input.encode("ascii"), hashlib.sha256).digest()
    return f"{signing_input}.{_b64url_encode(sig)}"


def _map_groups_to_role(groups: Sequence[str], mapping: Dict[str, str]) -> str:
    best = "viewer"
    for grp in groups:
        cand = mapping.get(str(grp).strip())
        if cand in VALID_ENTERPRISE_ROLES and VALID_ENTERPRISE_ROLES[cand] > VALID_ENTERPRISE_ROLES[best]:
            best = cand
    return best


def _normalize_groups(groups: Optional[Sequence[Any]]) -> List[str]:
    if groups is None:
        return []
    if isinstance(groups, (str, bytes)) or not isinstance(groups, Sequence):
        raise ValueError("'groups' must be a list of group names.")
    out: List[str] = []
    seen: set[str] = set()
    for item in groups:
        raw = item.get("value") or item.get("display") if isinstance(item, dict) else item
        clean = str(raw or "").strip()
        if clean and clean not in seen:
            out.append(clean)
            seen.add(clean)
    return out


class EnterpriseIdentitySiemManager:
    """SQLite WAL manager for OIDC/SAML SSO, SCIM 2.0, Dual-Human P-10 Quorum, SIEM & OTLP/Prometheus Metrics."""

    build_hs256_id_token = staticmethod(build_hs256_id_token)

    def __init__(self, db_path: Optional[Union[str, Path]] = None) -> None:
        self._lock = threading.RLock()
        self._explicit_db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._active_target: Optional[str] = None
        self._db_path: Union[str, Path] = ":memory:"
        self._journal_mode = "unknown"
        self._closed = False
        with self._lock:
            self._ensure_conn()

    def _ensure_conn(self) -> sqlite3.Connection:
        resolved_path, connect_target = resolve_enterprise_db_target(self._explicit_db_path)
        if self._conn is not None and not self._closed and self._active_target == connect_target:
            return self._conn
        if self._conn is not None and not self._closed:
            self._conn.close()
        conn = sqlite3.connect(connect_target, check_same_thread=False, timeout=30.0)
        conn.row_factory = sqlite3.Row
        mode_row = conn.execute("PRAGMA journal_mode=WAL").fetchone()
        self._journal_mode = str(mode_row[0]).lower() if mode_row else "unknown"
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        with conn:
            conn.executescript(_SCHEMA_SQL)
        self._conn, self._active_target, self._db_path, self._closed = conn, connect_target, resolved_path, False
        return conn

    def _cipher_for_current_db(self) -> Any:
        key = _derive_aes256_key(_load_or_create_master_key(None, None, self._db_path))
        return AESGCM(key) if _HAS_CRYPTOGRAPHY else _StdlibAESGCM(key)

    @property
    def db_path(self) -> Union[str, Path]:
        with self._lock:
            if self._explicit_db_path is None and not self._closed:
                self._ensure_conn()
            return self._db_path

    @property
    def journal_mode(self) -> str:
        return self._journal_mode

    def close(self) -> None:
        with self._lock:
            if self._conn is not None and not self._closed:
                self._conn.close()
                self._closed = True

    @staticmethod
    def _clean_ws(workspace_id: str) -> str:
        ws = str(workspace_id or "").strip()
        if not ws:
            raise ValueError("'workspace_id' must be non-empty.")
        return ws

    def configure_oidc(
        self, workspace_id: str, issuer_url: str, client_id: str,
        signing_secret: Optional[str] = None, group_role_mapping: Optional[Dict[str, str]] = None, enabled: bool = True,
    ) -> Dict[str, Any]:
        ws = self._clean_ws(workspace_id)
        clean_issuer = validate_oidc_issuer_url(issuer_url)
        clean_client = str(client_id or "").strip()
        if not clean_client:
            raise ValueError("OIDC 'client_id' must be non-empty.")
        if group_role_mapping is not None and not isinstance(group_role_mapping, dict):
            raise ValueError("OIDC 'group_role_mapping' must be an object mapping IdP groups to roles.")

        clean_map: Dict[str, str] = {}
        for raw_group, raw_role in (group_role_mapping or {}).items():
            grp, role = str(raw_group or "").strip(), str(raw_role or "").strip().lower()
            if not grp:
                raise ValueError("OIDC 'group_role_mapping' keys must be non-empty group names.")
            if role not in VALID_ENTERPRISE_ROLES:
                raise ValueError(f"Unsupported mapped role '{role}'. Expected {sorted(VALID_ENTERPRISE_ROLES)}.")
            clean_map[grp] = role

        now, aad = _utc_now(), f"oidc:{ws}".encode("utf-8")
        with self._lock:
            conn, cipher = self._ensure_conn(), self._cipher_for_current_db()
            existing = conn.execute(
                "SELECT secret_nonce, secret_ciphertext, secret_fingerprint FROM platform_oidc_providers WHERE workspace_id=?", (ws,)
            ).fetchone()
            if signing_secret is not None and str(signing_secret) != "":
                raw_sec = str(signing_secret)
                if len(raw_sec) < 16:
                    raise ValueError("OIDC 'signing_secret' must be at least 16 characters.")
                nonce = os.urandom(12)
                ciphertext = cipher.encrypt(nonce, raw_sec.encode("utf-8"), aad)
                fp = f"sha256:{hashlib.sha256(raw_sec.encode('utf-8')).hexdigest()}"
            elif existing is not None and bytes(existing["secret_ciphertext"]):
                nonce, ciphertext, fp = bytes(existing["secret_nonce"]), bytes(existing["secret_ciphertext"]), str(existing["secret_fingerprint"])
            else:
                raise ValueError("OIDC 'signing_secret' (>= 16 chars) is required when configuring a provider.")

            with conn:
                conn.execute(
                    "INSERT INTO platform_oidc_providers VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
                    "ON CONFLICT(workspace_id) DO UPDATE SET issuer_url=excluded.issuer_url, client_id=excluded.client_id, "
                    "secret_nonce=excluded.secret_nonce, secret_ciphertext=excluded.secret_ciphertext, "
                    "secret_fingerprint=excluded.secret_fingerprint, group_role_mapping_json=excluded.group_role_mapping_json, "
                    "enabled=excluded.enabled, updated_at=excluded.updated_at",
                    (ws, clean_issuer, clean_client, nonce, ciphertext, fp, _canonical_json(clean_map), 1 if enabled else 0, now),
                )
        return {
            "workspace_id": ws, "enabled": bool(enabled), "issuer_url": clean_issuer, "client_id": clean_client,
            "group_role_mapping": clean_map, "signing_secret_configured": True, "signing_secret_fingerprint": fp, "updated_at": now,
        }

    def get_oidc(self, workspace_id: str = "default") -> Dict[str, Any]:
        ws = self._clean_ws(workspace_id)
        with self._lock:
            row = self._ensure_conn().execute(
                "SELECT issuer_url, client_id, secret_ciphertext, secret_fingerprint, group_role_mapping_json, enabled, updated_at "
                "FROM platform_oidc_providers WHERE workspace_id=?", (ws,),
            ).fetchone()
        if row is None:
            return {
                "workspace_id": ws, "enabled": False, "issuer_url": "", "client_id": "",
                "group_role_mapping": {}, "signing_secret_configured": False, "signing_secret_fingerprint": None, "updated_at": None,
            }
        has_secret = bool(bytes(row["secret_ciphertext"]))
        return {
            "workspace_id": ws, "enabled": bool(int(row["enabled"])), "issuer_url": str(row["issuer_url"]),
            "client_id": str(row["client_id"]), "group_role_mapping": json.loads(str(row["group_role_mapping_json"])),
            "signing_secret_configured": has_secret, "signing_secret_fingerprint": str(row["secret_fingerprint"]) if has_secret else None,
            "updated_at": str(row["updated_at"]),
        }

    def exchange_oidc_token(self, workspace_id: str, id_token: str) -> Dict[str, Any]:
        ws = self._clean_ws(workspace_id)
        raw_token = str(id_token or "").strip()
        if not raw_token:
            raise ValueError("OIDC 'id_token' must be non-empty.")

        with self._lock:
            row = self._ensure_conn().execute(
                "SELECT issuer_url, client_id, secret_nonce, secret_ciphertext, group_role_mapping_json, enabled "
                "FROM platform_oidc_providers WHERE workspace_id=?", (ws,),
            ).fetchone()
            if row is None or not bool(int(row["enabled"])) or not bytes(row["secret_ciphertext"]):
                raise PermissionError(f"OIDC federation is disabled or unconfigured for workspace '{ws}'.")
            try:
                signing_secret = self._cipher_for_current_db().decrypt(
                    bytes(row["secret_nonce"]), bytes(row["secret_ciphertext"]), f"oidc:{ws}".encode("utf-8")
                )
            except Exception as exc:
                raise PermissionError("OIDC signing secret decryption failed.") from exc

        parts = raw_token.split(".")
        if len(parts) != 3 or not parts[0] or not parts[1] or not parts[2]:
            raise PermissionError("Malformed compact JWT; expected 3 non-empty segments (header.payload.signature).")
        try:
            header = json.loads(_b64url_decode(parts[0]).decode("utf-8"))
            claims = json.loads(_b64url_decode(parts[1]).decode("utf-8"))
        except PermissionError:
            raise
        except Exception as exc:
            raise PermissionError("Malformed JWT JSON header or payload.") from exc

        if not isinstance(header, dict) or not isinstance(claims, dict):
            raise PermissionError("JWT header and claims payload must be JSON objects.")
        if header.get("alg") != "HS256":
            raise PermissionError(f"Unsupported or disallowed JWT alg '{header.get('alg')}'; strictly expected 'HS256'.")

        sig_bytes = _b64url_decode(parts[2])
        expected_sig = hmac.new(signing_secret, f"{parts[0]}.{parts[1]}".encode("ascii"), hashlib.sha256).digest()
        if not hmac.compare_digest(sig_bytes, expected_sig):
            raise PermissionError("OIDC token HMAC-SHA256 signature verification failed.")

        expected_iss, expected_aud = str(row["issuer_url"]), str(row["client_id"])
        if claims.get("iss") != expected_iss:
            raise PermissionError("OIDC token 'iss' claim does not match configured issuer_url.")
        aud_claim = claims.get("aud")
        aud_ok = (aud_claim == expected_aud) if isinstance(aud_claim, str) else (isinstance(aud_claim, list) and expected_aud in aud_claim)
        if not aud_ok:
            raise PermissionError("OIDC token 'aud' claim does not match configured client_id.")

        now = time.time()
        exp_val, nbf_val = claims.get("exp"), claims.get("nbf")
        if isinstance(exp_val, bool) or not isinstance(exp_val, (int, float)) or float(exp_val) <= (now - 30.0):
            raise PermissionError("OIDC token has expired or is missing a valid numeric 'exp' claim.")
        if nbf_val is not None and (isinstance(nbf_val, bool) or not isinstance(nbf_val, (int, float)) or float(nbf_val) > (now + 30.0)):
            raise PermissionError("OIDC token is not yet valid ('nbf' claim is in the future).")

        sub = str(claims.get("sub") or "").strip()
        if not sub:
            raise PermissionError("OIDC token is missing a non-empty 'sub' claim.")
        raw_groups = claims.get("groups", [])
        if raw_groups is None:
            groups: List[str] = []
        elif isinstance(raw_groups, str):
            groups = [raw_groups.strip()] if raw_groups.strip() else []
        elif isinstance(raw_groups, list):
            groups = [str(g).strip() for g in raw_groups if str(g).strip()]
        else:
            raise PermissionError("OIDC token 'groups' claim must be a list of strings.")

        mapped_role = _map_groups_to_role(groups, json.loads(str(row["group_role_mapping_json"])))
        return {
            "workspace_id": ws, "authenticated": True, "subject": sub, "email": str(claims.get("email") or "").strip(),
            "groups": groups, "mapped_role": mapped_role, "issuer": expected_iss,
        }

    @staticmethod
    def _scim_resource(row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"], "id": str(row["id"]),
            "workspace_id": str(row["workspace_id"]), "userName": str(row["user_name"]),
            "displayName": str(row["display_name"]), "active": bool(int(row["active"])),
            "groups": json.loads(str(row["groups_json"])), "mapped_role": str(row["mapped_role"]),
            "updated_at": str(row["updated_at"]),
        }

    def provision_scim_user(
        self, workspace_id: str, user_name: str, display_name: str = "",
        groups: Optional[Sequence[Any]] = None, active: bool = True, rbac: Optional[WorkspaceRbacController] = None,
    ) -> Dict[str, Any]:
        ws, clean_user = self._clean_ws(workspace_id), str(user_name or "").strip()
        if not clean_user:
            raise ValueError("SCIM 'user_name' ('userName') must be non-empty.")
        clean_display = str(display_name or "").strip() or clean_user
        clean_groups = _normalize_groups(groups)
        mapped_role = _map_groups_to_role(clean_groups, self.get_oidc(ws)["group_role_mapping"]) if active else "viewer"
        now = _utc_now()

        with self._lock:
            conn = self._ensure_conn()
            existing = conn.execute("SELECT id FROM platform_scim_users WHERE workspace_id=? AND user_name=?", (ws, clean_user)).fetchone()
            scim_id = str(existing["id"]) if existing is not None else f"scim-{uuid.uuid4().hex[:12]}"
            with conn:
                conn.execute(
                    "INSERT INTO platform_scim_users VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
                    "ON CONFLICT(workspace_id, user_name) DO UPDATE SET display_name=excluded.display_name, "
                    "active=excluded.active, groups_json=excluded.groups_json, mapped_role=excluded.mapped_role, updated_at=excluded.updated_at",
                    (scim_id, ws, clean_user, clean_display, 1 if active else 0, _canonical_json(clean_groups), mapped_role, now),
                )
            row = conn.execute("SELECT * FROM platform_scim_users WHERE workspace_id=? AND id=?", (ws, scim_id)).fetchone()
        if rbac is not None:
            rbac.upsert_member(ws, clean_user, mapped_role if active else "viewer")
        return self._scim_resource(row)  # type: ignore[arg-type]

    def patch_scim_user(
        self, workspace_id: str, scim_user_id: str, active: Optional[bool] = None,
        groups: Optional[Sequence[Any]] = None, display_name: Optional[str] = None, rbac: Optional[WorkspaceRbacController] = None,
    ) -> Dict[str, Any]:
        ws, clean_id = self._clean_ws(workspace_id), str(scim_user_id or "").strip()
        if not clean_id:
            raise KeyError("SCIM user id must be non-empty.")
        oidc_map, now = self.get_oidc(ws)["group_role_mapping"], _utc_now()

        with self._lock:
            conn = self._ensure_conn()
            existing = conn.execute("SELECT * FROM platform_scim_users WHERE workspace_id=? AND id=?", (ws, clean_id)).fetchone()
            if existing is None:
                raise KeyError(f"SCIM user '{clean_id}' not found in workspace '{ws}'.")
            next_active = bool(int(existing["active"])) if active is None else bool(active)
            next_groups = json.loads(str(existing["groups_json"])) if groups is None else _normalize_groups(groups)
            next_display = str(existing["display_name"]) if display_name is None else (str(display_name).strip() or str(existing["user_name"]))
            next_role = _map_groups_to_role(next_groups, oidc_map) if next_active else "viewer"
            with conn:
                conn.execute(
                    "UPDATE platform_scim_users SET display_name=?, active=?, groups_json=?, mapped_role=?, updated_at=? WHERE workspace_id=? AND id=?",
                    (next_display, 1 if next_active else 0, _canonical_json(next_groups), next_role, now, ws, clean_id),
                )
            row = conn.execute("SELECT * FROM platform_scim_users WHERE workspace_id=? AND id=?", (ws, clean_id)).fetchone()
        if rbac is not None:
            rbac.upsert_member(ws, str(existing["user_name"]), next_role if next_active else "viewer")
        return self._scim_resource(row)  # type: ignore[arg-type]

    def list_scim_users(self, workspace_id: str = "default") -> Dict[str, Any]:
        ws = self._clean_ws(workspace_id)
        with self._lock:
            rows = self._ensure_conn().execute("SELECT * FROM platform_scim_users WHERE workspace_id=? ORDER BY user_name ASC", (ws,)).fetchall()
        resources = [self._scim_resource(r) for r in rows]
        return {
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:ListResponse"],
            "workspace_id": ws, "totalResults": len(resources), "Resources": resources,
        }

    def approve_p10_quorum(
        self, workspace_id: str, proposal_id: str, approver_id: str, approver_role: str,
        initiator_id: str = "", required_approvals: int = 2, reason: str = "",
    ) -> Dict[str, Any]:
        ws, clean_prop = self._clean_ws(workspace_id), str(proposal_id or "").strip()
        if not clean_prop:
            raise ValueError("P-10 quorum 'proposal_id' must be non-empty.")
        if isinstance(required_approvals, bool) or not isinstance(required_approvals, int) or required_approvals < 2:
            raise ValueError("Dual-human P-10 quorum requires 'required_approvals' >= 2.")
        clean_role = str(approver_role or "").strip().lower()
        if clean_role not in {"owner", "operator"}:
            raise PermissionError(f"Dual-human P-10 quorum requires 'owner' or 'operator' role; role '{clean_role or 'none'}' is denied.")
        clean_approver = str(approver_id or "").strip()
        if not clean_approver or clean_approver.lower().startswith(_AUTONOMOUS_PRINCIPAL_PREFIXES):
            raise PermissionError(f"Autonomous or empty principal '{clean_approver}' cannot approve human-only P-10 quorum.")
        clean_init = str(initiator_id or "").strip()
        if clean_init and clean_approver == clean_init:
            raise PermissionError("Self-approval is forbidden: proposal initiator cannot approve own P-10 quorum.")

        clean_reason, now = str(redact_secrets(str(reason or "").strip())), _utc_now()
        with self._lock:
            conn = self._ensure_conn()
            existing = conn.execute(
                "SELECT initiator_id, required_approvals, approvals_json FROM platform_p10_quorums WHERE workspace_id=? AND proposal_id=?",
                (ws, clean_prop),
            ).fetchone()
            if existing is not None:
                final_init = str(existing["initiator_id"] or "").strip() or clean_init
                if final_init and clean_approver == final_init:
                    raise PermissionError("Self-approval is forbidden: approver matches recorded proposal initiator.")
                approvals: List[Dict[str, Any]] = json.loads(str(existing["approvals_json"]))
                if any(str(item.get("approver_id")) == clean_approver for item in approvals):
                    raise RuntimeError("Duplicate quorum approval from same human principal")
                effective_req = max(int(existing["required_approvals"]), required_approvals)
            else:
                final_init, approvals, effective_req = clean_init, [], required_approvals

            approvals.append({"approver_id": clean_approver, "role": clean_role, "reason": clean_reason, "approved_at": now})
            count = len(approvals)
            q_status = "quorum_approved" if count >= effective_req else "awaiting_quorum"
            unsigned = {
                "workspace_id": ws, "proposal_id": clean_prop, "initiator_id": final_init,
                "required_approvals": effective_req, "approval_count": count, "status": q_status, "approvals": approvals,
            }
            receipt = "sha256:" + hashlib.sha256(_canonical_json(unsigned).encode("utf-8")).hexdigest()
            with conn:
                conn.execute(
                    "INSERT INTO platform_p10_quorums VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
                    "ON CONFLICT(workspace_id, proposal_id) DO UPDATE SET initiator_id=excluded.initiator_id, "
                    "required_approvals=excluded.required_approvals, approval_count=excluded.approval_count, status=excluded.status, "
                    "approvals_json=excluded.approvals_json, quorum_receipt_sha256=excluded.quorum_receipt_sha256, updated_at=excluded.updated_at",
                    (ws, clean_prop, final_init, effective_req, count, q_status, _canonical_json(approvals), receipt, now),
                )
        return {**unsigned, "quorum_receipt_sha256": receipt}

    def get_p10_quorum(self, workspace_id: str, proposal_id: str) -> Dict[str, Any]:
        ws, clean_prop = self._clean_ws(workspace_id), str(proposal_id or "").strip()
        with self._lock:
            row = self._ensure_conn().execute(
                "SELECT * FROM platform_p10_quorums WHERE workspace_id=? AND proposal_id=?", (ws, clean_prop)
            ).fetchone()
        if row is None:
            raise KeyError(f"P-10 quorum proposal '{clean_prop}' not found in workspace '{ws}'.")
        return {
            "workspace_id": str(row["workspace_id"]), "proposal_id": str(row["proposal_id"]),
            "initiator_id": str(row["initiator_id"]), "required_approvals": int(row["required_approvals"]),
            "approval_count": int(row["approval_count"]), "status": str(row["status"]),
            "approvals": json.loads(str(row["approvals_json"])), "quorum_receipt_sha256": str(row["quorum_receipt_sha256"]),
        }

    @staticmethod
    def _safe_query(conn: sqlite3.Connection, sql: str, params: Tuple[Any, ...]) -> List[sqlite3.Row]:
        try:
            return conn.execute(sql, params).fetchall()
        except sqlite3.OperationalError:
            return []

    @staticmethod
    def _safe_count(conn: sqlite3.Connection, sql: str, params: Tuple[Any, ...]) -> int:
        try:
            row = conn.execute(sql, params).fetchone()
            return int(row[0]) if row is not None else 0
        except sqlite3.OperationalError:
            return 0

    def export_siem(self, workspace_id: str = "default", export_format: str = "ocsf", limit: int = 50) -> Dict[str, Any]:
        ws, fmt = self._clean_ws(workspace_id), str(export_format or "").strip().lower()
        if fmt not in VALID_SIEM_FORMATS:
            raise ValueError(f"Unsupported SIEM export format '{fmt}'. Expected {sorted(VALID_SIEM_FORMATS)}.")
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1 or limit > 1000:
            raise ValueError("SIEM 'limit' must be an integer between 1 and 1000.")

        now_iso, raw_events = _utc_now(), []
        with self._lock:
            conn = self._ensure_conn()
            for r in self._safe_query(conn, "SELECT proposal_id, status, approval_count, required_approvals, approvals_json, updated_at FROM platform_p10_quorums WHERE workspace_id=? ORDER BY updated_at DESC LIMIT ?", (ws, limit)):
                raw_events.append({"time": str(r["updated_at"]), "class_uid": 3001, "category_name": "Identity & Access Management", "severity_id": 2 if str(r["status"]) == "quorum_approved" else 3, "event_type": "governance.p10_quorum", "activity_name": str(r["status"]), "message": f"P-10 proposal={r['proposal_id']} status={r['status']} approvals={r['approval_count']}/{r['required_approvals']} details={r['approvals_json']}"})
            for r in self._safe_query(conn, "SELECT user_name, display_name, active, mapped_role, updated_at FROM platform_scim_users WHERE workspace_id=? ORDER BY updated_at DESC LIMIT ?", (ws, limit)):
                raw_events.append({"time": str(r["updated_at"]), "class_uid": 3001, "category_name": "Identity & Access Management", "severity_id": 2, "event_type": "identity.scim_user", "activity_name": "provision" if int(r["active"]) else "deactivate", "message": f"SCIM user={r['user_name']} display={r['display_name']} role={r['mapped_role']} active={bool(int(r['active']))}"})
            for r in self._safe_query(conn, "SELECT run_id, workflow_id, status, payload_json, created_at FROM platform_kflow_runs WHERE workspace_id=? ORDER BY created_at DESC LIMIT ?", (ws, limit)):
                raw_events.append({"time": str(r["created_at"]), "class_uid": 6003, "category_name": "Application Activity", "severity_id": 4 if str(r["status"]) == "failed" else 2, "event_type": "automation.kflow_run", "activity_name": str(r["status"]), "message": f"KFlow run={r['run_id']} workflow={r['workflow_id']} status={r['status']} payload={r['payload_json']}"})
            for r in self._safe_query(conn, "SELECT namespace, entry_key, value_json, peer_id, tombstone, updated_at FROM platform_crdt_entries WHERE workspace_id=? ORDER BY updated_at DESC LIMIT ?", (ws, limit)):
                raw_events.append({"time": str(r["updated_at"]), "class_uid": 6003, "category_name": "Application Activity", "severity_id": 2, "event_type": "kspaces.crdt_sync", "activity_name": "remove" if int(r["tombstone"]) else "set", "message": f"CRDT ns={r['namespace']} key={r['entry_key']} peer={r['peer_id']} val={r['value_json']}"})

            raw_events.sort(key=lambda e: str(e["time"]), reverse=True)
            selected = raw_events[:limit] or [{"time": now_iso, "class_uid": 6003, "category_name": "Application Activity", "severity_id": 1, "event_type": "siem.heartbeat", "activity_name": "heartbeat", "message": f"Keelway SIEM audit stream active for workspace {ws}"}]
            records: List[Any] = []
            for ev in selected:
                clean_msg = str(redact_secrets(ev["message"])).replace("\r", " ").replace("\n", " ")
                ocsf_rec = redact_secrets({
                    "class_uid": ev["class_uid"], "category_name": ev["category_name"], "time": ev["time"],
                    "severity_id": ev["severity_id"], "workspace_id": ws, "event_type": ev["event_type"],
                    "activity_name": ev["activity_name"], "message": clean_msg,
                    "metadata": {"version": "1.1.0", "product": {"name": "Keelway", "vendor_name": "Sorvex Labs", "version": "1.0.0"}},
                })
                if fmt == "ocsf":
                    records.append(ocsf_rec)
                elif fmt == "jsonl":
                    records.append(_canonical_json(ocsf_rec))
                else:
                    safe_cef_msg = clean_msg.replace("\\", "\\\\").replace("=", "\\=").replace("|", "\\|")
                    cef_line = f"CEF:0|SorvexLabs|Keelway|1.0.0|{str(ev['event_type']).replace('|', '_')}|{str(ev['activity_name']).replace('|', '_')}|{ev['severity_id']}|workspace={ws} rt={ev['time']} msg={safe_cef_msg}"
                    records.append(str(redact_secrets(cef_line)))

            batch_sha256 = "sha256:" + hashlib.sha256(_canonical_json(records).encode("utf-8")).hexdigest()
            with conn:
                conn.execute("INSERT INTO platform_siem_exports VALUES (?, ?, ?, ?, ?, ?)", (f"siem-{uuid.uuid4().hex[:12]}", ws, fmt, len(records), batch_sha256, now_iso))

        return {"workspace_id": ws, "format": fmt, "record_count": len(records), "batch_sha256": batch_sha256, "exported_at": now_iso, "records": records}

    def get_observability_metrics(self, workspace_id: str = "default", metrics_format: str = "otlp_json") -> Dict[str, Any]:
        ws, raw_fmt = self._clean_ws(workspace_id), str(metrics_format or "").strip().lower()
        norm_fmt = "otlp_json" if raw_fmt == "otlp" else raw_fmt
        if norm_fmt not in VALID_METRICS_FORMATS:
            raise ValueError(f"Unsupported metrics format '{raw_fmt}'. Expected {sorted(VALID_METRICS_FORMATS)}.")

        now_iso, now_ns = _utc_now(), str(time.time_ns())
        with self._lock:
            conn = self._ensure_conn()
            counters: Dict[str, int] = {
                "keelway_kflow_runs_total": self._safe_count(conn, "SELECT COUNT(*) FROM platform_kflow_runs WHERE workspace_id=?", (ws,)),
                "keelway_crdt_entries_total": self._safe_count(conn, "SELECT COUNT(*) FROM platform_crdt_entries WHERE workspace_id=?", (ws,)),
                "keelway_mcp_servers_total": self._safe_count(conn, "SELECT COUNT(*) FROM platform_mcp_servers WHERE workspace_id=?", (ws,)),
                "keelway_scim_active_users": self._safe_count(conn, "SELECT COUNT(*) FROM platform_scim_users WHERE workspace_id=? AND active=1", (ws,)),
                "keelway_p10_quorum_approved_total": self._safe_count(conn, "SELECT COUNT(*) FROM platform_p10_quorums WHERE workspace_id=? AND status='quorum_approved'", (ws,)),
                "keelway_siem_exports_total": self._safe_count(conn, "SELECT COUNT(*) FROM platform_siem_exports WHERE workspace_id=?", (ws,)),
            }

        esc_ws = ws.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
        prom_lines, otlp_metrics = [], []
        dp_attrs = [{"key": "workspace", "value": {"stringValue": ws}}]
        for m_name, m_type, m_help in _METRIC_SPECS:
            val = counters[m_name]
            prom_lines.extend([f"# HELP {m_name} {m_help}", f"# TYPE {m_name} {m_type}", f'{m_name}{{workspace="{esc_ws}"}} {val}'])
            dp = [{"attributes": dp_attrs, "timeUnixNano": now_ns, "asInt": str(val)}]
            body = {"sum": {"dataPoints": dp, "aggregationTemporality": 2, "isMonotonic": True}} if m_type == "counter" else {"gauge": {"dataPoints": dp}}
            otlp_metrics.append({"name": m_name, "description": m_help, "unit": "1", **body})

        otlp_dict: Dict[str, Any] = {
            "resource": {"attributes": [
                {"key": "service.name", "value": {"stringValue": "keelway-core"}},
                {"key": "service.version", "value": {"stringValue": "1.0.0"}},
                {"key": "keelway.workspace_id", "value": {"stringValue": ws}},
            ]},
            "scopeMetrics": [{"scope": {"name": "keelway.platform.observability", "version": "1.0.0"}, "metrics": otlp_metrics}],
        }
        return {
            "workspace_id": ws, "format": norm_fmt, "generated_at": now_iso,
            "counters": counters, "prometheus_text": "\n".join(prom_lines) + "\n", "otlp_resource_metrics": otlp_dict,
        }


enterprise_identity_siem_manager = EnterpriseIdentitySiemManager()
