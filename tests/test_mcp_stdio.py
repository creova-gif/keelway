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


def _call(i, name, args):
    return {"jsonrpc": "2.0", "id": i, "method": "tools/call", "params": {"name": name, "arguments": args}}


@pytest.mark.asyncio
async def test_credentials_files_are_refused_and_hidden(tmp_path):
    (tmp_path / ".env").write_text("OPENAI_API_KEY=sk-live")
    (tmp_path / "deploy.pem").write_text("-----BEGIN KEY-----")
    (tmp_path / ".env.example").write_text("OPENAI_API_KEY=")
    (tmp_path / "app.py").write_text("x = 1")
    server = build_workspace_server(str(tmp_path))
    env, pem, example, tree = await _run(server, [
        _call(1, "read_file", {"path": ".env"}), _call(2, "read_file", {"path": "deploy.pem"}),
        _call(3, "read_file", {"path": ".env.example"}), _call(4, "list_files", {}),
    ])
    assert env["result"]["isError"] and pem["result"]["isError"]
    assert "sk-live" not in json.dumps(env)
    assert not example["result"].get("isError")
    listing = tree["result"]["content"][0]["text"]
    assert "app.py" in listing and "deploy.pem" not in listing


@pytest.mark.asyncio
async def test_symlinks_into_protected_dirs_are_pruned(tmp_path):
    (tmp_path / ".keelway").mkdir()
    (tmp_path / ".keelway" / "rules.json").write_text("{}")
    (tmp_path / "state").symlink_to(tmp_path / ".keelway")
    (tmp_path / "creds").symlink_to(tmp_path / ".env")
    (tmp_path / ".env").write_text("TOKEN=abc")
    server = build_workspace_server(str(tmp_path))
    tree, read, creds = await _run(server, [
        _call(1, "list_files", {}), _call(2, "read_file", {"path": "state/rules.json"}),
        _call(3, "read_file", {"path": "creds"}),
    ])
    assert "rules.json" not in tree["result"]["content"][0]["text"]
    assert read["result"]["isError"] and creds["result"]["isError"]


@pytest.mark.asyncio
async def test_git_diff_excludes_protected_and_secret_files(tmp_path):
    def git(*a):
        subprocess.run(["git", *a], cwd=tmp_path, check=True, capture_output=True)
    git("init", "-q")
    git("config", "user.email", "t@t")
    git("config", "user.name", "t")
    (tmp_path / ".keelway").mkdir()
    for f in (".keelway/rules.json", ".env", "app.py", ".env.example", "cfg/prod.key", "my keys/.env"):
        (tmp_path / f).parent.mkdir(exist_ok=True)
        (tmp_path / f).write_text("old\n")
    git("add", "-A")
    git("commit", "-qm", "init")
    for f in (".keelway/rules.json", ".env", "app.py", ".env.example", "cfg/prod.key", "my keys/.env"):
        (tmp_path / f).write_text(f"new-{f}\n")
    (reply,) = await _run(build_workspace_server(str(tmp_path)), [_call(1, "git_diff", {})])
    diff = reply["result"]["content"][0]["text"]
    assert "new-app.py" in diff
    assert "new-.keelway" not in diff and "new-.env\n" not in diff and "new-cfg/prod.key" not in diff
    assert "new-.env.example" in diff and "new-my keys" not in diff


@pytest.mark.asyncio
async def test_malformed_messages_do_not_end_the_session():
    replies = await _run(MCPProtocolServer(), [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": [1, 2]},
        {"jsonrpc": "2.0", "id": 2, "method": "initialize", "params": {"protocolVersion": ["2025-06-18"]}},
        [],
        {"jsonrpc": "2.0", "id": 3, "method": "ping"},
    ])
    assert replies[0]["error"]["code"] == -32602
    assert replies[1]["result"]["protocolVersion"] == "2025-06-18"
    assert replies[2]["error"]["code"] == -32600
    assert replies[3] == {"jsonrpc": "2.0", "id": 3, "result": {}}


@pytest.mark.asyncio
async def test_git_diff_in_workspace_below_repo_root(tmp_path):
    def git(*a):
        subprocess.run(["git", *a], cwd=tmp_path, check=True, capture_output=True)
    git("init", "-q")
    git("config", "user.email", "t@t")
    git("config", "user.name", "t")
    ws = tmp_path / "service"
    ws.mkdir()
    for f in ("service/app.py", "service/.env", "other.py"):
        (tmp_path / f).write_text("old\n")
    git("add", "-A")
    git("commit", "-qm", "init")
    for f in ("service/app.py", "service/.env", "other.py"):
        (tmp_path / f).write_text(f"new-{f}\n")
    (reply,) = await _run(build_workspace_server(str(ws)), [_call(1, "git_diff", {})])
    diff = reply["result"]["content"][0]["text"]
    assert "new-service/app.py" in diff
    assert "new-service/.env" not in diff and "new-other.py" not in diff
