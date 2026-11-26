#!/usr/bin/env python3
"""
Keelway Sovereign Release Bundler.
Sorvex Labs — Deterministic Release Packaging System.

Generates self-contained, offline-deployable, cryptographically attested
distribution archives for air-gapped sovereign enterprise environments.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import subprocess
import sys
import tarfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


EXCLUDED_DIR_NAMES: Set[str] = {
    "__pycache__",
    ".pytest_cache",
    ".git",
    ".github",
    ".keelway",
    ".gstack",
    ".vercel",
    ".venv",
    "venv",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    ".coverage",
    "node_modules",
    "dist",
    "build",
    "builds",
}

EXCLUDED_FILE_SUFFIXES: Set[str] = {
    ".pyc",
    ".pyo",
    ".pyd",
    ".DS_Store",
    ".coverage",
    ".tmp",
    ".bak",
}

EXCLUDED_DB_SUFFIXES: Set[str] = {
    ".db",
    ".sqlite",
    ".sqlite3",
    ".db-journal",
    ".db-wal",
    ".db-shm",
}


@dataclass
class BundledFile:
    rel_path: str
    sha256: str
    size_bytes: int


@dataclass
class ReleaseBundleResult:
    bundle_name: str
    archive_path: Path
    manifest_path: Path
    sha256sums_path: Path
    version: str
    git_commit: str
    release_timestamp: str
    total_file_count: int
    bundle_sha256: str
    files: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bundle_name": self.bundle_name,
            "bundle_file": self.archive_path.name,
            "bundle_archive": self.archive_path.name,
            "archive_path": str(self.archive_path),
            "manifest_path": str(self.manifest_path),
            "sha256sums_path": str(self.sha256sums_path),
            "version": self.version,
            "git_commit": self.git_commit,
            "commit": self.git_commit,
            "release_timestamp": self.release_timestamp,
            "timestamp": self.release_timestamp,
            "total_file_count": self.total_file_count,
            "file_count": self.total_file_count,
            "bundle_sha256": self.bundle_sha256,
            "sha256": self.bundle_sha256,
            "files": self.files,
        }


def compute_sha256(file_path: Path) -> str:
    """Compute hex SHA-256 digest of a file in 64KB chunks."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def get_git_commit(source_dir: Path) -> str:
    """Retrieve git HEAD commit hash or fallback to environment or default."""
    if "GIT_COMMIT" in os.environ:
        return os.environ["GIT_COMMIT"].strip()
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=source_dir,
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    except Exception:
        pass
    return "0000000000000000000000000000000000000000"


