"""
Keelway Sovereign CLI Phase 10A Subcommands (`kbrain`, `khub`).

Registered and dispatched via `core.cli_runtime` supporting `--workspace` / `--workspace-id`,
`--db-path`, and `--json` for scope-aware KBrain Hybrid Memory and KHub Air-Gapped Registry workflows.
"""

from __future__ import annotations

import argparse
import json
from typing import List, Optional


def _add_common_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--workspace",
        "--workspace-id",
        dest="workspace_id",
        default="default",
        help="Target workspace identifier (default: default)",
    )
    parser.add_argument("--db-path", default=None, help="Optional SQLite database path override")
    parser.add_argument("--json", action="store_true", help="Emit JSON output")


def register_kbrain_khub_cli_subparsers(subparsers: argparse._SubParsersAction) -> None:
    """Register `kbrain` (`record`, `search`, `resolve`) and `khub` (`skills`, `verify-mirror`) CLI subcommands."""
    kb = subparsers.add_parser(
        "kbrain",
        help="Manage scope-aware KBrain hybrid BM25 + 3-gram memory facts with DLP & P-10 conflict governance",
    )
    kb_sub = kb.add_subparsers(dest="kbrain_command", required=True)

    kb_rec = kb_sub.add_parser("record", help="Record a KBrain fact with fail-closed DLP secret scanning")
    kb_rec.add_argument("--key", required=True, help="Fact key identifier (e.g., arch.db)")
    kb_rec.add_argument("--statement", required=True, help="Fact statement text")
    kb_rec.add_argument(
        "--scope",
        default="project",
        choices=["local_session", "project", "team", "org"],
        help="Fact visibility scope (default: project)",
    )
    kb_rec.add_argument("--provenance-uri", default="workspace", help="Fact provenance URI (default: workspace)")
    kb_rec.add_argument("--tag", action="append", default=[], help="Optional tag (repeatable)")
    kb_rec.add_argument("--created-by", default="owner", help="Creator principal identifier")
    kb_rec.add_argument("--no-auto-approve", action="store_true", help="Record as proposed instead of auto-approved")
    _add_common_flags(kb_rec)

    kb_search = kb_sub.add_parser("search", help="Search KBrain facts via Hybrid BM25 + 3-gram cosine similarity")
    kb_search.add_argument("--query", default="", help="Search query string")
    kb_search.add_argument(
        "--max-scope",
        default="org",
        choices=["local_session", "project", "team", "org"],
        help="Maximum scope hierarchy ceiling (default: org)",
    )
    kb_search.add_argument("--include-conflicts", action="store_true", help="Include proposed and conflicting facts")
    kb_search.add_argument("--limit", type=int, default=10, help="Maximum facts to return (default: 10)")
    _add_common_flags(kb_search)

    kb_res = kb_sub.add_parser("resolve", help="Approve or reject a KBrain fact conflict (P-10 governance)")
    kb_res.add_argument("--fact-id", required=True, help="Target fact identifier")
    kb_res.add_argument("--resolution", required=True, choices=["approve", "reject"], help="Resolution decision")
    kb_res.add_argument("--approver-id", default="owner", help="Human approver identifier")
    _add_common_flags(kb_res)

    kh = subparsers.add_parser("khub", help="Inspect KHub air-gapped skill catalog and verify offline .tar.gz mirrors")
    kh_sub = kh.add_subparsers(dest="khub_command", required=True)

    kh_skills = kh_sub.add_parser("skills", help="List built-in KStack skills with SHA-256 file tree digests")
    _add_common_flags(kh_skills)

    kh_verify = kh_sub.add_parser("verify-mirror", help="Execute a cryptographic air-gapped .tar.gz mirror roundtrip")
    kh_verify.add_argument("--skill-id", action="append", default=[], help="Optional skill ID filter (repeatable)")
    _add_common_flags(kh_verify)


