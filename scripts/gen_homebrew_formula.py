#!/usr/bin/env python3
"""Generate a pinned Homebrew formula for Keelway.

Resolves the full dependency closure with ``pip install --dry-run --report``
using platform-pinned wheel artifacts (macOS arm64 + Linux x86_64, cp312 ABI),
then emits ``packaging/homebrew/keelway.rb`` with every transitive dep as a
``resource`` block carrying a URL + sha256 — deterministic installs, no
install-time network resolution beyond the pinned artifacts.

Usage:
    python scripts/gen_homebrew_formula.py \
        --version 1.1.0 \
        --sdist-url https://github.com/creova-gif/keelway/releases/download/v1.1.0/keelway-1.1.0.tar.gz \
        --sdist-sha256 87f2ff... \
        --out packaging/homebrew/keelway.rb

After the first PyPI publish, pass --sdist-url/--sdist-sha256 for the
files.pythonhosted.org sdist instead of the GitHub release asset.
"""

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

# pip --platform tags for the matrix we pin. cp313 matches
# `depends_on "python@3.13"`.
PLATFORMS = {
    "macos": ["macosx_11_0_arm64"],
    "linux": ["manylinux_2_17_x86_64", "manylinux2014_x86_64", "linux_x86_64"],
}
PY_VER = "3.13"
ABI = "cp313"


def resolve_report(sdist_path: Path, platform: str) -> dict:
    """Return pip's install report resolved for one platform."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as fh:
        report_path = Path(fh.name)
    cmd = [
        sys.executable, "-m", "pip", "install", "--dry-run",
        "--only-binary", ":all:", "--ignore-installed",
        "--report", str(report_path),
        "--python-version", PY_VER, "--implementation", "cp",
        "--abi", ABI, "--platform", platform, str(sdist_path),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"pip resolve failed for {platform}:\n{res.stderr}")
    return json.loads(report_path.read_text())


def wheel_resources(report: dict) -> dict:
    """name -> {url, sha256} for each resolved wheel (keelway excluded)."""
    out = {}
    for item in report.get("install", []):
        meta = item["metadata"]
        name = meta["name"].lower().replace("-", "_")
        if name == "keelway":
            continue
        dl = item.get("download_info") or {}
        url = dl.get("url", "")
        sha = (dl.get("archive_info") or {}).get("hashes", {}).get("sha256", "")
        if not url.endswith(".whl") or not sha:
            raise RuntimeError(f"{name}: expected pinned wheel + sha256, got {url!r}")
        out[name] = {"url": url, "sha256": sha}
    return out


def emit(version: str, sdist_url: str, sdist_sha: str,
         shared: dict, macos_only: dict, linux_only: dict) -> str:
    def block(name: str, res: dict, indent: str = "    ") -> str:
        return (f'{indent}resource "{name}" do\n'
                f'{indent}  url "{res["url"]}"\n'
                f'{indent}  sha256 "{res["sha256"]}"\n'
                f'{indent}end\n\n')

    shared_res = "".join(block(n, r) for n, r in sorted(shared.items()))
    macos_res = "".join(block(n, r) for n, r in sorted(macos_only.items()))
    linux_res = "".join(block(n, r) for n, r in sorted(linux_only.items()))
    macos_sec = f"  on_macos do\n    on_arm do\n{macos_res}    end\n  end\n\n" if macos_res else ""
    linux_sec = f"  on_linux do\n{linux_res}  end\n\n" if linux_res else ""

    return f'''class Keelway < Formula
  include Language::Python::Virtualenv

  desc "Customer-managed governance and audit platform for AI-powered software change"
  homepage "https://keelway.dev"
  url "{sdist_url}"
  sha256 "{sdist_sha}"
  license "PROPRIETARY"
  version "{version}"

  depends_on "python@3.13"

{shared_res}{macos_sec}{linux_sec}  def install
    virtualenv_install_with_resources
  end

  test do
    assert_match "overall_status", shell_output("#{{bin}}/keelway doctor --json")
  end
end
'''


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", required=True)
    ap.add_argument("--sdist-url", required=True)
    ap.add_argument("--sdist-sha256", required=True)
    ap.add_argument("--sdist-path", help="Local sdist path (skip download)")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    if args.sdist_path:
        sdist_path = Path(args.sdist_path)
    else:
        sdist_path = Path(tempfile.mkdtemp()) / "keelway.tar.gz"
        urllib.request.urlretrieve(args.sdist_url, sdist_path)
        digest = hashlib.sha256(sdist_path.read_bytes()).hexdigest()
        if digest != args.sdist_sha256:
            raise SystemExit(f"sha256 mismatch: {digest} != {args.sdist_sha256}")

    resolved = {}
    for os_name, plats in PLATFORMS.items():
        merged = {}
        for plat in plats:
            try:
                merged = wheel_resources(resolve_report(sdist_path, plat))
                break
            except RuntimeError as exc:
                last = exc
        else:
            raise SystemExit(f"no {os_name} platform resolved: {last}")
        resolved[os_name] = merged

    macos_set = resolved["macos"]
    linux_set = resolved["linux"]
    shared = {n: r for n, r in macos_set.items() if linux_set.get(n) == r}
    macos_only = {n: r for n, r in macos_set.items() if linux_set.get(n) != r}
    linux_only = {n: r for n, r in linux_set.items() if macos_set.get(n) != r}

    Path(args.out).write_text(emit(args.version, args.sdist_url,
                                 args.sdist_sha256, shared, macos_only, linux_only))
    print(f"wrote {args.out}: {len(shared)} shared + "
          f"{len(macos_only)} macos + {len(linux_only)} linux resources")
    return 0


if __name__ == "__main__":
    sys.exit(main())
