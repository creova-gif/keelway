#!/usr/bin/env python3
"""
Kora AI Developer & Operations CLI Tool.
Usage:
  kora doctor
  kora brief [--title TITLE]
  kora summarize <path_to_doc> [--store-memory]
  kora test-sandbox <command> [--approve]
  kora eval [--mock]
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.resolve()))

from core.config import settings
from core.storage.database import check_db_health, init_db, AsyncSessionLocal
from core.models.gateway import gateway
from core.api.schemas import Provider
from core.orchestration.workflows import (
    EngineeringBriefWorkflow,
    ResearchSummaryWorkflow,
    SandboxedFailureAnalysisWorkflow,
)


async def cmd_doctor():
    """Check health of environment, database, and providers."""
    print("\n[+] Running Kora AI System Diagnostics (kora doctor)...\n")

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
    parser = argparse.ArgumentParser(prog="kora", description="Kora AI Core Developer & Operations CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # doctor
    subparsers.add_parser("doctor", help="Run system and provider diagnostics")

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

    mem_list_parser = mem_subparsers.add_parser("list", help="List memories in scope")
    mem_list_parser.add_argument("--scope", default="project", help="Scope")

    args = parser.parse_args()

    if args.command == "doctor":
        asyncio.run(cmd_doctor())
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
                    results = await service.search(query_text=args.query, scope=args.scope)
                    print(f"\n[+] Found {len(results)} memory record(s) matching '{args.query}':")
                    for r in results:
                        print(f"  • [{r.scope}] {r.key}: {r.content[:100]}...")
                elif args.mem_action == "list":
                    results = await service.list_by_scope(scope=args.scope)
                    print(f"\n[+] Scope '{args.scope}' ({len(results)} records):")
                    for r in results:
                        print(f"  • {r.key} (updated: {r.updated_at.strftime('%Y-%m-%d %H:%M:%S')}): {r.content[:80]}...")
        asyncio.run(run_memory())


if __name__ == "__main__":
    main()
