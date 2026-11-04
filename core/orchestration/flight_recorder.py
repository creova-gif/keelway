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
from core.security.redact import redact_payload
from typing import Dict, Any, List, Optional, Tuple


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

    def __init__(self, task_id: str, recordings_dir: Optional[Path] = None, db_path: Optional[Any] = None, **kwargs):
        self.task_id = task_id
        self.db_path = db_path
        self.recordings_dir = recordings_dir or legacy_aware(Path(".keelway/recordings"), Path(".kora/recordings"))
        self.events: List[FlightEvent] = []
        self.current_index = 0
        self.redactions = 0  # credentials removed from what this tape stores
        self.tape_sha256: Optional[str] = None

    def record_event(
        self,
        event_type: str,
        payload: Dict[str, Any],
        event_index: Optional[int] = None,
        **kwargs,
    ) -> FlightEvent:
        # An agent can read .env or print secrets; the tape is exported, forked and shared, so it never stores them.
        payload, removed = redact_payload(payload)
        self.redactions += removed
        if event_index is not None:
            self.current_index = event_index
        else:
            self.current_index += 1
        event = FlightEvent(
            event_index=self.current_index,
            event_type=event_type,
            payload=payload,
            timestamp_utc=time.time(),
        )
        self.events.append(event)
        return event

    def record_concurrent_mutation(
        self,
        file_path: str,
        external_content: str,
        agent_content: str = "",
        base_content: str = "",
    ) -> FlightEvent:
        """Records an EXTERNAL_CONCURRENT_MUTATION event when external editor mutates a file during an agent run."""
        return self.record_event(
            event_type="EXTERNAL_CONCURRENT_MUTATION",
            payload={
                "file_path": file_path,
                "agent_content_len": len(agent_content),
                "external_content_len": len(external_content),
                "base_content_len": len(base_content),
                "status": "agent_paused_on_conflict",
            },
        )

    def get_tape(self) -> "FlightRecorder":
        return self

    def seal_tape(self) -> "FlightRecorder":
        """Calculates cryptographic seal and saves tape to disk."""
        data = {
            "task_id": self.task_id,
            "event_count": len(self.events),
            "events": [e.to_dict() for e in self.events],
        }
        serialized = json.dumps(data, indent=2, sort_keys=True)
        self.tape_sha256 = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        try:
            self.save_tape()
        except Exception:
            pass
        return self

    def fork_checkpoint(self, event_index: int, destination_path: Path) -> Dict[str, Any]:
        """Forks workspace files captured at or prior to the specified event index into an isolated directory."""
        tape = self.get_tape()
        dest_path = Path(destination_path)
        dest_path.mkdir(parents=True, exist_ok=True)
        files_restored: List[str] = []

        for ev in sorted(tape.events, key=lambda e: e.event_index):
            if ev.event_index > event_index:
                break
            payload = ev.payload or {}
            # Restore files written or modified up to this checkpoint
            if "path" in payload and "content" in payload:
                file_rel = payload["path"]
                dest_file = dest_path / file_rel
                dest_file.parent.mkdir(parents=True, exist_ok=True)
                dest_file.write_text(payload["content"], encoding="utf-8")
                files_restored.append(file_rel)

        return {
            "status": "success",
            "task_id": self.task_id,
            "event_index": event_index,
            "destination": str(dest_path),
            "files_restored": files_restored,
        }

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
            "redactions": self.redactions,
            "recorded_at": time.time(),
        }
        tape_path.write_text(json.dumps(final_payload, indent=2), encoding="utf-8")
        self.tape_sha256 = tape_hash
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

    def verify_integrity(self) -> Tuple[bool, str, str]:
        """Validates that the recorded tape matches its cryptographic SHA-256 seal."""
        canonical_data = {
            "task_id": self.task_id,
            "event_count": len(self.events),
            "events": self.events,
        }
        serialized = json.dumps(canonical_data, indent=2, sort_keys=True)
        calculated = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        claimed = self.tape_data.get("tape_sha256", "")
        return (calculated == claimed, calculated, claimed)

    def replay_all(self) -> List[Dict[str, Any]]:
        """Replays all events in deterministic chronological order from cursor position 0."""
        self.cursor = 0
        replayed = []
        while ev := self.step_forward():
            replayed.append(ev)
        return replayed

    def fork(self, at_index: int, new_task_id: str) -> FlightRecorder:
        """Forks the flight timeline at step N to test alternative prompts or tools."""
        fork_rec = FlightRecorder(task_id=new_task_id)
        for e in self.events[:at_index]:
            fork_rec.record_event(e["event_type"], e["payload"])
        return fork_rec
