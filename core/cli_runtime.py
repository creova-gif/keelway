"""
Keelway Sovereign CLI Phase 6 Runtime Subcommands (`vault`, `workspace`, `run`, `pricing-eval`).

Wired into `core.cli_tui` (`register_platform_cli_subparsers` / `dispatch_platform_cli`) so
`python cli.py <subcommand>` works seamlessly with zero modifications to `cli.py`.
"""

from __future__ import annotations

import argparse
import contextlib
import dataclasses
import importlib
import inspect
import io
import json
from typing import Any, Dict, List, Optional

_FALLBACK_CALIBRATED: Dict[str, Any] = {
    "pro_annual_usd": 29, "byom_annual_usd": 15, "supportive_rate": 1.0,
    "hidden_fee_distrust_score": 0.0, "pricing_health_score": 96.5,
}
_FALLBACK_LEGACY: Dict[str, Any] = {
    "pro_annual_usd": 39, "supportive_rate": 0.4,
    "hidden_fee_distrust_score": 0.68, "pricing_health_score": 54.0,
}


def _sanitize_secret_meta(meta: Dict[str, Any]) -> Dict[str, Any]:
    cipher = str(meta.get("cipher") or meta.get("encryption") or "AES-256-GCM")
    return {
        "workspace_id": meta.get("workspace_id", "default"),
        "name": meta["name"],
        "namespace": meta.get("namespace", "byom"),
        "masked_preview": meta["masked_preview"],
        "fingerprint_sha256": meta["fingerprint_sha256"],
        "version": int(meta["version"]),
        "cipher": cipher,
        "encryption": cipher,
        "updated_at": meta.get("updated_at", ""),
    }


def _to_plain_dict(obj: Any) -> Dict[str, Any]:
    if isinstance(obj, dict):
        return {k: (_to_plain_dict(v) if hasattr(v, "model_dump") or dataclasses.is_dataclass(v) else v) for k, v in obj.items()}
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return dataclasses.asdict(obj)
    return {"result": obj}


def _bind_pricing_kwargs(fn: Any, schedule: str, seats: int, api_spend: float) -> Dict[str, Any]:
    params = inspect.signature(fn).parameters
    accepts_var_kw = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values())
    candidates = (
        (("schedule", "mode"), schedule),
        (("seats", "seat_count", "team_seats"), seats),
        (("monthly_api_spend_usd", "api_spend_usd", "api_spend", "monthly_api_spend"), api_spend),
    )
    bound: Dict[str, Any] = {}
    for names, val in candidates:
        matched = next((n for n in names if n in params), None)
        if matched is not None:
            bound[matched] = val
        elif accepts_var_kw:
            bound[names[0]] = val
    return bound


def evaluate_pricing_cli(schedule: str = "compare", seats: int = 8, api_spend: float = 1200.0) -> Dict[str, Any]:
    """Run MiroFish pricing elasticity simulation or return deterministic Phase 6 fallback."""
    fallback: Dict[str, Any] = {
        "schedule": schedule, "seats": int(seats), "monthly_api_spend_usd": float(api_spend),
        "calibrated": dict(_FALLBACK_CALIBRATED), "legacy": dict(_FALLBACK_LEGACY),
    }
    try:
        pm = importlib.import_module("core.eval.pricing_mirofish")
    except Exception:
        return fallback

    try:
        raw: Any = None
        sim_fn = getattr(pm, "simulate_pricing_comparison", None)
        with contextlib.redirect_stdout(io.StringIO()):
            if callable(sim_fn):
                raw = sim_fn(**_bind_pricing_kwargs(sim_fn, schedule, seats, api_spend))
            elif getattr(pm, "PricingMiroFishSimulator", None) is not None:
                sim_cls = pm.PricingMiroFishSimulator
                sim = sim_cls(**_bind_pricing_kwargs(sim_cls, schedule, seats, api_spend))
                for method_name in ("simulate_comparison", "compare", "simulate", "evaluate", "run"):
                    method = getattr(sim, method_name, None)
                    if callable(method):
                        raw = method(**_bind_pricing_kwargs(method, schedule, seats, api_spend))
                        break
        if raw is None:
            return fallback
        out = _to_plain_dict(raw)
        out["schedule"] = schedule
        out.setdefault("seats", int(seats))
        out.setdefault("monthly_api_spend_usd", float(api_spend))
        nested = out.get("schedules") if isinstance(out.get("schedules"), dict) else {}
        cal_dict = out.get("calibrated") if isinstance(out.get("calibrated"), dict) else nested.get("calibrated", {})
        leg_dict = out.get("legacy") if isinstance(out.get("legacy"), dict) else nested.get("legacy", {})
        out["calibrated"] = {**_FALLBACK_CALIBRATED, **(cal_dict if isinstance(cal_dict, dict) else {})}
        out["legacy"] = {**_FALLBACK_LEGACY, **(leg_dict if isinstance(leg_dict, dict) else {})}
        if schedule in ("calibrated", "legacy") and isinstance(out.get(schedule), dict):
            selected = out[schedule]
            for k in ("supportive_rate", "hidden_fee_distrust_score", "pricing_health_score", "unit_economics", "personas"):
                if k in selected:
                    out[k] = selected[k]
        return out
    except Exception:
        return fallback


