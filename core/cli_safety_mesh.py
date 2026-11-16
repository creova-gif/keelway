"""
Keelway Sovereign CLI Phase 17A Formal Safety Verifier & Federated Edge-to-Cluster Mesh
Subcommands (`safety`, `mesh`).
"""

from __future__ import annotations

import argparse
import json
from typing import Any, Dict, List, Optional, Tuple

from core.platform.safety_and_mesh import (
    MeshSovereigntyViolationError,
    SafetyMeshValidationError,
    SQLiteSafetyAndMeshEngine,
)

_LEGACY_MESH_ACTIONS = frozenset({"status", "peers", "delegate", "prune", "save", "load"})


def _add_common_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--workspace", "--workspace-id", dest="workspace_id", default="default", help="Target workspace ID")
    parser.add_argument("--db-path", default=None, help="Optional SQLite database path override")
    parser.add_argument("--json", action="store_true", help="Emit JSON output")


def _add_legacy_peer_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--node-id", default=None, help="Peer node identifier")
    parser.add_argument("--host", default=None, help="Peer hostname")
    parser.add_argument("--lan-ip", default="127.0.0.1", help="Peer LAN IP address")
    parser.add_argument("--port", type=int, default=7420, help="Peer port")
    parser.add_argument("--vram", type=int, default=8192, help="Available VRAM in MB")
    parser.add_argument("--tailscale-ip", default=None, help="Optional Tailscale IP")
    parser.add_argument("--intent", default="Heavy AST optimization", help="Task intent for delegation")
    parser.add_argument("--min-vram", type=int, default=6000, help="Minimum VRAM in MB")
    parser.add_argument("--timeout", type=float, default=30.0, help="Heartbeat timeout")


def register_safety_mesh_cli_subparsers(subparsers: argparse._SubParsersAction) -> None:
    """Register `keelway safety` and `keelway mesh` sovereign CLI subcommands."""
    for name in ("safety", "mesh"):
        if name in subparsers._name_parser_map:
            subparsers._name_parser_map.pop(name, None)
            subparsers._choices_actions = [a for a in subparsers._choices_actions if getattr(a, "dest", None) != name]

    sf = subparsers.add_parser("safety", help="Formal state-machine safety verifier & P-10 guard auto-remediation")
    sf_sub = sf.add_subparsers(dest="safety_action", required=True)

    sf_ver = sf_sub.add_parser("verify", help="Verify workflow state-machine against 4 formal safety invariants")
    sf_ver.add_argument("--workflow-id", default="WF-TREASURY-01", help="Workflow identifier")
    sf_ver.add_argument("--workflow-name", "--workflow", dest="workflow_name", default="treasury-wire-approver", help="Workflow name")
    sf_ver.add_argument("--airgap", "--airgap-mode", dest="airgap_mode", action="store_true", help="Enforce zero cloud egress")
    sf_ver.add_argument("--inject-p10-guards", dest="inject_p10_guards", action="store_true", help="Auto-inject missing P-10 guards")
    sf_ver.add_argument("--spec-json", default=None, help="Optional JSON object or node array workflow spec")
    _add_common_flags(sf_ver)

    sf_list = sf_sub.add_parser("list", help="List persisted formal safety verification proofs")
    sf_list.add_argument("--limit", type=int, default=25, help="Maximum verifications to return (default: 25)")
    _add_common_flags(sf_list)

    ms = subparsers.add_parser("mesh", help="Federated edge-to-cluster agent mesh & attested workload handoffs")
    ms_sub = ms.add_subparsers(dest="action")

    ms_reg = ms_sub.add_parser("register", help="Register an attested edge_local or cluster_burst mesh node")
    ms_reg.add_argument("--name", default=None, help="Human-readable node name")
    ms_reg.add_argument("--tier", choices=["edge_local", "cluster_burst"], default=None, help="Mesh execution tier")
    ms_reg.add_argument("--hal", "--hardware-hal", dest="hardware_hal", choices=["apple_metal_secure_enclave", "nvidia_h100_cc", "linux_tpm2"], default=None, help="Hardware attestation HAL")
    ms_reg.add_argument("--region", default="local-loopback", help="Residency region (default: local-loopback)")
    ms_reg.add_argument("--vram-gb", type=int, default=32, help="Available VRAM in GB (default: 32)")
    ms_reg.add_argument("--status", choices=["ONLINE", "DRAINING"], default="ONLINE", help="Node operational status")
    _add_legacy_peer_flags(ms_reg)
    _add_common_flags(ms_reg)

    ms_nodes = ms_sub.add_parser("nodes", help="List attested federated edge & cluster mesh nodes")
    _add_common_flags(ms_nodes)

    ms_disp = ms_sub.add_parser("dispatch", help="Dispatch sovereign edge-to-cluster workload handoff")
    ms_disp.add_argument("--workflow-name", "--workflow", dest="workflow_name", default="clinical-synthesis-pipeline", help="Workflow name")
    ms_disp.add_argument("--task-summary", default="Ingest patient intake & synthesize anonymized cohort summary", help="Task summary")
    ms_disp.add_argument("--classification", "--data-classification", dest="data_classification", choices=["restricted_pii", "internal", "public"], default="restricted_pii", help="Data classification")
    ms_disp.add_argument("--pin-edge-only", dest="pin_edge_only", action="store_true", help="Keep execution pinned to edge_local")
    ms_disp.add_argument("--force-raw-cloud-burst", dest="force_raw_cloud_burst", action="store_true", help="Attempt raw cloud burst")
    _add_common_flags(ms_disp)

    ms_ho = ms_sub.add_parser("handoffs", help="List persisted federated mesh workload handoff receipts")
    ms_ho.add_argument("--limit", type=int, default=25, help="Maximum handoffs to return (default: 25)")
    _add_common_flags(ms_ho)

    for legacy_act in sorted(_LEGACY_MESH_ACTIONS):
        _add_legacy_peer_flags(ms_sub.add_parser(legacy_act, help=f"Peer workstation mesh action ({legacy_act})"))


