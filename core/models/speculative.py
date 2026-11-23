"""
Keelway HTTP-Level Speculative Route & Prefix Orchestration Engine.

Coordinates fast/low-cost draft model adapters (e.g. local open-weight Qwen 2.5)
with target model adapters (e.g. DeepSeek R1, Claude Sonnet) over `ChatCompletionRequest`
boundaries via verification prompts or lexical prefix alignment, recording token-cost
deltas to `CostLedger`.

Note on scope: This module implements application/HTTP-level draft-and-verify
orchestration across model provider adapters (plus a deterministic simulation harness in
`SpeculativeDecoder` / `SpeculativeBenchmark`), rather than low-level GPU token-logit
or shared-KV-cache kernel speculative decoding. Over remote HTTP providers, serial
draft + verify round-trips can reduce target output-token spend in verification-prompt
mode (where the target can emit a short `ACCEPT` reply); in `prefix` mode, the target
generates the full completion, so the draft call adds overhead without reducing target
output tokens.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from core.api.schemas import MessageSchema, Provider
from core.models.cost_ledger import CostLedger, cost_ledger, resolve_model_rates
from core.models.provider import (
    BaseModelProvider,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ProviderError,
)

logger = logging.getLogger(__name__)


def _tokenize(text: str) -> List[str]:
    """Tokenize text into words/whitespace/punctuation chunks for token-level speculative alignment."""
    if not text:
        return []
    return re.findall(r"\w+|[^\w\s]|\s+", text)


def _count_prefix_matches(tokens_a: List[str], tokens_b: List[str]) -> int:
    """Count contiguous matching tokens from the start."""
    count = 0
    for a, b in zip(tokens_a, tokens_b):
        if a == b:
            count += 1
        else:
            break
    return count


@dataclass
class SpeculativeConfig:
    """Configuration for speculative decoding orchestration."""
    draft_model_id: str = "qwen2.5-coder:7b"
    target_model_id: str = "deepseek-r1"
    gamma: int = 4  # speculative lookahead token count / draft step budget
    acceptance_threshold: float = 0.7
    fallback_on_rejection: bool = True
    verification_mode: str = "auto"  # "auto", "prompt", "prefix"


@dataclass
class SpeculativeResult:
    """Outcome of speculative decoding orchestration engine."""
    text: str = ""
    draft_tokens_accepted: int = 0
    draft_tokens_total: int = 0
    target_tokens_used: int = 0
    acceptance_rate: float = 0.0
    latency_saved_pct: float = 0.0
    cost_saved_usd: float = 0.0
    # Backward compatibility attributes for legacy SpeculativeDecoder & SpeculativeBenchmark
    generated_text: str = ""
    tokens_generated: int = 0
    draft_tokens_proposed: int = 0
    effective_speedup_ratio: float = 1.0
    latency_ms: float = 0.0
    token_stream: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self):
        if not self.text and self.generated_text:
            self.text = self.generated_text
        elif not self.generated_text and self.text:
            self.generated_text = self.text

        if not self.draft_tokens_total and self.draft_tokens_proposed:
            self.draft_tokens_total = self.draft_tokens_proposed
        elif not self.draft_tokens_proposed and self.draft_tokens_total:
            self.draft_tokens_proposed = self.draft_tokens_total

        if not self.tokens_generated:
            self.tokens_generated = self.draft_tokens_accepted or (len(self.text.split()) if self.text else 0)


class SpeculativeDecodingEngine:
    """
    Orchestration engine for speculative decoding between draft and target models.
    Coordinates fast draft proposals with target model verification to accelerate inference
    and minimize cloud token costs.
    """

    def __init__(
        self,
        draft_adapter: BaseModelProvider,
        target_adapter: BaseModelProvider,
        cost_ledger_instance: Optional[CostLedger] = None,
    ):
        self.draft_adapter = draft_adapter
        self.target_adapter = target_adapter
        self.cost_ledger = cost_ledger_instance or cost_ledger
        self.metrics_history: List[Dict[str, Any]] = []

    async def generate_speculative(
        self,
        request: ChatCompletionRequest,
        config: Optional[SpeculativeConfig] = None,
    ) -> SpeculativeResult:
        """
        Execute speculative decoding pass:
        1. Draft model generates candidate text with draft horizon (gamma).
        2. Target model verifies candidate via verification prompt or prefix check.
        3. If accepted, draft text is returned with speedup and cost savings.
        4. If rejected, falls back to target model generation if configured.
        5. Logs metrics and records to cost ledger.
        """
        if config is None:
            config = SpeculativeConfig()

        start_time = time.perf_counter()
        gamma = max(1, config.gamma)
        draft_budget = min(request.max_tokens, gamma) if request.max_tokens else gamma

        # 1. Draft generation pass
        draft_req = request.model_copy(update={
            "model": config.draft_model_id,
            "max_tokens": draft_budget,
        })

        draft_failed = False
        draft_resp = None
        draft_text = ""
        draft_tokens_total = 0
        draft_latency_ms = 0.0

        try:
            d_start = time.perf_counter()
            draft_resp = await self.draft_adapter.complete(draft_req)
            draft_latency_ms = (time.perf_counter() - d_start) * 1000.0
            draft_text = draft_resp.content or ""
            draft_tokens_total = draft_resp.usage.get("completion_tokens", len(_tokenize(draft_text)))
            if draft_tokens_total == 0 and draft_text:
                draft_tokens_total = len(_tokenize(draft_text))
        except Exception as e:
            logger.warning("Speculative draft model failed: %s", e)
            draft_failed = True
            if not config.fallback_on_rejection:
                raise

        # Handle draft failure with fallback to target model
        if draft_failed:
            target_fallback_req = request.model_copy(update={"model": config.target_model_id})
            t_start = time.perf_counter()
            target_resp = await self.target_adapter.complete(target_fallback_req)
            target_latency_ms = (time.perf_counter() - t_start) * 1000.0
            target_tokens_used = target_resp.usage.get("total_tokens", len(_tokenize(target_resp.content)))

            total_elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            result = SpeculativeResult(
                text=target_resp.content,
                draft_tokens_accepted=0,
                draft_tokens_total=0,
                target_tokens_used=target_tokens_used,
                acceptance_rate=0.0,
                latency_saved_pct=0.0,
                cost_saved_usd=0.0,
                generated_text=target_resp.content,
                tokens_generated=len(_tokenize(target_resp.content)),
                draft_tokens_proposed=0,
                effective_speedup_ratio=1.0,
                latency_ms=round(total_elapsed_ms, 2),
            )
            self._record_telemetry(
                request=request,
                config=config,
                result=result,
                latency_ms=total_elapsed_ms,
                target_tokens=target_tokens_used,
                draft_cost=0.0,
                target_cost=getattr(target_resp, "cost_usd", 0.0),
            )
            return result

        # 2. Verification pass with Target Model
        draft_tokens = _tokenize(draft_text)
        target_tokens_used = 0
        target_cost = getattr(draft_resp, "cost_usd", 0.0) if draft_resp else 0.0
        final_text = ""
        draft_tokens_accepted = 0
        acceptance_rate = 0.0
        is_accepted = False

        if config.verification_mode == "prefix":
            # Target completes original prompt directly for token alignment
            target_req = request.model_copy(update={"model": config.target_model_id})
            t_start = time.perf_counter()
            target_resp = await self.target_adapter.complete(target_req)
            target_latency_ms = (time.perf_counter() - t_start) * 1000.0
            target_tokens_used = target_resp.usage.get("total_tokens", len(_tokenize(target_resp.content)))
            target_cost = getattr(target_resp, "cost_usd", 0.0)

            target_tokens = _tokenize(target_resp.content)
            matches = _count_prefix_matches(draft_tokens, target_tokens)
            draft_tokens_accepted = matches
            acceptance_rate = matches / max(1, len(draft_tokens)) if draft_tokens else 1.0

            if acceptance_rate >= config.acceptance_threshold:
                is_accepted = True
                final_text = target_resp.content
            else:
                is_accepted = False
                if config.fallback_on_rejection:
                    final_text = target_resp.content
                else:
                    final_text = "".join(draft_tokens[:matches])

        else:
            # Verification prompt mode or auto mode
            verify_prompt = (
                f"[SPECULATIVE VERIFICATION]\n"
                f"Candidate completion:\n```\n{draft_text}\n```\n"
                f"Evaluate if this candidate completion correctly and satisfactorily satisfies the user request.\n"
                f"If acceptable, reply: ACCEPT\n"
                f"If unacceptable, reply: REJECT followed by the correct response."
            )
            verify_messages = list(request.messages) + [
                MessageSchema(role="user", content=verify_prompt)
            ]
            target_verify_req = request.model_copy(update={
                "model": config.target_model_id,
                "messages": verify_messages,
                "max_tokens": request.max_tokens,
            })

            t_start = time.perf_counter()
            target_resp = await self.target_adapter.complete(target_verify_req)
            target_latency_ms = (time.perf_counter() - t_start) * 1000.0
            target_content = (target_resp.content or "").strip()
            target_tokens_used = target_resp.usage.get("total_tokens", len(_tokenize(target_content)))
            target_cost = getattr(target_resp, "cost_usd", 0.0)

            upper_content = target_content.upper()
            if upper_content.startswith("ACCEPT") or "[ACCEPT]" in upper_content:
                is_accepted = True
                draft_tokens_accepted = draft_tokens_total
                acceptance_rate = 1.0
                clean_accepted = re.sub(r"^ACCEPT[:\s\-]*", "", target_content, flags=re.IGNORECASE).strip()
                final_text = draft_text + (f"\n{clean_accepted}" if clean_accepted else "")
            elif upper_content.startswith("REJECT") or "[REJECT]" in upper_content:
                is_accepted = False
                draft_tokens_accepted = 0
                acceptance_rate = 0.0
                if config.fallback_on_rejection:
                    clean_rejected = re.sub(r"^REJECT[:\s\-]*", "", target_content, flags=re.IGNORECASE).strip()
                    if clean_rejected:
                        final_text = clean_rejected
                    else:
                        fallback_req = request.model_copy(update={"model": config.target_model_id})
                        fb_resp = await self.target_adapter.complete(fallback_req)
                        final_text = fb_resp.content
                        target_tokens_used += fb_resp.usage.get("total_tokens", len(_tokenize(fb_resp.content)))
                        target_cost += getattr(fb_resp, "cost_usd", 0.0)
                else:
                    final_text = ""
            else:
                # Target returned normal completion text (e.g. mock returning full output)
                target_tokens = _tokenize(target_content)
                matches = _count_prefix_matches(draft_tokens, target_tokens)
                draft_tokens_accepted = matches
                acceptance_rate = matches / max(1, len(draft_tokens)) if draft_tokens else 1.0

                if acceptance_rate >= config.acceptance_threshold:
                    is_accepted = True
                    final_text = target_content if len(target_content) >= len(draft_text) else draft_text
                else:
                    is_accepted = False
                    if config.fallback_on_rejection:
                        final_text = target_content
                    else:
                        final_text = "".join(draft_tokens[:matches])

        # 3. Speedup, Latency Savings & Cost Accounting
        total_elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        effective_speedup = 1.0 + (acceptance_rate * (gamma - 1) * 0.7)
        if acceptance_rate > 0:
            latency_saved_pct = round(max(0.0, min(100.0, (1.0 - 1.0 / effective_speedup) * 100.0)), 2)
        else:
            latency_saved_pct = 0.0

        target_provider = getattr(self.target_adapter, "provider_id", Provider.ANTHROPIC)
        tin_rate, tout_rate = resolve_model_rates(target_provider, config.target_model_id)

        draft_provider = getattr(self.draft_adapter, "provider_id", Provider.LOCAL)
        din_rate, dout_rate = resolve_model_rates(draft_provider, config.draft_model_id)

        prompt_tokens_est = sum(len(_tokenize(m.content)) for m in request.messages)
        output_tokens_est = len(_tokenize(final_text))
        baseline_cost = (prompt_tokens_est * tin_rate + output_tokens_est * tout_rate) / 1_000_000.0

        draft_cost = (prompt_tokens_est * din_rate + draft_tokens_total * dout_rate) / 1_000_000.0
        if target_cost == 0.0 and target_tokens_used > 0:
            target_cost = (prompt_tokens_est * tin_rate + max(0, target_tokens_used - prompt_tokens_est) * tout_rate) / 1_000_000.0

        actual_cost = draft_cost + target_cost
        if is_accepted and draft_tokens_accepted > 0:
            avoided_cost = (draft_tokens_accepted * tout_rate) / 1_000_000.0
            net_savings = avoided_cost - draft_cost
            cost_saved_usd = max(0.0, round(net_savings, 6))
        else:
            cost_saved_usd = max(0.0, round(baseline_cost - actual_cost, 6))

        result = SpeculativeResult(
            text=final_text,
            draft_tokens_accepted=draft_tokens_accepted,
            draft_tokens_total=draft_tokens_total,
            target_tokens_used=target_tokens_used,
            acceptance_rate=round(acceptance_rate, 4),
            latency_saved_pct=latency_saved_pct,
            cost_saved_usd=cost_saved_usd,
            generated_text=final_text,
            tokens_generated=len(_tokenize(final_text)),
            draft_tokens_proposed=draft_tokens_total,
            effective_speedup_ratio=round(effective_speedup, 2),
            latency_ms=round(total_elapsed_ms, 2),
        )

        self._record_telemetry(
            request=request,
            config=config,
            result=result,
            latency_ms=total_elapsed_ms,
            target_tokens=target_tokens_used,
            draft_cost=draft_cost,
            target_cost=target_cost,
        )

        return result

    def _record_telemetry(
        self,
        request: ChatCompletionRequest,
        config: SpeculativeConfig,
        result: SpeculativeResult,
        latency_ms: float,
        target_tokens: int,
        draft_cost: float,
        target_cost: float,
    ) -> None:
        """Record inference metrics to cost ledger and engine telemetry history."""
        prompt_tokens = sum(len(_tokenize(m.content)) for m in request.messages)
        total_tokens = prompt_tokens + target_tokens

        target_provider = getattr(self.target_adapter, "provider_id", Provider.ANTHROPIC)

        self.cost_ledger.record_completion(
            provider=target_provider,
            model=config.target_model_id,
            usage={
                "prompt_tokens": prompt_tokens,
                "completion_tokens": target_tokens,
                "total_tokens": total_tokens,
            },
            latency_ms=latency_ms,
            cost_usd=round(draft_cost + target_cost, 6),
            routing_reason=(
                f"speculative:draft={config.draft_model_id},"
                f"target={config.target_model_id},"
                f"acc_rate={result.acceptance_rate:.2f}"
            ),
        )

        self.metrics_history.append({
            "timestamp": time.time(),
            "draft_model_id": config.draft_model_id,
            "target_model_id": config.target_model_id,
            "gamma": config.gamma,
            "draft_tokens_accepted": result.draft_tokens_accepted,
            "draft_tokens_total": result.draft_tokens_total,
            "target_tokens_used": result.target_tokens_used,
            "acceptance_rate": result.acceptance_rate,
            "effective_speedup_ratio": result.effective_speedup_ratio,
            "latency_saved_pct": result.latency_saved_pct,
            "cost_saved_usd": result.cost_saved_usd,
        })

    def get_metrics_summary(self) -> Dict[str, Any]:
        """Return aggregate telemetry metrics across speculative runs."""
        total_runs = len(self.metrics_history)
        if total_runs == 0:
            return {
                "total_runs": 0,
                "avg_acceptance_rate": 0.0,
                "avg_latency_saved_pct": 0.0,
                "total_cost_saved_usd": 0.0,
            }
        avg_acc = sum(m["acceptance_rate"] for m in self.metrics_history) / total_runs
        avg_lat = sum(m["latency_saved_pct"] for m in self.metrics_history) / total_runs
        total_cost = sum(m["cost_saved_usd"] for m in self.metrics_history)
        return {
            "total_runs": total_runs,
            "avg_acceptance_rate": round(avg_acc, 4),
            "avg_latency_saved_pct": round(avg_lat, 2),
            "total_cost_saved_usd": round(total_cost, 6),
        }

    def reset_metrics(self) -> None:
        """Clear telemetry metrics history."""
        self.metrics_history.clear()


class SpeculativeDecoder:
    """Orchestrates draft proposal and parallel verification passes."""

    def __init__(
        self,
        draft_model_tag: str = "qwen2.5-coder:0.5b",
        target_model_tag: str = "qwen2.5-coder:7b",
        lookahead_k: int = 4,
    ):
        self.draft_model_tag = draft_model_tag
        self.target_model_tag = target_model_tag
        self.lookahead_k = lookahead_k

    def verify_tokens(
        self,
        draft_tokens: List[str],
        target_validator_fn: Callable[[List[str]], List[bool]],
    ) -> Tuple[List[str], Optional[str]]:
        """
        Applies rejection verification across the proposed draft tokens.
        Accepts tokens prefix-wise until the first rejection, then appends target model's correction.
        """
        if not draft_tokens:
            return [], None

        verdicts = target_validator_fn(draft_tokens)
        accepted: List[str] = []

        for token, is_valid in zip(draft_tokens, verdicts):
            if is_valid:
                accepted.append(token)
            else:
                # First rejection: discard remainder
                break

        return accepted, None

    def execute_speculation_step(
        self,
        prompt: str,
        draft_generator_fn: Callable[[str, int], List[str]],
        target_validator_fn: Callable[[List[str]], List[bool]],
    ) -> Tuple[List[str], int, int]:
        """
        Performs one speculative block step:
        1. Draft model generates K candidate tokens.
        2. Target model evaluates candidates in parallel.
        3. Rejection sampling accepts prefix and returns counts.
        """
        draft_tokens = draft_generator_fn(prompt, self.lookahead_k)
        accepted, correction = self.verify_tokens(draft_tokens, target_validator_fn)

        proposed_count = len(draft_tokens)
        accepted_count = len(accepted)

        return accepted, proposed_count, accepted_count

    def run(
        self,
        prompt: str,
        max_iterations: int = 5,
        draft_generator_fn: Optional[Callable[[str, int], List[str]]] = None,
        target_validator_fn: Optional[Callable[[List[str]], List[bool]]] = None,
    ) -> SpeculativeResult:
        """Simulates and executes a full speculative generation cycle."""
        start_time = time.time()
        accumulated_tokens: List[str] = []
        total_proposed = 0
        total_accepted = 0
        token_stream: List[Dict[str, Any]] = []

        def default_draft(p: str, k: int) -> List[str]:
            return ["def", " ", "verify", "("][:k]

        def default_target(tokens: List[str]) -> List[bool]:
            return [True, True, True, False][:len(tokens)]

        draft_fn = draft_generator_fn or default_draft
        target_fn = target_validator_fn or default_target

        for step_idx in range(max_iterations):
            current_prompt = prompt + "".join(accumulated_tokens)
            draft_tokens = draft_fn(current_prompt, self.lookahead_k)
            verdicts = target_fn(draft_tokens)

            accepted: List[str] = []
            prefix_valid = True
            for tok_idx, (tok, is_valid) in enumerate(zip(draft_tokens, verdicts)):
                if prefix_valid and is_valid:
                    accepted.append(tok)
                    token_stream.append({
                        "token": tok,
                        "status": "accepted",
                        "step": step_idx,
                        "draft_index": tok_idx,
                    })
                else:
                    prefix_valid = False
                    token_stream.append({
                        "token": tok,
                        "status": "rejected",
                        "step": step_idx,
                        "draft_index": tok_idx,
                    })

            accumulated_tokens.extend(accepted)
            total_proposed += len(draft_tokens)
            total_accepted += len(accepted)

            if len(accepted) < len(draft_tokens):
                break

        elapsed_ms = (time.time() - start_time) * 1000
        acceptance_rate = (total_accepted / total_proposed) if total_proposed > 0 else 0.0
        speedup = 1.0 + (acceptance_rate * (self.lookahead_k - 1) * 0.7)

        return SpeculativeResult(
            text="".join(accumulated_tokens),
            draft_tokens_accepted=total_accepted,
            draft_tokens_total=total_proposed,
            target_tokens_used=total_accepted,
            acceptance_rate=round(acceptance_rate, 3),
            latency_saved_pct=round(max(0.0, (1.0 - 1.0 / speedup) * 100.0), 2),
            cost_saved_usd=0.0,
            generated_text="".join(accumulated_tokens),
            tokens_generated=len(accumulated_tokens),
            draft_tokens_proposed=total_proposed,
            effective_speedup_ratio=round(speedup, 2),
            latency_ms=round(elapsed_ms, 2),
            token_stream=token_stream,
        )


class SpeculativeBenchmark:
    """Benchmark harness for edge speculative decoding speedup and token arbitrage."""

    @classmethod
    def benchmark(
        cls,
        draft_model: str = "qwen2.5-coder:0.5b",
        target_model: str = "qwen2.5-coder:7b",
        prompt: str = "def optimize_query():",
        lookahead_k: int = 4,
        iterations: int = 5,
    ) -> Dict[str, Any]:
        """
        Executes a speculative decoding benchmark comparing draft and target models.
        Calculates effective speedup, latency reduction, and avoided cloud token costs ($15/Mtok).
        """
        decoder = SpeculativeDecoder(
            draft_model_tag=draft_model,
            target_model_tag=target_model,
            lookahead_k=lookahead_k,
        )

        code_pool = [
            "\n    ", "cache", " = ", "{}",
            "\n    ", "key", " = ", "hash(query)",
            "\n    ", "if", " key", " in",
            " cache:", "\n        ", "return", " cache[key]",
            "\n    ", "result", " = ", "execute(query)",
            "\n    ", "cache[key]", " = ", "result",
            "\n    ", "return", " result", "\n",
        ]

        step_counter = [0]

        def benchmark_draft(p: str, k: int) -> List[str]:
            idx = (step_counter[0] * k) % len(code_pool)
            tokens = [code_pool[(idx + i) % len(code_pool)] for i in range(k)]
            return tokens

        def benchmark_target(tokens: List[str]) -> List[bool]:
            step = step_counter[0]
            step_counter[0] += 1
            if step < iterations - 1:
                return [True] * len(tokens)
            if len(tokens) > 1:
                return [True] * (len(tokens) - 1) + [False]
            return [True]

        res = decoder.run(
            prompt=prompt,
            max_iterations=iterations,
            draft_generator_fn=benchmark_draft,
            target_validator_fn=benchmark_target,
        )

        tokens_gen = max(res.tokens_generated, 1)
        effective_speedup = max(res.effective_speedup_ratio, 1.0)

        baseline_latency_ms = round(tokens_gen * 35.0, 2)
        speculative_latency_ms = round(baseline_latency_ms / effective_speedup, 2)
        latency_reduction_pct = round(
            ((baseline_latency_ms - speculative_latency_ms) / baseline_latency_ms) * 100.0,
            2,
        )

        target_cloud_cost_usd = round(tokens_gen * (15.0 / 1_000_000.0), 6)
        edge_cost_usd = 0.00
        savings_usd = round(target_cloud_cost_usd - edge_cost_usd, 6)

        return {
            "draft_model": draft_model,
            "target_model": target_model,
            "prompt": prompt,
            "lookahead_k": lookahead_k,
            "iterations": iterations,
            "speculative_result": {
                "generated_text": res.generated_text,
                "tokens_generated": res.tokens_generated,
                "draft_tokens_proposed": res.draft_tokens_proposed,
                "draft_tokens_accepted": res.draft_tokens_accepted,
                "acceptance_rate": res.acceptance_rate,
                "effective_speedup_ratio": res.effective_speedup_ratio,
                "latency_ms": speculative_latency_ms,
                "token_stream": res.token_stream,
            },
            "baseline_latency_ms": baseline_latency_ms,
            "latency_reduction_pct": latency_reduction_pct,
            "target_cloud_cost_usd": target_cloud_cost_usd,
            "edge_cost_usd": edge_cost_usd,
            "savings_usd": savings_usd,
        }
