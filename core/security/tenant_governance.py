"""Keelway Enterprise Tenant Governance, Scoped API Keys, Spend Caps & Rate Limiting (Layer 6)."""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Literal, NamedTuple, Optional, Tuple

from pydantic import BaseModel, Field, field_validator

from core.security.firewall import DLPScanner
from core.security.governance_store import (
    GENESIS_GOVERNANCE_HASH,
    SQLiteGovernanceStore,
    compute_audit_event_hash,
)
from core.security.redact import redact_text

KEY_LIVE_PREFIX = "kw_live_"
KEY_PREFIX_LEN = 14  # "kw_live_" (8) + 6-hex short_id = 14 chars
_KEY_FORMAT_RE = re.compile(r"^kw_live_[0-9a-f]{6}_[0-9a-f]{32}$")
_KEY_INLINE_RE = re.compile(r"kw_live_[0-9a-f]{6}_[0-9a-f]{32}")
OPENCORE_FALLBACK_MODEL = "keelway-core:7b"
OPENCORE_FALLBACK_PROVIDER = "local"
_SOVEREIGN_LOCAL_PROVIDERS = frozenset({"local", "ollama", "vllm"})
AuditOutcome = Literal["allow", "deny", "downgrade_opencore"]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    return (
        None
        if dt is None
        else (dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc))
    )


def _parse_iso_utc(raw: Optional[str]) -> Optional[datetime]:
    if not raw:
        return None
    normalized = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    return _ensure_utc(datetime.fromisoformat(normalized))


class AuditChainStatus(NamedTuple):
    """Tuple-compatible verification status supporting both unpacking and boolean truthiness."""

    valid: bool
    broken_at_seq: Optional[int] = None

    def __bool__(self) -> bool:
        return self.valid


class GovernanceError(Exception):
    def __init__(self, reason: str, status_code: int = 403, tenant_id: Optional[str] = None) -> None:
        super().__init__(reason)
        self.reason, self.status_code, self.tenant_id = reason, status_code, tenant_id


class BudgetExceededGovernanceError(GovernanceError):
    def __init__(self, reason: str, tenant_id: Optional[str] = None) -> None:
        super().__init__(reason=reason, status_code=402, tenant_id=tenant_id)


class DataResidencyZone(str, Enum):
    LOCAL_ONLY = "local_only"
    AFRICA_SOVEREIGN = "africa_sovereign"
    EU_SOVEREIGN = "eu_sovereign"
    GLOBAL = "global"


class TenantPolicy(BaseModel):
    tenant_id: str = Field(..., min_length=1, max_length=128)
    name: str = Field(..., min_length=1, max_length=255)
    allowed_categories: List[str] = Field(
        default_factory=lambda: ["open_weight", "closed_proprietary"], min_length=1
    )
    allowed_providers: List[str] = Field(
        default_factory=lambda: ["local", "gemini"], min_length=1
    )
    residency_zone: DataResidencyZone = DataResidencyZone.GLOBAL
    daily_spend_limit_usd: float = Field(default=10.0, ge=0.0)
    monthly_spend_limit_usd: float = Field(default=100.0, ge=0.0)
    fallback_to_opencore_on_budget_exceeded: bool = True
    requests_per_minute: int = Field(default=60, ge=1)
    tokens_per_minute: int = Field(default=120_000, ge=1)
    log_redacted_prompts: bool = False
    retention_days: int = Field(default=30, ge=1, le=3650)

    @field_validator("allowed_categories", "allowed_providers")
    @classmethod
    def _normalize_str_list(cls, values: List[str]) -> List[str]:
        cleaned = [v.strip().lower() for v in values if v and v.strip()]
        if not cleaned:
            raise ValueError("Allowlist must contain at least one non-empty entry.")
        return cleaned


class ScopedAPIKeyMetadata(BaseModel):
    key_id: str
    tenant_id: str
    name: str
    key_prefix: str = Field(..., min_length=KEY_PREFIX_LEN, max_length=KEY_PREFIX_LEN)
    scopes: List[str]
    created_at: datetime
    expires_at: Optional[datetime] = None
    revoked: bool = False
    last_used_at: Optional[datetime] = None


class _StoredScopedKey(ScopedAPIKeyMetadata):
    secret_sha256: str

    def to_metadata(self) -> ScopedAPIKeyMetadata:
        return ScopedAPIKeyMetadata(**self.model_dump(exclude={"secret_sha256"}))


class KeyAuthenticationResult(BaseModel):
    valid: bool
    key_id: Optional[str] = None
    tenant_id: Optional[str] = None
    scopes: List[str] = Field(default_factory=list)
    reason: str
    status_code: int = 200

    def __bool__(self) -> bool:
        return self.valid


