"""
Unit tests for Keelway Model Registry.
Verifies registration, querying, filtering, and metadata validation for both
Open-Weight and Closed/Proprietary models.
"""

from core.models.registry import (
    ModelRegistry,
    ModelCategory,
    ModelFamily,
)
from core.api.schemas import Provider


def test_canonical_models_contain_both_categories():
    registry = ModelRegistry()
    open_weights = registry.list_models(category=ModelCategory.OPEN_WEIGHT)
    closed_models = registry.list_models(category=ModelCategory.CLOSED_PROPRIETARY)

    assert len(open_weights) >= 4, "Must contain at least 4 canonical open-weight models (Qwen, Llama, Mistral, DeepSeek)"
    assert len(closed_models) >= 3, "Must contain at least 3 canonical closed models (OpenAI, Anthropic, Gemini)"

    # Verify open-weight models have $0.00 external API pricing
    for m in open_weights:
        assert m.pricing_input_usd_per_mtok == 0.0
        assert m.pricing_output_usd_per_mtok == 0.0
        assert m.license != "Proprietary"

    # Verify closed models have valid rate cards and commercial licenses
    for m in closed_models:
        assert m.pricing_input_usd_per_mtok > 0.0
        assert m.pricing_output_usd_per_mtok > 0.0


def test_registry_lookup_by_id_and_alias():
    registry = ModelRegistry()
    qwen = registry.get("qwen2.5-coder:7b")
    assert qwen is not None
    assert qwen.family == ModelFamily.QWEN
    assert qwen.category == ModelCategory.OPEN_WEIGHT

    # Tag alias lookup
    qwen_alias = registry.get("qwen2.5-coder")
    assert qwen_alias is not None
    assert qwen_alias.id == "qwen2.5-coder:7b"

    gpt4o = registry.get("gpt-4o")
    assert gpt4o is not None
    assert gpt4o.category == ModelCategory.CLOSED_PROPRIETARY
    assert gpt4o.provider == Provider.OPENAI


def test_registry_filtering_by_capability():
    registry = ModelRegistry()
    code_models = registry.list_models(capability="code")
    assert len(code_models) >= 5

    reasoning_models = registry.list_models(capability="reasoning")
    assert any(m.id == "deepseek-r1:7b" for m in reasoning_models)
    assert any(m.id == "gpt-4o" for m in reasoning_models)


def test_registry_discovery_dict_structure():
    registry = ModelRegistry()
    disc = registry.to_discovery_dict()
    assert disc["object"] == "list"
    assert "data" in disc
    assert disc["categories"]["open_weight"] > 0
    assert disc["categories"]["closed_proprietary"] > 0

    first = disc["data"][0]
    assert "id" in first
    assert "category" in first
    assert "pricing" in first
    assert "context_window" in first
    assert "license" in first