def _resolve_verify_spec(args: argparse.Namespace) -> Tuple[str, str, Optional[List[Dict[str, Any]]], Optional[List[Dict[str, Any]]], bool, bool]:
    wf_id = str(getattr(args, "workflow_id", "WF-TREASURY-01") or "WF-TREASURY-01")
    wf_name = str(getattr(args, "workflow_name", "treasury-wire-approver") or "treasury-wire-approver")
    airgap, inject_p10, raw_spec = bool(getattr(args, "airgap_mode", False)), bool(getattr(args, "inject_p10_guards", False)), getattr(args, "spec_json", None)
    if not raw_spec:
        return wf_id, wf_name, None, None, airgap, inject_p10
    parsed = json.loads(raw_spec)
    if isinstance(parsed, list):
        return wf_id, wf_name, parsed, None, airgap, inject_p10
    if not isinstance(parsed, dict):
        raise SafetyMeshValidationError("--spec-json must be a JSON object or array of nodes.")
    wf_id = str(parsed["workflow_id"]) if wf_id == "WF-TREASURY-01" and parsed.get("workflow_id") else wf_id
    wf_name = str(parsed["workflow_name"]) if wf_name == "treasury-wire-approver" and parsed.get("workflow_name") else wf_name
    return wf_id, wf_name, parsed.get("nodes"), parsed.get("edges"), (airgap or bool(parsed.get("airgap_mode", False))), (inject_p10 or bool(parsed.get("inject_p10_guards", False)))