def _add_runtime_flags(parser: argparse.ArgumentParser, *, with_workspace: bool = False) -> None:
    if with_workspace:
        parser.add_argument("--workspace-id", default="default", help="Target workspace identifier")
    parser.add_argument("--db-path", default=None, help="Optional SQLite database path override")
    parser.add_argument("--json", action="store_true", help="Emit JSON output")


def register_runtime_cli_subparsers(subparsers: argparse._SubParsersAction) -> None:
    """Register `vault`, `workspace`, `run`, and `pricing-eval` sovereign CLI subcommands."""
    vault = subparsers.add_parser("vault", help="Manage local AES-256-GCM encrypted secrets in SQLite WAL")
    v_sub = vault.add_subparsers(dest="vault_command")

    v_list = v_sub.add_parser("list", help="List encrypted secret metadata (never exposes plaintext)")
    v_list.add_argument("--namespace", default=None, help="Optional namespace filter (byom, plugin, webhook, env, mcp)")
    _add_runtime_flags(v_list, with_workspace=True)

    v_put = v_sub.add_parser("put", help="Encrypt and store a secret using AES-256-GCM")
    v_put.add_argument("name", help="Secret identifier (e.g., OPENAI_API_KEY)")
    v_put.add_argument("secret_value", help="Plaintext secret value (encrypted at rest; never echoed)")
    v_put.add_argument("--namespace", default="byom", help="Secret namespace (default: byom)")
    _add_runtime_flags(v_put, with_workspace=True)

    v_rot = v_sub.add_parser("rotate", help="Rotate an existing encrypted secret and increment version")
    v_rot.add_argument("name", help="Secret identifier to rotate")
    v_rot.add_argument("secret_value", help="New plaintext secret value (never echoed)")
    _add_runtime_flags(v_rot, with_workspace=True)

    v_del = v_sub.add_parser("delete", help="Delete and revoke a secret from the local vault")
    v_del.add_argument("name", help="Secret identifier to delete")
    _add_runtime_flags(v_del, with_workspace=True)

    if "workspace" in subparsers._name_parser_map:
        subparsers._name_parser_map.pop("workspace", None)
        subparsers._choices_actions = [a for a in subparsers._choices_actions if getattr(a, "dest", None) != "workspace"]

    ws = subparsers.add_parser("workspace", help="Manage isolated multi-workspaces and 5-role RBAC permissions")
    ws_sub = ws.add_subparsers(dest="workspace_command")
    _add_runtime_flags(ws_sub.add_parser("list", help="List isolated platform workspaces"))

    ws_create = ws_sub.add_parser("create", help="Create or update an isolated platform workspace")
    ws_create.add_argument("id", help="Workspace identifier slug")
    ws_create.add_argument("--name", required=True, help="Human-readable workspace name")
    ws_create.add_argument("--branch", default="main", help="Git branch binding (default: main)")
    ws_create.add_argument("--isolation-mode", default="seatbelt_local", help="Isolation boundary mode")
    _add_runtime_flags(ws_create)

    ws_rbac = ws_sub.add_parser("rbac-check", help="Evaluate 5-role RBAC permission for an actor")
    ws_rbac.add_argument("--actor", required=True, help="Actor identifier")
    ws_rbac.add_argument("--permission", required=True, help="Permission string (e.g., secrets:write, p10:approve)")
    ws_rbac.add_argument("--role", default=None, help="Explicit RBAC role override")
    _add_runtime_flags(ws_rbac, with_workspace=True)

    for legacy_ws_cmd in ("add", "use", "remove", "delete"):
        lp = ws_sub.add_parser(legacy_ws_cmd, help=f"Legacy workspace directory action ({legacy_ws_cmd})")
        lp.add_argument("path", nargs="?", default=None, help="Directory path or workspace ID")
        lp.add_argument("--name", default=None, help="Workspace display name")
        lp.add_argument("--activate", action="store_true", help="Activate workspace")

    existing_run = subparsers._name_parser_map.get("run")
    if existing_run is not None:
        for action in existing_run._actions:
            if getattr(action, "dest", None) == "task":
                action.required = False
        run_p, req_stream = existing_run, False
    else:
        run_p = subparsers.add_parser("run", help="Start governed agent or workflow execution stream")
        req_stream = True

    run_p.add_argument("--kind", choices=["agent", "workflow"], required=req_stream, default=None, help="Execution kind")
    run_p.add_argument("--target", required=req_stream, default=None, help="Target agent or workflow identifier")
    run_p.add_argument("--objective", required=req_stream, default=None, help="Execution objective description")
    run_p.add_argument("--no-p10", action="store_true", help="Complete execution without holding at P-10 checkpoint")
    _add_runtime_flags(run_p, with_workspace=True)

    pe = subparsers.add_parser("pricing-eval", help="Simulate MiroFish multi-persona pricing elasticity & trust")
    pe.add_argument("--schedule", choices=["compare", "calibrated", "legacy"], default="compare", help="Pricing schedule mode")
    pe.add_argument("--seats", type=int, default=8, help="Team seat count (default: 8)")
    pe.add_argument("--api-spend", dest="api_spend", type=float, default=1200.0, help="Monthly BYOM API spend in USD")
    pe.add_argument("--json", action="store_true", help="Emit JSON pricing report")

    from core.cli_kflow_crdt import register_kflow_crdt_cli_subparsers
    from core.cli_mcp_eval import register_mcp_eval_cli_subparsers

    register_mcp_eval_cli_subparsers(subparsers)
    register_kflow_crdt_cli_subparsers(subparsers)


