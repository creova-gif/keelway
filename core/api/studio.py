"""
Keelway Studio API: live workspace status, working-tree diff, agent manifest inspection, and air-gap control.
"""

import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.agents import manifest as am
from core.agents.guard import static_refusal
from core.agents.registry import list_registered_manifests
from core.api import routes
from core.api.routes import FLIGHT_RECORDINGS_DIR, ws_manager
from core.api.schemas import Provider
from core.config import settings
from core.models.gateway import gateway
from core.security.auth import current_principal, require
from core.security.rbac import Permission
from core.storage.database import check_db_health, get_db
from core.storage.models import AgentManifestRecord, TaskRecord

router = APIRouter(prefix="/v1/studio", tags=["Studio"], dependencies=[Depends(current_principal)])

MAX_DIFF_BYTES = 512 * 1024
STUDIO_VERSION = "0.1.0"
_MANIFEST_SCAN_DIRS = ("agents", "docs/spec/examples", ".keelway/manifests")
_MANIFEST_SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"}
_MAX_MANIFEST_FILES = 200
_MAX_MANIFEST_FILE_BYTES = 256 * 1024
_MAX_MANIFEST_SCAN_DEPTH = 5


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
    stdout_reader = proc.stdout
    while len(out) <= limit and stdout_reader is not None:
        chunk = await stdout_reader.read(65536)
        if not chunk:
            break
        out += chunk
    if len(out) > limit and proc.returncode is None:
        proc.kill()
        await proc.wait()
        return 0, out.decode(errors="replace")
    await proc.wait()
    return proc.returncode if proc.returncode is not None else -1, out.decode(errors="replace")


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


def _load_existing_signing_key(workspace_root: Path) -> Optional[bytes]:
    """Read the workspace HMAC signing key if present on disk without ever creating or mutating files."""
    key_path = Path(workspace_root) / ".keelway" / am.KEY_FILE
    try:
        if not key_path.is_file() or key_path.is_symlink():
            return None
        raw_hex = key_path.read_text(encoding="utf-8").strip()
        if not raw_hex:
            return None
        return bytes.fromhex(raw_hex)
    except (OSError, ValueError):
        return None


def _inspect_signature(manifest: am.AgentManifest, workspace_root: Path) -> Dict[str, Any]:
    """Verify cryptographic HMAC-SHA256 manifest signature without mutating disk or leaking key material."""
    sig = manifest.signature
    if sig is None:
        return {
            "signature_status": "unsigned",
            "signature_reason": "not_signed",
            "signed_by": None,
            "signed_at": None,
            "key_id": None,
        }

    key = _load_existing_signing_key(workspace_root)
    if key is None:
        if sig.digest != am.digest(manifest):
            status, reason = "invalid_signature", "content_changed_since_signing"
        else:
            status, reason = "key_missing", "key_missing"
    else:
        ok, reason = am.verify(manifest, key)
        status = "verified" if ok else "invalid_signature"

    return {
        "signature_status": status,
        "signature_reason": reason,
        "signed_by": sig.signed_by,
        "signed_at": sig.signed_at,
        "key_id": sig.key_id,
    }


def _governance_summary(manifest: am.AgentManifest) -> Dict[str, Any]:
    """Extract normalized governance, capability, and budget boundaries from a validated manifest."""
    perms = manifest.permissions
    return {
        "routing": manifest.model.routing,
        "preferred_provider": manifest.model.preferred_provider,
        "autonomy": perms.autonomy,
        "sandbox": manifest.sandbox,
        "network": perms.network,
        "network_allow": list(perms.network_allow),
        "max_usd_per_run": manifest.budget.max_usd_per_run,
        "max_steps": manifest.budget.max_steps,
        "tools": list(manifest.tools),
        "mcp_servers": list(manifest.mcp_servers),
        "read_paths": list(perms.read_paths),
        "write_paths": list(perms.write_paths),
        "commands": list(perms.commands),
    }


