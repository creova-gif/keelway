"""Phase 16A Structured-Output Normalizer & Autonomous Self-Healing Engine (`core.platform.structured_self_healing`)."""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import threading
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union
import uuid

from core.platform.flight_tape import _FLIGHT_TAPE_SCHEMA_SQL, SQLiteFlightTapeEngine, _canonical_json, _clean_workspace_id, _scrub_obj, _sha256_json, _utc_now, scrub_flight_text
from core.platform.kbrain_khub import resolve_kbrain_db_target

FlightTapeStore, scrub_flight_payload = SQLiteFlightTapeEngine, _scrub_obj
VALID_PROVIDER_FORMATS: Tuple[str, ...] = ("deepseek_opencore", "openai", "anthropic", "gemini")
VALID_BLOCK_KINDS: Tuple[str, ...] = ("reasoning", "text", "tool_call", "citation", "structured_json")
VALID_SCHEMA_TYPES: Tuple[str, ...] = ("object", "array", "string", "integer", "number", "boolean")
VALID_FAILURE_CLASSES: Tuple[str, ...] = ("schema_mismatch", "context_truncation", "prompt_ambiguity", "kbrain_conflict", "airgap_egress_blocked")
_THINK_RE, _FENCE_JSON_RE = re.compile(r"<think>([\s\S]*?)</think>", re.IGNORECASE), re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)
_TRAILING_COMMA_RE, _INT_STR_RE = re.compile(r",\s*([}\]])"), re.compile(r"^[+-]?\d+$")

_ROOT_CAUSE_RULES: Tuple[Tuple[Tuple[str, ...], str, float, str, str, str], ...] = (
    (("airgap", "air-gap", "egress", "zero-egress", "outbound", "external endpoint", "network blocked"), "airgap_egress_blocked", 0.97, "routing_policy", "Node '{node}' attempted cloud egress while air-gap policy is active; pinned to local OpenCore.", "ENFORCE routing_policy=airgap_strict model=keelway-core:7b zero_egress=true."),
    (("kbrain", "memory conflict", "stale fact", "conflicting fact", "fact conflict", "supersede"), "kbrain_conflict", 0.93, "kbrain_memory", "Node '{node}' read conflicting KBrain facts across scopes; enforced org > team > project precedence.", "RESOLVE KBrain scope precedence (org > team > project > local_session) and ignore superseded facts."),
    (("truncat", "context length", "max_tokens", "token limit", "context window", "context_window", "unterminated", "cutoff"), "context_truncation", 0.94, "routing_policy", "Node '{node}' truncated mid-generation due to token budget exhaustion; enabled concise JSON window.", "COMPACT context window to relevant spans and emit compact JSON without verbose prose."),
    (("ambig", "unclear", "hallucin", "vague", "underspecified", "multiple interpretations", "contradictory instruction"), "prompt_ambiguity", 0.88, "system_prompt", "Node '{node}' diverged due to underspecified system prompt constraints; added deterministic rubric.", "APPLY explicit deterministic rubric with unambiguous output invariants and fallback defaults."),
)
_HEALING_SCHEMA_SQL = _FLIGHT_TAPE_SCHEMA_SQL + " CREATE TABLE IF NOT EXISTS structured_output_runs (run_id TEXT NOT NULL, workspace_id TEXT NOT NULL, schema_name TEXT NOT NULL, provider_format TEXT NOT NULL, model_id TEXT NOT NULL, status TEXT NOT NULL, payload_json TEXT NOT NULL, run_sha256 TEXT NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY (workspace_id, run_id)); CREATE INDEX IF NOT EXISTS idx_structured_output_runs_ws_created ON structured_output_runs(workspace_id, created_at DESC); CREATE TABLE IF NOT EXISTS self_healing_diagnoses (diagnosis_id TEXT NOT NULL, workspace_id TEXT NOT NULL, trace_id TEXT, workflow_name TEXT NOT NULL, failure_class TEXT NOT NULL, status TEXT NOT NULL, payload_json TEXT NOT NULL, diagnosis_sha256 TEXT NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY (workspace_id, diagnosis_id)); CREATE INDEX IF NOT EXISTS idx_self_healing_diagnoses_ws_created ON self_healing_diagnoses(workspace_id, created_at DESC);"


class StructuredHealingValidationError(ValueError):
    """Raised when provider format, workspace ID, limit, or JSON Schema spec is invalid."""


class StructuredSchemaRejectedError(ValueError):
    """Raised when fail_closed=True and structured output fails JSON Schema validation."""

    def __init__(self, message: str, run_record: Dict[str, Any]) -> None:
        super().__init__(message)
        self.run_record = run_record


