"""
Token management and audit log API.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.security.auth import Principal, create_api_token, current_principal, require, verify_audit_chain
from core.security.rbac import Permission, Role
from core.storage.database import get_db
from core.storage.models import ApiTokenRecord, AuditEventRecord

router = APIRouter(tags=["Auth & Audit"])


class TokenCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    role: Role = Role.ENGINEER


class TokenResponse(BaseModel):
    id: str
    name: str
    role: Role
    created_at: datetime
    last_used_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class TokenCreatedResponse(TokenResponse):
    token: str = Field(..., description="Shown once; only its hash is stored")


class AuditEventResponse(BaseModel):
    seq: int
    timestamp: str
    actor: str
    role: str
    action: str
    resource: str
    allowed: bool
    entry_hash: str

    model_config = {"from_attributes": True}


@router.get("/v1/auth/whoami")
async def whoami(principal: Principal = Depends(current_principal)) -> Dict[str, Any]:
    return {
        "actor": principal.actor,
        "role": principal.role.value,
        "permissions": principal.permissions,
        "auth_required": settings.auth_required,
    }


@router.get("/v1/auth/tokens", response_model=List[TokenResponse])
async def list_tokens(
    _: Principal = Depends(require(Permission.MANAGE_KEYS)),
    db: AsyncSession = Depends(get_db),
) -> List[TokenResponse]:
    rows = (await db.execute(select(ApiTokenRecord).order_by(ApiTokenRecord.created_at.desc()))).scalars().all()
    return [TokenResponse.model_validate(r) for r in rows]


@router.post("/v1/auth/tokens", response_model=TokenCreatedResponse, status_code=status.HTTP_201_CREATED)
async def create_token(
    request: TokenCreateRequest,
    _: Principal = Depends(require(Permission.MANAGE_KEYS)),
    db: AsyncSession = Depends(get_db),
) -> TokenCreatedResponse:
    record, token = await create_api_token(db, request.name, request.role)
    return TokenCreatedResponse(**TokenResponse.model_validate(record).model_dump(), token=token)


@router.delete("/v1/auth/tokens/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_token(
    token_id: str,
    _: Principal = Depends(require(Permission.MANAGE_KEYS)),
    db: AsyncSession = Depends(get_db),
) -> None:
    record = await db.get(ApiTokenRecord, token_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Token not found.")
    if record.revoked_at is None:
        record.revoked_at = datetime.now(timezone.utc)


@router.get("/v1/audit", response_model=List[AuditEventResponse])
async def list_audit_events(
    limit: int = 100,
    _: Principal = Depends(require(Permission.VIEW_AUDIT_LOGS)),
    db: AsyncSession = Depends(get_db),
) -> List[AuditEventResponse]:
    limit = max(1, min(limit, 500))
    rows = (await db.execute(select(AuditEventRecord).order_by(AuditEventRecord.seq.desc()).limit(limit))).scalars().all()
    return [AuditEventResponse.model_validate(r) for r in rows]


@router.get("/v1/audit/verify")
async def verify_audit(_: Principal = Depends(require(Permission.VIEW_AUDIT_LOGS))) -> Dict[str, Any]:
    return await verify_audit_chain()
