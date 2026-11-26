"""
Keelway Sovereign Air-Gap Bundle Exporter & Cryptographic Verifier.
Creates and validates tamper-evident, offline-deployable bundles with SHA-256 verification manifests.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tarfile
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class BundleVerificationResult:
    bundle_id: str
    is_valid: bool
    total_files: int
    matched_files: int
    mismatched_files: List[str]
    missing_files: List[str]
    root_digest_sha256: str
    duration_ms: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class BundleExportReceipt:
    bundle_id: str
    bundle_path: str
    total_files: int
    uncompressed_bytes: int
    compressed_bytes: int
    root_digest_sha256: str
    created_at_utc: str
    duration_ms: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AirGapBundleExporter:
    """Packages and cryptographically validates offline sovereign deployment bundles."""

    @classmethod
    def _compute_sha256(cls, file_path: Path) -> str:
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        return h.hexdigest()

    @classmethod
    def export_bundle(
        cls,
        source_dir: Optional[Path] = None,
        output_dir: Optional[Path] = None,
        bundle_name: Optional[str] = None,
        include_tar: bool = True,
    ) -> BundleExportReceipt:
        """Export core engine, templates, and checksums into an offline deployment bundle."""
        start_time = time.time()
        source_dir = Path(source_dir or Path(__file__).parent.parent.parent).resolve()
        now_ts = int(time.time())
        bundle_id = bundle_name or f"keelway-airgap-bundle-{now_ts}"

        if not output_dir:
            output_dir = Path("builds") / "sovereign"
        output_dir = Path(output_dir).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)

        bundle_dir = output_dir / bundle_id
        if bundle_dir.exists():
            shutil.rmtree(bundle_dir, ignore_errors=True)
        bundle_dir.mkdir(parents=True, exist_ok=True)

        files_manifest: List[Dict[str, Any]] = []
        checksum_lines: List[str] = []
        total_uncompressed = 0

        # Copy core package
        target_core = bundle_dir / "core"
        source_core = source_dir / "core"
        if source_core.exists():
            for root, dirs, files in os.walk(source_core):
                # Exclude pycache and temporary files
                dirs[:] = [d for d in dirs if d != "__pycache__" and not d.startswith(".")]
                for file in files:
                    if file.endswith((".pyc", ".pyo", ".pyd")) or file.startswith("."):
                        continue
                    src_file = Path(root) / file
                    rel_to_core = src_file.relative_to(source_core)
                    dst_file = target_core / rel_to_core
                    dst_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src_file, dst_file)

        # Copy CLI entrypoints and config
        for root_item in ("cli.py", "pyproject.toml", "README.md"):
            src_item = source_dir / root_item
            if src_item.exists() and src_item.is_file():
                shutil.copy2(src_item, bundle_dir / root_item)

        # Write offline deployment guide
        readme_offline = bundle_dir / "README.offline.md"
        readme_offline.write_text(f"""# Keelway Sovereign Air-Gapped Deployment Bundle

**Bundle ID:** `{bundle_id}`  
**Created:** {datetime.now(timezone.utc).isoformat()}  
**Compliance Standard:** NIST SP 800-53 SC-7 / ISO/IEC 27001 Zero-Egress

## Offline Bootstrap Instructions

1. Ensure Python 3.10+ is installed in the target air-gapped system.
2. Verify bundle integrity using the included SHA256SUMS:
   ```bash
   sha256sum -c SHA256SUMS
   ```
   Or via the Keelway CLI:
   ```bash
   keelway airgap bundle verify {bundle_id}.tar.gz
   ```
3. Launch Keelway in strict Air-Gap mode:
   ```bash
   python3 cli.py doctor
   python3 cli.py dev --host 127.0.0.1
   ```
