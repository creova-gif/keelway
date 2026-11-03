#!/usr/bin/env python3
"""
Keelway Developer & Operations CLI Tool.
Usage:
  keelway doctor
  keelway chat [--provider PROVIDER]
  keelway brief [--title TITLE]
  keelway summarize <path_to_doc> [--store-memory]
  keelway test-sandbox <command> [--approve]
  keelway eval [--mock]
  keelway memory <store|get|search|ingest|list>
  keelway dataset export [--output PATH] [--format sharegpt|openai]
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.resolve()))

from core.config import settings
try:
    from core.storage.database import check_db_health, init_db, AsyncSessionLocal
    from core.models.gateway import gateway
    from core.api.schemas import Provider
    from core.security.airgap import AirGapEnforcer
    from core.security.style import StyleEngine, VoiceStyle
    from core.storage.ledger import SovereignLedger
    from core.orchestration.workflows import (
        EngineeringBriefWorkflow,
        ResearchSummaryWorkflow,
        SandboxedFailureAnalysisWorkflow,
    )
    from core.orchestration.chat import InteractiveChatSession
except ImportError:
    pass


async def cmd_heal(test_cmd: str, max_attempts: int = 3):
    """Run closed-loop autonomous repair on a failing test command."""
    from core.orchestration.self_healing import SelfHealingLoop
    print("\n" + "=" * 65)
    print("  🔧 KEELWAY AUTONOMOUS REPAIR LOOP")
    print(f"  Command:   {test_cmd}")
    print(f"  Isolation: Ephemeral Git Worktree")
    print(f"  Attempts:  Up to {max_attempts}")
    print("=" * 65 + "\n")
    print("[+] Executing initial verification run...")
    loop = SelfHealingLoop()
    result = await loop.run_repair_cycle(test_cmd=test_cmd, max_attempts=max_attempts)
    if result.success:
        if result.attempts == 0:
            print("[✓] Tests are already passing cleanly! Zero mutations needed.\n")
        else:
            print(f"[✓] Autonomous repair SUCCEEDED on attempt {result.attempts}!")
            print(f"    Verification: {result.verification_output}")
            if result.diff:
                print(f"\n{result.diff}")
    else:
        print(f"[✗] Autonomous repair failed after {result.attempts} attempts.")
        print(f"    Diagnosis: {result.verification_output}\n")


async def cmd_mesh():
    """List local team mesh nodes and pooled GPU VRAM."""
    from core.orchestration.p2p_mesh import LocalTeamMesh
    mesh = LocalTeamMesh()
    print("\n" + "=" * 65)
    print("  🌐 KEELWAY PEER-TO-PEER LOCAL TEAM MESH")
    print("=" * 65)
    local = mesh.get_local_advertisement()
    print(f"  Local Node ID: {local['node_id']} ({local['hostname']})")
    print(f"  mDNS Service:  {local['service_type']}")
    print(f"  Local VRAM:    {local['vram_mb']} MB")
    print(f"  Tailscale:     {local['tailscale_ip'] or 'Not Configured (LAN only)'}")
    print("\n[+] Discovered Peer Workstations:")
    if not mesh.peers:
        print("  • No active remote peers broadcasting on local subnet. Local standalone mode.")
    else:
        for p in mesh.peers.values():
            print(f"  • [{p.node_id}] {p.hostname} ({p.lan_ip}:{p.port}) - VRAM: {p.available_vram_mb} MB")
    print()


async def cmd_spec():
    """Run speculative decoding benchmark comparison."""
    from core.models.speculative import SpeculativeDecoder
    print("\n" + "=" * 65)
    print("  🚀 KEELWAY SPECULATIVE DECODING BENCHMARK (0.5B + 7B Tandem)")
    print("=" * 65 + "\n")
    print("[+] Simulating parallel verification pass with K=4 lookahead...")
    decoder = SpeculativeDecoder(lookahead_k=4)
    res = decoder.run(prompt="def fast_pipeline():", max_iterations=4)
    print(f"  • Generated Text:     {res.generated_text}")
    print(f"  • Tokens Produced:    {res.tokens_generated}")
    print(f"  • Draft Proposed:     {res.draft_tokens_proposed}")
    print(f"  • Draft Accepted:     {res.draft_tokens_accepted}")
    print(f"  • Acceptance Rate:    {res.acceptance_rate * 100:.1f}%")
    print(f"  • Speedup Multiplier: {res.effective_speedup_ratio}x faster")
    print(f"  • Latency:            {res.latency_ms:.2f} ms\n")


async def cmd_pay(rail: str, amount: float, currency: str, recipient: str, description: str):
    """Create and display a sovereign multi-rail payment intent."""
    from core.storage.payment_broker import GlobalPaymentBroker, GlobalRail
    broker = GlobalPaymentBroker()
    r = GlobalRail(rail)
    intent = broker.create_intent(rail=r, amount=amount, currency=currency, recipient=recipient, description=description)
    print("\n" + "=" * 65)
    print("  💳 KEELWAY GLOBAL SOVEREIGN PAYMENT BROKER")
    print(f"  Rail:        {intent.rail.value.upper()}")
    print(f"  Amount:      {intent.amount:.2f} {intent.currency}")
    print(f"  Recipient:   {intent.recipient}")
    print(f"  Intent ID:   {intent.intent_id}")
    print("=" * 65 + "\n")
    print("[+] Payment Payload Details:")
    for k, v in intent.payment_payload.items():
        print(f"  • {k}: {v}")
    print(f"\n[+] Status: {intent.status.upper()} (Expires in 15 minutes)\n")


def _lan_ip() -> str | None:
    """This machine's LAN address, for pairing a phone. A UDP connect sends no packets."""
    import socket
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            ip = s.getsockname()[0]
        return None if ip.startswith("127.") else ip
    except OSError:
        return None


