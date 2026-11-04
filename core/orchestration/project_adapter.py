"""
Keelway Project & Framework Adapter.
Deterministically inspects workspace repositories to detect project runtime,
frameworks, package managers, entrypoints, and automated test runners.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class ProjectMetadata:
    root_path: str
    project_type: str  # python, node, rust, go, make, generic
    frameworks: List[str] = field(default_factory=list)
    package_manager: Optional[str] = None
    detected_test_command: Optional[str] = None
    entrypoints: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    has_git: bool = False
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ProjectAdapter:
    """Detects and adapts project frameworks in a given directory."""

    @classmethod
    def inspect(cls, root: str | Path) -> ProjectMetadata:
        root_path = Path(root).resolve()
        if not root_path.exists() or not root_path.is_dir():
            return ProjectMetadata(
                root_path=str(root_path),
                project_type="generic",
                summary="Directory does not exist or is not accessible.",
            )

        has_git = (root_path / ".git").is_dir()

        # Check Python
        py_meta = cls._inspect_python(root_path)
        if py_meta:
            py_meta.has_git = has_git
            return py_meta

        # Check Node / TypeScript
        node_meta = cls._inspect_node(root_path)
        if node_meta:
            node_meta.has_git = has_git
            return node_meta

        # Check Rust
        rust_meta = cls._inspect_rust(root_path)
        if rust_meta:
            rust_meta.has_git = has_git
            return rust_meta

        # Check Go
        go_meta = cls._inspect_go(root_path)
        if go_meta:
            go_meta.has_git = has_git
            return go_meta

        # Check Makefile
        make_meta = cls._inspect_make(root_path)
        if make_meta:
            make_meta.has_git = has_git
            return make_meta

        return ProjectMetadata(
            root_path=str(root_path),
            project_type="generic",
            frameworks=[],
            package_manager=None,
            detected_test_command=None,
            entrypoints=cls._find_common_entrypoints(root_path),
            has_git=has_git,
            summary="Generic workspace (no specific language manifest recognized)",
        )

    @classmethod
    def _inspect_python(cls, root: Path) -> Optional[ProjectMetadata]:
        py_indicators = [
            root / "pyproject.toml",
            root / "setup.py",
            root / "setup.cfg",
            root / "requirements.txt",
            root / "Pipfile",
            root / "poetry.lock",
        ]
        has_py_indicator = any(p.exists() for p in py_indicators)
        py_files = list(root.glob("*.py"))
        if not has_py_indicator and not py_files:
            return None

        frameworks: List[str] = []
        dependencies: List[str] = []
        pkg_manager = "pip"

        # Check virtualenv
        venv_python: Optional[str] = None
        for venv_name in [".venv", "venv", "env"]:
            bin_py = root / venv_name / "bin" / "python"
            if bin_py.exists():
                venv_python = str(bin_py)
                break

        # Check requirements or pyproject
        req_file = root / "requirements.txt"
        if req_file.exists():
            try:
                content = req_file.read_text(encoding="utf-8", errors="ignore")
                for line in content.splitlines():
                    cleaned = line.split("==")[0].split(">=")[0].split("#")[0].strip()
                    if cleaned:
                        dependencies.append(cleaned)
            except Exception:
                pass

        if (root / "poetry.lock").exists():
            pkg_manager = "poetry"
        elif (root / "Pipfile").exists():
            pkg_manager = "pipenv"
        elif (root / "uv.lock").exists():
            pkg_manager = "uv"

        # Framework detection
        dep_str = " ".join(dependencies).lower()
        if (root / "pyproject.toml").exists():
            try:
                dep_str += " " + (root / "pyproject.toml").read_text(encoding="utf-8", errors="ignore").lower()
            except Exception:
                pass

        if "pytest" in dep_str or (root / "pytest.ini").exists():
            frameworks.append("pytest")
        if "fastapi" in dep_str:
            frameworks.append("fastapi")
        if "flask" in dep_str:
            frameworks.append("flask")
        if "django" in dep_str:
            frameworks.append("django")
        if "torch" in dep_str or "pytorch" in dep_str:
            frameworks.append("pytorch")

        # Test command
        test_cmd = None
        has_tests_dir = (root / "tests").is_dir()
        has_test_files = bool(list(root.glob("test_*.py")) or list(root.glob("*_test.py")))

        if "pytest" in frameworks or (root / "pytest.ini").exists() or (root / "tests").is_dir():
            test_cmd = "pytest"
        elif has_test_files:
            # Check for unittest vs pytest
            first_test = next(root.glob("test_*.py"), None)
            if first_test:
                test_cmd = f"python3 -m unittest -q {first_test.name}"
            else:
                test_cmd = "python3 -m unittest discover"
        elif has_tests_dir:
            test_cmd = "python3 -m unittest discover"

        # Find entrypoints
        entrypoints = []
        for name in ["main.py", "app.py", "server.py", "cli.py", "manage.py"]:
            if (root / name).exists():
                entrypoints.append(name)

        summary = f"Python project ({pkg_manager})"
        if frameworks:
            summary += f" using {', '.join(frameworks)}"

        return ProjectMetadata(
            root_path=str(root),
            project_type="python",
            frameworks=frameworks,
            package_manager=pkg_manager,
            detected_test_command=test_cmd,
            entrypoints=entrypoints,
            dependencies=dependencies[:20],
            summary=summary,
        )

    @classmethod
    def _inspect_node(cls, root: Path) -> Optional[ProjectMetadata]:
        pkg_json = root / "package.json"
        if not pkg_json.exists():
            return None

        frameworks: List[str] = []
        dependencies: List[str] = []
        test_cmd: Optional[str] = None
        pkg_manager = "npm"

        if (root / "bun.lockb").exists() or (root / "bun.lock").exists():
            pkg_manager = "bun"
        elif (root / "pnpm-lock.yaml").exists():
            pkg_manager = "pnpm"
        elif (root / "yarn.lock").exists():
            pkg_manager = "yarn"

        try:
            data = json.loads(pkg_json.read_text(encoding="utf-8"))
            scripts = data.get("scripts", {})
            if "test" in scripts:
                script_val = scripts["test"]
                if "no test specified" not in script_val.lower():
                    test_cmd = f"{pkg_manager} test"

            all_deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
            dependencies = list(all_deps.keys())

            dep_str = " ".join(dependencies).lower()
            if "next" in dep_str:
                frameworks.append("next.js")
            if "react" in dep_str:
                frameworks.append("react")
            if "vue" in dep_str:
                frameworks.append("vue")
            if "svelte" in dep_str:
                frameworks.append("svelte")
            if "vitest" in dep_str:
                frameworks.append("vitest")
            if "jest" in dep_str:
                frameworks.append("jest")
            if "typescript" in dep_str or (root / "tsconfig.json").exists():
                frameworks.append("typescript")
            if "tailwindcss" in dep_str:
                frameworks.append("tailwind")
            if "express" in dep_str:
                frameworks.append("express")
        except Exception:
            pass

        entrypoints = []
        for name in ["src/index.ts", "src/main.ts", "src/index.js", "index.js", "app/page.tsx", "src/App.tsx"]:
            if (root / name).exists():
                entrypoints.append(name)

        summary = f"Node.js project ({pkg_manager})"
        if frameworks:
            summary += f" using {', '.join(frameworks)}"

        return ProjectMetadata(
            root_path=str(root),
            project_type="node",
            frameworks=frameworks,
            package_manager=pkg_manager,
            detected_test_command=test_cmd or f"{pkg_manager} test",
            entrypoints=entrypoints,
            dependencies=dependencies[:20],
            summary=summary,
        )

    @classmethod
    def _inspect_rust(cls, root: Path) -> Optional[ProjectMetadata]:
        cargo = root / "Cargo.toml"
        if not cargo.exists():
            return None

        frameworks = ["cargo"]
        entrypoints = []
        for name in ["src/main.rs", "src/lib.rs"]:
            if (root / name).exists():
                entrypoints.append(name)

        return ProjectMetadata(
            root_path=str(root),
            project_type="rust",
            frameworks=frameworks,
            package_manager="cargo",
            detected_test_command="cargo test",
            entrypoints=entrypoints,
            summary="Rust crate (cargo)",
        )

    @classmethod
    def _inspect_go(cls, root: Path) -> Optional[ProjectMetadata]:
        gomod = root / "go.mod"
        if not gomod.exists():
            return None

        entrypoints = []
        for name in ["main.go", "cmd/main.go"]:
            if (root / name).exists():
                entrypoints.append(name)

        return ProjectMetadata(
            root_path=str(root),
            project_type="go",
            frameworks=["go-modules"],
            package_manager="go",
            detected_test_command="go test ./...",
            entrypoints=entrypoints,
            summary="Go module",
        )

    @classmethod
    def _inspect_make(cls, root: Path) -> Optional[ProjectMetadata]:
        makefile = root / "Makefile"
        if not makefile.exists():
            return None

        has_test_target = False
        try:
            content = makefile.read_text(encoding="utf-8", errors="ignore")
            for line in content.splitlines():
                if line.strip().startswith("test:"):
                    has_test_target = True
                    break
        except Exception:
            pass

        return ProjectMetadata(
            root_path=str(root),
            project_type="make",
            frameworks=["make"],
            package_manager="make",
            detected_test_command="make test" if has_test_target else None,
            entrypoints=["Makefile"],
            summary="Makefile-driven project",
        )

    @classmethod
    def _find_common_entrypoints(cls, root: Path) -> List[str]:
        candidates = ["README.md", "main.py", "index.js", "index.html", "Makefile"]
        return [c for c in candidates if (root / c).exists()]
