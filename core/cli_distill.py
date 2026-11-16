"""
Keelway Sovereign CLI Phase 19A Semantic Prompt Cache, Shadow Dual-Run & QLoRA Distillation
Subcommands (`shadow`, `distill`).
"""

from __future__ import annotations

import argparse
import json
from typing import Optional

from core.platform.shadow_distillation import (
    DEFAULT_CODE_RESPONSE,
    DEFAULT_FRONTIER_MODEL,
    DEFAULT_LOCAL_MODEL,
    DEFAULT_SHADOW_PROMPT,
    SQLiteShadowDistillationEngine,
    ShadowDistillationValidationError,
)


def _add_common_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--workspace", "--workspace-id", dest="workspace_id", default="default", help="Target workspace ID")
    parser.add_argument("--db-path", default=None, help="Optional SQLite database path override")
    parser.add_argument("--json", action="store_true", help="Emit JSON output")


def register_distill_cli_subparsers(subparsers: argparse._SubParsersAction) -> None:
    """Register `keelway shadow` and `keelway distill` sovereign CLI subcommands."""
    for name in ("shadow", "distill"):
        if name in subparsers._name_parser_map:
            subparsers._name_parser_map.pop(name, None)
            subparsers._choices_actions = [a for a in subparsers._choices_actions if getattr(a, "dest", None) != name]

    sh = subparsers.add_parser("shadow", help="Semantic prompt cache & Frontier-vs-Local shadow dual-run router")
    sh_sub = sh.add_subparsers(dest="shadow_action", required=True)

    sh_eval = sh_sub.add_parser("evaluate", help="Evaluate prompt against 3-gram semantic cache or record shadow dual-run parity")
    sh_eval.add_argument("--prompt", default=DEFAULT_SHADOW_PROMPT, help="Input prompt text")
    sh_eval.add_argument("--frontier-response", default=DEFAULT_CODE_RESPONSE, help="Frontier BYOM reference response")
    sh_eval.add_argument("--local-response", default=DEFAULT_CODE_RESPONSE, help="Local OpenCore candidate response")
    sh_eval.add_argument("--frontier-model", default=DEFAULT_FRONTIER_MODEL, help="Frontier model identifier")
    sh_eval.add_argument("--local-model", default=DEFAULT_LOCAL_MODEL, help="Local OpenCore model identifier")
    sh_eval.add_argument("--task-tag", default="code-patch", help="Task isolation tag (default: code-patch)")
    sh_eval.add_argument("--frontier-cost-usd", type=float, default=0.018, help="Estimated Frontier invocation cost in USD")
    sh_eval.add_argument("--frontier-latency-ms", type=int, default=840, help="Frontier latency in milliseconds")
    sh_eval.add_argument("--local-latency-ms", type=int, default=95, help="Local candidate latency in milliseconds")
    sh_eval.add_argument("--similarity-threshold", type=float, default=0.82, help="3-gram shingle Jaccard cache threshold")
    sh_eval.add_argument("--bypass-cache", action="store_true", help="Force shadow evaluation even if cached")
    _add_common_flags(sh_eval)

    sh_pairs = sh_sub.add_parser("pairs", help="List DLP-scrubbed Frontier-vs-Local shadow distillation pairs")
    sh_pairs.add_argument("--task-tag", default="", help="Optional task tag filter")
    sh_pairs.add_argument("--limit", type=int, default=25, help="Maximum pairs to return (default: 25)")
    _add_common_flags(sh_pairs)

    sh_stats = sh_sub.add_parser("stats", help="Inspect semantic prompt cache hit rate, USD saved & DLP metrics")
    _add_common_flags(sh_stats)

    ds = subparsers.add_parser("distill", help="Compile SFT/DPO QLoRA datasets & evaluate OpenCore canary promotion")
    ds_sub = ds.add_subparsers(dest="distill_action", required=True)

    ds_comp = ds_sub.add_parser("compile", help="Compile DLP-scrubbed SFT JSONL or DPO preference QLoRA dataset")
    ds_comp.add_argument("--task-tag", default="", help="Optional task tag filter")
    ds_comp.add_argument(
        "--format",
        "--export-format",
        dest="export_format",
        choices=["sft_jsonl", "dpo_preference"],
        default="dpo_preference",
        help="Dataset export format (default: dpo_preference)",
    )
    ds_comp.add_argument("--base-model", "--target-base-model", dest="target_base_model", default=DEFAULT_LOCAL_MODEL, help="Target OpenCore base model")
    ds_comp.add_argument("--min-parity", "--min-parity-score", dest="min_parity_score", type=float, default=0.0, help="Minimum parity score filter")
    _add_common_flags(ds_comp)

    ds_list = ds_sub.add_parser("datasets", help="List compiled QLoRA distillation dataset manifests")
    ds_list.add_argument("--limit", type=int, default=25, help="Maximum datasets to return (default: 25)")
    _add_common_flags(ds_list)

    ds_prom = ds_sub.add_parser("promote", help="Evaluate OpenCore canary promotion readiness & projected savings")
    ds_prom.add_argument("--task-tag", default="code-patch", help="Task tag to evaluate (default: code-patch)")
    ds_prom.add_argument("--target-model", "--target-local-model", dest="target_local_model", default=DEFAULT_LOCAL_MODEL, help="Target local OpenCore model")
    ds_prom.add_argument("--min-pairs", type=int, default=3, help="Minimum required shadow pairs (default: 3)")
    ds_prom.add_argument("--min-parity", "--min-avg-parity", dest="min_avg_parity", type=float, default=0.85, help="Minimum empirical parity threshold (default: 0.85)")
    ds_prom.add_argument("--monthly-volume", "--monthly-request-volume", dest="monthly_request_volume", type=int, default=50000, help="Projected monthly request volume")
    _add_common_flags(ds_prom)


