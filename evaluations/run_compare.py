#!/usr/bin/env python3
"""
Keelway — Benchmark Evaluation Runner for EVAL-COMPARE-001.
Compares frontier models against local/open-weight models on a standardized engineering brief task.
"""

import argparse
import asyncio
import json
from pathlib import Path
from typing import Dict, Any, List

from core.api.schemas import (
    CompletionRequestSchema,
    CompletionResponseSchema,
    MessageSchema,
    Provider,
)
from core.models.gateway import ModelGateway, gateway as default_gateway
from core.models.adapters.base import ModelAdapter

PROMPT = """You are a Keelway engineering assistant.

Review the following pull request summary and produce a concise, prioritized engineering brief.

PR: "Add task state machine to agent backend"
- Changes: new TaskState enum, transition table, retry logic, human approval gate
- Files touched: core/orchestration/state.py, core/orchestration/engine.py, tests/test_state.py
- Failing test: test_retry_on_transient_error currently times out
- Related: KEELWAY.md says "Prefer explicit state over opaque agent loops"

Produce directly and concisely:
1. Summary of the change (2–3 sentences)
2. Risks (ranked)
3. Recommended next actions (ordered)
4. Citations to the files mentioned (core/orchestration/state.py, core/orchestration/engine.py, tests/test_state.py)
"""


class MockEvaluationAdapter(ModelAdapter):
    """Synthetic adapter for deterministic offline evaluation tests."""
    def __init__(self, provider: Provider, latency_ms: float, cost_usd: float, content: str):
        self.provider = provider
        self.latency_ms = latency_ms
        self.cost_usd = cost_usd
        self.content = content

    def is_available(self) -> bool:
        return True

    async def complete(self, request: CompletionRequestSchema) -> CompletionResponseSchema:
        await asyncio.sleep(0.05)  # Simulate brief I/O
        return CompletionResponseSchema(
            content=self.content,
            provider=self.provider,
            model=f"mock-{self.provider.value}-v1",
            usage={"prompt_tokens": 128, "completion_tokens": 194, "total_tokens": 322},
            latency_ms=self.latency_ms,
            cost_usd=self.cost_usd,
        )


def evaluate_content_quality(content: str) -> Dict[str, Any]:
    """Score output against the EVAL-COMPARE-001 success rubric."""
    has_summary = "summary" in content.lower()
    has_risks = "risk" in content.lower()
    has_actions = "action" in content.lower() or "next" in content.lower()
    has_citations = "state.py" in content or "engine.py" in content or "test_state.py" in content

    score = 0
    if has_summary:
        score += 1
    if has_risks:
        score += 1.5
    if has_actions:
        score += 1.5
    if has_citations:
        score += 1.0

    passed = (score >= 4.0)
    return {
        "score": round(score, 1),
        "passed": passed,
        "criteria": {
            "has_summary": has_summary,
            "has_ranked_risks": has_risks,
            "has_ordered_actions": has_actions,
            "has_file_citations": has_citations,
        }
    }


