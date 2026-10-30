import pytest
from core.api.schemas import Provider, CompletionResponseSchema, CompletionRequestSchema, MessageSchema
from core.security.airgap import AirGapEnforcer, AirGapViolationError
from core.security.style import StyleEngine, VoiceStyle
from core.storage.ledger import SovereignLedger
from core.models.gateway import ModelGateway
from unittest.mock import AsyncMock


def test_airgap_enforcer_blocks_cloud_providers():
    enforcer = AirGapEnforcer(enabled=True)
    # Local is allowed
    enforcer.validate_provider(Provider.LOCAL)

    # Cloud is blocked
    with pytest.raises(AirGapViolationError):
        enforcer.validate_provider(Provider.ANTHROPIC)

    with pytest.raises(AirGapViolationError):
        enforcer.validate_provider(Provider.OPENAI)


def test_airgap_attestation_hash():
    enforcer = AirGapEnforcer(enabled=True)
    attestation = enforcer.generate_attestation(
        task_id="task-99",
        model_name="qwen3.5:latest",
        tokens_processed=450,
    )
    assert attestation["air_gapped"] is True
    assert attestation["execution_target"] == "127.0.0.1 (Loopback)"
    assert len(attestation["attestation_sha256"]) == 64  # Valid SHA-256


def test_style_engine_de_slop():
    slop_input = (
        "In conclusion, this project seamlessly integrates with modern stacks. "
        "It is crucial to note that it stands as a testament to sovereign engineering, "
        "allowing teams to delve into high performance."
    )
    cleaned, removed = StyleEngine.de_slop(slop_input)
    assert "testament" not in cleaned
    assert "delve" not in cleaned
    assert "In conclusion" not in cleaned
    assert len(removed) >= 3


def test_sovereign_ledger_vouchers_and_savings():
    voucher_code = "KORA-AFRICA-2026-TOKEN"
    sig = SovereignLedger.generate_offline_voucher(voucher_code, 500_000)
    assert SovereignLedger.verify_voucher(voucher_code, 500_000, sig) is True
    assert SovereignLedger.verify_voucher(voucher_code, 100_000, sig) is False

    savings = SovereignLedger.calculate_cost_savings(tokens=2_000_000, cloud_rate_per_million=3.00)
    assert savings["actual_cost_usd"] == 0.00
    assert savings["dollars_saved_usd"] == 6.00
