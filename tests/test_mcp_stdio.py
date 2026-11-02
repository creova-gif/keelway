import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

from core.orchestration.mcp import MCPProtocolServer, build_workspace_server, serve_stdio

REPO = Path(__file__).resolve().parents[1]


async def _run(server, lines):
    out = io.StringIO()
    await serve_stdio(server, io.StringIO("".join(json.dumps(m) + "\n" if not isinstance(m, str) else m for m in lines)), out)
    return [json.loads(line) for line in out.getvalue().splitlines()]


@pytest.mark.asyncio
async def test_handshake_notifications_and_ping():
    replies = await _run(MCPProtocolServer(), [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "ping"},
    ])
    assert [r["id"] for r in replies] == [1, 2]
    assert replies[0]["result"]["protocolVersion"] == "2025-06-18"
    assert replies[0]["result"]["serverInfo"]["name"] == "keelway"


@pytest.mark.asyncio
async def test_parse_error_and_unknown_version():
    replies = await _run(MCPProtocolServer(), [
        "{not json\n",
        {"jsonrpc": "2.0", "id": 3, "method": "initialize", "params": {"protocolVersion": "1999-01-01"}},
    ])
    assert replies[0]["error"]["code"] == -32700
    assert replies[1]["result"]["protocolVersion"] == "2025-06-18"


@pytest.mark.asyncio
async def test_tool_failure_is_reported_in_result(tmp_path):
    (tmp_path / "a.txt").write_text("hello")
    (tmp_path / ".keelway").mkdir()
    (tmp_path / ".keelway" / "keelway.db").write_text("secret")
    server = build_workspace_server(str(tmp_path))
    ok, outside, protected = await _run(server, [
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "read_file", "arguments": {"path": "a.txt"}}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "read_file", "arguments": {"path": "../../etc/passwd"}}},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "read_file", "arguments": {"path": ".keelway/keelway.db"}}},
    ])
    assert "hello" in ok["result"]["content"][0]["text"]
    assert outside["result"]["isError"] is True
    assert protected["result"]["isError"] is True and "secret" not in json.dumps(protected)


@pytest.mark.asyncio
async def test_only_read_only_tools_are_exposed(tmp_path):
    (reply,) = await _run(build_workspace_server(str(tmp_path)), [{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}])
    names = {t["name"] for t in reply["result"]["tools"]}
    assert names == {"list_files", "read_file", "git_status", "git_diff"}


def test_cli_stdout_carries_only_mcp_messages(tmp_path):
    msgs = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    ]
    proc = subprocess.run(
        [sys.executable, str(REPO / "cli.py"), "mcp", "--workspace", str(tmp_path)],
        input="".join(json.dumps(m) + "\n" for m in msgs), capture_output=True, text=True, timeout=60,
        cwd=str(REPO), env={**__import__("os").environ, "PYTHONPATH": str(REPO)},
    )
    lines = proc.stdout.splitlines()
    assert [json.loads(line)["id"] for line in lines] == [1, 2], proc.stdout + proc.stderr