def dispatch_safety_mesh_cli(args: argparse.Namespace) -> Optional[int]:
    """Dispatch `keelway safety` and `keelway mesh` CLI subcommands."""
    cmd = getattr(args, "command", None)
    if cmd not in ("safety", "mesh"):
        return None
    if cmd == "mesh":
        m_act = getattr(args, "action", None)
        if m_act is None or m_act in _LEGACY_MESH_ACTIONS:
            return None
        if m_act == "register" and getattr(args, "name", None) is None and getattr(args, "tier", None) is None and getattr(args, "hardware_hal", None) is None:
            return None

    ws_id, as_json = str(getattr(args, "workspace_id", "default") or "default"), bool(getattr(args, "json", False))
    engine = SQLiteSafetyAndMeshEngine(db_path=getattr(args, "db_path", None))
    try:
        if cmd == "safety":
            act = getattr(args, "safety_action", None)
            if act == "verify":
                wf_id, wf_name, nodes, edges, airgap, inject_p10 = _resolve_verify_spec(args)
                res = engine.verify_workflow(workspace_id=ws_id, workflow_id=wf_id, workflow_name=wf_name, nodes=nodes, edges=edges, airgap_mode=airgap, inject_p10_guards=inject_p10)
                print(json.dumps(res, indent=2) if as_json else f"[{res['status']}] {res['verification_id']} states={res['states_explored']} violations={len(res['violations'])}")
                return 0
            if act == "list":
                res = engine.list_verifications(workspace_id=ws_id, limit=int(getattr(args, "limit", 25)))
                print(json.dumps(res, indent=2) if as_json else f"Safety Verifications [{ws_id}] count={res['count']}")
                return 0

        if cmd == "mesh":
            act = getattr(args, "action", None)
            if act == "register":
                if not getattr(args, "name", None) or not getattr(args, "tier", None) or not getattr(args, "hardware_hal", None):
                    raise SafetyMeshValidationError("mesh register requires --name, --tier, and --hal.")
                res = engine.register_node(workspace_id=ws_id, node_id=getattr(args, "node_id", None), name=str(args.name), tier=str(args.tier), hardware_hal=str(args.hardware_hal), region=str(getattr(args, "region", "local-loopback")), vram_gb=int(getattr(args, "vram_gb", 32)), status=str(getattr(args, "status", "ONLINE")))
                print(json.dumps(res, indent=2) if as_json else f"[{res['status']}] {res['node_id']} ({res['tier']} / {res['hardware_hal']})")
                return 0
            if act == "nodes":
                res = engine.list_nodes(workspace_id=ws_id)
                print(json.dumps(res, indent=2) if as_json else f"Mesh Nodes [{ws_id}] count={res['count']}")
                return 0
            if act == "dispatch":
                res = engine.dispatch_handoff(workspace_id=ws_id, workflow_name=str(getattr(args, "workflow_name", "clinical-synthesis-pipeline")), task_summary=str(getattr(args, "task_summary", "")), data_classification=str(getattr(args, "data_classification", "restricted_pii")), allow_sanitized_burst=not bool(getattr(args, "pin_edge_only", False)), force_raw_cloud_burst=bool(getattr(args, "force_raw_cloud_burst", False)))
                print(json.dumps(res, indent=2) if as_json else f"[{res['status']}] {res['handoff_id']} edge={res['edge_node_id']} burst={res['burst_node_id']} cost=${res['total_cost_usd']:.4f}")
                return 0
            if act == "handoffs":
                res = engine.list_handoffs(workspace_id=ws_id, limit=int(getattr(args, "limit", 25)))
                print(json.dumps(res, indent=2) if as_json else f"Mesh Handoffs [{ws_id}] count={res['count']}")
                return 0
    except MeshSovereigntyViolationError as exc:
        err = {"detail": str(exc), "error": str(exc), "code": "mesh_sovereignty_violation"}
        print(json.dumps(err, indent=2) if as_json else f"[-] {exc}")
        return 1
    except (SafetyMeshValidationError, ValueError, json.JSONDecodeError, OSError) as exc:
        err = {"detail": str(exc), "error": str(exc), "code": "safety_mesh_validation_error"}
        print(json.dumps(err, indent=2) if as_json else f"[-] {exc}")
        return 1
    finally:
        engine.close()

    return None
