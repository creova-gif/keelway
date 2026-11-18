"""Phase 19A Semantic Prompt Cache, Shadow Dual-Run Router & QLoRA Distillation Flywheel (`core.platform.shadow_distillation`)."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import threading
from typing import Any, Dict, List, Optional, Pattern, Tuple, Union
import uuid

from core.platform.flight_tape import _canonical_json, _sha256_json, _utc_now, scrub_flight_text
from core.platform.kbrain_khub import resolve_kbrain_db_target

VALID_SHADOW_VERDICTS: Tuple[str, ...] = ("CACHE_HIT", "LOCAL_PARITY_READY", "SHADOW_CAPTURED")
VALID_MATCH_TYPES: Tuple[str, ...] = ("exact_sha256", "semantic_shingle", "cache_miss")
VALID_EXPORT_FORMATS: Tuple[str, ...] = ("sft_jsonl", "dpo_preference")
VALID_PROMOTION_VERDICTS: Tuple[str, ...] = ("PROMOTE_TO_OPENCORE", "NEEDS_MORE_PAIRS", "HOLD_ON_FRONTIER")

DEFAULT_SHADOW_PROMPT = "Refactor retry loop with bounded exponential backoff in Python"
DEFAULT_FRONTIER_MODEL = "claude-3-7-sonnet"
DEFAULT_LOCAL_MODEL = "keelway-core:7b"
DEFAULT_CODE_RESPONSE = (
    "def retry_with_backoff(max_attempts: int = 3, base_delay: float = 0.25) -> float: "
    "return min(4.0, base_delay * (2 ** max_attempts))"
)

_ID_SLUG_RE = re.compile(r"^[a-zA-Z0-9_.:-]{1,128}$")
_TOKEN_RE = re.compile(r"[a-z0-9_]+")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
_STRUCT_SYMBOLS: Tuple[str, ...] = ("(", ")", "{", "}", "[", "]", ":", "def ", "return ", "class ", "async ", "=>")

_EXTRA_DLP_PATTERNS: Tuple[Tuple[Pattern[str], str], ...] = (
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----(?:[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----|[^\r\n]*)"), "[REDACTED_SECRET]"),
    (re.compile(r"(?i)(?:-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----|\bBEGIN [A-Z0-9 ]*PRIVATE KEY\b)"), "[REDACTED_SECRET]"),
    (re.compile(r"\bsk-live-[A-Za-z0-9_-]+"), "[REDACTED_SECRET]"),
    (re.compile(r"\bsk-(?:ant-|proj-|test-)?[A-Za-z0-9_-]{4,}"), "[REDACTED_SECRET]"),
    (re.compile(r"\bghp_[A-Za-z0-9]+"), "[REDACTED_SECRET]"),
    (re.compile(r"\bgh[ousr]_[A-Za-z0-9_-]{4,}"), "[REDACTED_SECRET]"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "[REDACTED_SECRET]"),
    (re.compile(r"\b(?:AKIA|ASIA)[A-Za-z0-9_-]{6,}"), "[REDACTED_SECRET]"),
    (re.compile(r"\bBearer\s+(?!\[REDACTED_SECRET\])[A-Za-z0-9._\-~+/]{6,}=*"), "Bearer [REDACTED_SECRET]"),
)

_DISTILL_SCHEMA_SQL = (
    "CREATE TABLE IF NOT EXISTS semantic_prompt_cache (cache_entry_id TEXT NOT NULL, workspace_id TEXT NOT NULL, task_tag TEXT NOT NULL, prompt_sha256 TEXT NOT NULL, shingles_json TEXT NOT NULL, scrubbed_prompt TEXT NOT NULL, cached_response TEXT NOT NULL, frontier_model TEXT NOT NULL, local_model TEXT NOT NULL, parity_score REAL NOT NULL, frontier_cost_usd REAL NOT NULL, latency_saved_per_hit_ms INTEGER NOT NULL, hit_count INTEGER NOT NULL DEFAULT 0, dlp_redactions INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, PRIMARY KEY (workspace_id, cache_entry_id)); "
    "CREATE INDEX IF NOT EXISTS idx_semantic_cache_ws_tag ON semantic_prompt_cache(workspace_id, task_tag, created_at DESC); "
    "CREATE TABLE IF NOT EXISTS semantic_cache_metrics (workspace_id TEXT PRIMARY KEY, total_lookups INTEGER NOT NULL DEFAULT 0, total_hits INTEGER NOT NULL DEFAULT 0, total_cost_saved_usd REAL NOT NULL DEFAULT 0.0, total_latency_saved_ms INTEGER NOT NULL DEFAULT 0, total_dlp_redactions INTEGER NOT NULL DEFAULT 0); "
    "CREATE TABLE IF NOT EXISTS shadow_distill_pairs (pair_id TEXT NOT NULL, workspace_id TEXT NOT NULL, task_tag TEXT NOT NULL, scrubbed_prompt TEXT NOT NULL, scrubbed_frontier_response TEXT NOT NULL, scrubbed_local_response TEXT NOT NULL, frontier_model TEXT NOT NULL, local_model TEXT NOT NULL, parity_score REAL NOT NULL, frontier_cost_usd REAL NOT NULL, dlp_redactions INTEGER NOT NULL DEFAULT 0, pair_sha256 TEXT NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY (workspace_id, pair_id)); "
    "CREATE INDEX IF NOT EXISTS idx_shadow_pairs_ws_tag_created ON shadow_distill_pairs(workspace_id, task_tag, created_at DESC); "
    "CREATE TABLE IF NOT EXISTS qlora_distill_datasets (dataset_id TEXT NOT NULL, workspace_id TEXT NOT NULL, task_tag TEXT NOT NULL, export_format TEXT NOT NULL, target_base_model TEXT NOT NULL, record_count INTEGER NOT NULL, avg_parity_score REAL NOT NULL, lora_rank INTEGER NOT NULL DEFAULT 16, lora_alpha INTEGER NOT NULL DEFAULT 32, dlp_redactions INTEGER NOT NULL DEFAULT 0, jsonl_preview TEXT NOT NULL, dataset_sha256 TEXT NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY (workspace_id, dataset_id)); "
    "CREATE INDEX IF NOT EXISTS idx_qlora_datasets_ws_created ON qlora_distill_datasets(workspace_id, created_at DESC);"
)


class ShadowDistillationValidationError(ValueError):
    """Raised when shadow prompt evaluation, cache lookup, dataset export, or promotion gate parameters are invalid."""


class LocalDLPSanitizer:
    """Deterministic pre-storage secret redactor for prompts, responses, and compiled QLoRA datasets."""

    @staticmethod
    def scrub(text: str) -> Tuple[str, int]:
        current, total = scrub_flight_text(str(text or ""))
        if not current:
            return "", 0
        for pattern, replacement in _EXTRA_DLP_PATTERNS:
            current, count = pattern.subn(replacement, current)
            total += count
        return current, total


def resolve_platform_db_path(db_path: Optional[Union[str, Path]] = None) -> Tuple[Union[str, Path], str]:
    """Resolve explicit or environment-configured SQLite WAL path (`platform_runtime.db`)."""
    eff_override = db_path if db_path is not None else (os.environ.get("KEELWAY_PLATFORM_DB_PATH", "").strip() or None)
    return resolve_kbrain_db_target(eff_override)


def _validate_slug(value: Any, field_name: str, *, allow_empty: bool = False) -> str:
    clean = str(value if value is not None else "").strip()
    if not clean:
        if allow_empty:
            return ""
        raise ShadowDistillationValidationError(f"{field_name} must be non-empty.")
    if ".." in clean or not _ID_SLUG_RE.fullmatch(clean):
        raise ShadowDistillationValidationError(f"Invalid {field_name} '{value}'.")
    return clean


def _validate_limit(limit: Any) -> int:
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise ShadowDistillationValidationError("limit must be a positive integer.")
    return min(limit, 200)


def _validate_unit_float(val: Any, field_name: str, *, min_exclusive: bool = False) -> float:
    if isinstance(val, bool) or not isinstance(val, (int, float)):
        raise ShadowDistillationValidationError(f"{field_name} must be a number between 0.0 and 1.0.")
    fval = float(val)
    if (fval <= 0.0 if min_exclusive else fval < 0.0) or fval > 1.0:
        raise ShadowDistillationValidationError(f"{field_name} must be within {'(0.0, 1.0]' if min_exclusive else '[0.0, 1.0]'}.")
    return fval


def _validate_nonneg_float(val: Any, field_name: str) -> float:
    if isinstance(val, bool) or not isinstance(val, (int, float)) or float(val) < 0.0:
        raise ShadowDistillationValidationError(f"{field_name} must be >= 0.0.")
    return round(float(val), 6)


def _validate_int_min(val: Any, field_name: str, minimum: int = 0) -> int:
    if isinstance(val, bool) or not isinstance(val, int) or val < minimum:
        raise ShadowDistillationValidationError(f"{field_name} must be an integer >= {minimum}.")
    return int(val)


def _compute_shingles(scrubbed_prompt: str) -> List[str]:
    norm = _NON_ALNUM_RE.sub(" ", scrubbed_prompt.lower()).strip()
    if not norm:
        return []
    return [norm] if len(norm) < 3 else sorted({norm[i : i + 3] for i in range(len(norm) - 2)})


def _shingle_jaccard(shingles_a: List[str], shingles_b: List[str]) -> float:
    if not shingles_a or not shingles_b:
        return 0.0
    set_a, set_b = set(shingles_a), set(shingles_b)
    union_len = len(set_a | set_b)
    return (len(set_a & set_b) / union_len) if union_len else 0.0


def _compute_parity_score(scrubbed_frontier: str, scrubbed_local: str) -> float:
    f_clean, l_clean = scrubbed_frontier.strip(), scrubbed_local.strip()
    if not l_clean:
        return 0.0 if f_clean else 1.0
    if not f_clean:
        return 0.0
    if f_clean == l_clean:
        return 1.0
    tokens_f, tokens_l = set(_TOKEN_RE.findall(f_clean.lower())), set(_TOKEN_RE.findall(l_clean.lower()))
    token_union = len(tokens_f | tokens_l)
    token_jaccard = (len(tokens_f & tokens_l) / token_union) if token_union else 0.0
    len_ratio = min(len(f_clean), len(l_clean)) / max(len(f_clean), len(l_clean))
    vec_f, vec_l = [f_clean.count(s) for s in _STRUCT_SYMBOLS], [l_clean.count(s) for s in _STRUCT_SYMBOLS]
    denom = sum(max(a, b) for a, b in zip(vec_f, vec_l))
    struct_score = 1.0 if denom == 0 else (1.0 - (sum(abs(a - b) for a, b in zip(vec_f, vec_l)) / denom))
    return round(max(0.0, min(1.0, (0.55 * token_jaccard) + (0.25 * len_ratio) + (0.20 * struct_score))), 4)


def _row_to_pair(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "pair_id": str(row["pair_id"]), "workspace_id": str(row["workspace_id"]), "task_tag": str(row["task_tag"]),
        "scrubbed_prompt": str(row["scrubbed_prompt"]), "scrubbed_frontier_response": str(row["scrubbed_frontier_response"]),
        "scrubbed_local_response": str(row["scrubbed_local_response"]), "frontier_model": str(row["frontier_model"]),
        "local_model": str(row["local_model"]), "parity_score": float(row["parity_score"]),
        "frontier_cost_usd": float(row["frontier_cost_usd"]), "dlp_redactions": int(row["dlp_redactions"]),
        "pair_sha256": str(row["pair_sha256"]), "created_at": str(row["created_at"]),
    }


def _row_to_dataset(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "dataset_id": str(row["dataset_id"]), "workspace_id": str(row["workspace_id"]), "task_tag": str(row["task_tag"]),
        "export_format": str(row["export_format"]), "target_base_model": str(row["target_base_model"]),
        "record_count": int(row["record_count"]), "avg_parity_score": float(row["avg_parity_score"]),
        "lora_rank": int(row["lora_rank"]), "lora_alpha": int(row["lora_alpha"]),
        "dlp_redactions": int(row["dlp_redactions"]), "jsonl_preview": str(row["jsonl_preview"]),
        "dataset_sha256": str(row["dataset_sha256"]), "created_at": str(row["created_at"]),
    }


class SQLiteShadowDistillationEngine:
    """Thread-safe SQLite WAL engine for Semantic Prompt Cache, Shadow Dual-Run & QLoRA Distillation."""

    def __init__(self, db_path: Optional[Union[str, Path]] = None) -> None:
        self._lock, self._explicit_db_path, self._conn, self._active_target = threading.RLock(), db_path, None, None
        self._db_path: Union[str, Path] = ":memory:"
        self._closed = False
        with self._lock:
            self._ensure_conn()

    def _ensure_conn(self) -> sqlite3.Connection:
        resolved_path, connect_target = resolve_platform_db_path(self._explicit_db_path)
        if self._conn is not None and not self._closed and self._active_target == connect_target:
            return self._conn
        if self._conn is not None and not self._closed:
            self._conn.close()
        conn = sqlite3.connect(connect_target, check_same_thread=False, timeout=30.0)
        conn.row_factory = sqlite3.Row
        for pragma in ("PRAGMA journal_mode=WAL", "PRAGMA synchronous=NORMAL", "PRAGMA foreign_keys=ON"):
            conn.execute(pragma)
        with conn:
            conn.executescript(_DISTILL_SCHEMA_SQL)
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

    def evaluate_shadow_prompt(
        self, workspace_id: str = "default", task_tag: str = "code-patch", prompt: str = DEFAULT_SHADOW_PROMPT,
        frontier_model: str = DEFAULT_FRONTIER_MODEL, local_model: str = DEFAULT_LOCAL_MODEL,
        frontier_response: str = DEFAULT_CODE_RESPONSE, local_response: str = DEFAULT_CODE_RESPONSE,
        frontier_cost_usd: float = 0.018, frontier_latency_ms: int = 840, local_latency_ms: int = 95,
        similarity_threshold: float = 0.82, bypass_cache: bool = False,
    ) -> Dict[str, Any]:
        ws = _validate_slug(workspace_id, "workspace_id")
        clean_tag = _validate_slug("code-patch" if task_tag is None or not str(task_tag).strip() else str(task_tag), "task_tag")
        raw_prompt, raw_frontier = str(prompt if prompt is not None else "").strip(), str(frontier_response if frontier_response is not None else "").strip()
        if not raw_prompt or not raw_frontier:
            raise ShadowDistillationValidationError("prompt and frontier_response must be non-empty.")
        raw_local = str(local_response if local_response is not None else "")
        clean_fcost, clean_flat = _validate_nonneg_float(frontier_cost_usd, "frontier_cost_usd"), _validate_int_min(frontier_latency_ms, "frontier_latency_ms", 0)
        _validate_int_min(local_latency_ms, "local_latency_ms", 0)
        clean_thresh = _validate_unit_float(similarity_threshold, "similarity_threshold", min_exclusive=True)

        scrubbed_prompt, r_p = LocalDLPSanitizer.scrub(raw_prompt)
        scrubbed_frontier, r_f = LocalDLPSanitizer.scrub(raw_frontier)
        scrubbed_local, r_l = LocalDLPSanitizer.scrub(raw_local)
        clean_fmodel, r_fm = LocalDLPSanitizer.scrub(str(frontier_model or DEFAULT_FRONTIER_MODEL).strip() or DEFAULT_FRONTIER_MODEL)
        clean_lmodel, r_lm = LocalDLPSanitizer.scrub(str(local_model or DEFAULT_LOCAL_MODEL).strip() or DEFAULT_LOCAL_MODEL)
        dlp_redactions = r_p + r_f + r_l + r_fm + r_lm

        prompt_sha256 = "sha256:" + hashlib.sha256(" ".join(scrubbed_prompt.strip().split()).encode("utf-8")).hexdigest()
        shingles, now_iso, evaluation_id = _compute_shingles(scrubbed_prompt), _utc_now(), f"seval-{uuid.uuid4().hex[:12]}"

        with self._lock:
            conn = self._ensure_conn()
            with conn:
                conn.execute("INSERT INTO semantic_cache_metrics (workspace_id, total_lookups, total_dlp_redactions) VALUES (?, 1, ?) ON CONFLICT(workspace_id) DO UPDATE SET total_lookups = total_lookups + 1, total_dlp_redactions = total_dlp_redactions + excluded.total_dlp_redactions", (ws, dlp_redactions))
                matched_row, match_type, sim_score = self._find_cache_hit(conn, ws, clean_tag, prompt_sha256, shingles, clean_thresh, bool(bypass_cache))
                if matched_row is not None:
                    cache_id, entry_cost = str(matched_row["cache_entry_id"]), float(matched_row["frontier_cost_usd"])
                    saved_cost, saved_lat = round(entry_cost if entry_cost > 0.0 else clean_fcost, 6), max(1, clean_flat)
                    conn.execute("UPDATE semantic_prompt_cache SET hit_count = hit_count + 1 WHERE workspace_id=? AND cache_entry_id=?", (ws, cache_id))
                    conn.execute("UPDATE semantic_cache_metrics SET total_hits = total_hits + 1, total_cost_saved_usd = ROUND(total_cost_saved_usd + ?, 6), total_latency_saved_ms = total_latency_saved_ms + ? WHERE workspace_id=?", (saved_cost, saved_lat, ws))
                    return self._build_eval_record(evaluation_id, None, cache_id, ws, clean_tag, "CACHE_HIT", match_type, sim_score, float(matched_row["parity_score"]), str(matched_row["frontier_model"]), str(matched_row["local_model"]), scrubbed_prompt, str(matched_row["cached_response"]), saved_cost, saved_lat, dlp_redactions, now_iso)

                parity_score = _compute_parity_score(scrubbed_frontier, scrubbed_local)
                verdict, cache_id, pair_id = ("LOCAL_PARITY_READY" if parity_score >= 0.85 else "SHADOW_CAPTURED"), f"scache-{uuid.uuid4().hex[:12]}", f"spair-{uuid.uuid4().hex[:12]}"
                conn.execute("INSERT INTO semantic_prompt_cache VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)", (cache_id, ws, clean_tag, prompt_sha256, _canonical_json(shingles), scrubbed_prompt, scrubbed_frontier, clean_fmodel, clean_lmodel, parity_score, clean_fcost, max(1, clean_flat), dlp_redactions, now_iso))
                pair_sha = _sha256_json({"pair_id": pair_id, "workspace_id": ws, "task_tag": clean_tag, "scrubbed_prompt": scrubbed_prompt, "scrubbed_frontier_response": scrubbed_frontier, "scrubbed_local_response": scrubbed_local, "frontier_model": clean_fmodel, "local_model": clean_lmodel, "parity_score": parity_score, "frontier_cost_usd": clean_fcost, "dlp_redactions": dlp_redactions, "created_at": now_iso})
                conn.execute("INSERT INTO shadow_distill_pairs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (pair_id, ws, clean_tag, scrubbed_prompt, scrubbed_frontier, scrubbed_local, clean_fmodel, clean_lmodel, parity_score, clean_fcost, dlp_redactions, pair_sha, now_iso))
                return self._build_eval_record(evaluation_id, pair_id, cache_id, ws, clean_tag, verdict, "cache_miss", sim_score, parity_score, clean_fmodel, clean_lmodel, scrubbed_prompt, scrubbed_frontier, 0.0, 0, dlp_redactions, now_iso)

    @staticmethod
    def _find_cache_hit(
        conn: sqlite3.Connection, ws: str, task_tag: str, prompt_sha256: str, shingles: List[str], threshold: float, bypass_cache: bool
    ) -> Tuple[Optional[sqlite3.Row], str, float]:
        if bypass_cache:
            return None, "cache_miss", 0.0
        rows = conn.execute(
            "SELECT * FROM semantic_prompt_cache WHERE workspace_id=? AND task_tag=? ORDER BY created_at DESC, rowid DESC", (ws, task_tag)
        ).fetchall()
        for row in rows:
            if str(row["prompt_sha256"]) == prompt_sha256:
                return row, "exact_sha256", 1.0
        best_row, best_sim = None, 0.0
        for row in rows:
            sim = _shingle_jaccard(shingles, json.loads(str(row["shingles_json"])))
            if sim > best_sim:
                best_sim, best_row = sim, row
        if best_row is not None and best_sim >= threshold:
            return best_row, "semantic_shingle", round(best_sim, 4)
        return None, "cache_miss", round(best_sim, 4)

    @staticmethod
    def _build_eval_record(
        evaluation_id: str, pair_id: Optional[str], cache_entry_id: str, ws: str, task_tag: str, verdict: str, match_type: str,
        similarity_score: float, parity_score: float, frontier_model: str, local_model: str, scrubbed_prompt: str,
        cached_response: str, cost_saved_usd: float, latency_saved_ms: int, dlp_redactions: int, created_at: str,
    ) -> Dict[str, Any]:
        base = {
            "evaluation_id": evaluation_id, "pair_id": pair_id, "cache_entry_id": cache_entry_id, "workspace_id": ws,
            "task_tag": task_tag, "verdict": verdict, "match_type": match_type, "similarity_score": similarity_score,
            "parity_score": parity_score, "frontier_model": frontier_model, "local_model": local_model,
            "scrubbed_prompt": scrubbed_prompt, "cached_response": cached_response, "cost_saved_usd": cost_saved_usd,
            "latency_saved_ms": latency_saved_ms, "dlp_redactions": dlp_redactions, "created_at": created_at,
        }
        return {**base, "event_sha256": _sha256_json(base)}

    def list_shadow_pairs(self, workspace_id: str = "default", task_tag: str = "", limit: int = 25) -> Dict[str, Any]:
        ws, clean_tag, cap = _validate_slug(workspace_id, "workspace_id"), _validate_slug(task_tag, "task_tag", allow_empty=True), _validate_limit(limit)
        with self._lock:
            conn = self._ensure_conn()
            rows = (
                conn.execute("SELECT * FROM shadow_distill_pairs WHERE workspace_id=? AND task_tag=? ORDER BY created_at DESC, rowid DESC LIMIT ?", (ws, clean_tag, cap)).fetchall()
                if clean_tag
                else conn.execute("SELECT * FROM shadow_distill_pairs WHERE workspace_id=? ORDER BY created_at DESC, rowid DESC LIMIT ?", (ws, cap)).fetchall()
            )
        pairs = [_row_to_pair(r) for r in rows]
        return {"workspace_id": ws, "count": len(pairs), "pairs": pairs}

    def get_cache_stats(self, workspace_id: str = "default") -> Dict[str, Any]:
        ws = _validate_slug(workspace_id, "workspace_id")
        with self._lock:
            conn = self._ensure_conn()
            entry_count = int(conn.execute("SELECT COUNT(*) AS cnt FROM semantic_prompt_cache WHERE workspace_id=?", (ws,)).fetchone()["cnt"])
            mrow = conn.execute("SELECT * FROM semantic_cache_metrics WHERE workspace_id=?", (ws,)).fetchone()
        lookups = int(mrow["total_lookups"]) if mrow is not None else 0
        hits = int(mrow["total_hits"]) if mrow is not None else 0
        return {
            "workspace_id": ws, "entry_count": entry_count, "total_hits": hits, "total_lookups": lookups,
            "hit_rate": round(hits / lookups, 4) if lookups > 0 else 0.0,
            "total_cost_saved_usd": round(float(mrow["total_cost_saved_usd"]), 6) if mrow is not None else 0.0,
            "total_latency_saved_ms": int(mrow["total_latency_saved_ms"]) if mrow is not None else 0,
            "total_dlp_redactions": int(mrow["total_dlp_redactions"]) if mrow is not None else 0,
        }

    def compile_distillation_dataset(
        self, workspace_id: str = "default", task_tag: str = "", export_format: str = "dpo_preference",
        target_base_model: str = DEFAULT_LOCAL_MODEL, min_parity_score: float = 0.0,
    ) -> Dict[str, Any]:
        ws, clean_tag = _validate_slug(workspace_id, "workspace_id"), _validate_slug(task_tag, "task_tag", allow_empty=True)
        clean_fmt = str(export_format or "").strip()
        if clean_fmt not in VALID_EXPORT_FORMATS:
            raise ShadowDistillationValidationError(f"Unsupported export_format '{export_format}'. Expected {list(VALID_EXPORT_FORMATS)}.")
        min_parity = _validate_unit_float(min_parity_score, "min_parity_score")
        clean_base, r_bm = LocalDLPSanitizer.scrub(str(target_base_model or DEFAULT_LOCAL_MODEL).strip() or DEFAULT_LOCAL_MODEL)

        with self._lock:
            conn = self._ensure_conn()
            rows = (
                conn.execute("SELECT * FROM shadow_distill_pairs WHERE workspace_id=? AND task_tag=? AND parity_score>=? ORDER BY created_at DESC, rowid DESC", (ws, clean_tag, min_parity)).fetchall()
                if clean_tag
                else conn.execute("SELECT * FROM shadow_distill_pairs WHERE workspace_id=? AND parity_score>=? ORDER BY created_at DESC, rowid DESC", (ws, min_parity)).fetchall()
            )
            lines, total_redactions = [], r_bm
            for r in rows:
                p_txt, rp = LocalDLPSanitizer.scrub(str(r["scrubbed_prompt"]))
                f_txt, rf = LocalDLPSanitizer.scrub(str(r["scrubbed_frontier_response"]))
                l_txt, rl = LocalDLPSanitizer.scrub(str(r["scrubbed_local_response"]))
                total_redactions += int(r["dlp_redactions"]) + rp + rf + rl
                item = {"prompt": p_txt, "completion": f_txt} if clean_fmt == "sft_jsonl" else {"prompt": p_txt, "chosen": f_txt, "rejected": l_txt}
                lines.append(json.dumps(item, ensure_ascii=False))

            rec_count = len(rows)
            avg_parity = round(sum(float(r["parity_score"]) for r in rows) / rec_count, 4) if rec_count > 0 else 0.0
            jsonl_preview, dataset_id, created_at = "\n".join(lines[:3]), f"qds-{uuid.uuid4().hex[:12]}", _utc_now()
            lora_rank, lora_alpha = 16, 32
            dataset_sha = _sha256_json({
                "dataset_id": dataset_id, "workspace_id": ws, "task_tag": clean_tag, "export_format": clean_fmt,
                "target_base_model": clean_base, "record_count": rec_count, "lora_rank": lora_rank, "lora_alpha": lora_alpha, "lines": lines,
            })
            with conn:
                conn.execute(
                    "INSERT INTO qlora_distill_datasets VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (dataset_id, ws, clean_tag, clean_fmt, clean_base, rec_count, avg_parity, lora_rank, lora_alpha, total_redactions, jsonl_preview, dataset_sha, created_at),
                )
        return {
            "dataset_id": dataset_id, "workspace_id": ws, "task_tag": clean_tag, "export_format": clean_fmt,
            "target_base_model": clean_base, "record_count": rec_count, "avg_parity_score": avg_parity,
            "lora_rank": lora_rank, "lora_alpha": lora_alpha, "dlp_redactions": total_redactions,
            "jsonl_preview": jsonl_preview, "dataset_sha256": dataset_sha, "created_at": created_at,
        }

    def list_distillation_datasets(self, workspace_id: str = "default", limit: int = 25) -> Dict[str, Any]:
        ws, cap = _validate_slug(workspace_id, "workspace_id"), _validate_limit(limit)
        with self._lock:
            rows = self._ensure_conn().execute(
                "SELECT * FROM qlora_distill_datasets WHERE workspace_id=? ORDER BY created_at DESC, rowid DESC LIMIT ?", (ws, cap)
            ).fetchall()
        datasets = [_row_to_dataset(r) for r in rows]
        return {"workspace_id": ws, "count": len(datasets), "datasets": datasets}

    def evaluate_promotion_gate(
        self, workspace_id: str = "default", task_tag: str = "code-patch", target_local_model: str = DEFAULT_LOCAL_MODEL,
        min_pairs: int = 3, min_avg_parity: float = 0.85, monthly_request_volume: int = 50000,
    ) -> Dict[str, Any]:
        ws = _validate_slug(workspace_id, "workspace_id")
        clean_tag = _validate_slug("code-patch" if task_tag is None else task_tag, "task_tag", allow_empty=True)
        clean_model, _ = LocalDLPSanitizer.scrub(str(target_local_model or DEFAULT_LOCAL_MODEL).strip() or DEFAULT_LOCAL_MODEL)
        req_pairs, req_parity, req_volume = _validate_int_min(min_pairs, "min_pairs", 1), _validate_unit_float(min_avg_parity, "min_avg_parity"), _validate_int_min(monthly_request_volume, "monthly_request_volume", 0)

        with self._lock:
            conn = self._ensure_conn()
            rows = (
                conn.execute("SELECT parity_score, frontier_cost_usd FROM shadow_distill_pairs WHERE workspace_id=? AND task_tag=?", (ws, clean_tag)).fetchall()
                if clean_tag
                else conn.execute("SELECT parity_score, frontier_cost_usd FROM shadow_distill_pairs WHERE workspace_id=?", (ws,)).fetchall()
            )
        pair_count = len(rows)
        avg_parity = round(sum(float(r["parity_score"]) for r in rows) / pair_count, 4) if pair_count > 0 else 0.0
        avg_cost = round(sum(float(r["frontier_cost_usd"]) for r in rows) / pair_count, 6) if pair_count > 0 else 0.0
        scope_label = clean_tag or "all-tasks"

        if pair_count < req_pairs:
            verdict, savings = "NEEDS_MORE_PAIRS", 0.0
            rec = f"Capture {req_pairs - pair_count} more shadow pair(s) for '{scope_label}' before promoting {clean_model}."
        elif avg_parity < req_parity:
            verdict, savings = "HOLD_ON_FRONTIER", 0.0
            rec = f"Hold '{scope_label}' on Frontier BYOM: avg parity {avg_parity:.4f} < {req_parity:.4f}. Compile a DPO QLoRA dataset for {clean_model}."
        else:
            verdict, savings = "PROMOTE_TO_OPENCORE", round(avg_cost * req_volume, 2)
            rec = f"Promote '{scope_label}' to OpenCore ({clean_model}): parity {avg_parity:.4f} >= {req_parity:.4f} across {pair_count} pairs (~${savings:,.2f}/mo saved)."

        eval_id, evaluated_at = f"dgate-{uuid.uuid4().hex[:12]}", _utc_now()
        base = {
            "evaluation_id": eval_id, "workspace_id": ws, "task_tag": clean_tag, "target_local_model": clean_model,
            "verdict": verdict, "pair_count": pair_count, "min_pairs": req_pairs, "avg_parity_score": avg_parity,
            "min_avg_parity": req_parity, "avg_frontier_cost_usd": avg_cost, "monthly_request_volume": req_volume,
            "projected_monthly_savings_usd": savings, "recommendation": rec, "evaluated_at": evaluated_at,
        }
        return {**base, "gate_sha256": _sha256_json(base)}


shadow_distillation_engine = SQLiteShadowDistillationEngine()