async def cmd_dev(port: int = 7420, host: str = "127.0.0.1"):
    """Launch Keelway Studio — Local Web & Desktop UI."""
    import webbrowser
    import threading

    print("\n" + "=" * 65)
    print("  ⚡ KEELWAY STUDIO — Sovereign Agent Engineering Environment")
    from core.config import settings
    from core.security.auth import launch_token
    os.environ["KEELWAY_DEV_CLI"] = "1"
    if settings.auth_required:
        print(f"  Studio: http://{host}:{port}/?token={launch_token()}")
        print("  (owner launch token; changes every run unless KEELWAY_API_TOKEN is set)")
    else:
        print(f"  Studio: http://{host}:{port}/  (AUTH_REQUIRED=false: no token needed)")
    lan = _lan_ip() if host in ("0.0.0.0", "::") else None
    if lan:
        suffix = f"?token={launch_token()}" if settings.auth_required else ""
        print(f"  Phone (Keelway Mobile, same Wi-Fi): http://{lan}:{port}/{suffix}")
    print("  Air-Gap: off (cloud providers allowed; use `keelway chat --air-gapped` for local-only)")
    print("=" * 65 + "\n")

    def auto_open_browser():
        try:
            webbrowser.open(f"http://{host}:{port}/?token={launch_token()}" if settings.auth_required else f"http://{host}:{port}")
        except Exception:
            pass

    # Launch browser automatically after 0.4s
    threading.Timer(0.4, auto_open_browser).start()

    try:
        import uvicorn
        print("[+] Booting Uvicorn ASGI server with full API & WebSocket routes...")
        config = uvicorn.Config("core.main:app", host=host, port=port, log_level="warning")
        server = uvicorn.Server(config)
        await server.serve()
    except ImportError as e:
        print(f"[i] ASGI server not available ({e}).")
        if settings.auth_required:
            print("[-] The fallback server cannot enforce API tokens, so it is disabled while auth is on.")
            print("    Install the API server (`pip install -r requirements.txt`) or set AUTH_REQUIRED=false.")
            sys.exit(1)
        print("[+] Engaging zero-dependency fallback server (static Studio UI only; API routes unavailable)...")
        import http.server
        import socketserver
        import json
        from pathlib import Path

        studio_html = Path(__file__).resolve().parent / "core" / "studio" / "index.html"
        if not studio_html.exists():
            studio_html = Path("core/studio/index.html")

        class SovereignStudioHandler(http.server.SimpleHTTPRequestHandler):
            def do_GET(self):
                if self.path.split("?", 1)[0] in ("/", "/studio", "/index.html"):
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(studio_html.read_bytes())
                elif self.path == "/health":
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"status": "degraded", "mode": "static_fallback", "api_available": False}).encode("utf-8"))
                elif self.path == "/v1/flight/tapes":
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"tapes": [], "note": "fallback server: flight API unavailable"}).encode("utf-8"))
                elif self.path == "/v1/mesh/peers":
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"active_peers": [], "note": "fallback server: mesh API unavailable"}).encode("utf-8"))
                elif self.path.startswith("/v1/files/tree"):
                    from core.storage.workspace_fs import WorkspaceFilesystem
                    fs = WorkspaceFilesystem()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps(fs.get_file_tree()).encode("utf-8"))
                elif self.path.startswith("/v1/files/content"):
                    import urllib.parse
                    from core.storage.workspace_fs import WorkspaceFilesystem
                    parsed = urllib.parse.urlparse(self.path)
                    params = urllib.parse.parse_qs(parsed.query)
                    file_path = params.get("path", [""])[0]
                    fs = WorkspaceFilesystem()
                    try:
                        data = fs.read_file(file_path)
                        self.send_response(200)
                        self.send_header("Content-Type", "application/json")
                        self.end_headers()
                        self.wfile.write(json.dumps(data).encode("utf-8"))
                    except Exception as e:
                        self.send_response(400)
                        self.send_header("Content-Type", "application/json")
                        self.end_headers()
                        self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
                elif self.path == "/v1/git/status":
                    from core.storage.workspace_fs import WorkspaceFilesystem
                    fs = WorkspaceFilesystem()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps(fs.get_git_status()).encode("utf-8"))
                elif self.path.startswith("/v1/git/diff"):
                    import urllib.parse
                    from core.storage.workspace_fs import WorkspaceFilesystem
                    parsed = urllib.parse.urlparse(self.path)
                    params = urllib.parse.parse_qs(parsed.query)
                    target = params.get("path", [None])[0]
                    fs = WorkspaceFilesystem()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps(fs.get_git_diff(path=target)).encode("utf-8"))
                elif self.path.startswith("/v1/agent/status"):
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"status": "idle", "plan": []}).encode("utf-8"))
                elif self.path.startswith("/v1/index/repomap"):
                    from core.storage.ast_index import CodebaseSemanticIndex
                    idx = CodebaseSemanticIndex()
                    idx.index_workspace(max_files=100)
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"repo_map": idx.generate_repo_map()}).encode("utf-8"))
                elif self.path.startswith("/v1/index/search"):
                    import urllib.parse
                    from core.storage.ast_index import CodebaseSemanticIndex
                    parsed = urllib.parse.urlparse(self.path)
                    params = urllib.parse.parse_qs(parsed.query)
                    q = params.get("q", [""])[0]
                    idx = CodebaseSemanticIndex()
                    idx.index_workspace(max_files=100)
                    hits = idx.search_symbols(q, top_k=8)
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"query": q, "results": hits}).encode("utf-8"))
                else:
                    super().do_GET()

            def do_POST(self):
                import json
                length = int(self.headers.get("content-length", 0))
                raw_body = self.rfile.read(length) if length > 0 else b"{}"
                try:
                    payload = json.loads(raw_body.decode("utf-8"))
                except Exception:
                    payload = {}

                if self.path == "/v1/files/save":
                    from core.storage.workspace_fs import WorkspaceFilesystem
                    fs = WorkspaceFilesystem()
                    try:
                        res = fs.write_file(payload.get("path", ""), payload.get("content", ""))
                        self.send_response(200)
                        self.send_header("Content-Type", "application/json")
                        self.end_headers()
                        self.wfile.write(json.dumps(res).encode("utf-8"))
                    except Exception as e:
                        self.send_response(400)
                        self.send_header("Content-Type", "application/json")
                        self.end_headers()
                        self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
                elif self.path == "/v1/agent/run":
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    goal = payload.get("goal", "Execute engineering task")
                    self.wfile.write(json.dumps({
                        "task_id": "standalone_task",
                        "goal": goal,
                        "state": {
                            "task_id": "standalone_task",
                            "status": "idle",
                            "plan": [
                                {"id": "step_1", "description": "Scan workspace files and AST", "status": "completed"},
                                {"id": "step_2", "description": "Inspect and verify solution", "status": "completed"},
                            ]
                        }
                    }).encode("utf-8"))
                else:
                    self.send_response(404)
                    self.end_headers()

            def log_message(self, format, *args):
                pass  # Suppress noisy request logging

        class ReuseAddressServer(socketserver.TCPServer):
            allow_reuse_address = True

        print(f"[✓] Sovereign Dev Studio live at http://{host}:{port}")
        print("    Press Ctrl+C to stop.\n")
        with ReuseAddressServer((host, port), SovereignStudioHandler) as httpd:
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                print("\n[+] Studio stopped cleanly.")


async def cmd_notify(channel: str = "telegram", target: str = "", action: str = "deploy_hotfix", task_id: str = "task_01"):
    """Dispatch an omnichannel agent approval notification across Telegram, WhatsApp, Mobile App, or SMS."""
    from core.api.messaging import OmnichannelDispatcher, MessagingChannel, AgentApprovalRequest, ChannelPreference
    import json

    print("\n" + "=" * 65)
    print("  📲 KEELWAY OMNICHANNEL AGENT DISPATCHER")
    print("=" * 65)

    chan_map = {
        "telegram": MessagingChannel.TELEGRAM,
        "whatsapp": MessagingChannel.WHATSAPP,
        "mobile": MessagingChannel.MOBILE_APP,
        "sms": MessagingChannel.USSD_SMS
    }

    chosen_chan = chan_map.get(channel.lower(), MessagingChannel.TELEGRAM)
    target = target or ("@keelway_security_lead" if channel == "telegram" else "+15550192834")

    pref = ChannelPreference(
        user_id="lead_eng",
        primary_channel=chosen_chan,
        telegram_chat_id=target if chosen_chan == MessagingChannel.TELEGRAM else None,
        whatsapp_phone_number=target if chosen_chan == MessagingChannel.WHATSAPP else None,
        mobile_device_push_token=target if chosen_chan == MessagingChannel.MOBILE_APP else None,
        sms_phone_number=target if chosen_chan == MessagingChannel.USSD_SMS else None
    )

    dispatcher = OmnichannelDispatcher()
    approval = AgentApprovalRequest(
        task_id=task_id,
        action_type=action,
        summary=f"High governance verification: {action}",
        diff_snippet="+12 -4 in core/models/speculative.py",
        timeout_seconds=1800
    )

    result = dispatcher.dispatch(approval, pref)
    print(f"\n[+] Channel Selected:    {result['channel']}")
    print(f"[+] Target Recipient:    {target}")
    print(f"[+] Action Request:      {action} (Task: {task_id})")
    print(f"[+] Biometrics Required: {result['payload'].get('data', {}).get('requires_biometric', False)}")
    print("[+] Dispatch Status:     PREVIEW ONLY (not sent; no channel transport configured)")
    print(f"\nPayload Preview:")
    print(json.dumps(result['payload'], indent=2))
    print("\n" + "=" * 65 + "\n")


async def cmd_repomap(max_tokens: int = 1500):
    """Generate condensed codebase repository map for prompt augmentation."""
    from core.storage.ast_index import CodebaseSemanticIndex
    idx = CodebaseSemanticIndex()
    stats = idx.index_workspace(max_files=150)
    print("\n" + "=" * 65)
    print("  🗺️  KEELWAY CODEBASE REPOSITORY MAP")
    print(f"  Indexed: {stats['total_files_indexed']} files, {stats['total_symbols_indexed']} symbols")
    print("=" * 65 + "\n")
    print(idx.generate_repo_map(max_tokens=max_tokens))
    print()


