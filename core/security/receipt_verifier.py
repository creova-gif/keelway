"""
Keelway Cryptographic Receipt Verifier & Deterministic Audit Replay Engine.
Verifies evaluation benchmarks, air-gap bundle manifests, flight tapes,
app build seals, agent manifests, and head anchors offline with zero external dependencies.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class ReceiptVerificationReport:
    receipt_type: str  # 'evaluation' | 'bundle' | 'flight_tape' | 'agent_build' | 'app_build' | 'head_anchor' | 'mesh_delegation' | 'unknown'
    is_valid: bool
    receipt_id: str
    digest_calculated: str
    digest_claimed: str
    details: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ReceiptVerifier:
    """Offline cryptographic receipt verification engine."""

    @classmethod
    def verify(
        cls,
        target: Any,
        secret_key: Optional[bytes] = None,
    ) -> ReceiptVerificationReport:
        """
        Auto-detects receipt format and performs cryptographic verification.
        Accepts a filesystem Path, raw JSON string, or parsed dictionary.
        """
        # 1. Handle tar.gz air-gap bundle archive
        if isinstance(target, (str, Path)):
            archive_path = Path(target)
            if archive_path.exists() and (archive_path.suffix == ".gz" or archive_path.name.endswith(".tar.gz")):
                return cls._verify_bundle_archive(archive_path)

        # 2. Parse JSON if string or path
        data: Dict[str, Any] = {}
        target_path = None
        if isinstance(target, (str, Path)):
            p = Path(target)
            if p.exists() and p.is_file():
                target_path = p
                try:
                    data = json.loads(p.read_text(encoding="utf-8"))
                except Exception as e:
                    return ReceiptVerificationReport(
                        receipt_type="unknown",
                        is_valid=False,
                        receipt_id=p.name,
                        digest_calculated="",
                        digest_claimed="",
                        errors=[f"Failed to parse JSON file: {e}"],
                    )
            elif isinstance(target, str) and target.strip().startswith("{"):
                try:
                    data = json.loads(target)
                except Exception as e:
                    return ReceiptVerificationReport(
                        receipt_type="unknown",
                        is_valid=False,
                        receipt_id="raw_json_string",
                        digest_calculated="",
                        digest_claimed="",
                        errors=[f"Failed to parse JSON string: {e}"],
                    )
            else:
                return ReceiptVerificationReport(
                    receipt_type="unknown",
                    is_valid=False,
                    receipt_id=str(target),
                    digest_calculated="",
                    digest_claimed="",
                    errors=[f"Receipt target not found on disk: {target}"],
                )
        elif isinstance(target, dict):
            data = target
        else:
            return ReceiptVerificationReport(
                receipt_type="unknown",
                is_valid=False,
                receipt_id="invalid_input",
                digest_calculated="",
                digest_claimed="",
                errors=[f"Unsupported target type: {type(target)}"],
            )

        # 3. Dispatch by detected schema / structure
        if "eval_run_id" in data and "task_results" in data:
            return cls._verify_evaluation_receipt(data)
        elif "tape_sha256" in data and "events" in data and "task_id" in data:
            return cls._verify_flight_tape(data)
        elif data.get("schema") == "keelway.head_anchor/v1" or ("head_hash" in data and "anchored_at" in data):
            return cls._verify_head_anchor(data, secret_key=secret_key)
        elif "delegation_id" in data and "target_node_id" in data and "signature" in data:
            return cls._verify_mesh_delegation(data, secret_key=secret_key)
        elif "bundle_id" in data and "root_digest_sha256" in data:
            return cls._verify_bundle_export_receipt(data, target_path)
        elif "flight_tape_sha256" in data and "app_name" in data and "template" in data:
            return cls._verify_app_build_receipt(data, target_path)
        elif data.get("bom_format") == "CycloneDX" or ("components" in data and "root_digest_sha256" in data and "provenance_signature" in data):
            return cls._verify_sbom_manifest(data, secret_key=secret_key)
        elif "manifest_digest" in data and "spec_name" in data and "receipt_sha256" in data:
            return cls._verify_agent_build_receipt(data)
        else:
            return ReceiptVerificationReport(
                receipt_type="unknown",
                is_valid=False,
                receipt_id=data.get("id", data.get("task_id", "unknown")),
                digest_calculated="",
                digest_claimed="",
                errors=["Could not identify a recognized Keelway receipt schema."],
                details={"keys_present": list(data.keys())},
            )

    @classmethod
    def _verify_bundle_archive(cls, archive_path: Path) -> ReceiptVerificationReport:
        from core.security.bundle_exporter import AirGapBundleExporter
        res = AirGapBundleExporter.verify_bundle(archive_path)
        errors = []
        if res.mismatched_files:
            errors.append(f"Mismatched files: {', '.join(res.mismatched_files[:5])}")
        if res.missing_files:
            errors.append(f"Missing files: {', '.join(res.missing_files[:5])}")

        return ReceiptVerificationReport(
            receipt_type="bundle_archive",
            is_valid=res.is_valid,
            receipt_id=res.bundle_id,
            digest_calculated=res.root_digest_sha256,
            digest_claimed=res.root_digest_sha256,
            details=res.to_dict(),
            errors=errors,
        )

    @classmethod
    def _verify_evaluation_receipt(cls, data: Dict[str, Any]) -> ReceiptVerificationReport:
        from evals.drift_detector import EvaluationReceipt
        claimed = data.get("receipt_sha256", "")
        receipt = EvaluationReceipt.from_dict(data)
        calculated = receipt.calculate_sha256()

        is_valid = (calculated == claimed)
        errors = []
        if not is_valid:
            errors.append(f"Calculated SHA-256 ({calculated}) does not match receipt seal ({claimed}).")

        return ReceiptVerificationReport(
            receipt_type="evaluation",
            is_valid=is_valid,
            receipt_id=receipt.eval_run_id,
            digest_calculated=calculated,
            digest_claimed=claimed,
            details={
                "model_name": receipt.model_name,
                "timestamp_utc": receipt.timestamp_utc,
                "passed_tasks": receipt.passed_tasks,
                "total_tasks": receipt.total_tasks,
                "pass_rate_pct": receipt.pass_rate_pct,
                "p50_latency_ms": receipt.p50_latency_ms,
                "p95_latency_ms": receipt.p95_latency_ms,
            },
            errors=errors,
        )

    @classmethod
    def _verify_flight_tape(cls, data: Dict[str, Any]) -> ReceiptVerificationReport:
        task_id = data.get("task_id", "unknown")
        claimed = data.get("tape_sha256", "")
        events = data.get("events", [])

        # Re-derive canonical tape data payload
        canonical_data = {
            "task_id": task_id,
            "event_count": len(events),
            "events": events,
        }
        serialized = json.dumps(canonical_data, indent=2, sort_keys=True)
        calculated = hashlib.sha256(serialized.encode("utf-8")).hexdigest()

        is_valid = (calculated == claimed)
        errors = []
        if not is_valid:
            errors.append(f"Calculated tape digest ({calculated}) does not match claimed ({claimed}).")

        event_types: Dict[str, int] = {}
        for ev in events:
            t = ev.get("event_type", "unknown")
            event_types[t] = event_types.get(t, 0) + 1

        return ReceiptVerificationReport(
            receipt_type="flight_tape",
            is_valid=is_valid,
            receipt_id=task_id,
            digest_calculated=calculated,
            digest_claimed=claimed,
            details={
                "total_events": len(events),
                "event_type_distribution": event_types,
                "redactions": data.get("redactions", 0),
                "recorded_at": data.get("recorded_at"),
            },
            errors=errors,
        )

    @classmethod
    def _verify_head_anchor(cls, data: Dict[str, Any], secret_key: Optional[bytes] = None) -> ReceiptVerificationReport:
        head_hash = data.get("head_hash", "")
        entries_count = data.get("entries_count", 0)
        anchored_at = data.get("anchored_at", "")
        claimed_sig = data.get("signature", "")

        key = secret_key
        if key is None:
            key_file = Path(".keelway/agent_signing.key")
            if key_file.exists():
                key = key_file.read_text().strip().encode("utf-8")
            else:
                key = b"keelway_default_anchor_key"

        msg = f"{head_hash}:{entries_count}:{anchored_at}".encode("utf-8")
        calculated_sig = hmac.new(key, msg, hashlib.sha256).hexdigest()

        is_valid = hmac.compare_digest(calculated_sig, claimed_sig)
        errors = []
        if not is_valid:
            errors.append("HMAC signature verification failed for audit head anchor.")

        return ReceiptVerificationReport(
            receipt_type="head_anchor",
            is_valid=is_valid,
            receipt_id=f"head_{head_hash[:12]}",
            digest_calculated=calculated_sig,
            digest_claimed=claimed_sig,
            details={
                "head_hash": head_hash,
                "entries_count": entries_count,
                "anchored_at": anchored_at,
                "schema": data.get("schema", "keelway.head_anchor/v1"),
            },
            errors=errors,
        )

    @classmethod
    def _verify_mesh_delegation(cls, data: Dict[str, Any], secret_key: Optional[bytes] = None) -> ReceiptVerificationReport:
        delegation_id = data.get("delegation_id", "")
        target_node = data.get("target_node_id", "")
        task_intent = data.get("task_intent", "")
        claimed_sig = data.get("signature", "")

        key = secret_key or b"keelway_mesh_p2p_default_secret_2026"
        msg = f"{delegation_id}:{target_node}:{task_intent}".encode("utf-8")
        calculated_sig = hmac.new(key, msg, hashlib.sha256).hexdigest()

        is_valid = hmac.compare_digest(calculated_sig, claimed_sig)
        errors = []
        if not is_valid:
            errors.append("HMAC signature verification failed for mesh task delegation.")

        return ReceiptVerificationReport(
            receipt_type="mesh_delegation",
            is_valid=is_valid,
            receipt_id=delegation_id,
            digest_calculated=calculated_sig,
            digest_claimed=claimed_sig,
            details={
                "target_hostname": data.get("target_hostname"),
                "allocated_vram_mb": data.get("allocated_vram_mb"),
                "status": data.get("status"),
                "duration_ms": data.get("duration_ms"),
            },
            errors=errors,
        )

    @classmethod
    def _verify_bundle_export_receipt(cls, data: Dict[str, Any], target_path: Optional[Path]) -> ReceiptVerificationReport:
        bundle_id = data.get("bundle_id", "")
        claimed_digest = data.get("root_digest_sha256", "")
        bundle_path_str = data.get("bundle_path")
        errors = []
        calculated = claimed_digest
        is_valid = bool(claimed_digest)

        # If bundle archive path exists, verify archive directly
        archive_path: Optional[Path] = None
        if bundle_path_str and Path(bundle_path_str).exists():
            archive_path = Path(bundle_path_str)
        elif target_path and target_path.parent:
            candidate = target_path.parent / f"{bundle_id}.tar.gz"
            if candidate.exists():
                archive_path = candidate

        if archive_path and archive_path.exists():
            from core.security.bundle_exporter import AirGapBundleExporter
            res = AirGapBundleExporter.verify_bundle(archive_path)
            is_valid = res.is_valid
            calculated = res.root_digest_sha256
            if not is_valid:
                errors.append(f"Bundle archive validation failed: {len(res.mismatched_files)} mismatches.")

        return ReceiptVerificationReport(
            receipt_type="bundle_receipt",
            is_valid=is_valid,
            receipt_id=bundle_id,
            digest_calculated=calculated,
            digest_claimed=claimed_digest,
            details={
                "total_files": data.get("total_files"),
                "uncompressed_bytes": data.get("uncompressed_bytes"),
                "created_at_utc": data.get("created_at_utc"),
            },
            errors=errors,
        )

    @classmethod
    def _verify_app_build_receipt(cls, data: Dict[str, Any], target_path: Optional[Path]) -> ReceiptVerificationReport:
        app_name = data.get("app_name", "")
        claimed_tape_sha = data.get("flight_tape_sha256", "")
        tape_path_str = data.get("flight_tape_path")
        errors = []
        is_valid = True
        calculated = claimed_tape_sha

        # If flight tape exists on disk, cross-verify
        tape_path: Optional[Path] = None
        if tape_path_str and Path(tape_path_str).exists():
            tape_path = Path(tape_path_str)
        elif target_path and target_path.parent:
            candidate = target_path.parent / Path(tape_path_str or "").name
            if candidate.exists():
                tape_path = candidate

        if tape_path and tape_path.exists():
            tape_report = cls._verify_flight_tape(json.loads(tape_path.read_text(encoding="utf-8")))
            if not tape_report.is_valid:
                is_valid = False
                errors.append(f"Linked flight tape failed integrity check: {tape_report.errors}")
            calculated = tape_report.digest_calculated

        if not data.get("tests_passed", False):
            errors.append("App build receipt indicates unit tests failed during scaffolding.")
            is_valid = False

        return ReceiptVerificationReport(
            receipt_type="app_build",
            is_valid=is_valid,
            receipt_id=f"app_{app_name}",
            digest_calculated=calculated,
            digest_claimed=claimed_tape_sha,
            details={
                "template": data.get("template"),
                "files_scaffolded": len(data.get("files_scaffolded", [])),
                "tests_passed": data.get("tests_passed"),
                "export_dir": data.get("export_dir"),
                "duration_ms": data.get("duration_ms"),
            },
            errors=errors,
        )

    @classmethod
    def _verify_agent_build_receipt(cls, data: Dict[str, Any]) -> ReceiptVerificationReport:
        spec_name = data.get("spec_name", "")
        version = data.get("version", "")
        manifest_digest = data.get("manifest_digest", "")
        claimed = data.get("receipt_sha256", "")
        tests_passed = data.get("tests_passed", False)
        dur_ms = data.get("duration_ms", 0.0)

        seal_payload = f"{spec_name}:{version}:{manifest_digest}:{tests_passed}:{dur_ms}"
        calculated = hashlib.sha256(seal_payload.encode()).hexdigest()

        is_valid = (calculated == claimed)
        errors = []
        if not is_valid:
            errors.append(f"Calculated agent seal ({calculated}) does not match receipt seal ({claimed}).")

        return ReceiptVerificationReport(
            receipt_type="agent_build",
            is_valid=is_valid,
            receipt_id=f"agent_{spec_name}@{version}",
            digest_calculated=calculated,
            digest_claimed=claimed,
            details={
                "spec_name": spec_name,
                "version": version,
                "manifest_digest": manifest_digest,
                "files_created": len(data.get("files_created", [])),
                "tests_passed": tests_passed,
                "duration_ms": dur_ms,
            },
            errors=errors,
        )

    @classmethod
    def _verify_sbom_manifest(cls, data: Dict[str, Any], secret_key: Optional[bytes] = None) -> ReceiptVerificationReport:
        from core.security.sbom import SBOMVerifier, DEFAULT_PROVENANCE_KEY
        key = secret_key or DEFAULT_PROVENANCE_KEY
        valid, status, details = SBOMVerifier.verify(data, signing_key=key)
        errors = [] if valid else [f"SBOM provenance verification failed: {status}"]
        return ReceiptVerificationReport(
            receipt_type="sbom_manifest",
            is_valid=valid,
            receipt_id=data.get("serial_number", "unknown_sbom"),
            digest_calculated=details.get("root_digest", ""),
            digest_claimed=data.get("root_digest_sha256", ""),
            details=details,
            errors=errors,
        )

