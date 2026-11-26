"""ADR-0042 Phase 1 — package-consolidation migration diagnostics.

Scans Python sources for imports of the provisional ``core.*`` runtime and the
isolated ``keelway_core`` reference engine, tallying usage per top-level module
so the post-beta ``keelway.*`` unification (ADR-0042 Phase 2/3) can be planned
against real data. Read-only; never executes scanned code.
"""

from __future__ import annotations

import ast
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

SCAN_ROOTS = ("core", "keelway", "keelway_core", "tests", "cli.py")
EXCLUDED_DIRS = {".venv", "venv", "node_modules", "__pycache__", ".git", "dist", "build"}


@dataclass
class MigrationCheckReport:
    """Aggregate import census for ADR-0042 migration planning."""

    scanned_files: int = 0
    core_imports: Counter = field(default_factory=Counter)
    keelway_core_imports: Counter = field(default_factory=Counter)
    keelway_imports: Counter = field(default_factory=Counter)
    files_with_core_imports: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scanned_files": self.scanned_files,
            "core_import_modules": dict(self.core_imports.most_common()),
            "keelway_core_import_modules": dict(self.keelway_core_imports.most_common()),
            "keelway_import_modules": dict(self.keelway_imports.most_common()),
            "files_with_core_imports": self.files_with_core_imports,
        }


def _iter_python_files(root: Path) -> Iterable[Path]:
    if root.is_file() and root.suffix == ".py":
        yield root
        return
    for path in sorted(root.rglob("*.py")):
        if any(part in EXCLUDED_DIRS for part in path.parts):
            continue
        yield path


def _module_prefix(node: ast.AST) -> Optional[str]:
    """Return the dotted module prefix for Import/ImportFrom nodes."""
    if isinstance(node, ast.Import):
        names = [alias.name for alias in node.names]
    elif isinstance(node, ast.ImportFrom):
        if node.module is None or node.level:
            return None
        names = [node.module]
    else:
        return None
    for name in names:
        for prefix in ("core", "keelway_core", "keelway"):
            if name == prefix or name.startswith(prefix + "."):
                return name
    return None


def scan_migration_imports(repo_root: Path) -> MigrationCheckReport:
    """Census ``core.*``, ``keelway_core.*`` and ``keelway.*`` imports under ``repo_root``."""
    report = MigrationCheckReport()
    for rel in SCAN_ROOTS:
        target = repo_root / rel
        if not target.exists():
            continue
        for py_file in _iter_python_files(target):
            report.scanned_files += 1
            try:
                tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
            except (OSError, SyntaxError, UnicodeDecodeError):
                continue
            file_has_core = False
            for node in ast.walk(tree):
                module = _module_prefix(node)
                if module is None:
                    continue
                top = module.split(".", 1)[0]
                second = module.split(".")[1] if "." in module else ""
                key = f"{top}.{second}" if second else top
                if top == "core":
                    report.core_imports[key] += 1
                    file_has_core = True
                elif top == "keelway_core":
                    report.keelway_core_imports[key] += 1
                elif top == "keelway":
                    report.keelway_imports[key] += 1
            if file_has_core:
                report.files_with_core_imports.append(str(py_file.relative_to(repo_root)))
    return report


def format_migration_report(report: MigrationCheckReport) -> str:
    """Human-readable summary for ``keelway doctor --migration-check``."""
    lines = [
        "ADR-0042 Package Consolidation — Import Census",
        f"  Scanned files: {report.scanned_files}",
        f"  Files importing core.*: {len(report.files_with_core_imports)}",
        "",
        "  core.* imports by module (top 15):",
    ]
    for module, count in report.core_imports.most_common(15):
        lines.append(f"    {count:>5}  {module}")
    if report.keelway_core_imports:
        lines += ["", "  keelway_core.* imports (reference engine — isolated by design):"]
        for module, count in report.keelway_core_imports.most_common(10):
            lines.append(f"    {count:>5}  {module}")
    lines += [
        "",
        "  Authority (ADR-0042): core/ is provisional runtime authority;",
        "  keelway/ owns enterprise governance primitives; keelway_core/ is",
        "  the isolated reference engine. Physical consolidation is Phase 2/3.",
    ]
    return "\n".join(lines)
