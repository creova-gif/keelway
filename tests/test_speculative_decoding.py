"""
Comprehensive unit tests for Keelway Speculative Decoding Orchestration Engine.

Tests:
1. Draft acceptance scenarios (high agreement -> high acceptance rate, latency speedup, cost savings).
2. Draft rejection / divergence scenarios (fallback to target generation).
3. Cost and token accounting accuracy against rate cards.
4. Error handling when draft or target model errors.
5. Configuration, telemetry metrics summary, and lookahead scaling.
"""

from __future__ import annotations

import pytest
from typing import Any, AsyncIterator, Dict, List, Optional

from core.api.schemas import MessageSchema, Provider
from core.models.cost_ledger import CostLedger, MODEL_RATE_CARDS
from core.models.provider import (
    BaseModelProvider,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ModelCategory,
    ProviderError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    StreamChunk,
)
from core.models.speculative import (
    SpeculativeConfig,
    SpeculativeDecodingEngine,
    SpeculativeResult,
    _count_prefix_matches,
    _tokenize,
)


class MockModelProvider(BaseModelProvider):
    """Configurable mock provider adapter for deterministic speculative decoding tests."""

    def __init__(
        self,
        provider_id: Provider = Provider.LOCAL,
        category: ModelCategory = ModelCategory.OPEN_WEIGHT,
        response_content: str = "default mock response",
        completion_tokens: int = 20,
        prompt_tokens: int = 10,
        cost_usd: float = 0.0,
        latency_ms: float = 15.0,
        error_to_raise: Optional[Exception] = None,
    ):
        self.provider_id = provider_id
        self.category = category
        self.response_content = response_content
        self.completion_tokens = completion_tokens
        self.prompt_tokens = prompt_tokens
        self.cost_usd = cost_usd
        self.latency_ms = latency_ms
        self.error_to_raise = error_to_raise
        self.calls: List[ChatCompletionRequest] = []

    def is_available(self) -> bool:
        return True

    async def complete(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        self.calls.append(request)
        if self.error_to_raise:
            raise self.error_to_raise
        return ChatCompletionResponse(
            model=request.model or "mock-model",
            provider=self.provider_id,
            category=self.category,
            content=self.response_content,
            usage={
                "prompt_tokens": self.prompt_tokens,
                "completion_tokens": self.completion_tokens,
                "total_tokens": self.prompt_tokens + self.completion_tokens,
            },
            latency_ms=self.latency_ms,
            cost_usd=self.cost_usd,
        )

    async def stream_complete(self, request: ChatCompletionRequest) -> AsyncIterator[StreamChunk]:
        yield StreamChunk(
            model=request.model or "mock-model",
            provider=self.provider_id,
            delta_content=self.response_content,
        )

    async def health_check(self) -> Dict[str, Any]:
        return {"status": "ok"}


# ---------------------------------------------------------------------------
# 1. Config & Result Dataclass Tests
# ---------------------------------------------------------------------------

def test_speculative_config_defaults():
    """Verify default parameters of SpeculativeConfig."""
    config = SpeculativeConfig()
    assert config.draft_model_id == "qwen2.5-coder:7b"
    assert config.target_model_id == "deepseek-r1"
    assert config.gamma == 4
    assert config.acceptance_threshold == 0.7
    assert config.fallback_on_rejection is True
    assert config.verification_mode == "auto"


def test_speculative_config_custom():
    """Verify custom initialization of SpeculativeConfig."""
    config = SpeculativeConfig(
        draft_model_id="qwen2.5-coder:1.5b",
        target_model_id="claude-3-5-sonnet",
        gamma=8,
        acceptance_threshold=0.85,
        fallback_on_rejection=False,
        verification_mode="prefix",
    )
    assert config.draft_model_id == "qwen2.5-coder:1.5b"
    assert config.target_model_id == "claude-3-5-sonnet"
    assert config.gamma == 8
    assert config.acceptance_threshold == 0.85
    assert config.fallback_on_rejection is False
    assert config.verification_mode == "prefix"


def test_speculative_result_attributes():
    """Verify SpeculativeResult fields and bidirectional backward compatibility."""
    res = SpeculativeResult(
        text="def solve(): return 42",
        draft_tokens_accepted=8,
        draft_tokens_total=8,
        target_tokens_used=2,
        acceptance_rate=1.0,
        latency_saved_pct=65.5,
        cost_saved_usd=0.00012,
    )
    assert res.text == "def solve(): return 42"
    assert res.generated_text == "def solve(): return 42"
    assert res.draft_tokens_accepted == 8
    assert res.draft_tokens_total == 8
    assert res.draft_tokens_proposed == 8
    assert res.target_tokens_used == 2
    assert res.acceptance_rate == 1.0
    assert res.latency_saved_pct == 65.5
    assert res.cost_saved_usd == 0.00012


def test_tokenization_and_prefix_matching():
    """Verify tokenization helper and prefix matching logic."""
    text_a = "def add(x, y): return x + y"
    text_b = "def add(x, y): return x - y"
    toks_a = _tokenize(text_a)
    toks_b = _tokenize(text_b)
    matches = _count_prefix_matches(toks_a, toks_b)
    assert matches > 0
    assert toks_a[:matches] == toks_b[:matches]


# ---------------------------------------------------------------------------
# 2. Draft Acceptance Scenarios (High Agreement)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_draft_acceptance_prompt_mode():
    """High agreement scenario: Draft model generates response, target verifies ACCEPT."""
    draft_code = "def fib(n):\n    return n if n <= 1 else fib(n-1) + fib(n-2)"
    draft_adapter = MockModelProvider(
        provider_id=Provider.LOCAL,
        response_content=draft_code,
        completion_tokens=25,
        cost_usd=0.0,
    )
    target_adapter = MockModelProvider(
        provider_id=Provider.ANTHROPIC,
        response_content="ACCEPT: Verified correct recursive Fibonacci implementation.",
        completion_tokens=8,
        cost_usd=0.0001,
    )

    ledger = CostLedger()
    engine = SpeculativeDecodingEngine(
        draft_adapter=draft_adapter,
        target_adapter=target_adapter,
        cost_ledger_instance=ledger,
    )

    req = ChatCompletionRequest(
        messages=[MessageSchema(role="user", content="Write fibonacci in Python")],
        max_tokens=100,
    )
    config = SpeculativeConfig(
        draft_model_id="qwen2.5-coder:7b",
        target_model_id="claude-3-5-sonnet",
        gamma=4,
        acceptance_threshold=0.7,
        verification_mode="prompt",
    )

    result = await engine.generate_speculative(req, config)

    assert result.acceptance_rate == 1.0
    assert result.draft_tokens_accepted == 25
    assert result.draft_tokens_total == 25
    assert draft_code in result.text
    assert result.effective_speedup_ratio > 2.0
    assert result.latency_saved_pct > 50.0
    assert result.cost_saved_usd > 0.0

    # Ensure draft model was called with limited max_tokens (gamma budget)
    assert len(draft_adapter.calls) == 1
    assert draft_adapter.calls[0].max_tokens == 4
    assert draft_adapter.calls[0].model == "qwen2.5-coder:7b"

    # Ensure target model was called for verification
    assert len(target_adapter.calls) == 1
    assert target_adapter.calls[0].model == "claude-3-5-sonnet"


@pytest.mark.asyncio
async def test_draft_acceptance_prefix_mode():
    """Prefix verification mode: Draft and target models produce identical matching token sequences."""
    shared_response = "SELECT id, name FROM users WHERE active = true ORDER BY id DESC LIMIT 10;"
    draft_adapter = MockModelProvider(
        provider_id=Provider.LOCAL,
        response_content=shared_response,
        completion_tokens=20,
    )
    target_adapter = MockModelProvider(
        provider_id=Provider.ANTHROPIC,
        response_content=shared_response,
        completion_tokens=20,
    )

    engine = SpeculativeDecodingEngine(draft_adapter, target_adapter, CostLedger())
    req = ChatCompletionRequest(
        messages=[MessageSchema(role="user", content="SQL query for active users")],
        max_tokens=64,
    )
    config = SpeculativeConfig(
        draft_model_id="qwen2.5-coder:7b",
        target_model_id="deepseek-r1",
        gamma=6,
        acceptance_threshold=0.8,
        verification_mode="prefix",
    )

    result = await engine.generate_speculative(req, config)

    assert result.acceptance_rate == 1.0
    assert result.draft_tokens_accepted > 0
    assert result.text == shared_response
    assert result.effective_speedup_ratio > 1.5
    assert result.latency_saved_pct > 0.0


# ---------------------------------------------------------------------------
# 3. Draft Rejection / Divergence Scenarios (Fallback to Target)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_draft_rejection_with_inline_target_correction():
    """Draft model generates invalid output, target model rejects and supplies corrected output."""
    draft_hallucination = "def parse_json(s): return eval(s)"  # dangerous/incorrect
    target_correction = "def parse_json(s): import json; return json.loads(s)"

    draft_adapter = MockModelProvider(
        provider_id=Provider.LOCAL,
        response_content=draft_hallucination,
        completion_tokens=15,
    )
    target_adapter = MockModelProvider(
        provider_id=Provider.ANTHROPIC,
        response_content=f"REJECT: {target_correction}",
        completion_tokens=20,
    )

    engine = SpeculativeDecodingEngine(draft_adapter, target_adapter, CostLedger())
    req = ChatCompletionRequest(
        messages=[MessageSchema(role="user", content="Safe JSON parse function")],
        max_tokens=128,
    )
    config = SpeculativeConfig(
        draft_model_id="qwen2.5-coder:7b",
        target_model_id="claude-3-5-sonnet",
        gamma=4,
        acceptance_threshold=0.7,
        fallback_on_rejection=True,
    )

    result = await engine.generate_speculative(req, config)

    assert result.acceptance_rate == 0.0
    assert result.draft_tokens_accepted == 0
    assert target_correction in result.text
    assert result.latency_saved_pct == 0.0
    assert result.cost_saved_usd == 0.0


@pytest.mark.asyncio
async def test_draft_rejection_fallback_regeneration():
    """Target model rejects without inline correction, triggering full target regeneration."""
    draft_adapter = MockModelProvider(
        provider_id=Provider.LOCAL,
        response_content="Wrong draft content",
        completion_tokens=5,
    )

    # First call: target rejects. Second call: target generates full fallback completion.
    call_count = [0]
    target_final_text = "Accurate full target model completion."

    class DynamicTargetProvider(MockModelProvider):
        async def complete(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
            self.calls.append(request)
            call_count[0] += 1
            if call_count[0] == 1:
                return ChatCompletionResponse(
                    model=request.model or "target",
                    provider=self.provider_id,
                    category=self.category,
                    content="REJECT",
                    usage={"prompt_tokens": 10, "completion_tokens": 1, "total_tokens": 11},
                    latency_ms=10.0,
                )
            else:
                return ChatCompletionResponse(
                    model=request.model or "target",
                    provider=self.provider_id,
                    category=self.category,
                    content=target_final_text,
                    usage={"prompt_tokens": 10, "completion_tokens": 12, "total_tokens": 22},
                    latency_ms=30.0,
                )

    target_adapter = DynamicTargetProvider(provider_id=Provider.ANTHROPIC)
    engine = SpeculativeDecodingEngine(draft_adapter, target_adapter, CostLedger())

    req = ChatCompletionRequest(
        messages=[MessageSchema(role="user", content="Test prompt")],
        max_tokens=64,
    )
    config = SpeculativeConfig(
        draft_model_id="qwen2.5-coder:7b",
        target_model_id="deepseek-r1",
        fallback_on_rejection=True,
    )

    result = await engine.generate_speculative(req, config)

    assert result.text == target_final_text
    assert result.acceptance_rate == 0.0
    assert result.draft_tokens_accepted == 0
    assert len(target_adapter.calls) == 2  # 1 verify + 1 fallback generation


@pytest.mark.asyncio
async def test_draft_rejection_without_fallback():
    """When fallback_on_rejection=False, engine rejects draft without invoking target regeneration."""
    draft_adapter = MockModelProvider(
        provider_id=Provider.LOCAL,
        response_content="Unsatisfactory response",
        completion_tokens=10,
    )
    target_adapter = MockModelProvider(
        provider_id=Provider.ANTHROPIC,
        response_content="REJECT",
        completion_tokens=1,
    )

    engine = SpeculativeDecodingEngine(draft_adapter, target_adapter, CostLedger())
    req = ChatCompletionRequest(
        messages=[MessageSchema(role="user", content="Prompt")],
        max_tokens=50,
    )
    config = SpeculativeConfig(
        fallback_on_rejection=False,
    )

    result = await engine.generate_speculative(req, config)

    assert result.acceptance_rate == 0.0
    assert result.draft_tokens_accepted == 0
    assert result.text == ""
    # Target was only called once for verification, no fallback call
    assert len(target_adapter.calls) == 1


# ---------------------------------------------------------------------------
# 4. Cost & Token Accounting Accuracy
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cost_and_token_accounting_accuracy():
    """Verify exact token accounting and cost savings calculation against model rate cards."""
    draft_tokens = 50
    draft_adapter = MockModelProvider(
        provider_id=Provider.LOCAL,
        response_content="A" * 200,
        completion_tokens=draft_tokens,
        cost_usd=0.0,
    )
    target_adapter = MockModelProvider(
        provider_id=Provider.ANTHROPIC,
        response_content="ACCEPT",
        completion_tokens=1,
        cost_usd=0.0,
    )

    ledger = CostLedger()
    engine = SpeculativeDecodingEngine(draft_adapter, target_adapter, cost_ledger_instance=ledger)

    req = ChatCompletionRequest(
        messages=[MessageSchema(role="user", content="Generate 50 tokens")],
        max_tokens=100,
    )
    config = SpeculativeConfig(
        draft_model_id="qwen2.5-coder",  # $0.0 / Mtok (Local)
        target_model_id="claude-3-5-sonnet",  # ($3.00, $15.00) / Mtok
        gamma=draft_tokens,
    )

    result = await engine.generate_speculative(req, config)

    assert result.draft_tokens_accepted == draft_tokens
    assert result.draft_tokens_total == draft_tokens
    assert result.acceptance_rate == 1.0

    # Expected avoided cloud output cost: 50 * ($15.00 / 1,000,000) = $0.00075
    expected_savings = round(draft_tokens * (15.0 / 1_000_000.0), 6)
    assert result.cost_saved_usd == expected_savings

    # Verify audit entry recorded in cost ledger
    entries = ledger.list_entries()
    assert len(entries) == 1
    assert entries[0]["model"] == "claude-3-5-sonnet"
    assert "speculative:draft=" in entries[0]["routing_reason"]


# ---------------------------------------------------------------------------
# 5. Error Handling Scenarios
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_error_handling_draft_failure_with_fallback():
    """When draft model errors, engine gracefully falls back to target model without failing."""
    draft_adapter = MockModelProvider(
        provider_id=Provider.LOCAL,
        error_to_raise=ProviderTimeoutError("Draft model timed out", Provider.LOCAL),
    )
    target_adapter = MockModelProvider(
        provider_id=Provider.ANTHROPIC,
        response_content="Target model generated content successfully.",
        completion_tokens=25,
    )

    engine = SpeculativeDecodingEngine(draft_adapter, target_adapter, CostLedger())
    req = ChatCompletionRequest(
        messages=[MessageSchema(role="user", content="Hello")],
        max_tokens=50,
    )
    config = SpeculativeConfig(
        fallback_on_rejection=True,
    )

    result = await engine.generate_speculative(req, config)

    assert result.text == "Target model generated content successfully."
    assert result.draft_tokens_accepted == 0
    assert result.draft_tokens_total == 0
    assert result.acceptance_rate == 0.0
    assert result.effective_speedup_ratio == 1.0
    assert len(target_adapter.calls) == 1


@pytest.mark.asyncio
async def test_error_handling_draft_failure_without_fallback():
    """When fallback_on_rejection=False, draft model error is raised to caller."""
    draft_adapter = MockModelProvider(
        provider_id=Provider.LOCAL,
        error_to_raise=ProviderRateLimitError("Draft model rate limited", Provider.LOCAL),
    )
    target_adapter = MockModelProvider(
        provider_id=Provider.ANTHROPIC,
        response_content="Target response",
    )

    engine = SpeculativeDecodingEngine(draft_adapter, target_adapter, CostLedger())
    req = ChatCompletionRequest(
        messages=[MessageSchema(role="user", content="Hello")],
        max_tokens=50,
    )
    config = SpeculativeConfig(
        fallback_on_rejection=False,
    )

    with pytest.raises(ProviderRateLimitError):
        await engine.generate_speculative(req, config)


@pytest.mark.asyncio
async def test_error_handling_target_failure():
    """When target model errors, engine propagates the error."""
    draft_adapter = MockModelProvider(
        provider_id=Provider.LOCAL,
        response_content="Draft proposal",
        completion_tokens=10,
    )
    target_adapter = MockModelProvider(
        provider_id=Provider.ANTHROPIC,
        error_to_raise=ProviderError("Target verification outage", Provider.ANTHROPIC),
    )

    engine = SpeculativeDecodingEngine(draft_adapter, target_adapter, CostLedger())
    req = ChatCompletionRequest(
        messages=[MessageSchema(role="user", content="Hello")],
        max_tokens=50,
    )

    with pytest.raises(ProviderError):
        await engine.generate_speculative(req)


# ---------------------------------------------------------------------------
# 6. Telemetry History & Gamma Scaling
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_engine_telemetry_metrics_summary():
    """Verify aggregate telemetry recording across multiple speculative passes."""
    draft_adapter = MockModelProvider(
        provider_id=Provider.LOCAL,
        response_content="Sample code",
        completion_tokens=20,
    )
    target_adapter = MockModelProvider(
        provider_id=Provider.ANTHROPIC,
        response_content="ACCEPT",
        completion_tokens=2,
    )

    engine = SpeculativeDecodingEngine(draft_adapter, target_adapter, CostLedger())
    req = ChatCompletionRequest(
        messages=[MessageSchema(role="user", content="Prompt")],
        max_tokens=50,
    )

    # 1. Successful pass
    await engine.generate_speculative(req, SpeculativeConfig(gamma=4))

    # 2. Rejection pass
    target_adapter.response_content = "REJECT"
    await engine.generate_speculative(req, SpeculativeConfig(gamma=4))

    summary = engine.get_metrics_summary()
    assert summary["total_runs"] == 2
    assert 0.4 < summary["avg_acceptance_rate"] < 0.6  # (1.0 + 0.0) / 2 = 0.5
    assert summary["total_cost_saved_usd"] >= 0.0

    engine.reset_metrics()
    assert engine.get_metrics_summary()["total_runs"] == 0


@pytest.mark.asyncio
async def test_gamma_scaling_speedup():
    """Higher gamma lookahead yields higher speedup and latency savings when draft is accepted."""
    draft_adapter = MockModelProvider(
        provider_id=Provider.LOCAL,
        response_content="Long candidate token stream for lookahead benchmark",
        completion_tokens=30,
    )
    target_adapter = MockModelProvider(
        provider_id=Provider.ANTHROPIC,
        response_content="ACCEPT",
        completion_tokens=1,
    )

    engine = SpeculativeDecodingEngine(draft_adapter, target_adapter, CostLedger())
    req = ChatCompletionRequest(
        messages=[MessageSchema(role="user", content="Benchmark")],
        max_tokens=100,
    )

    res_small_gamma = await engine.generate_speculative(req, SpeculativeConfig(gamma=2))
    res_large_gamma = await engine.generate_speculative(req, SpeculativeConfig(gamma=8))

    assert res_large_gamma.effective_speedup_ratio > res_small_gamma.effective_speedup_ratio
    assert res_large_gamma.latency_saved_pct > res_small_gamma.latency_saved_pct