""", encoding="utf-8")

        # Collect all files and generate SHA256SUMS
        for root, dirs, files in os.walk(bundle_dir):
            dirs[:] = sorted([d for d in dirs if not d.startswith(".")])
            for file in sorted(files):
                if file in ("SHA256SUMS", "bundle_manifest.json"):
                    continue
                fpath = Path(root) / file
                rel_path = fpath.relative_to(bundle_dir).as_posix()
                f_size = fpath.stat().st_size
                f_hash = cls._compute_sha256(fpath)
                total_uncompressed += f_size

                files_manifest.append({
                    "path": rel_path,
                    "size_bytes": f_size,
                    "sha256": f_hash,
                })
                checksum_lines.append(f"{f_hash}  {rel_path}")

        # Write SHA256SUMS
        sums_file = bundle_dir / "SHA256SUMS"
        sums_file.write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")

        # Compute root digest of SHA256SUMS content
        root_digest = hashlib.sha256(sums_file.read_bytes()).hexdigest()

        # Write bundle_manifest.json
        manifest_data = {
            "bundle_id": bundle_id,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "keelway_version": "0.1.0",
            "profile": "air-gapped-sovereign",
            "root_digest_sha256": root_digest,
            "total_files": len(files_manifest),
            "files": files_manifest,
        }
        manifest_file = bundle_dir / "bundle_manifest.json"
        manifest_file.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")

        # Optional tar.gz creation
        tar_path = output_dir / f"{bundle_id}.tar.gz"
        compressed_bytes = 0
        final_bundle_path = str(bundle_dir)

        if include_tar:
            with tarfile.open(tar_path, "w:gz") as tar:
                tar.add(bundle_dir, arcname=bundle_id)
            compressed_bytes = tar_path.stat().st_size
            final_bundle_path = str(tar_path)

        duration_ms = (time.time() - start_time) * 1000.0

        return BundleExportReceipt(
            bundle_id=bundle_id,
            bundle_path=final_bundle_path,
            total_files=len(files_manifest),
            uncompressed_bytes=total_uncompressed,
            compressed_bytes=compressed_bytes,
            root_digest_sha256=root_digest,
            created_at_utc=datetime.now(timezone.utc).isoformat(),
            duration_ms=duration_ms,
        )

    @classmethod
    def verify_bundle(cls, bundle_path: Path, temp_extract_dir: Optional[Path] = None) -> BundleVerificationResult:
        """Verify the integrity of a sovereign deployment bundle directory or tar.gz archive."""
        start_time = time.time()
        bundle_path = Path(bundle_path).resolve()
        if not bundle_path.exists():
            raise FileNotFoundError(f"Bundle path does not exist: {bundle_path}")

        extracted_dir = bundle_path
        cleanup_temp = False

        if bundle_path.is_file() and (bundle_path.name.endswith(".tar.gz") or bundle_path.name.endswith(".tgz")):
            cleanup_temp = True
            extract_root = temp_extract_dir or (bundle_path.parent / f"_verify_{int(time.time())}")
            extract_root.mkdir(parents=True, exist_ok=True)
            with tarfile.open(bundle_path, "r:gz") as tar:
                tar.extractall(path=extract_root)
            # Find the root folder inside extract_root
            subdirs = [d for d in extract_root.iterdir() if d.is_dir()]
            extracted_dir = subdirs[0] if subdirs else extract_root

        try:
            manifest_file = extracted_dir / "bundle_manifest.json"
            sums_file = extracted_dir / "SHA256SUMS"

            if not manifest_file.exists() or not sums_file.exists():
                return BundleVerificationResult(
                    bundle_id=bundle_path.stem,
                    is_valid=False,
                    total_files=0,
                    matched_files=0,
                    mismatched_files=[],
                    missing_files=["bundle_manifest.json" if not manifest_file.exists() else "SHA256SUMS"],
                    root_digest_sha256="",
                    duration_ms=(time.time() - start_time) * 1000.0,
                )

            manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
            bundle_id = manifest.get("bundle_id", bundle_path.stem)
            recorded_root_digest = manifest.get("root_digest_sha256", "")
            actual_root_digest = hashlib.sha256(sums_file.read_bytes()).hexdigest()

            if recorded_root_digest != actual_root_digest:
                return BundleVerificationResult(
                    bundle_id=bundle_id,
                    is_valid=False,
                    total_files=len(manifest.get("files", [])),
                    matched_files=0,
                    mismatched_files=["SHA256SUMS (root digest mismatch)"],
                    missing_files=[],
                    root_digest_sha256=actual_root_digest,
                    duration_ms=(time.time() - start_time) * 1000.0,
                )

            matched_count = 0
            mismatched: List[str] = []
            missing: List[str] = []

            for f_info in manifest.get("files", []):
                rel_path = f_info["path"]
                expected_sha = f_info["sha256"]
                target_file = extracted_dir / rel_path

                if not target_file.exists():
                    missing.append(rel_path)
                    continue

                actual_sha = cls._compute_sha256(target_file)
                if actual_sha == expected_sha:
                    matched_count += 1
                else:
                    mismatched.append(rel_path)

            total_files = len(manifest.get("files", []))
            is_valid = (matched_count == total_files) and not missing and not mismatched

            return BundleVerificationResult(
                bundle_id=bundle_id,
                is_valid=is_valid,
                total_files=total_files,
                matched_files=matched_count,
                mismatched_files=mismatched,
                missing_files=missing,
                root_digest_sha256=actual_root_digest,
                duration_ms=(time.time() - start_time) * 1000.0,
            )
        finally:
            if cleanup_temp and extracted_dir != bundle_path:
                shutil.rmtree(extract_root, ignore_errors=True)
