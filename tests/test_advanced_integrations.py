import pytest
from core.security.telemetry import TelemetryTracer
from core.orchestration.mcp import MCPProtocolServer
from core.orchestration.worktree import EphemeralWorktreeManager
from pathlib import Path


def test_opentelemetry_genai_semantic_tracer():
    tracer = TelemetryTracer(service_name="kora-test")
    span = tracer.start_span(
        name="chat_completion",
        system="local",
        request_model="qwen3.5:latest",
        air_gapped=True,
    )
    assert span.trace_id is not None
    assert span.attributes["gen_ai.system"] == "local"
    assert span.attributes["gen_ai.air_gapped"] is True

    attrs = tracer.end_span(
        span=span,
        response_model="qwen3.5:latest",
        input_tokens=150,
        output_tokens=75,
        duration_ms=420.5,
        status="OK",
    )
    assert attrs["gen_ai.usage.input_tokens"] == 150
    assert attrs["gen_ai.usage.output_tokens"] == 75
    assert attrs["gen_ai.client.operation.duration_ms"] == 420.5


@pytest.mark.asyncio
async def test_mcp_protocol_server_tools_and_resources():
    server = MCPProtocolServer()

    # Register a tool
    async def mock_handler(params):
        return {"result": f"Echo: {params.get('msg')}"}

    server.register_tool(
        name="echo_tool",
        description="Echoes message",
        parameters_schema={"type": "object", "properties": {"msg": {"type": "string"}}},
        handler=mock_handler,
    )

    # Register a resource
    server.register_resource(
        uri="kora-memory://project/adr-001",
        name="ADR-001 Memory Chunk",
        description="Core architecture principles",
    )

    # Test tools/list
    res_tools = await server.handle_jsonrpc_request({"id": 1, "method": "tools/list"})
    assert len(res_tools["result"]["tools"]) == 1
    assert res_tools["result"]["tools"][0]["name"] == "echo_tool"

    # Test resources/list
    res_resources = await server.handle_jsonrpc_request({"id": 2, "method": "resources/list"})
    assert len(res_resources["result"]["resources"]) == 1
    assert res_resources["result"]["resources"][0]["uri"] == "kora-memory://project/adr-001"

    # Test tools/call
    res_call = await server.handle_jsonrpc_request({
        "id": 3,
        "method": "tools/call",
        "params": {"name": "echo_tool", "arguments": {"msg": "Sovereign AI"}},
    })
    assert "Sovereign AI" in res_call["result"]["content"][0]["text"]


@pytest.mark.asyncio
async def test_ephemeral_git_worktree_lifecycle():
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)
        manager = EphemeralWorktreeManager(repo_root=repo_root)

        session = await manager.create_worktree("task_test_42")
        assert session.worktree_dir.exists()
        assert "agent_task_test_42" in session.worktree_dir.name

        # Verify command execution in isolated worktree directory
        code, out, _ = await session.run_command("pwd")
        assert code == 0
        assert str(session.worktree_dir) in out

        # Teardown
        cleaned = await manager.remove_worktree(session, delete_branch=False)
        assert cleaned is True
        assert not session.worktree_dir.exists()
