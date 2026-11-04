import pytest
from httpx import AsyncClient, ASGITransport
from core.main import app
from core.orchestration.flight_recorder import FlightRecorder


@pytest.mark.asyncio
async def test_flight_fork_api_endpoint(tmp_path):
    recorder = FlightRecorder(task_id="api_fork_task")
    recorder.record_event(
        event_type="file_write",
        payload={"path": "calc.py", "content": "def add(a, b): return a + b"},
        event_index=0
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/v1/flight/tape/api_fork_task/fork",
            json={"event_index": 0}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["task_id"] == "api_fork_task"
        assert data["event_index"] == 0
        assert "destination" in data