class ScopedAPIKeyManager:
    """Thread-safe manager issuing and authenticating `kw_live_<short_id>_<32_hex>` keys."""

    def __init__(
        self,
        salt: Optional[str] = None,
        now_fn: Callable[[], datetime] = _utc_now,
        store: Optional[SQLiteGovernanceStore] = None,
    ) -> None:
        self._lock = threading.RLock()
        self._store = store
        self._now_fn = now_fn
        if self._store is not None:
            self._salt = self._store.get_or_create_salt(fallback_salt=salt)
        else:
            self._salt = salt or secrets.token_hex(32)
        self._records: Dict[str, _StoredScopedKey] = {}
        self._dummy_digest = hashlib.sha256(f"{self._salt}:dummy".encode("utf-8")).hexdigest()
        if self._store is not None:
            self._hydrate_from_store_locked()

    def _hydrate_from_store_locked(self) -> None:
        assert self._store is not None
        for row in self._store.list_scoped_keys():
            created_dt = _parse_iso_utc(row["created_at"]) or self._now_fn()
            rec = _StoredScopedKey(
                key_id=row["key_id"],
                tenant_id=row["tenant_id"],
                name=row["name"],
                key_prefix=row["key_prefix"],
                secret_sha256=row["secret_sha256"],
                scopes=list(row["scopes"]),
                created_at=created_dt,
                expires_at=_parse_iso_utc(row["expires_at"]),
                revoked=bool(row["revoked"]),
                last_used_at=_parse_iso_utc(row["last_used_at"]),
            )
            self._records[rec.key_id] = rec

    def _salted_sha256(self, key_id: str, raw_key: str) -> str:
        return hashlib.sha256(f"{self._salt}:{key_id}:{raw_key}".encode("utf-8")).hexdigest()

    def issue_key(
        self,
        tenant_id: str,
        name: str,
        scopes: List[str],
        expires_at: Optional[datetime] = None,
    ) -> Tuple[ScopedAPIKeyMetadata, str]:
        if not tenant_id.strip() or not name.strip():
            raise GovernanceError("tenant_id and key name must be non-empty.", status_code=400)
        normalized_scopes = sorted({s.strip() for s in scopes if s and s.strip()})
        if not normalized_scopes:
            raise GovernanceError("At least one non-empty scope is required.", status_code=400)
        with self._lock:
            short_id = secrets.token_hex(3)
            while any(r.key_prefix == f"{KEY_LIVE_PREFIX}{short_id}" for r in self._records.values()):
                short_id = secrets.token_hex(3)
            key_id = f"key_{short_id}_{secrets.token_hex(4)}"
            raw_key = f"{KEY_LIVE_PREFIX}{short_id}_{secrets.token_hex(16)}"
            created_at = _ensure_utc(self._now_fn()) or _utc_now()
            exp_utc = _ensure_utc(expires_at)
            record = _StoredScopedKey(
                key_id=key_id,
                tenant_id=tenant_id.strip(),
                name=name.strip(),
                key_prefix=raw_key[:KEY_PREFIX_LEN],
                secret_sha256=self._salted_sha256(key_id, raw_key),
                scopes=normalized_scopes,
                created_at=created_at,
                expires_at=exp_utc,
            )
            if self._store is not None:
                self._store.insert_scoped_key(
                    key_id=record.key_id,
                    tenant_id=record.tenant_id,
                    name=record.name,
                    key_prefix=record.key_prefix,
                    secret_sha256=record.secret_sha256,
                    scopes=record.scopes,
                    created_at=record.created_at.isoformat(),
                    expires_at=record.expires_at.isoformat() if record.expires_at else None,
                    revoked=record.revoked,
                    last_used_at=None,
                )
            self._records[key_id] = record
            return record.to_metadata(), raw_key

    def authenticate_key(
        self, raw_key: str, required_scope: Optional[str] = None
    ) -> KeyAuthenticationResult:
        if not raw_key or not _KEY_FORMAT_RE.fullmatch(raw_key):
            hmac.compare_digest(self._dummy_digest, self._dummy_digest)
            return KeyAuthenticationResult(
                valid=False, reason="Invalid API key format.", status_code=401
            )
        prefix = raw_key[:KEY_PREFIX_LEN]
        with self._lock:
            matched: Optional[_StoredScopedKey] = None
            for rec in self._records.values():
                if rec.key_prefix == prefix:
                    if hmac.compare_digest(
                        rec.secret_sha256, self._salted_sha256(rec.key_id, raw_key)
                    ):
                        matched = rec
                    break
            else:
                hmac.compare_digest(self._dummy_digest, self._salted_sha256("none", raw_key))
            if matched is None:
                return KeyAuthenticationResult(
                    valid=False, reason="Unrecognized API key.", status_code=401
                )
            base = {"key_id": matched.key_id, "tenant_id": matched.tenant_id}
            if matched.revoked:
                return KeyAuthenticationResult(
                    valid=False, reason="API key has been revoked.", status_code=401, **base
                )
            now = _ensure_utc(self._now_fn()) or _utc_now()
            if matched.expires_at is not None and now >= matched.expires_at:
                return KeyAuthenticationResult(
                    valid=False, reason="API key has expired.", status_code=401, **base
                )
            if (
                required_scope
                and required_scope not in matched.scopes
                and "*" not in matched.scopes
            ):
                return KeyAuthenticationResult(
                    valid=False,
                    scopes=list(matched.scopes),
                    reason=f"API key lacks required scope '{required_scope}'.",
                    status_code=403,
                    **base,
                )
            matched.last_used_at = now
            if self._store is not None:
                self._store.update_key_last_used(matched.key_id, now.isoformat())
            return KeyAuthenticationResult(
                valid=True,
                scopes=list(matched.scopes),
                reason="Authenticated.",
                status_code=200,
                **base,
            )

    def authenticate(
        self, raw_key: str, required_scope: Optional[str] = None
    ) -> KeyAuthenticationResult:
        """Alias for `authenticate_key`."""
        return self.authenticate_key(raw_key, required_scope=required_scope)

    def revoke_key(self, key_id: str) -> ScopedAPIKeyMetadata:
        with self._lock:
            rec = self._records.get(key_id)
            if rec is None:
                raise GovernanceError(f"API key '{key_id}' not found.", status_code=404)
            rec.revoked = True
            if self._store is not None:
                self._store.update_key_revoked(key_id, True)
            return rec.to_metadata()

    def list_keys(self, tenant_id: Optional[str] = None) -> List[ScopedAPIKeyMetadata]:
        with self._lock:
            items = [
                r.to_metadata()
                for r in self._records.values()
                if tenant_id is None or r.tenant_id == tenant_id
            ]
            return sorted(items, key=lambda k: k.created_at)


