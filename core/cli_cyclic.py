"""
Keelway Sovereign CLI Phase 15A Cyclic KFlow & Autopilot Subcommands (`kflow-cyclic`, `autopilot`).

Registered and dispatched via `core.cli_runtime` supporting `--workspace` / `--workspace-id`,
`--db-path`, and `--json` for bounded reflection loops, dynamic fan-out shards, saga compensation,
pre-storage DLP guards, and cost-latency-privacy autopilot simulations.
"""

from __future__ import annotations

import argparse
import json
from typing import Any, Dict, List, Optional

from core.platform.kflow_cyclic_autopilot import (
    CyclicKFlowPolicyViolationError,
    CyclicKFlowValidationError,
    SQLiteCyclicKFlowEngine,
)


def _add_common_cyclic_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--workspace",
        "--workspace-id",
        dest="workspace_id",
        default="default",
        help="Target workspace identifier (default: default)",
    )
    parser.add_argument("--db-path", default=None, help="Optional SQLite database path override")
    parser.add_argument("--json", action="store_true", help="Emit JSON output")


def register_cyclic_cli_subparsers(subparsers: argparse._SubParsersAction) -> None:
    """Register `keelway kflow-cyclic` and `keelway autopilot` sovereign CLI subcommands."""
    kc = subparsers.add_parser(
        "kflow-cyclic",
        help="Validate, execute, and inspect bounded cyclic KFlow reflection graphs and saga compensations",
    )
    kc_sub = kc.add_subparsers(dest="cyclic_action", required=True)

    kc_val = kc_sub.add_parser("validate", help="Validate cyclic KFlow forward DAG spine and loop back-edges")
    kc_val.add_argument("--workflow-id", default="WF-CYCLIC-01", help="Target workflow ID (default: WF-CYCLIC-01)")
    kc_val.add_argument("--nodes-json", default=None, help="Optional JSON array of KFlow node specs")
    kc_val.add_argument("--loop-edges-json", default=None, help="Optional JSON array of bounded loop back-edges")
    _add_common_cyclic_flags(kc_val)

    kc_exec = kc_sub.add_parser("execute", help="Execute a bounded cyclic reflection loop with DLP & P-10 gates")
    kc_exec.add_argument("--workflow-id", default="WF-CYCLIC-01", help="Target workflow ID (default: WF-CYCLIC-01)")
    kc_exec.add_argument("--nodes-json", default=None, help="Optional JSON array of KFlow node specs")
    kc_exec.add_argument("--loop-edges-json", default=None, help="Optional JSON array of bounded loop back-edges")
    kc_exec.add_argument("--max-iterations", dest="max_iterations", type=int, default=None, help="Loop cap override (1..10)")
    kc_exec.add_argument("--critic-threshold", type=float, default=0.85, help="Critic convergence threshold (default: 0.85)")
    kc_exec.add_argument("--fan-out-shards", type=int, default=None, help="Dynamic fan-out shard count override (1..16)")
    kc_exec.add_argument("--simulate-timeout", action="store_true", help="Simulate timeout and trigger saga rollback")
    kc_exec.add_argument("--initial-state-json", default=None, help="Optional JSON object initial state (DLP-guarded)")
    kc_exec.add_argument("--approve-node", dest="approved_node_ids", action="append", default=None, help="Approve P-10 node ID")
    _add_common_cyclic_flags(kc_exec)

    kc_runs = kc_sub.add_parser("runs", help="List persisted cyclic KFlow execution receipts")
    kc_runs.add_argument("--workflow-id", default=None, help="Optional workflow ID filter")
    kc_runs.add_argument("--limit", type=int, default=25, help="Maximum runs to return (default: 25)")
    _add_common_cyclic_flags(kc_runs)

    ap = subparsers.add_parser(
        "autopilot",
        help="Simulate and list Cost-Latency-Privacy Autopilot OpenCore routing plans",
    )
    ap_sub = ap.add_subparsers(dest="autopilot_action", required=True)

    ap_sim = ap_sub.add_parser("simulate", help="Simulate P95 budget cap & privacy policy node routing")
    ap_sim.add_argument("--workflow-id", default="WF-CYCLIC-01", help="Target workflow ID (default: WF-CYCLIC-01)")
    ap_sim.add_argument("--budget-usd", "--budget-cap-usd", dest="budget_usd", type=float, default=0.15, help="P95 spend cap in USD")
    ap_sim.add_argument("--privacy-policy", default="hybrid_balanced", help="Privacy policy (hybrid_balanced|airgap_strict|eu_residency)")
    ap_sim.add_argument("--expected-loop-multiplier", type=int, default=2, help="Expected P95 loop multiplier (default: 2)")
    ap_sim.add_argument("--nodes-json", default=None, help="Optional JSON array of KFlow node specs")
    ap_sim.add_argument("--loop-edges-json", default=None, help="Optional JSON array of bounded loop back-edges")
    _add_common_cyclic_flags(ap_sim)

    ap_list = ap_sub.add_parser("list", help="List persisted Cost-Latency-Privacy Autopilot simulations")
    ap_list.add_argument("--workflow-id", default=None, help="Optional workflow ID filter")
    ap_list.add_argument("--limit", type=int, default=25, help="Maximum simulations to return (default: 25)")
    _add_common_cyclic_flags(ap_list)


