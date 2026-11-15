"""
Phase 11A OTel GenAI Flight-Tape Engine, Deterministic Time-Travel Replay & Eval Promotion (`core.platform.flight_tape`).

Persists OpenTelemetry GenAI / LangGraph / flat agent execution traces (`platform_flight_tapes`,
`platform_flight_steps`) and 1-click promoted golden evaluation dataset cases (`platform_eval_dataset_cases`)
in SQLite WAL (`platform_runtime.db`) with non-blocking pre-storage DLP secret redaction.
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

from core.platform.kbrain_khub import resolve_kbrain_db_target

_WORKSPACE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_TRACE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_WORD_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{3,}")
_SENSITIVE_DICT_KEYS = frozenset(
    {"password", "passwd", "api_key", "apikey", "secret", "client_secret", "access_token", "auth_token", "private_key"}
)
_LOCAL_MODEL_PREFIXES: Tuple[str, ...] = ("keelway-core", "qwen", "llama", "mistral", "deepseek", "ollama")
_DLP_SCRUB_PATTERNS: Tuple[Tuple[Pattern[str], str], ...] = (
    (re.compile(r"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----(?:[\s\S]*?-----END (?:[A-Z0-9 ]+ )?PRIVATE KEY-----|[^\r\n]*)"), "[REDACTED_SECRET]"),
    (re.compile(r"(?i)(?:postgres|postgresql|mysql|mongodb|redis)://[^:\s/]+:[^@\s/]+@"), "[REDACTED_SECRET]@"),
    (re.compile(r"\bsk-(?:ant-|proj-|live-|test-)?[A-Za-z0-9_-]{10,}"), "[REDACTED_SECRET]"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{12,}"), "[REDACTED_SECRET]"),
    (re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"), "[REDACTED_SECRET]"),
    (re.compile(r"\bBearer\s+(?!\[REDACTED_SECRET\])[A-Za-z0-9._\-~+/]{12,}=*"), "Bearer [REDACTED_SECRET]"),
    (re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}"), "[REDACTED_SECRET]"),
    (
        re.compile(
            r"(?i)\b(password|passwd|api[_-]?key|apikey|secret|client[_-]?secret|access[_-]?token|auth[_-]?token)"
            r"\s*([:=])\s*(['\"]?)(?!\[REDACTED_SECRET\])[^\s'\",;}{)(\]\[]{6,}\3"
        ),
        r"\1\2[REDACTED_SECRET]",
    ),
)

_FLIGHT_TAPE_SCHEMA_SQL = (
    "CREATE TABLE IF NOT EXISTS platform_flight_tapes ("
    "trace_id TEXT NOT NULL, workspace_id TEXT NOT NULL, workflow_name TEXT NOT NULL, "
    "source_framework TEXT NOT NULL, parent_trace_id TEXT, forked_from_step INTEGER, "
    "status TEXT NOT NULL, total_steps INTEGER NOT NULL, cached_steps_reused INTEGER NOT NULL DEFAULT 0, "
    "total_tokens INTEGER NOT NULL, total_cost_usd REAL NOT NULL, cost_delta_usd REAL NOT NULL DEFAULT 0.0, "
    "dlp_redactions INTEGER NOT NULL DEFAULT 0, tape_sha256 TEXT NOT NULL, created_at TEXT NOT NULL, "
    "PRIMARY KEY (workspace_id, trace_id)); "
    "CREATE INDEX IF NOT EXISTS idx_platform_flight_tapes_ws_created ON platform_flight_tapes(workspace_id, created_at DESC); "
    "CREATE TABLE IF NOT EXISTS platform_flight_steps ("
    "id INTEGER PRIMARY KEY AUTOINCREMENT, workspace_id TEXT NOT NULL, trace_id TEXT NOT NULL, "
    "step_index INTEGER NOT NULL, node_name TEXT NOT NULL, span_kind TEXT NOT NULL, "
    "model_id TEXT NOT NULL, prompt_text TEXT NOT NULL, output_text TEXT NOT NULL, "
    "state_json TEXT NOT NULL, input_tokens INTEGER NOT NULL, output_tokens INTEGER NOT NULL, "
    "cost_usd REAL NOT NULL, cached_reuse INTEGER NOT NULL DEFAULT 0, step_sha256 TEXT NOT NULL); "
    "CREATE INDEX IF NOT EXISTS idx_platform_flight_steps_lookup ON platform_flight_steps(workspace_id, trace_id, step_index ASC); "
    "CREATE TABLE IF NOT EXISTS platform_eval_dataset_cases ("
    "case_id TEXT NOT NULL, workspace_id TEXT NOT NULL, source_trace_id TEXT NOT NULL, "
    "title TEXT NOT NULL, input_prompt TEXT NOT NULL, expected_substrings_json TEXT NOT NULL, "
    "forbidden_substrings_json TEXT NOT NULL, pinned_tool_mocks_json TEXT NOT NULL, "
    "case_sha256 TEXT NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL, "
    "PRIMARY KEY (workspace_id, case_id)); "
    "CREATE INDEX IF NOT EXISTS idx_platform_eval_cases_ws_created ON platform_eval_dataset_cases(workspace_id, created_at DESC);"
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256_json(obj: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical_json(obj).encode("utf-8")).hexdigest()


def _clean_workspace_id(workspace_id: str) -> str:
    clean = str(workspace_id or "").strip()
    if not clean or not _WORKSPACE_ID_RE.fullmatch(clean):
        raise ValueError(f"Invalid workspace_id '{workspace_id}'.")
    return clean


def _clean_trace_id(trace_id: Optional[str], *, allow_generate: bool = False) -> str:
    raw = str(trace_id or "").strip()
    if not raw and allow_generate:
        return f"trace-{uuid.uuid4().hex[:12]}"
    if not raw or not _TRACE_ID_RE.fullmatch(raw):
        raise ValueError(f"Invalid trace_id '{trace_id}'.")
    return raw


def _first_present(sources: Sequence[Tuple[Dict[str, Any], str]], default: Any = None) -> Any:
    for mapping, key in sources:
        if mapping.get(key) is not None:
            return mapping[key]
    return default


def scrub_flight_text(text: str) -> Tuple[str, int]:
    """Scrub secret patterns into `[REDACTED_SECRET]` and return `(scrubbed_text, redaction_count)`."""
    current = str(text or "")
    if not current:
        return "", 0
    total = 0
    for pattern, replacement in _DLP_SCRUB_PATTERNS:
        current, count = pattern.subn(replacement, current)
        total += count
    return current, total


def _scrub_obj(value: Any) -> Tuple[Any, int]:
    if isinstance(value, str):
        return scrub_flight_text(value)
    if isinstance(value, dict):
        out_dict: Dict[str, Any] = {}
        count = 0
        for raw_k, raw_v in value.items():
            clean_k, k_cnt = scrub_flight_text(str(raw_k))
            count += k_cnt
            if clean_k.strip().lower() in _SENSITIVE_DICT_KEYS and isinstance(raw_v, str) and raw_v.strip():
                v_scrubbed, v_cnt = scrub_flight_text(raw_v)
                out_dict[clean_k] = "[REDACTED_SECRET]" if (v_cnt == 0 and v_scrubbed != "[REDACTED_SECRET]") else v_scrubbed
                count += 1 if (v_cnt == 0 and v_scrubbed != "[REDACTED_SECRET]") else v_cnt
            else:
                v_clean, v_cnt = _scrub_obj(raw_v)
                out_dict[clean_k], count = v_clean, count + v_cnt
        return out_dict, count
    if isinstance(value, (list, tuple)):
        out_list: List[Any] = []
        count = 0
        for item in value:
            c_item, c_cnt = _scrub_obj(item)
            out_list.append(c_item)
            count += c_cnt
        return out_list, count
    return value, 0


def scrub_flight_state(raw_state: Any) -> Tuple[Dict[str, Any], str, int]:
    """Normalize and scrub step state dictionary, returning `(state_dict, canonical_state_json, redactions)`."""
    if raw_state is None:
        base: Dict[str, Any] = {}
    elif isinstance(raw_state, dict):
        base = dict(raw_state)
    elif isinstance(raw_state, str):
        stripped = raw_state.strip()
        try:
            parsed = json.loads(stripped) if stripped else {}
            base = parsed if isinstance(parsed, dict) else {"value": parsed}
        except json.JSONDecodeError:
            base = {"raw_state": stripped}
    else:
        base = {"value": raw_state}
    scrubbed_dict, count = _scrub_obj(base)
    return scrubbed_dict, _canonical_json(scrubbed_dict), count


def _is_local_open_weight_model(model_id: str) -> bool:
    norm = str(model_id or "").strip().lower()
    if "/" in norm:
        prefix, rest = norm.split("/", 1)
        if prefix in ("ollama", "local", "vllm", "lmstudio", "opencore"):
            return True
        norm = rest
    return norm.startswith(_LOCAL_MODEL_PREFIXES)


def _estimate_cost_usd(model_id: str, input_tokens: int, output_tokens: int, span_kind: str) -> float:
    norm_model = str(model_id or "").strip().lower()
    if (span_kind == "tool" and norm_model in ("", "tool", "tool-runtime", "none")) or _is_local_open_weight_model(norm_model):
        return 0.0
    return round((max(0, input_tokens) * 0.0025 + max(0, output_tokens) * 0.01) / 1000.0, 6)


def _decode_otlp_any_value(val_obj: Any) -> Any:
    if not isinstance(val_obj, dict):
        return val_obj
    for k in ("stringValue", "string_value", "boolValue", "bool_value"):
        if k in val_obj:
            return val_obj[k]
    for k, caster in (("intValue", int), ("int_value", int), ("doubleValue", float), ("double_value", float)):
        if k in val_obj:
            try:
                return caster(val_obj[k])
            except (TypeError, ValueError):
                return val_obj[k]
    if isinstance(val_obj.get("arrayValue"), dict):
        vals = val_obj["arrayValue"].get("values", [])
        return [_decode_otlp_any_value(v) for v in vals] if isinstance(vals, list) else []
    if isinstance(val_obj.get("kvlistValue"), dict):
        vals = val_obj["kvlistValue"].get("values", [])
        return _decode_otlp_attributes(vals) if isinstance(vals, list) else {}
    return val_obj


def _decode_otlp_attributes(raw_attrs: Any) -> Dict[str, Any]:
    if isinstance(raw_attrs, dict):
        return {str(k): _decode_otlp_any_value(v) for k, v in raw_attrs.items()}
    if isinstance(raw_attrs, list):
        return {str(e["key"]): _decode_otlp_any_value(e.get("value")) for e in raw_attrs if isinstance(e, dict) and "key" in e}
    return {}


def _extract_otlp_spans(resource_spans: Sequence[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Optional[str], Optional[str]]:
    flat: List[Dict[str, Any]] = []
    detected_service, detected_trace_id = None, None
    for rs in resource_spans:
        if not isinstance(rs, dict):
            continue
        res_obj = rs.get("resource")
        res_attrs = _decode_otlp_attributes(res_obj.get("attributes") if isinstance(res_obj, dict) else None)
        if not detected_service and res_attrs.get("service.name"):
            detected_service = str(res_attrs["service.name"]).strip()
        scope_list = rs.get("scopeSpans") or rs.get("scope_spans") or rs.get("instrumentationLibrarySpans") or []
        for scope_entry in scope_list if isinstance(scope_list, list) else []:
            spans_arr = scope_entry.get("spans", []) if isinstance(scope_entry, dict) else []
            for sp in spans_arr if isinstance(spans_arr, list) else []:
                if isinstance(sp, dict):
                    cand_tid = str(sp.get("traceId") or sp.get("trace_id") or "").strip()
                    if not detected_trace_id and cand_tid and _TRACE_ID_RE.fullmatch(cand_tid):
                        detected_trace_id = cand_tid
                    flat.append(sp)
    return flat, detected_service, detected_trace_id


def _make_step_dict(
    idx: int, node_name: str, span_kind: str, model_id: str, prompt_text: str,
    output_text: str, state_dict: Dict[str, Any], state_json: str, in_tok: int, out_tok: int, cost_usd: float,
) -> Dict[str, Any]:
    step_sha = _sha256_json(
        {"model_id": model_id, "node_name": node_name, "output_text": output_text, "prompt_text": prompt_text, "span_kind": span_kind, "state_json": state_json, "step_index": idx}
    )
    return {
        "step_index": idx, "node_name": node_name, "span_kind": span_kind, "model_id": model_id,
        "prompt_text": prompt_text, "prompt": prompt_text, "output_text": output_text, "output": output_text,
        "state": state_dict, "state_json": state_json, "input_tokens": in_tok, "output_tokens": out_tok,
        "cost_usd": cost_usd, "cached_reuse": False, "step_sha256": step_sha,
    }


def _make_tape_meta(
    tid: str, ws: str, wf: str, fw: str, parent_tid: Optional[str], forked_step: Optional[int], status: str,
    steps: Sequence[Dict[str, Any]], cached_reused: int, total_tok: int, tok_delta: int, total_cost: float, cost_delta: float, redactions: int,
) -> Dict[str, Any]:
    tape_sha = _sha256_json(
        {"forked_from_step": forked_step, "parent_trace_id": parent_tid, "step_hashes": [s["step_sha256"] for s in steps], "trace_id": tid, "workflow_name": wf, "workspace_id": ws}
    )
    return {
        "trace_id": tid, "workspace_id": ws, "workflow_name": wf, "source_framework": fw, "parent_trace_id": parent_tid,
        "forked_from_step": forked_step, "status": status, "total_steps": len(steps), "cached_steps_reused": cached_reused,
        "total_tokens": total_tok, "tokens_delta": tok_delta, "total_cost_usd": total_cost, "cost_delta_usd": cost_delta,
        "dlp_redactions": redactions, "tape_sha256": tape_sha, "created_at": _utc_now(),
    }


class SQLiteFlightTapeEngine:
    """Dynamic SQLite WAL Flight-Tape OTel trace store, deterministic time-travel replayer, and eval promoter."""

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
        resolved_path, connect_target = resolve_kbrain_db_target(self._explicit_db_path)
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
            conn.executescript(_FLIGHT_TAPE_SCHEMA_SQL)
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

    def _normalize_span(self, idx: int, raw_span: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
        if not isinstance(raw_span, dict):
            raise ValueError(f"Span at index {idx} must be a JSON object.")
        attrs = _decode_otlp_attributes(raw_span.get("attributes"))
        for ev in raw_span.get("events") if isinstance(raw_span.get("events"), list) else []:
            if isinstance(ev, dict):
                for k, v in _decode_otlp_attributes(ev.get("attributes")).items():
                    attrs.setdefault(k, v)

        explicit_kind = str(raw_span.get("span_kind") or attrs.get("keelway.span.kind") or attrs.get("openinference.span.kind") or "").strip().lower()
        op_name = str(attrs.get("gen_ai.operation.name") or "").strip().lower()
        if explicit_kind in ("tool", "llm", "agent", "chain", "retriever", "human_gate"):
            span_kind = explicit_kind
        elif "tool" in explicit_kind or "tool.name" in attrs or "tool_name" in raw_span or "tool" in op_name:
            span_kind = "tool"
        elif any(k in attrs for k in ("gen_ai.request.model", "gen_ai.prompt")) or any(k in raw_span for k in ("model_id", "model")):
            span_kind = "llm"
        else:
            span_kind = "agent"

        raw_node = raw_span.get("node_name") or attrs.get("langgraph.node") or attrs.get("tool.name") or raw_span.get("tool_name") or raw_span.get("name") or f"step-{idx}"
        raw_model = raw_span.get("model_id") or raw_span.get("model") or attrs.get("gen_ai.request.model") or attrs.get("gen_ai.response.model") or attrs.get("llm.model_name") or ("tool" if span_kind == "tool" else "gpt-4o")
        raw_prompt = _first_present([(raw_span, "prompt_text"), (raw_span, "prompt"), (raw_span, "input"), (attrs, "gen_ai.prompt"), (attrs, "input.value"), (attrs, "tool.arguments")], "")
        raw_output = _first_present([(raw_span, "output_text"), (raw_span, "output"), (raw_span, "completion"), (attrs, "gen_ai.completion"), (attrs, "output.value"), (attrs, "tool.output")], "")
        raw_state = raw_span["state"] if "state" in raw_span else raw_span["state_json"] if "state_json" in raw_span else attrs.get("langgraph.state")

        node_name, r_node = scrub_flight_text(str(raw_node).strip() or f"step-{idx}")
        model_id, r_model = scrub_flight_text(str(raw_model).strip() or "gpt-4o")
        prompt_text, r_prompt = scrub_flight_text(_canonical_json(raw_prompt) if isinstance(raw_prompt, (dict, list)) else str(raw_prompt))
        output_text, r_output = scrub_flight_text(_canonical_json(raw_output) if isinstance(raw_output, (dict, list)) else str(raw_output))
        state_dict, state_json, r_state = scrub_flight_state(raw_state)

        raw_in = _first_present([(raw_span, "input_tokens"), (attrs, "gen_ai.usage.input_tokens"), (attrs, "gen_ai.usage.prompt_tokens")])
        raw_out = _first_present([(raw_span, "output_tokens"), (attrs, "gen_ai.usage.output_tokens"), (attrs, "gen_ai.usage.completion_tokens")])
        in_tok = max(0, int(raw_in)) if raw_in is not None else (0 if span_kind == "tool" or not prompt_text else max(1, len(prompt_text) // 4))
        out_tok = max(0, int(raw_out)) if raw_out is not None else (0 if span_kind == "tool" or not output_text else max(1, len(output_text) // 4))

        raw_cost = _first_present([(raw_span, "cost_usd"), (attrs, "gen_ai.usage.cost_usd")])
        cost_usd = round(max(0.0, float(raw_cost)), 6) if raw_cost is not None else _estimate_cost_usd(model_id, in_tok, out_tok, span_kind)
        return (
            _make_step_dict(idx, node_name, span_kind, model_id, prompt_text, output_text, state_dict, state_json, in_tok, out_tok, cost_usd),
            r_node + r_model + r_prompt + r_output + r_state,
        )

    @staticmethod
    def _row_to_step(row: sqlite3.Row) -> Dict[str, Any]:
        state_str, p_txt, o_txt = str(row["state_json"]), str(row["prompt_text"]), str(row["output_text"])
        return {
            "step_index": int(row["step_index"]), "node_name": str(row["node_name"]), "span_kind": str(row["span_kind"]),
            "model_id": str(row["model_id"]), "prompt_text": p_txt, "prompt": p_txt, "output_text": o_txt, "output": o_txt,
            "state": json.loads(state_str) if state_str else {}, "state_json": state_str,
            "input_tokens": int(row["input_tokens"]), "output_tokens": int(row["output_tokens"]),
            "cost_usd": float(row["cost_usd"]), "cached_reuse": bool(row["cached_reuse"]), "step_sha256": str(row["step_sha256"]),
        }

    def _assemble_tape(self, conn: sqlite3.Connection, row: sqlite3.Row) -> Dict[str, Any]:
        ws, tid = str(row["workspace_id"]), str(row["trace_id"])
        step_rows = conn.execute("SELECT * FROM platform_flight_steps WHERE workspace_id=? AND trace_id=? ORDER BY step_index ASC", (ws, tid)).fetchall()
        parent_tid = str(row["parent_trace_id"]) if row["parent_trace_id"] else None
        total_tokens, tokens_delta = int(row["total_tokens"]), 0
        if parent_tid:
            p_row = conn.execute("SELECT total_tokens FROM platform_flight_tapes WHERE workspace_id=? AND trace_id=?", (ws, parent_tid)).fetchone()
            if p_row is not None:
                tokens_delta = total_tokens - int(p_row["total_tokens"])
        return {
            "trace_id": tid, "workspace_id": ws, "workflow_name": str(row["workflow_name"]),
            "source_framework": str(row["source_framework"]), "parent_trace_id": parent_tid,
            "forked_from_step": int(row["forked_from_step"]) if row["forked_from_step"] is not None else None,
            "status": str(row["status"]), "total_steps": int(row["total_steps"]),
            "cached_steps_reused": int(row["cached_steps_reused"]), "total_tokens": total_tokens,
            "tokens_delta": tokens_delta, "total_cost_usd": float(row["total_cost_usd"]),
            "cost_delta_usd": float(row["cost_delta_usd"]), "dlp_redactions": int(row["dlp_redactions"]),
            "tape_sha256": str(row["tape_sha256"]), "created_at": str(row["created_at"]),
            "steps": [self._row_to_step(s) for s in step_rows],
        }

    def _persist_tape_and_steps(self, conn: sqlite3.Connection, tape_meta: Dict[str, Any], steps: Sequence[Dict[str, Any]]) -> None:
        ws, tid = tape_meta["workspace_id"], tape_meta["trace_id"]
        with conn:
            conn.execute("DELETE FROM platform_flight_steps WHERE workspace_id=? AND trace_id=?", (ws, tid))
            conn.execute(
                "INSERT OR REPLACE INTO platform_flight_tapes ("
                "trace_id, workspace_id, workflow_name, source_framework, parent_trace_id, forked_from_step, "
                "status, total_steps, cached_steps_reused, total_tokens, total_cost_usd, cost_delta_usd, "
                "dlp_redactions, tape_sha256, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    tid, ws, tape_meta["workflow_name"], tape_meta["source_framework"], tape_meta["parent_trace_id"],
                    tape_meta["forked_from_step"], tape_meta["status"], tape_meta["total_steps"],
                    tape_meta["cached_steps_reused"], tape_meta["total_tokens"], tape_meta["total_cost_usd"],
                    tape_meta["cost_delta_usd"], tape_meta["dlp_redactions"], tape_meta["tape_sha256"], tape_meta["created_at"],
                ),
            )
            for s in steps:
                conn.execute(
                    "INSERT INTO platform_flight_steps ("
                    "workspace_id, trace_id, step_index, node_name, span_kind, model_id, prompt_text, "
                    "output_text, state_json, input_tokens, output_tokens, cost_usd, cached_reuse, step_sha256"
                    ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        ws, tid, s["step_index"], s["node_name"], s["span_kind"], s["model_id"], s["prompt_text"],
                        s["output_text"], s["state_json"], s["input_tokens"], s["output_tokens"], s["cost_usd"],
                        1 if s["cached_reuse"] else 0, s["step_sha256"],
                    ),
                )

    def ingest_traces(
        self, workspace_id: str = "default", workflow_name: str = "agent-trace", source_framework: str = "opentelemetry_genai",
        spans: Optional[Sequence[Dict[str, Any]]] = None, resource_spans: Optional[Sequence[Dict[str, Any]]] = None, trace_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        ws = _clean_workspace_id(workspace_id)
        collected: List[Dict[str, Any]] = list(spans or [])
        detected_service, detected_tid = None, None
        if resource_spans:
            otlp_spans, detected_service, detected_tid = _extract_otlp_spans(resource_spans)
            collected.extend(otlp_spans)
        if not collected:
            raise ValueError("Trace ingestion requires at least 1 span in 'spans' or 'resource_spans'.")
        if not trace_id and not detected_tid:
            first_tid = str(collected[0].get("traceId") or collected[0].get("trace_id") or "").strip()
            if first_tid and _TRACE_ID_RE.fullmatch(first_tid):
                detected_tid = first_tid

        resolved_tid = _clean_trace_id(trace_id or detected_tid, allow_generate=True)
        raw_wf = str(workflow_name or "").strip()
        if (not raw_wf or raw_wf == "agent-trace") and detected_service:
            raw_wf = detected_service
        clean_wf, wf_r = scrub_flight_text(raw_wf or "agent-trace")
        clean_fw, fw_r = scrub_flight_text(str(source_framework or "opentelemetry_genai").strip() or "opentelemetry_genai")

        normalized_steps: List[Dict[str, Any]] = []
        total_redactions = wf_r + fw_r
        for idx, raw_sp in enumerate(collected):
            step_dict, step_r = self._normalize_span(idx, raw_sp)
            normalized_steps.append(step_dict)
            total_redactions += step_r

        total_tokens = sum(s["input_tokens"] + s["output_tokens"] for s in normalized_steps)
        total_cost = round(sum(s["cost_usd"] for s in normalized_steps), 6)
        tape_meta = _make_tape_meta(resolved_tid, ws, clean_wf, clean_fw, None, None, "recorded", normalized_steps, 0, total_tokens, 0, total_cost, 0.0, total_redactions)
        with self._lock:
            self._persist_tape_and_steps(self._ensure_conn(), tape_meta, normalized_steps)
        return {**tape_meta, "steps": normalized_steps}

    def get_tape(self, workspace_id: str = "default", trace_id: str = "") -> Dict[str, Any]:
        ws, tid = _clean_workspace_id(workspace_id), str(trace_id or "").strip()
        if not tid:
            raise KeyError("Trace '' not found.")
        with self._lock:
            conn = self._ensure_conn()
            row = conn.execute("SELECT * FROM platform_flight_tapes WHERE workspace_id=? AND trace_id=?", (ws, tid)).fetchone()
            if row is None:
                raise KeyError(f"Flight tape '{tid}' not found in workspace '{ws}'.")
            return self._assemble_tape(conn, row)

    def list_tapes(self, workspace_id: str = "default", limit: int = 20) -> Dict[str, Any]:
        ws = _clean_workspace_id(workspace_id)
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise ValueError("limit must be a positive integer.")
        with self._lock:
            conn = self._ensure_conn()
            rows = conn.execute("SELECT * FROM platform_flight_tapes WHERE workspace_id=? ORDER BY created_at DESC, rowid DESC LIMIT ?", (ws, min(limit, 200))).fetchall()
            tapes = [self._assemble_tape(conn, r) for r in rows]
        return {"workspace_id": ws, "total_tapes": len(tapes), "tapes": tapes}

    def replay_tape(
        self, workspace_id: str = "default", trace_id: str = "", from_step_index: int = 0,
        override_prompt: Optional[str] = None, override_model: Optional[str] = None, override_state: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        parent = self.get_tape(workspace_id=workspace_id, trace_id=trace_id)
        ws, parent_steps = parent["workspace_id"], parent["steps"]
        if isinstance(from_step_index, bool) or not isinstance(from_step_index, int) or not (0 <= from_step_index < len(parent_steps)):
            raise ValueError(f"from_step_index={from_step_index} out of bounds for trace '{trace_id}' with {len(parent_steps)} steps.")
        if override_state is not None and not isinstance(override_state, dict):
            raise ValueError("override_state must be a JSON object when provided.")

        clean_model_override, replay_redactions = None, 0
        if override_model is not None and str(override_model).strip():
            clean_model_override, replay_redactions = scrub_flight_text(str(override_model).strip())

        fork_steps: List[Dict[str, Any]] = []
        for idx, p_step in enumerate(parent_steps):
            if idx < from_step_index:
                fork_steps.append({**p_step, "cached_reuse": True, "cost_usd": 0.0})
                continue

            eff_model = clean_model_override if clean_model_override and (idx == from_step_index or p_step["span_kind"] != "tool") else p_step["model_id"]
            if idx == from_step_index and override_prompt is not None:
                eff_prompt, r_p = scrub_flight_text(str(override_prompt))
                replay_redactions += r_p
                in_tokens = max(1, len(eff_prompt) // 4) if eff_prompt else 0
            else:
                eff_prompt, in_tokens = p_step["prompt_text"], p_step["input_tokens"]

            eff_state, eff_state_json, r_s = scrub_flight_state({**p_step["state"], **(override_state or {})})
            cf_digest = _sha256_json({"model": eff_model, "node": p_step["node_name"], "parent_step_sha256": p_step["step_sha256"], "prompt": eff_prompt, "state": eff_state, "step_index": idx})[7:19]
            eff_output, r_o = scrub_flight_text(f"[{eff_model} counterfactual:{cf_digest}] {p_step['node_name']} -> prompt={eff_prompt[:96]} state_keys={sorted(eff_state.keys())}")
            replay_redactions += r_s + r_o

            out_tokens = p_step["output_tokens"] if (override_prompt is None and not override_state and p_step["output_tokens"] > 0) else max(1, len(eff_output) // 4)
            step_cost = _estimate_cost_usd(eff_model, in_tokens, out_tokens, p_step["span_kind"])
            fork_steps.append(_make_step_dict(idx, p_step["node_name"], p_step["span_kind"], eff_model, eff_prompt, eff_output, eff_state, eff_state_json, in_tokens, out_tokens, step_cost))

        fork_tid = f"fork-{uuid.uuid4().hex[:12]}"
        new_total_tokens = sum(s["input_tokens"] + s["output_tokens"] for s in fork_steps if not s["cached_reuse"])
        new_total_cost = round(sum(s["cost_usd"] for s in fork_steps), 6)
        fork_meta = _make_tape_meta(
            fork_tid, ws, parent["workflow_name"], parent["source_framework"], parent["trace_id"],
            from_step_index, "replayed", fork_steps, from_step_index, new_total_tokens,
            int(new_total_tokens) - int(parent["total_tokens"]), new_total_cost,
            round(new_total_cost - float(parent["total_cost_usd"]), 6), int(parent["dlp_redactions"]) + replay_redactions,
        )
        with self._lock:
            self._persist_tape_and_steps(self._ensure_conn(), fork_meta, fork_steps)
        return {**fork_meta, "steps": fork_steps}

    def promote_trace_to_eval(
        self, workspace_id: str = "default", trace_id: str = "", title: Optional[str] = None,
        expected_substrings: Optional[Sequence[str]] = None, forbidden_substrings: Optional[Sequence[str]] = None, created_by: str = "owner",
    ) -> Dict[str, Any]:
        tape = self.get_tape(workspace_id=workspace_id, trace_id=trace_id)
        ws, steps = tape["workspace_id"], tape["steps"]
        clean_title, _ = scrub_flight_text(str(title or "").strip() or f"Golden eval: {tape['workflow_name']} ({tape['trace_id']})")
        clean_creator, _ = scrub_flight_text(str(created_by or "owner").strip() or "owner")
        input_prompt = steps[0]["prompt_text"] if steps and steps[0]["prompt_text"] else tape["workflow_name"]
        pinned_tool_mocks = [
            {"step_index": s["step_index"], "tool_name": s["node_name"], "input": s["prompt_text"], "mock_output": s["output_text"], "state": s["state"], "step_sha256": s["step_sha256"]}
            for s in steps if s["span_kind"] == "tool"
        ]
        if expected_substrings:
            clean_expected = [scrub_flight_text(str(x).strip())[0] for x in expected_substrings if str(x).strip()]
        else:
            final_out = steps[-1]["output_text"] if steps else ""
            dedup_words = list(dict.fromkeys(tok for tok in _WORD_RE.findall(final_out) if tok != "REDACTED_SECRET"))[:3]
            clean_expected = dedup_words or ([final_out.strip()[:48]] if final_out.strip() else [tape["workflow_name"]])

        clean_forbidden = (
            ["[REDACTED_SECRET]", "Traceback"]
            if forbidden_substrings is None
            else ["[REDACTED_SECRET]" if str(x).strip() == "[REDACTED_SECRET]" else scrub_flight_text(str(x).strip())[0] for x in forbidden_substrings if str(x).strip()]
        )
        case_id, created_at = f"evalcase-{uuid.uuid4().hex[:12]}", _utc_now()
        case_sha256 = _sha256_json({"expected_substrings": clean_expected, "forbidden_substrings": clean_forbidden, "input_prompt": input_prompt, "pinned_tool_mocks": pinned_tool_mocks, "source_trace_id": tape["trace_id"], "title": clean_title, "workspace_id": ws})
        with self._lock:
            conn = self._ensure_conn()
            with conn:
                conn.execute(
                    "INSERT INTO platform_eval_dataset_cases (case_id, workspace_id, source_trace_id, title, input_prompt, expected_substrings_json, forbidden_substrings_json, pinned_tool_mocks_json, case_sha256, created_by, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (case_id, ws, tape["trace_id"], clean_title, input_prompt, _canonical_json(clean_expected), _canonical_json(clean_forbidden), _canonical_json(pinned_tool_mocks), case_sha256, clean_creator, created_at),
                )
        return {
            "case_id": case_id, "workspace_id": ws, "source_trace_id": tape["trace_id"], "title": clean_title,
            "input_prompt": input_prompt, "expected_substrings": clean_expected, "forbidden_substrings": clean_forbidden,
            "pinned_tool_mocks": pinned_tool_mocks, "case_sha256": case_sha256, "created_by": clean_creator, "created_at": created_at,
        }

    def list_eval_cases(self, workspace_id: str = "default") -> Dict[str, Any]:
        ws = _clean_workspace_id(workspace_id)
        with self._lock:
            rows = self._ensure_conn().execute("SELECT * FROM platform_eval_dataset_cases WHERE workspace_id=? ORDER BY created_at DESC, rowid DESC", (ws,)).fetchall()
        cases = [
            {
                "case_id": str(r["case_id"]), "workspace_id": str(r["workspace_id"]), "source_trace_id": str(r["source_trace_id"]),
                "title": str(r["title"]), "input_prompt": str(r["input_prompt"]),
                "expected_substrings": json.loads(str(r["expected_substrings_json"])),
                "forbidden_substrings": json.loads(str(r["forbidden_substrings_json"])),
                "pinned_tool_mocks": json.loads(str(r["pinned_tool_mocks_json"])),
                "case_sha256": str(r["case_sha256"]), "created_by": str(r["created_by"]), "created_at": str(r["created_at"]),
            }
            for r in rows
        ]
        return {"workspace_id": ws, "total_cases": len(cases), "cases": cases}


flight_tape_engine = SQLiteFlightTapeEngine()
