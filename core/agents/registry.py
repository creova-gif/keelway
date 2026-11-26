"""
Agent Manifest Registry for Keelway Core.
Stores agent manifests by name@version with instant kill-switch capabilities.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.agents import manifest as am
from core.storage.models import AgentManifestRecord


class ManifestRegistryError(ValueError):
    """Raised when manifest registration or retrieval fails."""


async def register_manifest(
    db: AsyncSession,
    data: Dict[str, Any],
    owner_override: Optional[str] = None,
) -> AgentManifestRecord:
    """Validate, digest, and store a manifest by name@version in the registry."""
    report = am.validate(data)
    if not report.ok:
        raise ManifestRegistryError(f"Invalid manifest: {'; '.join(report.errors)}")

    manifest = report.manifest
    if manifest is None:
        raise ManifestRegistryError("manifest validation produced no manifest")
    record_id = f"{manifest.name}@{manifest.version}"
    digest = am.digest(manifest)
    owner = owner_override or manifest.owner

    existing = await db.get(AgentManifestRecord, record_id)
    if existing is not None:
        raise ManifestRegistryError(f"Manifest '{record_id}' is already registered.")

    record = AgentManifestRecord(
        id=record_id,
        name=manifest.name,
        version=manifest.version,
        owner=owner,
        description=manifest.description,
        digest=digest,
        manifest_json=json.dumps(data, sort_keys=True),
        enabled=True,
    )
    db.add(record)
    await db.flush()
    return record


async def list_registered_manifests(
    db: AsyncSession,
    enabled_only: bool = False,
) -> List[AgentManifestRecord]:
    """List all registered agent manifests."""
    query = select(AgentManifestRecord).order_by(AgentManifestRecord.name, AgentManifestRecord.version.desc())
    if enabled_only:
        query = query.where(AgentManifestRecord.enabled.is_(True))
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_registered_manifest(
    db: AsyncSession,
    name: str,
    version: str,
) -> Optional[AgentManifestRecord]:
    """Retrieve a registered manifest by exact name and version."""
    record_id = f"{name}@{version}"
    return await db.get(AgentManifestRecord, record_id)


async def resolve_manifest_ref(
    db: AsyncSession,
    ref: str,
) -> AgentManifestRecord:
    """Resolve 'name@version' or 'name' (latest registered version).
    
    Raises ManifestRegistryError if not found or if the manifest is disabled via kill-switch.
    """
    if "@" in ref:
        name, version = ref.split("@", 1)
        record = await get_registered_manifest(db, name, version)
    else:
        # Latest version by semantic order
        query = select(AgentManifestRecord).where(AgentManifestRecord.name == ref).order_by(AgentManifestRecord.created_at.desc()).limit(1)
        result = await db.execute(query)
        record = result.scalars().first()

    if record is None:
        raise ManifestRegistryError(f"Manifest '{ref}' is not registered.")
    if not record.enabled:
        raise ManifestRegistryError(f"Manifest '{record.id}' has been disabled by security kill-switch.")
    return record


async def toggle_manifest_status(
    db: AsyncSession,
    name: str,
    version: str,
    enabled: bool,
) -> AgentManifestRecord:
    """Set the kill-switch status for an agent manifest."""
    record = await get_registered_manifest(db, name, version)
    if record is None:
        raise ManifestRegistryError(f"Manifest '{name}@{version}' not found.")
    record.enabled = enabled
    record.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return record
