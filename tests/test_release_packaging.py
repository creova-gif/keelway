"""
Tests for Keelway Sovereign Release Packaging & Distribution Bundler.
Sorvex Labs — Sovereign Engineering Suite.

Verifies:
- Standalone bundler generates .tar.gz archive, root SHA256SUMS, and release-manifest.json.
- Exclusion of __pycache__, .pytest_cache, .git, and temporary test databases.
- Inclusion of core modules, cli.py, studio assets, and templates.
- Archive unpacks into clean directory and all files pass SHA-256 integrity check.
- Tamper and corrupt file detection.
- Deterministic byte-for-byte reproducible build output.
- Unpacked distribution can be imported and executed completely offline without network access.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

from scripts.build_release_bundle import (
    build_release_bundle,
    compute_sha256,
    verify_unpacked_distribution,
    ReleaseBundleResult,
)


@pytest.fixture(scope="module")
def shared_bundle(tmp_path_factory) -> ReleaseBundleResult:
    """Build a release bundle once for the module test suite."""
    out_dir = tmp_path_factory.mktemp("release_dist")
    return build_release_bundle(
        output_dir=out_dir,
        version="0.1.0",
        bundle_name="keelway-beta-v0.1.0-sovereign",
        deterministic=True,
    )


def test_packager_generates_required_artifacts(shared_bundle: ReleaseBundleResult):
    """Verify the bundler generates the .tar.gz, SHA256SUMS, and release-manifest.json."""
    assert shared_bundle.archive_path.exists(), "Distribution .tar.gz archive missing"
    assert shared_bundle.archive_path.name == "keelway-beta-v0.1.0-sovereign.tar.gz"
    assert shared_bundle.archive_path.stat().st_size > 50000

    assert shared_bundle.sha256sums_path.exists(), "Root SHA256SUMS file missing"
    assert shared_bundle.sha256sums_path.stat().st_size > 0

    assert shared_bundle.manifest_path.exists(), "release-manifest.json missing"
    assert shared_bundle.manifest_path.stat().st_size > 0

    manifest = json.loads(shared_bundle.manifest_path.read_text(encoding="utf-8"))

    # Required metadata fields
    assert "release_timestamp" in manifest or "timestamp" in manifest
    assert "version" in manifest
    assert manifest["version"] == "0.1.0"
    assert "git_commit" in manifest or "commit" in manifest
    assert len(manifest.get("git_commit", manifest.get("commit", ""))) >= 7
    assert "total_file_count" in manifest or "file_count" in manifest
    assert manifest.get("total_file_count", manifest.get("file_count")) > 50
    assert "bundle_sha256" in manifest or "sha256" in manifest

    # Cryptographic integrity of the bundle archive against manifest
    expected_bundle_hash = compute_sha256(shared_bundle.archive_path)
    assert manifest["bundle_sha256"] == expected_bundle_hash
    assert len(manifest["bundle_sha256"]) == 64


def test_exclusions_no_pycache_git_or_db(shared_bundle: ReleaseBundleResult):
    """Verify cache directories, .git, and temporary databases are strictly excluded."""
    manifest = json.loads(shared_bundle.manifest_path.read_text(encoding="utf-8"))
    paths = [f["path"] for f in manifest.get("files", [])]

    for path_str in paths:
        parts = Path(path_str).parts
        assert "__pycache__" not in parts, f"__pycache__ found in {path_str}"
        assert ".pytest_cache" not in parts, f".pytest_cache found in {path_str}"
        assert ".git" not in parts, f".git found in {path_str}"
        assert ".venv" not in parts, f".venv found in {path_str}"
        assert not path_str.endswith(".pyc"), f"Compiled bytecode found: {path_str}"
        assert not path_str.endswith(".pyo"), f"Compiled bytecode found: {path_str}"
        assert not path_str.endswith(".pyd"), f"Compiled bytecode found: {path_str}"
        assert not path_str.endswith(".db"), f"Temporary database found: {path_str}"
        assert not path_str.endswith(".sqlite"), f"Temporary database found: {path_str}"
        assert not path_str.endswith(".sqlite3"), f"Temporary database found: {path_str}"
        assert "audit.db" not in path_str, f"Audit database found: {path_str}"


def test_core_modules_cli_and_studio_assets_collected(shared_bundle: ReleaseBundleResult):
    """Verify core runtime modules, CLI entrypoint, Studio assets, and templates are collected."""
    manifest = json.loads(shared_bundle.manifest_path.read_text(encoding="utf-8"))
    paths = {f["path"] for f in manifest.get("files", [])}

    # CLI
    assert "cli.py" in paths

    # Core runtime modules
    assert "core/__init__.py" in paths
    assert "core/config.py" in paths
    assert "core/main.py" in paths
    assert "core/security/airgap.py" in paths
    assert "core/security/bundle_exporter.py" in paths

    # Studio assets
    assert "core/studio/index.html" in paths
    assert "core/studio/assets/studio.css" in paths
    assert "core/studio/assets/studio.js" in paths

    # Templates (Helm templates and/or top-level templates)
    template_paths = [p for p in paths if "template" in p.lower() or p.endswith(".tpl")]
    assert len(template_paths) > 0, "No templates were bundled"


def test_archive_unpack_and_sha256_integrity(shared_bundle: ReleaseBundleResult, tmp_path: Path):
    """Verify archive unpacks into a clean directory and passes SHA-256 integrity check."""
    unpack_dir = tmp_path / "clean_unpacked"
    unpack_dir.mkdir(parents=True, exist_ok=True)

    with tarfile.open(shared_bundle.archive_path, "r:gz") as tar:
        tar.extractall(path=unpack_dir)

    # 1. SHA256SUMS must exist at the root of the unpacked archive
    sums_file = unpack_dir / "SHA256SUMS"
    assert sums_file.exists(), "SHA256SUMS missing from unpacked distribution"

    # 2. Automated integrity check across all unpacked files
    is_valid, errors = verify_unpacked_distribution(unpack_dir, sums_file)
    assert is_valid, f"SHA-256 verification failed with errors: {errors}"
    assert len(errors) == 0

    # 3. Double-check all lines in SHA256SUMS explicitly
    lines = [line.strip() for line in sums_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == shared_bundle.total_file_count

    for line in lines:
        expected_hash, rel_path = line.split(None, 1)
        file_path = unpack_dir / rel_path.strip()
        assert file_path.exists(), f"File in SHA256SUMS does not exist: {rel_path}"
        actual_hash = compute_sha256(file_path)
        assert actual_hash == expected_hash, f"Hash mismatch for {rel_path}"


def test_tamper_detection_in_unpacked_distribution(shared_bundle: ReleaseBundleResult, tmp_path: Path):
    """Verify corrupted or modified files are caught by integrity verification."""
    unpack_dir = tmp_path / "tamper_test"
    with tarfile.open(shared_bundle.archive_path, "r:gz") as tar:
        tar.extractall(path=unpack_dir)

    # Clean verification passes
    is_valid, errors = verify_unpacked_distribution(unpack_dir)
    assert is_valid

    # Corrupt a file
    cli_path = unpack_dir / "cli.py"
    with open(cli_path, "ab") as f:
        f.write(b"\n# MALICIOUS INJECTION\n")

    is_valid_after_tamper, errors_after_tamper = verify_unpacked_distribution(unpack_dir)
    assert not is_valid_after_tamper
    assert any("cli.py" in err for err in errors_after_tamper)


def test_deterministic_reproducible_archive(tmp_path: Path):
    """Verify consecutive packaging runs produce byte-for-byte identical archives."""
    dist_a = tmp_path / "dist_a"
    dist_b = tmp_path / "dist_b"

    res_a = build_release_bundle(
        output_dir=dist_a,
        version="0.1.0",
        bundle_name="keelway-beta-v0.1.0-sovereign",
        deterministic=True,
        fixed_timestamp=1700000000,
    )
    res_b = build_release_bundle(
        output_dir=dist_b,
        version="0.1.0",
        bundle_name="keelway-beta-v0.1.0-sovereign",
        deterministic=True,
        fixed_timestamp=1700000000,
    )

    bytes_a = res_a.archive_path.read_bytes()
    bytes_b = res_b.archive_path.read_bytes()

    assert bytes_a == bytes_b, "Archives are not byte-for-byte identical"
    assert res_a.bundle_sha256 == res_b.bundle_sha256


def test_unpacked_distribution_imported_and_executed_offline(
    shared_bundle: ReleaseBundleResult, tmp_path: Path
):
    """
    Verify the unpacked distribution can be imported and executed in a strict
    air-gapped environment with all outbound network socket connections blocked.
    """
    offline_dir = tmp_path / "offline_exec"
    with tarfile.open(shared_bundle.archive_path, "r:gz") as tar:
        tar.extractall(path=offline_dir)

    # Verification script that blocks socket connection attempts
    offline_test_script = """
