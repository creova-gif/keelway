"""
Unit tests for Keelway Mobile CLI & Pairing Management (cli.py).
"""
import pytest
from cli import cmd_mobile


@pytest.mark.asyncio
async def test_mobile_pair_command(capsys):
    rc = await cmd_mobile(action="pair", host="0.0.0.0", port=7420)
    assert rc == 0
    captured = capsys.readouterr()
    assert "KEELWAY MOBILE" in captured.out
    assert "Wi-Fi / LAN Address" in captured.out
    assert "Studio Pairing Link" in captured.out
    assert "keelway://pair?link=" in captured.out
    assert "Pairing Instructions:" in captured.out


@pytest.mark.asyncio
async def test_mobile_status_command(capsys):
    rc = await cmd_mobile(action="status", host="0.0.0.0", port=7420)
    assert rc == 0
    captured = capsys.readouterr()
    assert "PAIRING & APPROVAL STATUS" in captured.out
    assert "Local Gateway Host" in captured.out
    assert "Database Connectivity" in captured.out


@pytest.mark.asyncio
async def test_mobile_notify_command(capsys):
    rc = await cmd_mobile(
        action="notify",
        target="expo_push_token_test_abc",
        action_name="git_push_remote",
        task_id="task_test_99",
    )
    assert rc == 0
    captured = capsys.readouterr()
    assert "Dispatching mobile approval notification" in captured.out
    assert "MOBILE_APP" in captured.out
    assert "DELIVERED [OK]" in captured.out
    assert "expo_push_token_test_abc" in captured.out