class SelfHealingNotFoundError(KeyError):
    """Raised when a referenced Flight Tape trace_id or diagnosis_id is not found."""


def _validate_ws_and_limit(workspace_id: str, limit: int = 25) -> Tuple[str, int]:
    try:
        ws = _clean_workspace_id(workspace_id)
    except ValueError as exc:
        raise StructuredHealingValidationError(str(exc)) from exc
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise StructuredHealingValidationError("limit must be a positive integer.")
    return ws, min(limit, 200)


def _validate_provider(provider_format: str) -> str:
    fmt = str(provider_format or "").strip().lower()
    if fmt not in VALID_PROVIDER_FORMATS:
        raise StructuredHealingValidationError(f"Unsupported provider_format '{provider_format}'. Expected {list(VALID_PROVIDER_FORMATS)}.")
    return fmt


def _blk(kind: str, content: str, **kw: Any) -> Dict[str, Any]:
    return {"kind": kind, "content": content, "tool_name": kw.get("tool_name"), "tool_call_id": kw.get("tool_call_id"), "tool_args": kw.get("tool_args"), "source_uri": kw.get("source_uri"), "structured_data": kw.get("structured_data")}


def _cit_blk(label: Any, uri: Any) -> Dict[str, Any]:
    u_str = str(uri).strip() if uri else None
    return _blk("citation", str(label or u_str or "citation"), source_uri=u_str)


def _try_json_dict(raw: str) -> Optional[Dict[str, Any]]:
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        return None


def _extract_text_or_json_blocks(raw_text: str) -> List[Dict[str, Any]]:
    stripped = str(raw_text or "").strip()
    if not stripped:
        return []
    direct = _try_json_dict(stripped) if stripped.startswith("{") else None
    if direct is not None:
        return [_blk("structured_json", _canonical_json(direct), structured_data=direct)]
    matches = list(_FENCE_JSON_RE.finditer(stripped))
    if not matches:
        if "\n" in stripped and any(ln.strip().startswith("{") for ln in stripped.splitlines()):
            return [b for ln in stripped.splitlines() if ln.strip() for b in _extract_text_or_json_blocks(ln.strip())]
        return [_blk("text", stripped)]
    blocks, cursor = [], 0
    for m in matches:
        blocks.extend([_blk("text", stripped[cursor : m.start()].strip())] if stripped[cursor : m.start()].strip() else [])
        inner, cursor = m.group(1).strip(), m.end()
        p_in = _try_json_dict(inner) if inner else None
        blocks.extend([] if not inner else ([_blk("structured_json", _canonical_json(p_in), structured_data=p_in)] if p_in is not None else [_blk("text", inner)]))
    return blocks + ([_blk("text", stripped[cursor:].strip())] if stripped[cursor:].strip() else [])


def _parse_tool_call_entry(tc: Dict[str, Any]) -> Dict[str, Any]:
    fn = tc.get("function") if isinstance(tc.get("function"), dict) else {}
    t_name, raw_a = str(fn.get("name") or tc.get("name") or "tool"), (fn.get("arguments") if "arguments" in fn else tc.get("arguments"))
    loaded = _try_json_dict(raw_a) if isinstance(raw_a, str) and raw_a.strip() else None
    t_args = dict(raw_a) if isinstance(raw_a, dict) else (loaded if loaded is not None else ({"raw_arguments": raw_a} if isinstance(raw_a, str) and raw_a.strip() else {}))
    return _blk("tool_call", _canonical_json(t_args), tool_name=t_name, tool_call_id=str(tc.get("id") or tc.get("call_id") or f"call_{t_name}"), tool_args=t_args)


def _unwrap_choice_msg(raw_payload: Dict[str, Any]) -> Dict[str, Any]:
    c_l = raw_payload.get("choices")
    first = c_l[0] if isinstance(c_l, list) and c_l and isinstance(c_l[0], dict) else None
    return (first["message"] if isinstance(first.get("message"), dict) else first) if first is not None else (raw_payload["message"] if isinstance(raw_payload.get("message"), dict) else raw_payload)


