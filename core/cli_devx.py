"""
Keelway Sovereign CLI Phase 11A Subcommands (`traces`, `trace-eval`, `migrate-langgraph`).

Registered and dispatched via `core.cli_runtime` supporting `--workspace` / `--workspace-id`,
`--db-path`, and `--json` for OTel GenAI Flight-Tape ingestion, time-travel replay, golden eval
dataset promotion, and 100% static LangGraph-to-KFlow AST/Regex migration.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional


def _add_common_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--workspace",
        "--workspace-id",
        dest="workspace_id",
        default="default",
        help="Target workspace identifier (default: default)",
    )
    parser.add_argument("--db-path", default=None, help="Optional SQLite database path override")
    parser.add_argument("--json", action="store_true", help="Emit JSON output")


def register_devx_cli_subparsers(subparsers: argparse._SubParsersAction) -> None:
    """Register `traces`, `trace-eval`, and `migrate-langgraph` sovereign CLI subcommands."""
    tr = subparsers.add_parser(
        "traces",
        help="Ingest OTel GenAI / LangGraph spans, list Flight Tapes, and run counterfactual time-travel replays",
    )
    tr_sub = tr.add_subparsers(dest="traces_command", required=True)

    tr_ingest = tr_sub.add_parser("ingest", help="Ingest flat spans or OTLP resourceSpans JSON with DLP scrubbing")
    tr_ingest.add_argument("--file", required=True, help="Path to spans or OTLP resourceSpans JSON file")
    tr_ingest.add_argument("--trace-id", default=None, help="Optional explicit trace identifier")
    tr_ingest.add_argument("--workflow-name", default=None, help="Optional workflow name override")
    tr_ingest.add_argument("--source-framework", default=None, help="Source framework tag (default: opentelemetry_genai)")
    _add_common_flags(tr_ingest)

    tr_list = tr_sub.add_parser("list", help="List persisted Flight-Tape traces in workspace")
    tr_list.add_argument("--limit", type=int, default=20, help="Maximum traces to return (default: 20)")
    _add_common_flags(tr_list)

    tr_replay = tr_sub.add_parser("replay", help="Fork and replay a Flight Tape from a chosen step index")
    tr_replay.add_argument("--trace-id", required=True, help="Parent trace identifier to fork from")
    tr_replay.add_argument("--from-step", dest="from_step", type=int, default=0, help="Step index to fork from")
    tr_replay.add_argument("--override-model", default=None, help="Counterfactual model override (e.g., keelway-core:7b)")
    tr_replay.add_argument("--override-prompt", default=None, help="Counterfactual prompt override at fork step")
    tr_replay.add_argument("--override-state", default=None, help="Optional JSON object state override")
    _add_common_flags(tr_replay)

    te = subparsers.add_parser(
        "trace-eval",
        help="Promote Flight-Tape traces into golden regression eval dataset cases and list promoted cases",
    )
    te_sub = te.add_subparsers(dest="trace_eval_command", required=True)

    te_promote = te_sub.add_parser("promote", help="Promote a recorded Flight-Tape trace to a golden eval case")
    te_promote.add_argument("--trace-id", required=True, help="Source trace identifier to promote")
    te_promote.add_argument("--title", default=None, help="Optional eval case title")
    te_promote.add_argument("--expected", action="append", default=[], help="Expected output substring (repeatable)")
    te_promote.add_argument("--forbidden", action="append", default=[], help="Forbidden output substring (repeatable)")
    te_promote.add_argument("--created-by", default="owner", help="Creator principal identifier")
    _add_common_flags(te_promote)

    te_list = te_sub.add_parser("list", help="List promoted golden evaluation dataset cases")
    _add_common_flags(te_list)

    mg = subparsers.add_parser(
        "migrate-langgraph",
        help="Statically analyze Python/TypeScript LangGraph StateGraph source into a KFlow DAG blueprint",
    )
    src_group = mg.add_mutually_exclusive_group(required=True)
    src_group.add_argument("--file", default=None, help="Path to Python (.py) or TypeScript (.ts) LangGraph source file")
    src_group.add_argument("--code", default=None, help="Inline LangGraph source code snippet")
    mg.add_argument("--lang", choices=["python", "typescript"], default=None, help="Source language override")
    mg.add_argument("--name", default=None, help="Optional KFlow workflow name")
    _add_common_flags(mg)


def _load_ingest_payload(file_path: str) -> Dict[str, Any]:
    raw_text = Path(file_path).read_text(encoding="utf-8")
    parsed = json.loads(raw_text)
    if isinstance(parsed, list):
        return {"spans": parsed}
    if isinstance(parsed, dict):
        return parsed
    raise ValueError("Trace JSON file must contain a JSON array of spans or an OTLP JSON object.")


def dispatch_devx_cli(args: argparse.Namespace) -> Optional[int]:
    """Dispatch `traces`, `trace-eval`, and `migrate-langgraph` CLI subcommands. Returns exit code or None."""
    cmd = getattr(args, "command", None)

    if cmd == "traces":
        from core.platform.flight_tape import SQLiteFlightTapeEngine

        sub = getattr(args, "traces_command", None)
        ws_id = str(getattr(args, "workspace_id", "default") or "default")
        as_json = bool(getattr(args, "json", False))
        engine = SQLiteFlightTapeEngine(db_path=getattr(args, "db_path", None))
        try:
            if sub == "ingest":
                doc = _load_ingest_payload(str(args.file))
                res_spans = doc.get("resource_spans") if doc.get("resource_spans") is not None else doc.get("resourceSpans")
                wf_name = str(getattr(args, "workflow_name", None) or doc.get("workflow_name") or "agent-trace")
                fw_name = str(
                    getattr(args, "source_framework", None) or doc.get("source_framework") or "opentelemetry_genai"
                )
                tid = getattr(args, "trace_id", None) or doc.get("trace_id")
                tape = engine.ingest_traces(
                    workspace_id=ws_id,
                    workflow_name=wf_name,
                    source_framework=fw_name,
                    spans=doc.get("spans"),
                    resource_spans=res_spans,
                    trace_id=tid,
                )
                if as_json:
                    print(json.dumps(tape, indent=2))
                else:
                    print(
                        f"[+] Ingested Flight Tape {tape['trace_id']} [{ws_id}] steps={tape['total_steps']} "
                        f"tokens={tape['total_tokens']} cost=${tape['total_cost_usd']:.6f} "
                        f"dlp_redactions={tape['dlp_redactions']} sha256={tape['tape_sha256'][:23]}..."
                    )
                return 0

            if sub == "list":
                listing = engine.list_tapes(workspace_id=ws_id, limit=int(getattr(args, "limit", 20)))
                if as_json:
                    print(json.dumps(listing, indent=2))
                else:
                    print(f"Keelway Flight Tapes [{ws_id}] total={listing['total_tapes']}:")
                    for t in listing["tapes"]:
                        print(
                            f"  - {t['trace_id']} ({t['workflow_name']}) steps={t['total_steps']} "
                            f"cost=${t['total_cost_usd']:.6f} status={t['status']}"
                        )
                return 0

            if sub == "replay":
                raw_state_str = getattr(args, "override_state", None)
                state_override: Optional[Dict[str, Any]] = json.loads(raw_state_str) if raw_state_str else None
                forked = engine.replay_tape(
                    workspace_id=ws_id,
                    trace_id=str(args.trace_id),
                    from_step_index=int(getattr(args, "from_step", 0)),
                    override_prompt=getattr(args, "override_prompt", None),
                    override_model=getattr(args, "override_model", None),
                    override_state=state_override,
                )
                if as_json:
                    print(json.dumps(forked, indent=2))
                else:
                    print(
                        f"[+] Replayed Flight Tape {forked['trace_id']} (parent={forked['parent_trace_id']}, "
                        f"cached_reused={forked['cached_steps_reused']}, cost_delta=${forked['cost_delta_usd']:.6f})"
                    )
                return 0
        except (OSError, json.JSONDecodeError, KeyError, ValueError) as exc:
            print(json.dumps({"error": str(exc)}, indent=2) if as_json else f"[-] Traces error: {exc}")
            return 1
        finally:
            engine.close()

    if cmd == "trace-eval":
        from core.platform.flight_tape import SQLiteFlightTapeEngine

        sub = getattr(args, "trace_eval_command", None)
        ws_id = str(getattr(args, "workspace_id", "default") or "default")
        as_json = bool(getattr(args, "json", False))
        engine = SQLiteFlightTapeEngine(db_path=getattr(args, "db_path", None))
        try:
            if sub == "promote":
                exp_list: List[str] = list(getattr(args, "expected", None) or [])
                forb_list: List[str] = list(getattr(args, "forbidden", None) or [])
                case = engine.promote_trace_to_eval(
                    workspace_id=ws_id,
                    trace_id=str(args.trace_id),
                    title=getattr(args, "title", None),
                    expected_substrings=exp_list if exp_list else None,
                    forbidden_substrings=forb_list if forb_list else None,
                    created_by=str(getattr(args, "created_by", "owner")),
                )
                if as_json:
                    print(json.dumps(case, indent=2))
                else:
                    print(
                        f"[+] Promoted eval case {case['case_id']} from trace {case['source_trace_id']} "
                        f"(mocks={len(case['pinned_tool_mocks'])}, sha256={case['case_sha256'][:23]}...)"
                    )
                return 0

            if sub == "list":
                dataset = engine.list_eval_cases(workspace_id=ws_id)
                if as_json:
                    print(json.dumps(dataset, indent=2))
                else:
                    print(f"Keelway Golden Eval Dataset [{ws_id}] total={dataset['total_cases']}:")
                    for c in dataset["cases"]:
                        print(f"  - {c['case_id']} trace={c['source_trace_id']} title={c['title']}")
                return 0
        except (KeyError, ValueError) as exc:
            print(json.dumps({"error": str(exc)}, indent=2) if as_json else f"[-] Trace-eval error: {exc}")
            return 1
        finally:
            engine.close()

    if cmd == "migrate-langgraph":
        from core.platform.langgraph_migrator import LangGraphMigrator

        ws_id = str(getattr(args, "workspace_id", "default") or "default")
        as_json = bool(getattr(args, "json", False))
        file_arg = getattr(args, "file", None)
        code_arg = getattr(args, "code", None)
        lang_arg = getattr(args, "lang", None)
        try:
            if file_arg:
                src_path = Path(str(file_arg))
                source_code = src_path.read_text(encoding="utf-8")
                eff_lang = lang_arg or ("typescript" if src_path.suffix.lower() in (".ts", ".tsx") else "python")
            else:
                source_code = str(code_arg or "")
                eff_lang = lang_arg or "python"

            report = LangGraphMigrator().migrate_source(
                source_code=source_code,
                source_language=eff_lang,
                workflow_name=getattr(args, "name", None),
                workspace_id=ws_id,
            )
            if as_json:
                print(json.dumps(report, indent=2))
            else:
                print(
                    f"[+] Migrated LangGraph -> KFlow '{report['workflow_name']}' ({report['source_language']}): "
                    f"nodes={len(report['nodes'])} cycles={report['cycles_detected']} "
                    f"p10_gates={len(report['p10_gates_injected'])} warnings={len(report['legacy_warnings'])}"
                )
            return 0
        except (OSError, ValueError) as exc:
            print(json.dumps({"error": str(exc)}, indent=2) if as_json else f"[-] LangGraph migration error: {exc}")
            return 1

    return None
