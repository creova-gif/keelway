from fastapi.testclient import TestClient

from core.api.studio import parse_unified_diff
from core.main import app
from core.models.gateway import gateway

SAMPLE_DIFF = """diff --git a/core/x.py b/core/x.py
index 1111111..2222222 100644
--- a/core/x.py
+++ b/core/x.py
@@ -1,3 +1,3 @@
 keep
-old
+new
 tail
diff --git a/img.png b/img.png
Binary files a/img.png and b/img.png differ
"""


def test_parse_unified_diff_line_numbers_and_counts():
    files = parse_unified_diff(SAMPLE_DIFF)
    assert [f["path"] for f in files] == ["core/x.py", "img.png"]
    x = files[0]
    assert (x["additions"], x["deletions"]) == (1, 1)
    assert [(ln["type"], ln["old"], ln["new"]) for ln in x["lines"]] == [
        ("hunk", None, None), ("context", 1, 1), ("del", 2, None), ("add", None, 2), ("context", 3, 3),
    ]
    assert files[1]["binary"] is True



def test_studio_status_and_diff():
    with TestClient(app) as client:
        status = client.get("/v1/studio/status").json()
        assert status["database_connected"] is True
        assert set(status["providers"]) == {"anthropic", "openai", "google", "local"}
        assert status["tasks"]["total"] == sum(status["tasks"]["by_state"].values())
        diff = client.get("/v1/studio/diff").json()
        assert set(diff) == {"available", "truncated", "files"}


def test_air_gap_toggle_broadcasts_to_studio_clients():
    original = gateway.air_gap.enabled
    try:
        with TestClient(app) as client, client.websocket_connect("/v1/ws/studio") as ws:
            assert ws.receive_json()["type"] == "handshake"
            resp = client.post("/v1/studio/airgap", json={"enabled": not original})
            assert resp.json()["air_gapped"] is (not original)
            assert gateway.air_gap.enabled is (not original)
            event = ws.receive_json()
            assert event == {**event, "type": "air_gap_status_changed", "air_gapped": not original}
    finally:
        gateway.air_gap.enabled = original


def test_task_changes_broadcast_agent_state_changed():
    with TestClient(app) as client, client.websocket_connect("/v1/ws/studio") as ws:
        ws.receive_json()
        task = client.post("/v1/tasks", json={"title": "Broadcast check"}).json()
        created = ws.receive_json()
        assert created["type"] == "agent_state_changed"
        assert (created["task_id"], created["previous_state"], created["new_state"]) == (task["id"], None, "created")

        client.post(f"/v1/tasks/{task['id']}/transition", json={"target_state": "planned"})
        moved = ws.receive_json()
        assert (moved["previous_state"], moved["new_state"]) == ("created", "planned")