def _security_warnings(
    manifest: am.AgentManifest,
    report_warnings: List[str],
    signature_status: str,
    signature_reason: str,
) -> List[str]:
    """Build actionable security posture warnings for Studio inspection."""
    warnings: List[str] = []
    if signature_status == "unsigned":
        warnings.append("Manifest is unsigned")
    elif signature_status == "invalid_signature":
        warnings.append(
            f"Invalid cryptographic signature ({signature_reason}): manifest content or signature failed verification"
        )
    elif signature_status == "key_missing":
        warnings.append(
            "Workspace signing key (.keelway/agent_signing.key) is missing; signature authenticity cannot be verified"
        )

    perms = manifest.permissions
    if perms.network == "allowlist":
        warnings.append(
            "Network policy is 'allowlist': OS sandbox enforces zero network and loop_from_manifest will refuse runs until network == 'none'"
        )
    if perms.autonomy == "autonomous" and (set(manifest.tools) & am.MUTATING_TOOLS):
        warnings.append("Autonomous file mutation enabled")

    refusal = static_refusal(manifest)
    if refusal:
        warnings.append(f"Static runtime guard refusal: {refusal}")

    for w in report_warnings:
        if w not in warnings:
            warnings.append(w)
    return warnings


def _discover_workspace_manifest_files(workspace_root: Path) -> List[Tuple[str, Path]]:
    """Discover `*.agent.json` files in bounded workspace locations, skipping `.git` and `node_modules`."""
    try:
        root_resolved = Path(workspace_root).resolve()
    except OSError:
        return []

    found: List[Tuple[str, Path]] = []
    seen_resolved: set[Path] = set()

    for rel_dir in _MANIFEST_SCAN_DIRS:
        scan_base = root_resolved / rel_dir
        if not scan_base.exists() or not scan_base.is_dir():
            continue
        try:
            scan_base.resolve().relative_to(root_resolved)
        except ValueError:
            continue

        for dirpath, dirnames, filenames in os.walk(scan_base, followlinks=False):
            current = Path(dirpath)
            try:
                rel_current = current.resolve().relative_to(scan_base.resolve())
                depth = len(rel_current.parts)
            except ValueError:
                dirnames[:] = []
                continue

            dirnames[:] = sorted(
                d for d in dirnames
                if d not in _MANIFEST_SKIP_DIRS and depth < _MAX_MANIFEST_SCAN_DEPTH
            )

            for fname in sorted(filenames):
                if not fname.endswith(".agent.json"):
                    continue
                candidate = current / fname
                if candidate.is_symlink():
                    continue
                try:
                    resolved = candidate.resolve()
                    rel_posix = resolved.relative_to(root_resolved).as_posix()
                    st = resolved.stat()
                except (OSError, ValueError):
                    continue
                if st.st_size > _MAX_MANIFEST_FILE_BYTES or resolved in seen_resolved:
                    continue
                seen_resolved.add(resolved)
                found.append((rel_posix, resolved))
                if len(found) >= _MAX_MANIFEST_FILES:
                    return sorted(found, key=lambda item: item[0])

    return sorted(found, key=lambda item: item[0])


