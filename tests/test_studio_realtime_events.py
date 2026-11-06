"""
Test suite for Keelway Studio Realtime Event Streaming & Proof Strip Lifecycle.

Validates:
1. Server-Sent Events (SSE) `/v1/events/stream` and `/v1/flight/stream` cleanly yield
   structured JSON event frames matching Keelway's Proof Strip lifecycle:
   INSPECT -> PLAN -> AUTHORIZE -> EXECUTE -> VERIFY -> SEAL.
2. Clients subscribing to task events receive live updates when events are recorded.
3. Multiple concurrent subscribers and task-filtered subscriptions.
4. Clean disconnection and reconnection handling without leaking file descriptors,
   subscriber queues, or background tasks.
5. Security controls: Token authentication (Bearer header & query param) and origin policy.
"""

import asyncio
import json
import threading
import time
from pathlib import Path
from typing import List, Dict, Any

import pytest
from starlette.testclient import TestClient

from core.main import app
from core.api.routes import (
    ws_manager,
    PROOF_STRIP_STAGES,
    map_to_proof_stage,
    _active_agent_loops,
)
from core.models.gateway import gateway
from core.security.auth import launch_token
from core.storage.workspace_fs import WorkspaceFilesystem


def _read_sse_events(
    client: TestClient,
    url: str,
    headers: Dict[str, str],
    stop_condition,
    max_events: int = 10,
    timeout_sec: float = 3.0,
) -> List[Dict[str, Any]]:
    """Helper to collect parsed JSON frames from an SSE stream until condition is met."""
    events = []
    start_time = time.time()

    with client.stream("GET", url, headers=headers) as resp:
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")

        for line in resp.iter_lines():
            if time.time() - start_time > timeout_sec:
                break
            if line.startswith("data: "):
                payload = json.loads(line[6:])
                events.append(payload)
                if stop_condition(payload):
                    break
                if len(events) >= max_events:
                    break
    return events


def test_proof_strip_lifecycle_stage_mapping_contract():
    """Verify that all 6 Proof Strip stages are properly defined and mapped."""
    assert PROOF_STRIP_STAGES == ("INSPECT", "PLAN", "AUTHORIZE", "EXECUTE", "VERIFY", "SEAL")

    # 1. INSPECT
    assert map_to_proof_stage("handshake") == "INSPECT"
    assert map_to_proof_stage("context_loading", status="created") == "INSPECT"
    assert map_to_proof_stage("air_gap_status_changed") == "INSPECT"

    # 2. PLAN
    assert map_to_proof_stage("plan_initialized") == "PLAN"
    assert map_to_proof_stage("agent_state_changed", status="planning") == "PLAN"
    assert map_to_proof_stage("agent_state_changed", status="plan_ready") == "PLAN"

    # 3. AUTHORIZE
    assert map_to_proof_stage("approval_requested", status="awaiting_approval") == "AUTHORIZE"
    assert map_to_proof_stage("approval_granted") == "AUTHORIZE"
    assert map_to_proof_stage("quorum_approval_requested") == "AUTHORIZE"
    assert map_to_proof_stage("policy_evaluation") == "AUTHORIZE"

    # 4. EXECUTE
    assert map_to_proof_stage("tool_call", status="executing_tool") == "EXECUTE"
    assert map_to_proof_stage("diff_proposed") == "EXECUTE"
    assert map_to_proof_stage("tool:write_file") == "EXECUTE"
    assert map_to_proof_stage("tool_success") == "EXECUTE"

    # 5. VERIFY
    assert map_to_proof_stage("verification_run", status="verifying") == "VERIFY"
    assert map_to_proof_stage("test_suite_execution") == "VERIFY"
    assert map_to_proof_stage("self_healing_result") == "VERIFY"

    # 6. SEAL
    assert map_to_proof_stage("flight_tape_sealed", status="completed") == "SEAL"
    assert map_to_proof_stage("audit_sealed") == "SEAL"
    assert map_to_proof_stage("agent_state_changed", status="sealed") == "SEAL"


