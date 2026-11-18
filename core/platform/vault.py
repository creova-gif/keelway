"""
Local Encrypted Secret Vault (`LocalSecretVault`) for the Keelway Unified Agent Platform.

Encrypts BYOM API keys, plugin tokens, webhook signing keys, and workspace environment secrets
at rest in SQLite WAL (`platform_secrets`) using `AES-256-GCM` (12-byte random nonce,
`HKDF-SHA256` master-key derivation, and Associated Authenticated Data row binding).
Uses `cryptography` C-extensions with a byte-identical NIST FIPS 197 / SP 800-38D / RFC 5869
stdlib fallback when running in minimal environments without native OpenSSL wheels.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import hmac
import os
from pathlib import Path
import secrets
import sqlite3
import threading
import warnings
from typing import Any, Dict, List, Optional, Tuple, Union

VALID_SECRET_NAMESPACES = frozenset({"byom", "plugin", "plugins", "webhook", "webhooks", "env", "mcp"})
_HKDF_SALT = b"keelway-local-secret-vault-v1"
_HKDF_INFO = b"keelway.platform.vault.aes256gcm"

try:
    from cryptography.exceptions import InvalidTag
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF

    _HAS_CRYPTOGRAPHY = True
except ImportError:  # pragma: no cover - exercised in lightweight Python 3.14 venvs
    _HAS_CRYPTOGRAPHY = False

    class InvalidTag(Exception):  # type: ignore[no-redef]
        """Raised when AES-256-GCM authentication tag verification fails."""


def _gf_mul2(x: int) -> int:
    return ((x << 1) ^ 0x1B) & 0xFF if (x & 0x80) else (x << 1) & 0xFF


def _build_sbox() -> List[int]:
    sbox, p, q = [0] * 256, 1, 1
    while True:
        p = (p ^ (p << 1) ^ (0x11B if p & 0x80 else 0)) & 0xFF
        q ^= q << 1
        q ^= q << 2
        q ^= q << 4
        q = (q ^ (0x09 if q & 0x80 else 0)) & 0xFF
        x = q ^ ((q << 1 | q >> 7) & 0xFF) ^ ((q << 2 | q >> 6) & 0xFF) ^ ((q << 3 | q >> 5) & 0xFF) ^ ((q << 4 | q >> 4) & 0xFF)
        sbox[p] = x ^ 0x63
        if p == 1:
            break
    sbox[0] = 0x63
    return sbox


_SBOX = _build_sbox()


def _aes256_expand_key(key: bytes) -> List[List[int]]:
    w, rcon = [list(key[i : i + 4]) for i in range(0, 32, 4)], 1
    for i in range(8, 60):
        t = list(w[i - 1])
        if i % 8 == 0:
            t, rcon = [_SBOX[t[1]] ^ rcon, _SBOX[t[2]], _SBOX[t[3]], _SBOX[t[0]]], _gf_mul2(rcon)
        elif i % 8 == 4:
            t = [_SBOX[b] for b in t]
        w.append([w[i - 8][j] ^ t[j] for j in range(4)])
    return [[w[r * 4 + c][j] for c in range(4) for j in range(4)] for r in range(15)]


def _aes256_encrypt_block(rk: List[List[int]], block: bytes) -> bytes:
    s = [block[i] ^ rk[0][i] for i in range(16)]
    for rnd in range(1, 14):
        s = [_SBOX[b] for b in s]
        s = [s[0], s[5], s[10], s[15], s[4], s[9], s[14], s[3], s[8], s[13], s[2], s[7], s[12], s[1], s[6], s[11]]
        ns = [0] * 16
        for c in range(0, 16, 4):
            a0, a1, a2, a3 = s[c], s[c + 1], s[c + 2], s[c + 3]
            t = a0 ^ a1 ^ a2 ^ a3
            ns[c : c + 4] = [a0 ^ t ^ _gf_mul2(a0 ^ a1), a1 ^ t ^ _gf_mul2(a1 ^ a2), a2 ^ t ^ _gf_mul2(a2 ^ a3), a3 ^ t ^ _gf_mul2(a3 ^ a0)]
        s = [ns[i] ^ rk[rnd][i] for i in range(16)]
    s = [_SBOX[b] for b in s]
    s = [s[0], s[5], s[10], s[15], s[4], s[9], s[14], s[3], s[8], s[13], s[2], s[7], s[12], s[1], s[6], s[11]]
    return bytes(s[i] ^ rk[14][i] for i in range(16))


def _ghash(h_int: int, aad: bytes, ct: bytes) -> bytes:
    pad_a = aad + b"\x00" * ((16 - len(aad) % 16) % 16)
    pad_c = ct + b"\x00" * ((16 - len(ct) % 16) % 16)
    stream = pad_a + pad_c + (len(aad) * 8).to_bytes(8, "big") + (len(ct) * 8).to_bytes(8, "big")
    y = 0
    for off in range(0, len(stream), 16):
        x, z, v = y ^ int.from_bytes(stream[off : off + 16], "big"), 0, h_int
        for bit in range(127, -1, -1):
            if (x >> bit) & 1:
                z ^= v
            v = (v >> 1) ^ (0xE1 << 120) if (v & 1) else (v >> 1)
        y = z
    return y.to_bytes(16, "big")


class _StdlibAESGCM:
    """NIST SP 800-38D AES-256-GCM authenticated cipher with 96-bit nonces."""

    def __init__(self, key: bytes) -> None:
        if len(key) != 32:
            raise ValueError("AES-256-GCM requires a 32-byte key.")
        self._rk = _aes256_expand_key(key)
        self._h = int.from_bytes(_aes256_encrypt_block(self._rk, b"\x00" * 16), "big")

    def _gctr(self, icb: bytes, data: bytes) -> bytes:
        if not data:
            return b""
        prefix, ctr, out = icb[:12], int.from_bytes(icb[12:], "big"), bytearray()
        for off in range(0, len(data), 16):
            ks = _aes256_encrypt_block(self._rk, prefix + ctr.to_bytes(4, "big"))
            out.extend(b ^ k for b, k in zip(data[off : off + 16], ks))
            ctr = (ctr + 1) & 0xFFFFFFFF
        return bytes(out)

    def encrypt(self, nonce: bytes, data: bytes, associated_data: Optional[bytes]) -> bytes:
        if len(nonce) != 12:
            raise ValueError("AES-256-GCM nonce must be 12 bytes.")
        aad = associated_data or b""
        ct = self._gctr(nonce + b"\x00\x00\x00\x02", data)
        return ct + self._gctr(nonce + b"\x00\x00\x00\x01", _ghash(self._h, aad, ct))

    def decrypt(self, nonce: bytes, data: bytes, associated_data: Optional[bytes]) -> bytes:
        if len(nonce) != 12 or len(data) < 16:
            raise InvalidTag("Invalid AES-256-GCM nonce or ciphertext tag length.")
        ct, tag = data[:-16], data[-16:]
        expected = self._gctr(nonce + b"\x00\x00\x00\x01", _ghash(self._h, associated_data or b"", ct))
        if not hmac.compare_digest(tag, expected):
            raise InvalidTag("AES-256-GCM tag mismatch.")
        return self._gctr(nonce + b"\x00\x00\x00\x02", ct)


class VaultError(Exception):
    """Base error for `LocalSecretVault` operations."""


class VaultTamperError(VaultError):
    """Raised when `AES-256-GCM` authentication fails (`InvalidTag`) due to row/ciphertext tampering."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def mask_secret(secret_value: str) -> str:
    return "****" if len(secret_value) <= 8 else f"{secret_value[:4]}****{secret_value[-4:]}"


