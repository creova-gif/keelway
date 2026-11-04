"""
Keelway Sovereign Sync Package
Supports cross-machine encrypted task sync and external editor sync bridge.
"""
from core.sync.engine import (
    EncryptedSyncEnvelope,
    SovereignSyncEngine,
    SyncRecord,
    decrypt_payload,
    encrypt_payload,
    get_shared_sync_engine,
)
from core.sync.bridge import ExternalEditorSyncBridge, ConcurrentEditConflict

__all__ = [
    "EncryptedSyncEnvelope",
    "SovereignSyncEngine",
    "SyncRecord",
    "decrypt_payload",
    "encrypt_payload",
    "get_shared_sync_engine",
    "ExternalEditorSyncBridge",
    "ConcurrentEditConflict",
]
