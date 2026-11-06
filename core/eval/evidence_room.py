"""
Keelway Investor & Enterprise Evidence Room Pipeline (WP21).
Assembles cryptographically sealed, 100% reproducible verification packages
linking Git commits, benchmark receipts, flight tapes, SBOM provenance, and test results.
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import hashlib
import json
import os
import subprocess
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def _run_coroutine_safely(coro):
    """Executes a coroutine safely whether or not an event loop is already running."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
    else:
        return asyncio.run(coro)


@dataclass
class EvidenceMetric:
    name: str
    category: str  # "tests" | "benchmark" | "security" | "architecture" | "compliance"
    claim: str
    observed_value: Any
    is_verified: bool
    evidence_path_or_receipt: str
    reproduce_command: str


@dataclass
class EvidenceRoomPackage:
    package_id: str
    commit_sha: str
    git_branch: str
    timestamp_utc: str
    summary: Dict[str, Any]
    metrics: List[Dict[str, Any]]
    reproducibility_guide: Dict[str, str]
    package_sha256: str = ""

    def calculate_sha256(self) -> str:
        payload = {
            "package_id": self.package_id,
            "commit_sha": self.commit_sha,
            "git_branch": self.git_branch,
            "timestamp_utc": self.timestamp_utc,
            "summary": self.summary,
            "metrics": self.metrics,
            "reproducibility_guide": self.reproducibility_guide,
        }
        canonical_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(canonical_bytes).hexdigest()

    def seal(self) -> None:
        self.package_sha256 = self.calculate_sha256()

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        if not data.get("package_sha256"):
            data["package_sha256"] = self.calculate_sha256()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> EvidenceRoomPackage:
        return cls(
            package_id=data["package_id"],
            commit_sha=data["commit_sha"],
            git_branch=data["git_branch"],
            timestamp_utc=data["timestamp_utc"],
            summary=data["summary"],
            metrics=data["metrics"],
            reproducibility_guide=data["reproducibility_guide"],
            package_sha256=data.get("package_sha256", ""),
        )