def _resolve_sqlite_target(db_path: Optional[Union[str, Path]], env_var: str = "KEELWAY_RUNTIME_DB_PATH") -> Tuple[Union[str, Path], str]:
    raw = str(db_path).strip() if db_path is not None else os.environ.get(env_var, "").strip()
    if raw == ":memory:":
        return ":memory:", ":memory:"
    target = Path(raw).expanduser().resolve() if raw else (Path.home() / ".keelway" / "platform_runtime.db")
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        return target, str(target)
    except OSError as exc:
        # Ephemeral fallback keeps sandboxes/read-only-HOME environments alive,
        # but evidence silently evaporates — it must never be silent.
        if os.environ.get("KEELWAY_DB_FAIL_CLOSED", "").strip().lower() in {"1", "true", "yes", "on"}:
            raise RuntimeError(
                f"KEELWAY_DB_FAIL_CLOSED is set and storage directory "
                f"'{target.parent}' could not be created; refusing ephemeral "
                ":memory: fallback."
            ) from exc
        warnings.warn(
            f"SQLite storage directory '{target.parent}' could not be created "
            f"({exc}); falling back to ephemeral :memory: — runtime evidence "
            "will NOT persist. Set KEELWAY_DB_FAIL_CLOSED=1 to refuse instead.",
            RuntimeWarning,
            stacklevel=2,
        )
        return ":memory:", ":memory:"


