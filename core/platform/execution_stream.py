"""
Live Agent & KFlow Workflow SSE Execution Streamer (`LiveExecutionStreamer`).

Produces deterministic ordered execution trace events (`run.started`, `step.tool_call`,
`step.completed`, `p10.held` / `run.completed`), pauses at human-only `P-10` checkpoints,
resumes or aborts upon explicit human approval/denial (`p10.approved` / `p10.denied`),
persists runs in SQLite WAL, and emits signed webhook events when `SignedWebhookBus` is attached.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import threading
from typing import Any, Dict, Iterator, List, Optional, Union
import uuid

from core.platform.rbac_webhooks import SignedWebhookBus, signed_webhook_bus
from core.platform.vault import _resolve_sqlite_target

VALID_EXECUTION_KINDS = frozenset({"agent", "workflow"})
VALID_P10_DECISIONS = frozenset({"approve", "deny"})
_AUTOMATED_ACTOR_PREFIXES = ("agent:", "bot:", "service-agent:")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class LiveExecutionStreamer:
    """Manages live agent & KFlow DAG execution runs, P-10 checkpoints, and SSE event streams."""

    def __init__(
        self,
        db_path: Optional[Union[str, Path]] = None,
        webhook_bus: Optional[SignedWebhookBus] = None,
    ) -> None:
        self._lock = threading.RLock()
        self.webhook_bus = webhook_bus
        self._db_path, connect_target = _resolve_sqlite_target(db_path)
        self._conn = sqlite3.connect(connect_target, check_same_thread=False, timeout=30.0)
        self._conn.row_factory = sqlite3.Row
        self._closed = False
        self._runs: Dict[str, Dict[str, Any]] = {}
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._init_schema_and_load_locked()

    def _init_schema_and_load_locked(self) -> None:
        with self._conn:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS platform_execution_runs (
                    run_id TEXT PRIMARY KEY,
                    workspace_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_platform_exec_runs_ws ON platform_execution_runs(workspace_id);
                """
            )
            rows = self._conn.execute(
                "SELECT run_id, payload_json FROM platform_execution_runs ORDER BY rowid ASC"
            ).fetchall()
            for row in rows:
                self._runs[str(row["run_id"])] = json.loads(str(row["payload_json"]))

    def close(self) -> None:
        with self._lock:
            if not self._closed:
                self._conn.close()
                self._closed = True

    def _persist_locked(self, run: Dict[str, Any]) -> None:
        encoded = json.dumps(run, separators=(",", ":"), default=str)
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO platform_execution_runs (run_id, workspace_id, status, payload_json, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    status = excluded.status,
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """,
                (run["run_id"], run["workspace_id"], run["status"], encoded, run["updated_at"]),
            )

    @staticmethod
    def _clone_run(run: Dict[str, Any]) -> Dict[str, Any]:
        return {
            **run,
            "events": [dict(evt) for evt in run["events"]],
        }

    def start_run(
        self,
        workspace_id: str,
        kind: str,
        target_id: str,
        objective: str,
        requires_p10: bool = True,
        initiator: str = "local-operator",
    ) -> Dict[str, Any]:
        ws = str(workspace_id or "").strip()
        clean_kind = str(kind or "").strip().lower()
        clean_target = str(target_id or "").strip()
        clean_objective = str(objective or "").strip()
        clean_initiator = str(initiator or "local-operator").strip() or "local-operator"

        if not ws:
            raise ValueError("Execution 'workspace_id' must be non-empty.")
        if clean_kind not in VALID_EXECUTION_KINDS:
            raise ValueError(
                f"Unsupported execution kind '{clean_kind}'. Expected one of {sorted(VALID_EXECUTION_KINDS)}."
            )
        if not clean_target:
            raise ValueError("Execution 'target_id' must be non-empty.")
        if not clean_objective:
            raise ValueError("Execution 'objective' must be non-empty.")

        run_id = f"run-{uuid.uuid4().hex[:10]}"
        now = _utc_now()
        events: List[Dict[str, Any]] = [
            {
                "seq": 1,
                "type": "run.started",
                "run_id": run_id,
                "workspace_id": ws,
                "kind": clean_kind,
                "target_id": clean_target,
                "objective": clean_objective,
                "timestamp": now,
            },
            {
                "seq": 2,
                "type": "step.tool_call",
                "run_id": run_id,
                "step": "inspect_context",
                "detail": f"Inspecting {clean_kind} '{clean_target}' workspace state in '{ws}'.",
                "digest_sha256": _sha256(f"{run_id}:2:inspect_context:{ws}:{clean_target}"),
                "timestamp": now,
            },
            {
                "seq": 3,
                "type": "step.completed",
                "run_id": run_id,
                "step": "synthesize_plan",
                "detail": f"Synthesized deterministic execution plan for: {clean_objective[:180]}",
                "digest_sha256": _sha256(f"{run_id}:3:synthesize_plan:{clean_objective}"),
                "timestamp": now,
            },
        ]

        if requires_p10:
            run_status = "awaiting_p10_approval"
            events.append(
                {
                    "seq": 4,
                    "type": "p10.held",
                    "run_id": run_id,
                    "status": "awaiting_p10_approval",
                    "message": "Held at P-10 human-only checkpoint",
                    "timestamp": now,
                }
            )
            emit_type = "execution.p10.held"
        else:
            run_status = "completed"
            receipt = _sha256(f"{run_id}:completed:{ws}:{clean_target}:{now}")
            events.append(
                {
                    "seq": 4,
                    "type": "run.completed",
                    "run_id": run_id,
                    "status": "completed",
                    "receipt_sha256": receipt,
                    "timestamp": now,
                }
            )
            emit_type = "execution.run.completed"

        run_record: Dict[str, Any] = {
            "run_id": run_id,
            "workspace_id": ws,
            "kind": clean_kind,
            "target_id": clean_target,
            "objective": clean_objective,
            "initiator": clean_initiator,
            "requires_p10": bool(requires_p10),
            "status": run_status,
            "p10_decision": None,
            "events": events,
            "created_at": now,
            "updated_at": now,
        }

        with self._lock:
            self._runs[run_id] = run_record
            self._persist_locked(run_record)
            snapshot = self._clone_run(run_record)

        if self.webhook_bus is not None:
            self.webhook_bus.emit_event(
                workspace_id=ws,
                event_type=emit_type,
                payload={
                    "run_id": run_id,
                    "kind": clean_kind,
                    "target_id": clean_target,
                    "status": run_status,
                },
            )
        return snapshot

    def get_run(self, run_id: str) -> Dict[str, Any]:
        clean_id = str(run_id or "").strip()
        with self._lock:
            run = self._runs.get(clean_id)
            if run is None:
                row = self._conn.execute(
                    "SELECT payload_json FROM platform_execution_runs WHERE run_id = ?",
                    (clean_id,),
                ).fetchone()
                if row is None:
                    raise KeyError(f"Execution run '{clean_id}' not found.")
                run = json.loads(str(row["payload_json"]))
                self._runs[clean_id] = run
            return self._clone_run(run)

    def list_runs(self, workspace_id: str = "default") -> List[Dict[str, Any]]:
        ws = str(workspace_id or "default").strip() or "default"
        with self._lock:
            return [self._clone_run(r) for r in self._runs.values() if r["workspace_id"] == ws]

    def resolve_p10(
        self,
        run_id: str,
        decision: str,
        approver: str = "local-operator",
        reason: str = "",
        disallow_self_approval: bool = False,
    ) -> Dict[str, Any]:
        clean_decision = str(decision or "").strip().lower()
        if clean_decision not in VALID_P10_DECISIONS:
            raise ValueError("P-10 decision must be 'approve' or 'deny'.")
        clean_approver = str(approver or "local-operator").strip() or "local-operator"
        if clean_approver.lower().startswith(_AUTOMATED_ACTOR_PREFIXES):
            raise ValueError(
                "P-10 is a human-only checkpoint; autonomous agent identities cannot approve or deny P-10."
            )
        clean_reason = str(reason or "").strip()

        with self._lock:
            current = self.get_run(run_id)
            if current["status"] != "awaiting_p10_approval":
                raise ValueError(
                    f"Run '{run_id}' has status '{current['status']}' and is not awaiting P-10 approval."
                )
            run_initiator = str(current.get("initiator") or "").strip()
            if disallow_self_approval and run_initiator and clean_approver == run_initiator:
                raise PermissionError(
                    f"P-10 self-approval denied: initiator '{run_initiator}' cannot approve their own checkpoint."
                )

            now = _utc_now()
            next_seq = len(current["events"]) + 1
            p10_receipt = _sha256(f"{run_id}:p10:{clean_decision}:{clean_approver}:{clean_reason}:{now}")

            if clean_decision == "approve":
                current["events"].append(
                    {
                        "seq": next_seq,
                        "type": "p10.approved",
                        "run_id": run_id,
                        "approver": clean_approver,
                        "reason": clean_reason,
                        "p10_receipt_sha256": p10_receipt,
                        "timestamp": now,
                    }
                )
                current["events"].append(
                    {
                        "seq": next_seq + 1,
                        "type": "run.completed",
                        "run_id": run_id,
                        "status": "completed",
                        "p10_receipt_sha256": p10_receipt,
                        "receipt_sha256": _sha256(f"{run_id}:completed:{p10_receipt}"),
                        "timestamp": now,
                    }
                )
                current["status"] = "completed"
                webhook_event = "execution.p10.approved"
            else:
                current["events"].append(
                    {
                        "seq": next_seq,
                        "type": "p10.denied",
                        "run_id": run_id,
                        "approver": clean_approver,
                        "reason": clean_reason,
                        "p10_receipt_sha256": p10_receipt,
                        "timestamp": now,
                    }
                )
                current["events"].append(
                    {
                        "seq": next_seq + 1,
                        "type": "run.aborted",
                        "run_id": run_id,
                        "status": "aborted_by_p10",
                        "p10_receipt_sha256": p10_receipt,
                        "timestamp": now,
                    }
                )
                current["status"] = "aborted_by_p10"
                webhook_event = "execution.p10.denied"

            current["p10_decision"] = {
                "decision": clean_decision,
                "approver": clean_approver,
                "reason": clean_reason,
                "p10_receipt_sha256": p10_receipt,
                "decided_at": now,
            }
            current["updated_at"] = now
            self._runs[run_id] = current
            self._persist_locked(current)
            snapshot = self._clone_run(current)

        if self.webhook_bus is not None:
            self.webhook_bus.emit_event(
                workspace_id=snapshot["workspace_id"],
                event_type=webhook_event,
                payload={
                    "run_id": run_id,
                    "status": snapshot["status"],
                    "decision": clean_decision,
                    "approver": clean_approver,
                    "p10_receipt_sha256": p10_receipt,
                },
            )
        return snapshot

    def iter_sse_lines(self, run_id: str) -> Iterator[str]:
        run = self.get_run(run_id)
        for evt in run["events"]:
            yield f"data: {json.dumps(evt, separators=(',', ':'))}\n\n"
        yield "data: [DONE]\n\n"


live_execution_streamer = LiveExecutionStreamer(webhook_bus=signed_webhook_bus)
