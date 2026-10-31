"""
API authentication, RBAC enforcement, and the hash-chained audit log.

Tokens are bearer secrets. Two kinds are accepted:
- the per-process launch token (owner role), printed by `kora dev` and fixed via KORA_API_TOKEN;
- named tokens minted with `kora token create` or POST /v1/auth/tokens, stored only as SHA-256 hashes.
"""

import asyncio
import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.security.rbac import ROLE_PERMISSIONS, AccessControlManager, Permission, Role
from core.storage.database import AsyncSessionLocal
from core.storage.models import ApiTokenRecord, AuditEventRecord

TOKEN_PREFIX = "kora_"
GENESIS_HASH = "0" * 64


def generate_token() -> str:
    return TOKEN_PREFIX + secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


_launch_token = settings.kora_api_token or generate_token()
_audit_lock = asyncio.Lock()


def launch_token() -> str:
    return _launch_token


@dataclass(frozen=True)
class Principal:
    actor: str
    role: Role
    token_id: Optional[str] = None

    def can(self, permission: Permission) -> bool:
        return AccessControlManager.can_perform(self.role, permission)

    @property
    def permissions(self) -> List[str]:
        return [p.value for p in ROLE_PERMISSIONS.get(self.role, [])]


LOCAL_OWNER = Principal(actor="local", role=Role.OWNER)


async def create_api_token(db: AsyncSession, name: str, role: Role) -> Tuple[ApiTokenRecord, str]:
    token = generate_token()
    record = ApiTokenRecord(name=name, role=role.value, token_hash=hash_token(token))
    db.add(record)
    await db.flush()
    await db.refresh(record)
    return record, token


async def principal_for_token(token: Optional[str]) -> Optional[Principal]:
    if not token:
        return None
    if hmac.compare_digest(token.encode(), _launch_token.encode()):
        return Principal(actor="launch-token", role=Role.OWNER)
    async with AsyncSessionLocal() as db:
        record = (await db.execute(
            select(ApiTokenRecord).where(
                ApiTokenRecord.token_hash == hash_token(token),
                ApiTokenRecord.revoked_at.is_(None),
            )
        )).scalar_one_or_none()
        if record is None:
            return None
        record.last_used_at = datetime.now(timezone.utc)
        await db.commit()
        return Principal(actor=record.name, role=Role(record.role), token_id=record.id)


def token_from_headers(headers) -> Optional[str]:
    scheme, _, value = headers.get("authorization", "").partition(" ")
    if scheme.lower() == "bearer" and value.strip():
        return value.strip()
    return headers.get("x-kora-token")


async def current_principal(request: Request) -> Principal:
    if not settings.auth_required:
        return LOCAL_OWNER
    principal = await principal_for_token(token_from_headers(request.headers))
    if principal is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid API token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return principal


def require(permission: Permission):
    """Route dependency: authenticate, check the role's permission, and audit the decision."""

    async def dependency(request: Request, principal: Principal = Depends(current_principal)) -> Principal:
        allowed = principal.can(permission)
        await record_audit(principal, permission.value, f"{request.method} {request.url.path}", allowed)
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{principal.role.value}' lacks permission '{permission.value}'.",
            )
        return principal

    return dependency


def _audit_fields(actor: str, role: str, action: str, resource: str, allowed: bool, timestamp: str) -> Dict[str, Any]:
    return {"actor": actor, "role": role, "action": action, "resource": resource, "allowed": allowed, "timestamp": timestamp}


def _chain_hash(prev_hash: str, fields: Dict[str, Any]) -> str:
    canonical = json.dumps(fields, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256((prev_hash + canonical).encode("utf-8")).hexdigest()


async def record_audit(principal: Principal, action: str, resource: str, allowed: bool) -> None:
    """Append one entry in its own committed transaction, so denials survive the request's rollback."""
    fields = _audit_fields(
        principal.actor, principal.role.value, action, resource[:512], allowed,
        datetime.now(timezone.utc).isoformat(),
    )
    # prev_hash is UNIQUE, so a concurrent writer in another process that raced us onto the
    # same predecessor fails the insert and retries on the new head instead of forking the chain.
    async with _audit_lock:
        for _ in range(5):
            async with AsyncSessionLocal() as db:
                prev = (await db.execute(
                    select(AuditEventRecord.entry_hash).order_by(AuditEventRecord.seq.desc()).limit(1)
                )).scalar_one_or_none() or GENESIS_HASH
                db.add(AuditEventRecord(**fields, prev_hash=prev, entry_hash=_chain_hash(prev, fields)))
                try:
                    await db.commit()
                    return
                except IntegrityError:
                    await db.rollback()
        raise RuntimeError("Could not append audit entry after concurrent retries.")


async def verify_audit_chain() -> Dict[str, Any]:
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(select(AuditEventRecord).order_by(AuditEventRecord.seq))).scalars().all()
    prev = GENESIS_HASH
    for row in rows:
        fields = _audit_fields(row.actor, row.role, row.action, row.resource, bool(row.allowed), row.timestamp)
        if row.prev_hash != prev or row.entry_hash != _chain_hash(prev, fields):
            return {"valid": False, "entries": len(rows), "broken_at_seq": row.seq}
        prev = row.entry_hash
    return {"valid": True, "entries": len(rows), "head": prev}
