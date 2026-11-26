"""
API authentication, RBAC enforcement, and the hash-chained audit log.

Tokens are bearer secrets. Two kinds are accepted:
- the per-process launch token (owner role), printed by `keelway dev` and fixed via KEELWAY_API_TOKEN;
- named tokens minted with `keelway token create` or POST /v1/auth/tokens, stored only as SHA-256 hashes.

Phones pair with a single-use code from `keelway mobile pair` (valid for minutes) and exchange it at
POST /v1/auth/pair for a phone-role token that expires and can only reach PHONE_ROUTES.
"""

import asyncio
import hashlib
import hmac
import json
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple, cast

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.security.rbac import ROLE_PERMISSIONS, AccessControlManager, Permission, Role
from core.storage.database import AsyncSessionLocal
from core.storage.models import ApiTokenRecord, AuditEventRecord, PairingCodeRecord

TOKEN_PREFIX = "keelway_"
PAIRING_PREFIX = "keelway_pair_"
GENESIS_HASH = "0" * 64
PAIRING_CODE_TTL = timedelta(minutes=10)
PHONE_TOKEN_TTL = timedelta(days=30)

# Everything a phone-role token may call. Anything else is refused, whatever its permission check.
PHONE_ROUTES = (
    ("GET", re.compile(r"/v1/auth/whoami")),
    ("GET", re.compile(r"/v1/studio/status")),
    ("GET", re.compile(r"/v1/agent/runs")),
    ("GET", re.compile(r"/v1/agent/status/[^/]+")),
    ("POST", re.compile(r"/v1/agent/approve/[^/]+")),
    # Bridge-watch receipt reads: latest tape entries + merkle inclusion proofs.
    ("GET", re.compile(r"/v1/phone/receipts")),
    ("GET", re.compile(r"/v1/audit/merkle/root")),
    ("GET", re.compile(r"/v1/audit/merkle/proof/[^/]+")),
)


def phone_route_allowed(method: str, path: str) -> bool:
    return any(method == m and rx.fullmatch(path) for m, rx in PHONE_ROUTES)


def _aware(dt: Optional[datetime]) -> Optional[datetime]:
    """SQLite hands back naive datetimes; every stored timestamp is UTC."""
    return dt.replace(tzinfo=timezone.utc) if dt is not None and dt.tzinfo is None else dt


def generate_token() -> str:
    return TOKEN_PREFIX + secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


_launch_token = settings.keelway_api_token or generate_token()
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


async def create_api_token(
    db: AsyncSession, name: str, role: Role, expires_at: Optional[datetime] = None,
) -> Tuple[ApiTokenRecord, str]:
    token = generate_token()
    record = ApiTokenRecord(name=name, role=role.value, token_hash=hash_token(token), expires_at=expires_at)
    db.add(record)
    await db.flush()
    await db.refresh(record)
    return record, token


async def create_pairing_code(db: AsyncSession, ttl: timedelta = PAIRING_CODE_TTL) -> Tuple[PairingCodeRecord, str]:
    code = PAIRING_PREFIX + secrets.token_urlsafe(24)
    record = PairingCodeRecord(code_hash=hash_token(code), expires_at=datetime.now(timezone.utc) + ttl)
    db.add(record)
    await db.flush()
    await db.refresh(record)
    return record, code


async def redeem_pairing_code(
    db: AsyncSession, code: str, device_name: str, ttl: timedelta = PHONE_TOKEN_TTL,
) -> Optional[Tuple[ApiTokenRecord, str]]:
    """Spend a pairing code once, before it expires, for a phone-role token. None if it can't be spent."""
    record = (await db.execute(
        select(PairingCodeRecord).where(PairingCodeRecord.code_hash == hash_token(code))
    )).scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if record is None or record.used_at is not None:
        return None
    expires_at = _aware(record.expires_at)
    if expires_at is None or expires_at <= now:
        return None
    # Conditional on used_at still being empty, so two phones racing on one code can't both win.
    claimed = cast(
        CursorResult[Any],
        await db.execute(
            update(PairingCodeRecord)
            .where(PairingCodeRecord.id == record.id, PairingCodeRecord.used_at.is_(None))
            .values(used_at=now)
        ),
    )
    if claimed.rowcount != 1:
        return None
    token_record, token = await create_api_token(db, f"phone: {device_name}", Role.PHONE, expires_at=now + ttl)
    await db.execute(update(PairingCodeRecord).where(PairingCodeRecord.id == record.id).values(token_id=token_record.id))
    return token_record, token


async def principal_for_token(token: Optional[str]) -> Optional[Principal]:
    if not token or token.startswith(PAIRING_PREFIX):
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
        now = datetime.now(timezone.utc)
        expires_at = _aware(record.expires_at)
        if expires_at is not None and expires_at <= now:
            return None
        record.last_used_at = now
        await db.commit()
        return Principal(actor=record.name, role=Role(record.role), token_id=record.id)


def token_from_headers(headers) -> Optional[str]:
    scheme, _, value = headers.get("authorization", "").partition(" ")
    if scheme.lower() == "bearer" and value.strip():
        return value.strip()
    return headers.get("x-keelway-token")


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
    if principal.role == Role.PHONE and not phone_route_allowed(request.method, request.url.path):
        await record_audit(principal, "phone_route", f"{request.method} {request.url.path}", False)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="A paired phone can only view agent runs and approve or deny their steps.",
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