def get_commit_timestamp(source_dir: Path) -> int:
    """Retrieve git commit epoch timestamp or fallback to deterministic timestamp."""
    if "SOURCE_DATE_EPOCH" in os.environ:
        try:
            return int(os.environ["SOURCE_DATE_EPOCH"])
        except ValueError:
            pass
    try:
        res = subprocess.run(
            ["git", "log", "-1", "--format=%ct"],
            cwd=source_dir,
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode == 0 and res.stdout.strip():
            return int(res.stdout.strip())
    except Exception:
        pass
    return 1700000000  # Fallback deterministic epoch timestamp


def should_exclude(rel_path: Path, filename: str) -> bool:
    """Determine whether a file or directory should be excluded from release."""
    parts = set(rel_path.parts)
    if parts.intersection(EXCLUDED_DIR_NAMES):
        return True

    # Exclude dotfiles (e.g. .DS_Store, .gitignore), but keep normal files
    if filename.startswith(".") and filename != ".gitkeep":
        return True

    # Exclude compiled bytecode and temporary files
    for suffix in EXCLUDED_FILE_SUFFIXES:
        if filename.endswith(suffix):
            return True

    # Exclude test and development databases
    for db_suffix in EXCLUDED_DB_SUFFIXES:
        if filename.endswith(db_suffix):
            return True

    if "audit.db" in filename or (filename.startswith("test_") and filename.endswith(".db")):
        return True

    return False


def collect_release_files(source_dir: Path) -> Dict[str, Path]:
    """
    Collects core modules, studio assets, CLI, templates, and project metadata.
    Returns a dict mapping archive relative paths to source file Paths.
    """
    files_map: Dict[str, Path] = {}

    # 1. CLI entrypoint
    cli_file = source_dir / "cli.py"
    if cli_file.exists() and cli_file.is_file():
        files_map["cli.py"] = cli_file

    # 2. Core runtime modules & Studio assets
    core_dir = source_dir / "core"
    if core_dir.exists() and core_dir.is_dir():
        for root, dirs, files in os.walk(core_dir):
            rel_root = Path(root).relative_to(source_dir)
            # Prune excluded directories in-place
            dirs[:] = [
                d for d in dirs
                if d not in EXCLUDED_DIR_NAMES and not d.startswith(".")
            ]
            for f in files:
                rel_file = rel_root / f
                if should_exclude(rel_file, f):
                    continue
                files_map[rel_file.as_posix()] = Path(root) / f

    # 3. Templates (top-level templates and/or deploy helm templates)
    templates_dir = source_dir / "templates"
    if templates_dir.exists() and templates_dir.is_dir():
        for root, dirs, files in os.walk(templates_dir):
            rel_root = Path(root).relative_to(source_dir)
            dirs[:] = [
                d for d in dirs
                if d not in EXCLUDED_DIR_NAMES and not d.startswith(".")
            ]
            for f in files:
                rel_file = rel_root / f
                if should_exclude(rel_file, f):
                    continue
                files_map[rel_file.as_posix()] = Path(root) / f

    helm_templates = source_dir / "deploy" / "helm" / "keelway" / "templates"
    if helm_templates.exists() and helm_templates.is_dir():
        for root, dirs, files in os.walk(helm_templates):
            rel_to_helm = Path(root).relative_to(helm_templates)
            dirs[:] = [
                d for d in dirs
                if d not in EXCLUDED_DIR_NAMES and not d.startswith(".")
            ]
            for f in files:
                if should_exclude(rel_to_helm / f, f):
                    continue
                src_path = Path(root) / f
                # Put under deploy/helm/keelway/templates
                deploy_rel = (Path("deploy/helm/keelway/templates") / rel_to_helm / f).as_posix()
                files_map[deploy_rel] = src_path
                # If no top-level templates existed, also populate templates/helm
                if not templates_dir.exists():
                    tpl_rel = (Path("templates/helm") / rel_to_helm / f).as_posix()
                    files_map[tpl_rel] = src_path

    # 4. Standard distribution metadata files
    for meta_name in ("pyproject.toml", "README.md", "LICENSE", "NOTICE", "keelway-sbom.json"):
        meta_file = source_dir / meta_name
        if meta_file.exists() and meta_file.is_file():
            files_map[meta_name] = meta_file

    return files_map


def build_release_bundle(
    source_dir: Optional[Path] = None,
    output_dir: Optional[Path] = None,
    version: str = "0.1.0",
    bundle_name: Optional[str] = None,
    deterministic: bool = True,
    fixed_timestamp: Optional[int] = None,
) -> ReleaseBundleResult:
    """
    Build a standalone, deterministic release bundle with SHA256SUMS and release manifest.
    """
    source_dir = Path(source_dir or Path(__file__).resolve().parent.parent).resolve()
    if output_dir is None:
        output_dir = source_dir / "dist"
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    # Normalize version string
    clean_version = version.lstrip("v")
    if clean_version.startswith("beta-"):
        clean_version = clean_version.replace("beta-", "").lstrip("v")

    if not bundle_name:
        bundle_name = f"keelway-beta-v{clean_version}-sovereign"

    # Git metadata and timestamp
    git_commit = get_git_commit(source_dir)
    mtime = fixed_timestamp if fixed_timestamp is not None else get_commit_timestamp(source_dir)
    if deterministic:
        release_timestamp = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
    else:
        release_timestamp = datetime.now(timezone.utc).isoformat()

    # Collect and sort all files deterministically
    files_map = collect_release_files(source_dir)
    sorted_rel_paths = sorted(files_map.keys())

    bundled_files: List[BundledFile] = []
    checksum_lines: List[str] = []

    for rel_path in sorted_rel_paths:
        file_path = files_map[rel_path]
        file_sha256 = compute_sha256(file_path)
        file_size = file_path.stat().st_size
        bundled_files.append(
            BundledFile(rel_path=rel_path, sha256=file_sha256, size_bytes=file_size)
        )
        checksum_lines.append(f"{file_sha256}  {rel_path}")

    # Generate root SHA256SUMS content
    sha256sums_content = "\n".join(checksum_lines) + "\n"

    # Write root SHA256SUMS to output_dir
    dist_sums_path = output_dir / "SHA256SUMS"
    dist_sums_path.write_text(sha256sums_content, encoding="utf-8")

    # Generate the .tar.gz distribution archive
    archive_path = output_dir / f"{bundle_name}.tar.gz"

    def filter_tarinfo(tarinfo: tarfile.TarInfo) -> tarfile.TarInfo:
        if deterministic:
            tarinfo.uid = 0
            tarinfo.gid = 0
            tarinfo.uname = ""
            tarinfo.gname = ""
            tarinfo.mtime = mtime
            if tarinfo.isdir():
                tarinfo.mode = 0o755
            elif tarinfo.name == "cli.py" or tarinfo.name.endswith(".sh"):
                tarinfo.mode = 0o755
            else:
                tarinfo.mode = 0o644
        return tarinfo

    # Create deterministic tar.gz
    # Using gzip.GzipFile with fixed mtime ensures byte-for-byte reproducibility
    with open(archive_path, "wb") as raw_f:
        with gzip.GzipFile(
            filename="",
            mode="wb",
            fileobj=raw_f,
            mtime=mtime if deterministic else None,
        ) as gz_f:
            with tarfile.open(mode="w", fileobj=gz_f) as tar:
                # Add all bundled files in sorted order
                for b_file in bundled_files:
                    src_path = files_map[b_file.rel_path]
                    tar.add(
                        src_path,
                        arcname=b_file.rel_path,
                        recursive=False,
                        filter=filter_tarinfo,
                    )
                # Add root SHA256SUMS inside the archive
                tar.add(
                    dist_sums_path,
                    arcname="SHA256SUMS",
                    recursive=False,
                    filter=filter_tarinfo,
                )

    # Compute bundle SHA-256 on the generated .tar.gz archive
    bundle_sha256 = compute_sha256(archive_path)

    # Generate release-manifest.json
    files_list = [
        {"path": bf.rel_path, "sha256": bf.sha256, "size_bytes": bf.size_bytes}
        for bf in bundled_files
    ]
    manifest_data = {
        "bundle_name": bundle_name,
        "bundle_archive": archive_path.name,
        "bundle_file": archive_path.name,
        "bundle_sha256": bundle_sha256,
        "sha256": bundle_sha256,
        "version": clean_version,
        "git_commit": git_commit,
        "commit": git_commit,
        "release_timestamp": release_timestamp,
        "timestamp": release_timestamp,
        "total_file_count": len(bundled_files),
        "file_count": len(bundled_files),
        "files": files_list,
    }

    manifest_path = output_dir / "release-manifest.json"
    manifest_content = json.dumps(manifest_data, indent=2, sort_keys=True) + "\n"
    manifest_path.write_text(
        manifest_content,
        encoding="utf-8",
    )
    # Also write manifest.json for offline distribution compatibility
    (output_dir / "manifest.json").write_text(
        manifest_content,
        encoding="utf-8",
    )

    return ReleaseBundleResult(
        bundle_name=bundle_name,
        archive_path=archive_path,
        manifest_path=manifest_path,
        sha256sums_path=dist_sums_path,
        version=clean_version,
        git_commit=git_commit,
        release_timestamp=release_timestamp,
        total_file_count=len(bundled_files),
        bundle_sha256=bundle_sha256,
        files=files_list,
    )


def build_bundle(
    source_dir: Optional[Path] = None,
    output_dir: Optional[Path] = None,
    version: str = "0.1.0",
    bundle_name: Optional[str] = None,
    deterministic: bool = True,
    fixed_timestamp: Optional[int] = None,
) -> ReleaseBundleResult:
    """
    Build a standalone, deterministic release bundle with SHA256SUMS and release manifest.
    Alias for build_release_bundle.
    """
    return build_release_bundle(
        source_dir=source_dir,
        output_dir=output_dir,
        version=version,
        bundle_name=bundle_name,
        deterministic=deterministic,
        fixed_timestamp=fixed_timestamp,
    )


def verify_unpacked_distribution(
    unpacked_dir: Path,
    sums_file: Optional[Path] = None,
) -> Tuple[bool, List[str]]:
    """
    Verify the cryptographic integrity of all files in an unpacked distribution.
    Returns (is_valid, list_of_errors).
    """
    unpacked_dir = Path(unpacked_dir).resolve()
    if sums_file is None:
        sums_file = unpacked_dir / "SHA256SUMS"
    sums_file = Path(sums_file).resolve()

    if not sums_file.exists():
        return False, [f"SHA256SUMS file not found: {sums_file}"]

    errors: List[str] = []
    lines = sums_file.read_text(encoding="utf-8").splitlines()

    for line_idx, line in enumerate(lines, 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 1)
        if len(parts) != 2:
            errors.append(f"Line {line_idx}: malformed checksum entry '{line}'")
            continue
        expected_hash, rel_path = parts[0], parts[1].strip()
        target_file = unpacked_dir / rel_path

        if not target_file.exists():
            errors.append(f"Missing file: {rel_path}")
            continue

        actual_hash = compute_sha256(target_file)
        if actual_hash != expected_hash:
            errors.append(
                f"Hash mismatch for {rel_path}: expected {expected_hash}, got {actual_hash}"
            )

    return (len(errors) == 0, errors)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Keelway Sovereign Release Packaging Tool (Sorvex Labs)"
    )
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=None,
        help="Path to Keelway source root (default: repo root)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Path to output distribution directory (default: dist)",
    )
    parser.add_argument(
        "--version",
        default="0.1.0",
        help="Release version string (default: 0.1.0)",
    )
    parser.add_argument(
        "--bundle-name",
        default=None,
        help="Custom bundle name (default: keelway-beta-v<version>-sovereign)",
    )
    parser.add_argument(
        "--non-deterministic",
        action="store_true",
        help="Disable deterministic archiving timestamps and uids",
    )
    parser.add_argument(
        "--verify",
        type=Path,
        default=None,
        help="Verify an unpacked distribution directory against its SHA256SUMS",
    )

    args = parser.parse_args()

    if args.verify:
        is_valid, errors = verify_unpacked_distribution(args.verify)
        if is_valid:
            print(f"[✓] Integrity verified successfully: {args.verify}")
            sys.exit(0)
        else:
            print(f"[✗] Integrity verification failed ({len(errors)} errors):")
            for err in errors[:20]:
                print(f"  - {err}")
            sys.exit(1)

    print("[+] Building sovereign release bundle...")
    result = build_release_bundle(
        source_dir=args.source_dir,
        output_dir=args.output_dir,
        version=args.version,
        bundle_name=args.bundle_name,
        deterministic=not args.non_deterministic,
    )

    print(f"[✓] Release Bundle Created: {result.bundle_name}")
    print(f"  • Archive:     {result.archive_path} ({result.archive_path.stat().st_size} bytes)")
    print(f"  • Manifest:    {result.manifest_path}")
    print(f"  • Checksums:   {result.sha256sums_path}")
    print(f"  • SHA-256:     {result.bundle_sha256}")
    print(f"  • Files:       {result.total_file_count}")
    print(f"  • Git Commit:  {result.git_commit[:12]}")
    print(f"  • Timestamp:   {result.release_timestamp}")


if __name__ == "__main__":
    main()
