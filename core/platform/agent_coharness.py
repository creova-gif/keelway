"""Phase 18A Universal Coding-Agent Co-Harness, Single-Use P-10 Tickets & Worktree CI Gate (`core.platform.agent_coharness`)."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import threading
from typing import Any, Dict, List, Optional, Pattern, Sequence, Tuple, Union
import uuid

from core.platform.flight_tape import _canonical_json, _clean_workspace_id, _sha256_json, _utc_now, scrub_flight_text
from core.platform.kbrain_khub import resolve_kbrain_db_target
from core.platform.hook_plugin_templates import build_opencode_plugin_content

VALID_AGENT_HOSTS: Tuple[str, ...] = ("claude_code", "cursor", "codex_cli", "opencode", "gemini_cli", "hermes_acp")
VALID_HOOK_MODES: Tuple[str, ...] = ("enforce", "audit_only")
VALID_TICKET_STATUSES: Tuple[str, ...] = ("PENDING", "APPROVED", "DENIED", "CONSUMED")
VALID_TICKET_DECISIONS: Tuple[str, ...] = ("APPROVED", "DENIED")
VALID_PROVIDER_TIERS: Tuple[str, ...] = ("local_opencore", "frontier_byom")

_HOOK_TARGET_PATHS: Dict[str, str] = {
    "claude_code": ".claude/settings.local.json",
    "cursor": ".cursor/hooks.json",
    "codex_cli": ".codex/hooks.toml",
    "opencode": ".opencode/plugins/keelway-guard.ts",
}

_DEFAULT_WORKTREE_CANDIDATES: Tuple[Dict[str, Any], ...] = (
    {"candidate_id": "cand-local", "worktree_branch": "wt/opencore-7b", "model_id": "keelway-core:7b", "provider_tier": "local_opencore", "tests_passed": True, "eval_score": 0.92, "cost_usd": 0.0, "diff_excerpt": "+ assert retry_budget <= 3"},
    {"candidate_id": "cand-frontier", "worktree_branch": "wt/sonnet-byom", "model_id": "claude-3-7-sonnet", "provider_tier": "frontier_byom", "tests_passed": True, "eval_score": 0.93, "cost_usd": 0.048, "diff_excerpt": "+ assert retry_budget <= 3"},
)

_EXTRA_DLP_PATTERNS: Tuple[Tuple[Pattern[str], str], ...] = (
    (re.compile(r"(?i)(?:-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----|(?:\bBEGIN [A-Z0-9 ]*PRIVATE KEY\b)|\bPRIVATE KEY\b(?:\s*[:=]\s*\S+)?)"), "[REDACTED_SECRET]"),
    (re.compile(r"\bsk-(?:ant-|proj-|live-|test-)?[A-Za-z0-9_-]{4,}"), "[REDACTED_SECRET]"),
    (re.compile(r"\b(?:AKIA|ASIA)[A-Za-z0-9_-]{6,}"), "[REDACTED_SECRET]"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9_-]{6,}"), "[REDACTED_SECRET]"),
    (re.compile(r"\bBearer\s+(?!\[REDACTED_SECRET\])[A-Za-z0-9._\-~+/]{6,}=*"), "Bearer [REDACTED_SECRET]"),
)

_DESTRUCTIVE_CMD_PATTERNS: Tuple[Pattern[str], ...] = (
    re.compile(r"(?:^|\s|;|&&|\|\|)(?:sudo\s+)?rm\s+(?:-[a-zA-Z]*[rf][a-zA-Z]*\s+)+/(?:\*|\s|$|;|&|\|)"),
    re.compile(r"--no-preserve-root\b"),
    re.compile(r"\bmkfs(?:\.[a-z0-9]+)?\b", re.IGNORECASE),
    re.compile(r"\bdd\s+if=", re.IGNORECASE),
)

_SENSITIVE_CRED_PATTERNS: Tuple[Pattern[str], ...] = (
    re.compile(r"(?:~|/root|/home/[^\s/]+|/Users/[^\s/]+)?/\.ssh/id_[A-Za-z0-9_.-]*"),
    re.compile(r"/etc/(?:shadow|master\.passwd|sudoers)\b"),
    re.compile(r"(?:~|/|\b)\.aws/credentials\b"),
)

_SENSITIVE_MUTATION_PATTERNS: Tuple[Pattern[str], ...] = (
    re.compile(r"\bgit\s+push\b", re.IGNORECASE),
    re.compile(r"\bgit\s+reset\s+--hard\b", re.IGNORECASE),
    re.compile(r"\bdrop\s+table\b", re.IGNORECASE),
    re.compile(r"\bdelete\s+from\b", re.IGNORECASE),
    re.compile(r"\btruncate\b", re.IGNORECASE),
    re.compile(r"\bkubectl\s+(?:apply|delete)\b", re.IGNORECASE),
    re.compile(r"\bterraform\s+(?:apply|destroy)\b", re.IGNORECASE),
    re.compile(r"\bdocker\s+push\b", re.IGNORECASE),
    re.compile(r"\bnpm\s+publish\b", re.IGNORECASE),
    re.compile(r"\bchmod\s+(?:-[A-Za-z]+\s+)*777\b"),
    re.compile(r"\bcurl\b.*(?:-X|--request)\s*(?:POST|DELETE|PUT|PATCH)\b", re.IGNORECASE),
)

_UNSAFE_DIFF_PATTERNS: Tuple[Pattern[str], ...] = (
    re.compile(r"\brm\s+-(?:[a-zA-Z]*r[a-zA-Z]*f|[a-zA-Z]*f[a-zA-Z]*r)[a-zA-Z]*\s+/"),
    re.compile(r"\bdrop\s+table\b", re.IGNORECASE),
)

_COHARNESS_SCHEMA_SQL = (
    "CREATE TABLE IF NOT EXISTS harness_interceptions (interception_id TEXT NOT NULL, workspace_id TEXT NOT NULL, agent_host TEXT NOT NULL, tool_name TEXT NOT NULL, scrubbed_command TEXT NOT NULL, command_sha256 TEXT NOT NULL, verdict TEXT NOT NULL, reason_code TEXT NOT NULL, ticket_id TEXT, dlp_redactions INTEGER NOT NULL DEFAULT 0, payload_json TEXT NOT NULL, event_sha256 TEXT NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY (workspace_id, interception_id)); "
    "CREATE INDEX IF NOT EXISTS idx_harness_interceptions_ws_created ON harness_interceptions(workspace_id, created_at DESC); "
    "CREATE TABLE IF NOT EXISTS harness_approval_tickets (ticket_id TEXT NOT NULL, workspace_id TEXT NOT NULL, agent_host TEXT NOT NULL, tool_name TEXT NOT NULL, scrubbed_command TEXT NOT NULL, command_sha256 TEXT NOT NULL, status TEXT NOT NULL, reviewer TEXT, decision_reason TEXT, payload_json TEXT NOT NULL, ticket_sha256 TEXT NOT NULL, created_at TEXT NOT NULL, decided_at TEXT, consumed_at TEXT, PRIMARY KEY (workspace_id, ticket_id)); "
    "CREATE INDEX IF NOT EXISTS idx_harness_tickets_ws_created ON harness_approval_tickets(workspace_id, created_at DESC); "
    "CREATE TABLE IF NOT EXISTS worktree_ci_gate_runs (gate_run_id TEXT NOT NULL, workspace_id TEXT NOT NULL, workflow_name TEXT NOT NULL, status TEXT NOT NULL, min_eval_score REAL NOT NULL, winner_candidate_id TEXT, winner_model TEXT, cost_saved_usd REAL NOT NULL, dlp_redactions INTEGER NOT NULL DEFAULT 0, payload_json TEXT NOT NULL, gate_sha256 TEXT NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY (workspace_id, gate_run_id)); "
    "CREATE INDEX IF NOT EXISTS idx_worktree_ci_gate_ws_created ON worktree_ci_gate_runs(workspace_id, created_at DESC);"
)


class AgentCoharnessValidationError(ValueError):
    """Raised when co-harness hook parameters, ticket fields, or worktree candidate specs are invalid."""


class ApprovalTicketNotFoundError(KeyError):
    """Raised when a requested P-10 approval ticket_id does not exist in the workspace."""


class ApprovalTicketConflictError(RuntimeError):
    """Raised when attempting to approve or deny a single-use ticket that was already CONSUMED."""


def _validate_ws_and_limit(workspace_id: str, limit: int = 25) -> Tuple[str, int]:
    try:
        ws = _clean_workspace_id(workspace_id)
    except ValueError as exc:
        raise AgentCoharnessValidationError(str(exc)) from exc
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise AgentCoharnessValidationError("limit must be a positive integer.")
    return ws, min(limit, 200)


def _validate_enum(val: Any, allowed: Tuple[str, ...], field_name: str) -> str:
    clean = str(val or "").strip()
    if clean not in allowed:
        raise AgentCoharnessValidationError(f"Unsupported {field_name} '{val}'. Expected {list(allowed)}.")
    return clean


def _scrub_coharness_text(text: str) -> Tuple[str, int]:
    current, total = scrub_flight_text(str(text or ""))
    if not current:
        return "", 0
    for pattern, replacement in _EXTRA_DLP_PATTERNS:
        current, count = pattern.subn(replacement, current)
        total += count
    return current, total


def _build_hook_config_content(ws: str, host: str, mode: str) -> str:
    if host == "opencode":
        return build_opencode_plugin_content(ws, mode)
    adapter_hosts = ("claude_code", "codex_cli", "cursor")
    if host in adapter_hosts:
        # Adapter hosts consume native hook JSON on stdin via `harness agents intercept`/`event`.
        # Cursor accepts the nested Claude-style permissionDecision response.
        out_format = "json" if host == "codex_cli" else "claude-code"
        pre_cmd = (f"keelway harness agents intercept --agent {host} --payload - "
                   f"--mode {mode} --workspace {ws} --format {out_format}")
        post_cmd = (f"keelway harness agents event --agent {host} --event posttooluse "
                    f"--payload - --workspace {ws}")
        sess_cmd = (f"keelway harness agents event --agent {host} --event sessionstart "
                    f"--payload - --workspace {ws}")
        end_cmd = (f"keelway harness agents event --agent {host} --event sessionend "
                   f"--payload - --workspace {ws}")
    else:
        pre_cmd = f"keelway harness intercept --agent {host} --workspace {ws}"
        post_cmd = sess_cmd = ""
    if host == "claude_code":
        return json.dumps({"hooks": {
            "PreToolUse": [{"matcher": "Bash|Edit|Write|MultiEdit", "mode": mode, "hooks": [{"type": "command", "command": pre_cmd}]}],
            "PostToolUse": [{"matcher": "Bash|Edit|Write|MultiEdit", "hooks": [{"type": "command", "command": post_cmd}]}],
            "SessionStart": [{"hooks": [{"type": "command", "command": sess_cmd}]}],
        }}, indent=2)
    if host == "cursor":
        # Real Cursor hooks.json schema (cursor.com/docs/hooks): lowercase event
        # names under "hooks", command strings, optional tool_name matcher.
        # Payload carries Cursor tool names (Shell/Read/Write/Grep/...); the
        # co-harness classifies on the command string, so matcher is advisory.
        return json.dumps({"version": 1, "hooks": {
            "preToolUse": [{"command": pre_cmd,
                            "matcher": "Shell|Write|Edit|MultiEdit|Delete|Move|NotebookEdit"}],
            "postToolUse": [{"command": post_cmd}],
            "sessionStart": [{"command": sess_cmd}],
            "sessionEnd": [{"command": end_cmd}],
        }}, indent=2)
    if host == "codex_cli":
        return (f'[hooks.PreToolUse]\nevent = "PreToolUse"\nmode = "{mode}"\nworkspace_id = "{ws}"\ncommand = "{pre_cmd}"\n'
                f'[hooks.PostToolUse]\nevent = "PostToolUse"\nworkspace_id = "{ws}"\ncommand = "{post_cmd}"\n'
                f'[hooks.SessionStart]\nevent = "SessionStart"\nworkspace_id = "{ws}"\ncommand = "{sess_cmd}"\n')
    return f'[hooks.PreToolUse]\nevent = "PreToolUse"\nmode = "{mode}"\nworkspace_id = "{ws}"\ncommand = "{pre_cmd}"\n'


def _normalize_candidates(raw_candidates: Optional[Sequence[Any]]) -> Tuple[List[Dict[str, Any]], int, bool]:
    source = list(raw_candidates) if raw_candidates else [dict(c) for c in _DEFAULT_WORKTREE_CANDIDATES]
    normalized, seen_ids, redactions, unsafe_diff = [], set(), 0, False
    for raw in source:
        item = raw.model_dump() if hasattr(raw, "model_dump") else (dict(raw) if isinstance(raw, dict) else None)
        if not isinstance(item, dict):
            raise AgentCoharnessValidationError("Each worktree candidate must be an object.")
        cid_raw, branch_raw, model_raw = str(item.get("candidate_id") or "").strip(), str(item.get("worktree_branch") or "").strip(), str(item.get("model_id") or "").strip()
        if not cid_raw or not branch_raw or not model_raw:
            raise AgentCoharnessValidationError("Each candidate requires candidate_id, worktree_branch, and model_id.")
        tier = _validate_enum(item.get("provider_tier"), VALID_PROVIDER_TIERS, "provider_tier")
        raw_score, raw_cost = item.get("eval_score"), item.get("cost_usd", 0.0)
        if isinstance(raw_score, bool) or not isinstance(raw_score, (int, float)) or not (0.0 <= float(raw_score) <= 1.0):
            raise AgentCoharnessValidationError(f"eval_score on '{cid_raw}' must be between 0.0 and 1.0.")
        if isinstance(raw_cost, bool) or not isinstance(raw_cost, (int, float)) or float(raw_cost) < 0.0:
            raise AgentCoharnessValidationError(f"cost_usd on '{cid_raw}' must be >= 0.0.")

        excerpt_raw = str(item.get("diff_excerpt") or "")
        if any(p.search(excerpt_raw) for p in _UNSAFE_DIFF_PATTERNS):
            unsafe_diff = True
        cid, r1 = _scrub_coharness_text(cid_raw)
        if cid in seen_ids:
            raise AgentCoharnessValidationError(f"Duplicate candidate_id '{cid}' in worktree arena.")
        seen_ids.add(cid)
        branch, r2 = _scrub_coharness_text(branch_raw)
        model_id, r3 = _scrub_coharness_text(model_raw)
        excerpt, r4 = _scrub_coharness_text(excerpt_raw)
        redactions += r1 + r2 + r3 + r4
        normalized.append({"candidate_id": cid, "worktree_branch": branch, "model_id": model_id, "provider_tier": tier, "tests_passed": bool(item.get("tests_passed", False)), "eval_score": round(float(raw_score), 6), "cost_usd": round(float(raw_cost), 6), "diff_excerpt": excerpt})
    return normalized, redactions, unsafe_diff


class SQLiteAgentCoharnessEngine:
    """Thread-safe SQLite WAL engine for PreToolUse Agent Co-Harness, Single-Use P-10 Tickets & Worktree CI Gate."""

    def __init__(self, db_path: Optional[Union[str, Path]] = None) -> None:
        self._lock, self._explicit_db_path = threading.RLock(), db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._active_target: Optional[str] = None
        self._db_path: Union[str, Path] = ":memory:"
        self._closed = False
        with self._lock:
            self._ensure_conn()

    def _ensure_conn(self) -> sqlite3.Connection:
        eff_override = self._explicit_db_path if self._explicit_db_path is not None else (os.environ.get("KEELWAY_PLATFORM_DB_PATH", "").strip() or None)
        resolved_path, connect_target = resolve_kbrain_db_target(eff_override)
        if self._conn is not None and not self._closed and self._active_target == connect_target:
            return self._conn
        if self._conn is not None and not self._closed:
            self._conn.close()
        conn = sqlite3.connect(connect_target, check_same_thread=False, timeout=30.0)
        conn.row_factory = sqlite3.Row
        for pragma in ("PRAGMA journal_mode=WAL", "PRAGMA synchronous=NORMAL", "PRAGMA foreign_keys=ON"):
            conn.execute(pragma)
        with conn:
            conn.executescript(_COHARNESS_SCHEMA_SQL)
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

    def render_hook_manifest(self, workspace_id: str = "default", agent_host: str = "claude_code", mode: str = "enforce") -> Dict[str, Any]:
        ws, _ = _validate_ws_and_limit(workspace_id)
        host = _validate_enum(agent_host, VALID_AGENT_HOSTS, "agent_host")
        clean_mode = _validate_enum(mode, VALID_HOOK_MODES, "mode")
        if host not in _HOOK_TARGET_PATHS:
            raise AgentCoharnessValidationError(
                f"agent_host '{host}' has no hook manifest — ACP-governed agents "
                "are intercepted via `keelway harness agents acp` permission bridge.")
        target_path = _HOOK_TARGET_PATHS[host]
        content = _build_hook_config_content(ws, host, clean_mode)
        config_sha = "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest()
        return {"workspace_id": ws, "agent_host": host, "mode": clean_mode, "target_config_path": target_path, "hook_event": "PreToolUse", "config_content": content, "cli_install_hint": f"keelway harness hooks --agent {host} --mode {clean_mode} --workspace {ws} --install-dir .", "config_sha256": config_sha}

    def intercept_tool_call(
        self,
        workspace_id: str = "default",
        agent_host: str = "claude_code",
        tool_name: str = "Bash",
        command: str = "git push origin main",
        ticket_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        ws, _ = _validate_ws_and_limit(workspace_id)
        host = _validate_enum(agent_host, VALID_AGENT_HOSTS, "agent_host")
        raw_tool = str(tool_name or "Bash").strip() or "Bash"
        raw_cmd = str(command if command is not None else "git push origin main").strip()
        if not raw_cmd:
            raise AgentCoharnessValidationError("command must be non-empty.")

        command_sha256 = "sha256:" + hashlib.sha256(f"{raw_tool}:{raw_cmd}".encode("utf-8")).hexdigest()
        scrubbed_tool, r_tool = _scrub_coharness_text(raw_tool)
        scrubbed_command, r_cmd = _scrub_coharness_text(raw_cmd)
        dlp_redactions = r_tool + r_cmd
        clean_tid = str(ticket_id).strip() if ticket_id is not None and str(ticket_id).strip() else None
        now_iso = _utc_now()

        with self._lock:
            conn = self._ensure_conn()
            with conn:
                verdict, reason_code, explanation, out_tid = self._classify_and_bind_ticket(conn, ws, host, scrubbed_tool, raw_cmd, scrubbed_command, command_sha256, dlp_redactions, clean_tid, now_iso)
                interception_id = f"hint-{uuid.uuid4().hex[:12]}"
                event_sha = _sha256_json({"interception_id": interception_id, "workspace_id": ws, "agent_host": host, "tool_name": scrubbed_tool, "scrubbed_command": scrubbed_command, "command_sha256": command_sha256, "verdict": verdict, "reason_code": reason_code, "ticket_id": out_tid, "dlp_redactions": dlp_redactions, "created_at": now_iso})
                record = {"interception_id": interception_id, "workspace_id": ws, "agent_host": host, "tool_name": scrubbed_tool, "scrubbed_command": scrubbed_command, "command_sha256": command_sha256, "verdict": verdict, "reason_code": reason_code, "explanation": explanation, "ticket_id": out_tid, "dlp_redactions": dlp_redactions, "event_sha256": event_sha, "created_at": now_iso}
                conn.execute("INSERT INTO harness_interceptions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (interception_id, ws, host, scrubbed_tool, scrubbed_command, command_sha256, verdict, reason_code, out_tid, dlp_redactions, _canonical_json(record), event_sha, now_iso))
        return record

    def _classify_and_bind_ticket(
        self,
        conn: sqlite3.Connection,
        ws: str,
        host: str,
        scrubbed_tool: str,
        raw_cmd: str,
        scrubbed_command: str,
        command_sha256: str,
        dlp_redactions: int,
        clean_tid: Optional[str],
        now_iso: str,
    ) -> Tuple[str, str, str, Optional[str]]:
        if dlp_redactions > 0:
            return ("DENY", "dlp_secret_detected", "Inline secret detected and redacted before storage; execution blocked.", clean_tid)
        if any(p.search(raw_cmd) for p in _DESTRUCTIVE_CMD_PATTERNS):
            return ("DENY", "destructive_system_command", "Destructive root or block-device wipe command is permanently blocked.", clean_tid)
        if any(p.search(raw_cmd) for p in _SENSITIVE_CRED_PATTERNS):
            return ("DENY", "sensitive_credential_read", "Direct read or exfiltration of host SSH or OS/cloud credential files is blocked.", clean_tid)

        if clean_tid is not None:
            row = conn.execute("SELECT payload_json FROM harness_approval_tickets WHERE workspace_id=? AND ticket_id=?", (ws, clean_tid)).fetchone()
            if row is None:
                return ("DENY", "ticket_not_found", f"Approval ticket '{clean_tid}' was not found in workspace '{ws}'.", clean_tid)
            tkt = json.loads(str(row["payload_json"]))
            if tkt["command_sha256"] != command_sha256:
                return ("DENY", "ticket_command_mismatch", "Command SHA-256 does not match the approved single-use P-10 ticket.", clean_tid)
            t_status = str(tkt["status"])
            if t_status == "CONSUMED":
                return ("DENY", "ticket_already_consumed", f"Single-use P-10 ticket '{clean_tid}' was already consumed.", clean_tid)
            if t_status == "DENIED":
                return ("DENY", "ticket_denied", f"P-10 ticket '{clean_tid}' was denied by reviewer.", clean_tid)
            if t_status == "PENDING":
                return ("HOLD_TICKET", "ticket_still_pending", f"P-10 ticket '{clean_tid}' is still awaiting approval.", clean_tid)

            tkt["status"], tkt["consumed_at"] = "CONSUMED", now_iso
            tkt["ticket_sha256"] = _sha256_json({k: v for k, v in tkt.items() if k != "ticket_sha256"})
            conn.execute("UPDATE harness_approval_tickets SET status=?, consumed_at=?, payload_json=?, ticket_sha256=? WHERE workspace_id=? AND ticket_id=? AND status='APPROVED'", ("CONSUMED", now_iso, _canonical_json(tkt), tkt["ticket_sha256"], ws, clean_tid))
            return ("ALLOW_WITH_TICKET", "approved_single_use_ticket_consumed", f"Single-use P-10 ticket '{clean_tid}' verified and consumed.", clean_tid)

        if any(p.search(raw_cmd) for p in _SENSITIVE_MUTATION_PATTERNS):
            new_tid = f"ptkt-{uuid.uuid4().hex[:12]}"
            base_tkt = {"ticket_id": new_tid, "workspace_id": ws, "agent_host": host, "tool_name": scrubbed_tool, "scrubbed_command": scrubbed_command, "command_sha256": command_sha256, "status": "PENDING", "reviewer": None, "decision_reason": None, "created_at": now_iso, "decided_at": None, "consumed_at": None}
            t_sha = _sha256_json(base_tkt)
            tkt_record = {**base_tkt, "ticket_sha256": t_sha}
            conn.execute("INSERT INTO harness_approval_tickets VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (new_tid, ws, host, scrubbed_tool, scrubbed_command, command_sha256, "PENDING", None, None, _canonical_json(tkt_record), t_sha, now_iso, None, None))
            return ("HOLD_TICKET", "p10_ticket_required", f"Sensitive mutation held pending single-use P-10 approval ({new_tid}).", new_tid)

        return ("ALLOW", "safe_readonly_or_test", "Safe inspection or test command permitted without P-10 hold.", None)

    def list_tickets(self, workspace_id: str = "default", status: Optional[str] = None, limit: int = 25) -> Dict[str, Any]:
        ws, cap = _validate_ws_and_limit(workspace_id, limit)
        clean_status = _validate_enum(str(status).strip().upper(), VALID_TICKET_STATUSES, "status") if status is not None and str(status).strip() else None
        with self._lock:
            conn = self._ensure_conn()
            if clean_status:
                rows = conn.execute("SELECT payload_json FROM harness_approval_tickets WHERE workspace_id=? AND status=? ORDER BY created_at DESC, rowid DESC LIMIT ?", (ws, clean_status, cap)).fetchall()
            else:
                rows = conn.execute("SELECT payload_json FROM harness_approval_tickets WHERE workspace_id=? ORDER BY created_at DESC, rowid DESC LIMIT ?", (ws, cap)).fetchall()
        items = [json.loads(str(r["payload_json"])) for r in rows]
        return {"workspace_id": ws, "count": len(items), "tickets": items}

    def decide_ticket(
        self,
        workspace_id: str = "default",
        ticket_id: str = "",
        decision: str = "APPROVED",
        reviewer: str = "lead-engineer",
        reason: str = "Verified safe workspace scope",
    ) -> Dict[str, Any]:
        ws, _ = _validate_ws_and_limit(workspace_id)
        clean_tid = str(ticket_id or "").strip()
        if not clean_tid:
            raise ApprovalTicketNotFoundError("Approval ticket '' not found.")
        clean_dec = _validate_enum(str(decision or "").strip().upper(), VALID_TICKET_DECISIONS, "decision")
        clean_rev, _ = _scrub_coharness_text(str(reviewer or "lead-engineer").strip() or "lead-engineer")
        clean_rsn, _ = _scrub_coharness_text(str(reason or "Verified safe workspace scope").strip() or "Verified safe workspace scope")

        with self._lock:
            conn = self._ensure_conn()
            with conn:
                row = conn.execute("SELECT payload_json FROM harness_approval_tickets WHERE workspace_id=? AND ticket_id=?", (ws, clean_tid)).fetchone()
                if row is None:
                    raise ApprovalTicketNotFoundError(f"Approval ticket '{clean_tid}' not found in workspace '{ws}'.")
                tkt = json.loads(str(row["payload_json"]))
                if tkt["status"] == "CONSUMED":
                    raise ApprovalTicketConflictError(f"Single-use ticket '{clean_tid}' is already CONSUMED and cannot be re-decided.")
                decided_at = _utc_now()
                tkt["status"], tkt["reviewer"], tkt["decision_reason"], tkt["decided_at"] = clean_dec, clean_rev, clean_rsn, decided_at
                tkt["ticket_sha256"] = _sha256_json({k: v for k, v in tkt.items() if k != "ticket_sha256"})
                conn.execute("UPDATE harness_approval_tickets SET status=?, reviewer=?, decision_reason=?, decided_at=?, payload_json=?, ticket_sha256=? WHERE workspace_id=? AND ticket_id=?", (clean_dec, clean_rev, clean_rsn, decided_at, _canonical_json(tkt), tkt["ticket_sha256"], ws, clean_tid))
        return tkt

    def evaluate_worktree_ci_gate(
        self,
        workspace_id: str = "default",
        workflow_name: str = "pr-worktree-arena",
        diff_summary: str = "Refactor retry backoff & add unit test in core/platform/",
        min_eval_score: float = 0.85,
        candidates: Optional[Sequence[Any]] = None,
    ) -> Dict[str, Any]:
        ws, _ = _validate_ws_and_limit(workspace_id)
        if isinstance(min_eval_score, bool) or not isinstance(min_eval_score, (int, float)) or not (0.0 <= float(min_eval_score) <= 1.0):
            raise AgentCoharnessValidationError("min_eval_score must be between 0.0 and 1.0.")
        min_score = round(float(min_eval_score), 6)
        raw_sum = str(diff_summary or "Refactor retry backoff & add unit test in core/platform/").strip() or "Refactor retry backoff & add unit test in core/platform/"
        unsafe_sum = any(p.search(raw_sum) for p in _UNSAFE_DIFF_PATTERNS)
        clean_wf, r_wf = _scrub_coharness_text(str(workflow_name or "pr-worktree-arena").strip() or "pr-worktree-arena")
        clean_sum, r_sum = _scrub_coharness_text(raw_sum)
        norm_cands, r_cands, unsafe_cand = _normalize_candidates(candidates)
        total_redactions = r_wf + r_sum + r_cands

        winner_id, winner_model, cost_saved = None, None, 0.0
        if total_redactions > 0 or unsafe_sum or unsafe_cand:
            status = "FAIL_SAFETY"
        else:
            passing = [c for c in norm_cands if c["tests_passed"] is True and c["eval_score"] >= min_score]
            if not passing:
                status = "FAIL_REGRESSION"
            else:
                status = "PASS"
                top_score = max(c["eval_score"] for c in passing)
                local_viable = [c for c in passing if c["provider_tier"] == "local_opencore" and round(top_score - c["eval_score"], 9) <= 0.03]
                winner = max(local_viable or passing, key=lambda c: (c["eval_score"], -c["cost_usd"]))
                winner_id, winner_model = str(winner["candidate_id"]), str(winner["model_id"])
                cost_saved = round(max(c["cost_usd"] for c in norm_cands) - float(winner["cost_usd"]), 6)

        gate_run_id, created_at = f"cigate-{uuid.uuid4().hex[:12]}", _utc_now()
        gate_sha = _sha256_json({"gate_run_id": gate_run_id, "workspace_id": ws, "workflow_name": clean_wf, "diff_summary": clean_sum, "status": status, "min_eval_score": min_score, "winner_candidate_id": winner_id, "winner_model": winner_model, "cost_saved_usd": cost_saved, "dlp_redactions": total_redactions, "candidates": norm_cands})
        record = {"gate_run_id": gate_run_id, "workspace_id": ws, "workflow_name": clean_wf, "diff_summary": clean_sum, "status": status, "min_eval_score": min_score, "winner_candidate_id": winner_id, "winner_model": winner_model, "cost_saved_usd": cost_saved, "dlp_redactions": total_redactions, "candidates": norm_cands, "gate_sha256": gate_sha, "created_at": created_at}
        with self._lock:
            conn = self._ensure_conn()
            with conn:
                conn.execute("INSERT INTO worktree_ci_gate_runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (gate_run_id, ws, clean_wf, status, min_score, winner_id, winner_model, cost_saved, total_redactions, _canonical_json(record), gate_sha, created_at))
        return record

    def list_worktree_ci_gate_runs(self, workspace_id: str = "default", limit: int = 25) -> Dict[str, Any]:
        ws, cap = _validate_ws_and_limit(workspace_id, limit)
        with self._lock:
            rows = self._ensure_conn().execute("SELECT payload_json FROM worktree_ci_gate_runs WHERE workspace_id=? ORDER BY created_at DESC, rowid DESC LIMIT ?", (ws, cap)).fetchall()
        runs = [json.loads(str(r["payload_json"])) for r in rows]
        return {"workspace_id": ws, "count": len(runs), "runs": runs}


agent_coharness_engine = SQLiteAgentCoharnessEngine()
