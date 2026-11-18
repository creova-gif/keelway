"""
Keelway Sovereign CLI Phase 14 Step-Through Debugger Subcommands (`keelway debug`).

Registered and dispatched via `core.cli_runtime` supporting `--workspace` / `--workspace-id`,
`--db-path`, and `--json` for conditional gutter breakpoints, paused frame stepping
(`step_over`, `step_into`, `continue`, `mutate_state`), DLP secret guards, and 4D CodeLens.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.platform.step_debugger import (
    DebuggerPolicyViolationError,
    SQLiteStepDebuggerEngine,
    VALID_CONDITION_TYPES,
    VALID_STEP_ACTIONS,
)


def _add_common_debug_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--workspace",
        "--workspace-id",
        dest="workspace_id",
        default="default",
        help="Target workspace identifier (default: default)",
    )
    parser.add_argument("--db-path", default=None, help="Optional SQLite database path override")
    parser.add_argument("--json", action="store_true", help="Emit JSON output")


def register_debugger_cli_subparsers(subparsers: argparse._SubParsersAction) -> None:
    """Register `keelway debug` (`breakpoint`, `session`, `codelens`) sovereign CLI subcommands."""
    dbg = subparsers.add_parser(
        "debug",
        help="Manage live conditional breakpoints, paused frame stepping, and 4D IDE CodeLens",
    )
    dbg_sub = dbg.add_subparsers(dest="debug_group", required=True)

    bp = dbg_sub.add_parser("breakpoint", help="Create, list, and delete conditional gutter breakpoints")
    bp_sub = bp.add_subparsers(dest="breakpoint_action", required=True)

    bp_set = bp_sub.add_parser("set", help="Set a conditional or line-matched debugger breakpoint")
    bp_set.add_argument("--workflow-id", default="WF-STUDIO-01", help="Target workflow ID (default: WF-STUDIO-01)")
    bp_set.add_argument(
        "--condition",
        "--condition-type",
        dest="condition_type",
        choices=list(VALID_CONDITION_TYPES),
        default="always",
        help="Breakpoint trigger condition",
    )
    bp_set.add_argument("--threshold", type=float, default=None, help="Numeric threshold for cost/score conditions")
    bp_set.add_argument("--node-id", default=None, help="Optional KFlow node identifier filter")
    bp_set.add_argument("--file", dest="file_path", default="workflows/refund_agent.py", help="Source file path")
    bp_set.add_argument("--line", "--line-number", dest="line_number", type=int, default=None, help="Source line number")
    bp_set.add_argument("--label", default=None, help="Optional human-readable breakpoint label")
    bp_set.add_argument("--disabled", action="store_true", help="Create breakpoint in disabled state")
    _add_common_debug_flags(bp_set)

    bp_list = bp_sub.add_parser("list", help="List persisted debugger breakpoints")
    bp_list.add_argument("--workflow-id", default=None, help="Optional workflow identifier filter")
    _add_common_debug_flags(bp_list)

    bp_rm = bp_sub.add_parser("rm", help="Delete a debugger breakpoint by ID")
    bp_rm.add_argument("--breakpoint-id", default=None, help="Breakpoint identifier (bp-...)")
    bp_rm.add_argument("breakpoint_id_pos", nargs="?", default=None, help="Optional positional breakpoint ID")
    _add_common_debug_flags(bp_rm)

    sess = dbg_sub.add_parser("session", help="Start, list, and step live paused debugger sessions")
    sess_sub = sess.add_subparsers(dest="session_action", required=True)

    s_start = sess_sub.add_parser("start", help="Start a workflow debug session and pause on matching breakpoints")
    s_start.add_argument("--workflow-id", default="WF-STUDIO-01", help="Target workflow ID (default: WF-STUDIO-01)")
    s_start.add_argument("--steps-json", default=None, help="Optional JSON array of workflow steps")
    s_start.add_argument("--initial-state-json", default=None, help="Optional JSON object of initial variables")
    _add_common_debug_flags(s_start)

    s_list = sess_sub.add_parser("list", help="List recent debugger sessions")
    s_list.add_argument("--limit", type=int, default=20, help="Maximum sessions to return (default: 20)")
    _add_common_debug_flags(s_list)

    s_step = sess_sub.add_parser("step", help="Step or mutate a paused debugger session")
    s_step.add_argument("--session-id", required=True, help="Target debugger session ID (dbg-...)")
    s_step.add_argument("--action", choices=list(VALID_STEP_ACTIONS), default="step_over", help="Debugger step action")
    s_step.add_argument("--patch-json", default=None, help="Optional JSON object state patch (DLP-guarded)")
    _add_common_debug_flags(s_step)

    cl = dbg_sub.add_parser("codelens", help="Inspect 4D routing CodeLens and VS Code / Cursor attach URIs")
    cl.add_argument("--workflow-id", default="WF-STUDIO-01", help="Target workflow ID (default: WF-STUDIO-01)")
    cl.add_argument("--file", dest="file_path", default="workflows/refund_agent.py", help="Source file path")
    cl.add_argument("--source", default=None, help="Optional inline Python or TypeScript source code")
    _add_common_debug_flags(cl)


def dispatch_debugger_cli(args: argparse.Namespace) -> Optional[int]:
    """Dispatch `keelway debug` CLI subcommands. Returns process exit code or None."""
    if getattr(args, "command", None) != "debug":
        return None

    group = getattr(args, "debug_group", None)
    ws_id = str(getattr(args, "workspace_id", "default") or "default")
    as_json = bool(getattr(args, "json", False))
    engine = SQLiteStepDebuggerEngine(db_path=getattr(args, "db_path", None))
    try:
        if group == "breakpoint":
            bp_act = getattr(args, "breakpoint_action", None)
            if bp_act == "set":
                res = engine.set_breakpoint(
                    workspace_id=ws_id,
                    workflow_id=str(getattr(args, "workflow_id", "WF-STUDIO-01")),
                    node_id=getattr(args, "node_id", None),
                    file_path=str(getattr(args, "file_path", "workflows/refund_agent.py")),
                    line_number=getattr(args, "line_number", None),
                    condition_type=str(getattr(args, "condition_type", "always")),
                    threshold=getattr(args, "threshold", None),
                    enabled=not bool(getattr(args, "disabled", False)),
                    label=getattr(args, "label", None),
                )
                print(
                    json.dumps(res, indent=2) if as_json
                    else f"[+] Breakpoint {res['breakpoint_id']} [{ws_id}] {res['condition_type']} ({res['label']})"
                )
                return 0
            if bp_act == "list":
                res = engine.list_breakpoints(workspace_id=ws_id, workflow_id=getattr(args, "workflow_id", None))
                if as_json:
                    print(json.dumps(res, indent=2))
                else:
                    print(f"Keelway Debugger Breakpoints [{ws_id}] count={res['count']}:")
                    for b in res["breakpoints"]:
                        print(f"  - {b['breakpoint_id']} [{b['condition_type']}] {b['label']}")
                return 0
            if bp_act == "rm":
                bp_id = getattr(args, "breakpoint_id", None) or getattr(args, "breakpoint_id_pos", None) or ""
                res = engine.delete_breakpoint(workspace_id=ws_id, breakpoint_id=str(bp_id))
                print(json.dumps(res, indent=2) if as_json else f"[+] Deleted breakpoint {res['breakpoint_id']} [{ws_id}].")
                return 0

        if group == "session":
            s_act = getattr(args, "session_action", None)
            if s_act == "start":
                raw_steps = getattr(args, "steps_json", None)
                steps: Optional[List[Dict[str, Any]]] = json.loads(raw_steps) if raw_steps else None
                raw_init = getattr(args, "initial_state_json", None)
                init_state: Optional[Dict[str, Any]] = json.loads(raw_init) if raw_init else None
                res = engine.start_session(
                    workspace_id=ws_id,
                    workflow_id=str(getattr(args, "workflow_id", "WF-STUDIO-01")),
                    steps=steps,
                    initial_state=init_state,
                )
                print(
                    json.dumps(res, indent=2) if as_json
                    else f"[{res['status']}] Session {res['session_id']} step={res['current_step_index'] + 1}/{res['total_steps']} sha256={res['frame_sha256'][:16]}..."
                )
                return 0
            if s_act == "list":
                res = engine.list_sessions(workspace_id=ws_id, limit=int(getattr(args, "limit", 20)))
                if as_json:
                    print(json.dumps(res, indent=2))
                else:
                    print(f"Keelway Debugger Sessions [{ws_id}] count={res['count']}:")
                    for s in res["sessions"]:
                        print(f"  - {s['session_id']} [{s['status']}] step={s['current_step_index'] + 1}/{s['total_steps']}")
                return 0
            if s_act == "step":
                raw_patch = getattr(args, "patch_json", None)
                patch_obj: Optional[Dict[str, Any]] = json.loads(raw_patch) if raw_patch else None
                res = engine.step_session(
                    workspace_id=ws_id,
                    session_id=str(getattr(args, "session_id", "")),
                    action=str(getattr(args, "action", "step_over")),
                    state_patch=patch_obj,
                )
                print(
                    json.dumps(res, indent=2) if as_json
                    else f"[{res['status']}] Stepped {res['session_id']} ({args.action}) step={res['current_step_index'] + 1}/{res['total_steps']} depth={res['step_depth']}"
                )
                return 0

        if group == "codelens":
            file_str = str(getattr(args, "file_path", "workflows/refund_agent.py"))
            source_code: Optional[str] = getattr(args, "source", None)
            if source_code is None and Path(file_str).is_file():
                source_code = Path(file_str).read_text(encoding="utf-8")
            res = engine.get_codelens(
                workspace_id=ws_id,
                workflow_id=str(getattr(args, "workflow_id", "WF-STUDIO-01")),
                file_path=file_str,
                source_code=source_code,
            )
            if as_json:
                print(json.dumps(res, indent=2))
            else:
                print(f"Keelway 4D CodeLens [{ws_id}] {res['file_path']} ({len(res['lenses'])} lenses):")
                for lens in res["lenses"]:
                    print(f"  - L{lens['line_start']} {lens['symbol']}: {lens['model_checkpoint']} ({lens['provenance_4d']})")
            return 0
    except (DebuggerPolicyViolationError, KeyError, ValueError, json.JSONDecodeError, OSError) as exc:
        code = "policy_violation" if isinstance(exc, DebuggerPolicyViolationError) else "debugger_error"
        print(json.dumps({"error": str(exc), "code": code}, indent=2) if as_json else f"[-] Debugger error: {exc}")
        return 1
    finally:
        engine.close()

    return None
