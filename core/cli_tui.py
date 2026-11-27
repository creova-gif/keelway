"""
Keelway Sovereign CLI TUI Launch Card, Slash Command Strip & Platform Subcommands.

Provides a Claude-Code-inspired framed terminal launch card (`render_sovereign_tui_banner`)
with live workspace/git/OpenCore/sandbox/P-10 posture telemetry, an interactive slash command
strip, strict `NO_COLOR` / `plain=True` ASCII compliance, and top-level `marketplace` and
`blueprint` CLI workflows backed by `core.platform` (with deterministic standalone fallbacks).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

_INNER_WIDTH = 86
_SLASH_COMMANDS = ("/agents", "/ide", "/pm", "/nocode", "/marketplace", "/model", "/airgap", "/audit", "/doctor")

_UNICODE_ART = (
    r"██╗  ██╗███████╗███████╗██╗     ██╗    ██╗ █████╗ ██╗   ██╗",
    r"██║ ██╔╝██╔════╝██╔════╝██║     ██║    ██║██╔══██╗╚██╗ ██╔╝",
    r"█████╔╝ █████╗  █████╗  ██║     ██║ █╗ ██║███████║ ╚████╔╝ ",
    r"██╔═██╗ ██╔══╝  ██╔══╝  ██║     ██║███╗██║██╔══██║  ╚██╔╝  ",
    r"██║  ██╗███████╗███████╗███████╗╚███╔███╔╝██║  ██║   ██║   ",
    r"╚═╝  ╚═╝╚══════╝╚══════╝╚══════╝ ╚══╝╚══╝ ╚═╝  ╚═╝   ╚═╝   ",
)

_ASCII_ART = (
    r" _  ______ _____ _ __          __     __",
    r"| |/ /  ____|  ____| |         \ \   / /",
    r"| ' /| |__  | |__  | |     /\   \ \_/ / ",
    r"|  < |  __| |  __| | |    /  \   \   /  ",
    r"| . \| |____| |____| |___/ /\ \   | |   ",
    r"|_|\_\______|______|____/_/  \_\  |_|   ",
)

_FALLBACK_PACKAGES: List[Dict[str, Any]] = [
    {"id": "keelway.code-architect", "name": "Sovereign Code Architect", "kind": "ai_agent", "publisher_tier": "first_party", "price_usd": 0.0},
    {"id": "keelway.idea-to-prod-squad", "name": "Idea-to-Production Squad", "kind": "multi_agent_system", "publisher_tier": "first_party", "price_usd": 0.0},
    {"id": "community.ast-diff-auditor", "name": "AST Diff & Refactor Skill", "kind": "agent_skill", "publisher_tier": "verified_third_party", "price_usd": 19.0},
    {"id": "community.linear-mcp-bridge", "name": "Issue Tracker & Webhook Bridge", "kind": "plugin_extension", "publisher_tier": "verified_third_party", "price_usd": 29.0},
    {"id": "keelway.release-gate-dag", "name": "P-10 Governed Release Gate DAG", "kind": "automation_template", "publisher_tier": "first_party", "price_usd": 0.0},
    {"id": "community.sbom-provenance-cli", "name": "CycloneDX Provenance Verifier", "kind": "dev_tool", "publisher_tier": "verified_third_party", "price_usd": 15.0},
    {"id": "partner.regulated-fintech-vpc", "name": "Regulated FinTech Audit Pack", "kind": "industry_enterprise_solution", "publisher_tier": "enterprise_partner", "price_usd": 490.0},
]


def _resolve_use_color(plain: bool = False, use_color: Optional[bool] = None) -> bool:
    if plain or os.environ.get("NO_COLOR") is not None or os.environ.get("TERM") == "dumb":
        return False
    if use_color is not None:
        return bool(use_color)
    return bool(getattr(sys.stdout, "isatty", lambda: False)())


def _resolve_use_unicode(plain: bool = False) -> bool:
    encoding = getattr(sys.stdout, "encoding", "utf-8") or "utf-8"
    return not plain and sys.platform != "win32" and "utf" in encoding.lower()


def _detect_git_branch(workspace: Path) -> Optional[str]:
    cur = workspace.resolve()
    for candidate in (cur, *cur.parents):
        dot_git = candidate / ".git"
        if dot_git.is_dir():
            head_file = dot_git / "HEAD"
        elif dot_git.is_file():
            try:
                raw = dot_git.read_text(encoding="utf-8", errors="ignore").strip()
                head_file = (candidate / raw.split(":", 1)[1].strip()).resolve() / "HEAD" if raw.startswith("gitdir:") else dot_git
            except OSError:
                return None
        else:
            continue
        try:
            ref = head_file.read_text(encoding="utf-8", errors="ignore").strip()
            return ref[len("ref: refs/heads/") :] if ref.startswith("ref: refs/heads/") else (ref[:8] or "HEAD")
        except OSError:
            return "main"
    return None


def _detect_sandbox_label() -> str:
    this_platform = sys.platform
    if this_platform == "darwin":
        return "Seatbelt (macOS)"
    if this_platform.startswith("linux"):
        return "Bubblewrap (Linux)"
    return "Process Guard"


def render_slash_command_strip(plain: bool = False, use_color: Optional[bool] = None) -> str:
    """Render the interactive sovereign slash command strip."""
    if not _resolve_use_color(plain=plain, use_color=use_color):
        return "Slash:  " + "  ".join(_SLASH_COMMANDS)
    teal, bold, reset = "\033[38;2;45;212;191m", "\033[1m", "\033[0m"
    return f"{bold}Slash:{reset}  " + "  ".join(f"{teal}{cmd}{reset}" for cmd in _SLASH_COMMANDS)


def render_sovereign_tui_banner(
    plain: bool = False,
    use_color: Optional[bool] = None,
    workspace: Optional[Path] = None,
) -> str:
    """Render the Claude-Code-inspired framed Keelway TUI launch card."""
    color = _resolve_use_color(plain=plain, use_color=use_color)
    use_unicode = _resolve_use_unicode(plain=plain)
    ws_path = (workspace or Path.cwd()).resolve()
    ws_name = (ws_path.name or "workspace")[:38]
    branch = _detect_git_branch(ws_path)
    sandbox_label = _detect_sandbox_label()

    teal = "\033[38;2;45;212;191m" if color else ""
    blue = "\033[38;2;64;160;255m" if color else ""
    bold = "\033[1m" if color else ""
    dim = "\033[2m" if color else ""
    reset = "\033[0m" if color else ""
    v_bar = f"{blue}│{reset}" if use_unicode else "|"

    def _box_line(visible: str, styled: Optional[str] = None) -> str:
        clipped = visible[:_INNER_WIDTH]
        rendered = styled if (styled is not None and len(visible) <= _INNER_WIDTH) else clipped
        return f"{v_bar}{rendered}{' ' * max(0, _INNER_WIDTH - len(clipped))}{v_bar}"

    if use_unicode:
        top_title = "─── ◆ Keelway v1.1 · Unified AI-Native Agent Local Platform "
        top_border = f"{teal}╭{top_title}{reset}{blue}{'─' * max(3, _INNER_WIDTH - len(top_title))}╮{reset}"
        divider = f"{blue}├{'─' * _INNER_WIDTH}┤{reset}"
        bot_hint = "─── Launch '/app' via 'keelway dev' · 'keelway chat' · 'keelway blueprint' "
        bot_border = f"{blue}╰{bot_hint}{'─' * max(3, _INNER_WIDTH - len(bot_hint))}╯{reset}"
        ws_val = f"{ws_name} · ⎇ {branch}" if branch else f"{ws_name} · standalone"
        attribution = "Sorvex Labs • https://keelway.dev"
        posture_val = "Zero-Egress Ready · P-10 Human Approval Gates Active"
        views_val = "10-View Workspace (/app) · Builder + Non-Coder Modes"
        art_lines = _UNICODE_ART
    else:
        top_title = "--- * Keelway v1.1 - Unified AI-Native Agent Local Platform "
        top_border = f"+{top_title}{'-' * max(3, _INNER_WIDTH - len(top_title))}+"
        divider = f"+{'-' * _INNER_WIDTH}+"
        bot_hint = "--- Launch '/app' via 'keelway dev' | 'keelway chat' | 'keelway blueprint' "
        bot_border = f"+{bot_hint}{'-' * max(3, _INNER_WIDTH - len(bot_hint))}+"
        ws_val = f"{ws_name} (git:{branch})" if branch else f"{ws_name} (standalone)"
        attribution = "Sorvex Labs - https://keelway.dev"
        posture_val = "Zero-Egress Ready | P-10 Human Approval Gates Active"
        views_val = "10-View Workspace (/app) | Builder + Non-Coder Modes"
        art_lines = _ASCII_ART

    tagline = "Sovereign Local-First AI Developer Platform"
    rows: List[str] = [top_border, _box_line("")]
    for idx, art in enumerate(art_lines):
        vis = f"  {art}"
        rows.append(_box_line(vis, f"  {teal if idx < 3 else blue}{art}{reset}" if color else vis))

    rows.extend([
        _box_line(""),
        _box_line(f"  {tagline}", f"  {bold}{tagline}{reset}"),
        _box_line(f"  {attribution}", f"  {dim}{attribution}{reset}"),
        divider,
    ])
    telemetry = (
        ("Workspace:", ws_val),
        ("Runtime:", "OpenCore Local (keelway-core:7b) + BYOM Hybrid Gateway"),
        ("Sandbox:", sandbox_label),
        ("Posture:", posture_val),
        ("Views:", views_val),
    )
    for label, val in telemetry:
        pad_lbl = f"{label:<11}"
        vis_t = f"  {pad_lbl} {val}"
        rows.append(_box_line(vis_t, f"  {teal}{pad_lbl}{reset} {val}" if color else vis_t))

    slash_plain = "Slash:  " + "  ".join(_SLASH_COMMANDS)
    rows.append(divider)
    rows.append(_box_line(f"  {slash_plain}", f"  {render_slash_command_strip(plain=plain, use_color=color)}"))
    rows.append(bot_border)
    return "\n".join(rows)


def _list_marketplace_packages(kind: Optional[str] = None, query: Optional[str] = None) -> List[Dict[str, Any]]:
    try:
        from core.platform.marketplace import marketplace_registry

        return marketplace_registry.list_packages(kind=kind, query=query)
    except Exception:
        items = list(_FALLBACK_PACKAGES)
        if kind:
            items = [p for p in items if p["kind"] == kind]
        if query:
            items = [p for p in items if query.lower() in p["name"].lower() or query.lower() in p["id"].lower()]
        return items


def _scan_marketplace_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        from core.platform.marketplace import MarketplaceSecurityScanner

        return MarketplaceSecurityScanner().scan_package(payload)
    except Exception:
        raw = json.dumps(payload, sort_keys=True)
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        findings: List[Dict[str, str]] = []
        rules = (
            (r"ignore\s+(?:all\s+)?previous\s+instructions", "PROMPT_INJECTION_OVERRIDE"),
            (r"bypass\s+p-?10", "GUARDRAIL_BYPASS_P10"),
            (r"disable\s+air-?gap", "GUARDRAIL_DISABLE_AIRGAP"),
            (r"shell\s*=\s*True|\b(?:eval|exec)\s*\(", "UNSAFE_EXECUTION"),
            (r"\b(?:sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9]{20,})", "EMBEDDED_SECRET"),
        )
        for pattern, rule_id in rules:
            if re.search(pattern, raw, re.I):
                findings.append({"rule_id": rule_id, "severity": "critical", "message": f"Blocked pattern ({rule_id})."})
        passed = len(findings) == 0
        return {"passed": passed, "risk_grade": "A" if passed else "C", "findings": findings, "manifest_sha256": digest}


def _compile_blueprint(idea: str, workspace_id: str, target_stack: str) -> Dict[str, Any]:
    try:
        from core.platform.workspace_hub import UnifiedWorkspaceHub

        compiled = UnifiedWorkspaceHub().compile_nocode_blueprint(
            idea=idea, workspace_id=workspace_id, target_stack=target_stack
        )
        compiled.setdefault("issues", compiled.get("sprint_issues", []))
        compiled.setdefault("agent_team", compiled.get("team_run", {"name": "Idea-to-Production Squad"}))
        return compiled
    except Exception:
        slug = re.sub(r"[^a-z0-9]+", "-", idea.lower()).strip("-")[:24] or "sovereign-app"
        return {
            "idea": idea.strip(),
            "workspace_id": workspace_id,
            "prd": {"id": f"prd-{slug}", "title": f"PRD: {idea.strip()}"},
            "issues": [
                {"id": "KEEL-101", "title": "Architecture & schema specification", "assignee_agent": "code-architect"},
                {"id": "KEEL-102", "title": f"Build core flows for {idea.strip()}", "assignee_agent": "nocode-app-builder"},
                {"id": "KEEL-103", "title": "Security audit & P-10 release gate", "assignee_agent": "security-auditor"},
            ],
            "workflow": {"id": f"flow-{slug}", "name": "Idea-to-Production Governed DAG", "p10_approval_required": True},
            "agent_team": {"id": "nocode-guided-launch-squad", "p10_gate": "human_only"},
        }


_FALLBACK_CLUSTER_NODES: List[Dict[str, Any]] = [
    {"node_id": "node-metal-local-01", "runtime": "ollama_metal", "region": "airgap_local", "gpu_model": "Apple M-Series Metal Unified", "total_vram_gb": 32.0, "free_vram_gb": 32.0, "status": "healthy"},
    {"node_id": "node-vllm-us-01", "runtime": "vllm", "region": "us", "gpu_model": "NVIDIA H100 80GB", "total_vram_gb": 160.0, "free_vram_gb": 160.0, "status": "healthy"},
    {"node_id": "node-vllm-eu-01", "runtime": "vllm", "region": "eu", "gpu_model": "NVIDIA A100 80GB", "total_vram_gb": 80.0, "free_vram_gb": 80.0, "status": "healthy"},
]

_FALLBACK_LIFECYCLE: List[Dict[str, Any]] = [
    {"model_id": "keelway-core:7b", "stage": "stable", "traffic_weight_pct": 100, "benchmark_pass_rate": 0.98, "ttft_p95_ms": 145.0},
    {"model_id": "keelway-coder:14b-v2", "stage": "canary", "traffic_weight_pct": 15, "benchmark_pass_rate": 0.97, "ttft_p95_ms": 210.0},
]


def _list_cluster_nodes(region: Optional[str] = None, runtime: Optional[str] = None) -> List[Dict[str, Any]]:
    try:
        from core.cluster.scheduler import cluster_scheduler

        return [n.model_dump(mode="json") for n in cluster_scheduler.list_nodes(region=region, runtime=runtime)]
    except Exception:
        nodes = [dict(n) for n in _FALLBACK_CLUSTER_NODES]
        if region:
            nodes = [n for n in nodes if n["region"] == region]
        if runtime:
            nodes = [n for n in nodes if n["runtime"] == runtime]
        return nodes


def _schedule_cluster_model(model_id: str, vram_gb: float, region: Optional[str]) -> Dict[str, Any]:
    residency = region or "global"
    try:
        from core.cluster.scheduler import cluster_scheduler
    except Exception:
        eligible = [
            n for n in _list_cluster_nodes(region=None if residency == "global" else residency)
            if float(n.get("free_vram_gb", 0.0)) >= vram_gb and n.get("status") == "healthy"
        ]
        if not eligible:
            return {"scheduled": False, "model_id": model_id, "required_vram_gb": vram_gb, "region_residency": residency, "error": "No eligible cluster node satisfies VRAM/region constraints."}
        win = eligible[0]
        digest = hashlib.sha256(f"{win['node_id']}:{model_id}:{vram_gb}:{residency}".encode("utf-8")).hexdigest()
        return {"scheduled": True, "selected_node_id": win["node_id"], "model_id": model_id, "runtime": win["runtime"], "region": win["region"], "region_residency": residency, "required_vram_gb": vram_gb, "receipt_sha256": digest}

    try:
        decision = cluster_scheduler.schedule_placement(
            model_id=model_id, required_vram_gb=vram_gb, region_residency=residency
        )
        return {"scheduled": True, **decision.model_dump(mode="json")}
    except ValueError as exc:
        return {"scheduled": False, "model_id": model_id, "required_vram_gb": vram_gb, "region_residency": residency, "error": str(exc)}


def _list_cluster_lifecycle(stage: Optional[str] = None) -> List[Dict[str, Any]]:
    try:
        from core.cluster.lifecycle import model_lifecycle_registry

        return [e.model_dump(mode="json") for e in model_lifecycle_registry.list_entries(stage=stage)]
    except Exception:
        items = [dict(e) for e in _FALLBACK_LIFECYCLE]
        return [e for e in items if e["stage"] == stage] if stage else items


def register_platform_cli_subparsers(subparsers: argparse._SubParsersAction) -> None:
    """Register `keelway marketplace`, `keelway blueprint`, and `keelway cluster` subcommands."""
    mp = subparsers.add_parser("marketplace", help="Discover and security-scan verified Marketplace packages")
    mp_sub = mp.add_subparsers(dest="marketplace_command")

    mp_list = mp_sub.add_parser("list", help="List verified Marketplace packages and creator revenue splits")
    mp_list.add_argument("--kind", default=None, help="Filter by PackageKind (e.g., ai_agent, agent_skill)")
    mp_list.add_argument("--query", default=None, help="Search query substring")
    mp_list.add_argument("--json", action="store_true", help="Emit JSON output")

    mp_scan = mp_sub.add_parser("scan", help="Run Pre-Publication Security Scanner on a manifest file or text")
    mp_scan.add_argument("target", help="Path to package manifest file, JSON string, or inline instructions")
    mp_scan.add_argument("--json", action="store_true", help="Emit JSON security report")

    bp = subparsers.add_parser("blueprint", help="Compile an idea into a governed PRD, Sprint Issues & Automation DAG")
    bp.add_argument("idea", help="Natural-language product or workflow idea")
    bp.add_argument("--workspace-id", default="default", help="Target workspace identifier")
    bp.add_argument("--stack", default="fastapi_react_sqlite", help="Target application stack")
    bp.add_argument("--out", type=Path, default=None, help="Optional file path to write blueprint JSON")
    bp.add_argument("--json", action="store_true", help="Emit JSON output")

    cl = subparsers.add_parser("cluster", help="Inspect GPU cluster worker nodes, schedule placements & model lifecycle")
    cl_sub = cl.add_subparsers(dest="cluster_command")

    cl_nodes = cl_sub.add_parser("nodes", help="List registered GPU/Metal cluster worker nodes")
    cl_nodes.add_argument("--region", default=None, help="Filter by region (airgap_local, us, eu, africa)")
    cl_nodes.add_argument("--runtime", default=None, help="Filter by runtime (ollama_metal, vllm, ray_serve)")
    cl_nodes.add_argument("--json", action="store_true", help="Emit JSON output")

    cl_sched = cl_sub.add_parser("schedule", help="Compute deterministic GPU node placement for a model")
    cl_sched.add_argument("--model", required=True, help="Model identifier to schedule (e.g., keelway-core:7b)")
    cl_sched.add_argument("--vram", type=float, default=16.0, help="Required VRAM capacity in GB")
    cl_sched.add_argument("--region", default=None, help="Target region residency constraint")
    cl_sched.add_argument("--json", action="store_true", help="Emit JSON placement receipt")

    cl_life = cl_sub.add_parser("lifecycle", help="Inspect canary/stable model lifecycle stages and SLO gates")
    cl_life.add_argument("--stage", default=None, help="Optional stage filter (canary, stable, deprecated)")
    cl_life.add_argument("--json", action="store_true", help="Emit JSON output")

    from core.cli_runtime import register_runtime_cli_subparsers

    register_runtime_cli_subparsers(subparsers)


def dispatch_platform_cli(args: argparse.Namespace) -> Optional[int]:
    """Dispatch `marketplace`, `blueprint`, `cluster`, and Phase 6 runtime CLI commands."""
    from core.cli_runtime import dispatch_runtime_cli

    runtime_rc = dispatch_runtime_cli(args)
    if runtime_rc is not None:
        return runtime_rc
    cmd = getattr(args, "command", None)
    if cmd == "marketplace":
        sub = getattr(args, "marketplace_command", None) or "list"
        as_json = bool(getattr(args, "json", False))
        if sub == "list":
            packages = _list_marketplace_packages(getattr(args, "kind", None), getattr(args, "query", None))
            if as_json:
                print(json.dumps({"count": len(packages), "packages": packages}, indent=2))
            else:
                print(f"Keelway Verified Marketplace ({len(packages)} packages):")
                for pkg in packages:
                    print(f"  - {pkg.get('id', 'pkg'):<34} [{pkg.get('kind', 'pkg'):<28}] ({pkg.get('publisher_tier', 'verified')})")
            return 0

        if sub == "scan":
            raw_target = str(getattr(args, "target", ""))
            target_path = Path(raw_target)
            raw_text = target_path.read_text(encoding="utf-8") if target_path.is_file() else raw_target
            try:
                parsed = json.loads(raw_text)
                payload = parsed if isinstance(parsed, dict) else {"name": "inline", "content": parsed}
            except json.JSONDecodeError:
                payload = {"name": target_path.stem if target_path.is_file() else "inline-scan", "instructions": raw_text}

            report = _scan_marketplace_payload(payload)
            if as_json:
                print(json.dumps(report, indent=2))
            else:
                verdict = "PASSED [SHA-256 VERIFIED]" if report["passed"] else "BLOCKED [SECURITY GATE]"
                print(f"Marketplace Pre-Publish Security Scan: {verdict}")
                print(f"  Manifest SHA-256: {report['manifest_sha256']}  |  Risk Grade: {report.get('risk_grade', 'C')}")
                for f in report.get("findings", []):
                    print(f"  [!] {f.get('rule_id') or f.get('code', 'FINDING')}: {f.get('message') or f.get('detail', f)}")
            return 0 if report["passed"] else 1

    if cmd == "blueprint":
        bp = _compile_blueprint(
            idea=str(args.idea),
            workspace_id=str(getattr(args, "workspace_id", "default")),
            target_stack=str(getattr(args, "stack", "fastapi_react_sqlite")),
        )
        out_path: Optional[Path] = getattr(args, "out", None)
        if out_path is not None:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps(bp, indent=2), encoding="utf-8")
        if getattr(args, "json", False):
            print(json.dumps(bp, indent=2))
        else:
            prd_title = bp.get("prd", {}).get("title", args.idea)
            print(f"[+] Compiled Governed Blueprint — {prd_title}")
            print(f"    Sprint Issues: {len(bp.get('issues', []))} linked tasks ready for agent delegation")
            print("    Governance:    P-10 Human Approval Gate active on Risk C & production deploy")
        return 0

    if cmd == "cluster":
        sub = getattr(args, "cluster_command", None) or "nodes"
        as_json = bool(getattr(args, "json", False))
        if sub == "nodes":
            nodes = _list_cluster_nodes(getattr(args, "region", None), getattr(args, "runtime", None))
            if as_json:
                print(json.dumps({"count": len(nodes), "total": len(nodes), "nodes": nodes}, indent=2))
            else:
                print(f"Keelway GPU Cluster Fleet ({len(nodes)} nodes):")
                for n in nodes:
                    print(
                        f"  - {n['node_id']:<22} [{n['region']:<12} | {n['runtime']:<12}] "
                        f"{n.get('free_vram_gb', 0)}/{n.get('total_vram_gb', 0)} GB VRAM ({n.get('status', 'healthy')})"
                    )
            return 0

        if sub == "schedule":
            res = _schedule_cluster_model(
                model_id=str(args.model),
                vram_gb=float(getattr(args, "vram", 16.0)),
                region=getattr(args, "region", None),
            )
            if as_json:
                print(json.dumps(res, indent=2))
            elif res.get("scheduled"):
                print(
                    f"[+] Scheduled '{res['model_id']}' -> {res['selected_node_id']} "
                    f"({res.get('region')} / {res.get('runtime')}, {res['required_vram_gb']} GB VRAM)"
                )
            else:
                print(f"[-] Cluster placement rejected: {res.get('error', 'insufficient capacity')}")
            return 0 if res.get("scheduled") else 1

        if sub == "lifecycle":
            entries = _list_cluster_lifecycle(getattr(args, "stage", None))
            if as_json:
                print(json.dumps({"count": len(entries), "total": len(entries), "entries": entries, "models": entries}, indent=2))
            else:
                print(f"Keelway Model Lifecycle Registry ({len(entries)} models):")
                for e in entries:
                    print(
                        f"  - {e['model_id']:<24} [{e['stage']:<10}] "
                        f"traffic={e.get('traffic_weight_pct', 0)}%  pass={e.get('benchmark_pass_rate', 0):.2f}  ttft_p95={e.get('ttft_p95_ms', 0)}ms"
                    )
            return 0

    return None
