"""
Kora Dev Studio API: live workspace status, working-tree diff, and air-gap control.
"""

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.api import routes
from core.api.routes import FLIGHT_RECORDINGS_DIR, ws_manager
from core.config import settings
from core.models.gateway import gateway
from core.security.auth import current_principal, require
from core.security.rbac import Permission
from core.storage.database import check_db_health, get_db
from core.storage.models import TaskRecord

router = APIRouter(prefix="/v1/studio", tags=["Studio"], dependencies=[Depends(current_principal)])

MAX_DIFF_BYTES = 512 * 1024
STUDIO_VERSION = "0.1.0"


async def _git(*args: str, limit: int = MAX_DIFF_BYTES) -> Tuple[int, str]:
    """Run git in the open workspace, reading at most `limit + 1` bytes of stdout so huge outputs are never buffered."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "git", *args,
            cwd=str(routes._workspace_fs.root),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
    except FileNotFoundError:
        return 127, ""
    out = b""
    while len(out) <= limit:
        chunk = await proc.stdout.read(65536)
        if not chunk:
            break
        out += chunk
    if len(out) > limit and proc.returncode is None:
        proc.kill()
        await proc.wait()
        return 0, out.decode(errors="replace")
    await proc.wait()
    return proc.returncode, out.decode(errors="replace")


def parse_unified_diff(text: str) -> List[Dict[str, Any]]:
    """Split `git diff` output into per-file line lists with old/new line numbers."""
    files: List[Dict[str, Any]] = []
    current: Dict[str, Any] = {}
    old_no = new_no = 0
    for raw in text.splitlines():
        if raw.startswith("diff --git "):
            parts = raw.split(" b/", 1)
            current = {"path": parts[1] if len(parts) == 2 else raw[11:], "additions": 0, "deletions": 0, "binary": False, "lines": []}
            files.append(current)
            continue
        if not current:
            continue
        if raw.startswith("+++ ") or raw.startswith("--- ") or raw.startswith("index ") or raw.startswith(("new file", "deleted file", "similarity", "rename ", "old mode", "new mode")):
            if raw.startswith("+++ b/"):
                current["path"] = raw[6:]
            continue
        if raw.startswith("Binary files"):
            current["binary"] = True
            continue
        if raw.startswith("@@"):
            try:
                ranges = raw.split("@@")[1].split()
                old_no = int(ranges[0][1:].split(",")[0])
                new_no = int(ranges[1][1:].split(",")[0])
            except (IndexError, ValueError):
                old_no = new_no = 0
            current["lines"].append({"type": "hunk", "text": raw, "old": None, "new": None})
        elif raw.startswith("+"):
            current["additions"] += 1
            current["lines"].append({"type": "add", "text": raw[1:], "old": None, "new": new_no})
            new_no += 1
        elif raw.startswith("-"):
            current["deletions"] += 1
            current["lines"].append({"type": "del", "text": raw[1:], "old": old_no, "new": None})
            old_no += 1
        elif raw.startswith("\\"):
            continue
        else:
            current["lines"].append({"type": "context", "text": raw[1:] if raw.startswith(" ") else raw, "old": old_no, "new": new_no})
            old_no += 1
            new_no += 1
    return files


_HARDWARE: Dict[str, Any] = {}


def _hardware() -> Dict[str, Any]:
    """Host facts from the edge runtime probe (cached; RAM/arch don't change while running)."""
    if not _HARDWARE:
        from core.models.edge_loader import EdgeRuntimeManager
        hw = EdgeRuntimeManager().detect_hardware()
        _HARDWARE.update({
            "arch": hw.arch,
            "apple_silicon": hw.is_apple_silicon,
            "ram_gb": hw.estimated_ram_gb,
            "recommended_model": hw.recommended_model,
        })
    return _HARDWARE


@router.get("/status")
async def studio_status(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """Live runtime facts shown in the Studio header, status bar, and telemetry panel."""
    rows = await db.execute(select(TaskRecord.state, func.count()).group_by(TaskRecord.state))
    task_counts = {getattr(state, "value", state): count for state, count in rows.all()}

    branch_rc, branch = await _git("rev-parse", "--abbrev-ref", "HEAD")
    sha_rc, sha = await _git("rev-parse", "--short", "HEAD")
    tapes = len(list(FLIGHT_RECORDINGS_DIR.glob("*.flight.json"))) if FLIGHT_RECORDINGS_DIR.exists() else 0

    return {
        "version": STUDIO_VERSION,
        "environment": settings.env,
        "air_gapped": gateway.air_gap.enabled,
        "database_connected": await check_db_health(),
        "database_backend": settings.database_url.split(":", 1)[0],
        "ws_clients": len(ws_manager.active_connections),
        "providers": {
            "anthropic": bool(settings.anthropic_api_key),
            "openai": bool(settings.openai_api_key),
            "google": bool(settings.gemini_api_key),
            "local": True,
        },
        "local_model": settings.default_local_model,
        "hardware": _hardware(),
        "git": {
            "branch": branch.strip() if branch_rc == 0 else None,
            "sha": sha.strip() if sha_rc == 0 else None,
        },
        "tasks": {"total": sum(task_counts.values()), "by_state": task_counts},
        "flight_tapes": tapes,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/diff")
async def studio_diff() -> Dict[str, Any]:
    """Uncommitted changes in the Kora repo working tree (tracked files, vs HEAD)."""
    rc, out = await _git("diff", "--no-color", "--no-ext-diff", "HEAD")
    if rc != 0:
        return {"available": False, "truncated": False, "files": []}
    truncated = len(out.encode()) > MAX_DIFF_BYTES
    return {
        "available": True,
        "truncated": truncated,
        "files": parse_unified_diff(out[:MAX_DIFF_BYTES]),
    }


class AirGapRequest(BaseModel):
    enabled: bool


@router.post("/airgap", dependencies=[Depends(require(Permission.APPROVE_TIER3))])
async def set_air_gap(request: AirGapRequest) -> Dict[str, Any]:
    """Arm or disarm the zero-egress provider guard and notify every Studio client."""
    gateway.air_gap.enabled = request.enabled
    event = {
        "type": "air_gap_status_changed",
        "air_gapped": request.enabled,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    await ws_manager.broadcast(event)
    return event
