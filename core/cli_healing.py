"""
Keelway Sovereign CLI Phase 16A Structured-Output & Autonomous Self-Healing Subcommands
(`structured`, `heal`).

Registered and dispatched via `core.cli_runtime` supporting `--workspace` / `--workspace-id`,
`--db-path`, and `--json` for cross-provider `.content_blocks` normalization, JSON-Schema
enforcement/repair, and Flight-Tape failure root-cause diagnosis + Golden Eval promotion.
"""

from __future__ import annotations

import argparse
import json
from typing import Any, Dict, Optional

from core.platform.structured_self_healing import (
    SelfHealingNotFoundError,
    SQLiteStructuredHealingEngine,
    StructuredHealingValidationError,
    StructuredSchemaRejectedError,
)

_DEFAULT_CLI_SCHEMA = (
    '{"type":"object","required":["decision"],'
    '"properties":{"decision":{"type":"string"},"confidence":{"type":"number"}}}'
)


def _add_common_healing_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--workspace",
        "--workspace-id",
        dest="workspace_id",
        default="default",
        help="Target workspace identifier (default: default)",
    )
    parser.add_argument("--db-path", default=None, help="Optional SQLite database path override")
    parser.add_argument("--json", action="store_true", help="Emit JSON output")


def register_healing_cli_subparsers(subparsers: argparse._SubParsersAction) -> None:
    """Register `keelway structured` and `keelway heal` sovereign CLI subcommands."""
    st = subparsers.add_parser(
        "structured",
        help="Normalize cross-provider content blocks and enforce JSON-Schema structured outputs",
    )
    st_sub = st.add_subparsers(dest="structured_action", required=True)

    st_norm = st_sub.add_parser("normalize", help="Normalize provider payload into canonical content_blocks")
    st_norm.add_argument(
        "--provider-format",
        default="deepseek_opencore",
        help="Provider format (deepseek_opencore|openai|anthropic|gemini)",
    )
    st_norm.add_argument("--model-id", "--model", dest="model_id", default="keelway-core:7b", help="Model ID")
    st_norm.add_argument("--payload", "--raw-payload", dest="raw_payload", default="", help="Raw string or JSON payload")
    st_norm.add_argument("--payload-json", default=None, help="Explicit JSON object payload")
    _add_common_healing_flags(st_norm)

    st_enf = st_sub.add_parser("enforce", help="Validate or single-pass repair output against a JSON Schema")
    st_enf.add_argument("--schema", "--schema-json", dest="schema_json", default=_DEFAULT_CLI_SCHEMA, help="JSON Schema object")
    st_enf.add_argument("--output", "--raw-output", dest="raw_output", required=True, help="Raw model output string or JSON")
    st_enf.add_argument("--schema-name", default="AgentDecisionContract", help="Contract schema name")
    st_enf.add_argument("--provider-format", default="deepseek_opencore", help="Provider format")
    st_enf.add_argument("--model-id", "--model", dest="model_id", default="keelway-core:7b", help="Model ID")
    st_enf.add_argument("--strict", dest="strict_mode", action="store_true", help="Disable deterministic single-pass repair")
    st_enf.add_argument("--no-fail-closed", dest="no_fail_closed", action="store_true", help="Return SCHEMA_REJECTED instead of error")
    _add_common_healing_flags(st_enf)

    st_runs = st_sub.add_parser("runs", help="List persisted structured-output validation receipts")
    st_runs.add_argument("--limit", type=int, default=25, help="Maximum runs to return (default: 25)")
    _add_common_healing_flags(st_runs)

    existing_heal = getattr(subparsers, "_name_parser_map", {}).get("heal")
    if existing_heal is not None:
        hl = existing_heal
        for opt_act in hl._actions:
            if "--test" in getattr(opt_act, "option_strings", ()):
                opt_act.required = False
        hl_sub = hl.add_subparsers(dest="heal_action", required=False)
    else:
        hl = subparsers.add_parser("heal", help="Diagnose failed Flight-Tape traces and verify self-healing patches")
        hl_sub = hl.add_subparsers(dest="heal_action", required=True)

    hl_diag = hl_sub.add_parser("diagnose", help="Run autonomous root-cause diagnosis on a failed trace or step")
    hl_diag.add_argument("--trace-id", default=None, help="Existing Flight-Tape trace ID")
    hl_diag.add_argument("--workflow-name", "--workflow", dest="workflow_name", default="invoice-triage-agent", help="Workflow name")
    hl_diag.add_argument("--node-name", default=None, help="Failed node name")
    hl_diag.add_argument("--failure-hint", "--error-message", dest="error_message", default=None, help="Failure error message or hint")
    hl_diag.add_argument("--prompt-text", default=None, help="Prompt text for synthetic step diagnosis")
    hl_diag.add_argument("--output-text", default=None, help="Output text for synthetic step diagnosis")
    hl_diag.add_argument("--failed-step-json", default=None, help="Optional JSON object describing failed_step")
    _add_common_healing_flags(hl_diag)

    hl_apply = hl_sub.add_parser("apply", help="Verify self-healing patch replay and promote Golden Eval case")
    hl_apply.add_argument("diagnosis_id_pos", nargs="?", default=None, help="Diagnosis ID to apply")
    hl_apply.add_argument("--diagnosis-id", dest="diagnosis_id_flag", default=None, help="Diagnosis ID to apply")
    hl_apply.add_argument("--no-promote-eval", action="store_true", help="Skip Golden Eval regression case promotion")
    hl_apply.add_argument("--eval-title", default=None, help="Optional title for promoted Golden Eval case")
    _add_common_healing_flags(hl_apply)

    hl_list = hl_sub.add_parser("list", help="List persisted self-healing diagnoses")
    hl_list.add_argument("--limit", type=int, default=25, help="Maximum diagnoses to return (default: 25)")
    _add_common_healing_flags(hl_list)