def test_sse_endpoint_handshake_yields_inspect_stage():
    """Verify SSE connection yields an initial handshake frame matching INSPECT stage."""
    with TestClient(app) as client:
        token = launch_token()
        headers = {"Authorization": f"Bearer {token}"}

        events = _read_sse_events(
            client=client,
            url="/v1/events/stream",
            headers=headers,
            stop_condition=lambda e: e.get("type") == "handshake",
            max_events=1,
        )

        assert len(events) >= 1
        handshake = events[0]
        assert handshake["type"] == "handshake"
        assert handshake["stage"] == "INSPECT"
        assert handshake["server"] == "Keelway Studio"
        assert "air_gapped" in handshake
        assert "timestamp" in handshake


def test_sse_streams_full_six_stage_proof_strip_lifecycle(tmp_path, monkeypatch):
    """Verify that SSE stream yields structured JSON event frames for all 6 stages."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "target.py").write_text("def run(): return 1\n")

    from core.api import routes
    monkeypatch.setattr(routes, "_workspace_fs", WorkspaceFilesystem(root_dir=str(tmp_path)))

    with TestClient(app) as client:
        token = launch_token()
        headers = {"Authorization": f"Bearer {token}"}
        received_events = []
        stop_event = threading.Event()

        def stream_consumer():
            with client.stream("GET", "/v1/events/stream", headers=headers) as resp:
                for line in resp.iter_lines():
                    if stop_event.is_set():
                        break
                    if line.startswith("data: "):
                        ev = json.loads(line[6:])
                        received_events.append(ev)
                        if ev.get("stage") == "SEAL":
                            stop_event.set()
                            break

        consumer_thread = threading.Thread(target=stream_consumer)
        consumer_thread.start()
        time.sleep(0.15)  # Allow SSE subscription to register

        task_id = "realtime_proof_strip_task"

        # 1. INSPECT (Handshake already emitted on connection)
        # 2. PLAN (Create/run agent task)
        client.post(
            "/v1/agent/run",
            json={"task_id": task_id, "goal": "Refactor run() function", "steps": ["Modify target.py"]},
            headers=headers,
        )
        time.sleep(0.1)

        # 3. AUTHORIZE & EXECUTE (Step mutating tool requires human approval)
        client.post(
            f"/v1/agent/step/{task_id}",
            json={
                "tool_name": "write_file",
                "arguments": {"path": "target.py", "content": "def run(): return 42\n"},
                "step_id": "step_1",
            },
            headers=headers,
        )
        time.sleep(0.1)

        # Approve action -> completes tool execution
        client.post(
            f"/v1/agent/approve/{task_id}",
            json={"approved": True},
            headers=headers,
        )
        time.sleep(0.1)

        # 5. VERIFY (Simulate verification broadcast)
        asyncio.run(
            ws_manager.broadcast({
                "type": "test_verification",
                "stage": "VERIFY",
                "task_id": task_id,
                "exit_code": 0,
                "output": "1 passed in 0.05s",
            })
        )
        time.sleep(0.1)

        # 6. SEAL (Simulate tape sealing and completion)
        asyncio.run(
            ws_manager.broadcast({
                "type": "flight_tape_sealed",
                "stage": "SEAL",
                "task_id": task_id,
                "merkle_root": "073d5e86e3dba727c4dd0e561e24927e98fe51db",
                "status": "completed",
            })
        )

        consumer_thread.join(timeout=3.0)
        stop_event.set()

        # Collect distinct stages observed
        stages_observed = [e.get("stage") for e in received_events if "stage" in e]

        # Verify that all 6 lifecycle stages were emitted in structured frames
        for required_stage in ["INSPECT", "PLAN", "AUTHORIZE", "EXECUTE", "VERIFY", "SEAL"]:
            assert required_stage in stages_observed, f"Stage {required_stage} was not yielded in stream: {stages_observed}"

        # Verify frame structural schema
        for ev in received_events:
            assert "type" in ev
            assert "stage" in ev
            assert ev["stage"] in PROOF_STRIP_STAGES
            assert "timestamp" in ev


def test_task_filtered_subscription():
    """Verify that a client subscribing with task_id receives only matching task updates."""
    with TestClient(app) as client:
        token = launch_token()
        headers = {"Authorization": f"Bearer {token}"}
        task_a_events = []
        stop_event = threading.Event()

        def stream_consumer():
            with client.stream("GET", "/v1/events/stream?task_id=task_ALPHA", headers=headers) as resp:
                for line in resp.iter_lines():
                    if stop_event.is_set():
                        break
                    if line.startswith("data: "):
                        ev = json.loads(line[6:])
                        task_a_events.append(ev)
                        if ev.get("marker") == "done_alpha":
                            stop_event.set()
                            break

        consumer_thread = threading.Thread(target=stream_consumer)
        consumer_thread.start()
        time.sleep(0.15)

        # Broadcast event for task_B (should be filtered out by task_A subscriber)
        asyncio.run(
            ws_manager.broadcast({
                "type": "agent_loop_updated",
                "task_id": "task_BETA",
                "stage": "PLAN",
                "marker": "ignored_beta",
            })
        )
        time.sleep(0.05)

        # Broadcast event for task_A (should be received)
        asyncio.run(
            ws_manager.broadcast({
                "type": "agent_loop_updated",
                "task_id": "task_ALPHA",
                "stage": "EXECUTE",
                "marker": "done_alpha",
            })
        )

        consumer_thread.join(timeout=2.0)
        stop_event.set()

        # Handshake + task_ALPHA event, but NOT task_BETA event
        task_ids_received = [e.get("task_id") for e in task_a_events if e.get("task_id")]
        assert "task_ALPHA" in task_ids_received
        assert "task_BETA" not in task_ids_received


def test_clean_disconnection_and_reconnection_without_leaks():
    """Verify zero memory or subscriber leaks upon disconnect and clean reconnection."""
    with TestClient(app) as client:
        token = launch_token()
        headers = {"Authorization": f"Bearer {token}"}

        # Baseline: zero subscribers
        initial_subscribers = len(ws_manager.sse_subscribers)
        assert initial_subscribers == 0

        # Connect client 1
        with client.stream("GET", "/v1/events/stream", headers=headers) as resp1:
            for line in resp1.iter_lines():
                if line.startswith("data: "):
                    break
            # Active connection registered
            assert len(ws_manager.sse_subscribers) == 1

            # Connect client 2 concurrently
            with client.stream("GET", "/v1/events/stream", headers=headers) as resp2:
                for line in resp2.iter_lines():
                    if line.startswith("data: "):
                        break
                # Both connections registered
                assert len(ws_manager.sse_subscribers) == 2

            # Client 2 disconnected, client 1 still active
            assert len(ws_manager.sse_subscribers) == 1

        # Client 1 disconnected -> all subscriber queues unregistered cleanly
        assert len(ws_manager.sse_subscribers) == 0

        # Reconnection: New connection can connect and immediately receive frames
        reconnected_events = _read_sse_events(
            client=client,
            url="/v1/events/stream",
            headers=headers,
            stop_condition=lambda e: e.get("type") == "handshake",
            max_events=1,
        )
        assert len(reconnected_events) == 1
        assert reconnected_events[0]["stage"] == "INSPECT"
        assert len(ws_manager.sse_subscribers) == 0


def test_flight_stream_endpoint_yields_flight_frames(tmp_path, monkeypatch):
    """Verify `/v1/flight/stream` yields structured flight tape events matching Proof Strip."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "notes.txt").write_text("initial text\n")

    from core.api import routes
    monkeypatch.setattr(routes, "_workspace_fs", WorkspaceFilesystem(root_dir=str(tmp_path)))

    with TestClient(app) as client:
        token = launch_token()
        headers = {"Authorization": f"Bearer {token}"}
        task_id = "flight_stream_test"

        # Create agent run and step once
        client.post(
            "/v1/agent/run",
            json={"task_id": task_id, "goal": "Update notes", "steps": ["Update notes"]},
            headers=headers,
        )
        client.post(
            f"/v1/agent/step/{task_id}",
            json={"tool_name": "write_file", "arguments": {"path": "notes.txt", "content": "updated\n"}, "step_id": "step_1"},
            headers=headers,
        )

        # Stream flight events for this task
        events = _read_sse_events(
            client=client,
            url=f"/v1/flight/stream?task_id={task_id}",
            headers=headers,
            stop_condition=lambda e: e.get("event_type") == "approval_requested",
            max_events=5,
        )

        assert len(events) >= 1
        flight_frame = events[0]
        assert flight_frame["type"] in ("flight_event_frame", "flight_stream_update")
        assert "stage" in flight_frame
        assert flight_frame["stage"] in PROOF_STRIP_STAGES


