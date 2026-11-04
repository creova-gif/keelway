"""
Tests for unified Keelway Audit CLI: export, verify, and head anchoring commands.
"""
import pytest
from pathlib import Path

from cli import cmd_record
from core.security import record_format as rf


@pytest.mark.asyncio
async def test_audit_cli_anchor_export_and_verify(tmp_path, monkeypatch):
    # Set signing key for test environment
    monkeypatch.chdir(tmp_path)
    signing_key = tmp_path / ".keelway" / "agent_signing.key"
    signing_key.parent.mkdir(parents=True, exist_ok=True)
    signing_key.write_text("test_secret_key_audit_cli_2026")

    # 1. Anchor audit head
    anchor_file = tmp_path / "head.anchor.json"
    res_anchor = await cmd_record("anchor", path=anchor_file)
    assert res_anchor == 0
    assert anchor_file.exists()

    # 2. Export audit log
    export_file = tmp_path / "audit.jsonl"
    res_export = await cmd_record("export", path=export_file)
    assert res_export == 0
    assert export_file.exists()

    # 3. Verify audit log without anchor
    res_verify = await cmd_record("verify", path=export_file)
    assert res_verify == 0

    # 4. Verify audit log with anchor cross-verification
    res_verify_anchor = await cmd_record("verify", path=export_file, anchor=anchor_file)
    assert res_verify_anchor == 0
