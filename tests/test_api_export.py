"""
Tests for Keelway OpenAPI 3.1 schema export CLI subcommand and generator.
"""

import json
from pathlib import Path
import pytest

from cli import build_parser, cmd_openapi, main


def test_cmd_openapi_export_file(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """Test exporting OpenAPI schema to a file in a temporary directory."""
    out_file = tmp_path / "openapi.json"
    rc = cmd_openapi(out_path=out_file, to_stdout=False)
    assert rc == 0

    assert out_file.exists(), "Exported OpenAPI JSON file should exist"

    raw_content = out_file.read_text(encoding="utf-8")
    schema = json.loads(raw_content)

    # Validate OpenAPI specifications
    assert schema["openapi"].startswith("3."), f"Expected OpenAPI 3.x, got {schema['openapi']}"
    assert schema["info"]["title"] == "Keelway Core"
    assert len(schema["paths"]) >= 115, f"Expected at least 115 endpoints, got {len(schema['paths'])}"

    # Validate presence of key core and system endpoints
    key_endpoints = [
        "/v1/kstack/skills",
        "/v1/tasks",
        "/v1/doctor",
    ]
    for endpoint in key_endpoints:
        assert endpoint in schema["paths"], f"Endpoint '{endpoint}' missing from OpenAPI schema"

    captured = capsys.readouterr()
    assert "[+] Exported OpenAPI 3.1 schema" in captured.out
    assert str(out_file) in captured.out


def test_cmd_openapi_to_stdout(capsys: pytest.CaptureFixture) -> None:
    """Test streaming OpenAPI schema directly to stdout."""
    rc = cmd_openapi(to_stdout=True)
    assert rc == 0

    captured = capsys.readouterr()
    schema = json.loads(captured.out)
    assert schema["openapi"].startswith("3.")
    assert schema["info"]["title"] == "Keelway Core"
    assert "/v1/kstack/skills" in schema["paths"]


def test_cli_parser_openapi_subcommands() -> None:
    """Verify that build_parser properly wires the openapi and api export subcommands."""
    parser = build_parser()

    # 1. Test 'openapi' with default args
    args_default = parser.parse_args(["openapi"])
    assert args_default.command == "openapi"
    assert args_default.out == Path("website/openapi.json")
    assert not args_default.stdout

    # 2. Test 'openapi' with custom args
    args_custom = parser.parse_args(["openapi", "--out", "/tmp/schema.json", "--stdout"])
    assert args_custom.command == "openapi"
    assert args_custom.out == Path("/tmp/schema.json")
    assert args_custom.stdout is True

    # 3. Test 'api export' alias
    args_api = parser.parse_args(["api", "export", "--out", "dist/api.json"])
    assert args_api.command == "api"
    assert args_api.api_command == "export"
    assert args_api.out == Path("dist/api.json")
    assert not args_api.stdout


def test_cli_main_openapi_execution(tmp_path: Path) -> None:
    """Verify main entrypoint dispatches openapi subcommand and exits 0."""
    target = tmp_path / "sub" / "openapi.json"
    with pytest.raises(SystemExit) as exc_info:
        main(["openapi", "--out", str(target)])
    assert exc_info.value.code == 0
    assert target.exists()
    schema = json.loads(target.read_text(encoding="utf-8"))
    assert schema["info"]["title"] == "Keelway Core"