@dataclass
class _BucketState:
    request_tokens: float
    llm_tokens: float
    last_refill: float


class TokenBucketRateLimiter:
    """Thread-safe dual token-bucket limiter for RPM and TPM with injectable monotonic clock."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._lock = threading.Lock()
        self._buckets: Dict[str, _BucketState] = {}

    def consume(
        self,
        tenant_id: str,
        requests_per_minute: int,
        tokens_per_minute: int,
        estimated_tokens: int = 0,
    ) -> Tuple[bool, str, float]:
        if requests_per_minute <= 0 or tokens_per_minute <= 0 or estimated_tokens < 0:
            return False, "Invalid rate limit parameters.", 60.0
        if estimated_tokens > tokens_per_minute:
            return (
                False,
                f"Estimated tokens ({estimated_tokens}) exceed tenant TPM cap ({tokens_per_minute}).",
                60.0,
            )
        with self._lock:
            now = self._clock()
            req_rate, tok_rate = requests_per_minute / 60.0, tokens_per_minute / 60.0
            state = self._buckets.get(tenant_id)
            if state is None:
                state = _BucketState(float(requests_per_minute), float(tokens_per_minute), now)
                self._buckets[tenant_id] = state
            else:
                elapsed = max(0.0, now - state.last_refill)
                state.request_tokens = min(
                    float(requests_per_minute), state.request_tokens + elapsed * req_rate
                )
                state.llm_tokens = min(
                    float(tokens_per_minute), state.llm_tokens + elapsed * tok_rate
                )
                state.last_refill = now
            if state.request_tokens + 1e-9 < 1.0:
                return (
                    False,
                    f"Rate limit exceeded: {requests_per_minute} requests/minute.",
                    round((1.0 - state.request_tokens) / req_rate, 3),
                )
            if state.llm_tokens + 1e-9 < float(estimated_tokens):
                return (
                    False,
                    f"Token rate limit exceeded: {tokens_per_minute} tokens/minute.",
                    round((float(estimated_tokens) - state.llm_tokens) / tok_rate, 3),
                )
            state.request_tokens = max(0.0, state.request_tokens - 1.0)
            state.llm_tokens = max(0.0, state.llm_tokens - float(estimated_tokens))
            return True, "Within rate limits.", 0.0


class SpendSnapshot(BaseModel):
    tenant_id: str
    daily_spent_usd: float
    monthly_spent_usd: float
    total_tokens: int
    day_utc: str
    month_utc: str


class TenantSpendMeter:
    """Thread-safe daily and monthly USD spend tracker per tenant with optional SQLite persistence."""

    def __init__(
        self,
        now_fn: Callable[[], datetime] = _utc_now,
        store: Optional[SQLiteGovernanceStore] = None,
    ) -> None:
        self._now_fn = now_fn
        self._store = store
        self._lock = threading.RLock()
        self._state: Dict[str, SpendSnapshot] = {}
        if self._store is not None:
            self._hydrate_from_store_locked()

    def _hydrate_from_store_locked(self) -> None:
        assert self._store is not None
        now = _ensure_utc(self._now_fn()) or _utc_now()
        day_key, month_key = now.strftime("%Y-%m-%d"), now.strftime("%Y-%m")
        grouped: Dict[str, SpendSnapshot] = {}
        for ev in self._store.list_spend_events():
            snap = grouped.get(ev.tenant_id)
            if snap is None:
                snap = SpendSnapshot(
                    tenant_id=ev.tenant_id,
                    daily_spent_usd=0.0,
                    monthly_spent_usd=0.0,
                    total_tokens=0,
                    day_utc=day_key,
                    month_utc=month_key,
                )
                grouped[ev.tenant_id] = snap
            ev_dt = _parse_iso_utc(ev.recorded_at)
            snap.total_tokens += ev.tokens
            if ev_dt is not None:
                if ev_dt.strftime("%Y-%m") == month_key:
                    snap.monthly_spent_usd = round(snap.monthly_spent_usd + ev.amount_usd, 8)
                if ev_dt.strftime("%Y-%m-%d") == day_key:
                    snap.daily_spent_usd = round(snap.daily_spent_usd + ev.amount_usd, 8)
        self._state.update(grouped)

    def _rollover_locked(self, tenant_id: str) -> SpendSnapshot:
        now = _ensure_utc(self._now_fn()) or _utc_now()
        day_key, month_key = now.strftime("%Y-%m-%d"), now.strftime("%Y-%m")
        snap = self._state.get(tenant_id)
        if snap is None:
            snap = SpendSnapshot(
                tenant_id=tenant_id,
                daily_spent_usd=0.0,
                monthly_spent_usd=0.0,
                total_tokens=0,
                day_utc=day_key,
                month_utc=month_key,
            )
            self._state[tenant_id] = snap
        elif snap.month_utc != month_key:
            snap.monthly_spent_usd, snap.daily_spent_usd, snap.month_utc, snap.day_utc = (
                0.0,
                0.0,
                month_key,
                day_key,
            )
        elif snap.day_utc != day_key:
            snap.daily_spent_usd, snap.day_utc = 0.0, day_key
        return snap

    def record_spend(
        self,
        tenant_id: str,
        cost_usd: float,
        tokens: int = 0,
        model_id: str = "unspecified",
        provider: str = "unspecified",
    ) -> SpendSnapshot:
        if cost_usd < 0.0 or tokens < 0:
            raise GovernanceError(
                "Recorded cost_usd and tokens must be non-negative.", status_code=400
            )
        with self._lock:
            now = _ensure_utc(self._now_fn()) or _utc_now()
            snap = self._rollover_locked(tenant_id)
            if self._store is not None:
                self._store.append_spend_event(
                    tenant_id=tenant_id,
                    amount_usd=cost_usd,
                    model_id=model_id or "unspecified",
                    provider=provider or "unspecified",
                    recorded_at=now.isoformat(),
                    tokens=tokens,
                )
            snap.daily_spent_usd = round(snap.daily_spent_usd + cost_usd, 8)
            snap.monthly_spent_usd = round(snap.monthly_spent_usd + cost_usd, 8)
            snap.total_tokens += tokens
            return snap.model_copy(deep=True)

    def get_spend(self, tenant_id: str) -> SpendSnapshot:
        with self._lock:
            return self._rollover_locked(tenant_id).model_copy(deep=True)

    def check_budget(
        self,
        tenant_id: str,
        estimated_cost_usd: float,
        daily_limit_usd: float,
        monthly_limit_usd: float,
        is_paid_cloud: bool = True,
    ) -> Tuple[bool, Optional[str]]:
        if estimated_cost_usd < 0.0:
            return False, "Negative estimated cost is forbidden."
        if not is_paid_cloud and estimated_cost_usd == 0.0:
            return True, None
        with self._lock:
            snap = self._rollover_locked(tenant_id)
            proj_day = snap.daily_spent_usd + estimated_cost_usd
            proj_mon = snap.monthly_spent_usd + estimated_cost_usd
            if (proj_day > daily_limit_usd or (is_paid_cloud and snap.daily_spent_usd >= daily_limit_usd)) and (
                estimated_cost_usd > 0.0 or is_paid_cloud
            ):
                return False, f"Daily spend cap exceeded (${proj_day:.4f} / ${daily_limit_usd:.2f} USD)."
            if (proj_mon > monthly_limit_usd or (is_paid_cloud and snap.monthly_spent_usd >= monthly_limit_usd)) and (
                estimated_cost_usd > 0.0 or is_paid_cloud
            ):
                return False, f"Monthly spend cap exceeded (${proj_mon:.4f} / ${monthly_limit_usd:.2f} USD)."
            return True, None


class GovernanceAuditEntry(BaseModel):
    seq: int
    event_id: str = Field(default_factory=lambda: f"gov_evt_{secrets.token_hex(8)}")
    timestamp: str
    tenant_id: str
    action: str
    outcome: AuditOutcome
    reason: str
    model_id: Optional[str] = None
    provider: Optional[str] = None
    cost_usd: float = 0.0
    prompt_excerpt: Optional[str] = None
    prev_hash: str
    entry_hash: str

    @property
    def detail(self) -> str:
        return self.reason

    @property
    def event_hash(self) -> str:
        return self.entry_hash

    @property
    def redacted_prompt_preview(self) -> Optional[str]:
        return self.prompt_excerpt


class HashChainedGovernanceAuditLog:
    """Tamper-evident SHA-256 hash chain for governance evaluations and key lifecycle events."""

    def __init__(
        self,
        now_fn: Callable[[], datetime] = _utc_now,
        store: Optional[SQLiteGovernanceStore] = None,
    ) -> None:
        self._now_fn = now_fn
        self._store = store
        self._lock = threading.RLock()
        self._entries: List[GovernanceAuditEntry] = []
        if self._store is not None:
            self._hydrate_from_store_locked()

    def _hydrate_from_store_locked(self) -> None:
        assert self._store is not None
        for row in self._store.list_audit_events():
            outcome_val: AuditOutcome = (
                row.outcome  # type: ignore[assignment]
                if row.outcome in ("allow", "deny", "downgrade_opencore")
                else "deny"
            )
            self._entries.append(
                GovernanceAuditEntry(
                    seq=row.seq,
                    event_id=row.event_id,
                    timestamp=row.timestamp,
                    tenant_id=row.tenant_id,
                    action=row.action,
                    outcome=outcome_val,
                    reason=row.detail,
                    model_id=row.model_id,
                    provider=row.provider,
                    cost_usd=row.cost_usd,
                    prompt_excerpt=row.redacted_prompt_preview,
                    prev_hash=row.prev_hash,
                    entry_hash=row.event_hash,
                )
            )

    @property
    def chain_head(self) -> str:
        with self._lock:
            return self._entries[-1].entry_hash if self._entries else GENESIS_GOVERNANCE_HASH

    @staticmethod
    def _compute_hash(
        seq: int,
        event_id: str,
        timestamp: str,
        tenant_id: str,
        action: str,
        outcome: str,
        reason: str,
        prompt_excerpt: Optional[str],
        prev_hash: str,
        model_id: Optional[str] = None,
        provider: Optional[str] = None,
        cost_usd: float = 0.0,
    ) -> str:
        return compute_audit_event_hash(
            seq=seq,
            event_id=event_id,
            timestamp=timestamp,
            tenant_id=tenant_id,
            action=action,
            outcome=outcome,
            model_id=model_id,
            provider=provider,
            cost_usd=cost_usd,
            detail=reason,
            redacted_prompt_preview=prompt_excerpt,
            prev_hash=prev_hash,
        )

    def append(
        self,
        tenant_id: str,
        action: str,
        outcome: AuditOutcome,
        reason: str,
        prompt_preview: Optional[str] = None,
        log_redacted_prompts: bool = False,
        *,
        model_id: Optional[str] = None,
        provider: Optional[str] = None,
        cost_usd: float = 0.0,
    ) -> GovernanceAuditEntry:
        excerpt: Optional[str] = None
        if log_redacted_prompts and prompt_preview is not None:
            clean_prompt, _ = redact_text(prompt_preview)
            clean_prompt = _KEY_INLINE_RE.sub("[REDACTED_KEELWAY_KEY]", clean_prompt)
            excerpt = clean_prompt[:512]

        safe_reason, _ = DLPScanner.redact(reason)
        safe_reason = _KEY_INLINE_RE.sub("[REDACTED_KEELWAY_KEY]", safe_reason)

        with self._lock:
            seq = len(self._entries) + 1
            event_id = f"gov_evt_{seq:08d}_{secrets.token_hex(6)}"
            prev_hash = self._entries[-1].entry_hash if self._entries else GENESIS_GOVERNANCE_HASH
            now_dt = _ensure_utc(self._now_fn()) or _utc_now()
            ts = now_dt.isoformat()
            normalized_cost = round(float(cost_usd), 8)
            entry_hash = self._compute_hash(
                seq=seq,
                event_id=event_id,
                timestamp=ts,
                tenant_id=tenant_id,
                action=action,
                outcome=outcome,
                reason=safe_reason,
                prompt_excerpt=excerpt,
                prev_hash=prev_hash,
                model_id=model_id,
                provider=provider,
                cost_usd=normalized_cost,
            )
            if self._store is not None:
                self._store.append_audit_event(
                    seq=seq,
                    event_id=event_id,
                    timestamp=ts,
                    tenant_id=tenant_id,
                    action=action,
                    outcome=outcome,
                    model_id=model_id,
                    provider=provider,
                    cost_usd=normalized_cost,
                    detail=safe_reason,
                    redacted_prompt_preview=excerpt,
                    prev_hash=prev_hash,
                    event_hash=entry_hash,
                )
            entry = GovernanceAuditEntry(
                seq=seq,
                event_id=event_id,
                timestamp=ts,
                tenant_id=tenant_id,
                action=action,
                outcome=outcome,
                reason=safe_reason,
                model_id=model_id,
                provider=provider,
                cost_usd=normalized_cost,
                prompt_excerpt=excerpt,
                prev_hash=prev_hash,
                entry_hash=entry_hash,
            )
            self._entries.append(entry)
            return entry.model_copy(deep=True)

    def verify_integrity(self) -> AuditChainStatus:
        """Verify in-memory chain AND persisted SQLite chain when SQLite-backed."""
        with self._lock:
            prev = GENESIS_GOVERNANCE_HASH
            for idx, e in enumerate(self._entries, start=1):
                expected = self._compute_hash(
                    seq=e.seq,
                    event_id=e.event_id,
                    timestamp=e.timestamp,
                    tenant_id=e.tenant_id,
                    action=e.action,
                    outcome=e.outcome,
                    reason=e.reason,
                    prompt_excerpt=e.prompt_excerpt,
                    prev_hash=prev,
                    model_id=e.model_id,
                    provider=e.provider,
                    cost_usd=e.cost_usd,
                )
                if e.seq != idx or e.prev_hash != prev or e.entry_hash != expected:
                    return AuditChainStatus(False, idx)
                prev = e.entry_hash

            if self._store is not None:
                db_valid, seq_or_count, _err = self._store.verify_persisted_chain()
                if not db_valid:
                    return AuditChainStatus(False, seq_or_count)
                if seq_or_count != len(self._entries):
                    return AuditChainStatus(False, min(seq_or_count, len(self._entries)) + 1)
                if prev != self._store.get_chain_head():
                    return AuditChainStatus(False, max(1, len(self._entries)))

            return AuditChainStatus(True, None)

    def count_entries(self) -> int:
        with self._lock:
            return len(self._entries)

    def list_entries(
        self, tenant_id: Optional[str] = None, limit: int = 200
    ) -> List[GovernanceAuditEntry]:
        with self._lock:
            items = [
                e.model_copy(deep=True)
                for e in self._entries
                if tenant_id is None or e.tenant_id == tenant_id
            ]
            return items[-limit:] if limit > 0 else items


class GovernanceDecision(BaseModel):
    allowed: bool
    action: str
    effective_model: Optional[str] = None
    effective_provider: Optional[str] = None
    reason: str
    status_code: int
    retry_after_seconds: float = 0.0


class TenantGovernanceEngine:
    """Unified multi-tenant policy controller enforcing residency, rate limits, spend caps, and audit.

    Supports both zero-latency in-memory operation (`db_path=None` and `store=None`) and crash-safe
    SQLite WAL persistence (`db_path=...` or `store=SQLiteGovernanceStore(...)`).
    """

    def __init__(
        self,
        db_path: Optional[Path | str] = None,
        clock: Callable[[], float] = time.monotonic,
        now_fn: Callable[[], datetime] = _utc_now,
        seed_default_tenant: bool = True,
        store: Optional[SQLiteGovernanceStore] = None,
    ) -> None:
        self._lock = threading.RLock()
        self._now_fn = now_fn
        self._owns_store = store is None and db_path is not None
        self._store: Optional[SQLiteGovernanceStore] = (
            store if store is not None else (SQLiteGovernanceStore(db_path) if db_path is not None else None)
        )
        self._tenants: Dict[str, TenantPolicy] = {}

        if self._store is not None:
            for _tid, policy_json, _updated_at in self._store.list_policies():
                pol = TenantPolicy.model_validate_json(policy_json)
                self._tenants[pol.tenant_id] = pol

        self.key_manager = ScopedAPIKeyManager(now_fn=now_fn, store=self._store)
        self.rate_limiter = TokenBucketRateLimiter(clock=clock)
        self.spend_meter = TenantSpendMeter(now_fn=now_fn, store=self._store)
        self.audit_log = HashChainedGovernanceAuditLog(now_fn=now_fn, store=self._store)

        if seed_default_tenant and "default" not in self._tenants:
            default_policy = TenantPolicy(
                tenant_id="default",
                name="Default Keelway Workspace",
                allowed_categories=["open_weight", "closed_proprietary"],
                allowed_providers=[
                    "local",
                    "gemini",
                    "google",
                    "openai",
                    "anthropic",
                    "ollama",
                    "vllm",
                ],
                residency_zone=DataResidencyZone.GLOBAL,
            )
            self._tenants["default"] = default_policy
            if self._store is not None:
                now_iso = (_ensure_utc(self._now_fn()) or _utc_now()).isoformat()
                self._store.upsert_policy("default", default_policy.model_dump_json(), now_iso)

    @property
    def is_persistent(self) -> bool:
        return self._store is not None

    @property
    def store(self) -> Optional[SQLiteGovernanceStore]:
        return self._store

    @property
    def chain_head(self) -> str:
        return self.audit_log.chain_head

    def close(self) -> None:
        """Close the owned SQLite governance store if active."""
        if self._store is not None and self._owns_store:
            self._store.close()

    def __enter__(self) -> TenantGovernanceEngine:
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()

    def _persist_policy_locked(self, policy: TenantPolicy) -> None:
        if self._store is not None:
            now_iso = (_ensure_utc(self._now_fn()) or _utc_now()).isoformat()
            self._store.upsert_policy(policy.tenant_id, policy.model_dump_json(), now_iso)

    def create_tenant(self, policy: TenantPolicy) -> TenantPolicy:
        with self._lock:
            if policy.tenant_id in self._tenants:
                raise GovernanceError(
                    f"Tenant '{policy.tenant_id}' already exists.",
                    status_code=409,
                    tenant_id=policy.tenant_id,
                )
            stored = policy.model_copy(deep=True)
            self._persist_policy_locked(stored)
            self._tenants[stored.tenant_id] = stored
        self.audit_log.append(
            stored.tenant_id, "tenant.create", "allow", f"Created tenant '{stored.name}'."
        )
        return stored.model_copy(deep=True)

    def upsert_policy(self, policy: TenantPolicy) -> TenantPolicy:
        """Create or atomically replace a tenant governance policy."""
        with self._lock:
            is_update = policy.tenant_id in self._tenants
            stored = policy.model_copy(deep=True)
            self._persist_policy_locked(stored)
            self._tenants[stored.tenant_id] = stored
        action = "tenant.update" if is_update else "tenant.create"
        detail = (
            "Updated tenant governance policy."
            if is_update
            else f"Created tenant '{stored.name}'."
        )
        self.audit_log.append(stored.tenant_id, action, "allow", detail)
        return stored.model_copy(deep=True)

    def get_tenant(self, tenant_id: str) -> Optional[TenantPolicy]:
        with self._lock:
            pol = self._tenants.get(tenant_id)
            return pol.model_copy(deep=True) if pol else None

    def list_tenants(self) -> List[TenantPolicy]:
        with self._lock:
            return [p.model_copy(deep=True) for p in self._tenants.values()]

    def update_tenant(self, tenant_id: str, updates: Dict[str, Any]) -> TenantPolicy:
        with self._lock:
            existing = self._tenants.get(tenant_id)
            if existing is None:
                raise GovernanceError(
                    f"Tenant '{tenant_id}' not found.", status_code=404, tenant_id=tenant_id
                )
            merged = existing.model_dump()
            for k, v in updates.items():
                if v is not None and k != "tenant_id":
                    merged[k] = v
            updated = TenantPolicy.model_validate(merged)
            self._persist_policy_locked(updated)
            self._tenants[tenant_id] = updated
        self.audit_log.append(
            tenant_id, "tenant.update", "allow", "Updated tenant governance policy."
        )
        return updated.model_copy(deep=True)

    def issue_key(
        self,
        tenant_id: str,
        name: str,
        scopes: List[str],
        expires_at: Optional[datetime] = None,
    ) -> Tuple[ScopedAPIKeyMetadata, str]:
        if self.get_tenant(tenant_id) is None:
            raise GovernanceError(
                f"Tenant '{tenant_id}' not found.", status_code=404, tenant_id=tenant_id
            )
        meta, raw_key = self.key_manager.issue_key(
            tenant_id=tenant_id, name=name, scopes=scopes, expires_at=expires_at
        )
        self.audit_log.append(
            tenant_id,
            "key.issue",
            "allow",
            f"Issued scoped key '{meta.key_id}' ({meta.key_prefix}).",
        )
        return meta, raw_key

    def revoke_key(self, key_id: str) -> ScopedAPIKeyMetadata:
        meta = self.key_manager.revoke_key(key_id)
        self.audit_log.append(
            meta.tenant_id, "key.revoke", "allow", f"Revoked scoped key '{meta.key_id}'."
        )
        return meta

    def verify_key(
        self, raw_key: str, required_scope: Optional[str] = None
    ) -> KeyAuthenticationResult:
        res = self.key_manager.authenticate_key(raw_key, required_scope=required_scope)
        if res.valid and res.tenant_id and self.get_tenant(res.tenant_id) is None:
            res = KeyAuthenticationResult(
                valid=False,
                key_id=res.key_id,
                tenant_id=res.tenant_id,
                reason="Key belongs to an unregistered tenant.",
                status_code=403,
            )
        self.audit_log.append(
            res.tenant_id or "unknown",
            "key.verify",
            "allow" if res.valid else "deny",
            res.reason,
        )
        return res

    def authenticate(
        self, raw_key: str, required_scope: Optional[str] = None
    ) -> KeyAuthenticationResult:
        """Authenticate a `kw_live_*` scoped API key, updating `last_used_at` and audit chain."""
        return self.verify_key(raw_key, required_scope=required_scope)

    def record_spend(
        self,
        tenant_id: str,
        cost_usd: float,
        tokens: int = 0,
        model_id: str = "unspecified",
        provider: str = "unspecified",
    ) -> SpendSnapshot:
        if self.get_tenant(tenant_id) is None:
            raise GovernanceError(
                f"Tenant '{tenant_id}' not found.", status_code=404, tenant_id=tenant_id
            )
        snap = self.spend_meter.record_spend(
            tenant_id=tenant_id,
            cost_usd=cost_usd,
            tokens=tokens,
            model_id=model_id,
            provider=provider,
        )
        self.audit_log.append(
            tenant_id,
            "spend.record",
            "allow",
            f"Recorded ${cost_usd:.4f} USD ({tokens} tokens).",
            model_id=model_id,
            provider=provider,
            cost_usd=cost_usd,
        )
        return snap

    def evaluate_request(
        self,
        tenant_id: str,
        requested_model: str,
        provider: str,
        category: str,
        estimated_cost_usd: float = 0.0,
        estimated_tokens: int = 0,
        prompt_preview: Optional[str] = None,
        *,
        forbid_open_weight: bool = False,
        raise_on_deny: bool = False,
    ) -> GovernanceDecision:
        policy = self.get_tenant(tenant_id)
        if policy is None:
            reason = f"Unknown tenant '{tenant_id}' (fail-closed)."
            self.audit_log.append(
                tenant_id or "unknown",
                "request.evaluate",
                "deny",
                reason,
                model_id=requested_model or None,
                provider=provider or None,
            )
            if raise_on_deny:
                raise GovernanceError(reason, status_code=403, tenant_id=tenant_id)
            return GovernanceDecision(allowed=False, action="deny", reason=reason, status_code=403)

        prov, cat = (provider or "").strip().lower(), (category or "").strip().lower()
        log_prompts = policy.log_redacted_prompts

        def _deny(
            msg: str, code: int, retry_s: float = 0.0, budget_err: bool = False
        ) -> GovernanceDecision:
            self.audit_log.append(
                tenant_id,
                "request.evaluate",
                "deny",
                msg,
                prompt_preview,
                log_prompts,
                model_id=requested_model or None,
                provider=prov or None,
                cost_usd=0.0,
            )
            if raise_on_deny:
                if budget_err:
                    raise BudgetExceededGovernanceError(msg, tenant_id=tenant_id)
                raise GovernanceError(msg, status_code=code, tenant_id=tenant_id)
            return GovernanceDecision(
                allowed=False,
                action="deny",
                reason=msg,
                status_code=code,
                retry_after_seconds=retry_s,
            )

        if (
            not requested_model
            or not prov
            or not cat
            or estimated_cost_usd < 0.0
            or estimated_tokens < 0
        ):
            return _deny("Malformed or incomplete model governance parameters.", 403)
        if policy.residency_zone == DataResidencyZone.LOCAL_ONLY and prov != "local":
            return _deny(
                f"Data residency 'local_only' forbids non-local provider '{prov}'.", 403
            )
        if (
            policy.residency_zone
            in (DataResidencyZone.AFRICA_SOVEREIGN, DataResidencyZone.EU_SOVEREIGN)
            and prov not in _SOVEREIGN_LOCAL_PROVIDERS
        ):
            return _deny(
                f"Residency '{policy.residency_zone.value}' forbids non-sovereign cloud provider '{prov}'.",
                403,
            )
        if prov not in policy.allowed_providers:
            return _deny(f"Provider '{prov}' is not permitted for tenant '{tenant_id}'.", 403)
        if cat not in policy.allowed_categories:
            return _deny(f"Model category '{cat}' is not permitted for tenant '{tenant_id}'.", 403)

        within_rate, rate_reason, retry_after = self.rate_limiter.consume(
            tenant_id, policy.requests_per_minute, policy.tokens_per_minute, estimated_tokens
        )
        if not within_rate:
            return _deny(rate_reason, 429, retry_s=retry_after)

        is_paid_cloud = prov not in _SOVEREIGN_LOCAL_PROVIDERS or cat == "closed_proprietary"
        within_budget, budget_reason = self.spend_meter.check_budget(
            tenant_id,
            estimated_cost_usd,
            policy.daily_spend_limit_usd,
            policy.monthly_spend_limit_usd,
            is_paid_cloud,
        )
        if not within_budget:
            if (
                policy.fallback_to_opencore_on_budget_exceeded
                and not forbid_open_weight
                and "open_weight" in policy.allowed_categories
                and OPENCORE_FALLBACK_PROVIDER in policy.allowed_providers
            ):
                reason = (
                    f"{budget_reason} Automatically downgraded to "
                    f"'{OPENCORE_FALLBACK_MODEL}' ({OPENCORE_FALLBACK_PROVIDER}) at $0.00."
                )
                self.audit_log.append(
                    tenant_id,
                    "request.evaluate",
                    "downgrade_opencore",
                    reason,
                    prompt_preview,
                    log_prompts,
                    model_id=OPENCORE_FALLBACK_MODEL,
                    provider=OPENCORE_FALLBACK_PROVIDER,
                    cost_usd=0.0,
                )
                return GovernanceDecision(
                    allowed=True,
                    action="downgrade_opencore",
                    effective_model=OPENCORE_FALLBACK_MODEL,
                    effective_provider=OPENCORE_FALLBACK_PROVIDER,
                    reason=reason,
                    status_code=200,
                )
            return _deny(budget_reason or "Tenant spend budget exceeded.", 402, budget_err=True)

        ok_reason = f"Permitted '{requested_model}' via provider '{prov}'."
        self.audit_log.append(
            tenant_id,
            "request.evaluate",
            "allow",
            ok_reason,
            prompt_preview,
            log_prompts,
            model_id=requested_model,
            provider=prov,
            cost_usd=estimated_cost_usd,
        )
        return GovernanceDecision(
            allowed=True,
            action="allow",
            effective_model=requested_model,
            effective_provider=prov,
            reason=ok_reason,
            status_code=200,
        )

    def enforce_request(
        self,
        tenant_id: str,
        requested_model: str,
        provider: str,
        category: str,
        estimated_cost_usd: float = 0.0,
        estimated_tokens: int = 0,
        prompt_preview: Optional[str] = None,
        *,
        forbid_open_weight: bool = False,
    ) -> GovernanceDecision:
        return self.evaluate_request(
            tenant_id,
            requested_model,
            provider,
            category,
            estimated_cost_usd,
            estimated_tokens,
            prompt_preview,
            forbid_open_weight=forbid_open_weight,
            raise_on_deny=True,
        )

    def verify_audit_chain(self) -> AuditChainStatus:
        """Verify both in-memory audit chain and persisted SQLite table integrity."""
        return self.audit_log.verify_integrity()

    def get_persistence_telemetry(self) -> Dict[str, Any]:
        """Return safe persistence and cryptographic audit-chain telemetry (no paths or secrets)."""
        chain_status = self.verify_audit_chain()
        return {
            "persistent": self.is_persistent,
            "backend": "sqlite_wal" if self.is_persistent else "memory",
            "tenants_count": len(self.list_tenants()),
            "keys_count": len(self.key_manager.list_keys()),
            "audit_events_count": self.audit_log.count_entries(),
            "chain_verified": bool(chain_status.valid),
            "chain_head": self.audit_log.chain_head,
        }


# Canonical alias so both `TenantGovernanceController` and `TenantGovernanceEngine` refer to the same class
TenantGovernanceController = TenantGovernanceEngine

_singleton_lock = threading.RLock()
_initial_db_path = (os.environ.get("KEELWAY_GOVERNANCE_DB_PATH") or "").strip() or None
tenant_governance = TenantGovernanceController(db_path=_initial_db_path)
_active_singleton: TenantGovernanceController = tenant_governance
_active_singleton_db_path: Optional[str] = _initial_db_path


def get_governance_controller() -> TenantGovernanceController:
    """Return process-wide governance controller, honoring `KEELWAY_GOVERNANCE_DB_PATH` if configured."""
    global _active_singleton, _active_singleton_db_path
    with _singleton_lock:
        configured_path = (os.environ.get("KEELWAY_GOVERNANCE_DB_PATH") or "").strip() or None
        if configured_path != _active_singleton_db_path:
            if _active_singleton is not tenant_governance:
                _active_singleton.close()
            if configured_path is None:
                _active_singleton = tenant_governance
            else:
                _active_singleton = TenantGovernanceController(db_path=configured_path)
            _active_singleton_db_path = configured_path
        return _active_singleton
