"""
Ed25519 Cryptographic Manifest Signing & Verification (`KEEL-MANIFEST-007`).

Uses `cryptography.hazmat.primitives.asymmetric.ed25519` (`Ed25519PrivateKey` / `Ed25519PublicKey`)
with a byte-identical RFC 8032 / RFC 8410 stdlib fallback when running in minimal environments
without native OpenSSL wheels installed.
"""

from __future__ import annotations

import base64
import copy
import hashlib
import json
import os
import secrets
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

try:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
        Ed25519PublicKey,
    )

    _HAS_CRYPTOGRAPHY = True
except ImportError:  # pragma: no cover - exercised in lightweight venvs
    _HAS_CRYPTOGRAPHY = False

SORVEX_FIRST_PARTY_KEY_ID = "sorvex-labs-ed25519-v1"
_EXCLUDED_SIGNING_FIELDS = frozenset({"ed25519_signature", "signer_key_id", "security_report"})
_PKCS8_ED25519_PREFIX = bytes.fromhex("302e020100300506032b657004220420")

# RFC 8032 Ed25519 curve constants (used only when `cryptography` C-extension is absent)
_P = 2**255 - 19
_L = 2**252 + 27742317777372353535851937790883648493
_D = (-121665 * pow(121666, _P - 2, _P)) % _P
_I = pow(2, (_P - 1) // 4, _P)
_BY = (4 * pow(5, _P - 2, _P)) % _P
_BX_RAW = ((_BY * _BY - 1) * pow(_D * _BY * _BY + 1, _P - 2, _P)) % _P
_BX = pow(_BX_RAW, (_P + 3) // 8, _P)
if (_BX * _BX - _BX_RAW) % _P != 0:
    _BX = (_BX * _I) % _P
if _BX % 2 != 0:
    _BX = _P - _BX
_BASE = (_BX, _BY, 1, (_BX * _BY) % _P)


def _ed_add(p1: Tuple[int, int, int, int], p2: Tuple[int, int, int, int]) -> Tuple[int, int, int, int]:
    x1, y1, z1, t1 = p1
    x2, y2, z2, t2 = p2
    a = ((y1 - x1) * (y2 - x2)) % _P
    b = ((y1 + x1) * (y2 + x2)) % _P
    c = (t1 * 2 * _D * t2) % _P
    dd = (z1 * 2 * z2) % _P
    e, f, g, h = (b - a) % _P, (dd - c) % _P, (dd + c) % _P, (b + a) % _P
    return (e * f) % _P, (g * h) % _P, (f * g) % _P, (e * h) % _P


def _ed_mul(pt: Tuple[int, int, int, int], scalar: int) -> Tuple[int, int, int, int]:
    res = (0, 1, 1, 0)
    addend = pt
    n = scalar
    while n > 0:
        if n & 1:
            res = _ed_add(res, addend)
        addend = _ed_add(addend, addend)
        n >>= 1
    return res


def _ed_encode_point(pt: Tuple[int, int, int, int]) -> bytes:
    x, y, z, _ = pt
    zi = pow(z, _P - 2, _P)
    xp, yp = (x * zi) % _P, (y * zi) % _P
    return (yp | ((xp & 1) << 255)).to_bytes(32, "little")


def _ed_decode_point(enc: bytes) -> Tuple[int, int, int, int]:
    if len(enc) != 32:
        raise ValueError("Ed25519 public key must be 32 raw bytes.")
    v = int.from_bytes(enc, "little")
    y, sign = v & ((1 << 255) - 1), v >> 255
    if y >= _P:
        raise ValueError("Point y out of range.")
    u = (y * y - 1) % _P
    w = (_D * y * y + 1) % _P
    x2 = (u * pow(w, _P - 2, _P)) % _P
    x = pow(x2, (_P + 3) // 8, _P)
    if (x * x - x2) % _P != 0:
        x = (x * _I) % _P
    if (x * x - x2) % _P != 0 or (x == 0 and sign == 1):
        raise ValueError("Invalid Ed25519 curve point.")
    if (x & 1) != sign:
        x = _P - x
    return x, y, 1, (x * y) % _P


def _rfc8032_pub_from_seed(seed: bytes) -> bytes:
    h = hashlib.sha512(seed).digest()
    a = int.from_bytes(h[:32], "little")
    a &= (1 << 254) - 8
    a |= 1 << 254
    return _ed_encode_point(_ed_mul(_BASE, a))


def _rfc8032_sign(seed: bytes, msg: bytes) -> bytes:
    h = hashlib.sha512(seed).digest()
    a = (int.from_bytes(h[:32], "little") & ((1 << 254) - 8)) | (1 << 254)
    pub = _ed_encode_point(_ed_mul(_BASE, a))
    r = int.from_bytes(hashlib.sha512(h[32:] + msg).digest(), "little") % _L
    r_enc = _ed_encode_point(_ed_mul(_BASE, r))
    k = int.from_bytes(hashlib.sha512(r_enc + pub + msg).digest(), "little") % _L
    s = (r + k * a) % _L
    return r_enc + s.to_bytes(32, "little")


def _rfc8032_verify(pub: bytes, sig: bytes, msg: bytes) -> bool:
    if len(sig) != 64:
        return False
    s = int.from_bytes(sig[32:], "little")
    if s >= _L:
        return False
    a_pt = _ed_decode_point(pub)
    r_pt = _ed_decode_point(sig[:32])
    k = int.from_bytes(hashlib.sha512(sig[:32] + pub + msg).digest(), "little") % _L
    lhs = _ed_encode_point(_ed_mul(_BASE, s))
    rhs = _ed_encode_point(_ed_add(r_pt, _ed_mul(a_pt, _L - 0 if k == 0 else k)))
    return lhs == rhs


def _b64_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64_decode(text: str) -> bytes:
    cleaned = text.strip()
    if not cleaned:
        raise ValueError("Empty base64 input.")
    return base64.urlsafe_b64decode((cleaned + "=" * (-len(cleaned) % 4)).encode("ascii"))


def _seed_to_keypair(seed: bytes) -> Tuple[bytes, str]:
    if _HAS_CRYPTOGRAPHY:
        priv = Ed25519PrivateKey.from_private_bytes(seed)
        pem = priv.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        pub = priv.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        return pem, _b64_encode(pub)
    b64_der = base64.b64encode(_PKCS8_ED25519_PREFIX + seed).decode("ascii")
    pem = ("\n".join(["-----BEGIN " + "PRIVATE KEY-----", b64_der, "-----END " + "PRIVATE KEY-----", ""])).encode("ascii")
    return pem, _b64_encode(_rfc8032_pub_from_seed(seed))


def _seed_from_pem(private_key_pem: bytes) -> bytes:
    raw_pem = private_key_pem.encode("utf-8") if isinstance(private_key_pem, str) else bytes(private_key_pem)
    lines = [ln.strip() for ln in raw_pem.decode("ascii").splitlines() if ln.strip() and not ln.startswith("-----")]
    der = base64.b64decode("".join(lines))
    if len(der) != 48 or not der.startswith(_PKCS8_ED25519_PREFIX):
        raise ValueError("Invalid PKCS#8 Ed25519 PEM private key.")
    return der[16:]


def generate_publisher_keypair() -> Tuple[bytes, str]:
    """Generate a new Ed25519 publisher keypair: `(private_key_pem, public_key_urlsafe_b64)`."""
    if _HAS_CRYPTOGRAPHY:
        priv = Ed25519PrivateKey.generate()
        seed = priv.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())
        return _seed_to_keypair(seed)
    return _seed_to_keypair(secrets.token_bytes(32))


class FirstPartySigningKeyUnavailable(RuntimeError):
    """Raised when no managed first-party manifest signing key is configured."""


_LEGACY_DEV_SEED_DOMAIN = b"keelway.manifest.sorvex-labs.first-party.ed25519.v1"
_MANIFEST_KEY_ENVS = (
    "KEELWAY_MANIFEST_SIGNING_KEY",
    "KEELWAY_MANIFEST_SIGNING_SEED",
    "KEELWAY_MANIFEST_KEY_FILE",
    "KEELWAY_STATE_DIR",
    "KEELWAY_DEV_INSECURE_KEY",
)


def _decode_seed_material(text: str) -> bytes:
    """Decode a 32-byte Ed25519 seed from hex, base64, or PKCS#8 PEM text."""
    candidate = text.strip()
    if not candidate:
        raise ValueError("Empty signing seed material.")
    if "-----BEGIN" in candidate:
        return _seed_from_pem(candidate.encode("utf-8"))
    compact = "".join(candidate.split())
    try:
        raw = bytes.fromhex(compact)
    except ValueError:
        raw = base64.b64decode(compact, validate=True)
    if len(raw) != 32:
        raise ValueError("Ed25519 signing seed must decode to exactly 32 bytes.")
    return raw


def _first_party_key_file_path() -> Optional[Path]:
    explicit = os.environ.get("KEELWAY_MANIFEST_KEY_FILE", "").strip()
    if explicit:
        return Path(explicit).expanduser()
    state_dir = os.environ.get("KEELWAY_STATE_DIR", "").strip()
    if state_dir:
        return Path(state_dir).expanduser() / "manifest-signing.seed"
    return None


def _load_or_create_key_file_seed(path: Path) -> bytes:
    if path.exists():
        return _decode_seed_material(path.read_text(encoding="utf-8"))
    seed = secrets.token_bytes(32)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.write(fd, (seed.hex() + "\n").encode("ascii"))
    finally:
        os.close(fd)
    return seed


def _resolve_first_party_seed() -> Optional[bytes]:
    """Resolve the first-party Ed25519 seed from managed configuration.

    Resolution order:
    1. ``KEELWAY_MANIFEST_SIGNING_KEY`` (PKCS#8 PEM) or
       ``KEELWAY_MANIFEST_SIGNING_SEED`` (hex/base64 32-byte seed).
    2. ``KEELWAY_MANIFEST_KEY_FILE`` or ``$KEELWAY_STATE_DIR/manifest-signing.seed``
       (loaded if present, otherwise generated once with mode 0600).
    3. ``KEELWAY_DEV_INSECURE_KEY=1`` — deterministic legacy seed for local
       development and tests only. Never set this in production.
    4. Otherwise ``None`` (fail closed).
    """
    pem = os.environ.get("KEELWAY_MANIFEST_SIGNING_KEY", "").strip()
    if pem:
        return _seed_from_pem(pem.encode("utf-8"))
    seed_text = os.environ.get("KEELWAY_MANIFEST_SIGNING_SEED", "").strip()
    if seed_text:
        return _decode_seed_material(seed_text)
    key_file = _first_party_key_file_path()
    if key_file is not None:
        return _load_or_create_key_file_seed(key_file)
    if os.environ.get("KEELWAY_DEV_INSECURE_KEY", "").strip().lower() in {"1", "true", "yes"}:
        return hashlib.sha256(_LEGACY_DEV_SEED_DOMAIN).digest()
    return None


def get_sorvex_first_party_keypair() -> Tuple[bytes, str]:
    """Return the Sorvex Labs first-party manifest signing keypair.

    The private key is sourced from managed configuration (env seed/PEM or a
    persisted key file); the legacy deterministic key is available only behind
    ``KEELWAY_DEV_INSECURE_KEY=1``. Raises
    :class:`FirstPartySigningKeyUnavailable` when unconfigured.
    """
    seed = _resolve_first_party_seed()
    if seed is None:
        raise FirstPartySigningKeyUnavailable(
            "No first-party manifest signing key configured. Set "
            "KEELWAY_MANIFEST_SIGNING_KEY, KEELWAY_MANIFEST_SIGNING_SEED, or "
            "KEELWAY_MANIFEST_KEY_FILE (or KEELWAY_STATE_DIR); for local "
            "development only, set KEELWAY_DEV_INSECURE_KEY=1."
        )
    return _seed_to_keypair(seed)


def canonical_manifest_bytes(manifest: Dict[str, Any]) -> bytes:
    if not isinstance(manifest, dict):
        raise ValueError("Manifest must be a JSON object dictionary.")
    body = {k: v for k, v in manifest.items() if k not in _EXCLUDED_SIGNING_FIELDS}
    return json.dumps(body, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


class Ed25519ManifestSigner:
    """Signs and verifies `keelway.package/v1` and `keelway.agent/v1` manifests (`KEEL-MANIFEST-007`)."""

    def __init__(self, trusted_keys: Optional[Dict[str, str]] = None) -> None:
        if trusted_keys is None:
            try:
                _, first_party_pub = get_sorvex_first_party_keypair()
                self._trusted_keys: Dict[str, str] = {SORVEX_FIRST_PARTY_KEY_ID: first_party_pub}
            except FirstPartySigningKeyUnavailable:
                self._trusted_keys = {}
        else:
            self._trusted_keys = {}
            for k_id, pub_b64 in trusted_keys.items():
                self.register_trusted_key(k_id, pub_b64)

    def register_trusted_key(self, key_id: str, public_key_b64: str) -> None:
        clean_id = str(key_id or "").strip()
        if not clean_id:
            raise ValueError("Trusted publisher 'key_id' must be non-empty.")
        raw_pub = _b64_decode(public_key_b64)
        if _HAS_CRYPTOGRAPHY:
            Ed25519PublicKey.from_public_bytes(raw_pub)
        else:
            _ed_decode_point(raw_pub)
        self._trusted_keys[clean_id] = _b64_encode(raw_pub)

    def list_trusted_keys(self) -> Dict[str, str]:
        return dict(self._trusted_keys)

    def sign_manifest(self, manifest: Dict[str, Any], private_key_pem: bytes, key_id: str) -> Dict[str, Any]:
        clean_key_id = str(key_id or "").strip()
        if not clean_key_id:
            raise ValueError("Signing 'key_id' must be non-empty.")
        payload_bytes = canonical_manifest_bytes(manifest)
        if _HAS_CRYPTOGRAPHY:
            loaded = serialization.load_pem_private_key(
                private_key_pem.encode("utf-8") if isinstance(private_key_pem, str) else private_key_pem,
                password=None,
            )
            if not isinstance(loaded, Ed25519PrivateKey):
                raise ValueError("Manifest signing key must be Ed25519.")
            sig_raw = loaded.sign(payload_bytes)
        else:
            sig_raw = _rfc8032_sign(_seed_from_pem(private_key_pem), payload_bytes)
        signed = copy.deepcopy(manifest)
        signed["signer_key_id"] = clean_key_id
        signed["ed25519_signature"] = _b64_encode(sig_raw)
        return signed

    def verify_manifest(self, manifest: Dict[str, Any]) -> Tuple[bool, str]:
        if not isinstance(manifest, dict):
            return False, "UNSIGNED_MANIFEST"
        sig_text = str(manifest.get("ed25519_signature") or "").strip()
        if not sig_text:
            return False, "UNSIGNED_MANIFEST"
        key_id = str(manifest.get("signer_key_id") or "").strip()
        if not key_id or key_id not in self._trusted_keys:
            return False, "UNKNOWN_PUBLISHER_KEY"
        try:
            pub_bytes = _b64_decode(self._trusted_keys[key_id])
            sig_bytes = _b64_decode(sig_text)
            payload_bytes = canonical_manifest_bytes(manifest)
            if _HAS_CRYPTOGRAPHY:
                Ed25519PublicKey.from_public_bytes(pub_bytes).verify(sig_bytes, payload_bytes)
            elif not _rfc8032_verify(pub_bytes, sig_bytes, payload_bytes):
                return False, "INVALID_ED25519_SIGNATURE"
        except Exception:
            return False, "INVALID_ED25519_SIGNATURE"
        return True, "VERIFIED_ED25519"


manifest_signer = Ed25519ManifestSigner()