def dispatch_distill_cli(args: argparse.Namespace) -> Optional[int]:
    """Dispatch `keelway shadow` and `keelway distill` CLI subcommands."""
    cmd = getattr(args, "command", None)
    if cmd not in ("shadow", "distill"):
        return None

    ws_id = str(getattr(args, "workspace_id", "default") or "default")
    as_json = bool(getattr(args, "json", False))
    engine = SQLiteShadowDistillationEngine(db_path=getattr(args, "db_path", None))
    try:
        if cmd == "shadow":
            act = getattr(args, "shadow_action", None)
            if act == "evaluate":
                res = engine.evaluate_shadow_prompt(
                    workspace_id=ws_id,
                    task_tag=str(getattr(args, "task_tag", "code-patch")),
                    prompt=str(getattr(args, "prompt", DEFAULT_SHADOW_PROMPT)),
                    frontier_model=str(getattr(args, "frontier_model", DEFAULT_FRONTIER_MODEL)),
                    local_model=str(getattr(args, "local_model", DEFAULT_LOCAL_MODEL)),
                    frontier_response=str(getattr(args, "frontier_response", DEFAULT_CODE_RESPONSE)),
                    local_response=str(getattr(args, "local_response", DEFAULT_CODE_RESPONSE)),
                    frontier_cost_usd=float(getattr(args, "frontier_cost_usd", 0.018)),
                    frontier_latency_ms=int(getattr(args, "frontier_latency_ms", 840)),
                    local_latency_ms=int(getattr(args, "local_latency_ms", 95)),
                    similarity_threshold=float(getattr(args, "similarity_threshold", 0.82)),
                    bypass_cache=bool(getattr(args, "bypass_cache", False)),
                )
                print(
                    json.dumps(res, indent=2)
                    if as_json
                    else f"[{res['verdict']}] match={res['match_type']} parity={res['parity_score']:.4f} saved=${res['cost_saved_usd']:.4f}"
                )
                return 0

            if act == "pairs":
                res = engine.list_shadow_pairs(
                    workspace_id=ws_id,
                    task_tag=str(getattr(args, "task_tag", "")),
                    limit=int(getattr(args, "limit", 25)),
                )
                print(json.dumps(res, indent=2) if as_json else f"Shadow Pairs [{ws_id}] count={res['count']}")
                return 0

            if act == "stats":
                res = engine.get_cache_stats(workspace_id=ws_id)
                print(
                    json.dumps(res, indent=2)
                    if as_json
                    else f"Semantic Cache [{ws_id}] entries={res['entry_count']} hits={res['total_hits']}/{res['total_lookups']} saved=${res['total_cost_saved_usd']:.4f}"
                )
                return 0

        if cmd == "distill":
            act = getattr(args, "distill_action", None)
            if act == "compile":
                res = engine.compile_distillation_dataset(
                    workspace_id=ws_id,
                    task_tag=str(getattr(args, "task_tag", "")),
                    export_format=str(getattr(args, "export_format", "dpo_preference")),
                    target_base_model=str(getattr(args, "target_base_model", DEFAULT_LOCAL_MODEL)),
                    min_parity_score=float(getattr(args, "min_parity_score", 0.0)),
                )
                print(
                    json.dumps(res, indent=2)
                    if as_json
                    else f"[{res['export_format']}] {res['dataset_id']} records={res['record_count']} r={res['lora_rank']}/alpha={res['lora_alpha']}"
                )
                return 0

            if act == "datasets":
                res = engine.list_distillation_datasets(workspace_id=ws_id, limit=int(getattr(args, "limit", 25)))
                print(json.dumps(res, indent=2) if as_json else f"Distillation Datasets [{ws_id}] count={res['count']}")
                return 0

            if act == "promote":
                res = engine.evaluate_promotion_gate(
                    workspace_id=ws_id,
                    task_tag=str(getattr(args, "task_tag", "code-patch")),
                    target_local_model=str(getattr(args, "target_local_model", DEFAULT_LOCAL_MODEL)),
                    min_pairs=int(getattr(args, "min_pairs", 3)),
                    min_avg_parity=float(getattr(args, "min_avg_parity", 0.85)),
                    monthly_request_volume=int(getattr(args, "monthly_request_volume", 50000)),
                )
                print(
                    json.dumps(res, indent=2)
                    if as_json
                    else f"[{res['verdict']}] pairs={res['pair_count']}/{res['min_pairs']} parity={res['avg_parity_score']:.4f} savings=${res['projected_monthly_savings_usd']:.2f}/mo"
                )
                if res["verdict"] == "PROMOTE_TO_OPENCORE":
                    return 0
                return 2 if res["verdict"] == "NEEDS_MORE_PAIRS" else 1
    except (ShadowDistillationValidationError, ValueError, OSError) as exc:
        print(
            json.dumps({"detail": str(exc), "error": str(exc), "code": "shadow_distillation_validation_error"}, indent=2)
            if as_json
            else f"[-] {exc}"
        )
        return 1
    finally:
        engine.close()

    return None
