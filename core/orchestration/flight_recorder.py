"""
Keelway Deterministic Flight Recorder & Time-Travel Debugging Engine.
Captures byte-for-byte execution tapes (prompts, tool calls, environment headers, state changes)
to enable 100% reproducible offline replay and step-by-step forensic inspection.
"""

import json
import time
import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from core.config import legacy_aware
from typing import Dict, Any, List, Optional


@dataclass
class FlightEvent:
    event_index: int
    event_type: str  # 'prompt', 'model_response', 'tool_call', 'tool_result', 'state_transition'
    payload: Dict[str, Any]
    timestamp_utc: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_index": self.event_index,
            "event_type": self.event_type,
            "payload": self.payload,
            "timestamp_utc": self.timestamp_utc,
        }


class FlightRecorder:
    """Records every step of an agent run into an immutable, cryptographic execution tape."""

    def __init__(self, task_id: str, recordings_dir: Optional[Path] = None):
        self.task_id = task_id
        self.recordings_dir = recordings_dir or legacy_aware(Path(".keelway/recordings"), Path(".kora/recordings"))
        self.events: List[FlightEvent] = []
        self.current_index = 0

    def record_event(self, event_type: str, payload: Dict[str, Any]) -> FlightEvent:
        self.current_index += 1
        event = FlightEvent(
            event_index=self.current_index,
            event_type=event_type,
            payload=payload,
            timestamp_utc=time.time(),
        )
        self.events.append(event)
        return event

    def save_tape(self) -> Path:
        """Saves tape to disk with SHA-256 seal."""
        self.recordings_dir.mkdir(parents=True, exist_ok=True)
        tape_path = self.recordings_dir / f"{self.task_id}.flight.json"

        data = {
            "task_id": self.task_id,
            "event_count": len(self.events),
            "events": [e.to_dict() for e in self.events],
        }
        serialized = json.dumps(data, indent=2, sort_keys=True)
        tape_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()

        final_payload = {
            **data,
            "tape_sha256": tape_hash,
            "recorded_at": time.time(),
        }
        tape_path.write_text(json.dumps(final_payload, indent=2), encoding="utf-8")
        return tape_path


class FlightPlayer:
    """Replays recorded tapes deterministically without calling external models or tools."""

    def __init__(self, tape_path: Path):
        if not tape_path.exists():
            raise FileNotFoundError(f"Flight tape not found: {tape_path}")
        self.tape_data = json.loads(tape_path.read_text(encoding="utf-8"))
        self.task_id = self.tape_data["task_id"]
        self.events = self.tape_data["events"]
        self.cursor = 0

    def step_forward(self) -> Optional[Dict[str, Any]]:
        """Steps forward one event in the timeline."""
        if self.cursor < len(self.events):
            event = self.events[self.cursor]
            self.cursor += 1
            return event
        return None

    def rewind(self, to_index: int = 0) -> None:
        """Rewinds timeline to an earlier step."""
        self.cursor = max(0, min(to_index, len(self.events)))

    def fork(self, at_index: int, new_task_id: str) -> FlightRecorder:
        """Forks the flight timeline at step N to test alternative prompts or tools."""
        fork_rec = FlightRecorder(task_id=new_task_id)
        for e in self.events[:at_index]:
            fork_rec.record_event(e["event_type"], e["payload"])
        return fork_rec
