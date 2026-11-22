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
from core.security.auth import (
    Principal, create_api_token, create_pairing_code, current_principal, record_audit, redeem_pairing_code, require,
    verify_audit_chain,
)
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
    expires_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class PairingCodeResponse(BaseModel):
    code: str = Field(..., description="Single use; only its hash is stored")
    expires_at: datetime


class PairRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=200)
    device_name: str = Field("phone", min_length=1, max_length=60)


class PairedTokenResponse(BaseModel):
    token: str
    role: Role
    expires_at: datetime


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
    prev_hash: str
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


@router.post("/v1/auth/pairing-codes", response_model=PairingCodeResponse, status_code=status.HTTP_201_CREATED)
async def create_phone_pairing_code(
    _: Principal = Depends(require(Permission.MANAGE_KEYS)),
    db: AsyncSession = Depends(get_db),
) -> PairingCodeResponse:
    record, code = await create_pairing_code(db)
    return PairingCodeResponse(code=code, expires_at=record.expires_at)


@router.post("/v1/auth/pair", response_model=PairedTokenResponse)
async def pair_phone(request: PairRequest, db: AsyncSession = Depends(get_db)) -> PairedTokenResponse:
    """Unauthenticated by design: the single-use code is the credential."""
    redeemed = await redeem_pairing_code(db, request.code.strip(), request.device_name.strip() or "phone")
    if redeemed is None:
        raise HTTPException(status_code=401, detail="Pairing code is invalid, expired or already used. Run `keelway mobile pair` again.")
    record, token = redeemed
    await db.commit()
    await record_audit(Principal(actor=record.name, role=Role.PHONE, token_id=record.id), "phone_paired", f"token {record.id}", True)
    return PairedTokenResponse(token=token, role=Role.PHONE, expires_at=record.expires_at)


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


@router.get("/v1/phone/receipts", response_model=List[AuditEventResponse])
async def phone_receipts(
    limit: int = 20,
    _: Principal = Depends(current_principal),
    db: AsyncSession = Depends(get_db),
) -> List[AuditEventResponse]:
    """Read-only tape view for the bridge watch: the most recent sealed audit entries.

    Phones reach this via the PHONE_ROUTES allowlist rather than VIEW_AUDIT_LOGS;
    it returns the same redacted entry fields the audit list exposes, newest first.
    """
    limit = max(1, min(limit, 100))
    rows = (await db.execute(select(AuditEventRecord).order_by(AuditEventRecord.seq.desc()).limit(limit))).scalars().all()
    return [AuditEventResponse.model_validate(r) for r in rows]


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


@router.get("/v1/audit/export")
async def export_audit(
    download: bool = False,
    _: Principal = Depends(require(Permission.VIEW_AUDIT_LOGS)),
) -> Any:
    """Export the live audit log in portable Keelway Record v1 JSONL format."""
    from fastapi.responses import Response
    from core.security.record_export import export_record

    res = await export_record()
    headers = {"Content-Type": "application/x-ndjson; charset=utf-8"}
    if download:
        headers["Content-Disposition"] = "attachment; filename=keelway-audit.record.jsonl"
    return Response(content=res["text"], media_type="application/x-ndjson", headers=headers)


@router.post("/v1/audit/anchor")
async def anchor_audit_head(
    principal: Principal = Depends(require(Permission.VIEW_AUDIT_LOGS)),
) -> Dict[str, Any]:
    """Create a signed head anchor receipt and git note for the current audit head."""
    from core.security.record_export import create_head_anchor
    from core.security.auth import record_audit
    anchor_data = await create_head_anchor()
    await record_audit(principal, "audit_head_anchored", f"head={anchor_data['head_hash']} entries={anchor_data['entries_count']}", True)
    return anchor_data


@router.get("/v1/audit/anchor")
async def get_audit_head_anchor(
    _: Principal = Depends(require(Permission.VIEW_AUDIT_LOGS)),
) -> Dict[str, Any]:
    """Retrieve the latest signed head anchor for the audit log."""
    from core.security.record_export import create_head_anchor
    return await create_head_anchor()