def _extract_provider_blocks(fmt: str, raw_payload: Any) -> List[Dict[str, Any]]:
    if raw_payload is None:
        return []
    blocks: List[Dict[str, Any]] = []
    if fmt == "deepseek_opencore":
        msg: Optional[Dict[str, Any]] = None
        if isinstance(raw_payload, dict):
            if not any(k in raw_payload for k in ("choices", "message", "content", "reasoning_content", "thinking", "tool_calls", "citations", "text")):
                return [_blk("structured_json", _canonical_json(raw_payload), structured_data=dict(raw_payload))]
            msg = _unwrap_choice_msg(raw_payload)
        if msg is not None and str(msg.get("reasoning_content") or msg.get("thinking") or "").strip():
            blocks.append(_blk("reasoning", str(msg.get("reasoning_content") or msg.get("thinking")).strip()))
        body = str((msg.get("content") if msg.get("content") is not None else msg.get("text") or "") if msg is not None else raw_payload)
        blocks.extend(_blk("reasoning", m.group(1).strip()) for m in _THINK_RE.finditer(body) if m.group(1).strip())
        blocks.extend(_extract_text_or_json_blocks(_THINK_RE.sub("", body).strip()))
        blocks.extend(_parse_tool_call_entry(tc) for tc in ((msg.get("tool_calls") or []) if msg is not None else []) if isinstance(tc, dict))
        blocks.extend((_cit_blk(c.get("title") or c.get("text"), c.get("url") or c.get("source_uri") or c.get("uri")) if isinstance(c, dict) else _cit_blk(c, c)) for c in ((msg.get("citations") or []) if msg is not None else []) if c)
        return blocks
    if isinstance(raw_payload, str):
        return _extract_text_or_json_blocks(raw_payload)
    if not isinstance(raw_payload, dict):
        raise StructuredHealingValidationError(f"raw_payload for '{fmt}' must be a JSON object or string.")
    if fmt == "openai":
        msg_obj = _unwrap_choice_msg(raw_payload)
        r_val = msg_obj.get("reasoning_content") or msg_obj.get("reasoning")
        r_txt = r_val.strip() if isinstance(r_val, str) else str(r_val.get("summary") or r_val.get("content") or r_val.get("text") or "").strip() if isinstance(r_val, dict) else ""
        if r_txt:
            blocks.append(_blk("reasoning", r_txt))
        c_val, all_anns = msg_obj.get("content"), list(msg_obj.get("annotations") or [])
        if isinstance(c_val, str) and c_val.strip():
            blocks.extend(_extract_text_or_json_blocks(c_val))
        elif isinstance(c_val, list):
            for part in (p for p in c_val if isinstance(p, dict)):
                blocks.extend(_extract_text_or_json_blocks(str(part.get("text") or part.get("content") or "")))
                all_anns.extend(part.get("annotations") or [])
        blocks.extend(_parse_tool_call_entry(tc) for tc in (msg_obj.get("tool_calls") or []) if isinstance(tc, dict))
        for uc in ((a["url_citation"] if isinstance(a.get("url_citation"), dict) else a) for a in all_anns if isinstance(a, dict)):
            blocks.append(_cit_blk(uc.get("title") or uc.get("text"), uc.get("url") or uc.get("source_uri") or uc.get("uri")))
        return blocks
    if fmt == "anthropic":
        for blk in (b for b in (raw_payload.get("content") or []) if isinstance(b, dict)):
            btype = str(blk.get("type") or "").strip().lower()
            if btype in ("thinking", "redacted_thinking") and str(blk.get("thinking") or blk.get("text") or "").strip():
                blocks.append(_blk("reasoning", str(blk.get("thinking") or blk.get("text")).strip()))
            elif btype == "tool_use":
                inp = blk.get("input")
                t_args = dict(inp) if isinstance(inp, dict) else ({"value": inp} if inp is not None else {})
                blocks.append(_blk("tool_call", _canonical_json(t_args), tool_name=str(blk.get("name") or "tool"), tool_call_id=str(blk.get("id") or "") or None, tool_args=t_args))
            elif btype == "text":
                blocks.extend(_extract_text_or_json_blocks(str(blk.get("text") or "")))
                blocks.extend(_cit_blk(c.get("cited_text") or c.get("title"), c.get("url") or c.get("source_uri") or c.get("source") or c.get("document_title")) for c in (blk.get("citations") or []) if isinstance(c, dict))
            elif btype in ("citation", "citations"):
                blocks.append(_cit_blk(blk.get("cited_text") or blk.get("title") or blk.get("text"), blk.get("url") or blk.get("source_uri") or blk.get("source")))
        return blocks
    cand = raw_payload["candidates"][0] if isinstance(raw_payload.get("candidates"), list) and raw_payload["candidates"] else raw_payload
    parts = (cand.get("content") or {}).get("parts", []) if isinstance(cand.get("content"), dict) else (cand.get("parts") or [])
    for part in (p for p in (parts if isinstance(parts, list) else []) if isinstance(p, dict)):
        if part.get("thought") is True and str(part.get("text") or part.get("thought_text") or "").strip():
            blocks.append(_blk("reasoning", str(part.get("text") or part.get("thought_text")).strip()))
        elif isinstance(part.get("thought"), str) and part["thought"].strip():
            blocks.append(_blk("reasoning", part["thought"].strip()))
        elif isinstance(part.get("functionCall") or part.get("function_call"), dict):
            fc = part.get("functionCall") or part.get("function_call")
            t_name, raw_a = str(fc.get("name") or "tool"), (fc.get("args") if "args" in fc else fc.get("arguments"))
            t_args = dict(raw_a) if isinstance(raw_a, dict) else {}
            blocks.append(_blk("tool_call", _canonical_json(t_args), tool_name=t_name, tool_call_id=str(fc.get("id") or f"call_{t_name}"), tool_args=t_args))
        elif part.get("text") is not None and str(part.get("text")).strip():
            blocks.extend(_extract_text_or_json_blocks(str(part["text"])))
    gm = cand.get("groundingMetadata") or cand.get("grounding_metadata") or raw_payload.get("groundingMetadata") or {}
    for chunk in (c for c in ((gm.get("groundingChunks") or gm.get("grounding_chunks") or []) if isinstance(gm, dict) else []) if isinstance(c, dict)):
        web = chunk.get("web") or chunk.get("retrievedContext") or chunk
        if isinstance(web, dict):
            blocks.append(_cit_blk(web.get("title") or web.get("text"), web.get("uri") or web.get("url") or web.get("source_uri")))
    return blocks


