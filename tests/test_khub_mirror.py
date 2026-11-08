"""
Unit tests for KHub Enterprise Air-Gapped Mirror Export and Import (Section 1A/2A).
Verifies:
1. Exporting built-in KStack skills into an offline air-gapped mirror catalog.
2. Generating signed khub-mirror-manifest.json with fail-closed air-gap defaults.
3. Exporting to a unified compressed .tar.gz bundle archive.
4. Importing, verifying, and unpacking mirror archives into target repositories.
5. Tamper detection on modified member bundles.
6. CLI cmd_hub integration for mirror export and import.
"""

import json
from pathlib import Path
import pytest

from core.khub.sync import KHubBundlePacker, KHubMirror
from cli import cmd_hub


def test_khub_mirror_export_directory(tmp_path):
    mirror_dir = tmp_path / "mirror_dir"
    res = KHubMirror.export_mirror(mirror_dir)
    assert res["status"] == "exported"
    assert res["mode"] == "directory"
    assert res["total_skills"] >= 8
    assert res["catalog_digest_sha256"] != ""

    manifest_file = mirror_dir / "khub-mirror-manifest.json"
    assert manifest_file.is_file()
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    assert manifest["mirror_format"] == "khub-airgap-mirror-v1"
    assert manifest["air_gap_compliant"] is True
    assert manifest["network_policy"] == "none"
    assert len(manifest["skills"]) >= 8

    # Check that bundles exist
    for skill in manifest["skills"]:
        bundle_path = mirror_dir / skill["bundle_file"]
        assert bundle_path.is_file()
        assert skill["network_policy"] == "none"
        assert skill["air_gap_compliant"] is True


def test_khub_mirror_export_archive(tmp_path):
    mirror_archive = tmp_path / "khub-airgap-mirror.tar.gz"
    res = KHubMirror.export_mirror(mirror_archive)
    assert res["status"] == "exported"
    assert res["mode"] == "archive"
    assert mirror_archive.is_file()
    assert res["archive_sha256"] != ""
    assert res["total_skills"] >= 8


def test_khub_mirror_import_and_verification(tmp_path):
    mirror_archive = tmp_path / "offline-mirror.tar.gz"
    KHubMirror.export_mirror(mirror_archive)

    dest_dir = tmp_path / "imported_skills"
    res = KHubMirror.import_mirror(mirror_archive, destination_dir=dest_dir, auto_approve=True, verify=True)
    assert res["status"] == "imported"
    assert res["total_imported"] >= 8
    assert res["verified"] is True

    # Check imported directories
    for s in res["imported_skills"]:
        skill_path = Path(s["destination"])
        assert skill_path.is_dir()
        assert (skill_path / "SKILL.md").is_file()
        assert s["approved"] is True


def test_khub_mirror_tamper_detection(tmp_path):
    mirror_dir = tmp_path / "mirror_tamper"
    KHubMirror.export_mirror(mirror_dir)

    manifest_file = mirror_dir / "khub-mirror-manifest.json"
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    first_bundle = mirror_dir / manifest["skills"][0]["bundle_file"]

    # Tamper with the bundle bytes
    tampered_bytes = first_bundle.read_bytes() + b"\x00\x00\x00"
    first_bundle.write_bytes(tampered_bytes)

    dest_dir = tmp_path / "tamper_import"
    with pytest.raises(ValueError, match="checksum mismatch"):
        KHubMirror.import_mirror(mirror_dir, destination_dir=dest_dir, verify=True)


def test_cli_hub_mirror_workflow(tmp_path):
    archive_out = tmp_path / "cli_mirror.tar.gz"
    # 1. Export via CLI
    rc_export = cmd_hub(action="mirror", out=archive_out)
    assert rc_export == 0
    assert archive_out.is_file()

    # 2. Import via CLI
    import_dest = tmp_path / "cli_imported"
    rc_import = cmd_hub(action="mirror", import_mirror=archive_out, dest=import_dest, auto_approve=True)
    assert rc_import == 0
    assert (import_dest / "plan" / "SKILL.md").is_file()
    assert (import_dest / "review" / "SKILL.md").is_file()
