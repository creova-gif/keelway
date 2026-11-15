"""
Keelway Sovereign CLI Phase 8 Subcommands (`kflow`, `kspaces-sync`, `sbom`).

Registered and dispatched via `core.cli_runtime` while preserving legacy
`python cli.py sbom <generate|verify>` subcommand compatibility.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional


def _add_common_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--workspace-id", default="default", help="Target workspace identifier")
    parser.add_argument("--db-path", default=None, help="Optional SQLite database path override")
    parser.add_argument("--json", action="store_true", help="Emit JSON output")


def register_kflow_crdt_cli_subparsers(subparsers: argparse._SubParsersAction) -> None:
    """Register `kflow`, `kspaces-sync`, and non-positional `sbom [--verify] [--json]`."""
    kf = subparsers.add_parser("kflow", help="Execute topological KFlow DAG workflows and inspect run receipts")
    kf_sub = kf.add_subparsers(dest="kflow_command", required=True)

    kf_exec = kf_sub.add_parser("execute", help="Execute a multi-wave topological KFlow DAG workflow")
    kf_exec.add_argument("--workflow-id", required=True, help="Workflow identifier (e.g., WF-01)")
    kf_exec.add_argument("--nodes-json", required=True, help="JSON array of DAG node definitions")
    kf_exec.add_argument("--approve-node", action="append", default=[], help="Approve P-10 gated node ID (repeatable)")
    kf_exec.add_argument("--trigger", default="manual", help="Workflow trigger source (default: manual)")
    kf_exec.add_argument("--token-budget", type=int, default=25000, help="Maximum cumulative token budget")
    _add_common_flags(kf_exec)

    kf_runs = kf_sub.add_parser("runs", help="List persisted KFlow DAG runs newest-first")
    kf_runs.add_argument("--workflow-id", default=None, help="Optional workflow identifier filter")
    kf_runs.add_argument("--limit", type=int, default=25, help="Maximum runs to return (default: 25)")
    _add_common_flags(kf_runs)

    ks = subparsers.add_parser("kspaces-sync", help="Synchronize KSpaces LWW-Element-Set CRDT state across peers")
    ks_sub = ks.add_subparsers(dest="kspaces_sync_command", required=True)

    ks_push = ks_sub.add_parser("push", help="Apply CRDT set/remove operations with DLP secret scrubbing")
    ks_push.add_argument("--peer-id", required=True, help="Originating peer identifier")
    ks_push.add_argument("--ops-json", required=True, help="JSON array of CRDT set/remove operations")
    _add_common_flags(ks_push)

    ks_state = ks_sub.add_parser("state", help="Inspect converged KSpaces CRDT state, vector clock, and SHA-256 digest")
    ks_state.add_argument("--namespace", default=None, help="Optional namespace filter (e.g., issues, workspace)")
    _add_common_flags(ks_state)

    sbom_p = subparsers._name_parser_map.get("sbom")
    if sbom_p is None:
        sbom_p = subparsers.add_parser("sbom", help="Generate and verify CycloneDX Software Bill of Materials")
    else:
        for action in sbom_p._actions:
            if isinstance(action, argparse._SubParsersAction):
                action.required = False
    if "--verify" not in sbom_p._option_string_actions:
        sbom_p.add_argument("--verify", action="store_true", help="Cryptographically verify generated CycloneDX SBOM")
    if "--json" not in sbom_p._option_string_actions:
        sbom_p.add_argument("--json", action="store_true", help="Emit JSON CycloneDX SBOM verification report")
    if "--workspace-id" not in sbom_p._option_string_actions:
        sbom_p.add_argument("--workspace-id", default="default", help="Target workspace identifier")


def dispatch_kflow_crdt_cli(args: argparse.Namespace) -> Optional[int]:
    """Dispatch `kflow`, `kspaces-sync`, and `sbom [--verify] [--json]`. Returns exit code or None."""
    cmd = getattr(args, "command", None)

    if cmd == "kflow":
        from core.platform.kflow_crdt import KFlowCycleError, KFlowDagEngine

        sub = getattr(args, "kflow_command", None)
        ws_id = str(getattr(args, "workspace_id", "default") or "default")
        as_json = bool(getattr(args, "json", False))
        engine = KFlowDagEngine(db_path=getattr(args, "db_path", None))
        try:
            if sub == "execute":
                parsed_nodes = json.loads(str(args.nodes_json))
                if not isinstance(parsed_nodes, list):
                    raise ValueError("--nodes-json must decode to a JSON array of node objects.")
                approved: List[str] = list(getattr(args, "approve_node", None) or [])
                res = engine.execute_dag(
                    workspace_id=ws_id,
                    workflow_id=str(args.workflow_id),
                    nodes=parsed_nodes,
                    trigger=str(getattr(args, "trigger", "manual")),
                    token_budget=int(getattr(args, "token_budget", 25000)),
                    approved_node_ids=approved,
                )
                if as_json:
                    print(json.dumps(res, indent=2))
                else:
                    print(
                        f"[+] KFlow {res['run_id']} ({res['workflow_id']}) status={res['status']} "
                        f"waves={len(res['waves'])} tokens={res['tokens_used']}/{res['token_budget']} "
                        f"receipt={res['receipt_sha256'][:23]}..."
                    )
                return 1 if res["status"] == "failed" else 0

            if sub == "runs":
                listing = engine.list_runs(
                    workspace_id=ws_id,
                    workflow_id=getattr(args, "workflow_id", None),
                    limit=int(getattr(args, "limit", 25)),
                )
                if as_json:
                    print(json.dumps(listing, indent=2))
                else:
                    print(f"Keelway KFlow Runs [{ws_id}] ({listing['count']} runs):")
                    for r in listing["runs"]:
                        print(f"  - {r['run_id']} [{r['workflow_id']}] status={r['status']} waves={len(r['waves'])}")
                return 0
        except (KFlowCycleError, ValueError, json.JSONDecodeError) as exc:
            print(json.dumps({"error": str(exc)}, indent=2) if as_json else f"[-] KFlow error: {exc}")
            return 1
        finally:
            engine.close()

    if cmd == "kspaces-sync":
        from core.platform.kflow_crdt import KSpacesCrdtEngine

        sub = getattr(args, "kspaces_sync_command", None)
        ws_id = str(getattr(args, "workspace_id", "default") or "default")
        as_json = bool(getattr(args, "json", False))
        crdt = KSpacesCrdtEngine(db_path=getattr(args, "db_path", None))
        try:
            if sub == "push":
                parsed_ops = json.loads(str(args.ops_json))
                if not isinstance(parsed_ops, list):
                    raise ValueError("--ops-json must decode to a JSON array of CRDT operations.")
                res = crdt.apply_ops(ws_id, str(args.peer_id), parsed_ops)
                if as_json:
                    print(json.dumps(res, indent=2))
                else:
                    print(
                        f"[+] KSpaces CRDT Sync [{ws_id}] peer={res['peer_id']} applied={res['applied_count']} "
                        f"active={res['active_keys_count']} digest={res['state_digest_sha256'][:23]}..."
                    )
                return 0

            if sub == "state":
                state = crdt.get_state(workspace_id=ws_id, namespace=getattr(args, "namespace", None))
                if as_json:
                    print(json.dumps(state, indent=2))
                else:
                    print(
                        f"Keelway KSpaces CRDT State [{ws_id}] active={state['active_keys_count']} "
                        f"clock={state['vector_clock']} digest={state['state_digest_sha256'][:23]}..."
                    )
                return 0
        except (ValueError, json.JSONDecodeError) as exc:
            print(json.dumps({"error": str(exc)}, indent=2) if as_json else f"[-] KSpaces CRDT error: {exc}")
            return 1
        finally:
            crdt.close()

    if cmd == "sbom":
        if getattr(args, "sbom_command", None) in {"generate", "verify"}:
            return None
        from core.security.sbom import SBOMGenerator, SBOMVerifier

        ws_id = str(getattr(args, "workspace_id", "default") or "default")
        as_json = bool(getattr(args, "json", False))
        manifest_dict: Dict[str, Any] = SBOMGenerator.generate(repo_root=Path(__file__).resolve().parents[1]).to_dict()
        valid, v_status, _details = SBOMVerifier.verify(manifest_dict)
        report = {
            "workspace_id": ws_id,
            "verified": valid,
            "verification_status": v_status,
            "bom_format": manifest_dict["bom_format"],
            "spec_version": manifest_dict["spec_version"],
            "serial_number": manifest_dict["serial_number"],
            "component_count": len(manifest_dict["components"]),
            "root_digest_sha256": manifest_dict["root_digest_sha256"],
            "provenance_signature": manifest_dict["provenance_signature"],
            "manifest": manifest_dict,
        }
        if as_json:
            print(json.dumps(report, indent=2))
        else:
            print(
                f"Keelway CycloneDX {report['spec_version']} SBOM [{v_status}] "
                f"components={report['component_count']} sha256={report['root_digest_sha256'][:16]}..."
            )
        return 0 if valid else 1

    return None
