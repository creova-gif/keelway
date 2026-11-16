"""
Keelway Sovereign CLI Phase 18A Universal Coding-Agent Co-Harness & Worktree CI Gate
Subcommands (`harness`, `ci-gate`).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.agents.external import (
    EXTERNAL_AGENT_ADAPTERS,
    detect_external_agents,
    evaluate_hook_payload,
    get_adapter,
)
from core.platform.agent_coharness import (
    AgentCoharnessValidationError,
    ApprovalTicketConflictError,
    ApprovalTicketNotFoundError,
    SQLiteAgentCoharnessEngine,
)


def _add_common_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--workspace", "--workspace-id", dest="workspace_id", default="default", help="Target workspace ID")
    parser.add_argument("--db-path", default=None, help="Optional SQLite database path override")
    parser.add_argument("--json", action="store_true", help="Emit JSON output")


def _install_hook_file(install_dir: str, target_rel_path: str, content: str) -> str:
    base_dir = Path(install_dir).expanduser().resolve()
    dest_path = (base_dir / target_rel_path).resolve()
    if not dest_path.is_relative_to(base_dir):
        raise AgentCoharnessValidationError(f"Refusing to write hook outside install_dir '{base_dir}'.")
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    dest_path.write_text(content, encoding="utf-8")
    return str(dest_path)


def register_harness_cli_subparsers(subparsers: argparse._SubParsersAction) -> None:
    """Register `keelway harness` and `keelway ci-gate` sovereign CLI subcommands."""
    for name in ("harness", "ci-gate"):
        if name in subparsers._name_parser_map:
            subparsers._name_parser_map.pop(name, None)
            subparsers._choices_actions = [a for a in subparsers._choices_actions if getattr(a, "dest", None) != name]

    hr = subparsers.add_parser("harness", help="PreToolUse coding-agent co-harness & single-use P-10 approval tickets")
    hr_sub = hr.add_subparsers(dest="harness_action", required=True)

    hr_hooks = hr_sub.add_parser("hooks", help="Render or install PreToolUse hook configuration for Claude Code, Cursor, or Codex CLI")
    hr_hooks.add_argument("--agent", "--agent-host", dest="agent_host", choices=["claude_code", "cursor", "codex_cli"], default="claude_code", help="Coding agent host")
    hr_hooks.add_argument("--mode", choices=["enforce", "audit_only"], default="enforce", help="Interception enforcement mode")
    hr_hooks.add_argument("--install-dir", default=None, help="Optional directory to write the rendered hook config into")
    _add_common_flags(hr_hooks)

    hr_int = hr_sub.add_parser("intercept", help="Evaluate a PreToolUse tool invocation with DLP scrubbing & P-10 ticket binding")
    hr_int.add_argument("--agent", "--agent-host", dest="agent_host", choices=["claude_code", "cursor", "codex_cli"], default="claude_code", help="Coding agent host")
    hr_int.add_argument("--tool", "--tool-name", dest="tool_name", default="Bash", help="Tool name (default: Bash)")
    hr_int.add_argument("--command", dest="intercept_command", default="git push origin main", help="Command or tool payload to inspect")
    hr_int.add_argument("--ticket-id", default=None, help="Optional approved single-use P-10 ticket ID")
    _add_common_flags(hr_int)

    hr_tkts = hr_sub.add_parser("tickets", help="List single-use P-10 approval tickets")
    hr_tkts.add_argument("--status", default=None, help="Optional ticket status filter (PENDING, APPROVED, DENIED, CONSUMED)")
    hr_tkts.add_argument("--limit", type=int, default=25, help="Maximum tickets to return (default: 25)")
    _add_common_flags(hr_tkts)

    hr_dec = hr_sub.add_parser("decide", help="Approve or deny a pending P-10 ticket")
    hr_dec.add_argument("--ticket-id", required=True, help="Target P-10 ticket identifier")
    hr_dec.add_argument("--decision", choices=["APPROVED", "DENIED"], required=True, help="Reviewer decision")
    hr_dec.add_argument("--reviewer", default="lead-engineer", help="Reviewer identity")
    hr_dec.add_argument("--reason", default="Verified safe workspace scope", help="Decision rationale")
    _add_common_flags(hr_dec)

    hr_agents = hr_sub.add_parser("agents", help="Third-party coding-agent adapters (detect installed CLIs, evaluate native hook payloads)")
    hr_agents_sub = hr_agents.add_subparsers(dest="agents_action", required=True)

    hr_agents_det = hr_agents_sub.add_parser("detect", help="Probe registered agent adapters for installed CLIs")
    _add_common_flags(hr_agents_det)

    hr_agents_int = hr_agents_sub.add_parser("intercept", help="Evaluate a native agent hook payload (JSON) through Keelway policy")
    hr_agents_int.add_argument("--agent", "--agent-id", dest="agent_id", required=True,
                               choices=["claude_code", "codex_cli"], help="External agent adapter ID")
    hr_agents_int.add_argument("--payload", default=None,
                               help="Native hook payload JSON, '@path' to read a file, or '-' for stdin")
    hr_agents_int.add_argument("--mode", choices=["enforce", "audit_only"], default="audit_only",
                               help="Policy mode (default: audit_only)")
    hr_agents_int.add_argument("--format", dest="output_format", choices=["json", "claude-code"], default="json",
                               help="Output format: 'json' (default) or 'claude-code' PreToolUse permissionDecision JSON")
    _add_common_flags(hr_agents_int)

    cg = subparsers.add_parser("ci-gate", help="Parallel worktree candidate arena & hybrid unit-economics CI gate")
    cg_sub = cg.add_subparsers(dest="cigate_action", required=True)

    cg_eval = cg_sub.add_parser("evaluate", help="Evaluate parallel worktree candidates against safety, regression, and cost gates")
    cg_eval.add_argument("--workflow-name", "--workflow", dest="workflow_name", default="pr-worktree-arena", help="Workflow identifier")
    cg_eval.add_argument("--diff-summary", default="Refactor retry backoff & add unit test in core/platform/", help="Summary of candidate diff")
    cg_eval.add_argument("--min-eval-score", type=float, default=0.85, help="Minimum required evaluation score (0.0..1.0)")
    cg_eval.add_argument("--candidates-json", default=None, help="Optional JSON array of worktree candidate specs")
    _add_common_flags(cg_eval)

    cg_runs = cg_sub.add_parser("runs", help="List persisted worktree CI gate evaluation runs")
    cg_runs.add_argument("--limit", type=int, default=25, help="Maximum runs to return (default: 25)")
    _add_common_flags(cg_runs)


def _parse_candidates_arg(raw_json: Optional[str]) -> Optional[List[Dict[str, Any]]]:
    if not raw_json:
        return None
    parsed = json.loads(raw_json)
    if not isinstance(parsed, list):
        raise AgentCoharnessValidationError("--candidates-json must be a JSON array of candidate objects.")
    return parsed


def dispatch_harness_cli(args: argparse.Namespace) -> Optional[int]:
    """Dispatch `keelway harness` and `keelway ci-gate` CLI subcommands."""
    cmd = getattr(args, "command", None)
    if cmd not in ("harness", "ci-gate"):
        return None

    ws_id = str(getattr(args, "workspace_id", "default") or "default")
    as_json = bool(getattr(args, "json", False))
    engine = SQLiteAgentCoharnessEngine(db_path=getattr(args, "db_path", None))
    try:
        if cmd == "harness":
            act = getattr(args, "harness_action", None)
            if act == "hooks":
                res = engine.render_hook_manifest(
                    workspace_id=ws_id,
                    agent_host=str(getattr(args, "agent_host", "claude_code")),
                    mode=str(getattr(args, "mode", "enforce")),
                )
                install_dir = getattr(args, "install_dir", None)
                if install_dir:
                    res["installed_path"] = _install_hook_file(str(install_dir), res["target_config_path"], res["config_content"])
                print(json.dumps(res, indent=2) if as_json else f"[{res['agent_host']}] {res['target_config_path']} ({res['config_sha256']})")
                return 0

            if act == "intercept":
                res = engine.intercept_tool_call(
                    workspace_id=ws_id,
                    agent_host=str(getattr(args, "agent_host", "claude_code")),
                    tool_name=str(getattr(args, "tool_name", "Bash")),
                    command=str(getattr(args, "intercept_command", "git push origin main")),
                    ticket_id=getattr(args, "ticket_id", None),
                )
                print(json.dumps(res, indent=2) if as_json else f"[{res['verdict']}] reason={res['reason_code']} ticket={res['ticket_id']}")
                if res["verdict"] in ("ALLOW", "ALLOW_WITH_TICKET"):
                    return 0
                return 2 if res["verdict"] == "HOLD_TICKET" else 1

            if act == "tickets":
                res = engine.list_tickets(
                    workspace_id=ws_id,
                    status=getattr(args, "status", None),
                    limit=int(getattr(args, "limit", 25)),
                )
                print(json.dumps(res, indent=2) if as_json else f"Harness Tickets [{ws_id}] count={res['count']}")
                return 0

            if act == "decide":
                res = engine.decide_ticket(
                    workspace_id=ws_id,
                    ticket_id=str(args.ticket_id),
                    decision=str(args.decision),
                    reviewer=str(getattr(args, "reviewer", "lead-engineer")),
                    reason=str(getattr(args, "reason", "Verified safe workspace scope")),
                )
                print(json.dumps(res, indent=2) if as_json else f"[{res['status']}] {res['ticket_id']} reviewer={res['reviewer']}")
                return 0

            if act == "agents":
                agents_act = getattr(args, "agents_action", None)
                if agents_act == "detect":
                    detections = detect_external_agents()
                    adapters_meta = {k: v.capabilities() for k, v in EXTERNAL_AGENT_ADAPTERS.items()}
                    res = {"agents": [d.__dict__ for d in detections], "capabilities": adapters_meta}
                    print(json.dumps(res, indent=2) if as_json else
                          "\n".join(f"[{d.agent_id}] installed={d.installed} version={d.version or '-'}" for d in detections))
                    return 0

                if agents_act == "intercept":
                    raw = str(getattr(args, "payload", "") or "")
                    if not raw:
                        raise AgentCoharnessValidationError("agents intercept requires --payload <json|'@file'|'-'>.")
                    if raw == "-":
                        raw = sys.stdin.read()
                    elif raw.startswith("@"):
                        raw = Path(raw[1:]).expanduser().read_text(encoding="utf-8")
                    payload = json.loads(raw)
                    if not isinstance(payload, dict):
                        raise AgentCoharnessValidationError("Hook payload must be a JSON object.")
                    adapter = get_adapter(str(args.agent_id))
                    res = evaluate_hook_payload(
                        engine=engine,
                        agent_id=str(args.agent_id),
                        payload=payload,
                        workspace_id=ws_id,
                        mode=str(getattr(args, "mode", "audit_only")),
                        adapter=adapter,
                    )
                    out_format = str(getattr(args, "output_format", "json"))
                    if out_format == "claude-code":
                        decision_map = {"allow": "allow", "deny": "deny", "hold": "ask"}
                        permission = decision_map.get(res["decision"], "ask")
                        print(json.dumps({"hookSpecificOutput": {
                            "hookEventName": "PreToolUse",
                            "permissionDecision": permission,
                        }}))
                        return 0
                    print(json.dumps(res, indent=2) if as_json else
                          f"[{res['decision'].upper()}] agent={res['agent_id']} verdict={res['record']['verdict']} reason={res['record']['reason_code']}")
                    if res["decision"] == "deny":
                        return 1
                    if res["decision"] == "hold":
                        return 2
                    return 0

        if cmd == "ci-gate":
            act = getattr(args, "cigate_action", None)
            if act == "evaluate":
                cands = _parse_candidates_arg(getattr(args, "candidates_json", None))
                res = engine.evaluate_worktree_ci_gate(
                    workspace_id=ws_id,
                    workflow_name=str(getattr(args, "workflow_name", "pr-worktree-arena")),
                    diff_summary=str(getattr(args, "diff_summary", "Refactor retry backoff & add unit test in core/platform/")),
                    min_eval_score=float(getattr(args, "min_eval_score", 0.85)),
                    candidates=cands,
                )
                print(json.dumps(res, indent=2) if as_json else f"[{res['status']}] {res['gate_run_id']} winner={res['winner_candidate_id']} saved=${res['cost_saved_usd']:.4f}")
                return 0 if res["status"] == "PASS" else 1

            if act == "runs":
                res = engine.list_worktree_ci_gate_runs(workspace_id=ws_id, limit=int(getattr(args, "limit", 25)))
                print(json.dumps(res, indent=2) if as_json else f"Worktree CI Gate Runs [{ws_id}] count={res['count']}")
                return 0
    except ApprovalTicketNotFoundError as exc:
        msg = str(exc.args[0] if exc.args else exc)
        print(json.dumps({"detail": msg, "error": msg, "code": "ticket_not_found"}, indent=2) if as_json else f"[-] {msg}")
        return 1
    except ApprovalTicketConflictError as exc:
        print(json.dumps({"detail": str(exc), "error": str(exc), "code": "ticket_already_consumed"}, indent=2) if as_json else f"[-] {exc}")
        return 1
    except (AgentCoharnessValidationError, ValueError, json.JSONDecodeError, OSError) as exc:
        print(json.dumps({"detail": str(exc), "error": str(exc), "code": "agent_coharness_validation_error"}, indent=2) if as_json else f"[-] {exc}")
        return 1
    finally:
        engine.close()

    return None
