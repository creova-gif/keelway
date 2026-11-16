"""
Phase 14 Live Step-Through Debugger Engine, Conditional Gutter Breakpoints, DLP-Guarded
State Mutation & 4D Routing CodeLens (`core.platform.step_debugger`).
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import threading
from typing import Any, Dict, List, Optional, Pattern, Sequence, Tuple, Union
import uuid

from core.platform.flight_tape import _clean_workspace_id
from core.platform.kflow_bidirectional_sync import resolve_studio_db_target

VALID_CONDITION_TYPES: Tuple[str, ...] = (
    "always", "cost_usd_gt", "hybrid_score_lt", "before_shell_tool", "before_p10_gate", "line_match",
)
VALID_STEP_ACTIONS: Tuple[str, ...] = ("step_over", "step_into", "continue", "mutate_state")
_SECRET_DLP_PATTERNS: Tuple[Pattern[str], ...] = (
    re.compile(r"sk-[A-Za-z0-9_-]{12,}"),
    re.compile(r"AKIA[0-9A-Z]{12,}"),
    re.compile(r"ghp_[A-Za-z0-9]{16,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
)
_SYMBOL_PATTERNS: Tuple[Pattern[str], ...] = (
    re.compile(r"""(?:\.add_node|\bstudio\.node)\s*\(\s*['"]([A-Za-z0-9_.-]+)['"]"""),
    re.compile(r"""\.addNode\s*\(\s*['"`]([A-Za-z0-9_.-]+)['"`]"""),
    re.compile(r"""\bid\s*:\s*['"`]([A-Za-z0-9_.-]+)['"`]"""),
    re.compile(r"""^\s*(?:async\s+)?def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\("""),
    re.compile(r"""^\s*(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*\("""),
)
_DEFAULT_STEPS: Tuple[Dict[str, Any], ...] = (
    {"node_id": "triage_claim", "agent_id": "intake-router", "tool_name": "kbrain_query", "cost_usd": 0.04, "hybrid_score": 0.88, "requires_p10": False, "line_number": 8, "variables": {"claim_id": "CLM-402", "refund_usd": 180}},
    {"node_id": "verify_ledger", "agent_id": "shell-auditor", "tool_name": "shell_exec", "cost_usd": 0.31, "hybrid_score": 0.42, "requires_p10": False, "line_number": 14, "variables": {"ledger_ok": True}},
    {"node_id": "approve_payout", "agent_id": "treasury-guard", "tool_name": "stripe_refund", "cost_usd": 0.09, "hybrid_score": 0.94, "requires_p10": True, "line_number": 21, "variables": {"approved": False}},
)
_DEFAULT_CODELENS_SPECS: Tuple[Dict[str, Any], ...] = (
    {"symbol": "triage_claim", "line_start": 8, "model_checkpoint": "keelway-core:7b", "p50_ms": 142, "avg_cost_usd": 0.0, "provenance_4d": "Apache-2.0 · Local Metal · Self-Operated · Zero-Egress"},
    {"symbol": "verify_ledger", "line_start": 14, "model_checkpoint": "keelway-core:7b", "p50_ms": 218, "avg_cost_usd": 0.0, "provenance_4d": "Apache-2.0 · Local Metal · Seatbelt-Confined · Zero-Egress"},
    {"symbol": "approve_payout", "line_start": 21, "model_checkpoint": "claude-3-7-sonnet", "p50_ms": 390, "avg_cost_usd": 0.009, "provenance_4d": "Commercial · Frontier Cloud · Audited · P-10-Gated"},
)
_DEBUGGER_SCHEMA_SQL = (
    "CREATE TABLE IF NOT EXISTS debugger_breakpoints ("
    "breakpoint_id TEXT NOT NULL, workspace_id TEXT NOT NULL, workflow_id TEXT NOT NULL, node_id TEXT, "
    "file_path TEXT NOT NULL, line_number INTEGER, condition_type TEXT NOT NULL, threshold REAL, "
    "enabled INTEGER NOT NULL, label TEXT NOT NULL, created_at TEXT NOT NULL, "
    "PRIMARY KEY (workspace_id, breakpoint_id)); "
    "CREATE INDEX IF NOT EXISTS idx_debugger_breakpoints_ws_wf ON debugger_breakpoints(workspace_id, workflow_id, created_at ASC); "
    "CREATE TABLE IF NOT EXISTS debugger_sessions ("
    "session_id TEXT NOT NULL, workspace_id TEXT NOT NULL, workflow_id TEXT NOT NULL, status TEXT NOT NULL, "
    "current_step_index INTEGER NOT NULL, step_depth INTEGER NOT NULL, total_steps INTEGER NOT NULL, "
    "hit_breakpoint_id TEXT, hit_reason TEXT, steps_json TEXT NOT NULL, active_step_json TEXT NOT NULL, "
    "variables_json TEXT NOT NULL, call_stack_json TEXT NOT NULL, mutation_count INTEGER NOT NULL, "
    "mutations_json TEXT NOT NULL, frame_sha256 TEXT NOT NULL, updated_at TEXT NOT NULL, "
    "PRIMARY KEY (workspace_id, session_id)); "
    "CREATE INDEX IF NOT EXISTS idx_debugger_sessions_ws_time ON debugger_sessions(workspace_id, updated_at DESC);"
)


