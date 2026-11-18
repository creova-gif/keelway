"""
Keelway Sovereign CLI Phase 9 Enterprise Subcommands (`sso`, `scim`, `siem-export`, `metrics`).

Registered and dispatched via `core.cli_runtime` with `--json` output and deterministic exit codes.
"""

from __future__ import annotations

import argparse
import json
from typing import Dict, List, Optional


def _add_enterprise_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--workspace",
        "--workspace-id",
        dest="workspace_id",
        default="default",
        help="Target workspace identifier (default: default)",
    )
    parser.add_argument("--db-path", default=None, help="Optional SQLite database path override")
    parser.add_argument("--json", action="store_true", help="Emit JSON output")


def _parse_group_mappings(raw_items: List[str]) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    for item in raw_items:
        text = str(item or "").strip()
        if not text:
            continue
        if "=" not in text:
            raise ValueError(f"Invalid --map '{text}'; expected <group>=<role> (e.g., keelway-operators=operator).")
        grp, role = text.split("=", 1)
        mapping[grp.strip()] = role.strip()
    return mapping


def register_enterprise_cli_subparsers(subparsers: argparse._SubParsersAction) -> None:
    """Register `sso`, `scim`, `siem-export`, and `metrics` sovereign CLI subcommands."""
    sso = subparsers.add_parser("sso", help="Configure and inspect OIDC/SAML enterprise SSO federation")
    sso_sub = sso.add_subparsers(dest="sso_command", required=True)

    sso_status = sso_sub.add_parser("status", help="Inspect workspace OIDC/SAML SSO provider status")
    _add_enterprise_flags(sso_status)

    sso_cfg = sso_sub.add_parser("configure", help="Configure workspace OIDC/SAML SSO federation")
    sso_cfg.add_argument("--issuer", "--issuer-url", dest="issuer_url", required=True, help="OIDC issuer URL")
    sso_cfg.add_argument("--client-id", dest="client_id", required=True, help="OIDC client ID")
    sso_cfg.add_argument("--secret", "--signing-secret", dest="signing_secret", default=None, help="HS256 signing secret (>= 16 chars)")
    sso_cfg.add_argument("--map", dest="mappings", action="append", default=[], help="Group-to-role mapping <group>=<role> (repeatable)")
    sso_cfg.add_argument("--disable", action="store_true", help="Store OIDC configuration in disabled state")
    _add_enterprise_flags(sso_cfg)

    sso_ex = sso_sub.add_parser("exchange", help="Verify and exchange a compact HS256 OIDC ID token")
    sso_ex.add_argument("--id-token", "--token", dest="id_token", required=True, help="Compact JWT ID token")
    _add_enterprise_flags(sso_ex)

    scim = subparsers.add_parser("scim", help="Manage SCIM 2.0 enterprise directory user provisioning")
    scim_sub = scim.add_subparsers(dest="scim_command", required=True)

    scim_list = scim_sub.add_parser("list", help="List SCIM 2.0 directory users in workspace")
    _add_enterprise_flags(scim_list)

    scim_prov = scim_sub.add_parser("provision", help="Provision or update a SCIM 2.0 directory user")
    scim_prov.add_argument("--user", "--user-name", dest="user_name", required=True, help="SCIM userName (e.g., sre@enterprise.example)")
    scim_prov.add_argument("--display-name", dest="display_name", default="", help="Human displayName")
    scim_prov.add_argument("--group", dest="groups", action="append", default=[], help="IdP group membership (repeatable)")
    scim_prov.add_argument("--inactive", action="store_true", help="Provision user in deactivated state")
    _add_enterprise_flags(scim_prov)

    scim_deact = scim_sub.add_parser("deactivate", help="Deactivate a SCIM 2.0 user and revoke privileged RBAC")
    scim_deact.add_argument("--id", dest="scim_user_id", required=True, help="SCIM user ID")
    _add_enterprise_flags(scim_deact)

    siem = subparsers.add_parser("siem-export", help="Export DLP-redacted tamper-evident SIEM audit batch")
    siem.add_argument("--format", dest="export_format", default="ocsf", help="SIEM export format: ocsf, cef, or jsonl")
    siem.add_argument("--limit", type=int, default=50, help="Maximum audit records to export (default: 50)")
    _add_enterprise_flags(siem)

    metrics = subparsers.add_parser("metrics", help="Export Prometheus 0.0.4 or OpenTelemetry OTLP metrics")
    metrics.add_argument("--format", dest="metrics_format", default="otlp_json", help="Metrics format: prometheus or otlp_json")
    _add_enterprise_flags(metrics)