def _load_or_create_master_key(master_key: Optional[Union[str, bytes]], key_file_path: Optional[Union[str, Path]], db_path: Union[str, Path]) -> bytes:
    if master_key is not None:
        raw_bytes = master_key.encode("utf-8") if isinstance(master_key, str) else bytes(master_key)
        if not raw_bytes.strip():
            raise ValueError("Vault master_key must be non-empty.")
        return raw_bytes
    if os.environ.get("KEELWAY_VAULT_MASTER_KEY", "").strip():
        return os.environ["KEELWAY_VAULT_MASTER_KEY"].strip().encode("utf-8")
    kf = Path(key_file_path).expanduser().resolve() if key_file_path is not None else (db_path.parent / "vault_master.key" if isinstance(db_path, Path) else Path.home() / ".keelway" / "vault_master.key")
    try:
        kf.parent.mkdir(parents=True, exist_ok=True)
        if kf.exists() and kf.read_bytes().strip():
            os.chmod(kf, 0o600)
            return kf.read_bytes().strip()
        generated = secrets.token_hex(32).encode("utf-8")
        fd = os.open(str(kf), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            os.write(fd, generated)
        finally:
            os.close(fd)
        os.chmod(kf, 0o600)
        return generated
    except OSError:
        return secrets.token_bytes(32)


def _derive_aes256_key(master_material: bytes) -> bytes:
    if _HAS_CRYPTOGRAPHY:
        return HKDF(algorithm=hashes.SHA256(), length=32, salt=_HKDF_SALT, info=_HKDF_INFO).derive(master_material)
    return hmac.new(hmac.new(_HKDF_SALT, master_material, hashlib.sha256).digest(), _HKDF_INFO + b"\x01", hashlib.sha256).digest()[:32]


class LocalSecretVault:
    """Thread-safe `AES-256-GCM` secret vault backed by SQLite WAL."""

    def __init__(self, db_path: Optional[Union[str, Path]] = None, master_key: Optional[Union[str, bytes]] = None, key_file_path: Optional[Union[str, Path]] = None) -> None:
        self._lock = threading.RLock()
        self._db_path, connect_target = _resolve_sqlite_target(db_path)
        derived = _derive_aes256_key(_load_or_create_master_key(master_key, key_file_path, self._db_path))
        self._aesgcm: Any = AESGCM(derived) if _HAS_CRYPTOGRAPHY else _StdlibAESGCM(derived)
        self._conn = sqlite3.connect(connect_target, check_same_thread=False, timeout=30.0)
        self._conn.row_factory = sqlite3.Row
        self._closed = False
        with self._lock:
            mode_row = self._conn.execute("PRAGMA journal_mode=WAL").fetchone()
            self._journal_mode = str(mode_row[0]).lower() if mode_row else "unknown"
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            with self._conn:
                self._conn.executescript(
                    "CREATE TABLE IF NOT EXISTS platform_secrets (workspace_id TEXT NOT NULL, name TEXT NOT NULL, "
                    "namespace TEXT NOT NULL, nonce BLOB NOT NULL, ciphertext BLOB NOT NULL, masked_preview TEXT NOT NULL, "
                    "fingerprint_sha256 TEXT NOT NULL, version INTEGER NOT NULL, updated_at TEXT NOT NULL, "
                    "PRIMARY KEY(workspace_id, name)); CREATE INDEX IF NOT EXISTS idx_platform_secrets_ws ON platform_secrets(workspace_id);"
                )

    @property
    def db_path(self) -> Union[str, Path]:
        return self._db_path

    @property
    def journal_mode(self) -> str:
        return self._journal_mode

    def close(self) -> None:
        with self._lock:
            if not self._closed:
                self._conn.close()
                self._closed = True

    @staticmethod
    def _validate(workspace_id: str, name: str, namespace: Optional[str] = None, secret_value: Optional[str] = None) -> Tuple[str, str, str]:
        ws, clean_name = str(workspace_id or "").strip(), str(name or "").strip()
        if not ws:
            raise ValueError("Secret 'workspace_id' must be non-empty.")
        if not clean_name or len(clean_name) > 128:
            raise ValueError("Secret 'name' must be between 1 and 128 characters.")
        clean_ns = str(namespace or "byom").strip().lower()
        if namespace is not None and clean_ns not in VALID_SECRET_NAMESPACES:
            raise ValueError(f"Unsupported secret namespace '{clean_ns}'. Expected {sorted(VALID_SECRET_NAMESPACES)}.")
        if secret_value is not None and (not isinstance(secret_value, str) or not secret_value.strip()):
            raise ValueError("Secret 'secret_value' must be a non-empty string.")
        return ws, clean_name, clean_ns

    @staticmethod
    def _aad(ws: str, name: str, ns: str, ver: int) -> bytes:
        return f"{ws}:{name}:{ns}:v{ver}".encode("utf-8")

    @staticmethod
    def _meta(ws: str, name: str, ns: str, masked: str, fp: str, ver: int, ts: str) -> Dict[str, Any]:
        return {
            "workspace_id": ws, "name": name, "namespace": ns, "masked_preview": masked,
            "fingerprint_sha256": fp, "version": ver, "encryption": "AES-256-GCM", "updated_at": ts,
        }

    def put_secret(self, workspace_id: str, name: str, secret_value: str, namespace: str = "byom") -> Dict[str, Any]:
        ws, clean_name, clean_ns = self._validate(workspace_id, name, namespace, secret_value)
        with self._lock, self._conn:
            existing = self._conn.execute(
                "SELECT version FROM platform_secrets WHERE workspace_id = ? AND name = ?", (ws, clean_name)
            ).fetchone()
            ver, nonce, now = (int(existing["version"]) + 1 if existing is not None else 1), os.urandom(12), _utc_now()
            ct = self._aesgcm.encrypt(nonce, secret_value.encode("utf-8"), self._aad(ws, clean_name, clean_ns, ver))
            masked, fp = mask_secret(secret_value), hashlib.sha256(secret_value.encode("utf-8")).hexdigest()
            self._conn.execute(
                "INSERT INTO platform_secrets VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(workspace_id, name) DO UPDATE SET namespace=excluded.namespace, nonce=excluded.nonce, "
                "ciphertext=excluded.ciphertext, masked_preview=excluded.masked_preview, "
                "fingerprint_sha256=excluded.fingerprint_sha256, version=excluded.version, updated_at=excluded.updated_at",
                (ws, clean_name, clean_ns, nonce, ct, masked, fp, ver, now),
            )
            return self._meta(ws, clean_name, clean_ns, masked, fp, ver, now)

    def rotate_secret(self, workspace_id: str, name: str, secret_value: str, namespace: Optional[str] = None) -> Dict[str, Any]:
        ws, clean_name, _ = self._validate(workspace_id, name, namespace, secret_value)
        with self._lock, self._conn:
            existing = self._conn.execute(
                "SELECT namespace, version FROM platform_secrets WHERE workspace_id = ? AND name = ?", (ws, clean_name)
            ).fetchone()
            if existing is None:
                raise KeyError(f"Secret '{clean_name}' not found in workspace '{ws}'.")
            target_ns = self._validate(ws, clean_name, namespace)[2] if namespace is not None else str(existing["namespace"])
            ver, nonce, now = int(existing["version"]) + 1, os.urandom(12), _utc_now()
            ct = self._aesgcm.encrypt(nonce, secret_value.encode("utf-8"), self._aad(ws, clean_name, target_ns, ver))
            masked, fp = mask_secret(secret_value), hashlib.sha256(secret_value.encode("utf-8")).hexdigest()
            self._conn.execute(
                "UPDATE platform_secrets SET namespace=?, nonce=?, ciphertext=?, masked_preview=?, "
                "fingerprint_sha256=?, version=?, updated_at=? WHERE workspace_id=? AND name=?",
                (target_ns, nonce, ct, masked, fp, ver, now, ws, clean_name),
            )
            return self._meta(ws, clean_name, target_ns, masked, fp, ver, now)

    def list_secrets(self, workspace_id: str = "default", namespace: Optional[str] = None) -> List[Dict[str, Any]]:
        ws, _, clean_ns = self._validate(workspace_id, "_list", namespace)
        with self._lock:
            sql = "SELECT workspace_id, name, namespace, masked_preview, fingerprint_sha256, version, updated_at FROM platform_secrets WHERE workspace_id = ?"
            params: Tuple[Any, ...] = (ws, clean_ns) if namespace is not None else (ws,)
            rows = self._conn.execute(sql + (" AND namespace = ?" if namespace is not None else "") + " ORDER BY name ASC", params).fetchall()
            return [self._meta(str(r[0]), str(r[1]), str(r[2]), str(r[3]), str(r[4]), int(r[5]), str(r[6])) for r in rows]

    def delete_secret(self, workspace_id: str, name: str) -> Dict[str, Any]:
        ws, clean_name, _ = self._validate(workspace_id, name)
        with self._lock, self._conn:
            if self._conn.execute("DELETE FROM platform_secrets WHERE workspace_id=? AND name=?", (ws, clean_name)).rowcount == 0:
                raise KeyError(f"Secret '{clean_name}' not found in workspace '{ws}'.")
            return {"deleted": True, "revoked": True, "workspace_id": ws, "name": clean_name}

    def resolve_secret_for_runtime(self, workspace_id: str, name: str) -> str:
        ws, clean_name, _ = self._validate(workspace_id, name)
        with self._lock:
            row = self._conn.execute(
                "SELECT workspace_id, name, namespace, nonce, ciphertext, version FROM platform_secrets WHERE workspace_id=? AND name=?",
                (ws, clean_name),
            ).fetchone()
            if row is None:
                raise KeyError(f"Secret '{clean_name}' not found in workspace '{ws}'.")
            aad = self._aad(str(row["workspace_id"]), str(row["name"]), str(row["namespace"]), int(row["version"]))
            try:
                return self._aesgcm.decrypt(bytes(row["nonce"]), bytes(row["ciphertext"]), aad).decode("utf-8")
            except (InvalidTag, ValueError, TypeError, UnicodeDecodeError) as exc:
                raise VaultTamperError(f"Vault integrity check failed (InvalidTag) for '{clean_name}'.") from exc


local_secret_vault = LocalSecretVault()
