"""
Keelway Sovereign CLI Phase 7 Subcommands (`mcp <servers|tools|call>`, `eval-suite`).

Registered and dispatched via `core.cli_runtime` while preserving standalone
`python cli.py mcp [--workspace ...]` stdio server compatibility.
"""

from __future__ import annotations

import argparse
import json
from typing import Any, Dict, Optional

_EVAL_CHOICES = ["all", "workspace_ast", "governance_p10", "security_redteam", "routing_pricing"]


def _add_common_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--workspace-id", default="default", help="Target workspace identifier")
    parser.add_argument("--db-path", default=None, help="Optional SQLite database path override")
    parser.add_argument("--json", action="store_true", help="Emit JSON output")


def register_mcp_eval_cli_subparsers(subparsers: argparse._SubParsersAction) -> None:
    """Register `mcp <servers|tools|call>` and `eval-suite` subcommands."""
    mcp_parser = subparsers._name_parser_map.get("mcp")
    if mcp_parser is None:
        mcp_parser = subparsers.add_parser(
            "mcp",
            help="Manage workspace MCP servers/tools or serve MCP over stdio",
        )
        mcp_parser.add_argument("--workspace", default=None, help="Workspace root (default: current directory)")

    mcp_sub = mcp_parser.add_subparsers(dest="mcp_command")
    _add_common_flags(mcp_sub.add_parser("servers", help="List built-in and registered workspace MCP servers"))
    _add_common_flags(mcp_sub.add_parser("tools", help="List discovered MCP tools and input schemas"))

    mcp_call = mcp_sub.add_parser("call", help="Invoke an MCP tool with DLP secret redaction and SHA-256 receipt")
    mcp_call.add_argument("tool_name", help="Registered MCP tool name (e.g., workspace.list_files)")
    mcp_call.add_argument("--args", default="{}", help="JSON object string of tool arguments")
    _add_common_flags(mcp_call)

    ev = subparsers.add_parser(
        "eval-suite",
        help="Run the 16-case Production Golden Evaluation & Adversarial Red-Team Suite",
    )
    ev.add_argument("--category", choices=_EVAL_CHOICES, default="all", help="Evaluation category filter")
    _add_common_flags(ev)


def dispatch_mcp_eval_cli(args: argparse.Namespace) -> Optional[int]:
    """Dispatch `mcp <servers|tools|call>` and `eval-suite`. Returns exit code or None."""
    cmd = getattr(args, "command", None)

    if cmd == "mcp":
        sub = getattr(args, "mcp_command", None)
        if sub is None:
            return None

        from core.orchestration.mcp import PROTOCOL_VERSION
        from core.platform.mcp_registry import PlatformMcpRegistry

        ws_id = str(getattr(args, "workspace_id", "default") or "default")
        as_json = bool(getattr(args, "json", False))
        registry = PlatformMcpRegistry(
            db_path=getattr(args, "db_path", None),
            workspace_root=getattr(args, "workspace", None),
        )
        try:
            if sub == "servers":
                servers = registry.list_servers(workspace_id=ws_id)
                if as_json:
                    print(
                        json.dumps(
                            {
                                "workspace_id": ws_id,
                                "protocol_version": PROTOCOL_VERSION,
                                "count": len(servers),
                                "total": len(servers),
                                "servers": servers,
                            },
                            indent=2,
                        )
                    )
                else:
                    print(f"Keelway MCP Servers [{ws_id}] (protocol {PROTOCOL_VERSION}, {len(servers)} servers):")
                    for srv in servers:
                        kind_tag = "builtin" if srv.get("builtin") else srv.get("transport", "sse")
                        print(f"  - {srv['id']:<24} [{kind_tag:<8}] tools={srv['tools_count']} endpoint={srv['endpoint']}")
                return 0

            if sub == "tools":
                payload = registry.list_tools(workspace_id=ws_id)
                if as_json:
                    print(json.dumps(payload, indent=2))
                else:
                    print(f"Keelway MCP Tools [{ws_id}] ({payload['count']} tools):")
                    for tool in payload["tools"]:
                        print(f"  - {tool['name']:<28} [{tool['server_id']}] {tool['description']}")
                return 0

            if sub == "call":
                raw_args = str(getattr(args, "args", "{}") or "{}").strip()
                parsed_args: Dict[str, Any] = json.loads(raw_args) if raw_args else {}
                if not isinstance(parsed_args, dict):
                    raise ValueError("--args must decode to a JSON object.")
                res = registry.call_tool(ws_id, str(args.tool_name), parsed_args)
                if as_json:
                    print(json.dumps(res, indent=2))
                else:
                    print(f"[+] MCP {res['tool_name']} (redacted={res['redacted']}, receipt={res['receipt_sha256'][:16]}...)")
                    print(json.dumps(res["result"], indent=2))
                return 0
        except (KeyError, ValueError, json.JSONDecodeError) as exc:
            err_body = {"ok": False, "error": str(exc)}
            print(json.dumps(err_body, indent=2) if as_json else f"[-] MCP error: {exc}")
            return 1
        finally:
            registry.close()

    if cmd == "eval-suite":
        from core.eval.golden_suite import GoldenEvalSuite

        ws_id = str(getattr(args, "workspace_id", "default") or "default")
        cat = str(getattr(args, "category", "all") or "all")
        as_json = bool(getattr(args, "json", False))
        suite = GoldenEvalSuite(db_path=getattr(args, "db_path", None))
        try:
            report = suite.run_suite(workspace_id=ws_id, category=cat)
            if as_json:
                print(json.dumps(report, indent=2))
            else:
                print(
                    f"Keelway Golden Eval Suite [{ws_id}] category={cat} "
                    f"{report['passed_cases']}/{report['total_cases']} passed "
                    f"({report['duration_ms']:.1f}ms, receipt={report['receipt_sha256'][:16]}...)"
                )
                for case in report["cases"]:
                    mark = "PASS" if case["passed"] else "FAIL"
                    print(f"  [{mark}] {case['id']:<28} ({case['duration_ms']:.1f}ms) {case['evidence']}")
            return 0 if report["failed_cases"] == 0 else 1
        except ValueError as exc:
            print(json.dumps({"error": str(exc)}, indent=2) if as_json else f"[-] Eval suite error: {exc}")
            return 1
        finally:
            suite.close()

    return None
