import pytest
import pytest_asyncio
import uvicorn
import asyncio
from core.main import app
from core.sdk import (
    KeelwayClient,
    AsyncKeelwayClient,
    AuthenticationError,
    PolicyViolationError,
    TaskNotFoundError,
    AirGapEgressError,
)
from core.security.auth import launch_token


@pytest.fixture(scope="module")
def local_server():
    """Runs a live instance of the Keelway FastAPI app on loopback for SDK testing."""
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()

    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    loop = asyncio.new_event_loop()

    import threading
    t = threading.Thread(target=lambda: loop.run_until_complete(server.serve()), daemon=True)
    t.start()

    # Wait until live
    import time
    base_url = f"http://127.0.0.1:{port}"
    for _ in range(50):
        try:
            import httpx
            r = httpx.get(f"{base_url}/health", timeout=1.0)
            if r.status_code == 200:
                break
        except Exception:
            time.sleep(0.05)
    else:
        raise RuntimeError("Local test server failed to start")

    yield base_url
    server.should_exit = True
    t.join(timeout=2.0)


@pytest.fixture
def auth_token():
    return launch_token()


def test_sdk_system_health_and_doctor(local_server, auth_token):
    client = KeelwayClient(base_url=local_server, token=auth_token)
    health = client.get_health()
    assert health["status"] == "ok"
    assert health["database_connected"] is True

    status = client.get_status()
    assert status["database_connected"] is True
    assert "version" in status

    doctor = client.run_doctor()
    assert doctor["overall_status"] == "HEALTHY"
    assert len(doctor["sections"]) == 7
    client.close()


@pytest.mark.asyncio
async def test_async_sdk_task_lifecycle(local_server, auth_token):
    async with AsyncKeelwayClient(base_url=local_server, token=auth_token) as client:
        # Create task
        task = await client.create_task(goal="SDK test task", policy="ask_before_changes")
        assert "id" in task
        tid = task["id"]

        # Get task
        info = await client.get_task(tid)
        assert info["title"] == "SDK test task" or info["goal"] == "SDK test task"

        # List tasks
        all_tasks = await client.list_tasks()
        assert any(t.get("id") == tid for t in all_tasks)


def test_sdk_codebase_intelligence_and_facts(local_server, auth_token):
    with KeelwayClient(base_url=local_server, token=auth_token) as client:
        # Code search
        search_res = client.search_codebase("KeelwayClient")
        assert "total_files" in search_res or "results" in search_res or "symbols" in search_res

        # Fact memory
        fact_res = client.record_fact(key="sdk_test_key", statement="Keelway Python SDK is production-ready", scope="PROJECT")
        assert fact_res.get("status") == "ok" or "key" in fact_res

        facts = client.query_facts(scope="PROJECT", query="SDK")
        assert isinstance(facts, list)


def test_sdk_resource_not_found(local_server, auth_token):
    with KeelwayClient(base_url=local_server, token=auth_token) as client:
        with pytest.raises(TaskNotFoundError):
            client.get_task("nonexistent_task_id_9999")
