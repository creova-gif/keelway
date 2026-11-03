"""Export the live audit log as a Keelway Record file (see record_format.py)."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import select

from core.security.record_format import dump_jsonl, verify_entries
from core.storage.database import AsyncSessionLocal
from core.storage.models import AuditEventRecord


async def load_entries() -> List[Dict[str, Any]]:
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(select(AuditEventRecord).order_by(AuditEventRecord.seq))).scalars().all()
    return [
        {
            "seq": row.seq, "timestamp": row.timestamp, "actor": row.actor, "role": row.role, "action": row.action,
            "resource": row.resource, "allowed": bool(row.allowed), "prev_hash": row.prev_hash, "entry_hash": row.entry_hash,
        }
        for row in rows
    ]


async def export_record(path: Optional[Path] = None) -> Dict[str, Any]:
    """Write the log to `path` (or return the text) and report whether the exported chain verifies."""
    entries = await load_entries()
    text = dump_jsonl(entries)
    result = verify_entries(entries)
    if path is not None:
        Path(path).write_text(text, encoding="utf-8")
    return {"text": text, "entries": len(entries), "valid": result["valid"], "head": result.get("head")}
