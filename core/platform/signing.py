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
from typing import Any, Dict, Optional, Tuple

from core.platform.manifest_keys import TRUSTED_FIRST_PARTY_MANIFEST_KEYS

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
FIRST_PARTY_SIGNING_KEY_ENV = "KEELWAY_FIRST_PARTY_MANIFEST_SIGNING_KEY"
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


def load_first_party_signing_key() -> Optional[Tuple[bytes, str]]:
    """Sorvex Labs first-party signing key from `FIRST_PARTY_SIGNING_KEY_ENV`, or None when unset."""
    pem_text = os.environ.get(FIRST_PARTY_SIGNING_KEY_ENV, "").strip()
    if not pem_text:
        return None
    return _seed_to_keypair(_seed_from_pem(pem_text.replace("\\n", "\n").encode("ascii")))


def default_trusted_manifest_keys() -> Dict[str, str]:
    """First-party public keys from `manifest_keys.py`, plus the configured signing key's public half."""
    keys = dict(TRUSTED_FIRST_PARTY_MANIFEST_KEYS)
    loaded = load_first_party_signing_key()
    if loaded is not None:
        keys[SORVEX_FIRST_PARTY_KEY_ID] = loaded[1]
    return keys


def canonical_manifest_bytes(manifest: Dict[str, Any]) -> bytes:
    if not isinstance(manifest, dict):
        raise ValueError("Manifest must be a JSON object dictionary.")
    body = {k: v for k, v in manifest.items() if k not in _EXCLUDED_SIGNING_FIELDS}
    return json.dumps(body, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


class Ed25519ManifestSigner:
    """Signs and verifies `keelway.package/v1` and `keelway.agent/v1` manifests (`KEEL-MANIFEST-007`)."""

    def __init__(self, trusted_keys: Optional[Dict[str, str]] = None) -> None:
        self._trusted_keys: Dict[str, str] = {}
        for k_id, pub_b64 in (default_trusted_manifest_keys() if trusted_keys is None else trusted_keys).items():
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
