"""Tests for Keelway Model Gateway (FR-04, FR-10).
Validates local and mock provider routing, capabilities declaration, and token ceilings.
"""
import pytest

from keelway.models.gateway import BudgetExceededError, ModelGateway, ProviderKind


def test_model_gateway_deterministic_mock():
    gateway = ModelGateway(provider=ProviderKind.DETERMINISTIC_MOCK)
    res = gateway.generate_patch_proposal(
        task_prompt="Create auth middleware",
        file_tree=["app.py"],
        token_ceiling=5000,
        tokens_used_so_far=100,
    )
    assert res["file_path"] == "governed_module.py"
    assert "keelway_verified" in res["content"]
    assert res["tokens_consumed"] == 150
    assert res["cost_cents"] >= 1
    assert res["provider"] == "deterministic_mock"


def test_model_gateway_enforces_token_budget_ceiling():
    gateway = ModelGateway(provider=ProviderKind.DETERMINISTIC_MOCK)
    
    # Trying to generate when token ceiling is already reached
    with pytest.raises(BudgetExceededError) as exc_info:
        gateway.generate_patch_proposal(
            task_prompt="Heavy refactoring",
            file_tree=["large_file.py"],
            token_ceiling=1000,
            tokens_used_so_far=1000,
        )
    assert "token ceiling of 1000 exceeded" in str(exc_info.value)


def test_model_gateway_capabilities_schema():
    gateway = ModelGateway(provider=ProviderKind.LOCAL_OLLAMA)
    assert gateway.capabilities.supports_structured_output is True
    assert gateway.capabilities.supports_code_generation is True
    assert gateway.capabilities.max_context_window == 128000
    assert gateway.endpoint_url == "http://localhost:11434"
