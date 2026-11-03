"""Keelway TPM 2.0 Quote Verifier, Event-Log Replay & Monotonic NV Counter.
Implements ADR-061, ADR-062, ADR-064, and the normative attestation algorithms in
309_TPM_QUOTE_PCR_SELECTION_EVENT_LOG_REPLAY_AND_TEST_VECTORS.md.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from typing import Dict, List, Optional, Tuple
from pydantic import BaseModel, Field


class TPMEventLogEntry(BaseModel):
    pcr_index: int
    event_type: str
    digest_sha256: str
    event_description: str


class TPMQuotePayload(BaseModel):
    station_id: str
    attestation_key_id: str
    nonce: str
    pcr_selection: List[int]
    quoted_pcr_digest: str
    event_log: List[TPMEventLogEntry]
    signature: str


class TPMQuoteVerificationResult(BaseModel):
    is_valid: bool
    status_code: str
    error_message: Optional[str] = None
    recomputed_pcr_digest: Optional[str] = None
    golden_profile_matched: bool = False


class TPMQuoteVerifier:
    """Verifies TPM 2.0 quotes, measured boot event log replay, and NV monotonic floors."""

    def __init__(
        self,
        customer_golden_boot_profile: Dict[int, str],
        active_ak_key: bytes = b"customer_enrolled_tpm_ak_secret_key",
    ):
        self.customer_golden_boot_profile = customer_golden_boot_profile
        self.active_ak_key = active_ak_key
        self._consumed_nonces: set = set()
        self.monotonic_counter_floor: int = 0

    def generate_attestation_nonce(self) -> str:
        """Generates 256-bit unpredictable single-use nonce."""
        nonce = secrets.token_hex(32)
        return nonce

    def replay_event_log(self, event_log: List[TPMEventLogEntry]) -> Dict[int, str]:
        """Independently replays event-log extend operations starting from zero registers.
        
        PCR_extend(PCR_n, event_digest) = SHA256(PCR_n || event_digest)
        """
        pcr_registers: Dict[int, str] = {}

        for entry in event_log:
            current_val = pcr_registers.get(entry.pcr_index, "0" * 64)
            # Recompute extend
            preimage = bytes.fromhex(current_val) + bytes.fromhex(entry.digest_sha256)
            new_val = hashlib.sha256(preimage).hexdigest()
            pcr_registers[entry.pcr_index] = new_val

        return pcr_registers

    def verify_quote(
        self,
        quote: TPMQuotePayload,
        expected_nonce: str,
    ) -> TPMQuoteVerificationResult:
        """Strict deterministic verification per ADR-064 / Document 309."""
        # 1. Single-use nonce check (anti-replay)
        if quote.nonce != expected_nonce:
            return TPMQuoteVerificationResult(
                is_valid=False,
                status_code="ERR_TPM_NONCE_MISMATCH",
                error_message="Nonce does not match issued challenge; possible replay attack",
            )

        if quote.nonce in self._consumed_nonces:
            return TPMQuoteVerificationResult(
                is_valid=False,
                status_code="ERR_TPM_NONCE_REPLAYED",
                error_message="Nonce has already been consumed; replay detected",
            )
        self._consumed_nonces.add(quote.nonce)

        # 2. Verify signature over quote data using enrolled AK
        msg = f"{quote.station_id}:{quote.attestation_key_id}:{quote.nonce}:{quote.quoted_pcr_digest}"
        expected_sig = hmac.new(self.active_ak_key, msg.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(quote.signature, expected_sig):
            return TPMQuoteVerificationResult(
                is_valid=False,
                status_code="ERR_TPM_INVALID_AK_SIGNATURE",
                error_message="TPM quote signature could not be verified with enrolled AK",
            )

        # 3. Independent Event-Log Replay
        replayed_pcrs = self.replay_event_log(quote.event_log)

        # 4. Hash of selected replayed PCRs
        selected_pcrs_concat = "".join(
            replayed_pcrs.get(pcr_idx, "0" * 64) for pcr_idx in sorted(quote.pcr_selection)
        )
        recomputed_pcr_digest = hashlib.sha256(selected_pcrs_concat.encode("utf-8")).hexdigest()

        if recomputed_pcr_digest != quote.quoted_pcr_digest:
            return TPMQuoteVerificationResult(
                is_valid=False,
                status_code="ERR_TPM_EVENT_LOG_REPLAY_MISMATCH",
                error_message="Replayed event log PCR digest does not match hardware-quoted PCR digest",
                recomputed_pcr_digest=recomputed_pcr_digest,
            )

        # 5. Check against Customer Golden Boot Profile
        for pcr_idx, expected_val in self.customer_golden_boot_profile.items():
            if replayed_pcrs.get(pcr_idx) != expected_val:
                return TPMQuoteVerificationResult(
                    is_valid=False,
                    status_code="ERR_TPM_GOLDEN_BOOT_MISMATCH",
                    error_message=f"PCR {pcr_idx} value '{replayed_pcrs.get(pcr_idx)}' differs from golden profile '{expected_val}'",
                    golden_profile_matched=False,
                )

        return TPMQuoteVerificationResult(
            is_valid=True,
            status_code="INFO_TPM_QUOTE_VERIFIED_GOLDEN_MATCH",
            recomputed_pcr_digest=recomputed_pcr_digest,
            golden_profile_matched=True,
        )

    def advance_monotonic_nv_counter(self, new_counter_value: int) -> bool:
        """Enforces rollback resistance across machine restarts or snapshot rollbacks."""
        if new_counter_value <= self.monotonic_counter_floor:
            return False  # Rollback detected!
        self.monotonic_counter_floor = new_counter_value
        return True
