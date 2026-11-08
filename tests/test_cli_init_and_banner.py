"""Unit tests for Keelway CLI banner artwork and top-level `keelway init` workflow."""

import json
import os
import subprocess
from pathlib import Path
import pytest

from cli import get_banner, print_banner, cmd_init, main, build_parser


def test_banner_ascii_fallback_and_unicode():
    """Verify banner returns ASCII fallback when plain=True, and unicode otherwise."""
    ascii_banner = get_banner(plain=True, use_color=False)
    assert "_  ______ _____ _ __" in ascii_banner
    assert "Sovereign Local-First AI Developer Platform" in ascii_banner
    assert "Sorvex Labs" in ascii_banner
    assert "https://keelway.dev" in ascii_banner
    assert "\033[" not in ascii_banner

    # Test with color disabled
    banner_no_color = get_banner(plain=False, use_color=False)
    assert "\033[" not in banner_no_color
    assert "Sovereign Local-First AI Developer Platform" in banner_no_color


def test_banner_respects_no_color(monkeypatch):
    """Verify get_banner honors NO_COLOR environment variable."""
    monkeypatch.setenv("NO_COLOR", "1")
    banner = get_banner()
    assert "\033[" not in banner


def test_cli_no_args_prints_banner_and_essential_commands(capsys):
    """Calling main([]) should display banner, essential commands, and exit 0."""
    ret = main([])
    assert ret == 0
    captured = capsys.readouterr()
    assert "Sovereign Local-First AI Developer Platform" in captured.out
    assert "Essential Commands:" in captured.out
    assert "init" in captured.out
    assert "dev" in captured.out
    assert "doctor" in captured.out
    assert "chat" in captured.out


def test_cli_parser_has_init_subcommand():
    """Verify build_parser includes top-level init command."""
    parser = build_parser()
    parsed = parser.parse_args(["init", "--model", "custom-model"])
    assert parsed.command == "init"
    assert parsed.model == "custom-model"


def test_cmd_init_non_git_workspace(tmp_path: Path):
    """Test cmd_init creates .keelway/ directory and config.json in a non-git directory."""
    ws = tmp_path / "sample_project"
    ws.mkdir()

    ret = cmd_init(path=ws, quiet=True)
    assert ret == 0

    keelway_dir = ws / ".keelway"
    assert keelway_dir.is_dir()
    assert (keelway_dir / "evidence").is_dir()
    assert (keelway_dir / "logs").is_dir()

    cfg_file = keelway_dir / "config.json"
    assert cfg_file.is_file()

    cfg = json.loads(cfg_file.read_text(encoding="utf-8"))
    assert cfg["version"] == "1.0.0"
    assert cfg["workspace"]["name"] == "sample_project"
    assert cfg["workspace"]["git_enabled"] is False
    assert cfg["runtime"]["default_provider"] == "local"
    assert "local_model" in cfg["runtime"]
    assert "sandbox_backend" in cfg["security"]
    assert cfg["security"]["require_approval_for_destructive"] is True


def test_cmd_init_git_workspace(tmp_path: Path):
    """Test cmd_init detects git repository and branch in git directory."""
    ws = tmp_path / "git_project"
    ws.mkdir()
    (ws / ".git").mkdir()

    ret = cmd_init(path=ws, model="qwen2.5-coder:7b", quiet=True)
    assert ret == 0

    cfg_file = ws / ".keelway" / "config.json"
    assert cfg_file.is_file()

    cfg = json.loads(cfg_file.read_text(encoding="utf-8"))
    assert cfg["workspace"]["git_enabled"] is True
    assert cfg["runtime"]["local_model"] == "qwen2.5-coder:7b"


def test_cmd_init_idempotency_and_update(tmp_path: Path):
    """Test running init twice updates configuration non-destructively without error."""
    ws = tmp_path / "idempotent_project"
    ws.mkdir()

    # Initial run
    assert cmd_init(path=ws, model="test-model-1", quiet=True) == 0
    cfg1 = json.loads((ws / ".keelway" / "config.json").read_text(encoding="utf-8"))
    assert cfg1["runtime"]["local_model"] == "test-model-1"

    # Second run with different model override
    assert cmd_init(path=ws, model="test-model-2", quiet=True) == 0
    cfg2 = json.loads((ws / ".keelway" / "config.json").read_text(encoding="utf-8"))
    assert cfg2["runtime"]["local_model"] == "test-model-2"