def _resolve_normalize_payload(args: argparse.Namespace) -> Any:
    explicit_json = getattr(args, "payload_json", None)
    if explicit_json is not None:
        return json.loads(explicit_json)
    raw = str(getattr(args, "raw_payload", "") or "")
    stripped = raw.strip()
    fmt = str(getattr(args, "provider_format", "deepseek_opencore") or "").strip().lower()
    if stripped.startswith("{") and fmt != "deepseek_opencore":
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            return raw
    return raw


def dispatch_healing_cli(args: argparse.Namespace) -> Optional[int]:
    """Dispatch `keelway structured` and `keelway heal` CLI subcommands."""
    cmd = getattr(args, "command", None)
    if cmd not in ("structured", "heal") or (cmd == "heal" and getattr(args, "heal_action", None) is None):
        return None

    ws_id = str(getattr(args, "workspace_id", "default") or "default")
    as_json = bool(getattr(args, "json", False))
    engine = SQLiteStructuredHealingEngine(db_path=getattr(args, "db_path", None))
    try:
        if cmd == "structured":
            act = getattr(args, "structured_action", None)
            if act == "normalize":
                res = engine.normalize_content_blocks(
                    workspace_id=ws_id,
                    provider_format=str(getattr(args, "provider_format", "deepseek_opencore")),
                    raw_payload=_resolve_normalize_payload(args),
                    model_id=str(getattr(args, "model_id", "keelway-core:7b")),
                )
                print(
                    json.dumps(res, indent=2) if as_json
                    else f"[NORMALIZED] {res['provider_format']} blocks={res['block_count']} dlp_redactions={res['dlp_redactions']}"
                )
                return 0
            if act == "enforce":
                schema_obj = json.loads(str(getattr(args, "schema_json", _DEFAULT_CLI_SCHEMA)))
                res = engine.enforce_structured_output(
                    workspace_id=ws_id,
                    json_schema=schema_obj,
                    raw_output=str(getattr(args, "raw_output", "")),
                    schema_name=str(getattr(args, "schema_name", "AgentDecisionContract")),
                    provider_format=str(getattr(args, "provider_format", "deepseek_opencore")),
                    model_id=str(getattr(args, "model_id", "keelway-core:7b")),
                    strict_mode=bool(getattr(args, "strict_mode", False)),
                    fail_closed=not bool(getattr(args, "no_fail_closed", False)),
                )
                print(
                    json.dumps(res, indent=2) if as_json
                    else f"[{res['status']}] {res['run_id']} schema={res['schema_name']} repaired={res['repair_applied']}"
                )
                return 0
            if act == "runs":
                res = engine.list_structured_runs(workspace_id=ws_id, limit=int(getattr(args, "limit", 25)))
                print(json.dumps(res, indent=2) if as_json else f"Structured Runs [{ws_id}] count={res['count']}")
                return 0

        if cmd == "heal":
            act = getattr(args, "heal_action", None)
            if act == "diagnose":
                raw_step = getattr(args, "failed_step_json", None)
                failed_step: Optional[Dict[str, Any]] = None
                if raw_step:
                    failed_step = json.loads(raw_step)
                elif any(getattr(args, f, None) is not None for f in ("node_name", "error_message", "prompt_text", "output_text")):
                    failed_step = {
                        "node_name": getattr(args, "node_name", None) or "extract_invoice_fields",
                        "prompt_text": getattr(args, "prompt_text", None) or "Extract structured fields.",
                        "output_text": getattr(args, "output_text", None) or "",
                        "error_message": getattr(args, "error_message", None) or "",
                    }
                res = engine.diagnose_failure(
                    workspace_id=ws_id,
                    trace_id=getattr(args, "trace_id", None),
                    workflow_name=str(getattr(args, "workflow_name", "invoice-triage-agent")),
                    failed_step=failed_step,
                )
                print(
                    json.dumps(res, indent=2) if as_json
                    else f"[{res['status']}] {res['diagnosis_id']} class={res['failure_class']} conf={res['confidence']}"
                )
                return 0
            if act == "apply":
                diag_id = str(getattr(args, "diagnosis_id_flag", None) or getattr(args, "diagnosis_id_pos", None) or "").strip()
                res = engine.apply_healing_patch(
                    workspace_id=ws_id,
                    diagnosis_id=diag_id,
                    promote_to_eval=not bool(getattr(args, "no_promote_eval", False)),
                    eval_title=getattr(args, "eval_title", None),
                )
                print(
                    json.dumps(res, indent=2) if as_json
                    else f"[VERIFIED_HEALED] {res['diagnosis']['diagnosis_id']} replay={res['diagnosis']['verification_replay_trace_id']}"
                )
                return 0
            if act == "list":
                res = engine.list_diagnoses(workspace_id=ws_id, limit=int(getattr(args, "limit", 25)))
                print(json.dumps(res, indent=2) if as_json else f"Self-Healing Diagnoses [{ws_id}] count={res['count']}")
                return 0
    except StructuredSchemaRejectedError as exc:
        err_obj = {"error": str(exc), "code": "structured_schema_rejected", "run": exc.run_record}
        print(json.dumps(err_obj, indent=2) if as_json else f"[-] {exc}")
        return 1
    except SelfHealingNotFoundError as exc:
        msg = str(exc.args[0] if exc.args else exc)
        print(json.dumps({"error": msg, "code": "not_found"}, indent=2) if as_json else f"[-] {msg}")
        return 1
    except (StructuredHealingValidationError, ValueError, json.JSONDecodeError, OSError) as exc:
        print(json.dumps({"error": str(exc), "code": "healing_validation_error"}, indent=2) if as_json else f"[-] {exc}")
        return 1
    finally:
        engine.close()

    return None
