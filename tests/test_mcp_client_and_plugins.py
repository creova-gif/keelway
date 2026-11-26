"""
Tests for Keelway Universal Model Context Protocol (MCP) Client & Plugin Extension Architecture (WP14).
Validates JSON-RPC handshake, tool discovery, tool invocation, stdio transports,
PluginManifest digest integrity, PluginManager lifecycle, agent loop tool mounting, and API endpoints.
"""
import sys
import pytest
from fastapi.testclient import TestClient

from core.orchestration.mcp import MCPProtocolServer
from core.orchestration.mcp_client import MCPClient, MCPClientManager
from core.plugins.manifest import PluginManifest, PluginPermissions
from core.plugins.manager import PluginManager
from core.orchestration.agent_loop import AutonomousAgentLoop, AutonomyPolicy
from core.storage.workspace_fs import WorkspaceFilesystem
from core.main import app


@pytest.fixture
def mock_mcp_server():
    """Create an in-process MCPProtocolServer exposing sample math and echo tools."""
    server = MCPProtocolServer()

    async def _add(args):
        a = args.get("a", 0)
        b = args.get("b", 0)
        return {"result": a + b}

    async def _echo(args):
        return {"echo": args.get("message", "")}

    server.register_tool(
        "add_numbers",
        "Add two numbers together",
        {"type": "object", "properties": {"a": {"type": "number"}, "b": {"type": "number"}}, "required": ["a", "b"]},
        _add,
    )
    server.register_tool(
        "echo_message",
        "Echo a message string",
        {"type": "object", "properties": {"message": {"type": "string"}}, "required": ["message"]},
        _echo,
    )
    return server


@pytest.mark.asyncio
async def test_mcp_client_in_process_handshake_and_tools(mock_mcp_server):
    client = MCPClient(
        server_id="in_proc_math",
        in_process_server=mock_mcp_server,
    )
    assert not client.initialized
    await client.connect()
    assert client.initialized
    assert "add_numbers" in client.discovered_tools
    assert "echo_message" in client.discovered_tools

    # Call tool
    res_add = await client.call_tool("add_numbers", {"a": 12, "b": 30})
    assert res_add.get("result") == 42

    res_echo = await client.call_tool("echo_message", {"message": "Hello Keelway"})
    assert res_echo.get("echo") == "Hello Keelway"

    await client.disconnect()
    assert not client.initialized


@pytest.mark.asyncio
async def test_mcp_client_stdio_subprocess(tmp_path):
    """Test standard subprocess stdio transport using a minimal Python stdio server."""
    server_script = tmp_path / "mock_mcp_stdio.py"
    server_script.write_text("""
import sys, json

while True:
    line = sys.stdin.readline()
    if not line:
        break
    req = json.loads(line)
    method = req.get("method")
    msg_id = req.get("id")

    if method == "initialize":
        res = {"protocolVersion": "2025-06-18", "serverInfo": {"name": "mock-stdio-server", "version": "1.0"}}
    elif method == "notifications/initialized":
        continue
    elif method == "tools/list":
        res = {
            "tools": [
                {
                    "name": "multiply",
                    "description": "Multiply two numbers",
                    "inputSchema": {"type": "object", "properties": {"x": {"type": "number"}, "y": {"type": "number"}}}
                }
            ]
        }
    elif method == "tools/call":
        args = req.get("params", {}).get("arguments", {})
        res = {"product": args.get("x", 0) * args.get("y", 0)}
    else:
        res = {"status": "ok"}

    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": msg_id, "result": res}) + "\\n")
    sys.stdout.flush()
""")

    client = MCPClient(
        server_id="stdio_math",
        command=sys.executable,
        args=[str(server_script)],
    )
    await client.connect()
    assert client.initialized
    assert "multiply" in client.discovered_tools

    res = await client.call_tool("multiply", {"x": 6, "y": 7})
    assert res.get("product") == 42

    await client.disconnect()
    assert client.proc is None


