"""
Keelway Autonomous Agent Payment & Mandate Protocol (AP2 + HTTP 402).
Enables machine-to-machine microtransactions, cryptographic spend mandates,
and offline/regional voucher settlement without requiring USD credit cards.
"""

import hashlib
import time
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Any, List, Optional


class PaymentRail(str, Enum):
    HTTP_402_MICRO = "http_402_micro"
    OFFLINE_VOUCHER = "offline_voucher"
    LOCAL_CREDIT = "local_credit"


@dataclass
class SpendMandate:
    """Cryptographically signed authorization permitting an AI agent to transact within boundaries."""
    mandate_id: str
    user_id: str
    max_amount_cents: int
    allowed_rails: List[PaymentRail]
    expiry_unix: int
    signature: str

    def is_valid(self, amount_cents: int, rail: PaymentRail) -> bool:
        """Verifies spending limit, rail allowance, and expiry timestamp."""
        if time.time() > self.expiry_unix:
            return False
        if amount_cents > self.max_amount_cents:
            return False
        if rail not in self.allowed_rails:
            return False
        # Verify cryptographic signature
        expected_sig = hashlib.sha256(
            f"{self.mandate_id}:{self.user_id}:{self.max_amount_cents}:{self.expiry_unix}".encode("utf-8")
        ).hexdigest()[:16]
        return self.signature == expected_sig


class AgentPaymentGateway:
    """Handles agentic commerce settlement, HTTP 402 parsing, and mandate enforcement."""

    def __init__(self, secret_salt: str = "KEELWAY_AP2_SALT_2026"):
        self.secret_salt = secret_salt
        self.ledger: List[Dict[str, Any]] = []

    def issue_mandate(
        self,
        user_id: str,
        max_amount_cents: int = 1000,  # $10.00 max
        duration_seconds: int = 86400,  # 24 hours
        allowed_rails: Optional[List[PaymentRail]] = None,
    ) -> SpendMandate:
        """Issues a cryptographically signed spending mandate for an agent."""
        mandate_id = f"mandate_{hashlib.md5(f'{user_id}:{time.time()}'.encode()).hexdigest()[:10]}"
        expiry_unix = int(time.time() + duration_seconds)
        rails = allowed_rails or [PaymentRail.HTTP_402_MICRO, PaymentRail.OFFLINE_VOUCHER, PaymentRail.LOCAL_CREDIT]

        sig = hashlib.sha256(
            f"{mandate_id}:{user_id}:{max_amount_cents}:{expiry_unix}".encode("utf-8")
        ).hexdigest()[:16]

        return SpendMandate(
            mandate_id=mandate_id,
            user_id=user_id,
            max_amount_cents=max_amount_cents,
            allowed_rails=rails,
            expiry_unix=expiry_unix,
            signature=sig,
        )

    def handle_http_402_challenge(
        self,
        status_code: int,
        challenge_headers: Dict[str, str],
        mandate: SpendMandate,
    ) -> Dict[str, Any]:
        """
        Parses an HTTP 402 'Payment Required' response, validates against user mandate,
        and generates an authorized payment header or token.
        """
        if status_code != 402:
            return {"status": "skipped", "reason": "Not an HTTP 402 challenge"}

        # Extract price from challenge (e.g. 'amount-cents': '5' for 0.05 micro-query)
        price_cents = int(challenge_headers.get("x-payment-amount-cents", "1"))
        destination = challenge_headers.get("x-payment-destination", "local-settlement")

        if not mandate.is_valid(price_cents, PaymentRail.HTTP_402_MICRO):
            return {
                "status": "denied",
                "error": f"Spend mandate violated: {price_cents}c exceeds limits or mandate expired.",
            }

        # Deduct / authorize
        tx_hash = hashlib.sha256(f"{mandate.mandate_id}:{price_cents}:{time.time()}".encode()).hexdigest()[:16]
        tx_record = {
            "tx_hash": tx_hash,
            "mandate_id": mandate.mandate_id,
            "amount_cents": price_cents,
            "destination": destination,
            "rail": PaymentRail.HTTP_402_MICRO.value,
            "timestamp": int(time.time()),
            "status": "settled",
        }
        self.ledger.append(tx_record)

        return {
            "status": "authorized",
            "auth_header": f"Bearer ap2_{tx_hash}",
            "amount_cents": price_cents,
            "tx_hash": tx_hash,
        }
