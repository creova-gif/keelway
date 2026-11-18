"""
Keelway Sovereign CLI Phase 20A Cryptographic MCP & Skill Merkle Lockfile, Poisoning/Rug-Pull
Firewall & Conformance Benchmark Subcommands (`lock`, `bench`).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, List, Optional

from core.platform.mcp_lockfile_and_bench import (
    DEFAULT_BENCH_MODEL_ID,
    DEFAULT_BENCH_TARGET_ID,
    DEFAULT_LOCKFILE_NAME,
    LockfileNotFoundError,
    SQLiteSupplyChainLockEngine,
    SupplyChainValidationError,
    VALID_SIMULATE_MODES,
    VALID_TARGET_KINDS,
)


def _add_common_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--workspace", "--workspace-id", dest="workspace_id", default="default", help="Target workspace ID")
    parser.add_argument("--db-path", default=None, help="Optional SQLite database path override")
    parser.add_argument("--json", action="store_true", help="Emit JSON output")


def _parse_json_list(raw: Optional[str], flag_name: str) -> Optional[List[Any]]:
    if raw is None:
        return None
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise SupplyChainValidationError(f"Invalid JSON passed to {flag_name}: {exc}") from exc
    if not isinstance(parsed, list):
        raise SupplyChainValidationError(f"{flag_name} must decode to a JSON array.")
    return parsed


def register_supply_chain_cli_subparsers(subparsers: argparse._SubParsersAction) -> None:
    """Register `keelway lock` and `keelway bench` sovereign CLI subcommands."""
    for name in ("lock", "bench"):
        if name in subparsers._name_parser_map:
            subparsers._name_parser_map.pop(name, None)
            subparsers._choices_actions = [a for a in subparsers._choices_actions if getattr(a, "dest", None) != name]

    lk = subparsers.add_parser("lock", help="Cryptographic MCP & skill Merkle lockfile and rug-pull/poisoning firewall")
    lk_sub = lk.add_subparsers(dest="lock_action", required=True)

    lk_pin = lk_sub.add_parser("pin", help="Scan MCP tools for poisoning and pin canonical SHA-256 Merkle lockfile")
    lk_pin.add_argument("--name", "--lockfile-name", dest="lockfile_name", default=DEFAULT_LOCKFILE_NAME, help="Lockfile name")
    lk_pin.add_argument("--tools-json", default=None, help="Optional JSON array of MCP tool specifications")
    lk_pin.add_argument("--output", default=None, help="Optional path to write canonical keelway.lock.json")
    _add_common_flags(lk_pin)

    lk_ver = lk_sub.add_parser("verify", help="Verify live MCP tools against pinned Merkle lockfile for drift or poisoning")
    lk_ver.add_argument("--lockfile-id", default=None, help="Specific lockfile ID (defaults to latest workspace lockfile)")
    lk_ver.add_argument("--tools-json", default=None, help="Optional JSON array of live MCP tool specifications")
    lk_ver.add_argument("--simulate-rug-pull", action="store_true", help="Simulate silent post-install schema/description rug-pull")
    lk_ver.add_argument("--simulate-poisoning", action="store_true", help="Simulate post-install prompt/Unicode tool poisoning")
    lk_ver.add_argument("--simulate-mode", choices=list(VALID_SIMULATE_MODES), default=None, help="Explicit simulation mode")
    _add_common_flags(lk_ver)

    lk_list = lk_sub.add_parser("list", help="List pinned workspace MCP Merkle lockfile snapshots")
    lk_list.add_argument("--limit", type=int, default=25, help="Maximum snapshots to return (default: 25)")
    _add_common_flags(lk_list)

    lk_vers = lk_sub.add_parser("verifications", help="List historical MCP lockfile verification receipts")
    lk_vers.add_argument("--limit", type=int, default=25, help="Maximum receipts to return (default: 25)")
    _add_common_flags(lk_vers)

    bn = subparsers.add_parser("bench", help="Deterministic agent, MCP server & skill conformance benchmark harness")
    bn_sub = bn.add_subparsers(dest="bench_action", required=True)

    bn_run = bn_sub.add_parser("run", help="Run deterministic conformance & p95 latency benchmark")
    bn_run.add_argument("--target-id", default=DEFAULT_BENCH_TARGET_ID, help="Target MCP server, skill, or model ID")
    bn_run.add_argument("--target-kind", choices=list(VALID_TARGET_KINDS), default="mcp_server", help="Target artifact kind")
    bn_run.add_argument("--model", "--model-id", dest="model_id", default=DEFAULT_BENCH_MODEL_ID, help="Evaluated model ID")
    bn_run.add_argument("--latency-budget-ms", type=int, default=250, help="Maximum p95 latency budget in milliseconds")
    bn_run.add_argument("--min-score", "--min-conformance-score", dest="min_conformance_score", type=float, default=0.90, help="Minimum conformance score [0.0, 1.0]")
    bn_run.add_argument("--scenarios-json", default=None, help="Optional JSON array of benchmark scenario outcomes")
    _add_common_flags(bn_run)

    bn_runs = bn_sub.add_parser("runs", help="List conformance benchmark runs and certificates")
    bn_runs.add_argument("--limit", type=int, default=25, help="Maximum benchmark runs to return (default: 25)")
    _add_common_flags(bn_runs)


def dispatch_supply_chain_cli(args: argparse.Namespace) -> Optional[int]:
    """Dispatch `keelway lock` and `keelway bench` CLI subcommands."""
    cmd = getattr(args, "command", None)
    if cmd not in ("lock", "bench"):
        return None

    ws_id = str(getattr(args, "workspace_id", "default") or "default")
    as_json = bool(getattr(args, "json", False))
    engine = SQLiteSupplyChainLockEngine(db_path=getattr(args, "db_path", None))
    try:
        if cmd == "lock":
            act = getattr(args, "lock_action", None)
            if act == "pin":
                res = engine.pin_mcp_lockfile(
                    workspace_id=ws_id,
                    lockfile_name=str(getattr(args, "lockfile_name", DEFAULT_LOCKFILE_NAME)),
                    tools=_parse_json_list(getattr(args, "tools_json", None), "--tools-json"),
                )
                out_path = getattr(args, "output", None)
                if res["status"] == "PINNED" and out_path:
                    target = Path(str(out_path))
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(res["lockfile_json"] + "\n", encoding="utf-8")
                print(
                    json.dumps(res, indent=2)
                    if as_json
                    else f"[{res['status']}] {res['lockfile_id'] or 'BLOCKED'} tools={res['tool_count']} merkle={res['merkle_root_sha256']}"
                )
                return 0 if res["status"] == "PINNED" else 1

            if act == "verify":
                sim_rug = bool(getattr(args, "simulate_rug_pull", False))
                sim_poison = bool(getattr(args, "simulate_poisoning", False))
                if sim_rug and sim_poison:
                    raise SupplyChainValidationError("Cannot combine --simulate-rug-pull and --simulate-poisoning.")
                sim_mode = "poisoning" if sim_poison else ("rug_pull" if sim_rug else (getattr(args, "simulate_mode", None) or "clean"))
                res = engine.verify_mcp_lockfile(
                    workspace_id=ws_id,
                    lockfile_id=getattr(args, "lockfile_id", None),
                    live_tools=_parse_json_list(getattr(args, "tools_json", None), "--tools-json"),
                    simulate_mode=str(sim_mode),
                )
                print(
                    json.dumps(res, indent=2)
                    if as_json
                    else f"[{res['verdict']}] lockfile={res['lockfile_id']} drifted={len(res['drifted_tools'])} poisoning={len(res['poisoning_findings'])}"
                )
                return 0 if res["verdict"] == "LOCK_VERIFIED" else 1

            if act == "list":
                res = engine.list_mcp_lockfiles(workspace_id=ws_id, limit=int(getattr(args, "limit", 25)))
                print(json.dumps(res, indent=2) if as_json else f"MCP Lockfiles [{ws_id}] count={res['count']}")
                return 0

            if act == "verifications":
                res = engine.list_lock_verifications(workspace_id=ws_id, limit=int(getattr(args, "limit", 25)))
                print(json.dumps(res, indent=2) if as_json else f"MCP Lock Verifications [{ws_id}] count={res['count']}")
                return 0

        if cmd == "bench":
            act = getattr(args, "bench_action", None)
            if act == "run":
                res = engine.run_conformance_benchmark(
                    workspace_id=ws_id,
                    target_id=str(getattr(args, "target_id", DEFAULT_BENCH_TARGET_ID)),
                    target_kind=str(getattr(args, "target_kind", "mcp_server")),
                    model_id=str(getattr(args, "model_id", DEFAULT_BENCH_MODEL_ID)),
                    latency_budget_ms=int(getattr(args, "latency_budget_ms", 250)),
                    min_conformance_score=float(getattr(args, "min_conformance_score", 0.90)),
                    scenarios=_parse_json_list(getattr(args, "scenarios_json", None), "--scenarios-json"),
                )
                print(
                    json.dumps(res, indent=2)
                    if as_json
                    else f"[{res['verdict']}] target={res['target_id']} score={res['conformance_score']:.4f} p95={res['p95_latency_ms']}ms/{res['latency_budget_ms']}ms"
                )
                return 0 if res["verdict"] == "PASS_CERTIFIED" else 1

            if act == "runs":
                res = engine.list_conformance_benchmarks(workspace_id=ws_id, limit=int(getattr(args, "limit", 25)))
                print(json.dumps(res, indent=2) if as_json else f"Conformance Benchmarks [{ws_id}] count={res['count']}")
                return 0
    except (LockfileNotFoundError, SupplyChainValidationError, ValueError, OSError) as exc:
        code = "lockfile_not_found" if isinstance(exc, LockfileNotFoundError) else "supply_chain_validation_error"
        print(
            json.dumps({"detail": str(exc), "error": str(exc), "code": code}, indent=2)
            if as_json
            else f"[-] {exc}"
        )
        return 1
    finally:
        engine.close()

    return None