def dispatch_enterprise_cli(args: argparse.Namespace) -> Optional[int]:
    """Dispatch `sso`, `scim`, `siem-export`, and `metrics`. Returns exit code or None."""
    cmd = getattr(args, "command", None)
    if cmd not in {"sso", "scim", "siem-export", "metrics"}:
        return None

    from core.platform.enterprise_identity_siem import EnterpriseIdentitySiemManager
    from core.platform.rbac_webhooks import WorkspaceRbacController

    ws_id = str(getattr(args, "workspace_id", "default") or "default")
    db_path = getattr(args, "db_path", None)
    as_json = bool(getattr(args, "json", False))
    manager = EnterpriseIdentitySiemManager(db_path=db_path)

    try:
        if cmd == "sso":
            sub = getattr(args, "sso_command", None)
            if sub == "status":
                res = manager.get_oidc(workspace_id=ws_id)
                if as_json:
                    print(json.dumps(res, indent=2))
                else:
                    state = "ENABLED" if res["enabled"] else "DISABLED"
                    print(f"Keelway Enterprise OIDC [{ws_id}] {state} issuer={res['issuer_url'] or 'unconfigured'} client={res['client_id'] or '-'}")
                return 0
            if sub == "configure":
                mapping = _parse_group_mappings(list(getattr(args, "mappings", None) or []))
                res = manager.configure_oidc(
                    workspace_id=ws_id,
                    issuer_url=str(args.issuer_url),
                    client_id=str(args.client_id),
                    signing_secret=getattr(args, "signing_secret", None),
                    group_role_mapping=mapping,
                    enabled=not bool(getattr(args, "disable", False)),
                )
                if as_json:
                    print(json.dumps(res, indent=2))
                else:
                    print(f"[+] Configured OIDC [{ws_id}] issuer={res['issuer_url']} fp={res['signing_secret_fingerprint']}")
                return 0
            if sub == "exchange":
                res = manager.exchange_oidc_token(workspace_id=ws_id, id_token=str(args.id_token))
                print(json.dumps(res, indent=2) if as_json else f"[+] Authenticated subject={res['subject']} role={res['mapped_role']}")
                return 0

        if cmd == "scim":
            sub = getattr(args, "scim_command", None)
            if sub == "list":
                res = manager.list_scim_users(workspace_id=ws_id)
                if as_json:
                    print(json.dumps(res, indent=2))
                else:
                    print(f"Keelway SCIM 2.0 Directory [{ws_id}] ({res['totalResults']} users):")
                    for u in res["Resources"]:
                        print(f"  - {u['id']} {u['userName']} role={u['mapped_role']} active={u['active']}")
                return 0
            rbac = WorkspaceRbacController(db_path=manager.db_path)
            try:
                if sub == "provision":
                    res = manager.provision_scim_user(
                        workspace_id=ws_id,
                        user_name=str(args.user_name),
                        display_name=str(getattr(args, "display_name", "")),
                        groups=list(getattr(args, "groups", None) or []),
                        active=not bool(getattr(args, "inactive", False)),
                        rbac=rbac,
                    )
                    print(json.dumps(res, indent=2) if as_json else f"[+] Provisioned SCIM user {res['userName']} ({res['id']}) role={res['mapped_role']}")
                    return 0
                if sub == "deactivate":
                    res = manager.patch_scim_user(workspace_id=ws_id, scim_user_id=str(args.scim_user_id), active=False, rbac=rbac)
                    print(json.dumps(res, indent=2) if as_json else f"[+] Deactivated SCIM user {res['userName']} ({res['id']}) role={res['mapped_role']}")
                    return 0
            finally:
                rbac.close()

        if cmd == "siem-export":
            res = manager.export_siem(
                workspace_id=ws_id,
                export_format=str(getattr(args, "export_format", "ocsf")),
                limit=int(getattr(args, "limit", 50)),
            )
            if as_json:
                print(json.dumps(res, indent=2))
            else:
                print(f"[+] SIEM Export [{ws_id}] format={res['format']} records={res['record_count']} batch={res['batch_sha256']}")
            return 0

        if cmd == "metrics":
            res = manager.get_observability_metrics(
                workspace_id=ws_id,
                metrics_format=str(getattr(args, "metrics_format", "otlp_json")),
            )
            if as_json:
                print(json.dumps(res, indent=2))
            elif res["format"] == "prometheus":
                print(res["prometheus_text"], end="")
            else:
                print(json.dumps(res["otlp_resource_metrics"], indent=2))
            return 0
    except (KeyError, PermissionError, RuntimeError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}, indent=2) if as_json else f"[-] Enterprise CLI error: {exc}")
        return 1
    finally:
        manager.close()

    return None