def _inspect_manifest_payload(raw: Any, workspace_root: Path) -> Dict[str, Any]:
    """Validate and inspect a raw manifest payload without mutating disk or database."""
    parsed = raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except ValueError as exc:
            return {
                "valid": False,
                "errors": [f"Invalid JSON: {exc}"],
                "digest": None,
                "signature_status": "unsigned",
                "signature_reason": "invalid_json",
                "signed_by": None,
                "signed_at": None,
                "key_id": None,
                "governance_summary": None,
                "security_warnings": [],
                "canonical_json": None,
            }

    report = am.validate(parsed)
    if not report.ok or report.manifest is None:
        return {
            "valid": False,
            "errors": list(report.errors),
            "digest": None,
            "signature_status": "unsigned",
            "signature_reason": "invalid_manifest",
            "signed_by": None,
            "signed_at": None,
            "key_id": None,
            "governance_summary": None,
            "security_warnings": [],
            "canonical_json": None,
        }

    manifest = report.manifest
    dig = am.digest(manifest)
    sig_info = _inspect_signature(manifest, workspace_root)
    gov = _governance_summary(manifest)
    warnings = _security_warnings(
        manifest,
        report.warnings,
        sig_info["signature_status"],
        sig_info["signature_reason"],
    )
    return {
        "valid": True,
        "errors": [],
        "id": f"{manifest.name}@{manifest.version}",
        "name": manifest.name,
        "version": manifest.version,
        "owner": manifest.owner,
        "description": manifest.description,
        "digest": dig,
        "signature_status": sig_info["signature_status"],
        "signature_reason": sig_info["signature_reason"],
        "signed_by": sig_info["signed_by"],
        "signed_at": sig_info["signed_at"],
        "key_id": sig_info["key_id"],
        "governance_summary": gov,
        "security_warnings": warnings,
        "canonical_json": am.to_json(manifest),
    }


@router.get("/status")
async def studio_status(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """Live runtime facts shown in the Studio header, status bar, and telemetry panel."""
    rows = await db.execute(select(TaskRecord.state, func.count()).group_by(TaskRecord.state))
    task_counts = {getattr(state, "value", state): count for state, count in rows.all()}

    reg_count_row = await db.execute(select(func.count()).select_from(AgentManifestRecord))
    reg_manifests_count = int(reg_count_row.scalar() or 0)
    ws_manifests_count = len(_discover_workspace_manifest_files(Path(routes._workspace_fs.root)))

    branch_rc, branch = await _git("rev-parse", "--abbrev-ref", "HEAD")
    sha_rc, sha = await _git("rev-parse", "--short", "HEAD")
    tapes = len(list(FLIGHT_RECORDINGS_DIR.glob("*.flight.json"))) if FLIGHT_RECORDINGS_DIR.exists() else 0
    local_adapter = gateway.adapters.get(Provider.LOCAL)
    local = (await asyncio.to_thread(local_adapter.describe) if local_adapter is not None and hasattr(local_adapter, "describe")
             else {"up": bool(local_adapter), "available": bool(local_adapter), "api": None, "model": None})
    from core.models.cost_ledger import cost_ledger
    economics = cost_ledger.get_summary()

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
            "local": local["available"],
        },
        "local_model": local["model"] or ("no model installed" if local["up"] else "not running"),
        "local_runtime": local,
        "hardware": _hardware(),
        "git": {
            "branch": branch.strip() if branch_rc == 0 else None,
            "sha": sha.strip() if sha_rc == 0 else None,
        },
        "tasks": {"total": sum(task_counts.values()), "by_state": task_counts},
        "manifests_count": reg_manifests_count + ws_manifests_count,
        "flight_tapes": tapes,
        "economics": economics,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/manifests")
