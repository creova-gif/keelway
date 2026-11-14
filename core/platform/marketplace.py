"""
Keelway Marketplace Registry & Pre-Publication Security Validator (`keelway.package/v1`).

Supports all 7 canonical package kinds across 1st-party Sorvex Labs, verified 3rd-party creators,
and enterprise partners, gated by deterministic pre-publication security validation against:
1. Prompt-injection & guardrail-bypass instructions
2. Dangerous execution / shell exfiltration hooks
3. Excessive or wildcard filesystem/network/credential permissions
4. Hardcoded live secrets and credentials
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import re
from typing import Any, Dict, List, Optional

from core.platform.persistence import SQLitePlatformStore
from core.platform.signing import (
    SORVEX_FIRST_PARTY_KEY_ID,
    Ed25519ManifestSigner,
    get_sorvex_first_party_keypair,
)
from core.platform.subscription import MARKETPLACE_SPLITS, subscription_policy_engine
from core.security.redact import redact_text


class PackageKind(str, Enum):
    AI_AGENT = "ai_agent"
    MULTI_AGENT_SYSTEM = "multi_agent_system"
    AGENT_SKILL = "agent_skill"
    PLUGIN_EXTENSION = "plugin_extension"
    AUTOMATION_TEMPLATE = "automation_template"
    DEV_TOOL = "dev_tool"
    INDUSTRY_ENTERPRISE_SOLUTION = "industry_enterprise_solution"


class MarketplaceSecurityError(ValueError):
    """Raised when a package or extension fails mandatory pre-publication security validation."""

    def __init__(self, report: Dict[str, Any]) -> None:
        self.report = report
        reasons = "; ".join(f["message"] for f in report.get("findings", []))
        super().__init__(f"Marketplace security validation failed: {reasons or 'policy violation'}")


_PROMPT_INJECTION_RULES = (
    ("ignore_previous_instructions", re.compile(r"(?i)\bignore\s+(?:all\s+)?previous\s+instructions\b")),
    ("disregard_system_prompt", re.compile(r"(?i)\bdisregard\s+(?:the\s+)?system\s+prompt\b")),
    ("bypass_p10", re.compile(r"(?i)\bbypass\s+p-?10\b")),
    ("disable_airgap", re.compile(r"(?i)\bdisable\s+air-?gap\b")),
    ("auto_approve_risk_c", re.compile(r"(?i)\bauto-?approve\s+risk\s*c\b")),
    ("exfiltrate_directive", re.compile(r"(?i)\bexfiltrat(?:e|ion)\b")),
)

_DANGEROUS_EXEC_RULES = (
    ("python_eval", re.compile(r"\beval\s*\(")),
    ("python_exec", re.compile(r"\bexec\s*\(")),
    ("os_system", re.compile(r"\bos\.system\s*\(")),
    ("subprocess_shell_true", re.compile(r"\bshell\s*=\s*True\b")),
    ("curl_pipe_shell", re.compile(r"(?i)\bcurl\b[^\n|]*\|\s*(?:sh|bash|zsh)\b")),
)

_HIGH_CONFIDENCE_SECRET_RULES = (
    ("openai_project_key", re.compile(r"\bsk-proj-[A-Za-z0-9_-]{10,}")),
    ("anthropic_api_key", re.compile(r"\bsk-ant-(?:api\d*-)?[A-Za-z0-9_-]{12,}")),
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("github_pat", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}")),
)


def _canonical_sha256(payload: Dict[str, Any]) -> str:
    body = {
        k: v
        for k, v in payload.items()
        if k not in {"manifest_sha256", "security_report", "security_verified", "ed25519_signature", "signer_key_id"}
    }
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _collect_strings(obj: Any, prefix: str = "") -> List[tuple[str, str]]:
    out: List[tuple[str, str]] = []
    if isinstance(obj, str):
        out.append((prefix or "root", obj))
    elif isinstance(obj, dict):
        for k, v in obj.items():
            if k in {"security_report", "manifest_sha256", "ed25519_signature", "signer_key_id"}:
                continue
            child = f"{prefix}.{k}" if prefix else str(k)
            out.extend(_collect_strings(v, child))
    elif isinstance(obj, (list, tuple)):
        for idx, item in enumerate(obj):
            out.extend(_collect_strings(item, f"{prefix}[{idx}]"))
    return out


class MarketplaceSecurityScanner:
    """Deterministic static & permission envelope validator for Marketplace packages and SDK extensions."""

    def scan_package(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        findings: List[Dict[str, str]] = []
        string_fields = _collect_strings(payload)

        for field_path, text in string_fields:
            for rule_id, rx in _PROMPT_INJECTION_RULES:
                if rx.search(text):
                    findings.append(
                        {
                            "category": "prompt_injection",
                            "rule_id": rule_id,
                            "severity": "critical",
                            "field": field_path,
                            "message": f"Blocked prompt-injection or guardrail-bypass phrase ({rule_id}) in '{field_path}'.",
                        }
                    )
            for rule_id, rx in _DANGEROUS_EXEC_RULES:
                if rx.search(text):
                    findings.append(
                        {
                            "category": "dangerous_execution",
                            "rule_id": rule_id,
                            "severity": "critical",
                            "field": field_path,
                            "message": f"Blocked unsafe dynamic/shell execution pattern ({rule_id}) in '{field_path}'.",
                        }
                    )
            for rule_id, rx in _HIGH_CONFIDENCE_SECRET_RULES:
                if rx.search(text):
                    findings.append(
                        {
                            "category": "hardcoded_secret",
                            "rule_id": rule_id,
                            "severity": "critical",
                            "field": field_path,
                            "message": f"Blocked embedded live credential pattern ({rule_id}) in '{field_path}'.",
                        }
                    )
            _, redact_count = redact_text(text)
            if redact_count > 0 and not any(
                f["category"] == "hardcoded_secret" and f["field"] == field_path for f in findings
            ):
                findings.append(
                    {
                        "category": "hardcoded_secret",
                        "rule_id": "dlp_redaction_hit",
                        "severity": "critical",
                        "field": field_path,
                        "message": f"DLP secret scanner detected {redact_count} embedded credential(s) in '{field_path}'.",
                    }
                )

        perms = payload.get("permissions") or {}
        if isinstance(perms, dict):
            write_paths = [str(p).strip() for p in (perms.get("write_paths") or [])]
            for wp in write_paths:
                if wp in {"/", "/**", "*"} or ".." in wp.split("/") or wp.startswith(".."):
                    findings.append(
                        {
                            "category": "unsafe_permissions",
                            "rule_id": "wildcard_or_traversal_write_path",
                            "severity": "high",
                            "field": "permissions.write_paths",
                            "message": f"Unsafe write_path '{wp}': root wildcard and '..' traversal are prohibited.",
                        }
                    )
            network_mode = str(perms.get("network", "none")).strip().lower()
            env_access = perms.get("env_access") or perms.get("credential_paths") or []
            requires_p10 = bool(perms.get("requires_p10_approval", False))
            if network_mode == "full" and env_access and not requires_p10:
                findings.append(
                    {
                        "category": "unsafe_permissions",
                        "rule_id": "unscoped_network_with_env_access",
                        "severity": "high",
                        "field": "permissions",
                        "message": "Full network access combined with env_access requires requires_p10_approval=True.",
                    }
                )

        passed = len(findings) == 0
        risk_grade = "A" if passed else ("C" if any(f["severity"] == "critical" for f in findings) else "B")
        return {
            "passed": passed,
            "risk_grade": risk_grade,
            "findings": findings,
            "findings_count": len(findings),
            "manifest_sha256": _canonical_sha256(payload),
            "scanned_at": datetime.now(timezone.utc).isoformat(),
        }


CURATED_SEED_PACKAGES: List[Dict[str, Any]] = [
    {
        "id": "keelway-pr-sentinel",
        "name": "Keelway PR Sentinel Agent",
        "kind": PackageKind.AI_AGENT.value,
        "version": "1.4.0",
        "publisher": "Sorvex Labs",
        "publisher_tier": "first_party",
        "pricing_model": "free",
        "price_usd": 0.0,
        "description": "Deterministic diff reviewer enforcing architecture boundaries, typing, and regression tests.",
        "permissions": {"read_paths": ["core/", "tests/"], "write_paths": [], "network": "none", "requires_p10_approval": False},
    },
    {
        "id": "keelway-release-swarm",
        "name": "Autonomous Release Gate Squad",
        "kind": PackageKind.MULTI_AGENT_SYSTEM.value,
        "version": "2.1.0",
        "publisher": "Sorvex Labs",
        "publisher_tier": "first_party",
        "pricing_model": "monthly",
        "price_usd": 29.0,
        "description": "Coordinated Architect + QA + Security Auditor swarm with mandatory P-10 deploy checkpoints.",
        "permissions": {"read_paths": ["./"], "write_paths": ["artifacts/"], "network": "scoped", "requires_p10_approval": True},
    },
    {
        "id": "sorvex-diataxis-writer",
        "name": "Diataxis Architecture Skill Pack",
        "kind": PackageKind.AGENT_SKILL.value,
        "version": "1.2.2",
        "publisher": "Sorvex Labs",
        "publisher_tier": "first_party",
        "pricing_model": "free",
        "price_usd": 0.0,
        "description": "Structured tutorials, how-to runbooks, API references, and ADR synthesis from live repositories.",
        "permissions": {"read_paths": ["core/", "docs/"], "write_paths": ["docs/"], "network": "none", "requires_p10_approval": False},
    },
    {
        "id": "linear-github-mcp-bridge",
        "name": "Linear & GitHub Bidirectional Bridge",
        "kind": PackageKind.PLUGIN_EXTENSION.value,
        "version": "1.3.1",
        "publisher": "Northstar DevTools",
        "publisher_tier": "verified_third_party",
        "pricing_model": "monthly",
        "price_usd": 15.0,
        "description": "Synchronizes Keelway PM sprint issues, PR status checks, and release milestones via scoped webhooks.",
        "permissions": {"read_paths": ["docs/"], "write_paths": [".keelway/sync/"], "network": "scoped", "requires_p10_approval": True},
    },
    {
        "id": "kflow-ci-healer-dag",
        "name": "Nightly Flake Triage & Patch DAG",
        "kind": PackageKind.AUTOMATION_TEMPLATE.value,
        "version": "1.1.0",
        "publisher": "BuildPulse Studio",
        "publisher_tier": "verified_third_party",
        "pricing_model": "one_time",
        "price_usd": 39.0,
        "description": "Durable KFlow workflow template that isolates failing pytest/vitest targets and proposes minimal diffs.",
        "permissions": {"read_paths": ["tests/", "src/"], "write_paths": [".keelway/patches/"], "network": "none", "requires_p10_approval": True},
    },
    {
        "id": "ast-boundary-profiler",
        "name": "Polyglot AST Dependency & Size Guard",
        "kind": PackageKind.DEV_TOOL.value,
        "version": "1.0.4",
        "publisher": "Lattice Static Analysis",
        "publisher_tier": "verified_third_party",
        "pricing_model": "free",
        "price_usd": 0.0,
        "description": "Zero-egress static analyzer enforcing module import layering and file-size ratchets.",
        "permissions": {"read_paths": ["./"], "write_paths": [], "network": "none", "requires_p10_approval": False},
    },
    {
        "id": "finreg-sovereign-compliance",
        "name": "FinReg SOC2 / PCI Sovereign Control Suite",
        "kind": PackageKind.INDUSTRY_ENTERPRISE_SOLUTION.value,
        "version": "3.0.0",
        "publisher": "Aegis Regulated Systems",
        "publisher_tier": "enterprise_partner",
        "pricing_model": "enterprise",
        "price_usd": 499.0,
        "description": "Air-gapped financial compliance pack with dual-human quorum policies and hash-chained evidence export.",
        "permissions": {"read_paths": ["core/", "audit/"], "write_paths": ["exports/"], "network": "none", "requires_p10_approval": True},
    },
    {
        "id": "hipaa-clinical-intake-pack",
        "name": "Clinical Operations & PHI Guardrail System",
        "kind": PackageKind.INDUSTRY_ENTERPRISE_SOLUTION.value,
        "version": "2.2.0",
        "publisher": "Veridian Health Partners",
        "publisher_tier": "enterprise_partner",
        "pricing_model": "enterprise",
        "price_usd": 399.0,
        "description": "Healthcare workflow automation with local-only PHI redaction and audit-locked retention policies.",
        "permissions": {"read_paths": ["workflows/"], "write_paths": ["audit_bundles/"], "network": "none", "requires_p10_approval": True},
    },
    {
        "id": "nocode-crud-launchpad",
        "name": "Guided Internal Tool Scaffold Skill",
        "kind": PackageKind.AGENT_SKILL.value,
        "version": "1.5.0",
        "publisher": "CraftWorks AI",
        "publisher_tier": "verified_third_party",
        "pricing_model": "one_time",
        "price_usd": 25.0,
        "description": "Turns plain-language business forms and approval tables into accessible React + FastAPI apps.",
        "permissions": {"read_paths": ["templates/"], "write_paths": ["app_scaffold/"], "network": "none", "requires_p10_approval": False},
    },
]


class MarketplaceRegistry:
    """Manages curated and newly published `keelway.package/v1` listings and workspace installations."""

    def __init__(
        self,
        scanner: Optional[MarketplaceSecurityScanner] = None,
        store: Optional[SQLitePlatformStore] = None,
        signer: Optional[Ed25519ManifestSigner] = None,
    ) -> None:
        self.scanner = scanner or MarketplaceSecurityScanner()
        self.store = store
        self.signer = signer or Ed25519ManifestSigner()
        self._packages: Dict[str, Dict[str, Any]] = {}
        self._installed_by_workspace: Dict[str, Dict[str, Dict[str, Any]]] = {}

        if self.store is not None:
            for persisted_pkg in self.store.list_packages():
                pkg_id = str(persisted_pkg.get("id") or "").strip()
                if pkg_id:
                    self._packages[pkg_id] = dict(persisted_pkg)

        for seed in CURATED_SEED_PACKAGES:
            if seed["id"] not in self._packages:
                self.publish_package(seed)

        if self.store is not None:
            for row in self.store.list_all_installs():
                pkg = self._packages.get(row["package_id"])
                if pkg is None:
                    continue
                ws_map = self._installed_by_workspace.setdefault(row["workspace_id"], {})
                ws_map[row["package_id"]] = {
                    "installed": True,
                    "package_id": row["package_id"],
                    "workspace_id": row["workspace_id"],
                    "name": pkg["name"],
                    "kind": pkg["kind"],
                    "version": pkg["version"],
                    "manifest_sha256": pkg["manifest_sha256"],
                    "config": dict(row.get("config") or {}),
                    "installed_at": row["installed_at"],
                }

    def publish_package(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        pkg_id = str(payload.get("id") or "").strip()
        if not pkg_id:
            raise ValueError("Package 'id' is required.")
        kind_val = str(payload.get("kind") or PackageKind.AGENT_SKILL.value).strip()
        if kind_val not in {k.value for k in PackageKind}:
            raise ValueError(f"Unsupported package kind '{kind_val}'.")

        publisher_tier = str(payload.get("publisher_tier") or "verified_third_party").strip().lower()
        if publisher_tier not in MARKETPLACE_SPLITS:
            raise ValueError(f"Unsupported publisher_tier '{publisher_tier}'.")

        if payload.get("ed25519_signature") or payload.get("signer_key_id"):
            sig_ok, sig_reason = self.signer.verify_manifest(payload)
            if not sig_ok:
                raise MarketplaceSecurityError(
                    {
                        "passed": False,
                        "risk_grade": "C",
                        "findings": [
                            {
                                "category": "invalid_signature",
                                "rule_id": sig_reason.lower(),
                                "severity": "critical",
                                "field": "ed25519_signature",
                                "message": f"Ed25519 manifest signature verification failed: {sig_reason}.",
                            }
                        ],
                        "findings_count": 1,
                        "manifest_sha256": _canonical_sha256(payload),
                        "scanned_at": datetime.now(timezone.utc).isoformat(),
                    }
                )

        report = self.scanner.scan_package(payload)
        if not report["passed"]:
            raise MarketplaceSecurityError(report)

        price_usd = float(payload.get("price_usd", 0.0) or 0.0)
        split = subscription_policy_engine.calculate_marketplace_split(publisher_tier, price_usd)

        record: Dict[str, Any] = {
            "schema": "keelway.package/v1",
            "id": pkg_id,
            "name": str(payload.get("name") or pkg_id),
            "kind": kind_val,
            "version": str(payload.get("version") or "1.0.0"),
            "publisher": str(payload.get("publisher") or "Community Publisher"),
            "publisher_tier": publisher_tier,
            "pricing_model": str(payload.get("pricing_model") or ("free" if price_usd == 0 else "monthly")),
            "price_usd": price_usd,
            "description": str(payload.get("description") or ""),
            "permissions": dict(payload.get("permissions") or {"read_paths": [], "write_paths": [], "network": "none"}),
            "revenue_split": split,
            "manifest_sha256": report["manifest_sha256"],
            "security_verified": True,
            "security_report": report,
        }

        if payload.get("license_spdx") or payload.get("license"):
            record["license_spdx"] = str(payload.get("license_spdx") or payload.get("license"))

        if payload.get("ed25519_signature") and payload.get("signer_key_id"):
            record["signer_key_id"] = str(payload["signer_key_id"])
            record["ed25519_signature"] = str(payload["ed25519_signature"])
        elif publisher_tier == "first_party":
            sorvex_pem, _ = get_sorvex_first_party_keypair()
            record = self.signer.sign_manifest(record, sorvex_pem, SORVEX_FIRST_PARTY_KEY_ID)

        self._packages[pkg_id] = record
        if self.store is not None:
            self.store.upsert_package(pkg_id, kind_val, record)
        return dict(record)

    def list_packages(
        self,
        kind: Optional[str] = None,
        query: Optional[str] = None,
        publisher_tier: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        results = list(self._packages.values())
        if kind:
            results = [p for p in results if p["kind"] == kind]
        if publisher_tier:
            results = [p for p in results if p["publisher_tier"] == publisher_tier]
        if query:
            q = query.strip().lower()
            results = [
                p
                for p in results
                if q in p["name"].lower() or q in p["description"].lower() or q in p["id"].lower()
            ]
        return [dict(p) for p in results]

    def get_package(self, package_id: str) -> Optional[Dict[str, Any]]:
        pkg = self._packages.get(package_id)
        return dict(pkg) if pkg else None

    def install_package(
        self,
        package_id: str,
        workspace_id: str = "default",
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        pkg = self._packages.get(package_id)
        if pkg is None:
            raise KeyError(f"Marketplace package '{package_id}' not found.")
        ws_map = self._installed_by_workspace.setdefault(workspace_id, {})
        installed_at = datetime.now(timezone.utc).isoformat()
        clean_cfg = dict(config or {})
        entry = {
            "installed": True,
            "package_id": package_id,
            "workspace_id": workspace_id,
            "name": pkg["name"],
            "kind": pkg["kind"],
            "version": pkg["version"],
            "manifest_sha256": pkg["manifest_sha256"],
            "config": clean_cfg,
            "installed_at": installed_at,
        }
        ws_map[package_id] = entry
        if self.store is not None:
            self.store.upsert_install(
                workspace_id=workspace_id,
                package_id=package_id,
                config=clean_cfg,
                installed_at=installed_at,
            )
        return dict(entry)

    def uninstall_package(self, package_id: str, workspace_id: str = "default") -> Dict[str, Any]:
        ws_map = self._installed_by_workspace.get(workspace_id, {})
        existed = package_id in ws_map
        ws_map.pop(package_id, None)
        if self.store is not None:
            self.store.remove_install(workspace_id=workspace_id, package_id=package_id)
        return {"uninstalled": existed, "package_id": package_id, "workspace_id": workspace_id}

    def list_installed(self, workspace_id: str = "default") -> List[Dict[str, Any]]:
        return [dict(v) for v in self._installed_by_workspace.get(workspace_id, {}).values()]


marketplace_registry = MarketplaceRegistry()