class DebuggerPolicyViolationError(ValueError):
    """Raised when debugger state mutation payloads contain secret material blocked by DLP."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _assert_no_dlp_secrets(payload: Any) -> None:
    if payload is None:
        return
    serialized = payload if isinstance(payload, str) else _canonical_json(payload)
    for pattern in _SECRET_DLP_PATTERNS:
        if pattern.search(serialized):
            raise DebuggerPolicyViolationError(
                "DLP policy violation: raw secret token detected in state_patch; mutation rejected before SQLite persistence."
            )


def _compute_frame_sha256(ws: str, wf: str, status: str, idx: int, depth: int, variables: Dict[str, Any], muts: int) -> str:
    return hashlib.sha256(_canonical_json([ws, wf, status, idx, depth, variables, muts]).encode("utf-8")).hexdigest()


def _normalize_step(raw: Dict[str, Any], index: int) -> Dict[str, Any]:
    line_raw = raw.get("line_number")
    line_no = int(line_raw) if line_raw is not None and not isinstance(line_raw, bool) else (index + 1) * 6
    raw_vars = raw.get("variables")
    return {
        "node_id": str(raw.get("node_id") or f"step_{index + 1}").strip() or f"step_{index + 1}",
        "agent_id": str(raw.get("agent_id") or "governed-agent").strip() or "governed-agent",
        "tool_name": str(raw.get("tool_name") or "agent_step").strip() or "agent_step",
        "cost_usd": round(float(raw.get("cost_usd", 0.0) or 0.0), 6),
        "hybrid_score": round(float(raw.get("hybrid_score", 1.0) if raw.get("hybrid_score") is not None else 1.0), 4),
        "requires_p10": bool(raw.get("requires_p10", False)),
        "line_number": line_no,
        "variables": dict(raw_vars) if isinstance(raw_vars, dict) else {},
    }


def _build_call_stack(active_step: Dict[str, Any], step_index: int, step_depth: int) -> List[Dict[str, Any]]:
    base_line, tool = int(active_step.get("line_number", 1)), str(active_step.get("tool_name", "inner") or "inner")
    stack = [{"depth": 0, "node_id": str(active_step["node_id"]), "agent_id": str(active_step["agent_id"]), "line_number": base_line, "tool_name": tool, "frame_index": step_index}]
    for d in range(1, step_depth + 1):
        stack.append({"depth": d, "node_id": f"{active_step['node_id']}:{tool}", "agent_id": str(active_step["agent_id"]), "line_number": base_line + d, "tool_name": tool, "frame_index": step_index})
    return stack


def _match_breakpoint(step: Dict[str, Any], bp: Dict[str, Any]) -> Optional[str]:
    if not bp.get("enabled", True):
        return None
    bp_node = bp.get("node_id")
    if bp_node is not None and str(bp_node).strip() and str(bp_node).strip() != "*":
        if str(step.get("node_id", "")) != str(bp_node).strip():
            return None
    cond = str(bp["condition_type"])
    if cond == "always":
        return "always (step boundary)"
    if cond == "cost_usd_gt":
        thr, cost = float(bp["threshold"]) if bp.get("threshold") is not None else 0.25, float(step.get("cost_usd", 0.0))
        return f"cost_usd_gt ({cost:.2f} > {thr:.2f})" if cost > thr else None
    if cond == "hybrid_score_lt":
        thr, score = float(bp["threshold"]) if bp.get("threshold") is not None else 0.50, float(step.get("hybrid_score", 1.0))
        return f"hybrid_score_lt ({score:.2f} < {thr:.2f})" if score < thr else None
    if cond == "before_shell_tool":
        tool_norm = str(step.get("tool_name", "")).lower()
        return f"before_shell_tool ({step.get('tool_name', '')})" if any(t in tool_norm for t in ("shell", "bash", "exec")) else None
    if cond == "before_p10_gate":
        return f"before_p10_gate ({step.get('node_id', '')})" if bool(step.get("requires_p10", False)) else None
    if cond == "line_match":
        bp_line = bp.get("line_number")
        if bp_line is not None:
            return f"line_match (L{bp_line})" if int(step.get("line_number", -1)) == int(bp_line) else None
        if bp_node is not None and str(bp_node).strip() and str(bp_node).strip() != "*":
            return f"line_match ({bp_node})"
    return None


def _extract_source_symbols(source_code: str) -> List[Tuple[str, int, str]]:
    found: List[Tuple[str, int, str]] = []
    seen: set[str] = set()
    for idx, line in enumerate(source_code.splitlines(), start=1):
        for regex in _SYMBOL_PATTERNS:
            for match in regex.finditer(line):
                sym = match.group(1).strip()
                if sym and sym not in {"START", "END", "__start__", "__end__", "main"} and sym not in seen:
                    seen.add(sym)
                    found.append((sym, idx, line))
    return found


def _format_session_dict(
    sid: str, ws: str, wf: str, status: str, idx: int, depth: int, total: int,
    hit_bp_id: Optional[str], hit_reason: Optional[str], active_step: Dict[str, Any],
    variables: Dict[str, Any], call_stack: List[Dict[str, Any]], mut_count: int,
    mutations: List[Dict[str, Any]], frame_sha: str, updated_at: str,
) -> Dict[str, Any]:
    return {
        "session_id": sid, "workspace_id": ws, "workflow_id": wf, "status": status,
        "current_step_index": idx, "step_depth": depth, "total_steps": total,
        "hit_breakpoint_id": hit_bp_id, "hit_reason": hit_reason,
        "active_step": active_step, "active_frame": active_step, "variables": variables,
        "call_stack": call_stack, "mutation_count": mut_count, "mutations": mutations,
        "frame_sha256": frame_sha, "updated_at": updated_at,
    }


class SQLiteStepDebuggerEngine:
    """Thread-safe SQLite WAL engine for live conditional breakpoints, paused frame stepping, and 4D CodeLens."""

    def __init__(self, db_path: Optional[Union[str, Path]] = None) -> None:
        self._lock = threading.RLock()
        self._explicit_db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._active_target: Optional[str] = None
        self._db_path: Union[str, Path] = ":memory:"
        self._closed = False
        with self._lock:
            self._ensure_conn()

    def _ensure_conn(self) -> sqlite3.Connection:
        resolved_path, connect_target = resolve_studio_db_target(self._explicit_db_path)
        if self._conn is not None and not self._closed and self._active_target == connect_target:
            return self._conn
        if self._conn is not None and not self._closed:
            self._conn.close()
        conn = sqlite3.connect(connect_target, check_same_thread=False, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        with conn:
            conn.executescript(_DEBUGGER_SCHEMA_SQL)
        self._conn, self._active_target, self._db_path, self._closed = conn, connect_target, resolved_path, False
        return conn

    @property
    def db_path(self) -> Union[str, Path]:
        with self._lock:
            if self._explicit_db_path is None and not self._closed:
                self._ensure_conn()
            return self._db_path

    def close(self) -> None:
        with self._lock:
            if self._conn is not None and not self._closed:
                self._conn.close()
                self._closed = True

    @staticmethod
    def _row_to_breakpoint(row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "breakpoint_id": str(row["breakpoint_id"]), "workspace_id": str(row["workspace_id"]), "workflow_id": str(row["workflow_id"]),
            "node_id": str(row["node_id"]) if row["node_id"] is not None else None, "file_path": str(row["file_path"]),
            "line_number": int(row["line_number"]) if row["line_number"] is not None else None, "condition_type": str(row["condition_type"]),
            "threshold": float(row["threshold"]) if row["threshold"] is not None else None, "enabled": bool(row["enabled"]),
            "label": str(row["label"]), "created_at": str(row["created_at"]),
        }

    @staticmethod
    def _row_to_session(row: sqlite3.Row) -> Dict[str, Any]:
        return _format_session_dict(
            str(row["session_id"]), str(row["workspace_id"]), str(row["workflow_id"]), str(row["status"]),
            int(row["current_step_index"]), int(row["step_depth"]), int(row["total_steps"]),
            str(row["hit_breakpoint_id"]) if row["hit_breakpoint_id"] is not None else None,
            str(row["hit_reason"]) if row["hit_reason"] is not None else None,
            json.loads(str(row["active_step_json"])), json.loads(str(row["variables_json"])), json.loads(str(row["call_stack_json"])),
            int(row["mutation_count"]), json.loads(str(row["mutations_json"])), str(row["frame_sha256"]), str(row["updated_at"]),
        )

    def set_breakpoint(
        self, workspace_id: str = "default", workflow_id: str = "WF-STUDIO-01", node_id: Optional[str] = None,
        file_path: str = "workflows/refund_agent.py", line_number: Optional[int] = None,
        condition_type: str = "always", threshold: Optional[float] = None, enabled: bool = True, label: Optional[str] = None,
    ) -> Dict[str, Any]:
        ws, wf, cond = _clean_workspace_id(workspace_id), str(workflow_id or "WF-STUDIO-01").strip() or "WF-STUDIO-01", str(condition_type or "").strip()
        if cond not in VALID_CONDITION_TYPES:
            raise ValueError(f"Unsupported condition_type '{cond}'. Expected one of {list(VALID_CONDITION_TYPES)}.")
        clean_node = str(node_id).strip() if node_id is not None and str(node_id).strip() else None
        clean_file = str(file_path or "workflows/refund_agent.py").strip() or "workflows/refund_agent.py"
        if line_number is not None and (isinstance(line_number, bool) or int(line_number) < 1):
            raise ValueError("line_number must be a positive integer.")
        clean_line = int(line_number) if line_number is not None else None
        if threshold is not None and isinstance(threshold, bool):
            raise ValueError("threshold must be numeric.")
        clean_thr = float(threshold) if threshold is not None else None
        eff_enabled = bool(enabled)
        eff_label = str(label).strip() if label is not None and str(label).strip() else f"{cond}" + (f" ({clean_thr})" if clean_thr is not None else "")
        bp_id, created_at = f"bp-{uuid.uuid4().hex[:12]}", _utc_now()
        with self._lock:
            conn = self._ensure_conn()
            with conn:
                conn.execute("INSERT INTO debugger_breakpoints VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (bp_id, ws, wf, clean_node, clean_file, clean_line, cond, clean_thr, 1 if eff_enabled else 0, eff_label, created_at))
        return {
            "breakpoint_id": bp_id, "workspace_id": ws, "workflow_id": wf, "node_id": clean_node, "file_path": clean_file,
            "line_number": clean_line, "condition_type": cond, "threshold": clean_thr, "enabled": eff_enabled, "label": eff_label, "created_at": created_at,
        }

    def list_breakpoints(self, workspace_id: str = "default", workflow_id: Optional[str] = None) -> Dict[str, Any]:
        ws = _clean_workspace_id(workspace_id)
        clean_wf = str(workflow_id).strip() if workflow_id is not None and str(workflow_id).strip() else None
        with self._lock:
            conn = self._ensure_conn()
            if clean_wf is not None:
                rows = conn.execute("SELECT * FROM debugger_breakpoints WHERE workspace_id=? AND workflow_id=? ORDER BY created_at ASC, rowid ASC", (ws, clean_wf)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM debugger_breakpoints WHERE workspace_id=? ORDER BY created_at ASC, rowid ASC", (ws,)).fetchall()
        items = [self._row_to_breakpoint(r) for r in rows]
        return {"workspace_id": ws, "count": len(items), "breakpoints": items}

    def delete_breakpoint(self, workspace_id: str = "default", breakpoint_id: str = "") -> Dict[str, Any]:
        ws, clean_id = _clean_workspace_id(workspace_id), str(breakpoint_id or "").strip()
        if not clean_id:
            raise KeyError("breakpoint_id must be non-empty.")
        with self._lock:
            conn = self._ensure_conn()
            with conn:
                cur = conn.execute("DELETE FROM debugger_breakpoints WHERE workspace_id=? AND breakpoint_id=?", (ws, clean_id))
        if cur.rowcount == 0:
            raise KeyError(f"Breakpoint '{clean_id}' not found in workspace '{ws}'.")
        return {"deleted": True, "breakpoint_id": clean_id, "workspace_id": ws}

    def _load_active_breakpoints(self, conn: sqlite3.Connection, ws: str, wf: str) -> List[Dict[str, Any]]:
        rows = conn.execute(
            "SELECT * FROM debugger_breakpoints WHERE workspace_id=? AND enabled=1 AND (workflow_id=? OR workflow_id='*') ORDER BY created_at ASC, rowid ASC",
            (ws, wf),
        ).fetchall()
        return [self._row_to_breakpoint(r) for r in rows]

    @staticmethod
    def _first_matching_bp(step: Dict[str, Any], bps: Sequence[Dict[str, Any]]) -> Tuple[Optional[str], Optional[str]]:
        for bp in bps:
            reason = _match_breakpoint(step, bp)
            if reason is not None:
                return str(bp["breakpoint_id"]), reason
        return None, None

    def start_session(
        self, workspace_id: str = "default", workflow_id: str = "WF-STUDIO-01",
        steps: Optional[Sequence[Dict[str, Any]]] = None, initial_state: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        ws = _clean_workspace_id(workspace_id)
        wf = str(workflow_id or "WF-STUDIO-01").strip() or "WF-STUDIO-01"
        _assert_no_dlp_secrets(initial_state)
        norm_steps = [_normalize_step(s, idx) for idx, s in enumerate(list(steps) if steps else [dict(s) for s in _DEFAULT_STEPS])]
        variables: Dict[str, Any] = dict(initial_state) if isinstance(initial_state, dict) else {"tenant": "acme", "dry_run": True}
        with self._lock:
            bps = self._load_active_breakpoints(self._ensure_conn(), ws, wf)

        status, curr_idx, hit_bp_id, hit_reason = "COMPLETED", len(norm_steps) - 1, None, None
        for idx, step in enumerate(norm_steps):
            variables.update(step.get("variables") or {})
            matched_id, matched_reason = self._first_matching_bp(step, bps)
            if matched_id is not None:
                status, curr_idx, hit_bp_id, hit_reason = "PAUSED", idx, matched_id, matched_reason
                break

        active_step = norm_steps[curr_idx]
        call_stack = _build_call_stack(active_step, curr_idx, 0)
        session_id, updated_at = f"dbg-{uuid.uuid4().hex[:12]}", _utc_now()
        frame_sha256 = _compute_frame_sha256(ws, wf, status, curr_idx, 0, variables, 0)
        with self._lock:
            conn = self._ensure_conn()
            with conn:
                conn.execute(
                    "INSERT INTO debugger_sessions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (session_id, ws, wf, status, curr_idx, 0, len(norm_steps), hit_bp_id, hit_reason, _canonical_json(norm_steps), _canonical_json(active_step), _canonical_json(variables), _canonical_json(call_stack), 0, "[]", frame_sha256, updated_at),
                )
        return _format_session_dict(session_id, ws, wf, status, curr_idx, 0, len(norm_steps), hit_bp_id, hit_reason, active_step, variables, call_stack, 0, [], frame_sha256, updated_at)

    def get_session(self, workspace_id: str = "default", session_id: str = "") -> Dict[str, Any]:
        ws, clean_sid = _clean_workspace_id(workspace_id), str(session_id or "").strip()
        if not clean_sid:
            raise KeyError("session_id must be non-empty.")
        with self._lock:
            row = self._ensure_conn().execute("SELECT * FROM debugger_sessions WHERE workspace_id=? AND session_id=?", (ws, clean_sid)).fetchone()
        if row is None:
            raise KeyError(f"Debugger session '{clean_sid}' not found in workspace '{ws}'.")
        return self._row_to_session(row)

    def list_sessions(self, workspace_id: str = "default", limit: int = 20) -> Dict[str, Any]:
        ws = _clean_workspace_id(workspace_id)
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise ValueError("limit must be a positive integer.")
        with self._lock:
            rows = self._ensure_conn().execute("SELECT * FROM debugger_sessions WHERE workspace_id=? ORDER BY updated_at DESC, rowid DESC LIMIT ?", (ws, min(limit, 200))).fetchall()
        items = [self._row_to_session(r) for r in rows]
        return {"workspace_id": ws, "count": len(items), "sessions": items}

    def step_session(
        self, workspace_id: str = "default", session_id: str = "",
        action: str = "step_over", state_patch: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        ws, clean_action = _clean_workspace_id(workspace_id), str(action or "").strip()
        if clean_action not in VALID_STEP_ACTIONS:
            raise ValueError(f"Unsupported debugger action '{clean_action}'. Expected {list(VALID_STEP_ACTIONS)}.")
        if state_patch is not None:
            if not isinstance(state_patch, dict):
                raise ValueError("state_patch must be a JSON object.")
            _assert_no_dlp_secrets(state_patch)

        clean_sid = str(session_id or "").strip()
        with self._lock:
            conn = self._ensure_conn()
            row = conn.execute("SELECT * FROM debugger_sessions WHERE workspace_id=? AND session_id=?", (ws, clean_sid)).fetchone()
            if row is None:
                raise KeyError(f"Debugger session '{clean_sid}' not found in workspace '{ws}'.")
            wf, status = str(row["workflow_id"]), str(row["status"])
            curr_idx, step_depth = int(row["current_step_index"]), int(row["step_depth"])
            hit_bp_id = str(row["hit_breakpoint_id"]) if row["hit_breakpoint_id"] is not None else None
            hit_reason = str(row["hit_reason"]) if row["hit_reason"] is not None else None
            steps: List[Dict[str, Any]] = json.loads(str(row["steps_json"]))
            variables: Dict[str, Any] = json.loads(str(row["variables_json"]))
            mutation_count = int(row["mutation_count"])
            mutations: List[Dict[str, Any]] = json.loads(str(row["mutations_json"]))
            bps = self._load_active_breakpoints(conn, ws, wf)

        total_steps = len(steps)
        if state_patch:
            variables.update(state_patch)
            mutation_count += 1
            mutations.append({"seq": mutation_count, "patched_keys": sorted(str(k) for k in state_patch.keys()), "at_step": curr_idx})

        def _advance_one() -> Tuple[int, str, Optional[str], Optional[str]]:
            if curr_idx + 1 >= total_steps:
                return total_steps - 1, "COMPLETED", None, None
            nxt = curr_idx + 1
            variables.update(steps[nxt].get("variables") or {})
            m_id, m_reason = self._first_matching_bp(steps[nxt], bps)
            return nxt, "PAUSED", m_id, m_reason or "step_over"

        if clean_action == "step_into":
            if status == "PAUSED" and step_depth == 0:
                step_depth, hit_bp_id = 1, None
                hit_reason = f"step_into ({steps[curr_idx]['node_id']}:{steps[curr_idx].get('tool_name', 'inner')})"
            else:
                step_depth = 0
                curr_idx, status, hit_bp_id, hit_reason = _advance_one()
        elif clean_action == "step_over":
            step_depth = 0
            curr_idx, status, hit_bp_id, hit_reason = _advance_one()
        elif clean_action == "continue":
            step_depth, paused_next = 0, False
            for idx in range(curr_idx + 1, total_steps):
                variables.update(steps[idx].get("variables") or {})
                m_id, m_reason = self._first_matching_bp(steps[idx], bps)
                if m_id is not None:
                    curr_idx, status, hit_bp_id, hit_reason, paused_next = idx, "PAUSED", m_id, m_reason, True
                    break
            if not paused_next:
                curr_idx, status, hit_bp_id, hit_reason = total_steps - 1, "COMPLETED", None, None

        active_step = steps[curr_idx]
        call_stack = _build_call_stack(active_step, curr_idx, step_depth)
        frame_sha256 = _compute_frame_sha256(ws, wf, status, curr_idx, step_depth, variables, mutation_count)
        updated_at = _utc_now()
        with self._lock:
            conn = self._ensure_conn()
            with conn:
                conn.execute(
                    "UPDATE debugger_sessions SET status=?, current_step_index=?, step_depth=?, hit_breakpoint_id=?, "
                    "hit_reason=?, active_step_json=?, variables_json=?, call_stack_json=?, mutation_count=?, "
                    "mutations_json=?, frame_sha256=?, updated_at=? WHERE workspace_id=? AND session_id=?",
                    (status, curr_idx, step_depth, hit_bp_id, hit_reason, _canonical_json(active_step), _canonical_json(variables), _canonical_json(call_stack), mutation_count, _canonical_json(mutations), frame_sha256, updated_at, ws, clean_sid),
                )
        return _format_session_dict(clean_sid, ws, wf, status, curr_idx, step_depth, total_steps, hit_bp_id, hit_reason, active_step, variables, call_stack, mutation_count, mutations, frame_sha256, updated_at)

    def get_codelens(
        self, workspace_id: str = "default", workflow_id: str = "WF-STUDIO-01",
        file_path: str = "workflows/refund_agent.py", source_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        ws = _clean_workspace_id(workspace_id)
        wf = str(workflow_id or "WF-STUDIO-01").strip() or "WF-STUDIO-01"
        clean_file = str(file_path or "workflows/refund_agent.py").strip() or "workflows/refund_agent.py"
        with self._lock:
            bps = self._load_active_breakpoints(self._ensure_conn(), ws, wf)

        extracted = _extract_source_symbols(source_code) if source_code and source_code.strip() else []
        if extracted:
            raw_specs: List[Dict[str, Any]] = []
            for sym, line_no, raw_line in extracted:
                lower = f"{sym} {raw_line}".lower()
                if any(tok in lower for tok in ("p10", "approve", "payout", "escalat")):
                    raw_specs.append({"symbol": sym, "line_start": line_no, "model_checkpoint": "claude-3-7-sonnet", "p50_ms": 390, "avg_cost_usd": 0.009, "provenance_4d": "Commercial · Frontier Cloud · Audited · P-10-Gated"})
                elif any(tok in lower for tok in ("shell", "ledger", "exec", "audit")):
                    raw_specs.append({"symbol": sym, "line_start": line_no, "model_checkpoint": "keelway-core:7b", "p50_ms": 218, "avg_cost_usd": 0.0, "provenance_4d": "Apache-2.0 · Local Metal · Seatbelt-Confined · Zero-Egress"})
                else:
                    raw_specs.append({"symbol": sym, "line_start": line_no, "model_checkpoint": "keelway-core:7b", "p50_ms": 142, "avg_cost_usd": 0.0, "provenance_4d": "Apache-2.0 · Local Metal · Self-Operated · Zero-Egress"})
        else:
            raw_specs = [dict(item) for item in _DEFAULT_CODELENS_SPECS]

        vscode_uri = f"vscode://keelway.vscode-keelway/attach?port=7420&workspace={ws}&workflow={wf}"
        cursor_uri = f"cursor://keelway.vscode-keelway/attach?port=7420&workspace={ws}&workflow={wf}"
        lenses = [
            {
                "symbol": str(s["symbol"]), "file_path": clean_file, "line_start": int(s["line_start"]), "line": int(s["line_start"]),
                "model_checkpoint": s["model_checkpoint"], "p50_ms": int(s["p50_ms"]), "p50_latency_ms": int(s["p50_ms"]),
                "avg_cost_usd": float(s["avg_cost_usd"]), "provenance_4d": s["provenance_4d"],
                "attached_breakpoints": sum(1 for bp in bps if bp.get("node_id") == str(s["symbol"]) or (bp.get("line_number") is not None and int(bp["line_number"]) == int(s["line_start"]))),
            }
            for s in raw_specs
        ]
        bridge = {
            "protocol_version": "2026-11-15", "extension_id": "keelway.vscode-keelway",
            "loopback_origin_policy": "extension-host-bearer-only", "vscode_attach_uri": vscode_uri, "cursor_attach_uri": cursor_uri,
        }
        return {"workspace_id": ws, "workflow_id": wf, "file_path": clean_file, "vscode_attach_uri": vscode_uri, "cursor_attach_uri": cursor_uri, "bridge": bridge, "lenses": lenses}


step_debugger_engine = SQLiteStepDebuggerEngine()
