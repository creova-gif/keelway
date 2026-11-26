"""
Keelway Unified Workspace Hub & External Extension SDK.

Connects all 10 sovereign workspace views (`agents`, `ide`, `pm`, `product`, `automation`,
`marketplace`, `security`, `docs`, `operations`, `nocode`), 12 specialized lifecycle agents,
coordinated multi-agent teams with mandatory P-10 human approval checkpoints, the 9-stage
cross-agent SDLC (`Antigravity` / `Claude` / `Devin` / `gstack`), No-Code natural-language
blueprint compilation, and a security-validated Extension SDK.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Dict, List, Optional
import uuid

from core.platform.marketplace import MarketplaceSecurityScanner
from core.platform.persistence import SQLitePlatformStore
from core.security.redact import redact_text


PLATFORM_VIEWS: List[Dict[str, str]] = [
    {"id": "agents", "name": "Agents", "summary": "12 specialized lifecycle agents, multi-agent teams, and P-10 supervision."},
    {"id": "ide", "name": "IDE", "summary": "AI-assisted Tasks & Files workspace, AST symbol jump, diff review, and sandboxed shell."},
    {"id": "pm", "name": "Project Manager", "summary": "Linear-inspired issues, sprint boards, milestones, and 1-click agent delegation."},
    {"id": "product", "name": "Product", "summary": "Discovery, structured PRDs, acceptance criteria, RICE scoring, and release plans."},
    {"id": "automation", "name": "Automation", "summary": "Visual KFlow DAG & cron/webhook workflow builder with retry diagnostics."},
    {"id": "marketplace", "name": "Marketplace", "summary": "Security-verified 1st/3rd-party agents, skills, plugins, and enterprise packs."},
    {"id": "security", "name": "Security", "summary": "SHA-256 hash-chained Record ledger, RBAC, P-10 gates, and vulnerability posture."},
    {"id": "docs", "name": "Documentation", "summary": "Diataxis technical docs, onboarding runbooks, and cross-agent AGENTS.md contract."},
    {"id": "operations", "name": "Operations", "summary": "Deployments, rollback controls, OpenCore vs BYOM spend ledger, and latency SLOs."},
    {"id": "nocode", "name": "No-Code Builder", "summary": "Plain-language idea to linked PRD, sprint issues, DAG workflow, and governed deploy."},
]


def _agent_spec(
    agent_id: str,
    name: str,
    role_domain: str,
    scoped_tools: List[str],
    risk_tier: str,
    description: str,
) -> Dict[str, Any]:
    digest = hashlib.sha256(f"{agent_id}:{name}:{','.join(scoped_tools)}".encode("utf-8")).hexdigest()
    return {
        "id": agent_id,
        "name": name,
        "role_domain": role_domain,
        "scoped_tools": scoped_tools,
        "risk_tier": risk_tier,
        "requires_p10_for_mutations": risk_tier in {"B", "C"},
        "manifest_sha256": digest,
        "description": description,
    }


LIFECYCLE_AGENTS: List[Dict[str, Any]] = [
    _agent_spec("issue-triager", "Issue Triage & Resolver", "issue_triage_resolution", ["pm.read_issues", "repo.search_ast", "pm.update_status"], "A", "Classifies incoming bugs/tickets, reproduces root causes, and links candidate code paths."),
    _agent_spec("feature-coder", "Code Generation & Refactoring Specialist", "codegen_refactoring", ["repo.read_file", "repo.apply_patch", "sandbox.pytest"], "B", "Implements typed features and modular refactors strictly within file-ownership and size caps."),
    _agent_spec("pr-reviewer", "Pull Request & Diff QA Reviewer", "pr_review_qa", ["git.diff_inspect", "ast.boundary_check", "review.annotate"], "A", "Audits diffs for logic regressions, race conditions, gate tampering, and missing negative tests."),
    _agent_spec("qa-ci-runner", "Automated Test & CI Verification Agent", "automated_ci_testing", ["sandbox.pytest", "sandbox.vitest", "coverage.inspect"], "A", "Synthesizes unit/integration/a11y suites and reconciles CI failure logs before merge."),
    _agent_spec("security-auditor", "Security Assessment & Remediation Agent", "security_remediation", ["security.dlp_scan", "security.rbac_verify", "marketplace.scan"], "B", "Executes STRIDE/OWASP checks, secret hygiene scans, and remediation patches."),
    _agent_spec("tech-writer", "Diataxis Technical Documentation Agent", "technical_documentation", ["repo.read_file", "docs.write_markdown", "facts.sync_check"], "A", "Maintains tutorials, how-to guides, API references, and evidence-backed product docs."),
    _agent_spec("workflow-automator", "Workflow & Event Automation Architect", "workflow_automation", ["kflow.compile_dag", "cron.schedule", "webhook.bind"], "B", "Designs durable multi-step DAGs, retries, and event-driven automation pipelines."),
    _agent_spec("product-strategist", "Product Management & Roadmap Agent", "pm_roadmap_planning", ["product.write_prd", "pm.plan_sprint", "metrics.rice_score"], "A", "Drafts structured PRDs, acceptance criteria, RICE prioritizations, and milestone roadmaps."),
    _agent_spec("code-architect", "Systems Architecture & ADR Advisor", "architecture_decisions", ["repo.dependency_graph", "docs.write_adr", "scale.model_slo"], "A", "Defines shared-infrastructure boundaries, data schemas, ADRs, and latency/cost budgets."),
    _agent_spec("devops-sre", "DevOps, Release & Incident Responder", "devops_sre_incident", ["ops.deploy_preview", "ops.rollback", "ops.slo_inspect"], "C", "Manages staged rollouts, canary health checks, incident runbooks, and P-10 gated production deploys."),
    _agent_spec("custom-agent-forge", "Custom Agent & Skill Builder", "custom_agent_builder", ["agent.compose_manifest", "marketplace.scan", "sdk.register_skill"], "B", "Helps developers author, sign, and security-scan custom agents, skills, and MCP extensions."),
    _agent_spec("nocode-app-builder", "Guided Business & App Builder", "non_coder_app_builder", ["nocode.compile_blueprint", "product.write_prd", "ops.managed_deploy"], "B", "Translates plain-language business ideas from non-coders into governed full-stack workflows and apps."),
]


MULTI_AGENT_TEAMS: List[Dict[str, Any]] = [
    {
        "id": "idea-to-production-squad",
        "name": "Idea-to-Production Lifecycle Squad",
        "lead_agent": "product-strategist",
        "members": [
            "product-strategist",
            "code-architect",
            "feature-coder",
            "qa-ci-runner",
            "security-auditor",
            "devops-sre",
        ],
        "p10_checkpoints": ["schema_migration_apply", "production_deployment"],
        "description": "End-to-end delivery from PRD and architecture to tested implementation and P-10 gated release.",
    },
    {
        "id": "security-release-gate-squad",
        "name": "Security & Release Assurance Squad",
        "lead_agent": "security-auditor",
        "members": ["pr-reviewer", "security-auditor", "qa-ci-runner", "tech-writer"],
        "p10_checkpoints": ["security_waiver", "external_egress"],
        "description": "Pre-merge verification squad enforcing zero-secret leakage, RBAC invariants, and doc parity.",
    },
    {
        "id": "nocode-guided-launch-squad",
        "name": "Guided Non-Coder App Launch Squad",
        "lead_agent": "nocode-app-builder",
        "members": ["nocode-app-builder", "product-strategist", "workflow-automator", "security-auditor", "devops-sre"],
        "p10_checkpoints": ["managed_production_publish"],
        "description": "Turns plain-English business workflows into verified apps with human-approved deployment.",
    },
]


SDLC_WORKFLOW_STAGES: List[Dict[str, Any]] = [
    {"stage": 1, "id": "requirements", "name": "Requirements & Acceptance Criteria", "owner_agent": "product-strategist", "compatible_harnesses": ["Antigravity", "Claude", "Devin", "gstack"]},
    {"stage": 2, "id": "architecture", "name": "Architecture & Implementation Planning", "owner_agent": "code-architect", "compatible_harnesses": ["Antigravity", "Claude", "Devin", "gstack"]},
    {"stage": 3, "id": "issue_tracking", "name": "Issue Tracking & Sprint Assignment", "owner_agent": "issue-triager", "compatible_harnesses": ["Antigravity", "Claude", "Devin", "gstack"]},
    {"stage": 4, "id": "implementation", "name": "Implementation & Peer Diff Review", "owner_agent": "feature-coder", "compatible_harnesses": ["Antigravity", "Claude", "Devin", "gstack"]},
    {"stage": 5, "id": "verification", "name": "Automated Testing & Security Scanning", "owner_agent": "qa-ci-runner", "compatible_harnesses": ["Antigravity", "Claude", "Devin", "gstack"]},
    {"stage": 6, "id": "p10_approval", "name": "Human Governance Checkpoint (P-10)", "owner_agent": "human-operator", "compatible_harnesses": ["Antigravity", "Claude", "Devin", "gstack"]},
    {"stage": 7, "id": "documentation", "name": "Documentation & Change Management", "owner_agent": "tech-writer", "compatible_harnesses": ["Antigravity", "Claude", "Devin", "gstack"]},
    {"stage": 8, "id": "deployment", "name": "Deployment, SLO Monitoring & Rollback", "owner_agent": "devops-sre", "compatible_harnesses": ["Antigravity", "Claude", "Devin", "gstack"]},
    {"stage": 9, "id": "evaluation", "name": "Continuous Evaluation & Retro", "owner_agent": "pr-reviewer", "compatible_harnesses": ["Antigravity", "Claude", "Devin", "gstack"]},
]

SUPPORTED_EXTENSION_TYPES = {"skill", "tool", "webhook", "workflow_rule", "ui_panel"}
VALID_DIATAXIS_KINDS = {"tutorial", "how_to", "reference", "explanation"}
_ALLOWED_ISSUE_PATCH_FIELDS = {
    "title", "status", "priority", "sprint_id", "prd_id", "assignee_agent", "description", "dependencies"
}
_SENSITIVE_KEYWORDS = re.compile(r"(?i)\b(?:deploy|prod|production|migration|drop|delete|egress|external|publish)\b")
_LIVE_KEY_PATTERN = re.compile(r"\b(?:sk|pk|rk)[-_](?:live|test|proj|ant)[-_][A-Za-z0-9_-]{4,}")


def _next_record_id(prefix: str, items: List[Dict[str, Any]]) -> str:
    nums = [100]
    for item in items:
        m = re.search(r"(\d+)$", str(item.get("id") or ""))
        if m:
            nums.append(int(m.group(1)))
    return f"{prefix}-{max(nums) + 1}"


class ExtensionRegistry:
    """External Extension SDK allowing third-party hooks without mutating core platform modules."""

    def __init__(
        self,
        scanner: Optional[MarketplaceSecurityScanner] = None,
        store: Optional[SQLitePlatformStore] = None,
    ) -> None:
        self.scanner = scanner or MarketplaceSecurityScanner()
        self.store: Optional[SQLitePlatformStore] = None
        self._extensions: Dict[str, Dict[str, Any]] = {}
        if store is not None:
            self.bind_store(store)

    def bind_store(self, store: SQLitePlatformStore) -> None:
        self.store = store
        for persisted in self.store.list_records("__global__", "extensions"):
            ext_id = str(persisted.get("id") or "").strip()
            if ext_id:
                self._extensions[ext_id] = dict(persisted)

    def register_extension(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        ext_id = str(spec.get("id") or "").strip()
        if not ext_id:
            raise ValueError("Extension 'id' is required.")
        ext_type = str(spec.get("extension_type") or "skill").strip().lower()
        if ext_type not in SUPPORTED_EXTENSION_TYPES:
            raise ValueError(f"Unsupported extension_type '{ext_type}'. Expected one of {sorted(SUPPORTED_EXTENSION_TYPES)}.")

        report = self.scanner.scan_package(spec)
        if not report["passed"]:
            from core.platform.marketplace import MarketplaceSecurityError

            raise MarketplaceSecurityError(report)

        record = {
            "id": ext_id,
            "name": str(spec.get("name") or ext_id),
            "extension_type": ext_type,
            "version": str(spec.get("version") or "1.0.0"),
            "publisher": str(spec.get("publisher") or "External Developer"),
            "description": str(spec.get("description") or ""),
            "entrypoint": str(spec.get("entrypoint") or f"extensions.{ext_id}:handle"),
            "permissions": dict(spec.get("permissions") or {"read_paths": [], "write_paths": [], "network": "none"}),
            "manifest_sha256": report["manifest_sha256"],
            "status": "registered",
            "registered_at": datetime.now(timezone.utc).isoformat(),
        }
        self._extensions[ext_id] = record
        if self.store is not None:
            self.store.upsert_record("__global__", "extensions", ext_id, record)
        return dict(record)

    def list_extensions(self, extension_type: Optional[str] = None) -> List[Dict[str, Any]]:
        items = list(self._extensions.values())
        if extension_type:
            items = [e for e in items if e["extension_type"] == extension_type]
        return [dict(e) for e in items]


class UnifiedWorkspaceHub:
    """Shared state engine across all 10 Unified Platform Views with SQLite WAL or JSON persistence."""

    def __init__(
        self,
        storage_path: Optional[Path] = None,
        extension_registry: Optional[ExtensionRegistry] = None,
        store: Optional[SQLitePlatformStore] = None,
    ) -> None:
        self.storage_path = Path(storage_path) if storage_path else None
        self.store = store
        self.extensions = extension_registry or ExtensionRegistry(store=store)
        if extension_registry is not None and store is not None and self.extensions.store is None:
            self.extensions.bind_store(store)
        self._workspaces: Dict[str, Dict[str, Any]] = {}
        self._load()
        self._ensure_workspace("default")

    @staticmethod
    def _seed_workspace_template(workspace_id: str) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        return {
            "workspace_id": workspace_id,
            "project_name": "Keelway Sovereign Workspace" if workspace_id == "default" else workspace_id,
            "branch": "main",
            "active_model_id": "keelway-core:7b",
            "experience_mode": "builder",
            "sprints": [{"id": "SPR-01", "name": "Sprint 1 · Core Foundation", "status": "active"}],
            "prds": [{
                "id": "PRD-101",
                "title": "Unified Sovereign Agent Workspace",
                "summary": "Single local-first operating environment spanning 10 integrated engineering and business views.",
                "status": "approved",
                "acceptance_criteria": ["10 unified views share state", "P-10 human-only gates enforced"],
                "created_at": now,
            }],
            "issues": [{
                "id": "KEEL-101",
                "title": "Verify OpenCore local fallback under Community quota cap",
                "status": "in_progress",
                "priority": "high",
                "sprint_id": "SPR-01",
                "prd_id": "PRD-101",
                "assignee_agent": "qa-ci-runner",
                "created_at": now,
            }],
            "workflows": [{
                "id": "WF-101",
                "name": "Pre-Landing Gate & Audit Verification",
                "trigger": "git.pull_request",
                "status": "active",
                "nodes": [
                    {"id": "n1", "label": "Static & Secret Scan", "agent": "security-auditor"},
                    {"id": "n2", "label": "Pytest + Vitest Matrix", "agent": "qa-ci-runner"},
                    {"id": "n3", "label": "P-10 Human Release Signoff", "agent": "human-operator"},
                ],
                "created_at": now,
            }],
            "docs": [
                {"id": "DOC-101", "title": "Cross-Agent Engineering Contract (AGENTS.md)", "diataxis_kind": "reference", "summary": "Shared workflow across Antigravity, Claude Code, Devin, and gstack.", "body": "# Cross-Agent Contract\n\n```bash\n./scripts/verify_engineering_gates.sh\n```\n\n- [x] P-10 human-only gates enforced\n- [x] Deterministic file-size caps verified", "linked_prd_id": "PRD-101", "updated_at": now},
                {"id": "DOC-102", "title": "Quickstart: Launch a Local-First Multi-Agent Squad", "diataxis_kind": "tutorial", "summary": "Step-by-step walkthrough from plain-language PRD to P-10 gated team execution.", "body": "# Local-First Squad Tutorial\n\n```python\nrun = hub.dispatch_agent_team('idea-to-production-squad', 'Stage preview build')\n```\n\n- [x] Select workspace & active model\n- [ ] Approve P-10 release checkpoint", "linked_prd_id": "PRD-101", "updated_at": now},
                {"id": "DOC-103", "title": "How-To: Configure BYOM API Keys & DLP Guardrails", "diataxis_kind": "how_to", "summary": "Operational runbook for commercial API keys and zero-consumer-cookie enforcement.", "body": "# Configure BYOM & DLP\n\n```json\n{\"provider\": \"openai\", \"credential_kind\": \"api_key\"}\n```\n\n- [x] Reject consumer web cookies\n- [x] Run `/v1/platform/security/scan` preflight", "linked_prd_id": "PRD-101", "updated_at": now},
                {"id": "DOC-104", "title": "Architecture: SQLite WAL Store & Hash-Chained Record Ledger", "diataxis_kind": "explanation", "summary": "Design rationale behind crash-safe WAL persistence and Ed25519 manifest verification.", "body": "# Sovereign Persistence Architecture\n\n```sql\nPRAGMA journal_mode=WAL;\nPRAGMA synchronous=NORMAL;\n```\n\n- [x] Zero duplicate seed hydration\n- [x] Ed25519 tamper-evident manifests", "linked_prd_id": "PRD-101", "updated_at": now},
            ],
            "feedback": [{"id": "FB-101", "persona": "Staff Platform Engineer", "quote": "Linking PRDs, Diataxis runbooks, and P-10 gated KFlow pipelines in one sovereign hub eliminated release drift.", "impact_score": 9.2, "linked_prd_id": "PRD-101", "created_at": now}],
            "deployments": [{"id": "DEP-101", "environment": "local-sovereign", "status": "healthy", "ttft_p95_ms": 185, "slo_met": True}],
            "team_runs": [],
        }

    _META_KEYS = ("project_name", "branch", "active_model_id", "experience_mode", "sprints", "deployments", "team_runs")
    _RECORD_COLLECTIONS = ("prds", "issues", "workflows", "docs", "feedback")

    def _persist_workspace_to_sqlite(self, ws: Dict[str, Any]) -> None:
        if self.store is None:
            return
        wid = ws["workspace_id"]
        self.store.upsert_workspace_meta(wid, {k: ws[k] for k in self._META_KEYS})
        for col in self._RECORD_COLLECTIONS:
            for rec in ws[col]:
                self.store.upsert_record(wid, col, rec["id"], rec)

    def _hydrate_workspace_from_sqlite(self, workspace_id: str) -> Optional[Dict[str, Any]]:
        if self.store is None:
            return None
        meta = self.store.get_workspace_meta(workspace_id)
        cols = {col: self.store.list_records(workspace_id, col) for col in self._RECORD_COLLECTIONS}
        if meta is None and not any(cols.values()):
            return None
        base = self._seed_workspace_template(workspace_id)
        if meta:
            base.update({k: meta[k] for k in self._META_KEYS if k in meta})
        for col, rows in cols.items():
            base[col] = rows or base[col]
        return base

    def _ensure_workspace(self, workspace_id: str) -> Dict[str, Any]:
        if workspace_id not in self._workspaces:
            hydrated = self._hydrate_workspace_from_sqlite(workspace_id)
            if hydrated is not None:
                self._workspaces[workspace_id] = hydrated
            else:
                seeded = self._seed_workspace_template(workspace_id)
                self._workspaces[workspace_id] = seeded
                self._persist_workspace_to_sqlite(seeded)
        ws = self._workspaces[workspace_id]
        if "feedback" not in ws or "docs" not in ws:
            defaults = self._seed_workspace_template(workspace_id)
            ws.setdefault("docs", defaults["docs"])
            ws.setdefault("feedback", defaults["feedback"])
        return ws

    def _load(self) -> None:
        if self.storage_path and self.storage_path.exists():
            data = json.loads(self.storage_path.read_text(encoding="utf-8"))
            if isinstance(data.get("workspaces"), dict):
                self._workspaces.update(data["workspaces"])
        if self.store is not None:
            for ws_id in self.store.list_workspaces():
                if not ws_id.startswith("__"):
                    hydrated = self._hydrate_workspace_from_sqlite(ws_id)
                    if hydrated is not None:
                        self._workspaces[ws_id] = hydrated

    def _save(self, workspace_id: Optional[str] = None) -> None:
        if self.storage_path:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {"updated_at": datetime.now(timezone.utc).isoformat(), "workspaces": self._workspaces}
            self.storage_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        if self.store is not None and workspace_id and workspace_id in self._workspaces:
            ws = self._workspaces[workspace_id]
            self.store.upsert_workspace_meta(workspace_id, {k: ws[k] for k in self._META_KEYS})

    def get_overview(
        self,
        workspace_id: str = "default",
        installed_packages: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        ws = self._ensure_workspace(workspace_id)
        pending_p10 = sum(1 for r in ws["team_runs"] if r.get("status") == "awaiting_p10_approval")
        return {
            "workspace_id": workspace_id,
            "project_name": ws["project_name"],
            "branch": ws["branch"],
            "active_model_id": ws["active_model_id"],
            "experience_mode": ws["experience_mode"],
            "views": PLATFORM_VIEWS,
            "lifecycle_agents_count": len(LIFECYCLE_AGENTS),
            "multi_agent_teams_count": len(MULTI_AGENT_TEAMS),
            "sdlc_stages": SDLC_WORKFLOW_STAGES,
            "counts": {
                "issues": len(ws["issues"]),
                "prds": len(ws["prds"]),
                "workflows": len(ws["workflows"]),
                "docs": len(ws["docs"]),
                "feedback": len(ws["feedback"]),
                "deployments": len(ws["deployments"]),
                "pending_p10_approvals": pending_p10,
                "installed_packages": len(installed_packages or []),
                "registered_extensions": len(self.extensions.list_extensions()),
            },
            "installed_packages": installed_packages or [],
        }

    def list_agents_and_teams(self) -> Dict[str, Any]:
        return {
            "agents": [dict(a) for a in LIFECYCLE_AGENTS],
            "teams": [dict(t) for t in MULTI_AGENT_TEAMS],
            "sdlc_stages": [dict(s) for s in SDLC_WORKFLOW_STAGES],
        }

    def dispatch_agent_team(
        self,
        team_id: str,
        objective: str,
        workspace_id: str = "default",
        sensitive_mutation: bool = True,
        requested_by: str = "operator",
    ) -> Dict[str, Any]:
        ws = self._ensure_workspace(workspace_id)
        team = next((t for t in MULTI_AGENT_TEAMS if t["id"] == team_id), None)
        if team is None:
            raise KeyError(f"Multi-agent team '{team_id}' not found.")

        agents_by_id = {a["id"]: a for a in LIFECYCLE_AGENTS}
        requires_p10 = bool(sensitive_mutation or _SENSITIVE_KEYWORDS.search(objective))
        trace = []
        for idx, member_id in enumerate(team["members"], start=1):
            spec = agents_by_id[member_id]
            step_state = (
                "blocked_on_p10"
                if requires_p10 and idx == len(team["members"])
                else "ready"
            )
            trace.append(
                {
                    "step": idx,
                    "agent_id": member_id,
                    "agent_name": spec["name"],
                    "scoped_tools": spec["scoped_tools"],
                    "risk_tier": spec["risk_tier"],
                    "state": step_state,
                }
            )

        run_record = {
            "run_id": f"TEAMRUN-{uuid.uuid4().hex[:8].upper()}",
            "workspace_id": workspace_id,
            "team_id": team["id"],
            "team_name": team["name"],
            "objective": objective,
            "requested_by": requested_by,
            "status": "awaiting_p10_approval" if requires_p10 else "completed",
            "p10_checkpoint": {
                "gate": "P-10",
                "human_approval_required": requires_p10,
                "agent_self_approval_permitted": False,
                "checkpoints": team["p10_checkpoints"],
                "reason": (
                    "Sensitive mutation or production deployment requires explicit human P-10 approval."
                    if requires_p10
                    else "Read-only analysis completed within Risk A envelope."
                ),
            },
            "delegation_trace": trace,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        ws["team_runs"].append(run_record)
        self._save(workspace_id)
        return dict(run_record)

    def list_team_runs(self, workspace_id: str = "default") -> List[Dict[str, Any]]:
        return [dict(r) for r in self._ensure_workspace(workspace_id)["team_runs"]]

    def list_issues(self, workspace_id: str = "default") -> List[Dict[str, Any]]:
        return [dict(i) for i in self._ensure_workspace(workspace_id)["issues"]]

    def create_issue(
        self, title: str, workspace_id: str = "default", priority: str = "medium", status: str = "todo",
        assignee_agent: str = "feature-coder", prd_id: Optional[str] = None, sprint_id: str = "SPR-01",
    ) -> Dict[str, Any]:
        ws = self._ensure_workspace(workspace_id)
        issue = {
            "id": _next_record_id("KEEL", ws["issues"]),
            "title": title.strip(),
            "status": status,
            "priority": priority,
            "sprint_id": sprint_id,
            "prd_id": prd_id,
            "assignee_agent": assignee_agent,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        ws["issues"].append(issue)
        if self.store is not None:
            self.store.upsert_record(workspace_id, "issues", issue["id"], issue)
        self._save(workspace_id)
        return dict(issue)

    def update_issue(
        self, workspace_id: str = "default", issue_id: str = "", patch: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        ws = self._ensure_workspace(workspace_id)
        issue = next((i for i in ws["issues"] if i["id"] == issue_id), None)
        if issue is None:
            raise KeyError(f"Issue '{issue_id}' not found in workspace '{workspace_id}'.")
        for key, val in (patch or {}).items():
            if key not in _ALLOWED_ISSUE_PATCH_FIELDS:
                continue
            if key == "title":
                clean_title = str(val or "").strip()
                if not clean_title:
                    raise ValueError("Issue 'title' cannot be empty.")
                issue["title"] = clean_title
            elif key == "dependencies":
                issue["dependencies"] = list(val or [])
            else:
                issue[key] = val
        issue["updated_at"] = datetime.now(timezone.utc).isoformat()
        if self.store is not None:
            self.store.upsert_record(workspace_id, "issues", issue["id"], issue)
        self._save(workspace_id)
        return dict(issue)

    def list_prds(self, workspace_id: str = "default") -> List[Dict[str, Any]]:
        return [dict(p) for p in self._ensure_workspace(workspace_id)["prds"]]

    def create_prd(
        self,
        title: str,
        summary: str,
        workspace_id: str = "default",
        acceptance_criteria: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        ws = self._ensure_workspace(workspace_id)
        prd: Dict[str, Any] = {
            "id": _next_record_id("PRD", ws["prds"]),
            "title": title.strip(),
            "summary": summary.strip(),
            "status": "draft",
            "acceptance_criteria": list(acceptance_criteria or ["Deterministic test coverage", "P-10 review"]),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        ws["prds"].append(prd)
        if self.store is not None:
            self.store.upsert_record(workspace_id, "prds", prd["id"], prd)
        self._save(workspace_id)
        return dict(prd)

    def list_workflows(self, workspace_id: str = "default") -> List[Dict[str, Any]]:
        return [dict(w) for w in self._ensure_workspace(workspace_id)["workflows"]]

    def list_sprints(self, workspace_id: str = "default") -> List[Dict[str, Any]]:
        return [dict(s) for s in self._ensure_workspace(workspace_id)["sprints"]]

    def list_docs(self, workspace_id: str = "default") -> List[Dict[str, Any]]:
        return [dict(d) for d in self._ensure_workspace(workspace_id)["docs"]]

    def upsert_doc(
        self, workspace_id: str = "default", *, doc_id: Optional[str] = None, title: str,
        diataxis_kind: str = "reference", summary: str = "", body: str = "", linked_prd_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        clean_title = str(title or "").strip()
        if not clean_title:
            raise ValueError("Document 'title' is required.")
        kind = str(diataxis_kind or "reference").strip().lower()
        if kind not in VALID_DIATAXIS_KINDS:
            raise ValueError(f"Invalid diataxis_kind '{kind}'. Expected one of {sorted(VALID_DIATAXIS_KINDS)}.")
        ws = self._ensure_workspace(workspace_id)
        now = datetime.now(timezone.utc).isoformat()
        clean_id = str(doc_id or "").strip()
        existing = next((d for d in ws["docs"] if d["id"] == clean_id), None) if clean_id else None
        if existing is not None:
            existing.update({"title": clean_title, "diataxis_kind": kind, "summary": summary.strip(), "body": body, "linked_prd_id": linked_prd_id, "updated_at": now})
            doc = existing
        else:
            doc = {"id": clean_id or _next_record_id("DOC", ws["docs"]), "title": clean_title, "diataxis_kind": kind, "summary": summary.strip(), "body": body, "linked_prd_id": linked_prd_id, "updated_at": now}
            ws["docs"].append(doc)
        if self.store is not None:
            self.store.upsert_record(workspace_id, "docs", doc["id"], doc)
        self._save(workspace_id)
        return dict(doc)

    def list_feedback(self, workspace_id: str = "default") -> List[Dict[str, Any]]:
        return [dict(f) for f in self._ensure_workspace(workspace_id)["feedback"]]

    def create_feedback(
        self, persona: str, quote: str, impact_score: float = 8.0,
        linked_prd_id: Optional[str] = None, workspace_id: str = "default",
    ) -> Dict[str, Any]:
        clean_persona, clean_quote = str(persona or "").strip(), str(quote or "").strip()
        if not clean_persona or not clean_quote:
            raise ValueError("Feedback 'persona' and 'quote' must be non-empty.")
        score = round(float(impact_score), 2)
        if not (0.0 <= score <= 10.0):
            raise ValueError("Feedback 'impact_score' must be between 0.0 and 10.0.")
        ws = self._ensure_workspace(workspace_id)
        entry: Dict[str, Any] = {
            "id": _next_record_id("FB", ws["feedback"]), "persona": clean_persona, "quote": clean_quote,
            "impact_score": score, "linked_prd_id": linked_prd_id, "created_at": datetime.now(timezone.utc).isoformat(),
        }
        ws["feedback"].append(entry)
        if self.store is not None:
            self.store.upsert_record(workspace_id, "feedback", entry["id"], entry)
        self._save(workspace_id)
        return dict(entry)

    def scan_workspace_security(self, target_name: str, content: str, workspace_id: str = "default") -> Dict[str, Any]:
        clean_target = str(target_name or "workspace-artifact").strip() or "workspace-artifact"
        raw_content = str(content or "")
        report = self.extensions.scanner.scan_package(
            {"id": "ws-scan", "name": clean_target, "description": raw_content, "permissions": {"read_paths": ["./"], "write_paths": [], "network": "none"}}
        )
        findings = [dict(f) for f in report.get("findings", [])]
        redacted, redact_hits = redact_text(raw_content)
        if (redacted != raw_content or redact_hits > 0 or _LIVE_KEY_PATTERN.search(raw_content)) and not any(
            f.get("category") == "hardcoded_secret" for f in findings
        ):
            findings.append({
                "category": "hardcoded_secret", "rule_id": "workspace_secret_detected", "severity": "critical",
                "field": "content", "message": f"Detected embedded secret or API key in '{clean_target}'.",
            })
        passed = len(findings) == 0
        return {
            "workspace_id": workspace_id, "target_name": clean_target, "passed": passed,
            "risk_grade": "A" if passed else "BLOCKED", "findings": findings, "findings_count": len(findings),
            "manifest_sha256": report["manifest_sha256"], "scanned_at": report["scanned_at"],
        }

    def list_deployments(self, workspace_id: str = "default") -> List[Dict[str, Any]]:
        return [dict(d) for d in self._ensure_workspace(workspace_id)["deployments"]]

    def create_workflow(
        self,
        name: str,
        trigger: str = "manual",
        nodes: Optional[List[Dict[str, Any]]] = None,
        workspace_id: str = "default",
    ) -> Dict[str, Any]:
        ws = self._ensure_workspace(workspace_id)
        wf: Dict[str, Any] = {
            "id": _next_record_id("WF", ws["workflows"]),
            "name": name.strip(),
            "trigger": trigger,
            "status": "active",
            "nodes": list(nodes or [{"id": "n1", "label": "Execute Task", "agent": "workflow-automator"}]),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        ws["workflows"].append(wf)
        if self.store is not None:
            self.store.upsert_record(workspace_id, "workflows", wf["id"], wf)
        self._save(workspace_id)
        return dict(wf)

    def compile_nocode_blueprint(
        self,
        idea: str,
        workspace_id: str = "default",
        experience_mode: str = "non_coder",
        target_stack: str = "fastapi_react_sqlite",
    ) -> Dict[str, Any]:
        """Compiles a plain-language idea into linked PRD + 4 Sprint Issues + Workflow DAG + P-10 Team Run."""
        clean_idea = idea.strip()
        if not clean_idea:
            raise ValueError("Blueprint 'idea' must be non-empty.")
        ws = self._ensure_workspace(workspace_id)
        ws["experience_mode"] = experience_mode

        short_title = clean_idea[:68] + ("..." if len(clean_idea) > 68 else "")
        prd = self.create_prd(
            title=f"Blueprint PRD: {short_title}",
            summary=f"Auto-synthesized product specification for: {clean_idea}",
            workspace_id=workspace_id,
            acceptance_criteria=[
                "Accessible responsive UI with guided validation states",
                "Typed API & SQLite/PostgreSQL persistence with RBAC",
                "Automated test & security verification before P-10 launch",
            ],
        )

        issue_templates = [
            (f"Design data schema & API contracts for {short_title}", "high", "code-architect"),
            (f"Build interactive frontend & guided forms for {short_title}", "high", "nocode-app-builder"),
            (f"Configure notification & approval workflow rules for {short_title}", "medium", "workflow-automator"),
            (f"Run security, accessibility & regression checks for {short_title}", "high", "qa-ci-runner"),
        ]
        created_issues = [
            self.create_issue(
                title=title,
                workspace_id=workspace_id,
                priority=prio,
                assignee_agent=agent_id,
                prd_id=prd["id"],
            )
            for title, prio, agent_id in issue_templates
        ]

        workflow = self.create_workflow(
            name=f"Automation Pipeline · {short_title[:42]}",
            trigger="event:submission.created",
            workspace_id=workspace_id,
            nodes=[
                {"id": "intake", "label": "Validate Input & RBAC", "agent": "nocode-app-builder"},
                {"id": "process", "label": "Execute Business Logic & Persist", "agent": "workflow-automator"},
                {"id": "audit", "label": "Append Hash-Chained Record Entry", "agent": "security-auditor"},
                {"id": "publish", "label": "Managed App Deploy (P-10 Gate)", "agent": "devops-sre"},
            ],
        )

        team_run = self.dispatch_agent_team(
            team_id="nocode-guided-launch-squad",
            objective=f"Build and stage managed deployment for: {clean_idea}",
            workspace_id=workspace_id,
            sensitive_mutation=True,
            requested_by=experience_mode,
        )

        return {
            "workspace_id": workspace_id,
            "experience_mode": experience_mode,
            "idea": clean_idea,
            "prd": prd,
            "sprint_issues": created_issues,
            "workflow": workflow,
            "team_run": team_run,
            "architecture_summary": {
                "target_stack": target_stack,
                "components": [
                    "Guided React 19 UI Surface",
                    "FastAPI Typed Domain Router",
                    "Durable Local-First SQLite / Postgres Store",
                    "KFlow Event & Approval DAG",
                ],
                "security_controls": ["RBAC Role Guard", "DLP Secret Redaction", "P-10 Human Deploy Approval"],
            },
        }


unified_workspace_hub = UnifiedWorkspaceHub()