@pytest.mark.asyncio
async def test_mcp_mount_into_agent_loop(mock_mcp_server, tmp_path):
    """Verify MCP tools can be mounted into AutonomousAgentLoop and called as native tools."""
    client = MCPClient(
        server_id="calc",
        in_process_server=mock_mcp_server,
    )
    manager = MCPClientManager()
    await manager.connect_client(client)

    fs = WorkspaceFilesystem(root_dir=str(tmp_path))
    agent = AutonomousAgentLoop(task_id="test_mcp_agent", workspace_fs=fs, policy=AutonomyPolicy.AUTONOMOUS)

    mounted_count = manager.mount_tools_into_agent_loop(agent, prefix_server=True)
    assert mounted_count >= 2
    assert "calc__add_numbers" in agent.tools

    tool = agent.tools["calc__add_numbers"]
    out = await tool.handler({"a": 100, "b": 50})
    assert out.get("result") == 150

    await manager.disconnect_all()


def test_plugin_manifest_digest_integrity():
    manifest = PluginManifest(
        name="git-enhanced",
        version="1.2.0",
        description="Enhanced git operations and blame intelligence",
        author="Sorvex Labs",
        capabilities=["git", "ast"],
        mcp_servers={"git-srv": {"command": "python", "args": ["-m", "git_srv"]}},
        permissions=PluginPermissions(read_paths=["**"], write_paths=["src/**"]),
    )
    digest = manifest.calculate_digest()
    assert len(digest) == 64
    assert manifest.digest_sha256 == digest

    # Serialization and deserialization roundtrip
    data = manifest.to_dict()
    loaded = PluginManifest.from_dict(data)
    assert loaded.name == "git-enhanced"
    assert loaded.calculate_digest() == digest


@pytest.mark.asyncio
async def test_plugin_manager_install_and_lifecycle(tmp_path):
    pm = PluginManager(plugins_dir=tmp_path / "plugins")

    manifest = PluginManifest(
        name="linter-plugin",
        version="0.1.0",
        description="Fast local code linter extension",
        author="Community",
        mcp_servers={},  # Empty for lightweight test
    )

    # 1. Install
    rec = await pm.install_plugin(manifest, activate=True)
    assert rec.status == "ACTIVE"
    assert rec.manifest.name == "linter-plugin"
    assert (tmp_path / "plugins" / "linter-plugin" / "plugin.json").exists()

    # 2. List
    plugins = pm.list_plugins()
    assert any(p["name"] == "linter-plugin" for p in plugins)

    # 3. Deactivate
    rec_deact = await pm.deactivate_plugin("linter-plugin")
    assert rec_deact.status == "DISABLED"

    # 4. Uninstall
    success = await pm.uninstall_plugin("linter-plugin")
    assert success is True
    assert not (tmp_path / "plugins" / "linter-plugin").exists()


@pytest.mark.asyncio
async def test_plugin_api_routes(tmp_path):
    client = TestClient(app)

    manifest_payload = {
        "name": "sample-tool-extension",
        "version": "1.0.0",
        "description": "Test plugin for API verification",
        "author": "Keelway Core",
        "capabilities": ["testing"],
        "mcp_servers": {},
        "permissions": {"read_paths": ["**"], "write_paths": []},
    }

    # 1. Install plugin
    res_install = client.post("/v1/plugins/install", json={"manifest": manifest_payload, "activate": True})
    assert res_install.status_code == 200
    data = res_install.json()
    assert data["name"] == "sample-tool-extension"
    assert data["status"] == "ACTIVE"

    # 2. List plugins
    res_list = client.get("/v1/plugins")
    assert res_list.status_code == 200
    plugins = res_list.json()
    assert any(p["name"] == "sample-tool-extension" for p in plugins)

    # 3. Deactivate plugin
    res_deact = client.post("/v1/plugins/sample-tool-extension/deactivate")
    assert res_deact.status_code == 200
    assert res_deact.json()["status"] == "DISABLED"

    # 4. Activate plugin
    res_act = client.post("/v1/plugins/sample-tool-extension/activate")
    assert res_act.status_code == 200
    assert res_act.json()["status"] == "ACTIVE"

    # 5. Delete plugin
    res_del = client.delete("/v1/plugins/sample-tool-extension")
    assert res_del.status_code == 200
    assert res_del.json()["status"] == "uninstalled"