async def run_eval_comparison(gw: ModelGateway, providers_to_test: List[Provider], output_dir: Path) -> Dict[str, Any]:
    results: Dict[str, Any] = {}

    print("\n============================================================")
    print("  Keelway — Benchmark Evaluation Task: EVAL-COMPARE-001     ")
    print("============================================================\n")

    for provider in providers_to_test:
        adapter = gw.adapters.get(provider)
        if not adapter or not adapter.is_available():
            print(f"[-] Skipping {provider.value.upper()}: Provider adapter not configured or API key missing.")
            results[provider.value] = {
                "status": "UNCONFIGURED",
                "error": "API key or endpoint missing",
            }
            continue

        print(f"[*] Executing benchmark on {provider.value.upper()}...")
        request = CompletionRequestSchema(
            messages=[MessageSchema(role="user", content=PROMPT)],
            preferred_provider=provider,
            temperature=0.2,
            max_tokens=2500,
        )

        try:
            resp = await adapter.complete(request)
            evaluation = evaluate_content_quality(resp.content)

            results[provider.value] = {
                "status": "COMPLETED",
                "model": resp.model,
                "latency_ms": resp.latency_ms,
                "cost_usd": resp.cost_usd,
                "usage": resp.usage,
                "evaluation": evaluation,
                "content_preview": resp.content[:200] + "..." if len(resp.content) > 200 else resp.content,
                "content": resp.content,
            }
            print(f"    -> Latency: {resp.latency_ms:.1f}ms | Cost: ${resp.cost_usd:.5f} | Score: {evaluation['score']}/5.0")
        except Exception as e:
            print(f"    [!] Error during execution: {e}")
            results[provider.value] = {
                "status": "FAILED",
                "error": str(e),
            }

    # Save artifact
    output_dir.mkdir(parents=True, exist_ok=True)
    results_file = output_dir / "results.json"
    results_file.write_text(json.dumps(results, indent=2))
    print(f"\n[+] Raw results saved to: {results_file.resolve()}\n")

    # Render summary table
    print("### EVAL-COMPARE-001 Benchmark Results\n")
    print("| Provider | Model | Latency (ms) | Tokens (In/Out) | Cost (USD) | Score (/5) | Status |")
    print("|---|---|---|---|---|---|---|")
    for prov_name, data in results.items():
        if data.get("status") == "COMPLETED":
            eval_data = data["evaluation"]
            tokens_str = f"{data['usage']['prompt_tokens']} / {data['usage']['completion_tokens']}"
            status_str = "PASS" if eval_data["passed"] else "FAIL"
            print(f"| {prov_name.capitalize()} | {data['model']} | {data['latency_ms']:.1f} | {tokens_str} | ${data['cost_usd']:.5f} | {eval_data['score']} | {status_str} |")
        else:
            print(f"| {prov_name.capitalize()} | N/A | N/A | N/A | N/A | N/A | {data.get('status')} |")

    return results


def main():
    parser = argparse.ArgumentParser(description="Keelway Model Comparison Benchmark")
    parser.add_argument("--mock", action="store_true", help="Run with simulated mock providers for offline testing")
    parser.add_argument("--providers", nargs="+", default=None, help="List of providers to evaluate (e.g. google openai)")
    parser.add_argument("--output-dir", default="evaluations/results/EVAL-COMPARE-001", help="Results output directory")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)

    if args.mock:
        gw = ModelGateway(adapters={
            Provider.ANTHROPIC: MockEvaluationAdapter(
                provider=Provider.ANTHROPIC,
                latency_ms=620.0,
                cost_usd=0.00329,
                content=(
                    "1. Summary of Changes:\n"
                    "This PR introduces an explicit TaskState enum and transition table to the agent backend, "
                    "replacing opaque loops with deterministic transitions and adding human approval gates.\n\n"
                    "2. Ranked Risks:\n"
                    "- 1. Flaky transient error recovery: test_retry_on_transient_error times out.\n"
                    "- 2. Approval bypass vulnerability.\n\n"
                    "3. Ordered Next Actions:\n"
                    "1. Investigate timeout in test_retry_on_transient_error.\n"
                    "2. Assert transition invariants.\n\n"
                    "4. Citations:\n"
                    "- core/orchestration/state.py\n"
                    "- core/orchestration/engine.py\n"
                    "- tests/test_state.py"
                ),
            ),
            Provider.LOCAL: MockEvaluationAdapter(
                provider=Provider.LOCAL,
                latency_ms=185.0,
                cost_usd=0.0,
                content=(
                    "1. Summary of Changes:\n"
                    "Adds explicit TaskState enum to backend for reliable orchestration.\n\n"
                    "2. Ranked Risks:\n"
                    "- 1. Timeout in retry tests.\n\n"
                    "3. Recommended Actions:\n"
                    "1. Fix test timeout.\n\n"
                    "4. Citations:\n"
                    "- core/orchestration/state.py\n"
                    "- tests/test_state.py"
                ),
            ),
        })
        providers = [Provider.ANTHROPIC, Provider.LOCAL]
    else:
        gw = default_gateway
        if args.providers:
            providers = [Provider(p.lower()) for p in args.providers]
        else:
            providers = [Provider.GOOGLE, Provider.OPENAI, Provider.ANTHROPIC, Provider.LOCAL]

    asyncio.run(run_eval_comparison(gw, providers, output_dir))


if __name__ == "__main__":
    main()
