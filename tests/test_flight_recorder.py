import pytest
import tempfile
from pathlib import Path
from core.orchestration.flight_recorder import FlightRecorder, FlightPlayer


def test_flight_recorder_and_deterministic_player():
    with tempfile.TemporaryDirectory() as tmpdir:
        recordings_dir = Path(tmpdir)
        recorder = FlightRecorder(task_id="task_test_replay", recordings_dir=recordings_dir)

        # Record events
        recorder.record_event("state_transition", {"from": "CREATED", "to": "PLANNING"})
        recorder.record_event("prompt", {"user_input": "Refactor gateway.py"})
        recorder.record_event("tool_call", {"tool": "git_status", "args": {}})
        recorder.record_event("tool_result", {"tool": "git_status", "output": "clean"})
        recorder.record_event("state_transition", {"from": "PLANNING", "to": "COMPLETED"})

        tape_path = recorder.save_tape()
        assert tape_path.exists()

        # Replay events
        player = FlightPlayer(tape_path)
        assert len(player.events) == 5

        # Step 1
        e1 = player.step_forward()
        assert e1["event_type"] == "state_transition"
        assert e1["payload"]["to"] == "PLANNING"

        # Step 2
        e2 = player.step_forward()
        assert e2["event_type"] == "prompt"
        assert e2["payload"]["user_input"] == "Refactor gateway.py"

        # Rewind test
        player.rewind(to_index=1)
        assert player.cursor == 1
        e_rewound = player.step_forward()
        assert e_rewound["event_type"] == "prompt"

        # Fork test at step 2
        forked = player.fork(at_index=2, new_task_id="task_fork_experiment")
        assert len(forked.events) == 2
        assert forked.task_id == "task_fork_experiment"
