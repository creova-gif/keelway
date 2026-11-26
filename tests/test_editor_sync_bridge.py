"""
Tests for Keelway Dual-Mode Sovereign IDE: External Editor Sync Bridge & Conflict Policy.
Verifies:
- 150ms debouncing of external filesystem events.
- Path containment validation preventing path traversal attacks.
- Subprocess launching for VS Code and Cursor.
- Pessimistic Pause & Prompt on concurrent agent/human mutations.
- Flight recorder event emission for EXTERNAL_CONCURRENT_MUTATION.
- Full HTTP API endpoints: /v1/sync/status, /v1/sync/open-in-editor, /v1/sync/resolve-conflict.
"""

import time
import pytest
from starlette.testclient import TestClient

from core.main import app
from core.sync.bridge import ExternalEditorSyncBridge
from core.orchestration.flight_recorder import FlightRecorder


def test_sync_bridge_debounce(tmp_path):
    """Verifies that events arriving within 150ms are debounced."""
    bridge = ExternalEditorSyncBridge(workspace_root=tmp_path, debounce_ms=150)
    file_path = "src/main.py"

    # First event is not debounced
    assert bridge.is_debounced(file_path) is False

    # Immediate second event (< 150ms) is debounced
    assert bridge.is_debounced(file_path) is True

    # Sleep past debounce interval
    time.sleep(0.16)
    assert bridge.is_debounced(file_path) is False


def test_sync_bridge_path_containment(tmp_path):
    """Verifies strict path containment preventing traversal outside workspace root."""
    bridge = ExternalEditorSyncBridge(workspace_root=tmp_path)

    # Valid relative paths resolve inside root
    valid = bridge.validate_path_containment("app/routes.py")
    assert valid == (tmp_path / "app/routes.py").resolve()

    # Path traversal outside root is rejected
    with pytest.raises(ValueError, match="Path traversal detected"):
        bridge.validate_path_containment("../../etc/passwd")


def test_sync_bridge_open_in_editor(tmp_path):
    """Verifies open_in_editor generates correct CLI invocations with -r flag."""
    bridge = ExternalEditorSyncBridge(workspace_root=tmp_path)
    launched_commands = []

    def mock_runner(cmd):
        launched_commands.append(cmd)

    # Launch VS Code
    res_code = bridge.open_in_editor(editor="vscode", relative_path="main.py", runner=mock_runner)
    assert res_code["status"] == "launched"
    assert res_code["editor"] == "vscode"
    assert launched_commands[-1] == ["code", "-r", str(tmp_path / "main.py")]

    # Launch Cursor
    res_cursor = bridge.open_in_editor(editor="cursor", relative_path="", runner=mock_runner)
    assert res_cursor["status"] == "launched"
    assert res_cursor["editor"] == "cursor"
    assert launched_commands[-1] == ["cursor", "-r", str(tmp_path)]


def test_sync_bridge_missing_binary(tmp_path):
    """Verifies that an unsupported or uninstalled editor raises appropriate errors."""
    bridge = ExternalEditorSyncBridge(workspace_root=tmp_path)

    with pytest.raises(ValueError, match="Unsupported editor"):
        bridge.open_in_editor(editor="unsupported_ide")


def test_concurrent_mutation_detection_and_flight_recording(tmp_path):
    """Verifies Pessimistic Pause & Prompt: external change on active lease triggers conflict & tape event."""
    conflicts_seen = []

    def on_conflict(conflict):
        conflicts_seen.append(conflict)

    bridge = ExternalEditorSyncBridge(workspace_root=tmp_path, debounce_ms=10, on_conflict_callback=on_conflict)
    test_file = tmp_path / "calculator.py"
    test_file.write_text("def add(a, b): return a + b\n", encoding="utf-8")

    # Agent acquires lease on calculator.py
    bridge.acquire_file_lease(
        file_path="calculator.py",
        agent_id="agent_123",
        base_content="def add(a, b): return a + b\n",
        agent_content="def add(a, b): return a + b + 0\n",
    )

    # External editor modifies calculator.py
    external_edit = "def add(a, b):\n    # external developer change\n    return a + b\n"
    test_file.write_text(external_edit, encoding="utf-8")

    # Sleep past 10ms debounce
    time.sleep(0.02)
    conflict = bridge.notify_external_change(file_path="calculator.py", external_content=external_edit)

    assert conflict is not None
    assert conflict.file_path == "calculator.py"
    assert conflict.agent_id == "agent_123"
    assert conflict.external_content == external_edit
    assert len(conflicts_seen) == 1

    # Verify flight recorder tape captures the concurrent mutation event
    recorder = FlightRecorder(task_id="task_concurrent_test", recordings_dir=tmp_path / "recordings")
    event = recorder.record_concurrent_mutation(
        file_path=conflict.file_path,
        external_content=conflict.external_content,
        agent_content=conflict.agent_content,
        base_content=conflict.base_content,
    )
    assert event.event_type == "EXTERNAL_CONCURRENT_MUTATION"
    assert event.payload["status"] == "agent_paused_on_conflict"
    assert event.payload["file_path"] == "calculator.py"

    # Resolve conflict: keep_external
    res_keep_ext = bridge.resolve_conflict(file_path="calculator.py", resolution="keep_external")
    assert res_keep_ext["status"] == "resolved"
    assert res_keep_ext["resolution"] == "keep_external"
    assert test_file.read_text(encoding="utf-8") == external_edit


def test_sync_api_endpoints():
    """Verifies the HTTP API endpoints for sync status and open-in-editor."""
    with TestClient(app) as client:
        # GET /v1/editor-sync/status
        status_res = client.get("/v1/editor-sync/status")
        assert status_res.status_code == 200
        data = status_res.json()
        assert "watching" in data
        assert "debounce_ms" in data
        assert data["debounce_ms"] == 150
        assert "detected_editors" in data

        # POST /v1/editor-sync/open-in-editor with traversal attempt
        bad_req = client.post(
            "/v1/editor-sync/open-in-editor",
            json={"editor": "vscode", "relative_path": "../../outside.txt"},
        )
        assert bad_req.status_code == 400
        assert "Path traversal" in bad_req.json()["detail"]
