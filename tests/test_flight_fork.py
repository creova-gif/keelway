import pytest
import tempfile
import shutil
from pathlib import Path
from core.orchestration.flight_recorder import FlightRecorder


def test_flight_recorder_fork_checkpoint_worktree():
    temp_dir = Path(tempfile.mkdtemp())
    try:
        recorder = FlightRecorder(task_id="fork_test_01", db_path=temp_dir / "flight.db")
        recorder.record_event(
            event_type="file_write",
            payload={"path": "main.py", "content": "print('v1')"},
            event_index=0
        )
        recorder.record_event(
            event_type="file_write",
            payload={"path": "main.py", "content": "print('v2')"},
            event_index=1
        )

        fork_dir = temp_dir / "fork_worktree"
        result = recorder.fork_checkpoint(event_index=0, destination_path=fork_dir)
        
        assert result["status"] == "success"
        assert result["event_index"] == 0
        assert (fork_dir / "main.py").exists()
        assert (fork_dir / "main.py").read_text() == "print('v1')"
    finally:
        shutil.rmtree(temp_dir)