async def studio_list_manifests(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """Discover and inspect registered DB manifests and workspace `*.agent.json` files."""
    workspace_root = Path(routes._workspace_fs.root)
    records = await list_registered_manifests(db, enabled_only=False)
    ws_files = _discover_workspace_manifest_files(workspace_root)

    manifests: List[Dict[str, Any]] = []
    registry_enabled_by_id: Dict[str, bool] = {}

    for record in records:
        registry_enabled_by_id[record.id] = bool(record.enabled)
        try:
            raw_data = json.loads(record.manifest_json)
        except ValueError:
            raw_data = None
        inspected = _inspect_manifest_payload(raw_data, workspace_root)
        entry: Dict[str, Any] = {
            "id": record.id,
            "name": record.name,
            "version": record.version,
            "owner": record.owner,
            "description": record.description or inspected.get("description", ""),
            "source": "registry",
            "path": None,
            "enabled": bool(record.enabled),
            "valid": inspected["valid"],
            "errors": inspected["errors"],
            "digest": inspected["digest"] or record.digest,
            "signature_status": inspected["signature_status"],
            "signature_reason": inspected["signature_reason"],
            "signed_by": inspected["signed_by"],
            "signed_at": inspected["signed_at"],
            "key_id": inspected["key_id"],
            "governance_summary": inspected["governance_summary"],
            "security_warnings": list(inspected["security_warnings"]),
            "canonical_json": inspected["canonical_json"],
        }
        if not record.enabled:
            entry["security_warnings"].insert(
                0, f"Manifest '{record.id}' is currently disabled via registry security kill-switch"
            )
        manifests.append(entry)

    for rel_path, full_path in ws_files:
        try:
            raw_data = am.load_file(full_path)
            inspected = _inspect_manifest_payload(raw_data, workspace_root)
        except ValueError as exc:
            inspected = {
                "valid": False,
                "errors": [str(exc)],
                "digest": None,
                "signature_status": "unsigned",
                "signature_reason": "invalid_json",
                "signed_by": None,
                "signed_at": None,
                "key_id": None,
                "governance_summary": None,
                "security_warnings": ["Workspace manifest file is not valid JSON"],
                "canonical_json": None,
            }

        if inspected["valid"]:
            manifest_id = inspected["id"]
            enabled = registry_enabled_by_id.get(manifest_id, True)
            warnings = list(inspected["security_warnings"])
            if not enabled:
                warnings.insert(
                    0, f"Matching registry manifest '{manifest_id}' is disabled via security kill-switch"
                )
            manifests.append({
                "id": manifest_id,
                "name": inspected["name"],
                "version": inspected["version"],
                "owner": inspected["owner"],
                "description": inspected["description"],
                "source": "workspace",
                "path": rel_path,
                "enabled": enabled,
                "valid": True,
                "errors": [],
                "digest": inspected["digest"],
                "signature_status": inspected["signature_status"],
                "signature_reason": inspected["signature_reason"],
                "signed_by": inspected["signed_by"],
                "signed_at": inspected["signed_at"],
                "key_id": inspected["key_id"],
                "governance_summary": inspected["governance_summary"],
                "security_warnings": warnings,
                "canonical_json": inspected["canonical_json"],
            })
        else:
            stem = full_path.name[:-len(".agent.json")] if full_path.name.endswith(".agent.json") else full_path.stem
            manifests.append({
                "id": f"{stem}@invalid",
                "name": stem,
                "version": "0.0.0",
                "owner": "unknown",
                "description": f"Invalid manifest at {rel_path}",
                "source": "workspace",
                "path": rel_path,
                "enabled": False,
                "valid": False,
                "errors": inspected["errors"],
                "digest": None,
                "signature_status": "unsigned",
                "signature_reason": inspected["signature_reason"],
                "signed_by": None,
                "signed_at": None,
                "key_id": None,
                "governance_summary": None,
                "security_warnings": inspected["security_warnings"] or ["Manifest failed schema validation"],
                "canonical_json": None,
            })

    return {
        "manifests": manifests,
        "count": len(manifests),
        "signing_key_present": _load_existing_signing_key(workspace_root) is not None,
    }


@router.post("/manifests/inspect")
async def studio_inspect_manifest(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and inspect an arbitrary `keelway.agent/v1` manifest payload without mutating disk."""
    workspace_root = Path(routes._workspace_fs.root)
    raw_manifest = payload["manifest"] if isinstance(payload, dict) and "manifest" in payload else payload
    return _inspect_manifest_payload(raw_manifest, workspace_root)


@router.get("/diff")
async def studio_diff() -> Dict[str, Any]:
    """Uncommitted changes in the Keelway repo working tree (tracked files, vs HEAD)."""
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