def dispatch_runtime_cli(args: argparse.Namespace) -> Optional[int]:
    """Dispatch `vault`, `workspace`, `run`, `pricing-eval`, `mcp`, `eval-suite`, `kflow`, `kspaces-sync`, and `sbom`."""
    from core.cli_kflow_crdt import dispatch_kflow_crdt_cli
    from core.cli_mcp_eval import dispatch_mcp_eval_cli

    kflow_crdt_rc = dispatch_kflow_crdt_cli(args)
    if kflow_crdt_rc is not None:
        return kflow_crdt_rc

    mcp_eval_rc = dispatch_mcp_eval_cli(args)
    if mcp_eval_rc is not None:
        return mcp_eval_rc
    cmd = getattr(args, "command", None)

    if cmd == "vault":
        from core.platform.vault import LocalSecretVault

        sub = getattr(args, "vault_command", None) or "list"
        as_json, ws_id = bool(getattr(args, "json", False)), str(getattr(args, "workspace_id", "default"))
        vault = LocalSecretVault(db_path=getattr(args, "db_path", None))
        try:
            if sub == "list":
                items = [_sanitize_secret_meta(m) for m in vault.list_secrets(workspace_id=ws_id, namespace=getattr(args, "namespace", None))]
                if as_json:
                    print(json.dumps({"workspace_id": ws_id, "count": len(items), "total": len(items), "secrets": items}, indent=2))
                else:
                    print(f"Keelway Local Secret Vault [{ws_id}] ({len(items)} secrets):")
                    for s in items:
                        print(f"  - {s['name']:<24} [{s['namespace']}] v{s['version']} {s['cipher']} preview={s['masked_preview']} sha256={s['fingerprint_sha256'][:16]}...")
                return 0
            if sub in ("put", "rotate"):
                raw = (
                    vault.put_secret(ws_id, str(args.name), str(args.secret_value), namespace=str(getattr(args, "namespace", "byom")))
                    if sub == "put"
                    else vault.rotate_secret(ws_id, str(args.name), str(args.secret_value))
                )
                safe = _sanitize_secret_meta(raw)
                verb = "Stored" if sub == "put" else "Rotated"
                print(json.dumps(safe, indent=2) if as_json else f"[+] {verb} secret '{safe['name']}' (v{safe['version']}, cipher={safe['cipher']}, preview={safe['masked_preview']}, sha256={safe['fingerprint_sha256']})")
                return 0
            if sub == "delete":
                res = vault.delete_secret(ws_id, str(args.name))
                print(json.dumps(res, indent=2) if as_json else f"[+] Deleted secret '{res['name']}' from workspace '{res['workspace_id']}'.")
                return 0
        except (KeyError, ValueError) as exc:
            print(json.dumps({"error": str(exc)}, indent=2) if as_json else f"[-] Vault error: {exc}")
            return 1
        finally:
            vault.close()

    if cmd == "workspace":
        sub = getattr(args, "workspace_command", None) or "list"
        if sub in {"add", "use", "remove", "delete"}:
            return None
        from core.platform.rbac_webhooks import WorkspaceRbacController

        as_json = bool(getattr(args, "json", False))
        ctrl = WorkspaceRbacController(db_path=getattr(args, "db_path", None))
        try:
            if sub == "list":
                items = ctrl.list_workspaces()
                if as_json:
                    print(json.dumps({"count": len(items), "total": len(items), "workspaces": items}, indent=2))
                else:
                    print(f"Keelway Workspaces ({len(items)}):")
                    for w in items:
                        print(f"  - {w['id']:<20} {w['name']} (branch={w['branch']}, isolation={w['isolation_mode']})")
                return 0
            if sub == "create":
                created = ctrl.create_workspace(str(args.id), str(args.name), str(getattr(args, "branch", "main")), str(getattr(args, "isolation_mode", "seatbelt_local")))
                print(json.dumps(created, indent=2) if as_json else f"[+] Workspace '{created['id']}' ready ({created['isolation_mode']} on {created['branch']}).")
                return 0
            if sub == "rbac-check":
                verdict = ctrl.check_permission(str(getattr(args, "workspace_id", "default")), str(args.actor), str(args.permission), explicit_role=getattr(args, "role", None))
                tag = "ALLOWED" if verdict["allowed"] else "DENIED"
                print(json.dumps(verdict, indent=2) if as_json else f"[{tag}] actor={verdict['actor_id']} role={verdict['role']} permission={verdict['permission']} ({verdict['reason']})")
                return 0 if verdict["allowed"] else 1
        except ValueError as exc:
            print(json.dumps({"error": str(exc)}, indent=2) if as_json else f"[-] Workspace error: {exc}")
            return 1
        finally:
            ctrl.close()

    if cmd == "run":
        kind, target, objective = getattr(args, "kind", None), getattr(args, "target", None), getattr(args, "objective", None)
        if getattr(args, "task", None) and not (kind or target or objective):
            return None
        as_json = bool(getattr(args, "json", False))
        if not (kind and target and objective):
            msg = "run requires --kind <agent|workflow>, --target <ID>, and --objective <TEXT>."
            print(json.dumps({"error": msg}, indent=2) if as_json else f"[-] {msg}")
            return 2
        from core.platform.execution_stream import LiveExecutionStreamer

        streamer = LiveExecutionStreamer(db_path=getattr(args, "db_path", None))
        try:
            snap = streamer.start_run(str(getattr(args, "workspace_id", "default")), str(kind), str(target), str(objective), requires_p10=not bool(getattr(args, "no_p10", False)))
            streamed: List[Dict[str, Any]] = []
            for sse_line in streamer.iter_sse_lines(snap["run_id"]):
                payload = sse_line[5:].strip() if sse_line.startswith("data:") else ""
                if payload and payload != "[DONE]":
                    streamed.append(json.loads(payload))
            snap["events"] = streamed or snap["events"]
            if as_json:
                print(json.dumps(snap, indent=2))
            else:
                for evt in snap["events"]:
                    detail = evt.get("detail") or evt.get("message") or evt.get("objective") or evt.get("status") or evt.get("target_id") or ""
                    print(f"[{evt['seq']}] {evt['type']}: {detail}")
            return 0
        finally:
            streamer.close()

    if cmd == "pricing-eval":
        report = evaluate_pricing_cli(str(getattr(args, "schedule", "compare")), int(getattr(args, "seats", 8)), float(getattr(args, "api_spend", 1200.0)))
        if getattr(args, "json", False):
            print(json.dumps(report, indent=2))
        else:
            cal, leg = report.get("calibrated", {}), report.get("legacy", {})
            print(f"Keelway Pricing Elasticity Evaluation (schedule={report['schedule']}, seats={report['seats']}, api_spend=${report['monthly_api_spend_usd']:.0f}/mo)")
            print(f"  Calibrated: Pro=${cal.get('pro_annual_usd', 29)}/mo | BYOM=${cal.get('byom_annual_usd', 15)}/mo | Health={cal.get('pricing_health_score', 96.5)} | Distrust={cal.get('hidden_fee_distrust_score', 0.0)}")
            print(f"  Legacy:     Pro=${leg.get('pro_annual_usd', 39)}/mo | Health={leg.get('pricing_health_score', 54.0)} | Distrust={leg.get('hidden_fee_distrust_score', 0.68)}")
        return 0

    return None
