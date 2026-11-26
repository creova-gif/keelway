"""Keelway Command-Line Interface.
Implements local operator CLI commands for running workflows, reviewing diffs,
scaffolding demo repositories, and exporting/verifying cryptographic audit logs.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import uvicorn

from keelway.api.app import app
from keelway.audit.export import AuditExporter
from keelway.audit.store import SQLiteAuditStore
from keelway.core.runner import GovernedRunCoordinator


def scaffold_demo_repository(target_dir: str) -> None:
    """Scaffolds a clean sample Git repository for testing Keelway governance."""
    os.makedirs(target_dir, exist_ok=True)
    app_py = os.path.join(target_dir, "app.py")
    test_py = os.path.join(target_dir, "test_app.py")
    readme_md = os.path.join(target_dir, "README.md")

    with open(app_py, "w") as f:
        f.write('''"""Demo Microservice for Keelway Governance Testing."""

def health_check():
    return {"status": "ok", "service": "demo_service", "version": "1.0.0"}

def calculate_discount(amount: float, discount_pct: float) -> float:
    if discount_pct < 0 or discount_pct > 100:
        raise ValueError("Invalid discount percentage")
    return round(amount * (1.0 - discount_pct / 100.0), 2)
''')

    with open(test_py, "w") as f:
        f.write('''import pytest
from app import health_check, calculate_discount

def test_health_check():
    res = health_check()
    assert res["status"] == "ok"
    assert res["service"] == "demo_service"

def test_calculate_discount():
    assert calculate_discount(100.0, 20.0) == 80.0
    assert calculate_discount(50.0, 10.0) == 45.0
''')

    with open(readme_md, "w") as f:
        f.write('''# Demo Service
Sample repository used for evaluating and testing Keelway governance and audit controls.
''')

    # Initialize Git repository
    subprocess.run(["git", "init"], cwd=target_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Keelway Demo Developer"], cwd=target_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "dev@sorvexlabs.test"], cwd=target_dir, check=True, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=target_dir, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: initial commit of demo service"], cwd=target_dir, check=True, capture_output=True)
    print(f"✅ Demo repository scaffolded and initialized at: {os.path.abspath(target_dir)}")


def main():
    invoked_as = os.path.basename(sys.argv[0]) or "keelway-ops"
    prog = invoked_as if invoked_as.startswith("keelway") else "keelway-ops"
    if prog == "keelway-core":
        print(
            "WARNING: 'keelway-core' is deprecated; use 'keelway-ops' instead.",
            file=sys.stderr,
        )
    parser = argparse.ArgumentParser(
        prog=prog,
        description="Keelway by Sorvex Labs: Governed AI Software Change CLI",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Command: run
    run_parser = subparsers.add_parser("run", help="Start a governed AI change run")
    run_parser.add_argument("--task", required=True, help="Task description for the coding agent")
    run_parser.add_argument("--repo", default=".", help="Local repository path")
    run_parser.add_argument("--actor", default="local_engineer", help="Actor initiating the run")
    run_parser.add_argument(
        "--classification",
        default="internal",
        choices=["internal", "staging", "production"],
        help="Run environment classification",
    )
    run_parser.add_argument("--db", default="keelway_audit.db", help="Path to SQLite audit store")

    # Command: serve
    serve_parser = subparsers.add_parser("serve", help="Start the Keelway local API and dashboard server")
    serve_parser.add_argument("--host", default="127.0.0.1", help="Bind host")
    serve_parser.add_argument("--port", type=int, default=8000, help="Bind port")

    # Command: verify
    verify_parser = subparsers.add_parser("verify", help="Verify cryptographic audit chain integrity")
    verify_parser.add_argument("--run-id", required=True, help="Run ID to verify")
    verify_parser.add_argument("--db", default="keelway_audit.db", help="Path to SQLite audit store")

    # Command: export
    export_parser = subparsers.add_parser("export", help="Export sealed audit verification bundle")
    export_parser.add_argument("--run-id", required=True, help="Run ID to export")
    export_parser.add_argument("--db", default="keelway_audit.db", help="Path to SQLite audit store")
    export_parser.add_argument("--out", help="Output file path (default: stdout)")

    # Command: status
    status_parser = subparsers.add_parser("status", help="Inspect status and events of a run from SQLite")
    status_parser.add_argument("--run-id", required=True, help="Run ID to inspect")
    status_parser.add_argument("--db", default="keelway_audit.db", help="Path to SQLite audit store")

    # Command: init-demo
    demo_parser = subparsers.add_parser("init-demo", help="Scaffold a demo git repository for developer testing")
    demo_parser.add_argument("--dir", default="examples/demo_service", help="Target directory path")

    # Command: runner
    runner_parser = subparsers.add_parser("runner", help="Run outbound customer runner daemon")
    runner_parser.add_argument("--runner-id", default="runner_local_01", help="Runner identifier")
    runner_parser.add_argument("--org", default="org_sorvex_demo", help="Enrolled organization ID")
    runner_parser.add_argument("--secret", default="customer_secret_key_123", help="Shared secret key")
    runner_parser.add_argument("--server", default="http://127.0.0.1:8000", help="Control plane URL")
    runner_parser.add_argument("--repo", default=".", help="Allowed repository path")
    runner_parser.add_argument("--once", action="store_true", help="Poll once and exit")

    args = parser.parse_args()

    if args.command == "serve":
        print(f"🚀 Starting Keelway Local Governance Server on http://{args.host}:{args.port}")
        uvicorn.run(app, host=args.host, port=args.port)
    elif args.command == "run":
        print(f"🛡️ Keelway: Initializing governed run for task: {args.task}")
        store = SQLiteAuditStore(db_path=args.db)
        coord = GovernedRunCoordinator(
            actor_id=args.actor,
            repo_path=args.repo,
            classification=args.classification,
            audit_store=store,
        )
        ok, msg = coord.start_run(args.task)
        if not ok:
            print(f"❌ Run failed: {msg}")
            sys.exit(1)

        print("✅ Governed run reached approval gate.")
        print(f"   Run ID: {coord.run_id}")
        print(f"   Classification: {coord.classification.upper()}")
        print(f"   Approval ID: {msg}")
        patch_hash = coord.workspace.get_patch_hash()
        print(f"   Candidate Patch Hash: {patch_hash[:16]}...")
        diff = coord.workspace.get_diff()
        print("\n--- CANDIDATE PATCH DIFF (ISOLATED WORKSPACE) ---")
        print(diff)
        print("-------------------------------------------------")
        print(f"Audit events durably recorded to: {args.db}")
        print(f"To verify cryptographic integrity: python -m keelway.cli.main verify --run-id {coord.run_id} --db {args.db}")
        print(f"To export sealed compliance bundle: python -m keelway.cli.main export --run-id {coord.run_id} --db {args.db} --out bundle.json")
    elif args.command == "verify":
        store = SQLiteAuditStore(db_path=args.db)
        verified, err = store.verify_persisted_chain(args.run_id)
        if verified:
            events = store.get_events(args.run_id)
            print(f"✅ Run {args.run_id} VERIFIED: {len(events)} events, 0 tampering detected.")
        else:
            print(f"❌ Run {args.run_id} TAMPERED / INVALID: {err}")
            sys.exit(1)
    elif args.command == "export":
        store = SQLiteAuditStore(db_path=args.db)
        events = store.get_events(args.run_id)
        if not events:
            print(f"❌ No events found for run {args.run_id} in {args.db}")
            sys.exit(1)
        # Reconstruct manifest from first event
        first_payload = events[0].payload
        from keelway.core.models import RunManifest
        manifest = RunManifest(**first_payload)
        exporter = AuditExporter()
        bundle = exporter.export(manifest, events, redact_prompts=True)
        bundle_json = bundle.model_dump_json(indent=2)
        if args.out:
            with open(args.out, "w") as f:
                f.write(bundle_json)
            print(f"✅ Sealed audit bundle exported to {args.out}")
        else:
            print(bundle_json)
    elif args.command == "status":
        store = SQLiteAuditStore(db_path=args.db)
        events = store.get_events(args.run_id)
        if not events:
            print(f"❌ No events found for run {args.run_id} in {args.db}")
            sys.exit(1)
        print(f"📋 Status for Run ID: {args.run_id}")
        print(f"   Total Events: {len(events)}")
        first_event = events[0]
        last_event = events[-1]
        print(f"   Created: {first_event.created_at}")
        print(f"   Latest Event: #{last_event.seq} [{last_event.kind}] at {last_event.created_at}")
        for ev in events:
            print(f"   • #{ev.seq} [{ev.kind}] (hash: {ev.hash[:12]}...)")
    elif args.command == "init-demo":
        scaffold_demo_repository(args.dir)
    elif args.command == "runner":
        from keelway.runner.daemon import CustomerRunnerDaemon
        print(f"🤖 Starting Keelway Outbound Runner Daemon [{args.runner_id}] for org [{args.org}]")
        print(f"   Target Control Plane: {args.server}")
        print(f"   Allowed Repos: {args.repo}")
        runner = CustomerRunnerDaemon(
            runner_id=args.runner_id,
            org_id=args.org,
            secret_key=args.secret.encode("utf-8"),
            control_plane_url=args.server,
            allowed_repos=[args.repo],
        )
        if args.once:
            print("   Polling control plane for pending jobs...")
            res = runner.poll_and_execute_once()
            if res:
                print(f"✅ Job executed successfully: Run ID {res.get('run_id')}")
            else:
                print("ℹ️ No pending jobs found for this org.")
        else:
            import time
            print("   Listening for outbound jobs (Ctrl+C to stop)...")
            try:
                while True:
                    res = runner.poll_and_execute_once()
                    if res:
                        print(f"✅ Job executed: Run ID {res.get('run_id')}")
                    time.sleep(3)
            except KeyboardInterrupt:
                print("\n🛑 Runner stopped.")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