@pytest.mark.auth
def test_realtime_endpoints_security_and_origin_enforcement():
    """Verify unauthenticated requests and forbidden origins are rejected."""
    with TestClient(app) as client:
        # 1. Missing authentication token rejected with 401
        with client.stream("GET", "/v1/events/stream") as resp_unauth:
            assert resp_unauth.status_code == 401

        # 2. Forbidden foreign origin rejected with 403
        token = launch_token()
        with client.stream(
            "GET",
            "/v1/events/stream",
            headers={"Authorization": f"Bearer {token}", "Origin": "https://malicious-site.example", "Host": "localhost:7420"},
        ) as resp_evil:
            assert resp_evil.status_code == 403

        # 3. Valid origin and query param token allowed
        with client.stream(
            "GET",
            f"/v1/events/stream?token={token}",
            headers={"Origin": "http://localhost:7420", "Host": "localhost:7420"},
        ) as resp_ok:
            assert resp_ok.status_code == 200


def test_websocket_studio_streaming_proof_strip_frames_and_clean_disconnect(tmp_path, monkeypatch):
    """Verify WebSocket studio channel yields structured frames matching Proof Strip lifecycle with clean disconnect."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "script.py").write_text("print('v1')\n")

    from core.api import routes
    monkeypatch.setattr(routes, "_workspace_fs", WorkspaceFilesystem(root_dir=str(tmp_path)))

    initial_ws_count = len(ws_manager.active_connections)

    with TestClient(app) as client, client.websocket_connect("/v1/ws/studio") as ws:
        assert len(ws_manager.active_connections) == initial_ws_count + 1

        # Handshake frame in INSPECT stage
        hs = ws.receive_json()
        assert hs["type"] == "handshake"
        assert hs["stage"] == "INSPECT"
        assert hs["server"] == "Keelway Studio"

        # Ping-pong check
        ws.send_json({"type": "ping"})
        pong = ws.receive_json()
        assert pong["type"] == "pong"

        task_id = "ws_proof_strip_task"

        # PLAN stage: run agent task
        client.post(
            "/v1/agent/run",
            json={"task_id": task_id, "goal": "Update script", "steps": ["Modify script.py"]},
        )
        plan_ev = ws.receive_json()
        assert plan_ev["type"] == "agent_loop_updated"
        assert plan_ev["stage"] == "PLAN"

        # Step tool -> pauses for human approval -> AUTHORIZE stage
        client.post(
            f"/v1/agent/step/{task_id}",
            json={"tool_name": "write_file", "arguments": {"path": "script.py", "content": "print('v2')\n"}, "step_id": "step_1"},
        )
        auth_ev = ws.receive_json()
        assert auth_ev["type"] == "agent_loop_updated"
        assert auth_ev["stage"] == "AUTHORIZE"

        # Approve -> completes execution -> EXECUTE stage
        client.post(f"/v1/agent/approve/{task_id}", json={"approved": True})
        exec_ev = ws.receive_json()
        assert exec_ev["type"] == "agent_loop_updated"
        assert exec_ev["stage"] == "EXECUTE"

    # After websocket context closes, verify active connection count drops cleanly to baseline
    assert len(ws_manager.active_connections) == initial_ws_count