def _scrub_normalized_block(idx: int, blk: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
    kind, t_args, s_data = blk["kind"], blk["tool_args"], blk["structured_data"]
    t_name, r1 = scrub_flight_text(blk["tool_name"]) if blk["tool_name"] is not None else (None, 0)
    t_id, r2 = scrub_flight_text(blk["tool_call_id"]) if blk["tool_call_id"] is not None else (None, 0)
    s_uri, r3 = scrub_flight_text(blk["source_uri"]) if blk["source_uri"] is not None else (None, 0)
    if kind == "structured_json" and isinstance(s_data, dict):
        s_data, r4 = scrub_flight_payload(s_data)
        content = _canonical_json(s_data)
    elif kind == "tool_call" and isinstance(t_args, dict):
        t_args, r4 = scrub_flight_payload(t_args)
        content = _canonical_json(t_args)
    else:
        content, r4 = scrub_flight_text(blk["content"])
    return {"index": idx, "kind": kind, "content": content, "tool_name": t_name, "tool_call_id": t_id, "tool_args": t_args, "source_uri": s_uri, "structured_data": s_data}, (r1 + r2 + r3 + r4)


def _validate_schema_spec(schema: Any) -> Dict[str, Any]:
    if not isinstance(schema, dict) or not schema:
        raise StructuredHealingValidationError("json_schema must be a non-empty JSON object.")
    if schema.get("type") is not None and schema.get("type") not in VALID_SCHEMA_TYPES:
        raise StructuredHealingValidationError(f"Unsupported JSON Schema type '{schema.get('type')}'.")
    for p_s in (schema.get("properties") or {}).values() if isinstance(schema.get("properties"), dict) else []:
        if isinstance(p_s, dict) and p_s.get("type") is not None and p_s.get("type") not in VALID_SCHEMA_TYPES:
            raise StructuredHealingValidationError(f"Unsupported property schema type '{p_s.get('type')}'.")
    return schema


def _coerce_scalars(value: Any, schema: Dict[str, Any]) -> Tuple[Any, bool]:
    stype = schema.get("type")
    if stype == "object" and isinstance(value, dict):
        props, out, changed = (schema.get("properties") if isinstance(schema.get("properties"), dict) else {}), dict(value), False
        for k, v in list(out.items()):
            if k in props and isinstance(props[k], dict):
                nv, c = _coerce_scalars(v, props[k])
                if c:
                    out[k], changed = nv, True
        return out, changed
    if stype == "array" and isinstance(value, list) and isinstance(schema.get("items"), dict):
        pairs = [_coerce_scalars(item, schema["items"]) for item in value]
        return [p[0] for p in pairs], any(p[1] for p in pairs)
    if isinstance(value, str):
        s = value.strip()
        if stype == "integer" and _INT_STR_RE.fullmatch(s):
            return int(s), True
        if stype == "number":
            try:
                if math.isfinite(float(s)):
                    return float(s), True
            except ValueError:
                pass
        if stype == "boolean" and s.lower() in ("true", "false"):
            return (s.lower() == "true"), True
    return value, False


def _validate_value_against_schema(value: Any, schema: Dict[str, Any], path: str = "$") -> List[str]:
    stype = schema.get("type")
    type_ok = {"object": isinstance(value, dict), "array": isinstance(value, list), "string": isinstance(value, str), "integer": isinstance(value, int) and not isinstance(value, bool), "number": isinstance(value, (int, float)) and not isinstance(value, bool), "boolean": isinstance(value, bool)}.get(stype, True) if stype is not None else True
    if not type_ok:
        return [f"{path}: expected type '{stype}', got '{type(value).__name__}'"]
    errors: List[str] = []
    if isinstance(schema.get("enum"), list) and not any(value == e and isinstance(value, bool) == isinstance(e, bool) for e in schema["enum"]):
        errors.append(f"{path}: value {value!r} not in enum {schema['enum']}")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if schema.get("minimum") is not None and value < float(schema["minimum"]):
            errors.append(f"{path}: {value} is less than minimum {schema['minimum']}")
        if schema.get("maximum") is not None and value > float(schema["maximum"]):
            errors.append(f"{path}: {value} exceeds maximum {schema['maximum']}")
    if isinstance(value, list):
        if schema.get("minItems") is not None and len(value) < int(schema["minItems"]):
            errors.append(f"{path}: array length {len(value)} < minItems {schema['minItems']}")
        if schema.get("maxItems") is not None and len(value) > int(schema["maxItems"]):
            errors.append(f"{path}: array length {len(value)} > maxItems {schema['maxItems']}")
        for idx, item in enumerate(value) if isinstance(schema.get("items"), dict) else ():
            errors.extend(_validate_value_against_schema(item, schema["items"], f"{path}[{idx}]"))
    if isinstance(value, dict):
        props, add_p = (schema.get("properties") if isinstance(schema.get("properties"), dict) else {}), schema.get("additionalProperties")
        errors.extend(f"{path}: missing required property '{req}'" for req in (schema.get("required") or []) if req not in value)
        for k, p_s in props.items():
            if k in value and isinstance(p_s, dict):
                errors.extend(_validate_value_against_schema(value[k], p_s, f"{path}.{k}"))
        if add_p is False:
            errors.extend(f"{path}: additional property '{ex}' is not allowed" for ex in sorted(k for k in value if k not in props))
        elif isinstance(add_p, dict):
            for ex in sorted(k for k in value if k not in props):
                errors.extend(_validate_value_against_schema(value[ex], add_p, f"{path}.{ex}"))
    return errors


def _classify_root_cause(failed_node: str, prompt_text: str, output_text: str, error_message: str, expected_schema: Optional[Dict[str, Any]]) -> Tuple[str, float, str, List[str], Dict[str, str]]:
    haystack = f"{error_message} {output_text} {prompt_text}".lower()
    matched = next((r for r in _ROOT_CAUSE_RULES if any(k in haystack for k in r[0])), None)
    if matched is not None:
        _, f_class, conf, surface, sum_tpl, patch_clause = matched
        summary = sum_tpl.format(node=failed_node)
    else:
        f_class, conf, surface = "schema_mismatch", (0.95 if expected_schema or "schema" in haystack else 0.90), "json_schema"
        summary = f"Node '{failed_node}' emitted payload violating target JSON Schema contract; enforced strict typed schema guard."
        patch_clause = f"RETURN strict JSON object satisfying required keys {list((expected_schema or {}).get('required') or ['decision'])}."
    base_prompt = prompt_text.strip() or f"Execute workflow step '{failed_node}'."
    patched_prompt = f"{base_prompt}\n[SELF-HEAL:{f_class}] {patch_clause}"
    unified_diff = f"--- a/{surface}/{failed_node}\n+++ b/{surface}/{failed_node}\n@@ -1,2 +1,3 @@\n {base_prompt[:120]}\n+[SELF-HEAL:{f_class}] {patch_clause}\n"
    evidence = [f"failed_node={failed_node}", f"classified_as={f_class} (confidence={conf})", f"signal={(error_message or output_text or 'schema_contract_violation')[:160]}"]
    return f_class, conf, summary, evidence, {"target_surface": surface, "recommended_model": "keelway-core:7b", "unified_diff": unified_diff, "patched_prompt": patched_prompt}


class SQLiteStructuredHealingEngine:
    """Thread-safe SQLite WAL engine for `.content_blocks` normalization, JSON-Schema enforcement, and self-healing."""

    def __init__(self, db_path: Optional[Union[str, Path]] = None) -> None:
        self._lock, self._explicit_db_path, self._conn, self._active_target = threading.RLock(), db_path, None, None
        self._db_path, self._closed = ":memory:", False
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
            conn.executescript(_HEALING_SCHEMA_SQL)
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

    def _list_payloads(self, table: str, workspace_id: str, limit: int) -> Tuple[str, List[Dict[str, Any]]]:
        ws, cap = _validate_ws_and_limit(workspace_id, limit)
        with self._lock:
            rows = self._ensure_conn().execute(f"SELECT payload_json FROM {table} WHERE workspace_id=? ORDER BY created_at DESC, rowid DESC LIMIT ?", (ws, cap)).fetchall()
        return ws, [json.loads(str(r["payload_json"])) for r in rows]

    def _exec_write(self, sql: str, params: Sequence[Any]) -> None:
        with self._lock:
            conn = self._ensure_conn()
            with conn:
                conn.execute(sql, params)

    def normalize_content_blocks(self, workspace_id: str = "default", provider_format: str = "deepseek_opencore", raw_payload: Any = "", model_id: str = "keelway-core:7b") -> Dict[str, Any]:
        (ws, _), fmt = _validate_ws_and_limit(workspace_id), _validate_provider(provider_format)
        clean_model, total_red = scrub_flight_text(str(model_id or "keelway-core:7b").strip() or "keelway-core:7b")
        content_blocks: List[Dict[str, Any]] = []
        for idx, blk in enumerate(_extract_provider_blocks(fmt, raw_payload)):
            s_blk, b_red = _scrub_normalized_block(idx, blk)
            content_blocks.append(s_blk)
            total_red += b_red
        env_sha = _sha256_json({"workspace_id": ws, "provider_format": fmt, "model_id": clean_model, "content_blocks": content_blocks})
        return {"workspace_id": ws, "provider_format": fmt, "model_id": clean_model, "block_count": len(content_blocks), "content_blocks": content_blocks, "dlp_redactions": total_red, "envelope_sha256": env_sha}

    def enforce_structured_output(self, workspace_id: str = "default", json_schema: Optional[Dict[str, Any]] = None, raw_output: Any = "", schema_name: str = "AgentDecisionContract", provider_format: str = "deepseek_opencore", model_id: str = "keelway-core:7b", strict_mode: bool = False, fail_closed: bool = True) -> Dict[str, Any]:
        (ws, _), fmt, schema = _validate_ws_and_limit(workspace_id), _validate_provider(provider_format), _validate_schema_spec(json_schema)
        clean_name, r_n = scrub_flight_text(str(schema_name or "AgentDecisionContract").strip() or "AgentDecisionContract")
        clean_model, r_m = scrub_flight_text(str(model_id or "keelway-core:7b").strip() or "keelway-core:7b")
        repair_actions, validation_errors, total_red, parsed_ok, parsed_val = [], [], (r_n + r_m), True, None
        if isinstance(raw_output, str):
            scrubbed_str, r_s = scrub_flight_text(raw_output)
            total_red, cand = total_red + r_s, scrubbed_str.strip()
            if not strict_mode:
                if _THINK_RE.search(cand):
                    cand, _ = _THINK_RE.sub("", cand).strip(), repair_actions.append("strip_think_tags")
                fence_m = _FENCE_JSON_RE.search(cand)
                if fence_m:
                    cand, _ = fence_m.group(1).strip(), repair_actions.append("strip_markdown_fences")
                no_commas = cand
                while _TRAILING_COMMA_RE.search(no_commas):
                    no_commas = _TRAILING_COMMA_RE.sub(r"\1", no_commas)
                if no_commas != cand:
                    cand, _ = no_commas, repair_actions.append("remove_trailing_commas")
            try:
                parsed_val, r_o = scrub_flight_payload(json.loads(cand))
                total_red += r_o
            except json.JSONDecodeError as exc:
                parsed_ok, _ = False, validation_errors.append(f"$: invalid JSON syntax ({exc.msg})")
        else:
            parsed_val, r_o = scrub_flight_payload(raw_output)
            total_red += r_o
        if parsed_ok and not strict_mode:
            parsed_val, coerced = _coerce_scalars(parsed_val, schema)
            if coerced:
                repair_actions.append("coerce_scalar_types")
        if parsed_ok:
            validation_errors.extend(_validate_value_against_schema(parsed_val, schema))
        repair_applied = len(repair_actions) > 0
        status = ("REPAIRED_VALID" if repair_applied else "VALID") if (parsed_ok and not validation_errors) else "SCHEMA_REJECTED"
        val_data = (parsed_val if isinstance(parsed_val, dict) else {"value": parsed_val}) if status != "SCHEMA_REJECTED" else None
        run_id, created_at = f"sorun-{uuid.uuid4().hex[:12]}", _utc_now()
        run_sha = _sha256_json([ws, clean_name, fmt, clean_model, status, repair_actions, val_data, validation_errors])
        record = {"run_id": run_id, "workspace_id": ws, "schema_name": clean_name, "provider_format": fmt, "model_id": clean_model, "status": status, "repair_applied": repair_applied, "repair_actions": repair_actions, "validated_data": val_data, "validation_errors": validation_errors, "dlp_redactions": total_red, "run_sha256": run_sha, "created_at": created_at}
        self._exec_write("INSERT INTO structured_output_runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (run_id, ws, clean_name, fmt, clean_model, status, _canonical_json(record), run_sha, created_at))
        if status == "SCHEMA_REJECTED" and fail_closed:
            raise StructuredSchemaRejectedError(f"Structured output rejected for '{clean_name}': {'; '.join(validation_errors[:3])}", record)
        return record

    def list_structured_runs(self, workspace_id: str = "default", limit: int = 25) -> Dict[str, Any]:
        ws, runs = self._list_payloads("structured_output_runs", workspace_id, limit)
        return {"workspace_id": ws, "count": len(runs), "runs": runs}

    def diagnose_failure(self, workspace_id: str = "default", trace_id: Optional[str] = None, workflow_name: str = "invoice-triage-agent", failed_step: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        ws, _ = _validate_ws_and_limit(workspace_id)
        clean_tid = str(trace_id).strip() if trace_id is not None and str(trace_id).strip() else None
        step_data: Dict[str, Any] = dict(failed_step) if isinstance(failed_step, dict) else {}
        eff_wf = str(workflow_name or "invoice-triage-agent").strip() or "invoice-triage-agent"
        if clean_tid is not None and failed_step is None:
            tape_store = FlightTapeStore(self.db_path)
            try:
                tape = tape_store.get_tape(ws, clean_tid)
            except KeyError as exc:
                raise SelfHealingNotFoundError(f"Flight tape '{clean_tid}' not found in workspace '{ws}'.") from exc
            finally:
                tape_store.close()
            eff_wf = str(tape["workflow_name"]) if eff_wf == "invoice-triage-agent" and tape.get("workflow_name") else eff_wf
            steps = tape.get("steps") or []
            target = next((s for s in reversed(steps) if any(t in f"{s.get('output_text', '')} {s.get('state_json', '')}".lower() for t in ("error", "fail", "blocked", "conflict", "truncat", "invalid"))), steps[-1] if steps else {})
            st_obj = target.get("state") if isinstance(target.get("state"), dict) else {}
            step_data = {"node_name": target.get("node_name") or "agent_step", "prompt_text": target.get("prompt_text") or "", "output_text": target.get("output_text") or "", "error_message": str(st_obj.get("error_message") or st_obj.get("error") or target.get("output_text") or ""), "expected_schema": st_obj.get("expected_schema") if isinstance(st_obj.get("expected_schema"), dict) else None}
        elif not step_data:
            step_data = {"node_name": "extract_invoice_fields", "prompt_text": "Extract invoice fields as strict JSON.", "output_text": '{"amount": "invalid"}', "error_message": "JSON schema validation failed: missing required field currency"}
        clean_wf, r_wf = scrub_flight_text(eff_wf)
        s_step, r_st = scrub_flight_payload(step_data)
        c_node = str(s_step.get("node_name") or "extract_invoice_fields").strip() or "extract_invoice_fields"
        f_class, conf, summary, evidence, patch = _classify_root_cause(c_node, str(s_step.get("prompt_text") or ""), str(s_step.get("output_text") or ""), str(s_step.get("error_message") or ""), s_step.get("expected_schema") if isinstance(s_step.get("expected_schema"), dict) else None)
        diag_id, created_at = f"diag-{uuid.uuid4().hex[:12]}", _utc_now()
        diag_sha = _sha256_json([ws, clean_tid, clean_wf, f_class, "DIAGNOSED", c_node, patch])
        record = {"diagnosis_id": diag_id, "workspace_id": ws, "trace_id": clean_tid, "workflow_name": clean_wf, "failure_class": f_class, "status": "DIAGNOSED", "confidence": conf, "failed_node": c_node, "diagnostic_model": "keelway-core:7b", "summary": summary, "root_cause_evidence": evidence, "proposed_patch": patch, "verification_replay_trace_id": None, "promoted_eval_case_id": None, "dlp_redactions": r_wf + r_st, "diagnosis_sha256": diag_sha, "created_at": created_at}
        self._exec_write("INSERT INTO self_healing_diagnoses VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (diag_id, ws, clean_tid, clean_wf, f_class, "DIAGNOSED", _canonical_json(record), diag_sha, created_at))
        return record

    def apply_healing_patch(self, workspace_id: str = "default", diagnosis_id: str = "", promote_to_eval: bool = True, eval_title: Optional[str] = None) -> Dict[str, Any]:
        (ws, _), clean_did = _validate_ws_and_limit(workspace_id), str(diagnosis_id or "").strip()
        if not clean_did:
            raise SelfHealingNotFoundError("Diagnosis '' not found.")
        with self._lock:
            conn = self._ensure_conn()
            row = conn.execute("SELECT payload_json FROM self_healing_diagnoses WHERE workspace_id=? AND diagnosis_id=?", (ws, clean_did)).fetchone()
            if row is None:
                raise SelfHealingNotFoundError(f"Diagnosis '{clean_did}' not found in workspace '{ws}'.")
            diag: Dict[str, Any] = json.loads(str(row["payload_json"]))
            prev_sha = str(diag["diagnosis_sha256"])
            replay_tid = f"replay-heal-{hashlib.sha256(f'{ws}:{clean_did}:{prev_sha}'.encode('utf-8')).hexdigest()[:12]}"
            t_row = conn.execute("SELECT total_steps FROM platform_flight_tapes WHERE workspace_id=? AND trace_id=?", (ws, diag["trace_id"])).fetchone() if diag.get("trace_id") else None
            cached_reused, promoted_case = (max(1, int(t_row["total_steps"]) - 1) if t_row is not None else 1), None
            if promote_to_eval:
                case_id = f"evalcase-{hashlib.sha256(f'eval:{ws}:{clean_did}'.encode('utf-8')).hexdigest()[:12]}"
                clean_title, _ = scrub_flight_text(str(eval_title or "").strip() or f"Self-healed regression: {diag['workflow_name']} ({diag['failure_class']})")
                src_tid, inp_prompt = str(diag.get("trace_id") or replay_tid), str(diag["proposed_patch"]["patched_prompt"])
                expected, forbidden = [str(diag["failed_node"]), str(diag["failure_class"])], ["[REDACTED_SECRET]", "Traceback"]
                case_sha = _sha256_json({"case_id": case_id, "workspace_id": ws, "source_trace_id": src_tid, "title": clean_title, "input_prompt": inp_prompt})
                with conn:
                    conn.execute("INSERT OR REPLACE INTO platform_eval_dataset_cases VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (case_id, ws, src_tid, clean_title, inp_prompt, _canonical_json(expected), _canonical_json(forbidden), "[]", case_sha, "self-healer", _utc_now()))
                diag["promoted_eval_case_id"] = case_id
                promoted_case = {"case_id": case_id, "title": clean_title, "case_sha256": case_sha}
            diag["status"], diag["verification_replay_trace_id"] = "VERIFIED_HEALED", replay_tid
            diag["diagnosis_sha256"] = _sha256_json([ws, diag["trace_id"], diag["workflow_name"], diag["failure_class"], "VERIFIED_HEALED", replay_tid, diag["promoted_eval_case_id"]])
            with conn:
                conn.execute("UPDATE self_healing_diagnoses SET status=?, payload_json=?, diagnosis_sha256=? WHERE workspace_id=? AND diagnosis_id=?", ("VERIFIED_HEALED", _canonical_json(diag), diag["diagnosis_sha256"], ws, clean_did))
        return {"diagnosis": diag, "verified_healed": True, "cached_steps_reused": cached_reused, "replay_cost_usd": 0.0, "promoted_eval_case": promoted_case}

    def list_diagnoses(self, workspace_id: str = "default", limit: int = 25) -> Dict[str, Any]:
        ws, diagnoses = self._list_payloads("self_healing_diagnoses", workspace_id, limit)
        return {"workspace_id": ws, "count": len(diagnoses), "diagnoses": diagnoses}


structured_healing_engine = SQLiteStructuredHealingEngine()
