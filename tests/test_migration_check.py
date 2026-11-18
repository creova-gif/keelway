"""KEEL-ENG-033 — ADR-0042 Phase 1 migration-check import census."""

from __future__ import annotations

import json
from pathlib import Path

from core.system.migration_check import (
    format_migration_report,
    scan_migration_imports,
)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_scan_counts_core_and_keelway_core_imports(tmp_path: Path) -> None:
    _write(tmp_path / "core" / "pkg" / "mod.py", "x = 1\n")
    _write(
        tmp_path / "core" / "pkg" / "user.py",
        "import core.models.gateway\nfrom core.security import rbac\nimport os\n",
    )
    _write(
        tmp_path / "keelway_core" / "engine.py",
        "from keelway_core.provider import Provider\n",
    )
    _write(
        tmp_path / "keelway" / "approvals" / "svc.py",
        "from keelway.security.source_defaults import is_source_default\n"
        "from core.platform.signing import manifest_signer\n",
    )
    _write(tmp_path / "tests" / "test_x.py", "import core.api.routes\n")

    report = scan_migration_imports(tmp_path)
    data = report.to_dict()

    assert data["scanned_files"] == 5
    assert data["core_import_modules"]["core.models"] == 1
    assert data["core_import_modules"]["core.security"] == 1
    assert data["core_import_modules"]["core.platform"] == 1
    assert data["core_import_modules"]["core.api"] == 1
    assert data["keelway_core_import_modules"]["keelway_core.provider"] == 1
    assert data["keelway_import_modules"]["keelway.security"] == 1
    assert len(data["files_with_core_imports"]) == 3


def test_scan_ignores_excluded_dirs_and_unparseable_files(tmp_path: Path) -> None:
    _write(tmp_path / "core" / "a.py", "import core.x\n")
    _write(tmp_path / "core" / "__pycache__" / "b.py", "import core.y\n")
    _write(tmp_path / "core" / ".venv" / "c.py", "import core.z\n")
    _write(tmp_path / "core" / "broken.py", "def broken(:\n")

    report = scan_migration_imports(tmp_path)
    assert report.scanned_files == 2
    assert report.core_imports.get("core.x") == 1


def test_format_report_mentions_authority(tmp_path: Path) -> None:
    _write(tmp_path / "cli.py", "import core.config\n")
    report = scan_migration_imports(tmp_path)
    text = format_migration_report(report)
    assert "ADR-0042" in text
    assert "provisional runtime authority" in text


def test_json_serializable(tmp_path: Path) -> None:
    _write(tmp_path / "cli.py", "from core.api import routes\n")
    report = scan_migration_imports(tmp_path)
    json.dumps(report.to_dict())
