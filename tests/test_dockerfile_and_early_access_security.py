"""Regression gates for Dockerfile stage Python version alignment, private PII
early-access webhook routing, and repository governance documentation.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def extract_dockerfile_python_versions(dockerfile_text: str) -> tuple[list[str], list[str]]:
    """Return (from_stage_versions, site_packages_versions) from a Dockerfile."""
    from_versions = re.findall(
        r"^\s*FROM\s+python:(\d+\.\d+)(?:-[^\s]+)?(?:\s+AS\s+\S+)?\s*$",
        dockerfile_text,
        flags=re.MULTILINE | re.IGNORECASE,
    )
    site_pkg_versions = re.findall(
        r"/usr/local/lib/python(\d+\.\d+)/site-packages",
        dockerfile_text,
    )
    return from_versions, site_pkg_versions


def validate_dockerfile_version_consistency(dockerfile_text: str) -> str:
    """Validate that all Python FROM stages and site-packages paths share one minor version."""
    from_versions, site_pkg_versions = extract_dockerfile_python_versions(dockerfile_text)
    if len(from_versions) < 2:
        raise AssertionError(f"Expected multi-stage Python FROM declarations, found: {from_versions}")
    if len(set(from_versions)) != 1:
        raise AssertionError(f"Dockerfile builder/runtime FROM Python versions drifted: {from_versions}")
    if not site_pkg_versions:
        raise AssertionError("Expected explicit /usr/local/lib/pythonX.Y/site-packages COPY in Dockerfile")
    canonical_version = from_versions[0]
    mismatched = [v for v in site_pkg_versions if v != canonical_version]
    if mismatched:
        raise AssertionError(
            f"Dockerfile FROM python:{canonical_version} mismatches site-packages version(s): {site_pkg_versions}"
        )
    return canonical_version


def test_dockerfile_stage_and_site_packages_versions_aligned() -> None:
    dockerfile_text = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")
    canonical_version = validate_dockerfile_version_consistency(dockerfile_text)

    # Verify synthetic regression detector catches the exact 3.14 vs 3.12 bug from run 45028274734
    broken_dockerfile = dockerfile_text.replace(
        f"/usr/local/lib/python{canonical_version}/site-packages",
        "/usr/local/lib/python3.12/site-packages",
    )
    if canonical_version != "3.12":
        with pytest.raises(AssertionError, match="mismatches site-packages"):
            validate_dockerfile_version_consistency(broken_dockerfile)

    # Verify compatibility with pyproject.toml minimum Python and CI test matrix
    pyproject_text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    req_match = re.search(r'requires-python\s*=\s*">=(\d+\.\d+)"', pyproject_text)
    assert req_match is not None, "pyproject.toml must declare requires-python"
    min_tuple = tuple(int(p) for p in req_match.group(1).split("."))
    docker_tuple = tuple(int(p) for p in canonical_version.split("."))
    assert docker_tuple >= min_tuple, (
        f"Dockerfile Python {canonical_version} is older than requires-python >={req_match.group(1)}"
    )

    ci_text = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert f'"{canonical_version}"' in ci_text, (
        f"Dockerfile Python {canonical_version} must be tested in .github/workflows/ci.yml matrix"
    )


def test_early_access_serverless_never_leaks_pii_to_github_issues() -> None:
    early_access_src = (REPO_ROOT / "api" / "early-access.js").read_text(encoding="utf-8")
    assert "EARLY_ACCESS_GH_TOKEN" not in early_access_src
    assert "https://api.github.com/repos/" not in early_access_src
    assert "EARLY_ACCESS_WEBHOOK_URL" in early_access_src

    node_bin = shutil.which("node")
    assert node_bin is not None, "node is required to execute api/early-access.js security suite"
    proc = subprocess.run(
        [node_bin, "--test", str(REPO_ROOT / "tests" / "js" / "early_access.test.mjs")],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert proc.returncode == 0, f"api/early-access.js security tests failed:\n{proc.stdout}\n{proc.stderr}"


def test_governance_files_and_readme_technical_precision() -> None:
    dot_env = REPO_ROOT / ".env.example"
    assert dot_env.is_file(), ".env.example must exist at repository root"
    dot_env_text = dot_env.read_text(encoding="utf-8")
    assert "EARLY_ACCESS_WEBHOOK_URL=" in dot_env_text

    codeowners = REPO_ROOT / ".github" / "CODEOWNERS"
    assert codeowners.is_file(), ".github/CODEOWNERS must exist"
    assert "* @creova-gif" in codeowners.read_text(encoding="utf-8")

    agents_md = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Authoritative Decision Hierarchy" in agents_md
    assert "UNIVERSAL TASK EXECUTION PROTOCOL (Stages A–F)" in agents_md

    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert "```mermaid" in readme
    assert "Engineering Decisions & Security Boundaries" in readme
    assert "HTTP-level" in readme and "KV-cache" in readme
    assert "bubblewrap" in readme and "Seatbelt" in readme
    assert "2-Human Quorum" in readme
