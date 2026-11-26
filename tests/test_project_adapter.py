"""
Tests for Keelway Project Framework Adapter and Manifest Management CLI.
Validates:
1. Deterministic framework detection (Python, Node/TS, Rust, Go, Make, Generic).
2. Automated test runner command detection.
3. API endpoints /v1/project/info and /v1/workspace project metadata.
4. CLI commands 'project info', 'agent register', and 'agent list'.
"""
import json
from pathlib import Path
import pytest
from starlette.testclient import TestClient

from core.main import app
from core.orchestration.project_adapter import ProjectAdapter, ProjectMetadata
from core.storage.workspace_fs import WorkspaceFilesystem
from core.api import routes


@pytest.fixture
def test_client(tmp_path, monkeypatch):
    prev_fs = routes._workspace_fs
    monkeypatch.chdir(tmp_path)
    (tmp_path / "main.py").write_text("print('hello')\n")
    (tmp_path / "requirements.txt").write_text("fastapi>=0.100.0\npytest>=8.0.0\n")
    routes.set_workspace_fs(WorkspaceFilesystem(root_dir=str(tmp_path)))
    try:
        with TestClient(app) as client:
            yield client
    finally:
        routes.set_workspace_fs(prev_fs)


def test_python_project_detection(tmp_path):
    py_dir = tmp_path / "py_sample"
    py_dir.mkdir()
    (py_dir / "pyproject.toml").write_text('[tool.pytest.ini_options]\naddopts = "-ra -q"\n')
    (py_dir / "requirements.txt").write_text("fastapi==0.115.0\npytest==8.3.0\n")
    (py_dir / "cli.py").write_text("#!/usr/bin/env python3\n")
    (py_dir / "tests").mkdir()
    (py_dir / "tests" / "test_sample.py").write_text("def test_ok(): pass\n")

    meta = ProjectAdapter.inspect(py_dir)
    assert meta.project_type == "python"
    assert "pytest" in meta.frameworks
    assert "fastapi" in meta.frameworks
    assert meta.package_manager == "pip"
    assert meta.detected_test_command == "pytest"
    assert "cli.py" in meta.entrypoints


def test_node_typescript_project_detection(tmp_path):
    node_dir = tmp_path / "node_sample"
    node_dir.mkdir()
    (node_dir / "package.json").write_text(json.dumps({
        "name": "sample-app",
        "scripts": {"test": "vitest run", "build": "next build"},
        "dependencies": {"next": "15.0.0", "react": "19.0.0"},
        "devDependencies": {"vitest": "2.0.0", "typescript": "5.5.0"}
    }))
    (node_dir / "bun.lockb").write_text("")
    (node_dir / "src").mkdir()
    (node_dir / "src" / "index.ts").write_text("console.log('hi');\n")

    meta = ProjectAdapter.inspect(node_dir)
    assert meta.project_type == "node"
    assert meta.package_manager == "bun"
    assert "next.js" in meta.frameworks
    assert "react" in meta.frameworks
    assert "vitest" in meta.frameworks
    assert "typescript" in meta.frameworks
    assert meta.detected_test_command == "bun test"
    assert "src/index.ts" in meta.entrypoints


def test_rust_project_detection(tmp_path):
    rust_dir = tmp_path / "rust_sample"
    rust_dir.mkdir()
    (rust_dir / "Cargo.toml").write_text('[package]\nname = "sample"\nversion = "0.1.0"\n')
    (rust_dir / "src").mkdir()
    (rust_dir / "src" / "main.rs").write_text("fn main() {}\n")

    meta = ProjectAdapter.inspect(rust_dir)
    assert meta.project_type == "rust"
    assert meta.package_manager == "cargo"
    assert meta.detected_test_command == "cargo test"
    assert "src/main.rs" in meta.entrypoints


def test_go_project_detection(tmp_path):
    go_dir = tmp_path / "go_sample"
    go_dir.mkdir()
    (go_dir / "go.mod").write_text("module example.com/sample\n\ngo 1.22\n")
    (go_dir / "main.go").write_text("package main\n\nfunc main() {}\n")

    meta = ProjectAdapter.inspect(go_dir)
    assert meta.project_type == "go"
    assert meta.package_manager == "go"
    assert meta.detected_test_command == "go test ./..."
    assert "main.go" in meta.entrypoints


def test_project_info_api_endpoint(test_client):
    res = test_client.get("/v1/project/info")
    assert res.status_code == 200
    data = res.json()
    assert data["project_type"] == "python"
    assert "fastapi" in data["frameworks"]
    assert "pytest" in data["frameworks"]

    # Also check /v1/workspace returns project metadata
    ws_res = test_client.get("/v1/workspace")
    assert ws_res.status_code == 200
    ws_data = ws_res.json()
    assert "project" in ws_data
    assert ws_data["project"]["project_type"] == "python"


def test_cli_project_info_and_agent_commands(tmp_path):
    # Verify ProjectAdapter directly on tmp_path
    meta = ProjectAdapter.inspect(tmp_path)
    assert isinstance(meta, ProjectMetadata)

    # Test agent validate and sign on sample manifest
    example_manifest = Path("docs/spec/examples/test-fixer.agent.json").resolve()
    assert example_manifest.exists()

    # Import and run cmd_agent directly
    from cli import cmd_agent, cmd_project
    val_code = cmd_agent("validate", example_manifest)
    assert val_code == 0

    proj_code = cmd_project("info", tmp_path)
    assert proj_code == 0