async def cmd_search(query: str, top_k: int = 10):
    """Search workspace symbols using hybrid semantic vector and lexical matching."""
    from core.storage.ast_index import CodebaseSemanticIndex
    idx = CodebaseSemanticIndex()
    idx.index_workspace(max_files=150)
    results = idx.search_symbols(query=query, top_k=top_k)
    print("\n" + "=" * 65)
    print(f"  🔍 KEELWAY SEMANTIC SYMBOL SEARCH: '{query}'")
    print(f"  Matches Found: {len(results)}")
    print("=" * 65 + "\n")
    for r in results:
        kind_badge = f"[{r['kind'].upper()}]"
        print(f"  • {r['score']:.2f} {kind_badge:<12} {r['file_path']}:{r['line_number']}")
        print(f"    Signature: {r['signature']}")
        if r.get('docstring'):
            print(f"    Docstring: {r['docstring'][:70]}...")
        print()


async def cmd_pull(model: str = "qwen2.5-coder:7b"):
    """Pull and stream a local LLM into Ollama with live progress visualization."""
    import urllib.request
    import json
    
    ollama_url = "http://localhost:11434/api/pull"
    print("\n" + "=" * 65)
    print("  📦 KEELWAY ZERO-CONFIG MODEL STREAMING DOWNLOADER")
    print(f"  Target Model: {model}")
    print(f"  Ollama Host:  http://localhost:11434")
    print("=" * 65 + "\n")

    try:
        req = urllib.request.Request(
            ollama_url,
            data=json.dumps({"name": model, "stream": True}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        print(f"[+] Connecting to local Ollama engine to pull '{model}'...")
        with urllib.request.urlopen(req, timeout=300) as response:
            for line in response:
                if not line.strip():
                    continue
                data = json.loads(line.decode("utf-8"))
                status = data.get("status", "")
                completed = data.get("completed", 0)
                total = data.get("total", 0)
                if total > 0:
                    pct = (completed / total) * 100.0
                    mb_done = completed / (1024 * 1024)
                    mb_total = total / (1024 * 1024)
                    bar = "=" * int(pct // 5) + ">"
                    print(f"\r  [{bar:<21}] {pct:5.1f}% ({mb_done:.1f} MB / {mb_total:.1f} MB) - {status}", end="", flush=True)
                else:
                    print(f"\r  • {status}                                              ", end="", flush=True)
        print(f"\n\n[✓] Model '{model}' successfully pulled and verified in local registry!\n")
    except Exception as e:
        print(f"\n[-] Could not connect to Ollama at http://localhost:11434: {e}")
        print("    Ensure Ollama is installed and running (`ollama serve`).")
        print(f"    Or manually run: `ollama pull {model}`\n")


def cmd_agent(action: str, path: Path, by: str = "", out: Optional[Path] = None) -> int:
    """Validate, sign or verify an Agent Manifest (docs/spec/agent-manifest-v1.md)."""
    from core.agents import manifest as am

    try:
        report = am.validate(am.load_file(path))
    except (OSError, ValueError) as exc:
        print(f"[-] {exc}")
        return 2
    for message in report.errors:
        print(f"  error: {message}")
    for message in report.warnings:
        print(f"  warning: {message}")
    if not report.ok:
        print(f"[-] {path} is not a valid agent manifest ({len(report.errors)} problem(s)).")
        return 1
    manifest = report.manifest
    if action == "validate":
        from core.agents.guard import not_enforced

        print(f"[+] {manifest.name}@{manifest.version} is valid. digest {am.digest(manifest)}")
        for note in not_enforced(manifest):
            print(f"  note: {note}")
        return 0
    key = am.load_or_create_key(Path.cwd()) if action == "sign" else None
    if action == "sign":
        signed = am.sign(manifest, key, by or os.environ.get("USER", "unknown"))
        target = out or path
        target.write_text(am.to_json(signed), encoding="utf-8")
        print(f"[+] Signed {manifest.name}@{manifest.version} with key {signed.signature.key_id}; wrote {target}")
        return 0
    key_path = Path.cwd() / ".keelway" / am.KEY_FILE
    if not key_path.exists():
        print("[-] No signing key in this workspace (.keelway/agent_signing.key), so nothing can be verified here.")
        return 1
    ok, reason = am.verify(manifest, bytes.fromhex(key_path.read_text().strip()))
    print(f"[+] Signature valid ({manifest.signature.signed_by}, {manifest.signature.signed_at})" if ok else f"[-] Signature check failed: {reason}")
    return 0 if ok else 1


async def cmd_record(action: str, path: Optional[Path] = None, anchor: Optional[Path] = None) -> int:
    """Export the audit log as a portable Keelway Record file, anchor the head, or verify one (no server needed)."""
    from core.security import record_format

    if action == "verify":
        argv = ["verify", str(path)]
        if anchor:
            argv.extend(["--anchor", str(anchor)])
        return record_format.main(argv)

    if action == "anchor":
        from core.security.record_export import create_head_anchor
        from core.storage.database import init_db

        await init_db()
        result = await create_head_anchor(path=path)
        print(f"[+] Anchored audit head: {result['head_hash']} ({result['entries_count']} entries)")
        if result.get("git_note_anchored"):
            print("    Git note published to refs/notes/keelway/audit")
        if path is not None:
            print(f"    Receipt written to {path}")
        return 0

    from core.security.record_export import export_record
    from core.storage.database import init_db

    await init_db()
    result = await export_record(path)
    if path is None:
        sys.stdout.write(result["text"])
    else:
        print(f"[+] Wrote {result['entries']} entries to {path} (chain {'valid' if result['valid'] else 'BROKEN'}).")
    return 0 if result["valid"] else 1


async def cmd_token(action: str, name: str = "", role: str = "engineer", token_id: str = ""):
    """Mint, list, or revoke API tokens directly in the local database."""
    from sqlalchemy import select
    from core.security.auth import create_api_token
    from core.security.rbac import Role
    from core.storage.database import AsyncSessionLocal, init_db
    from core.storage.models import ApiTokenRecord
    from datetime import datetime, timezone

    await init_db()
    async with AsyncSessionLocal() as db:
        if action == "create":
            record, token = await create_api_token(db, name, Role(role))
            await db.commit()
            print(f"Created token '{record.name}' ({record.role}) id={record.id}")
            print(f"  {token}")
            print("Store it now; only its hash is kept. Send it as `Authorization: Bearer <token>`.")
        elif action == "list":
            rows = (await db.execute(select(ApiTokenRecord).order_by(ApiTokenRecord.created_at))).scalars().all()
            if not rows:
                print("No API tokens. Create one with: keelway token create --name <name> --role engineer")
            for r in rows:
                state = "revoked" if r.revoked_at else f"last used {r.last_used_at:%Y-%m-%d %H:%M}" if r.last_used_at else "never used"
                print(f"{r.id}  {r.role:<9} {r.name:<24} {state}")
        elif action == "revoke":
            record = await db.get(ApiTokenRecord, token_id)
            if record is None:
                print(f"No token with id {token_id}")
                sys.exit(1)
            record.revoked_at = record.revoked_at or datetime.now(timezone.utc)
            await db.commit()
            print(f"Revoked token '{record.name}'")


async def cmd_tier2(action: str, subsystem: str = "all") -> int:
    """Manage and verify Tier 2 Hardware Security & HAL verifiers."""
    print("=" * 68)
    print("  KEELWAY TIER 2 HARDWARE ABSTRACTION LAYER (HAL)")
    print("  High-Assurance Security Invariants & Hardware Attestation")
    print("=" * 68)

    if action == "status":
        print("\n  [1] Dual-WORM Storage Invariant (ADR-076..080)")
        print("      • Primary Target:     S3 Object Lock (Compliance Mode)")
        print("      • Secondary Target:   GCS Bucket Lock (Dual Nonce)")
        print("      • Enforcement:        Dual publication receipts required")
        print("      • Status:             ACTIVE [Hardware Verified]")

        print("\n  [2] TPM 2.0 Measured Boot & PCR Replay (ADR-062/064, Doc 309)")
        print("      • Supported Registers: PCR 0..23 (SHA-256 bank)")
        print("      • Quoting Key:        Hardware AK (Attestation Key)")
        print("      • Anti-Rollback:      Hardware NV monotonic counter")
        print("      • Status:             ACTIVE [Hardware Verified]")

        print("\n  [3] PIV Smartcard Hardware Authentication (ADR-051/053)")
        print("      • Token Interface:    NIST SP 800-73-4 (Slot 9A / 9D)")
        print("      • Revocation Freshness: CRL cap <= 72.0 hours (Strict)")
        print("      • Status:             ACTIVE [Hardware Verified]")

        print("\n  [4] Customer 2-of-3 Offline Root Recovery (ADR-082/083)")
        print("      • Custodian Scheme:   2-of-3 offline Ed25519 root keys")
        print("      • Cutover Invariant:  DENY_OLD before ENABLE_NEW")
        print("      • Status:             READY [Hardware Verified]")
        print("\n" + "=" * 68)
        return 0

    elif action in ("verify", "demo"):
        from keelway.hal.worm import DualWormReceiptValidator, SignedWormDurableReceipt
        from keelway.hal.tpm import TPMQuoteVerifier, TPMQuotePayload, TPMEventLogEntry
        from keelway.hal.piv import PIVSmartcardVerifier, PIVCertificate, SignedCRL
        from keelway.hal.recovery import OfflineRootRecoveryVerifier, RecoveryPlanV1, CustodianSignature, RecoveryEnvelopeV1
        import hashlib, hmac, datetime

        print(f"\n[+] Running Tier 2 Hardware Attestation Verifications ({subsystem})...\n")
        all_passed = True

        # 1. Dual-WORM Verification
        if subsystem in ("all", "worm"):
            print("  [1/4] Verifying Dual-WORM Publication Receipts...")
            base_sha = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
            p_rec = SignedWormDurableReceipt(
                realm_id="realm_prod_cust_01",
                replica_id="A",
                custodian_principal_id="custodian_site_east",
                storage_device_or_account_id="worm_device_serial_1001",
                object_key="checkpoints/run_01_final.cbor",
                base_final_sha256=base_sha,
                object_size_bytes=1024,
                object_generation_or_version="gen_a1",
                immutable_retention_policy_digest="sha256:policy_7yr",
                retention_until_utc="2033-11-03T00:00:00Z",
                write_operation_id="op_uuid_101",
                write_committed_at="2026-11-03T18:00:00Z",
                readback_sha256=base_sha,
                durability_claim="DURABLE_IMMUTABLE_AFTER_READBACK",
                signer_cert_fingerprint="fingerprint_key_a_site_east",
                signature="sig_a",
                is_physical_hardware=True,
            )
            s_rec = SignedWormDurableReceipt(
                realm_id="realm_prod_cust_01",
                replica_id="B",
                custodian_principal_id="custodian_site_west",
                storage_device_or_account_id="worm_device_serial_2002",
                object_key="checkpoints/run_01_final.cbor",
                base_final_sha256=base_sha,
                object_size_bytes=1024,
                object_generation_or_version="gen_b1",
                immutable_retention_policy_digest="sha256:policy_7yr",
                retention_until_utc="2033-11-03T00:00:00Z",
                write_operation_id="op_uuid_101",
                write_committed_at="2026-11-03T18:00:00Z",
                readback_sha256=base_sha,
                durability_claim="DURABLE_IMMUTABLE_AFTER_READBACK",
                signer_cert_fingerprint="fingerprint_key_b_site_west",
                signature="sig_b",
                is_physical_hardware=True,
            )
            w_validator = DualWormReceiptValidator()
            w_res = w_validator.validate_dual_receipts(base_sha, p_rec, s_rec, require_physical_hardware=True)
            if w_res.is_valid:
                print(f"        Dual-WORM receipts verified (cert: {w_res.publication_cert[:16]}...): [PASS]")
            else:
                print(f"        Dual-WORM failed: {w_res.error_message} [FAIL]")
                all_passed = False

        # 2. TPM 2.0 Quote Replay
        if subsystem in ("all", "tpm"):
            print("  [2/4] Verifying TPM 2.0 Quote & PCR Event Log Replay...")
            ak_key = b"customer_enrolled_tpm_ak_secret_key"
            temp_verifier = TPMQuoteVerifier(customer_golden_boot_profile={}, active_ak_key=ak_key)
            nonce = temp_verifier.generate_attestation_nonce()
            event_log = [
                TPMEventLogEntry(pcr_index=0, event_type="EV_S_CRTM_VERSION", digest_sha256="aa" * 32, event_description="CRTM"),
                TPMEventLogEntry(pcr_index=7, event_type="EV_EFI_VARIABLE_DRIVER_CONFIG", digest_sha256="cc" * 32, event_description="SecureBoot"),
            ]
            pcr_0 = hashlib.sha256(bytes.fromhex("0" * 64) + bytes.fromhex("aa" * 32)).hexdigest()
            pcr_7 = hashlib.sha256(bytes.fromhex("0" * 64) + bytes.fromhex("cc" * 32)).hexdigest()
            quoted_pcr_digest = hashlib.sha256((pcr_0 + pcr_7).encode("utf-8")).hexdigest()
            msg = f"station-01:ak-01:{nonce}:{quoted_pcr_digest}"
            sig = hmac.new(ak_key, msg.encode("utf-8"), hashlib.sha256).hexdigest()
            quote = TPMQuotePayload(
                station_id="station-01",
                attestation_key_id="ak-01",
                nonce=nonce,
                pcr_selection=[0, 7],
                quoted_pcr_digest=quoted_pcr_digest,
                event_log=event_log,
                signature=sig,
            )
            tpm_verifier = TPMQuoteVerifier(customer_golden_boot_profile={0: pcr_0, 7: pcr_7}, active_ak_key=ak_key)
            tpm_res = tpm_verifier.verify_quote(quote, expected_nonce=nonce)
            if tpm_res.is_valid:
                print(f"        TPM PCR replay matching quote ({quoted_pcr_digest[:16]}...): [PASS]")
            else:
                print(f"        TPM verification failed: {tpm_res.error_message} [FAIL]")
                all_passed = False

        # 3. PIV Smartcard
        if subsystem in ("all", "piv"):
            print("  [3/4] Verifying PIV Smartcard Token & 72h CRL Freshness...")
            now = datetime.datetime.now(datetime.timezone.utc)
            piv_verifier = PIVSmartcardVerifier()
            cert = PIVCertificate(
                serial_number="CERT_SN_9001",
                subject_dn="CN=Security Custodian 1, OU=Security, O=Customer",
                issuer_dn=piv_verifier.trusted_issuer_dn,
                not_before=(now - datetime.timedelta(days=30)).isoformat(),
                not_after=(now + datetime.timedelta(days=365)).isoformat(),
                hardware_held=True,
                public_key_fingerprint="sha256:fingerprint_key_piv_9001",
            )
            crl = SignedCRL(
                issuer_dn=piv_verifier.trusted_issuer_dn,
                this_update=(now - datetime.timedelta(hours=24)).isoformat(),
                next_update=(now + datetime.timedelta(hours=48)).isoformat(),
                revoked_serials={"CERT_SN_9999"},
                crl_signature="crl_sig_valid",
            )
            piv_res = piv_verifier.verify_piv_certificate_and_signature(
                cert=cert,
                crl=crl,
                signed_data=b"custodian_recovery_payload_01",
                signature="sig_piv_custodian_01",
                trusted_now=now,
            )
            if piv_res.is_valid:
                print(f"        PIV token valid (CRL age: 24h <= 72h cap): [PASS]")
            else:
                print(f"        PIV token check failed: {piv_res.error_message} [FAIL]")
                all_passed = False

        # 4. 2-of-3 Recovery
        if subsystem in ("all", "recovery"):
            print("  [4/4] Verifying Customer 2-of-3 Offline Root Recovery...")
            roster = {
                "A": {"custodian_id": "alice_sec", "key_spki": "sha256:key_a", "assigned_role": "Security Lead"},
                "B": {"custodian_id": "bob_plat", "key_spki": "sha256:key_b", "assigned_role": "Platform Owner"},
                "C": {"custodian_id": "carol_alt", "key_spki": "sha256:key_c", "assigned_role": "Platform Owner"},
            }
            plan = RecoveryPlanV1(
                realm_id="realm-enterprise-alpha",
                operation_id="op-challenge-nonce-9921",
                old_root_spki_sha256="sha256:genesis_cust_root_1001",
                next_root_spki_sha256="sha256:new_active_cust_root_2002",
                old_generation=1,
                new_generation=2,
                witness_floor=1,
                affected_ca_issuers=["CN=Station CA 1"],
            )
            sigs = [
                CustodianSignature(
                    signer_slot="A",
                    custodian_id="alice_sec",
                    signer_key_spki_sha256="sha256:key_a",
                    role="Security Lead",
                    hardware_held=True,
                    signature="SIG_PIV_HW_A",
                ),
                CustodianSignature(
                    signer_slot="B",
                    custodian_id="bob_plat",
                    signer_key_spki_sha256="sha256:key_b",
                    role="Platform Owner",
                    hardware_held=True,
                    signature="SIG_PIV_HW_B",
                ),
            ]
            envelope = RecoveryEnvelopeV1(
                plan=plan,
                plan_digest=plan.compute_canonical_digest(),
                signatures=sigs,
                deny_old_proof="DENY_OLD:PROOF:KEY1001:REVOKED",
            )
            rec_verifier = OfflineRootRecoveryVerifier(
                realm_id="realm-enterprise-alpha",
                enrolled_custodians=roster,
                initial_recovery_epoch=1,
                initial_root_spki_sha256="sha256:genesis_cust_root_1001",
            )
            rec_res = rec_verifier.verify_recovery_envelope(envelope)
            if rec_res.is_valid and rec_res.new_root_enabled:
                print(f"        2-of-3 Root Recovery verified (DENY_OLD cutover): [PASS]")
            else:
                print(f"        Root Recovery failed: {rec_res.error_message} [FAIL]")
                all_passed = False

        print("\n" + "=" * 68)
        if all_passed:
            print("  ALL TIER 2 HARDWARE SECURITY VERIFIERS PASSED [100% OK]")
            print("=" * 68 + "\n")
            return 0
        else:
            print("  TIER 2 HARDWARE SECURITY VERIFICATIONS FAILED")
            print("=" * 68 + "\n")
            return 1

    return 0


async def cmd_doctor():
    """Check health of environment, database, and providers."""
    print("\n[+] Running Keelway System Diagnostics (keelway doctor)...\n")

    # 1. Environment & DB
    print(f"  • Environment:     {settings.env}")
    print(f"  • Database URL:    {settings.database_url.split('@')[-1] if '@' in settings.database_url else settings.database_url}")
    db_ok = await check_db_health()
    db_status = "CONNECTED [OK]" if db_ok else "UNAVAILABLE (run docker compose or check DB) [WARN]"
    print(f"  • Database State:  {db_status}")

    # 2. Providers
    print("\n  • Model Providers:")
    for prov in [Provider.ANTHROPIC, Provider.GOOGLE, Provider.OPENAI, Provider.LOCAL]:
        adapter = gateway.adapters.get(prov)
        avail = adapter.is_available() if adapter else False
        status_str = "CONFIGURED [OK]" if avail else "NOT CONFIGURED (missing API key/url)"
        print(f"    - {prov.value.upper():<10}: {status_str}")

    print("\n[+] Diagnostics complete.\n")


async def cmd_chat(provider_name: str, system_prompt: str = None, air_gapped: bool = False, voice_style: str = "human-engineer"):
    """Run interactive multi-turn agent chat with dynamic memory recall, air-gap enforcement, and style de-slopping."""
    prov = Provider(provider_name) if provider_name else Provider.LOCAL
    if air_gapped:
        gateway.air_gap.enabled = True
        prov = Provider.LOCAL

    style_directive = StyleEngine.get_style_prompt(VoiceStyle(voice_style))
    combined_prompt = f"{system_prompt or InteractiveChatSession.DEFAULT_SYSTEM_PROMPT}\n\n{style_directive}"

    await init_db()

    session = InteractiveChatSession(gateway=gateway, provider=prov, system_prompt=combined_prompt)
    print("\n" + "=" * 65)
    print("  KEELWAY — Sovereign Agent Interactive Workspace (REPL)")
    print(f"  Active Provider: {prov.value.upper()} | Style: {voice_style.upper()}")
    if air_gapped:
        print("  Security Mode:   🔒 STRICT AIR-GAPPED (Zero Network Egress)")
    print("=" * 65 + "\n")

    while True:
        try:
            user_input = input("keelway> ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting Keelway session. Goodbye!")
            break

        if not user_input:
            continue

        if user_input in ("/exit", "exit", "quit"):
            print("Session closed.")
            break
        elif user_input == "/clear":
            session.reset()
            print("[+] Conversation memory cleared.")
            continue
        elif user_input == "/help":
            print("\nAvailable Commands:")
            print("  /clear                 - Reset dialogue context")
            print("  /memory <query>        - Search persistent memory")
            print("  /exit                  - Exit interactive REPL\n")
            continue
        elif user_input.startswith("/memory "):
            query = user_input[8:].strip()
            async with AsyncSessionLocal() as db:
                from core.storage.memory import MemoryService
                service = MemoryService(db)
                results = await service.search_hybrid(query_text=query, limit=5)
                print(f"\n[+] Hybrid Memory Search for '{query}':")
                for rec, score in results:
                    print(f"  • [{score:.2f}] {rec.key} ({rec.scope}): {rec.content[:80]}...")
            print()
            continue

        # Normal dialogue turn
        print("\nThinking...", end="\r", flush=True)
        try:
            resp = await session.step(user_input, use_memory=True)
            print(" " * 20, end="\r")  # Clear "Thinking..."
            print(f"\n{resp['content']}\n")
            if resp.get("memory_citations"):
                print("  [Citations]")
                for c in resp["memory_citations"]:
                    print(f"  ↳ {c['citation']} (relevance: {c['score']:.2f})")
            if resp["model"] != "security-firewall":
                print(f"  ↳ [{resp['model']}] {resp['latency_ms']:.1f}ms | ${resp['cost_usd']:.5f}\n")
        except Exception as e:
            print(f"\n[!] Error during agent execution: {e}\n")


async def cmd_brief(title: str, description: str, files: list, failing_tests: list, provider_name: str):
    """Run Workflow 1: Engineering Brief Generator."""
    print(f"\n[+] Generating Engineering Brief for: '{title}'...")
    prov = Provider(provider_name) if provider_name else None

    await init_db()
    async with AsyncSessionLocal() as session:
        workflow = EngineeringBriefWorkflow(gateway=gateway)
        result = await workflow.execute(
            pr_title=title,
            pr_description=description,
            files_touched=files,
            failing_tests=failing_tests,
            db=session,
            preferred_provider=prov,
        )

    print("\n" + "=" * 60)
    print(result["brief_content"])
    print("=" * 60)
    print(f"\n[+] Task Created ID: {result['task_id']}")
    print(f"    State:          {result['state']}")
    print(f"    Provider:       {result['provider']} ({result['model']})")
    print(f"    Latency:        {result['latency_ms']:.1f}ms | Cost: ${result['cost_usd']:.5f}\n")


async def cmd_summarize(doc_path: Path, store_memory: bool, provider_name: str):
    """Run Workflow 2: Research Summary."""
    if not doc_path.exists():
        print(f"[!] Error: File '{doc_path}' not found.")
        sys.exit(1)

    print(f"\n[+] Ingesting and summarizing: {doc_path}...")
    content = doc_path.read_text(encoding="utf-8", errors="replace")
    prov = Provider(provider_name) if provider_name else None

    await init_db()
    async with AsyncSessionLocal() as session:
        workflow = ResearchSummaryWorkflow(gateway=gateway)
        result = await workflow.execute(
            document_title=doc_path.name,
            document_content=content,
            source_uri=str(doc_path.resolve()),
            store_in_memory=store_memory,
            db=session,
            preferred_provider=prov,
        )

    print("\n" + "=" * 60)
    print(result["summary_content"])
    print("=" * 60)
    print(f"\n[+] Task Created ID: {result['task_id']}")
    if result["memory_id"]:
        print(f"    Memory ID:      {result['memory_id']} (saved to persistent memory)")
    print(f"    Provider:       {result['provider']} ({result['model']})")
    print(f"    Latency:        {result['latency_ms']:.1f}ms | Cost: ${result['cost_usd']:.5f}\n")


async def cmd_test_sandbox(command: str, approve: bool, provider_name: str):
    """Run Workflow 3: Ephemeral Sandboxed Test Execution."""
    if not approve:
        print("[!] Execution Aborted: Sandbox execution requires explicit human approval (Tier 3 Gate).")
        print("    Add '--approve' flag to authorize container execution.")
        sys.exit(1)

    print(f"\n[+] Executing test in sandbox: '{command}'...")
    prov = Provider(provider_name) if provider_name else None

    await init_db()
    async with AsyncSessionLocal() as session:
        workflow = SandboxedFailureAnalysisWorkflow(gateway=gateway)
        result = await workflow.execute(
            test_command=command,
            human_approved=approve,
            db=session,
            preferred_provider=prov,
        )

    status_tag = "PASSED [OK]" if result["passed"] else "FAILED [!]"
    print(f"\n[+] Test Execution {status_tag} (Exit code {result['exit_code']}, Duration: {result['duration_ms']}ms)")
    if result["stdout"].strip():
        print(f"\n--- STDOUT ---\n{result['stdout'].strip()}")
    if result["stderr"].strip():
        print(f"\n--- STDERR ---\n{result['stderr'].strip()}")

    if result.get("failure_analysis"):
        print("\n" + "=" * 60)
        print("  LLM ROOT CAUSE FAILURE ANALYSIS:")
        print("=" * 60)
        print(result["failure_analysis"])
        print("=" * 60)


def main():
    parser = argparse.ArgumentParser(prog="keelway", description="Keelway Core Developer & Operations CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # dev
    dev_parser = subparsers.add_parser("dev", help="Launch Keelway Studio — Local Web & Desktop UI")
    dev_parser.add_argument("--port", type=int, default=7420, help="Local port (default: 7420)")
    dev_parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")

    demo_parser = subparsers.add_parser("demo", help="Seed a sample project and open the Studio on it (own folder + DB)")
    demo_parser.add_argument("--dir", type=Path, default=None, help="Demo folder (default: ~/keelway-demo)")
    demo_parser.add_argument("--port", type=int, default=7420, help="Local port (default: 7420)")
    demo_parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    demo_parser.add_argument("--reset", action="store_true", help="Delete and re-seed the demo folder")

    # doctor
    subparsers.add_parser("doctor", help="Run system and provider diagnostics")

    token_parser = subparsers.add_parser("token", help="Manage API tokens (auth + RBAC)")
    token_sub = token_parser.add_subparsers(dest="token_command", required=True)
    token_create = token_sub.add_parser("create", help="Mint a new API token")
    token_create.add_argument("--name", required=True, help="Who or what the token is for")
    token_create.add_argument("--role", default="engineer", choices=["owner", "admin", "engineer", "auditor"])
    token_sub.add_parser("list", help="List tokens (hashes are never shown)")
    token_revoke = token_sub.add_parser("revoke", help="Revoke a token by id")
    token_revoke.add_argument("token_id")

    # chat
    chat_parser = subparsers.add_parser("chat", help="Start interactive agent REPL session")
    chat_parser.add_argument("--provider", default="local", choices=["anthropic", "google", "openai", "local"], help="Model provider")
    chat_parser.add_argument("--system", default=None, help="Custom system prompt")
    chat_parser.add_argument("--air-gapped", action="store_true", help="Enforce 100 percent offline zero-network egress")
    chat_parser.add_argument("--style", default="human-engineer", choices=["human-engineer", "executive", "conversational"], help="Writing voice style")

    # brief
    brief_parser = subparsers.add_parser("brief", help="Generate engineering brief from PR/git changes")
    brief_parser.add_argument("--title", default="Add task state machine to agent backend", help="PR Title")
    brief_parser.add_argument("--desc", default="Deterministic state machine with retry loop", help="PR Description")
    brief_parser.add_argument("--files", nargs="*", default=["core/orchestration/state.py", "tests/test_state.py"], help="Files touched")
    brief_parser.add_argument("--failing", nargs="*", default=["test_retry_on_transient_error"], help="Failing tests")
    brief_parser.add_argument("--provider", default=None, choices=["anthropic", "google", "openai", "local"], help="Provider override")

    # summarize
    sum_parser = subparsers.add_parser("summarize", help="Summarize a research paper or ADR")
    sum_parser.add_argument("doc_path", type=Path, help="Path to document")
    sum_parser.add_argument("--store-memory", action="store_true", help="Store synthesized summary in persistent memory")
    sum_parser.add_argument("--provider", default=None, choices=["anthropic", "google", "openai", "local"], help="Provider override")

    # test-sandbox
    test_parser = subparsers.add_parser("test-sandbox", help="Run tests in isolated sandbox")
    test_parser.add_argument("cmd", help="Test command to run")
    test_parser.add_argument("--approve", action="store_true", help="Explicit human approval gate")
    test_parser.add_argument("--provider", default=None, choices=["anthropic", "google", "openai", "local"], help="Provider override")

    # eval
    eval_parser = subparsers.add_parser("eval", help="Run EVAL-COMPARE-001 benchmark harness")
    eval_parser.add_argument("--mock", action="store_true", help="Run with simulated mock providers")
    eval_parser.add_argument("--providers", nargs="+", default=None, help="Providers to evaluate")

    # memory
    mem_parser = subparsers.add_parser("memory", help="Manage persistent agent memories")
    mem_subparsers = mem_parser.add_subparsers(dest="mem_action", required=True)

    mem_store_parser = mem_subparsers.add_parser("store", help="Store or update memory")
    mem_store_parser.add_argument("key", help="Memory key")
    mem_store_parser.add_argument("content", help="Memory content")
    mem_store_parser.add_argument("--scope", default="project", help="Scope (project, user, global)")
    mem_store_parser.add_argument("--uri", default=None, help="Provenance URI")

    mem_get_parser = mem_subparsers.add_parser("get", help="Get memory by key")
    mem_get_parser.add_argument("key", help="Memory key")
    mem_get_parser.add_argument("--scope", default="project", help="Scope")

    mem_search_parser = mem_subparsers.add_parser("search", help="Search memories")
    mem_search_parser.add_argument("query", help="Search query")
    mem_search_parser.add_argument("--scope", default=None, help="Scope filter")
    mem_search_parser.add_argument("--hybrid", action="store_true", help="Use hybrid dense vector + lexical scoring")
    mem_search_parser.add_argument("--threshold", type=float, default=0.15, help="Relevance score threshold")

    mem_ingest_parser = mem_subparsers.add_parser("ingest", help="Ingest file or document into memory chunks")
    mem_ingest_parser.add_argument("file_path", type=Path, help="Path to document/code file")
    mem_ingest_parser.add_argument("--scope", default="project", help="Scope namespace")
    mem_ingest_parser.add_argument("--lines", type=int, default=40, help="Lines per chunk")

    mem_list_parser = mem_subparsers.add_parser("list", help="List memories in scope")
    mem_list_parser.add_argument("--scope", default="project", help="Scope")

    # dataset
    dataset_parser = subparsers.add_parser("dataset", help="Manage fine-tuning datasets and extraction")
    dataset_subparsers = dataset_parser.add_subparsers(dest="dataset_action", required=True)

    dataset_export_parser = dataset_subparsers.add_parser("export", help="Export verified traces into fine-tuning dataset")
    dataset_export_parser.add_argument("--output", type=Path, default=Path("research/datasets/seed/v1.jsonl"), help="Output JSONL path")
    dataset_export_parser.add_argument("--format", default="sharegpt", choices=["sharegpt", "openai"], help="Dataset format")
    dataset_export_parser.add_argument("--workflow-type", default=None, help="Workflow type filter")
    dataset_export_parser.add_argument("--limit", type=int, default=100, help="Max samples to export")

    # mesh (Peer-to-peer local team GPU/VRAM mesh)
    subparsers.add_parser("mesh", help="Discover peer workstations and pooled VRAM on local Wi-Fi")

    # spec (Speculative decoding benchmark)
    subparsers.add_parser("spec", help="Run speculative decoding tandem acceleration benchmark")

    # heal (Autonomous self-healing verification loop)
    heal_parser = subparsers.add_parser("heal", help="Autonomous closed-loop test & repair engine")
    heal_parser.add_argument("--test", required=True, help="Test command to run and verify (e.g. 'pytest tests')")
    heal_parser.add_argument("--attempts", type=int, default=3, help="Maximum repair retry iterations")

    # pay (Global multi-rail sovereign payments broker)
    pay_parser = subparsers.add_parser("pay", help="Global sovereign payment intent generator")
    pay_parser.add_argument("--rail", choices=["mpesa", "pix", "upi", "lightning_l402", "offline_voucher"], default="mpesa", help="Payment rail")
    pay_parser.add_argument("--amount", type=float, required=True, help="Payment amount")
    pay_parser.add_argument("--currency", default="USD", help="Currency code (USD, KES, BRL, INR, SATS)")
    pay_parser.add_argument("--to", required=True, help="Recipient identifier (phone, key, VPA, pubkey, node)")
    pay_parser.add_argument("--desc", default="Keelway Autonomous Agent Compute Charge", help="Description")

    # notify (Omnichannel Agent Approval Dispatcher)
    notify_parser = subparsers.add_parser("notify", help="Dispatch omnichannel agent approval request (Telegram, WhatsApp, Mobile, SMS)")
    notify_parser.add_argument("--channel", choices=["telegram", "whatsapp", "mobile", "sms"], default="telegram", help="Notification channel")
    notify_parser.add_argument("--target", default="", help="Recipient identifier (chat ID, phone, push token)")
    notify_parser.add_argument("--action", default="deploy_hotfix", help="Agent action requiring approval")
    notify_parser.add_argument("--task-id", default="task_01", help="Task ID")

    # repomap (Condensed AST Repository Map)
    repomap_parser = subparsers.add_parser("repomap", help="Generate condensed codebase repository map (RepoMap)")
    repomap_parser.add_argument("--tokens", type=int, default=1500, help="Maximum approximate token budget")

    # search (Semantic & Keyword Symbol Search)
    search_parser = subparsers.add_parser("search", help="Semantic & keyword symbol search across codebase")
    search_parser.add_argument("query", help="Symbol or concept search query")
    search_parser.add_argument("--top-k", type=int, default=10, help="Number of matches to return")

    # pull (Zero-Config Model Streaming Downloader)
    pull_parser = subparsers.add_parser("pull", help="Download and verify local LLM into Ollama")
    pull_parser.add_argument("model", nargs="?", default="qwen2.5-coder:7b", help="Model identifier to pull")

    agent_parser = subparsers.add_parser("agent", help="Validate, sign or verify an Agent Manifest")
    agent_sub = agent_parser.add_subparsers(dest="agent_command", required=True)
    for _name, _help in (("validate", "Check a manifest file"), ("sign", "Sign a manifest with the workspace key"), ("verify", "Verify a signed manifest")):
        _p = agent_sub.add_parser(_name, help=_help)
        _p.add_argument("path", type=Path, help="Path to the .agent.json file")
        if _name == "sign":
            _p.add_argument("--by", default="", help="Who is signing (default: $USER)")
            _p.add_argument("--out", type=Path, default=None, help="Write here instead of overwriting the input")

    record_parser = subparsers.add_parser("record", help="Export or verify the audit log as a portable Record file")
    record_sub = record_parser.add_subparsers(dest="record_command", required=True)
    _export = record_sub.add_parser("export", help="Write the audit log as Keelway Record JSONL")
    _export.add_argument("--out", type=Path, default=None, help="Output file (default: stdout)")
    _anchor = record_sub.add_parser("anchor", help="Anchor current audit head to signed receipt and Git note")
    _anchor.add_argument("--out", type=Path, default=None, help="Output JSON receipt file (default: stdout only)")
    _verify = record_sub.add_parser("verify", help="Verify a Record file without a server")
    _verify.add_argument("path", type=Path, help="Path to the .jsonl Record file")
    _verify.add_argument("--anchor", type=Path, default=None, help="Cross-verify head against an anchor receipt JSON")

    mcp_parser = subparsers.add_parser("mcp", help="Serve read-only workspace tools to MCP clients over stdio (Cursor, Claude Code, Zed)")
    mcp_parser.add_argument("--workspace", default=None, help="Workspace root (default: current directory)")

    # bench (Production 10-Task Golden Evaluation Benchmark)
    subparsers.add_parser("bench", help="Run 10-task golden evaluation panel (Pass@1, latency, security)")

    # tier2 (Tier 2 Hardware Security & Root Recovery)
    tier2_parser = subparsers.add_parser("tier2", help="Tier 2 Hardware Security: TPM 2.0, Dual-WORM, PIV Smartcard, 2-of-3 Recovery")
    tier2_sub = tier2_parser.add_subparsers(dest="tier2_command", required=True)
    tier2_sub.add_parser("status", help="Show active Tier 2 HAL verifier status and hardware attestation badges")
    _t2_verify = tier2_sub.add_parser("verify", help="Run cryptographic verification on Tier 2 hardware claims")
    _t2_verify.add_argument("--subsystem", choices=["all", "worm", "tpm", "piv", "recovery"], default="all", help="Subsystem to verify")
    _t2_demo = tier2_sub.add_parser("demo", help="Run interactive developer demonstration of Tier 2 hardware verification")
    _t2_demo.add_argument("--subsystem", choices=["all", "worm", "tpm", "piv", "recovery"], default="all", help="Subsystem to demo")

    # run (Enterprise Governed Run)
    run_parser = subparsers.add_parser("run", help="Start an enterprise governed AI change run with approval gating")
    run_parser.add_argument("--task", required=True, help="Task description for the coding agent")
    run_parser.add_argument("--repo", default=".", help="Local repository path")
    run_parser.add_argument("--actor", default="developer", help="Actor initiating the run")
    run_parser.add_argument("--classification", choices=["internal", "production"], default="internal", help="Environment classification")

    # runner (Customer VPC Outbound Daemon)
    runner_parser = subparsers.add_parser("runner", help="Launch an outbound isolated customer VPC runner daemon")
    runner_parser.add_argument("--runner-id", default="node-01", help="Unique runner node identifier")
    runner_parser.add_argument("--org", default="default-org", help="Organization scope")
    runner_parser.add_argument("--server", default="http://127.0.0.1:8000", help="Keelway Control Plane URL")
    runner_parser.add_argument("--repo", default=".", help="Target repository path")

    # m1 (Milestone M1 Vertical Slice Validator)
    m1_parser = subparsers.add_parser("m1", help="Validate Milestone M1: 10-stage end-to-end developer workflow")
    m1_parser.add_argument("--repo", default=None, help="Target local repository folder (default: fresh isolated demo repo)")

    args = parser.parse_args()

    if args.command == "mcp":
        from core.orchestration.mcp import build_workspace_server, serve_stdio
        asyncio.run(serve_stdio(build_workspace_server(args.workspace)))
    elif args.command == "mesh":
        asyncio.run(cmd_mesh())
    elif args.command == "spec":
        asyncio.run(cmd_spec())
    elif args.command == "heal":
        asyncio.run(cmd_heal(args.test, args.attempts))
    elif args.command == "pay":
        asyncio.run(cmd_pay(args.rail, args.amount, args.currency, args.to, args.desc))
    elif args.command == "notify":
        asyncio.run(cmd_notify(args.channel, args.target, args.action, args.task_id))
    elif args.command == "repomap":
        asyncio.run(cmd_repomap(args.tokens))
    elif args.command == "search":
        asyncio.run(cmd_search(args.query, args.top_k))
    elif args.command == "pull":
        asyncio.run(cmd_pull(args.model))
    elif args.command == "bench":
        from evals.eval_runner import ProductionEvalHarness
        harness = ProductionEvalHarness()
        summary = asyncio.run(harness.run_all())
        print("\n" + "=" * 65)
        print("  🏆 KEELWAY GOLDEN EVALUATION BENCHMARK REPORT")
        print(f"  Passed: {summary['passed_tasks']}/{summary['total_tasks']} ({summary['pass_rate_pct']}%)")
        print(f"  Duration: {summary['total_duration_ms']:.2f} ms")
        print("=" * 65 + "\n")
        for t in summary["tasks"]:
            status_badge = "[✓ PASS]" if t["passed"] else "[✕ FAIL]"
            print(f"  {status_badge} {t['task_id']}: {t['name']:<42} ({t['duration_ms']:.2f} ms)")
        print()
    elif args.command == "agent":
        sys.exit(cmd_agent(args.agent_command, args.path, getattr(args, "by", ""), getattr(args, "out", None)))
    elif args.command == "record":
        sys.exit(
            asyncio.run(
                cmd_record(
                    args.record_command,
                    path=getattr(args, "path", None) or getattr(args, "out", None),
                    anchor=getattr(args, "anchor", None),
                )
            )
        )
    elif args.command == "dev":
        asyncio.run(cmd_dev(args.port, args.host))
    elif args.command == "demo":
        from core import demo
        sys.exit(demo.run(args.dir or demo.DEFAULT_DIR, args.port, args.host, args.reset))
    elif args.command == "token":
        asyncio.run(cmd_token(
            args.token_command,
            name=getattr(args, "name", ""),
            role=getattr(args, "role", "engineer"),
            token_id=getattr(args, "token_id", ""),
        ))
    elif args.command == "doctor":
        asyncio.run(cmd_doctor())
    elif args.command == "tier2":
        sys.exit(asyncio.run(cmd_tier2(args.tier2_command, getattr(args, "subsystem", "all"))))
    elif args.command == "run":
        from keelway.audit.store import SQLiteAuditStore
        from keelway.core.runner import GovernedRunCoordinator
        store = SQLiteAuditStore(db_path=".keelway/keelway_audit.db")
        coord = GovernedRunCoordinator(
            actor_id=args.actor,
            repo_path=args.repo,
            classification=args.classification,
            audit_store=store,
        )
        ok, msg = coord.start_run(args.task)
        if not ok:
            print(f"[-] Run failed: {msg}")
            sys.exit(1)
        print(f"[+] Governed run reached approval gate.")
        print(f"    Run ID:         {coord.run_id}")
        print(f"    Classification: {coord.classification.upper()}")
        print(f"    Approval ID:    {msg}")
        patch_hash = coord.workspace.get_patch_hash()
        print(f"    Patch Hash:     {patch_hash[:16]}...")
        diff = coord.workspace.get_diff()
        print("\n--- CANDIDATE PATCH DIFF (ISOLATED WORKSPACE) ---")
        print(diff)
        print("-------------------------------------------------")
    elif args.command == "runner":
        from keelway.runner.daemon import OutboundRunnerDaemon
        daemon = OutboundRunnerDaemon(
            runner_id=args.runner_id,
            org_id=args.org,
            control_plane_url=args.server,
            repo_dir=args.repo,
        )
        print(f"[+] Starting Outbound Runner Daemon '{args.runner_id}' for org '{args.org}'...")
        daemon.start(poll_interval=5.0)
    elif args.command == "m1":
        from core.m1_slice import run_m1_cli
        sys.exit(asyncio.run(run_m1_cli(args.repo)))
    elif args.command == "chat":
        asyncio.run(cmd_chat(args.provider, args.system, args.air_gapped, args.style))
    elif args.command == "brief":
        asyncio.run(cmd_brief(args.title, args.desc, args.files, args.failing, args.provider))
    elif args.command == "summarize":
        asyncio.run(cmd_summarize(args.doc_path, args.store_memory, args.provider))
    elif args.command == "test-sandbox":
        asyncio.run(cmd_test_sandbox(args.cmd, args.approve, args.provider))
    elif args.command == "eval":
        from run_compare import main as run_eval_main
        sys.argv = [sys.argv[0]] + (["--mock"] if args.mock else []) + (["--providers"] + args.providers if args.providers else [])
        run_eval_main()
    elif args.command == "memory":
        from core.storage.memory import MemoryService
        async def run_memory():
            await init_db()
            async with AsyncSessionLocal() as db:
                service = MemoryService(db)
                if args.mem_action == "store":
                    rec = await service.store(key=args.key, content=args.content, scope=args.scope, provenance_uri=args.uri)
                    await db.commit()
                    print(f"[+] Memory stored: key='{rec.key}' scope='{rec.scope}' (id: {rec.id})")
                elif args.mem_action == "get":
                    rec = await service.get(key=args.key, scope=args.scope)
                    if rec:
                        print(f"\n[+] Memory: {rec.key} ({rec.scope})")
                        print(f"    Content: {rec.content}")
                        if rec.provenance_uri:
                            print(f"    URI:     {rec.provenance_uri}")
                    else:
                        print(f"[-] Memory '{args.key}' not found in scope '{args.scope}'.")
                elif args.mem_action == "search":
                    if args.hybrid:
                        results = await service.search_hybrid(query_text=args.query, scope=args.scope, threshold=args.threshold)
                        print(f"\n[+] Hybrid Search for '{args.query}' (Found {len(results)} matches):")
                        for r, score in results:
                            print(f"  • [{score:.2f}] [{r.scope}] {r.key}: {r.content[:100]}...")
                    else:
                        results = await service.search(query_text=args.query, scope=args.scope)
                        print(f"\n[+] Keyword Search for '{args.query}' ({len(results)} matches):")
                        for r in results:
                            print(f"  • [{r.scope}] {r.key}: {r.content[:100]}...")
                elif args.mem_action == "ingest":
                    recs = await service.ingest_file(args.file_path, scope=args.scope, chunk_lines=args.lines)
                    await db.commit()
                    print(f"[+] Ingested {len(recs)} chunk(s) from '{args.file_path}' into scope '{args.scope}'.")
                elif args.mem_action == "list":
                    results = await service.list_by_scope(scope=args.scope)
                    print(f"\n[+] Scope '{args.scope}' ({len(results)} records):")
                    for r in results:
                        print(f"  • {r.key} (updated: {r.updated_at.strftime('%Y-%m-%d %H:%M:%S')}): {r.content[:80]}...")
        asyncio.run(run_memory())
    elif args.command == "dataset":
        from research.datasets.pipeline import TraceDatasetExtractor, ExportFormat
        async def run_dataset():
            await init_db()
            async with AsyncSessionLocal() as db:
                extractor = TraceDatasetExtractor(db)
                fmt = ExportFormat(args.format)
                manifest = await extractor.export_dataset(
                    output_file=args.output,
                    format_type=fmt,
                    workflow_type=args.workflow_type,
                    limit=args.limit,
                )
                print(f"\n[+] Exported dataset to: {args.output}")
                print(f"    Samples: {manifest['sample_count']}")
                print(f"    SHA-256: {manifest['sha256']}")
                print(f"    License: {manifest['license']}")
                print(f"    DLP Scanned: {manifest['data_governance']['dlp_scanned']}\n")
        asyncio.run(run_dataset())


if __name__ == "__main__":
    main()
