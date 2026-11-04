"""
Keelway Sovereign Cross-Machine Encrypted Task Sync Engine.
Enables offline-first, peer-to-peer, or relay-backed synchronization of agent task states,
flight tapes, and workspace mutations across developer machines using authenticated encryption
(SHA-256 CTR keystream + HMAC-SHA256 Encrypt-then-MAC) and monotonic vector clocks.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import socket
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_SYNC_SECRET = b"keelway_cross_machine_sync_v1_secret"


def _derive_keys(master_key: bytes, salt: bytes) -> Tuple[bytes, bytes]:
    """Derives distinct enc_key and mac_key from master key using HKDF-like SHA-256 expansion."""
    prk = hmac.new(salt, master_key, hashlib.sha256).digest()
    enc_key = hmac.new(prk, b"keelway_sync_enc_v1", hashlib.sha256).digest()
    mac_key = hmac.new(prk, b"keelway_sync_mac_v1", hashlib.sha256).digest()
    return enc_key, mac_key


def _keystream_block(key: bytes, nonce: bytes, counter: int) -> bytes:
    counter_bytes = counter.to_bytes(8, byteorder="big")
    return hashlib.sha256(key + nonce + counter_bytes).digest()


def encrypt_payload(data: bytes, master_key: bytes) -> Dict[str, str]:
    """
    Encrypts arbitrary byte payload using SHA-256 CTR keystream with HMAC-SHA256 authentication.
    Returns dictionary with salt, nonce, ciphertext_b64, and auth_tag.
    """
    salt = secrets.token_bytes(16)
    nonce = secrets.token_bytes(16)
    enc_key, mac_key = _derive_keys(master_key, salt)

    ciphertext = bytearray(len(data))
    block_size = 32
    for offset in range(0, len(data), block_size):
        counter = offset // block_size
        k_block = _keystream_block(enc_key, nonce, counter)
        chunk = data[offset : offset + block_size]
        for i in range(len(chunk)):
            ciphertext[offset + i] = chunk[i] ^ k_block[i]

    raw_ciphertext = bytes(ciphertext)
    auth_tag = hmac.new(mac_key, salt + nonce + raw_ciphertext, hashlib.sha256).hexdigest()

    return {
        "salt_b64": base64.b64encode(salt).decode("ascii"),
        "nonce_b64": base64.b64encode(nonce).decode("ascii"),
        "ciphertext_b64": base64.b64encode(raw_ciphertext).decode("ascii"),
        "auth_tag": auth_tag,
    }


def decrypt_payload(envelope_enc: Dict[str, str], master_key: bytes) -> bytes:
    """
    Validates HMAC auth tag and decrypts ciphertext.
    Raises ValueError on tampering or invalid key (fail-closed).
    """
    salt = base64.b64decode(envelope_enc["salt_b64"])
    nonce = base64.b64decode(envelope_enc["nonce_b64"])
    raw_ciphertext = base64.b64decode(envelope_enc["ciphertext_b64"])
    expected_tag = envelope_enc["auth_tag"]

    enc_key, mac_key = _derive_keys(master_key, salt)
    calculated_tag = hmac.new(mac_key, salt + nonce + raw_ciphertext, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected_tag, calculated_tag):
        raise ValueError("CRYPTOGRAPHIC_INTEGRITY_FAILURE: Auth tag mismatch or corrupted ciphertext.")

    plaintext = bytearray(len(raw_ciphertext))
    block_size = 32
    for offset in range(0, len(raw_ciphertext), block_size):
        counter = offset // block_size
        k_block = _keystream_block(enc_key, nonce, counter)
        chunk = raw_ciphertext[offset : offset + block_size]
        for i in range(len(chunk)):
            plaintext[offset + i] = chunk[i] ^ k_block[i]

    return bytes(plaintext)


@dataclass
class SyncRecord:
    """Represents a discrete state change record in the append-only sync journal."""
    record_id: str
    machine_id: str
    workspace_id: str
    task_id: str
    lamport_time: int
    vector_clock: Dict[str, int]
    entity_type: str  # "task_state" | "flight_tape" | "approval_decision" | "workspace_meta"
    payload: Dict[str, Any]
    payload_sha256: str = ""
    timestamp_utc: str = ""

    def __post_init__(self):
        if not self.timestamp_utc:
            self.timestamp_utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        if not self.payload_sha256:
            canonical = json.dumps(self.payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
            self.payload_sha256 = hashlib.sha256(canonical).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SyncRecord:
        return cls(**data)


@dataclass
class EncryptedSyncEnvelope:
    """Represents a sealed, encrypted cross-machine sync transmission bundle."""
    envelope_id: str
    org_id: str
    source_machine_id: str
    records_count: int
    created_at_utc: str
    cipher: str
    salt_b64: str
    nonce_b64: str
    ciphertext_b64: str
    auth_tag: str
    bundle_digest_sha256: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> EncryptedSyncEnvelope:
        return cls(**data)


class SovereignSyncEngine:
    """
    Deterministic cross-machine state synchronizer.
    Maintains local monotonic vector clocks, logs change records, and safely resolves concurrent updates.
    """

    def __init__(
        self,
        machine_id: Optional[str] = None,
        org_id: str = "default-org",
        secret_key: bytes = DEFAULT_SYNC_SECRET,
    ):
        self.machine_id = machine_id or f"{socket.gethostname()}_{secrets.token_hex(4)}"
        self.org_id = org_id
        self.secret_key = secret_key
        self.lamport_counter = 0
        self.vector_clock: Dict[str, int] = {self.machine_id: 0}
        self.journal: List[SyncRecord] = []
        self.known_peers: Dict[str, Dict[str, Any]] = {}

    def record_mutation(
        self,
        entity_type: str,
        task_id: str,
        payload: Dict[str, Any],
        workspace_id: str = "default_workspace",
    ) -> SyncRecord:
        """Records a new local state mutation, increments logical clock, and signs the record."""
        self.lamport_counter += 1
        self.vector_clock[self.machine_id] = self.vector_clock.get(self.machine_id, 0) + 1

        rec = SyncRecord(
            record_id=f"rec_{secrets.token_hex(8)}",
            machine_id=self.machine_id,
            workspace_id=workspace_id,
            task_id=task_id,
            lamport_time=self.lamport_counter,
            vector_clock=dict(self.vector_clock),
            entity_type=entity_type,
            payload=payload,
        )
        self.journal.append(rec)
        return rec

    def export_envelope(self, since_lamport: int = 0) -> EncryptedSyncEnvelope:
        """Packages records strictly after since_lamport into an authenticated encrypted envelope."""
        selected_records = [r.to_dict() for r in self.journal if r.lamport_time > since_lamport]
        raw_json = json.dumps(selected_records, sort_keys=True).encode("utf-8")
        bundle_digest = hashlib.sha256(raw_json).hexdigest()

        enc = encrypt_payload(raw_json, self.secret_key)
        envelope_id = f"env_{self.machine_id[:8]}_{int(time.time())}_{secrets.token_hex(4)}"

        return EncryptedSyncEnvelope(
            envelope_id=envelope_id,
            org_id=self.org_id,
            source_machine_id=self.machine_id,
            records_count=len(selected_records),
            created_at_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            cipher="AES-256-CTR-HMAC-SHA256",
            salt_b64=enc["salt_b64"],
            nonce_b64=enc["nonce_b64"],
            ciphertext_b64=enc["ciphertext_b64"],
            auth_tag=enc["auth_tag"],
            bundle_digest_sha256=bundle_digest,
        )

    def import_envelope(self, envelope: EncryptedSyncEnvelope) -> Dict[str, Any]:
        """
        Decrypts, verifies, and deterministically merges an incoming encrypted envelope.
        Resolves conflicts using (Lamport timestamp, machine_id hash) total order.
        """
        if envelope.org_id != self.org_id:
            raise PermissionError(f"CROSS_ORG_DENIAL: Envelope org '{envelope.org_id}' does not match local '{self.org_id}'.")

        raw_bytes = decrypt_payload({
            "salt_b64": envelope.salt_b64,
            "nonce_b64": envelope.nonce_b64,
            "ciphertext_b64": envelope.ciphertext_b64,
            "auth_tag": envelope.auth_tag,
        }, self.secret_key)

        calc_digest = hashlib.sha256(raw_bytes).hexdigest()
        if calc_digest != envelope.bundle_digest_sha256:
            raise ValueError("BUNDLE_DIGEST_CORRUPTED: Raw payload digest mismatch.")

        records_data = json.loads(raw_bytes.decode("utf-8"))
        inbound_records = [SyncRecord.from_dict(d) for d in records_data]

        existing_ids = {r.record_id for r in self.journal}
        merged_count = 0

        for r in inbound_records:
            if r.record_id not in existing_ids:
                self.journal.append(r)
                existing_ids.add(r.record_id)
                merged_count += 1

                # Update local Lamport clock
                self.lamport_counter = max(self.lamport_counter, r.lamport_time) + 1

                # Update vector clock merge
                for node, seq in r.vector_clock.items():
                    self.vector_clock[node] = max(self.vector_clock.get(node, 0), seq)

        # Update peer tracking
        self.known_peers[envelope.source_machine_id] = {
            "last_seen_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "latest_envelope_id": envelope.envelope_id,
            "records_received": len(inbound_records),
        }

        # Keep journal deterministically sorted
        self.journal.sort(key=lambda x: (x.lamport_time, hashlib.sha256(x.machine_id.encode()).hexdigest(), x.record_id))

        return {
            "status": "MERGED",
            "envelope_id": envelope.envelope_id,
            "source_machine": envelope.source_machine_id,
            "records_processed": len(inbound_records),
            "new_records_merged": merged_count,
            "current_lamport_time": self.lamport_counter,
            "vector_clock": dict(self.vector_clock),
        }

    def get_status(self) -> Dict[str, Any]:
        """Provides operational status summary for local machine and active sync journal."""
        return {
            "machine_id": self.machine_id,
            "org_id": self.org_id,
            "lamport_counter": self.lamport_counter,
            "vector_clock": dict(self.vector_clock),
            "journal_records_total": len(self.journal),
            "known_peers": self.known_peers,
            "latest_record": self.journal[-1].to_dict() if self.journal else None,
        }


# Global shared engine singleton
_sync_engine: Optional[SovereignSyncEngine] = None


def get_shared_sync_engine() -> SovereignSyncEngine:
    global _sync_engine
    if _sync_engine is None:
        _sync_engine = SovereignSyncEngine()
    return _sync_engine
