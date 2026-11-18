"""
Interval scheduler for durable KFlow DAGs.

Schedules created through the app singleton (`flow_scheduler`) persist to
`$KEELWAY_STATE_DIR/schedules.json` — or `~/.keelway/schedules.json` with a
`legacy_aware` fallback to `~/.kora/schedules.json` — and survive restarts.
`FlowScheduler` instances constructed without a `persist_path` stay
in-memory. Each tick executes the DAG via the standard KFlow engine, so
proof packets are produced exactly as for a manual run.
"""

from __future__ import annotations

import asyncio
import json
import os
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from core.config import legacy_aware

MIN_INTERVAL_SECONDS = 60


@dataclass
class FlowSchedule:
    schedule_id: str
    flow_id: str
    interval_seconds: int
    created_at_epoch: float
    next_run_epoch: float
    runs_completed: int = 0
    last_run_epoch: Optional[float] = None
    last_status: Optional[str] = None  # "completed" | "failed" | None (not yet run)
    last_error: Optional[str] = None
    enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schedule_id": self.schedule_id,
            "flow_id": self.flow_id,
            "interval_seconds": self.interval_seconds,
            "created_at_epoch": self.created_at_epoch,
            "next_run_epoch": self.next_run_epoch,
            "runs_completed": self.runs_completed,
            "last_run_epoch": self.last_run_epoch,
            "last_status": self.last_status,
            "last_error": self.last_error,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FlowSchedule":
        return cls(
            schedule_id=data["schedule_id"],
            flow_id=data["flow_id"],
            interval_seconds=int(data["interval_seconds"]),
            created_at_epoch=float(data["created_at_epoch"]),
            next_run_epoch=float(data["next_run_epoch"]),
            runs_completed=int(data.get("runs_completed", 0)),
            last_run_epoch=data.get("last_run_epoch"),
            last_status=data.get("last_status"),
            last_error=data.get("last_error"),
            enabled=bool(data.get("enabled", True)),
        )


class FlowScheduler:
    """Runs registered KFlow DAGs on a fixed interval.

    The executor callable takes a flow_id and returns nothing; exceptions
    are captured onto the schedule so a failing flow does not kill the loop.
    """

    def __init__(
        self,
        executor: Optional[Callable[[str], Any]] = None,
        persist_path: Optional[Path] = None,
    ) -> None:
        self._schedules: Dict[str, FlowSchedule] = {}
        self._lock = threading.Lock()
        self._executor = executor or self._default_executor
        self._task: Optional[asyncio.Task] = None
        self._persist_path: Optional[Path] = Path(persist_path) if persist_path else None
        self._load()

    @property
    def persistent(self) -> bool:
        return self._persist_path is not None

    def _load(self) -> None:
        if self._persist_path is None or not self._persist_path.exists():
            return
        try:
            data = json.loads(self._persist_path.read_text(encoding="utf-8"))
            for item in data.get("schedules", []):
                sched = FlowSchedule.from_dict(item)
                self._schedules[sched.schedule_id] = sched
        except Exception:
            # A corrupt or hand-edited file must never block startup.
            pass

    def _save(self) -> None:
        if self._persist_path is None:
            return
        try:
            self._persist_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {"schedules": [s.to_dict() for s in self._schedules.values()]}
            tmp = self._persist_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            tmp.replace(self._persist_path)
        except Exception:
            # Persistence degradation must not kill scheduling; in-memory
            # state continues and the next mutation retries the write.
            pass

    @staticmethod
    def _default_executor(flow_id: str) -> None:
        import subprocess
        from core.kflow import kflow_engine

        head = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=10,
        ).stdout.strip() or "unresolved"
        kflow_engine.execute_dag(flow_id=flow_id, current_git_head_sha=head)

    def add(self, flow_id: str, interval_seconds: int) -> FlowSchedule:
        from core.kflow import kflow_engine

        if kflow_engine.get_flow(flow_id) is None:
            raise KeyError(f"Flow '{flow_id}' not found.")
        if interval_seconds < MIN_INTERVAL_SECONDS:
            raise ValueError(f"interval_seconds must be >= {MIN_INTERVAL_SECONDS}.")
        now = time.time()
        sched = FlowSchedule(
            schedule_id=f"sched_{uuid.uuid4().hex[:12]}",
            flow_id=flow_id,
            interval_seconds=interval_seconds,
            created_at_epoch=now,
            next_run_epoch=now + interval_seconds,
        )
        self._schedules[sched.schedule_id] = sched
        self._save()
        return sched

    def remove(self, schedule_id: str) -> bool:
        removed = self._schedules.pop(schedule_id, None) is not None
        if removed:
            self._save()
        return removed

    def list(self) -> List[Dict[str, Any]]:
        return [s.to_dict() for s in sorted(self._schedules.values(), key=lambda s: s.created_at_epoch)]

    def get(self, schedule_id: str) -> Optional[FlowSchedule]:
        return self._schedules.get(schedule_id)

    def run_due(self, now: Optional[float] = None) -> int:
        """Execute all due schedules once. Returns how many ran. Testable without sleeping."""
        now = now if now is not None else time.time()
        ran = 0
        with self._lock:
            due = [s for s in self._schedules.values() if s.enabled and s.next_run_epoch <= now]
        for sched in due:
            sched.last_run_epoch = now
            try:
                self._executor(sched.flow_id)
                sched.last_status = "completed"
                sched.last_error = None
            except Exception as exc:  # noqa: BLE001 — failures belong on the schedule, not the loop
                sched.last_status = "failed"
                sched.last_error = str(exc)
            sched.runs_completed += 1
            sched.next_run_epoch = now + sched.interval_seconds
            ran += 1
        if ran:
            self._save()
        return ran

    async def _loop(self) -> None:
        while True:
            await asyncio.sleep(5)
            try:
                await asyncio.to_thread(self.run_due)
            except Exception:  # noqa: BLE001 — keep the scheduler alive
                pass

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        self._save()


def _default_persist_path() -> Path:
    state_dir = os.environ.get("KEELWAY_STATE_DIR", "").strip()
    if state_dir:
        return Path(state_dir).expanduser() / "schedules.json"
    return legacy_aware(
        Path.home() / ".keelway" / "schedules.json",
        Path.home() / ".kora" / "schedules.json",
    )


flow_scheduler = FlowScheduler(persist_path=_default_persist_path())
