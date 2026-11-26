"""
Tests for Keelway Personal Agent Workflows.
Verifies Workflow 1: Engineering Brief Generator.
"""

import sys
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from core.main import app
from core.storage.database import init_db
from core.models.gateway import gateway, ModelGateway
from core.models.adapters.base import ModelAdapter
from core.api.schemas import (
    Provider,
    CompletionRequestSchema,
    CompletionResponseSchema,
)


class MockWorkflowAdapter(ModelAdapter):
    provider = Provider.LOCAL

    def is_available(self) -> bool:
        return True

    async def complete(self, request: CompletionRequestSchema) -> CompletionResponseSchema:
        return CompletionResponseSchema(
            content=(
                "### Summary of Changes\n"
                "This PR introduces an explicit TaskState enum and transition table to the backend.\n\n"
                "### Failing Tests\n"
                "- test_retry_on_transient_error times out.\n\n"
                "### KEELWAY.md Alignment\n"
                "Aligns with 'Prefer explicit state over opaque loops'.\n\n"
                "### Ranked Risks\n"
                "1. Timeout under transient network error.\n\n"
                "### Recommended Next Actions\n"
                "1. Fix retry timeout logic.\n\n"
                "### Citations\n"
                "- core/orchestration/state.py\n"
                "- tests/test_state.py"
            ),
            provider=self.provider,
            model="mock-brief-model",
            usage={"prompt_tokens": 200, "completion_tokens": 150, "total_tokens": 350},
            latency_ms=120.0,
            cost_usd=0.0015,
        )


@pytest_asyncio.fixture(autouse=True)
async def setup_database():
    await init_db()


@pytest.mark.asyncio
async def test_engineering_brief_endpoint():
    mock_gw = ModelGateway(adapters={Provider.LOCAL: MockWorkflowAdapter()})
    # Patch default gateway for test
    gateway.adapters = mock_gw.adapters

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "pr_title": "Add task state machine to agent backend",
            "pr_description": "New TaskState enum, transition table, retry logic",
            "files_touched": [
                "core/orchestration/state.py",
                "core/orchestration/engine.py",
                "tests/test_state.py"
            ],
            "failing_tests": ["test_retry_on_transient_error"],
            "preferred_provider": "local"
        }

        response = await client.post("/v1/workflows/engineering-brief", json=payload)
        assert response.status_code == 200
        data = response.json()

        assert data["task_id"] is not None
        assert data["state"] == "awaiting_approval"
        assert "core/orchestration/state.py" in data["citations"]
        assert "Summary of Changes" in data["brief_content"]
        assert data["cost_usd"] == 0.0015
        assert data["usage"]["total_tokens"] == 350

        # Verify task is in database via GET /v1/tasks/{id}
        res_task = await client.get(f"/v1/tasks/{data['task_id']}")
        assert res_task.status_code == 200
        task_data = res_task.json()
        assert task_data["state"] == "awaiting_approval"
        assert task_data["title"] == "Engineering Brief: Add task state machine to agent backend"


@pytest.mark.asyncio
async def test_research_summary_endpoint():
    mock_gw = ModelGateway(adapters={Provider.LOCAL: MockWorkflowAdapter()})
    gateway.adapters = mock_gw.adapters

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "document_title": "ADR-001 Shared AI Core Architecture",
            "document_content": (
                "ADR-001 proposes a shared AI Core across Keelway personal agent and Keelway Dev CLI. "
                "Adopts a 4-tier permission model and multi-provider gateway with cost arbitrage."
            ),
            "source_uri": "https://keelway.dev/adr/001",
            "store_in_memory": True,
            "memory_key": "adr_001_core",
            "preferred_provider": "local",
        }

        response = await client.post("/v1/workflows/research-summary", json=payload)
        assert response.status_code == 200
        data = response.json()

        assert data["task_id"] is not None
        assert data["memory_id"] is not None
        assert data["source_uri"] == payload["source_uri"]
        assert len(data["summary_content"]) > 0


@pytest.mark.asyncio
async def test_sandbox_test_approval_gate_enforcement():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Without human_approved=True, must be rejected with HTTP 403
        payload = {
            "test_command": "echo 'running unapproved test'",
            "human_approved": False,
        }
        response = await client.post("/v1/workflows/sandbox-test", json=payload)
        assert response.status_code == 403
        assert "Sandbox execution requires explicit human approval" in response.json()["detail"]


@pytest.mark.asyncio
async def test_sandbox_test_passing_execution():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "test_command": f"{sys.executable} -c \"print('Sandbox Test Suite: 5 passed')\"",
            "human_approved": True,
        }
        response = await client.post("/v1/workflows/sandbox-test", json=payload)
        assert response.status_code == 200
        data = response.json()

        assert data["passed"] is True
        assert data["exit_code"] == 0
        assert data["state"] == "completed"
        assert "Sandbox Test Suite: 5 passed" in data["stdout"]
        assert data["failure_analysis"] is None


@pytest.mark.asyncio
async def test_sandbox_test_failing_execution_with_llm_analysis():
    mock_gw = ModelGateway(adapters={Provider.LOCAL: MockWorkflowAdapter()})
    gateway.adapters = mock_gw.adapters

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "test_command": f"{sys.executable} -c \"raise RuntimeError('AssertionError in test_retry_transient')\"",
            "human_approved": True,
            "preferred_provider": "local",
        }
        response = await client.post("/v1/workflows/sandbox-test", json=payload)
        assert response.status_code == 200
        data = response.json()

        assert data["passed"] is False
        assert data["exit_code"] != 0
        assert data["state"] == "failed"
        assert data["failure_analysis"] is not None
        assert "RuntimeError" in data["stderr"]