class EvidenceRoomPipeline:
    """Gathers receipts that this process actually produced and seals them.

    A metric is verified only when this call recorded an attributable result.
    Checks that were not executed stay ``not_run`` and unverified. This
    assembler does not invent a pass count for them.
    """

    @staticmethod
    def _not_run_metric(
        *,
        name: str,
        category: str,
        subject: str,
        evidence_path_or_receipt: str,
        reproduce_command: str,
    ) -> EvidenceMetric:
        return EvidenceMetric(
            name=name,
            category=category,
            claim=f"Not run. No result is claimed for {subject}.",
            observed_value={"status": "not_run", "passed": None, "failed": None, "count": None},
            is_verified=False,
            evidence_path_or_receipt=evidence_path_or_receipt,
            reproduce_command=reproduce_command,
        )

    @staticmethod
    def _check_failed_metric(
        *,
        name: str,
        category: str,
        evidence_path_or_receipt: str,
        reproduce_command: str,
    ) -> EvidenceMetric:
        return EvidenceMetric(
            name=name,
            category=category,
            claim="The check did not finish. No result is claimed.",
            observed_value={"status": "error", "passed": None, "failed": None, "count": None},
            is_verified=False,
            evidence_path_or_receipt=evidence_path_or_receipt,
            reproduce_command=reproduce_command,
        )

    @classmethod
    def _golden_panel_metric(cls) -> EvidenceMetric:
        name = "10-Task Golden Evaluation Panel"
        category = "benchmark"
        evidence = "evals/eval_runner.py"
        command = "python3 cli.py bench --receipt"
        try:
            from evals.eval_runner import ProductionEvalHarness

            bench_res = _run_coroutine_safely(ProductionEvalHarness().run_all())
        except Exception:
            return cls._check_failed_metric(
                name=name,
                category=category,
                evidence_path_or_receipt=evidence,
                reproduce_command=command,
            )
        if not isinstance(bench_res, dict):
            return cls._check_failed_metric(
                name=name,
                category=category,
                evidence_path_or_receipt=evidence,
                reproduce_command=command,
            )
        passed_tasks = bench_res.get("passed_tasks")
        total_tasks = bench_res.get("total_tasks")
        attributable = (
            isinstance(passed_tasks, int)
            and isinstance(total_tasks, int)
            and not isinstance(passed_tasks, bool)
            and not isinstance(total_tasks, bool)
            and total_tasks > 0
            and 0 <= passed_tasks <= total_tasks
        )
        if not attributable:
            return cls._check_failed_metric(
                name=name,
                category=category,
                evidence_path_or_receipt=evidence,
                reproduce_command=command,
            )
        tasks = bench_res.get("tasks") if isinstance(bench_res.get("tasks"), list) else []
        task_ids = [
            item.get("task_id")
            for item in tasks
            if isinstance(item, dict) and isinstance(item.get("task_id"), str)
        ]
        observed: Dict[str, Any] = {
            "status": "executed",
            "passed_tasks": passed_tasks,
            "total_tasks": total_tasks,
            "task_ids": task_ids,
            "provenance": "in_process_harness",
            "fixture_task_ids": [task_id for task_id in task_ids if task_id == "EVAL-08"],
            "certification": "not_independent",
        }
        if isinstance(bench_res.get("pass_rate_pct"), (int, float)) and not isinstance(bench_res.get("pass_rate_pct"), bool):
            observed["pass_rate_pct"] = bench_res["pass_rate_pct"]
        if isinstance(bench_res.get("total_duration_ms"), (int, float)) and not isinstance(bench_res.get("total_duration_ms"), bool):
            observed["duration_ms"] = bench_res["total_duration_ms"]
        return EvidenceMetric(
            name=name,
            category=category,
            claim=(
                f"In-process golden panel finished with {passed_tasks} of {total_tasks} tasks passed. "
                "EVAL-08 uses stub generators. The count is this run's harness result, "
                "not independently verified model performance."
            ),
            observed_value=observed,
            is_verified=False,
            evidence_path_or_receipt=evidence,
            reproduce_command=command,
        )

    @classmethod
    def _airgap_metric(cls) -> EvidenceMetric:
        name = "NIST SP 800-53 SC-7 Air-Gap Audit"
        evidence = "core/security/airgap_auditor.py"
        command = "python3 cli.py airgap audit"
        try:
            from core.security.airgap_auditor import AirGapAuditor

            report = AirGapAuditor.audit_environment()
            checks = list(getattr(report, "checks", []) or [])
            compliant = bool(getattr(report, "overall_compliant", False))
        except Exception:
            return cls._check_failed_metric(
                name=name,
                category="compliance",
                evidence_path_or_receipt=evidence,
                reproduce_command=command,
            )
        return EvidenceMetric(
            name=name,
            category="compliance",
            claim=(
                f"In-process air-gap audit reported overall_compliant={compliant} "
                f"across {len(checks)} checks. EvidenceRoom does not re-certify those checks."
            ),
            observed_value={
                "status": "executed",
                "overall_compliant": compliant,
                "checks_count": len(checks),
            },
            is_verified=False,
            evidence_path_or_receipt=evidence,
            reproduce_command=command,
        )

    @classmethod
    def _sbom_metric(cls, repo_root: Path) -> EvidenceMetric:
        name = "CycloneDX SBOM & Provenance"
        evidence = "core/security/sbom.py"
        command = "python3 cli.py sbom verify"
        try:
            from core.security.sbom import SBOMGenerator

            sbom = SBOMGenerator.generate(repo_root=repo_root)
            component_count = len(sbom.components)
            signature_present = bool(sbom.provenance_signature)
            bom_format = sbom.bom_format
        except Exception:
            return cls._check_failed_metric(
                name=name,
                category="security",
                evidence_path_or_receipt=evidence,
                reproduce_command=command,
            )
        return EvidenceMetric(
            name=name,
            category="security",
            claim=(
                "An in-process SBOM document was generated. "
                "A signature field on that document is not independent release verification."
            ),
            observed_value={
                "status": "executed",
                "components": component_count,
                "signature_present": signature_present,
                "format": bom_format,
            },
            is_verified=False,
            evidence_path_or_receipt=evidence,
            reproduce_command=command,
        )

    @classmethod
    def _entitlement_metric(cls) -> EvidenceMetric:
        name = "Offline Entitlement Gating"
        evidence = "core/billing/entitlements.py"
        command = "python3 cli.py entitlements status"
        try:
            from core.billing.entitlements import get_shared_entitlement_manager

            manager = get_shared_entitlement_manager()
            stored = "default-org" in getattr(manager, "active_certificates", {})
            cert = manager.get_certificate("default-org")
            valid, status = cert.is_valid()
            tier = cert.tier.value
            seats = cert.seats
        except Exception:
            return cls._check_failed_metric(
                name=name,
                category="security",
                evidence_path_or_receipt=evidence,
                reproduce_command=command,
            )
        provenance = "stored" if stored else "in_process_fallback"
        if stored:
            claim = (
                f"A stored certificate was signature-checked locally ({status}). "
                "Local signature validation is not independent issuance."
            )
        else:
            claim = (
                "No stored entitlement certificate for default-org. "
                f"The in-process community fallback was signature-checked locally ({status}) "
                "and is not registered or independently issued evidence."
            )
        return EvidenceMetric(
            name=name,
            category="security",
            claim=claim,
            observed_value={
                "status": "executed",
                "provenance": provenance,
                "signature_valid": bool(valid),
                "certificate_status": status,
                "tier": tier,
                "seats": seats,
                "independently_issued": False,
            },
            is_verified=False,
            evidence_path_or_receipt=evidence,
            reproduce_command=command,
        )

    @classmethod
    def _get_git_info(cls, repo_root: Path) -> Tuple[str, str]:
        commit_sha = "unknown"
        branch = "main"
        try:
            p_sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(repo_root), capture_output=True, text=True, check=False)
            if p_sha.returncode == 0 and p_sha.stdout.strip():
                commit_sha = p_sha.stdout.strip()
            p_br = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=str(repo_root), capture_output=True, text=True, check=False)
            if p_br.returncode == 0 and p_br.stdout.strip():
                branch = p_br.stdout.strip()
        except Exception:
            pass
        return commit_sha, branch

    @classmethod
    def assemble_package(cls, repo_root: Optional[Path] = None) -> EvidenceRoomPackage:
        root = Path(repo_root or ".").resolve()
        commit_sha, branch = cls._get_git_info(root)
        now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        package_id = f"evd_{commit_sha[:10]}_{int(time.time())}"

        metrics: List[EvidenceMetric] = []

        # Checks that this call does not execute stay explicitly not-run.
        # No pass count is substituted for a run that did not happen.
        metrics.append(cls._not_run_metric(
            name="Automated Pytest Suite",
            category="tests",
            subject="the automated pytest suite",
            evidence_path_or_receipt="tests/",
            reproduce_command="pytest tests -q",
        ))
        metrics.append(cls._golden_panel_metric())
        metrics.append(cls._not_run_metric(
            name="Standalone Reference Core Engine",
            category="architecture",
            subject="the standalone reference core engine tests",
            evidence_path_or_receipt="keelway_core/",
            reproduce_command="pytest tests/test_keelway_core_engine.py tests/test_keelway_core_cli.py -q",
        ))
        metrics.append(cls._not_run_metric(
            name="Milestone M1 Developer Workflow",
            category="tests",
            subject="the milestone M1 developer workflow",
            evidence_path_or_receipt=".keelway/recordings/",
            reproduce_command="python3 cli.py m1",
        ))
        metrics.append(cls._airgap_metric())
        metrics.append(cls._sbom_metric(root))
        metrics.append(cls._entitlement_metric())
        metrics.append(cls._not_run_metric(
            name="Tier 2 Hardware Security HAL",
            category="security",
            subject="tier 2 hardware security checks",
            evidence_path_or_receipt="keelway/hal/",
            reproduce_command="python3 cli.py tier2 verify",
        ))
        metrics.append(cls._not_run_metric(
            name="Sovereign Pre-Flight System Doctor",
            category="architecture",
            subject="the pre-flight system doctor",
            evidence_path_or_receipt="core/system/doctor.py",
            reproduce_command="python3 cli.py doctor",
        ))
        metrics.append(cls._not_run_metric(
            name="Cross-Machine Sovereign Sync Engine",
            category="architecture",
            subject="the cross-machine sync engine",
            evidence_path_or_receipt="core/sync/engine.py",
            reproduce_command="python3 cli.py sync demo",
        ))

        reproducibility = {
            "full_tests": "PYTHONPATH=. pytest tests -q",
            "golden_bench": "python3 cli.py bench --receipt",
            "m1_slice": "python3 cli.py m1",
            "ref_core": "python3 scripts/reference_e2e_demo.py",
            "airgap_audit": "python3 cli.py airgap audit",
            "sbom_verify": "python3 cli.py sbom verify",
            "tier2_verify": "python3 cli.py tier2 verify",
            "system_doctor": "python3 cli.py doctor",
            "sync_demo": "python3 cli.py sync demo",
            "receipt_verify": "python3 cli.py receipt verify .keelway/evals/receipts/*.receipt.json",
        }

        verified_count = sum(1 for metric in metrics if metric.is_verified)
        not_run_count = sum(
            1 for metric in metrics if isinstance(metric.observed_value, dict) and metric.observed_value.get("status") == "not_run"
        )
        summary = {
            "product": "Keelway by Sorvex Labs",
            "open_core_runtime": "Kora AI Core by Kora Technologies",
            "commit_sha": commit_sha,
            "git_branch": branch,
            "total_metrics": len(metrics),
            "total_verified_metrics": verified_count,
            "not_run_metrics": not_run_count,
            "all_verified": bool(metrics) and verified_count == len(metrics),
            "simulated_metrics": False,
            "audited_by": "Keelway in-process evidence assembler",
        }

        pkg = EvidenceRoomPackage(
            package_id=package_id,
            commit_sha=commit_sha,
            git_branch=branch,
            timestamp_utc=now_iso,
            summary=summary,
            metrics=[asdict(m) for m in metrics],
            reproducibility_guide=reproducibility,
        )
        pkg.seal()
        return pkg

    @classmethod
    def verify_package(cls, data: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
        pkg = EvidenceRoomPackage.from_dict(data)
        calc = pkg.calculate_sha256()
        if calc != pkg.package_sha256:
            return False, "EVIDENCE_PACKAGE_TAMPERED", {"calculated": calc, "claimed": pkg.package_sha256}
        return True, "VERIFIED", {
            "package_id": pkg.package_id,
            "commit_sha": pkg.commit_sha,
            "metrics_count": len(pkg.metrics),
            "timestamp_utc": pkg.timestamp_utc,
        }
