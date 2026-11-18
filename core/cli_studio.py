"""
Keelway Sovereign CLI Phase 12A Studio Subcommands (`kflow-sync`, `blast-radius`, `prompt-gate`).

Registered and dispatched via `core.cli_runtime` supporting `--workspace` / `--workspace-id`,
`--db-path`, and `--json` for static Python/TypeScript KFlow Code <-> Graph AST synchronization,
Seatbelt/air-gap blast-radius boundary receipts, and deterministic Prompt/Schema Regression Gates.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.platform.kflow_bidirectional_sync import (
    KFlowBidirectionalSyncEngine,
    PayloadTooLargeError,
)
from core.platform.sandbox_blast_radius import SQLiteSandboxBlastRadiusEngine


def _add_common_studio_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--workspace",
        "--workspace-id",
        dest="workspace_id",
        default="default",
        help="Target workspace identifier (default: default)",
    )
    parser.add_argument("--db-path", default=None, help="Optional SQLite database path override")
    parser.add_argument("--json", action="store_true", help="Emit JSON output")


def register_studio_cli_subparsers(subparsers: argparse._SubParsersAction) -> None:
    """Register `kflow-sync`, `blast-radius`, and `prompt-gate` sovereign CLI subcommands."""
    ks = subparsers.add_parser(
        "kflow-sync",
        help="Synchronize KFlow Python/TypeScript source code and topological DAG nodes bidirectionally",
    )
    ks.add_argument(
        "--direction",
        choices=["code_to_graph", "graph_to_code"],
        default="code_to_graph",
        help="Sync direction (default: code_to_graph)",
    )
    ks.add_argument(
        "--language",
        "--lang",
        dest="language",
        choices=["python", "typescript"],
        default=None,
        help="Target source language (python or typescript)",
    )
    ks.add_argument("--workflow-id", default="WF-STUDIO-01", help="Workflow identifier (default: WF-STUDIO-01)")
    ks.add_argument("--source", default=None, help="Inline Python or TypeScript source code")
    ks.add_argument("--file", default=None, help="Path to source file (.py/.ts) or nodes JSON file")
    ks.add_argument("--nodes-json", default=None, help="Inline JSON array of KFlow nodes for graph_to_code")
    ks.add_argument("--persist", action="store_true", help="Persist sync receipt in SQLite WAL")
    _add_common_studio_flags(ks)

    br = subparsers.add_parser(
        "blast-radius",
        help="Record and inspect OS Seatbelt & air-gap sandbox blast-radius boundary receipts",
    )
    br_sub = br.add_subparsers(dest="blast_radius_command", required=True)

    br_rec = br_sub.add_parser("record", help="Record an OS sandbox blast-radius telemetry receipt")
    br_rec.add_argument("--trace-id", default=None, help="Optional Flight-Tape trace identifier")
    br_rec.add_argument("--workflow-id", default=None, help="Optional KFlow workflow identifier")
    br_rec.add_argument("--fs-read", action="append", default=[], help="Workspace file path read (repeatable)")
    br_rec.add_argument("--fs-write", action="append", default=[], help="Workspace file path written (repeatable)")
    br_rec.add_argument("--blocked-path", action="append", default=[], help="Blocked host path attempt (repeatable)")
    br_rec.add_argument("--egress-attempts", type=int, default=0, help="Outbound network egress attempts")
    br_rec.add_argument("--blocked-host", action="append", default=[], help="Blocked egress host (repeatable)")
    br_rec.add_argument("--p10-gates", type=int, default=0, help="Number of P-10 human governance gates triggered")
    br_rec.add_argument("--no-seatbelt", action="store_true", help="Mark receipt as non-seatbelted")
    _add_common_studio_flags(br_rec)

    br_list = br_sub.add_parser("list", help="List persisted sandbox blast-radius receipts")
    br_list.add_argument("--trace-id", default=None, help="Optional trace identifier filter")
    br_list.add_argument("--limit", type=int, default=25, help="Maximum audits to return (default: 25)")
    _add_common_studio_flags(br_list)

    pg = subparsers.add_parser(
        "prompt-gate",
        help="Evaluate candidate prompts/models against Golden Eval datasets and list regression gate runs",
    )
    pg_sub = pg.add_subparsers(dest="prompt_gate_command", required=True)

    pg_eval = pg_sub.add_parser("evaluate", help="Run deterministic Prompt/Schema Regression Gate")
    pg_eval.add_argument("--prompt-version", default="p-15", help="Candidate prompt version tag (default: p-15)")
    pg_eval.add_argument("--model-id", default="keelway-core:7b", help="Candidate model ID (default: keelway-core:7b)")
    pg_eval.add_argument("--prompt-text", default="", help="Candidate system/task prompt text")
    pg_eval.add_argument("--required-key", action="append", default=[], help="Required JSON output key (repeatable)")
    pg_eval.add_argument("--min-pass-rate", type=float, default=0.9, help="Minimum pass rate threshold (default: 0.9)")
    _add_common_studio_flags(pg_eval)

    pg_list = pg_sub.add_parser("list", help="List historical Prompt Regression Gate runs")
    pg_list.add_argument("--limit", type=int, default=20, help="Maximum runs to return (default: 20)")
    _add_common_studio_flags(pg_list)


def _parse_nodes_payload(raw_json: str) -> List[Dict[str, Any]]:
    parsed = json.loads(raw_json)
    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, dict) and isinstance(parsed.get("nodes"), list):
        return parsed["nodes"]
    raise ValueError("--nodes-json must contain a JSON array of node objects.")


def dispatch_studio_cli(args: argparse.Namespace) -> Optional[int]:
    """Dispatch `kflow-sync`, `blast-radius`, and `prompt-gate` CLI subcommands. Returns exit code or None."""
    cmd = getattr(args, "command", None)

    if cmd == "kflow-sync":
        ws_id = str(getattr(args, "workspace_id", "default") or "default")
        as_json = bool(getattr(args, "json", False))
        direction = str(getattr(args, "direction", "code_to_graph"))
        lang_arg = getattr(args, "language", None)
        file_arg = getattr(args, "file", None)
        source_arg = getattr(args, "source", None)
        nodes_json_arg = getattr(args, "nodes_json", None)
        engine = KFlowBidirectionalSyncEngine(db_path=getattr(args, "db_path", None))
        try:
            eff_lang = lang_arg or "python"
            source_code: Optional[str] = source_arg
            nodes_list: Optional[List[Dict[str, Any]]] = None

            if file_arg:
                fpath = Path(str(file_arg))
                file_text = fpath.read_text(encoding="utf-8")
                if direction == "graph_to_code" and nodes_json_arg is None:
                    nodes_list = _parse_nodes_payload(file_text)
                else:
                    source_code = file_text
                    if lang_arg is None and fpath.suffix.lower() in (".ts", ".tsx"):
                        eff_lang = "typescript"

            if nodes_json_arg is not None:
                nodes_list = _parse_nodes_payload(str(nodes_json_arg))

            res = engine.sync(
                workspace_id=ws_id,
                direction=direction,
                language=eff_lang,
                workflow_id=str(getattr(args, "workflow_id", "WF-STUDIO-01")),
                source_code=source_code,
                nodes=nodes_list,
                persist=bool(getattr(args, "persist", False)),
            )
            if as_json:
                print(json.dumps(res, indent=2))
            else:
                print(
                    f"[+] KFlow Sync [{ws_id}] {res['direction']} ({res['language']}) "
                    f"workflow={res['workflow_id']} nodes={len(res['nodes'])} "
                    f"edges={len(res['edges'])} cycles={len(res['cycle_back_edges'])} "
                    f"p10_locked={len(res['p10_locked_nodes'])} sha256={res['sync_sha256'][:23]}..."
                )
            return 0
        except (OSError, json.JSONDecodeError, PayloadTooLargeError, SyntaxError, ValueError) as exc:
            print(json.dumps({"error": str(exc)}, indent=2) if as_json else f"[-] KFlow sync error: {exc}")
            return 1
        finally:
            engine.close()

    if cmd == "blast-radius":
        sub = getattr(args, "blast_radius_command", None)
        ws_id = str(getattr(args, "workspace_id", "default") or "default")
        as_json = bool(getattr(args, "json", False))
        engine_br = SQLiteSandboxBlastRadiusEngine(db_path=getattr(args, "db_path", None))
        try:
            if sub == "record":
                rec = engine_br.record_blast_radius(
                    workspace_id=ws_id,
                    trace_id=getattr(args, "trace_id", None),
                    workflow_id=getattr(args, "workflow_id", None),
                    fs_reads=list(getattr(args, "fs_read", None) or []),
                    fs_writes=list(getattr(args, "fs_write", None) or []),
                    blocked_paths=list(getattr(args, "blocked_path", None) or []),
                    egress_attempts=int(getattr(args, "egress_attempts", 0)),
                    blocked_egress_hosts=list(getattr(args, "blocked_host", None) or []),
                    p10_gates_triggered=int(getattr(args, "p10_gates", 0)),
                    seatbelted=not bool(getattr(args, "no_seatbelt", False)),
                )
                if as_json:
                    print(json.dumps(rec, indent=2))
                else:
                    print(
                        f"[+] Recorded Blast-Radius {rec['audit_id']} [{ws_id}] tier={rec['risk_tier']} "
                        f"syscalls={rec['syscalls_audited']} zero_egress={rec['zero_unapproved_egress']}"
                    )
                return 0

            if sub == "list":
                listing = engine_br.list_blast_radius_audits(
                    workspace_id=ws_id,
                    trace_id=getattr(args, "trace_id", None),
                    limit=int(getattr(args, "limit", 25)),
                )
                if as_json:
                    print(json.dumps(listing, indent=2))
                else:
                    print(f"Keelway Blast-Radius Audits [{ws_id}] count={listing['count']}:")
                    for a in listing["audits"]:
                        print(f"  - {a['audit_id']} tier={a['risk_tier']} syscalls={a['syscalls_audited']}")
                return 0
        except ValueError as exc:
            print(json.dumps({"error": str(exc)}, indent=2) if as_json else f"[-] Blast-radius error: {exc}")
            return 1
        finally:
            engine_br.close()

    if cmd == "prompt-gate":
        sub = getattr(args, "prompt_gate_command", None)
        ws_id = str(getattr(args, "workspace_id", "default") or "default")
        as_json = bool(getattr(args, "json", False))
        engine_pg = SQLiteSandboxBlastRadiusEngine(db_path=getattr(args, "db_path", None))
        try:
            if sub == "evaluate":
                req_keys = list(getattr(args, "required_key", None) or [])
                gate_res = engine_pg.evaluate_prompt_gate(
                    workspace_id=ws_id,
                    candidate_prompt_version=str(getattr(args, "prompt_version", "p-15")),
                    candidate_model_id=str(getattr(args, "model_id", "keelway-core:7b")),
                    candidate_prompt_text=str(getattr(args, "prompt_text", "")),
                    required_json_keys=req_keys if req_keys else None,
                    min_pass_rate=float(getattr(args, "min_pass_rate", 0.9)),
                )
                if as_json:
                    print(json.dumps(gate_res, indent=2))
                else:
                    print(
                        f"[{gate_res['verdict']}] Prompt Gate {gate_res['gate_run_id']} [{ws_id}] "
                        f"pass_rate={gate_res['pass_rate']:.2%} ({gate_res['passed_cases']}/{gate_res['cases_evaluated']}) "
                        f"dlp={gate_res['dlp_violations']} cost_delta=${gate_res['cost_delta_usd']:.6f}"
                    )
                return 0

            if sub == "list":
                runs = engine_pg.list_prompt_gate_runs(
                    workspace_id=ws_id,
                    limit=int(getattr(args, "limit", 20)),
                )
                if as_json:
                    print(json.dumps(runs, indent=2))
                else:
                    print(f"Keelway Prompt Regression Gate Runs [{ws_id}] count={runs['count']}:")
                    for r in runs["runs"]:
                        print(f"  - {r['gate_run_id']} [{r['verdict']}] {r['candidate_prompt_version']} pass_rate={r['pass_rate']}")
                return 0
        except ValueError as exc:
            print(json.dumps({"error": str(exc)}, indent=2) if as_json else f"[-] Prompt-gate error: {exc}")
            return 1
        finally:
            engine_pg.close()

    return None
