"""
Keelway Sovereign Economic Ledger & Offline Token Budget.
Provides zero-dollar offline cost tracking, token quota governance,
and prepaid voucher redemption for regions with USD card or banking restrictions.
"""

import hashlib
import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.storage.models import MemoryRecord, utc_now


class SovereignLedger:
    """Tracks token consumption locally without external payment gatekeepers."""

    VOUCHER_SALT = "KEELWAY_SOVEREIGN_OFFLINE_SALT_2026"

    @classmethod
    def generate_offline_voucher(cls, code: str, token_quota: int) -> str:
        """Generates a cryptographic signature verifying an offline prepaid voucher."""
        raw = f"{code}:{token_quota}:{cls.VOUCHER_SALT}".encode("utf-8")
        return hashlib.sha256(raw).hexdigest()[:16].upper()

    @classmethod
    def verify_voucher(cls, code: str, token_quota: int, signature: str) -> bool:
        expected = cls.generate_offline_voucher(code, token_quota)
        return expected == signature.strip().upper()

    @staticmethod
    def calculate_cost_savings(tokens: int, cloud_rate_per_million: float = 3.00) -> Dict[str, Any]:
        """Calculates exact dollar savings from running on sovereign edge hardware vs cloud APIs."""
        estimated_cloud_cost = (tokens / 1_000_000.0) * cloud_rate_per_million
        return {
            "tokens_consumed": tokens,
            "actual_cost_usd": 0.00,
            "estimated_cloud_cost_usd": estimated_cloud_cost,
            "dollars_saved_usd": estimated_cloud_cost,
            "economic_sovereignty_ratio": 1.0,  # 100% saved
        }
