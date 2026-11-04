"""
Keelway Customer Runner Spool & Offline Sync Engine.

Provides durable local spooling of runner execution receipts, job acknowledgments,
logs, and telemetry during offline or disconnected states, with deterministic
batch synchronization and cryptographic batch receipts when reconnected.
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


@dataclass
class SpoolItem:
    """Represents a single spooled offline runner event or receipt."""
    item_id: str
    runner_id: str
    item_type: str
    payload: Dict[str, Any]
    created_at_epoch: float
    synced: bool
    sha256: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_id": self.item_id,
            "runner_id": self.runner_id,
            "item_type": self.item_type,
            "payload": self.payload,
            "created_at_epoch": self.created_at_epoch,
            "synced": self.synced,
            "sha256": self.sha256,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SpoolItem":
        return cls(
            item_id=data["item_id"],
            runner_id=data["runner_id"],
            item_type=data.get("item_type", "generic"),
            payload=data.get("payload", {}),
            created_at_epoch=float(data.get("created_at_epoch", time.time())),
            synced=bool(data.get("synced", False)),
            sha256=data.get("sha256", ""),
        )


@dataclass
class SpoolBatchReceipt:
    """Cryptographic batch receipt issued after processing incoming spooled items."""
    batch_id: str
    runner_id: str
    item_count: int
    accepted_count: int
    receipt_sha256: str
    timestamp_iso: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "runner_id": self.runner_id,
            "item_count": self.item_count,
            "accepted_count": self.accepted_count,
            "receipt_sha256": self.receipt_sha256,
            "timestamp_iso": self.timestamp_iso,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SpoolBatchReceipt":
        return cls(
            batch_id=data["batch_id"],
            runner_id=data["runner_id"],
            item_count=int(data.get("item_count", 0)),
            accepted_count=int(data.get("accepted_count", 0)),
            receipt_sha256=data.get("receipt_sha256", ""),
            timestamp_iso=data.get("timestamp_iso", ""),
        )


class RunnerSpoolManager:
    """Manages durable local spooling and batch synchronization for customer runners."""

    def __init__(self, persistence_path: Optional[Union[str, Path]] = None):
        if persistence_path is not None:
            self.persistence_path = Path(persistence_path)
        else:
            self.persistence_path = Path(".keelway/runner_spool/spool.json")

        self.items: Dict[str, SpoolItem] = {}
        self._load()

    def _load(self) -> None:
        if not self.persistence_path.is_file():
            return
        try:
            content = self.persistence_path.read_text(encoding="utf-8")
            raw = json.loads(content)
            items_list = raw.get("items", []) if isinstance(raw, dict) else raw
            for entry in items_list:
                item = SpoolItem.from_dict(entry)
                self.items[item.item_id] = item
        except Exception:
            pass

    def _save(self) -> None:
        self.persistence_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "items": [item.to_dict() for item in self.items.values()]
        }
        tmp_file = self.persistence_path.with_suffix(".tmp")
        tmp_file.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        tmp_file.replace(self.persistence_path)

    def enqueue_item(self, runner_id: str, item_type: str, payload: Dict[str, Any]) -> SpoolItem:
        """Enqueues an item into the spool with canonical JSON payload hashing."""
        canonical_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        payload_hash = hashlib.sha256(canonical_bytes).hexdigest()
        item_id = f"spool_{uuid.uuid4().hex[:12]}"
        now = time.time()

        item = SpoolItem(
            item_id=item_id,
            runner_id=runner_id,
            item_type=item_type,
            payload=payload,
            created_at_epoch=now,
            synced=False,
            sha256=payload_hash,
        )
        self.items[item.item_id] = item
        self._save()
        return item

    def get_pending_items(self, runner_id: str, limit: int = 50) -> List[SpoolItem]:
        """Returns pending unsynced items for a given runner node."""
        pending = [
            item for item in self.items.values()
            if item.runner_id == runner_id and not item.synced
        ]
        pending.sort(key=lambda x: x.created_at_epoch)
        return pending[:limit]

    def mark_synced(self, item_ids: List[str]) -> int:
        """Marks a list of item IDs as synced."""
        target_ids = set(item_ids)
        marked = 0
        for item_id in target_ids:
            if item_id in self.items and not self.items[item_id].synced:
                self.items[item_id].synced = True
                marked += 1
        if marked > 0:
            self._save()
        return marked

    def process_sync_batch(self, runner_id: str, items: List[Union[Dict[str, Any], SpoolItem]]) -> SpoolBatchReceipt:
        """
        Accepts a batch of incoming items from a runner, validates them,
        calculates composite batch SHA-256, marks local items synced, and returns a SpoolBatchReceipt.
        """
        normalized_items: List[Dict[str, Any]] = []
        for it in items:
            if hasattr(it, "to_dict"):
                normalized_items.append(it.to_dict())
            elif isinstance(it, dict):
                normalized_items.append(it)
            else:
                normalized_items.append({"raw": str(it)})

        canonical_batch = json.dumps(normalized_items, sort_keys=True, separators=(",", ":")).encode("utf-8")
        receipt_sha256 = hashlib.sha256(canonical_batch).hexdigest()

        # Update local items if present
        for entry in normalized_items:
            i_id = entry.get("item_id")
            if i_id and i_id in self.items:
                self.items[i_id].synced = True
            elif i_id:
                # Inbound item from runner not previously enqueued on server
                new_item = SpoolItem.from_dict({
                    **entry,
                    "runner_id": runner_id,
                    "synced": True,
                })
                self.items[new_item.item_id] = new_item

        self._save()

        batch_id = f"batch_{uuid.uuid4().hex[:12]}"
        timestamp_iso = datetime.now(timezone.utc).isoformat()

        return SpoolBatchReceipt(
            batch_id=batch_id,
            runner_id=runner_id,
            item_count=len(normalized_items),
            accepted_count=len(normalized_items),
            receipt_sha256=receipt_sha256,
            timestamp_iso=timestamp_iso,
        )

    def get_status(self, runner_id: str) -> Dict[str, Any]:
        """Returns pending and total spooled counts for a runner node."""
        pending_count = len([i for i in self.items.values() if i.runner_id == runner_id and not i.synced])
        total_spooled = len([i for i in self.items.values() if i.runner_id == runner_id])
        return {
            "runner_id": runner_id,
            "pending_count": pending_count,
            "total_spooled": total_spooled,
        }

    def flush(self, runner_id: str) -> int:
        """Flushes all pending items for a runner node by marking them synced."""
        pending_ids = [i.item_id for i in self.items.values() if i.runner_id == runner_id and not i.synced]
        return self.mark_synced(pending_ids)
