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


async def create_head_anchor(
    path: Optional[Path] = None,
    repo_root: Optional[Path] = None,
    key_bytes: Optional[bytes] = None,
) -> Dict[str, Any]:
    """Create a signed head anchor receipt and optionally write a Git note.

    Anchors the current head hash to prevent tail-truncation attacks.
    """
    import hashlib
    import hmac
    import json
    import subprocess
    from datetime import datetime, timezone

    entries = await load_entries()
    head = entries[-1]["entry_hash"] if entries else ("0" * 64)
    now_utc = datetime.now(timezone.utc).isoformat()

    key = key_bytes
    if key is None:
        key_file = Path(".keelway/agent_signing.key")
        if key_file.exists():
            key = key_file.read_text().strip().encode("utf-8")
        else:
            key = b"keelway_default_anchor_key"

    signature = hmac.new(key, f"{head}:{len(entries)}:{now_utc}".encode("utf-8"), hashlib.sha256).hexdigest()

    anchor_data = {
        "schema": "keelway.head_anchor/v1",
        "anchored_at": now_utc,
        "entries_count": len(entries),
        "head_hash": head,
        "signature": signature,
    }

    if repo_root is not None or Path(".git").exists():
        root = repo_root or Path(".")
        try:
            note_content = json.dumps(anchor_data, sort_keys=True)
            subprocess.run(
                ["git", "notes", "--ref=keelway/audit", "add", "-f", "-m", note_content, "HEAD"],
                cwd=str(root),
                capture_output=True,
                check=False,
            )
            anchor_data["git_note_anchored"] = True
        except Exception:
            anchor_data["git_note_anchored"] = False

    if path is not None:
        Path(path).write_text(json.dumps(anchor_data, indent=2), encoding="utf-8")

    return anchor_data