def _parse_json_list(raw: Optional[str]) -> Optional[List[Dict[str, Any]]]:
    if raw is None:
        return None
    parsed = json.loads(raw)
    if not isinstance(parsed, list):
        raise CyclicKFlowValidationError("Expected a JSON array.")
    return parsed


def dispatch_cyclic_cli(args: argparse.Namespace) -> Optional[int]:
    """Dispatch `keelway kflow-cyclic` and `keelway autopilot` CLI subcommands."""
    cmd = getattr(args, "command", None)
    if cmd not in ("kflow-cyclic", "autopilot"):
        return None

    ws_id = str(getattr(args, "workspace_id", "default") or "default")
    as_json = bool(getattr(args, "json", False))
    engine = SQLiteCyclicKFlowEngine(db_path=getattr(args, "db_path", None))
    try:
        if cmd == "kflow-cyclic":
            act = getattr(args, "cyclic_action", None)
            if act == "validate":
                res = engine.validate_cyclic_graph(
                    workspace_id=ws_id,
                    workflow_id=str(getattr(args, "workflow_id", "WF-CYCLIC-01")),
                    nodes=_parse_json_list(getattr(args, "nodes_json", None)),
                    loop_edges=_parse_json_list(getattr(args, "loop_edges_json", None)),
                )
                print(
                    json.dumps(res, indent=2) if as_json
                    else f"[VALID] {res['workflow_id']} [{ws_id}] nodes={res['node_count']} loops={res['loop_edge_count']} worst_case={res['max_worst_case_steps']}"
                )
                return 0
            if act == "execute":
                raw_init = getattr(args, "initial_state_json", None)
                init_state: Optional[Dict[str, Any]] = json.loads(raw_init) if raw_init else None
                res = engine.execute_cyclic_graph(
                    workspace_id=ws_id,
                    workflow_id=str(getattr(args, "workflow_id", "WF-CYCLIC-01")),
                    nodes=_parse_json_list(getattr(args, "nodes_json", None)),
                    loop_edges=_parse_json_list(getattr(args, "loop_edges_json", None)),
                    max_iterations_override=getattr(args, "max_iterations", None),
                    critic_threshold=float(getattr(args, "critic_threshold", 0.85)),
                    fan_out_shards=getattr(args, "fan_out_shards", None),
                    simulate_timeout=bool(getattr(args, "simulate_timeout", False)),
                    initial_state=init_state,
                    approved_node_ids=getattr(args, "approved_node_ids", None),
                )
                print(
                    json.dumps(res, indent=2) if as_json
                    else f"[{res['status']}] Run {res['run_id']} iters={res['iterations_executed']}/{res['max_iterations']} score={res['final_critic_score']}"
                )
                return 0
            if act == "runs":
                res = engine.list_cyclic_runs(
                    workspace_id=ws_id,
                    workflow_id=getattr(args, "workflow_id", None),
                    limit=int(getattr(args, "limit", 25)),
                )
                if as_json:
                    print(json.dumps(res, indent=2))
                else:
                    print(f"Keelway Cyclic KFlow Runs [{ws_id}] count={res['count']}:")
                    for r in res["runs"]:
                        print(f"  - {r['run_id']} [{r['status']}] iters={r['iterations_executed']} cost=${r['total_cost_usd']:.4f}")
                return 0

        if cmd == "autopilot":
            act = getattr(args, "autopilot_action", None)
            if act == "simulate":
                res = engine.simulate_autopilot(
                    workspace_id=ws_id,
                    workflow_id=str(getattr(args, "workflow_id", "WF-CYCLIC-01")),
                    nodes=_parse_json_list(getattr(args, "nodes_json", None)),
                    loop_edges=_parse_json_list(getattr(args, "loop_edges_json", None)),
                    budget_cap_usd=float(getattr(args, "budget_usd", 0.15)),
                    privacy_policy=str(getattr(args, "privacy_policy", "hybrid_balanced")),
                    expected_loop_multiplier=int(getattr(args, "expected_loop_multiplier", 2)),
                )
                print(
                    json.dumps(res, indent=2) if as_json
                    else f"[AUTOPILOT] {res['simulation_id']} policy={res['privacy_policy']} p95=${res['baseline_p95_usd']:.3f}->${res['optimized_p95_usd']:.3f} ({res['savings_pct']}% saved)"
                )
                return 0
            if act == "list":
                res = engine.list_autopilot_simulations(
                    workspace_id=ws_id,
                    workflow_id=getattr(args, "workflow_id", None),
                    limit=int(getattr(args, "limit", 25)),
                )
                if as_json:
                    print(json.dumps(res, indent=2))
                else:
                    print(f"Keelway Autopilot Simulations [{ws_id}] count={res['count']}:")
                    for s in res["simulations"]:
                        print(f"  - {s['simulation_id']} [{s['privacy_policy']}] savings={s['savings_pct']}%")
                return 0
    except (CyclicKFlowPolicyViolationError, CyclicKFlowValidationError, KeyError, ValueError, json.JSONDecodeError, OSError) as exc:
        code = "policy_violation" if isinstance(exc, CyclicKFlowPolicyViolationError) else "cyclic_validation_error"
        print(json.dumps({"error": str(exc), "code": code}, indent=2) if as_json else f"[-] Cyclic KFlow error: {exc}")
        return 1
    finally:
        engine.close()

    return None