def dispatch_kbrain_khub_cli(args: argparse.Namespace) -> Optional[int]:
    """Dispatch `kbrain` and `khub` sovereign CLI subcommands. Returns exit code or None."""
    cmd = getattr(args, "command", None)

    if cmd == "kbrain":
        from core.platform.kbrain_khub import SQLiteKBrainEngine, SecretLeakDetectedError

        sub = getattr(args, "kbrain_command", None)
        ws_id = str(getattr(args, "workspace_id", "default") or "default")
        as_json = bool(getattr(args, "json", False))
        engine = SQLiteKBrainEngine(db_path=getattr(args, "db_path", None))
        try:
            if sub == "record":
                tags: List[str] = list(getattr(args, "tag", None) or [])
                rec = engine.record_fact(
                    workspace_id=ws_id,
                    key=str(args.key),
                    statement=str(args.statement),
                    scope=str(getattr(args, "scope", "project")),
                    provenance_uri=str(getattr(args, "provenance_uri", "workspace")),
                    tags=tags,
                    created_by=str(getattr(args, "created_by", "owner")),
                    auto_approve=not bool(getattr(args, "no_auto_approve", False)),
                )
                if as_json:
                    print(json.dumps(rec, indent=2))
                else:
                    print(
                        f"[+] KBrain fact {rec['id']} [{rec['scope']}] key={rec['key']} "
                        f"status={rec['status']} sha256={rec['fact_sha256'][:23]}..."
                    )
                return 0

            if sub == "search":
                res = engine.search_facts(
                    workspace_id=ws_id,
                    query=str(getattr(args, "query", "")),
                    max_scope=str(getattr(args, "max_scope", "org")),
                    include_conflicts=bool(getattr(args, "include_conflicts", False)),
                    limit=int(getattr(args, "limit", 10)),
                )
                if as_json:
                    print(json.dumps(res, indent=2))
                else:
                    print(f"Keelway KBrain Search [{ws_id}] max_scope={res['max_scope']} matches={res['total_matches']}:")
                    for item in res["results"]:
                        print(
                            f"  - {item['id']} [{item['scope']}:{item['status']}] {item['key']} -> "
                            f"{item['statement']} (hybrid={item['hybrid_score']})"
                        )
                return 0

            if sub == "resolve":
                resolved = engine.resolve_fact(
                    workspace_id=ws_id,
                    fact_id=str(args.fact_id),
                    resolution=str(args.resolution),
                    approver_id=str(getattr(args, "approver_id", "owner")),
                )
                if as_json:
                    print(json.dumps(resolved, indent=2))
                else:
                    print(
                        f"[+] Resolved KBrain fact {resolved['id']} -> status={resolved['status']} "
                        f"(key={resolved['key']}, scope={resolved['scope']})"
                    )
                return 0
        except (SecretLeakDetectedError, KeyError, ValueError) as exc:
            print(json.dumps({"error": str(exc)}, indent=2) if as_json else f"[-] KBrain error: {exc}")
            return 1
        finally:
            engine.close()

    if cmd == "khub":
        from core.platform.kbrain_khub import SQLiteKHubRegistry

        sub = getattr(args, "khub_command", None)
        ws_id = str(getattr(args, "workspace_id", "default") or "default")
        as_json = bool(getattr(args, "json", False))
        registry = SQLiteKHubRegistry(db_path=getattr(args, "db_path", None))
        try:
            if sub == "skills":
                catalog = registry.list_skills(workspace_id=ws_id)
                if as_json:
                    print(json.dumps(catalog, indent=2))
                else:
                    print(
                        f"Keelway KHub Air-Gapped Skills [{ws_id}] total={catalog['total_skills']} "
                        f"digest={catalog['catalog_digest_sha256'][:23]}..."
                    )
                    for sk in catalog["skills"]:
                        print(f"  - {sk['skill_id']:<16} {sk['name']} ({sk['bundle_digest_sha256'][:23]}...)")
                return 0

            if sub == "verify-mirror":
                skill_ids: List[str] = list(getattr(args, "skill_id", None) or [])
                receipt = registry.verify_airgap_mirror(
                    workspace_id=ws_id,
                    skill_ids=skill_ids if skill_ids else None,
                )
                if as_json:
                    print(json.dumps(receipt, indent=2))
                else:
                    print(
                        f"[+] KHub Air-Gapped Mirror Verified [{ws_id}] skills={receipt['skills_verified']} "
                        f"format={receipt['mirror_format']} digest={receipt['catalog_digest_sha256'][:23]}..."
                    )
                return 0
        except (FileNotFoundError, ValueError) as exc:
            print(json.dumps({"error": str(exc)}, indent=2) if as_json else f"[-] KHub error: {exc}")
            return 1
        finally:
            registry.close()

    return None