import sys
import socket

# Block all network connection attempts at the socket level
def airgap_blocked_connect(*args, **kwargs):
    raise OSError("AIR-GAP VIOLATION: Network connection attempted during sovereign offline execution!")

socket.socket.connect = airgap_blocked_connect
socket.socket.connect_ex = airgap_blocked_connect
socket.create_connection = airgap_blocked_connect

# 1. Import core runtime modules
import core
from core.config import settings
assert settings.default_local_model, "default_local_model not configured"

# 2. Import cli entrypoint
import cli
assert hasattr(cli, "main"), "cli.main missing"

print("[✓] Unpacked core and cli imported successfully without network access.")
"""

    env = os.environ.copy()
    env["PYTHONPATH"] = str(offline_dir)
    env["NO_PROXY"] = "*"
    env["HTTP_PROXY"] = "http://127.0.0.1:0"
    env["HTTPS_PROXY"] = "http://127.0.0.1:0"

    # Test import in isolated subprocess
    res_import = subprocess.run(
        [sys.executable, "-c", offline_test_script],
        cwd=offline_dir,
        capture_output=True,
        text=True,
        env=env,
    )
    assert res_import.returncode == 0, f"Offline import failed: {res_import.stderr}"
    assert "[✓] Unpacked core and cli imported successfully" in res_import.stdout

    # Test CLI execution (--help)
    res_help = subprocess.run(
        [sys.executable, "cli.py", "--help"],
        cwd=offline_dir,
        capture_output=True,
        text=True,
        env=env,
    )
    assert res_help.returncode == 0, f"CLI help failed: {res_help.stderr}"
    assert "Keelway Core Developer & Operations CLI" in res_help.stdout
    assert "doctor" in res_help.stdout
    assert "airgap" in res_help.stdout
    assert "package" in res_help.stdout


def test_cli_bundler_command_line_interface(tmp_path: Path):
    """Verify running scripts/build_release_bundle.py from CLI directly."""
    cli_dist = tmp_path / "cli_dist"
    bundler_script = Path(__file__).resolve().parent.parent / "scripts" / "build_release_bundle.py"

    res = subprocess.run(
        [
            sys.executable,
            str(bundler_script),
            "--output-dir",
            str(cli_dist),
            "--version",
            "0.1.0",
        ],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, f"Bundler script failed: {res.stderr}"
    assert "[✓] Release Bundle Created" in res.stdout

    # Check generated files
    assert (cli_dist / "keelway-beta-v0.1.0-sovereign.tar.gz").exists()
    assert (cli_dist / "SHA256SUMS").exists()
    assert (cli_dist / "manifest.json").exists()
    assert (cli_dist / "release-manifest.json").exists()


def test_build_bundle_function_alias(tmp_path: Path):
    """Verify build_bundle function alias in scripts/build_release_bundle.py."""
    from scripts.build_release_bundle import build_bundle

    alias_dist = tmp_path / "alias_dist"
    res = build_bundle(output_dir=alias_dist, version="0.1.0")
    assert res.archive_path.exists()
    assert (alias_dist / "manifest.json").exists()
    assert (alias_dist / "SHA256SUMS").exists()
    assert res.bundle_sha256 == compute_sha256(res.archive_path)


def test_cli_cmd_package_direct(tmp_path: Path):
    """Verify direct invocation of cli.py:cmd_package function."""
    from cli import cmd_package

    func_dist = tmp_path / "func_dist"
    ret = cmd_package(
        out=func_dist,
        version="0.1.0",
        skip_tests=True,
    )
    assert ret == 0

    tar_path = func_dist / "keelway-beta-v0.1.0-sovereign.tar.gz"
    assert tar_path.exists()
    assert (func_dist / "SHA256SUMS").exists()
    assert (func_dist / "manifest.json").exists()
    assert (func_dist / "release-manifest.json").exists()

    # Verify cryptographic integrity of the unpacked archive
    unpack_dir = tmp_path / "func_unpacked"
    with tarfile.open(tar_path, "r:gz") as tar:
        tar.extractall(path=unpack_dir)
    is_valid, errors = verify_unpacked_distribution(unpack_dir)
    assert is_valid, f"Verification failed: {errors}"


def test_cli_subcommand_keelway_package(tmp_path: Path):
    """Verify executing 'keelway package' subcommand via cli.py."""
    subcmd_dist = tmp_path / "subcmd_dist"
    cli_script = Path(__file__).resolve().parent.parent / "cli.py"

    res = subprocess.run(
        [
            sys.executable,
            str(cli_script),
            "package",
            "--out",
            str(subcmd_dist),
            "--version",
            "0.1.0",
            "--skip-tests",
        ],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, f"keelway package CLI failed: {res.stderr}"
    assert "[✓] Release Package Created" in res.stdout

    tar_path = subcmd_dist / "keelway-beta-v0.1.0-sovereign.tar.gz"
    assert tar_path.exists()
    assert (subcmd_dist / "SHA256SUMS").exists()
    assert (subcmd_dist / "manifest.json").exists()
    assert (subcmd_dist / "release-manifest.json").exists()

    # Verify manifest fields
    manifest = json.loads((subcmd_dist / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["version"] == "0.1.0"
    assert "bundle_sha256" in manifest
    assert "files" in manifest


def test_cli_subcommand_package_runs_pre_release_tests(tmp_path: Path):
    """Verify 'keelway package' executes pre-release verification tests when not skipped."""
    tested_dist = tmp_path / "tested_dist"
    cli_script = Path(__file__).resolve().parent.parent / "cli.py"

    res = subprocess.run(
        [
            sys.executable,
            str(cli_script),
            "package",
            "--out",
            str(tested_dist),
            "--version",
            "0.1.0",
        ],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, f"keelway package with tests failed: {res.stderr}"
    assert "[+] Running pre-release verification tests..." in res.stdout
    assert "[✓] Pre-release verification tests passed." in res.stdout
    assert "[✓] Release Package Created" in res.stdout
    assert (tested_dist / "keelway-beta-v0.1.0-sovereign.tar.gz").exists()
    assert (tested_dist / "manifest.json").exists()
