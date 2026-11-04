"""Local-only reference workflow engine. Not a security boundary or production daemon."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path, PurePosixPath
import json
import os
import sqlite3
import stat
import tempfile
import time
import uuid
from typing import Any


class WorkflowError(RuntimeError):
    pass


def digest(data: bytes) -> str:
    return sha256(data).hexdigest()


def canonical(data: Any) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def safe_target(root_str: str, relative: str) -> Path:
    """Restrict to existing regular files beneath a symlink-free workspace subtree.

    This is a development guard, *not* a race-resistant privileged filesystem sandbox.
    """
    if not relative or "\\" in relative or "\x00" in relative:
        raise WorkflowError("invalid file path")
    rel = PurePosixPath(relative)
    if rel.is_absolute() or any(part in ("", ".", "..") for part in relative.split("/")):
        raise WorkflowError("workspace path escapes or is not canonical")
    root = Path(root_str)
    if not root.is_dir():
        raise WorkflowError("workspace unavailable")
    root = root.resolve(strict=True)
    target = root
    for part in rel.parts:
        target = target / part
        try:
            meta = target.lstat()
        except FileNotFoundError as exc:
            raise WorkflowError("only edits to existing files are supported") from exc
        if stat.S_ISLNK(meta.st_mode):
            raise WorkflowError("symlinks are prohibited")
    if not target.is_file() or not target.resolve().is_relative_to(root):
        raise WorkflowError("target is not a regular workspace file")
    return target


@dataclass(frozen=True)
class Task:
    id: str
    workspace: str
    goal: str
    state: str


class Engine:
    def __init__(self, database: str):
        self.database = str(database)
        self.db = sqlite3.connect(database)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA busy_timeout=3000")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY, workspace TEXT NOT NULL, goal TEXT NOT NULL,
                state TEXT NOT NULL, created_at REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS proposals (
                id TEXT PRIMARY KEY, task_id TEXT NOT NULL UNIQUE REFERENCES tasks(id),
                relpath TEXT NOT NULL, base_sha TEXT NOT NULL, target_sha TEXT NOT NULL,
                content BLOB NOT NULL, plan_digest TEXT NOT NULL,
                approved_by TEXT, applied INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS events (
                seq INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL REFERENCES tasks(id),
                kind TEXT NOT NULL, payload_json TEXT NOT NULL,
                prev_sha TEXT NOT NULL, entry_sha TEXT NOT NULL, created_at REAL NOT NULL);
        """)
        self.db.commit()

    def close(self) -> None:
        self.db.close()

    def _task(self, task_id: str) -> sqlite3.Row:
        row = self.db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        if row is None:
            raise WorkflowError("unknown task")
        return row

    def _proposal(self, task_id: str) -> sqlite3.Row:
        row = self.db.execute("SELECT * FROM proposals WHERE task_id=?", (task_id,)).fetchone()
        if row is None:
            raise WorkflowError("task has no proposal")
        return row

    def _event(self, task_id: str, kind: str, payload: dict) -> None:
        row = self.db.execute("SELECT entry_sha FROM events WHERE task_id=? ORDER BY seq DESC LIMIT 1", (task_id,)).fetchone()
        prior = row[0] if row else "0" * 64
        serialized = canonical({"task_id": task_id, "kind": kind, "payload": payload, "previous": prior})
        entry = digest(serialized)
        self.db.execute("INSERT INTO events(task_id,kind,payload_json,prev_sha,entry_sha,created_at) VALUES(?,?,?,?,?,?)", (task_id, kind, json.dumps(payload, sort_keys=True), prior, entry, time.time()))

    def create(self, workspace: str, goal: str) -> str:
        root = Path(workspace).resolve(strict=True)
        if not root.is_dir() or not goal.strip():
            raise WorkflowError("workspace directory and nonempty goal required")
        task_id = str(uuid.uuid4())
        with self.db:
            self.db.execute("INSERT INTO tasks VALUES (?,?,?,?,?)", (task_id, str(root), goal, "CREATED", time.time()))
            self._event(task_id, "CREATED", {"goal": goal, "workspace": str(root)})
        return task_id

    def task(self, task_id: str) -> dict:
        r = self._task(task_id)
        return {"id": r["id"], "workspace": r["workspace"], "goal": r["goal"], "state": r["state"]}

    def propose(self, task_id: str, relpath: str, content: bytes) -> dict:
        task = self._task(task_id)
        if task["state"] != "CREATED":
            raise WorkflowError("proposal only allowed from CREATED")
        path = safe_target(task["workspace"], relpath)
        base_sha = digest(path.read_bytes())
        target_sha = digest(content)
        body = {"task": task_id, "relpath": relpath, "base_sha": base_sha, "target_sha": target_sha}
        plan_digest = digest(canonical(body))
        with self.db:
            self.db.execute("INSERT INTO proposals(id,task_id,relpath,base_sha,target_sha,content,plan_digest) VALUES(?,?,?,?,?,?,?)", (str(uuid.uuid4()), task_id, relpath, base_sha, target_sha, content, plan_digest))
            self.db.execute("UPDATE tasks SET state='AWAITING_APPROVAL' WHERE id=?", (task_id,))
            self._event(task_id, "PROPOSED", body)
        return {**body, "plan_digest": plan_digest, "state": "AWAITING_APPROVAL"}

    def proposal(self, task_id: str) -> dict:
        p = self._proposal(task_id)
        return {k: p[k] for k in ("relpath", "base_sha", "target_sha", "plan_digest", "approved_by", "applied")}

    def approve(self, task_id: str, expected_digest: str, approver: str) -> None:
        task, p = self._task(task_id), self._proposal(task_id)
        if task["state"] != "AWAITING_APPROVAL" or not approver.strip() or len(expected_digest) != 64 or expected_digest != p["plan_digest"]:
            raise WorkflowError("approval denied: task state, approver, or exact digest mismatch")
        with self.db:
            self.db.execute("UPDATE proposals SET approved_by=? WHERE task_id=?", (approver, task_id))
            self.db.execute("UPDATE tasks SET state='APPROVED' WHERE id=?", (task_id,))
            self._event(task_id, "APPROVED", {"by": approver, "digest": expected_digest})

    def apply(self, task_id: str) -> dict:
        task, p = self._task(task_id), self._proposal(task_id)
        if task["state"] != "APPROVED" or not p["approved_by"] or p["applied"]:
            raise WorkflowError("apply denied: missing approval or invalid state")
        target = safe_target(task["workspace"], p["relpath"])
        if digest(target.read_bytes()) != p["base_sha"]:
            raise WorkflowError("source changed since proposal: no overwrite performed")
        # Development-only local filesystem mutation: no privilege or cross-process lock.
        mode = target.stat().st_mode & 0o777
        tmp = None
        try:
            with tempfile.NamedTemporaryFile(dir=str(target.parent), prefix=".keelway-", delete=False) as f:
                tmp = Path(f.name)
                f.write(p["content"])
                f.flush()
                os.fsync(f.fileno())
            os.chmod(tmp, mode)
            if digest(target.read_bytes()) != p["base_sha"]:
                raise WorkflowError("source changed during apply: aborted")
            os.replace(tmp, target)
            tmp = None
            with self.db:
                self.db.execute("UPDATE proposals SET applied=1 WHERE task_id=?", (task_id,))
                self.db.execute("UPDATE tasks SET state='VERIFYING' WHERE id=?", (task_id,))
                self._event(task_id, "APPLIED", {"relpath": p["relpath"], "target_sha": p["target_sha"]})
        finally:
            if tmp is not None:
                tmp.unlink(missing_ok=True)
        return {"path": p["relpath"], "sha256": digest(target.read_bytes()), "state": "VERIFYING"}

    def mark_verified(self, task_id: str, command: list[str], exit_code: int, stdout_hash: str, evidence: str) -> dict:
        """Only the caller that actually ran tests may invoke; do not trust as attestation."""
        task = self._task(task_id)
        if task["state"] != "VERIFYING":
            raise WorkflowError("verification only from VERIFYING")
        state = "COMPLETED" if exit_code == 0 else "FAILED"
        with self.db:
            self.db.execute("UPDATE tasks SET state=? WHERE id=?", (state, task_id))
            self._event(task_id, "TEST_EXECUTION", {"command": command, "exit_code": exit_code, "output_sha256": stdout_hash, "evidence": evidence})
        return {"state": state, "exit_code": exit_code, "output_sha256": stdout_hash}

    def cancel(self, task_id: str) -> None:
        task = self._task(task_id)
        if task["state"] in ("COMPLETED", "FAILED", "CANCELLED"):
            raise WorkflowError("terminal task cannot cancel")
        with self.db:
            self.db.execute("UPDATE tasks SET state='CANCELLED' WHERE id=?", (task_id,))
            self._event(task_id, "CANCELLED", {})

    def audit(self, task_id: str) -> dict:
        self._task(task_id)
        prior = "0" * 64
        rows = self.db.execute("SELECT kind,payload_json,prev_sha,entry_sha FROM events WHERE task_id=? ORDER BY seq", (task_id,)).fetchall()
        for row in rows:
            payload = json.loads(row["payload_json"])
            if prior != row["prev_sha"] or digest(canonical({"task_id": task_id, "kind": row["kind"], "payload": payload, "previous": prior})) != row["entry_sha"]:
                return {"ok": False, "events": len(rows), "reason": "audit chain mismatch"}
            prior = row["entry_sha"]
        return {"ok": True, "events": len(rows), "last_sha256": prior, "warning": "local hash chain is NOT signed or tamper-proof against database owners"}
