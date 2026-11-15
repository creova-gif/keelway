"""
KFlow Topological DAG Execution Engine & KSpaces LWW-Element-Set CRDT Sync (`core.platform.kflow_crdt`).

Persists deterministic multi-wave DAG workflow executions (`platform_kflow_runs`) with P-10 human
governance gates, chained SHA-256 data-flow digests, and token-budget enforcement alongside
commutative/associative/idempotent Lamport + Peer-ID CRDT state (`platform_crdt_entries`) with
pre-storage DLP secret scrubbing in crash-safe SQLite WAL mode.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import threading
from typing import Any, Dict, List, Optional, Set, Tuple, Union
import uuid

from core.platform.mcp_registry import redact_sensitive_text
from core.platform.vault import _resolve_sqlite_target
from core.security.redact import redact_payload

_SHORT_OPENAI_KEY_RE = re.compile(r"\bsk-(?:proj-|live-|test-)?[A-Za-z0-9_-]{12,}")


class KFlowCycleError(ValueError):
    """Raised when a KFlow workflow graph contains a cycle or an unknown upstream dependency."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _scrub_crdt_strings(obj: Any) -> Any:
    if isinstance(obj, str):
        clean, _ = redact_sensitive_text(obj)
        for match in reversed(list(_SHORT_OPENAI_KEY_RE.finditer(clean))):
            s_idx, e_idx = match.span()
            if not clean[s_idx:e_idx].startswith("[REDACTED"):
                clean = clean[:s_idx] + "[REDACTED_OPENAI_KEY]" + clean[e_idx:]
        return clean
    if isinstance(obj, dict):
        return {str(k): _scrub_crdt_strings(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_scrub_crdt_strings(v) for v in obj]
    return obj


def scrub_crdt_value(value: Any) -> Tuple[Any, str]:
    """Scrub secrets via `redact_payload` + `redact_sensitive_text` before CRDT storage."""
    redacted_obj, _ = redact_payload(value)
    scrubbed_obj = _scrub_crdt_strings(redacted_obj)
    try:
        encoded = json.dumps(scrubbed_obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"CRDT operation 'value' must be JSON-serializable: {exc}") from exc
    return json.loads(encoded), encoded


class KFlowDagEngine:
    """Topological Kahn-wave DAG workflow executor backed by SQLite WAL."""

    def __init__(self, db_path: Optional[Union[str, Path]] = None) -> None:
        self._lock = threading.Lock()
        self._db_path, connect_target = _resolve_sqlite_target(db_path)
        self._conn = sqlite3.connect(connect_target, check_same_thread=False, timeout=30.0)
        self._conn.row_factory = sqlite3.Row
        self._closed = False
        with self._lock:
            mode_row = self._conn.execute("PRAGMA journal_mode=WAL").fetchone()
            self._journal_mode = str(mode_row[0]).lower() if mode_row else "unknown"
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            with self._conn:
                self._conn.executescript(
                    "CREATE TABLE IF NOT EXISTS platform_kflow_runs ("
                    "run_id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, workflow_id TEXT NOT NULL, "
                    "status TEXT NOT NULL, payload_json TEXT NOT NULL, created_at TEXT NOT NULL); "
                    "CREATE INDEX IF NOT EXISTS idx_platform_kflow_runs_ws "
                    "ON platform_kflow_runs(workspace_id, workflow_id);"
                )

    @property
    def db_path(self) -> Union[str, Path]:
        return self._db_path

    @property
    def journal_mode(self) -> str:
        return self._journal_mode

    def close(self) -> None:
        with self._lock:
            if not self._closed:
                self._conn.close()
                self._closed = True

    @staticmethod
    def _normalize_nodes(raw_nodes: List[Dict[str, Any]]) -> Tuple[List[str], Dict[str, Dict[str, Any]]]:
        if not isinstance(raw_nodes, list) or len(raw_nodes) < 1:
            raise ValueError("KFlow 'nodes' must be a non-empty list of DAG nodes.")
        order: List[str] = []
        by_id: Dict[str, Dict[str, Any]] = {}
        for idx, raw in enumerate(raw_nodes):
            if not isinstance(raw, dict):
                raise ValueError(f"KFlow node at index {idx} must be an object.")
            nid = str(raw.get("id") or "").strip()
            if not nid:
                raise ValueError(f"KFlow node at index {idx} must have a non-empty 'id'.")
            if nid in by_id:
                raise ValueError(f"Duplicate KFlow node id '{nid}'.")
            label = str(raw.get("label") or raw.get("name") or nid).strip() or nid
            agent_id = (
                str(raw.get("agent_id") or raw.get("agentId") or raw.get("agent") or "workflow-orchestrator").strip()
                or "workflow-orchestrator"
            )
            raw_deps = raw.get("depends_on") if "depends_on" in raw else raw.get("dependsOn", [])
            if raw_deps is None:
                raw_deps = []
            if not isinstance(raw_deps, (list, tuple)):
                raise ValueError(f"KFlow node '{nid}' 'depends_on' must be a list of node ids.")
            deps: List[str] = []
            seen_deps: Set[str] = set()
            for dep_item in raw_deps:
                dep_id = str(dep_item or "").strip()
                if not dep_id:
                    raise ValueError(f"KFlow node '{nid}' contains an empty dependency id.")
                if dep_id not in seen_deps:
                    deps.append(dep_id)
                    seen_deps.add(dep_id)
            req_p10_raw = raw.get("requires_p10") if "requires_p10" in raw else raw.get("requiresP10", False)
            order.append(nid)
            by_id[nid] = {
                "id": nid, "label": label, "agent_id": agent_id,
                "depends_on": deps, "requires_p10": bool(req_p10_raw),
            }

        for nid in order:
            for dep in by_id[nid]["depends_on"]:
                if dep not in by_id:
                    raise KFlowCycleError(f"Unknown upstream node dependency '{dep}'")
        return order, by_id

    @staticmethod
    def _kahn_waves(
        order: List[str], by_id: Dict[str, Dict[str, Any]]
    ) -> Tuple[List[List[str]], List[str], Dict[str, int]]:
        in_degree: Dict[str, int] = {nid: len(by_id[nid]["depends_on"]) for nid in order}
        dependents: Dict[str, List[str]] = {nid: [] for nid in order}
        for nid in order:
            for dep in by_id[nid]["depends_on"]:
                dependents[dep].append(nid)

        waves: List[List[str]] = []
        topo: List[str] = []
        node_wave: Dict[str, int] = {}
        current_wave = [nid for nid in order if in_degree[nid] == 0]
        while current_wave:
            wave_idx = len(waves)
            waves.append(current_wave)
            for nid in current_wave:
                topo.append(nid)
                node_wave[nid] = wave_idx
                for child in dependents[nid]:
                    in_degree[child] -= 1
            next_set = {child for nid in current_wave for child in dependents[nid] if in_degree[child] == 0}
            current_wave = [nid for nid in order if nid in next_set]

        if len(topo) < len(order):
            raise KFlowCycleError("Cycle detected in KFlow DAG")
        return waves, topo, node_wave

    def execute_dag(
        self,
        workspace_id: str,
        workflow_id: str,
        nodes: List[Dict[str, Any]],
        trigger: str = "manual",
        token_budget: int = 25000,
        approved_node_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        ws = str(workspace_id or "").strip()
        wf = str(workflow_id or "").strip()
        clean_trigger = str(trigger or "manual").strip() or "manual"
        if not ws:
            raise ValueError("KFlow 'workspace_id' must be non-empty.")
        if not wf:
            raise ValueError("KFlow 'workflow_id' must be non-empty.")
        if isinstance(token_budget, bool) or not isinstance(token_budget, int) or token_budget < 0:
            raise ValueError("KFlow 'token_budget' must be a non-negative integer.")

        order, by_id = self._normalize_nodes(nodes)
        waves, topological_order, node_wave = self._kahn_waves(order, by_id)
        approved_set = {str(x).strip() for x in (approved_node_ids or []) if str(x).strip()}

        tokens_used = 0
        held_node_id: Optional[str] = None
        final_status = "completed"
        results_by_id: Dict[str, Dict[str, Any]] = {}

        def _up_digests(spec_obj: Dict[str, Any]) -> List[str]:
            return [
                str(results_by_id[d]["output_digest"])
                for d in spec_obj["depends_on"]
                if d in results_by_id and results_by_id[d].get("output_digest")
            ]

        def _mark_unvisited(rem_ids: List[str], rem_status: str) -> None:
            for rem_id in rem_ids:
                rem_spec = by_id[rem_id]
                results_by_id[rem_id] = {
                    **rem_spec, "wave": node_wave[rem_id], "status": rem_status,
                    "tokens": 0, "upstream_digests": _up_digests(rem_spec),
                    "output_digest": None, "error_detail": None,
                }

        for idx, nid in enumerate(topological_order):
            spec = by_id[nid]
            wave_idx = node_wave[nid]
            upstream_digests = _up_digests(spec)
            step_tokens = max(120, len(spec["label"]) * 12)

            if token_budget > 0 and (tokens_used + step_tokens > token_budget):
                results_by_id[nid] = {
                    **spec, "wave": wave_idx, "status": "failed", "tokens": 0,
                    "upstream_digests": upstream_digests, "output_digest": None,
                    "error_detail": "Token budget exceeded",
                }
                _mark_unvisited(topological_order[idx + 1 :], "blocked")
                final_status = "failed"
                break

            if spec["requires_p10"] and nid not in approved_set:
                held_node_id = nid
                final_status = "awaiting_p10"
                results_by_id[nid] = {
                    **spec, "wave": wave_idx, "status": "awaiting_p10", "tokens": 0,
                    "upstream_digests": upstream_digests, "output_digest": None, "error_detail": None,
                }
                _mark_unvisited(topological_order[idx + 1 :], "pending")
                break

            tokens_used += step_tokens
            digest_material = _canonical_json({
                "agent_id": spec["agent_id"], "label": spec["label"], "node_id": nid,
                "upstream_digests": upstream_digests, "wave": wave_idx, "workflow_id": wf,
            })
            output_digest = "sha256:" + hashlib.sha256(digest_material.encode("utf-8")).hexdigest()
            results_by_id[nid] = {
                **spec, "wave": wave_idx, "status": "passed", "tokens": step_tokens,
                "upstream_digests": upstream_digests, "output_digest": output_digest, "error_detail": None,
            }

        run_id = f"kflow-{uuid.uuid4().hex[:12]}"
        created_at = _utc_now()
        ordered_nodes = [results_by_id[nid] for nid in topological_order]
        unsigned_payload: Dict[str, Any] = {
            "run_id": run_id, "workspace_id": ws, "workflow_id": wf, "trigger": clean_trigger,
            "status": final_status, "held_node_id": held_node_id, "topological_order": topological_order,
            "waves": waves, "tokens_used": tokens_used, "token_budget": token_budget,
            "nodes": ordered_nodes, "created_at": created_at,
        }
        receipt_sha256 = "sha256:" + hashlib.sha256(_canonical_json(unsigned_payload).encode("utf-8")).hexdigest()
        payload: Dict[str, Any] = {**unsigned_payload, "receipt_sha256": receipt_sha256}

        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO platform_kflow_runs (run_id, workspace_id, workflow_id, status, payload_json, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (run_id, ws, wf, final_status, _canonical_json(payload), created_at),
            )
        return payload

    def list_runs(
        self, workspace_id: str = "default", workflow_id: Optional[str] = None, limit: int = 25
    ) -> Dict[str, Any]:
        ws = str(workspace_id or "default").strip()
        if not ws:
            raise ValueError("KFlow 'workspace_id' must be non-empty.")
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1 or limit > 500:
            raise ValueError("KFlow 'limit' must be an integer between 1 and 500.")
        clean_wf = str(workflow_id).strip() if workflow_id is not None and str(workflow_id).strip() else None
        with self._lock:
            if clean_wf is not None:
                rows = self._conn.execute(
                    "SELECT payload_json FROM platform_kflow_runs WHERE workspace_id=? AND workflow_id=? "
                    "ORDER BY created_at DESC, rowid DESC LIMIT ?",
                    (ws, clean_wf, limit),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT payload_json FROM platform_kflow_runs WHERE workspace_id=? "
                    "ORDER BY created_at DESC, rowid DESC LIMIT ?",
                    (ws, limit),
                ).fetchall()
        runs = [json.loads(str(r["payload_json"])) for r in rows]
        return {"workspace_id": ws, "count": len(runs), "runs": runs}


class KSpacesCrdtEngine:
    """Deterministic Lamport + Peer-ID LWW-Element-Set CRDT engine backed by SQLite WAL."""

    def __init__(self, db_path: Optional[Union[str, Path]] = None) -> None:
        self._lock = threading.Lock()
        self._db_path, connect_target = _resolve_sqlite_target(db_path)
        self._conn = sqlite3.connect(connect_target, check_same_thread=False, timeout=30.0)
        self._conn.row_factory = sqlite3.Row
        self._closed = False
        with self._lock:
            mode_row = self._conn.execute("PRAGMA journal_mode=WAL").fetchone()
            self._journal_mode = str(mode_row[0]).lower() if mode_row else "unknown"
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            with self._conn:
                self._conn.executescript(
                    "CREATE TABLE IF NOT EXISTS platform_crdt_entries ("
                    "workspace_id TEXT NOT NULL, namespace TEXT NOT NULL, entry_key TEXT NOT NULL, "
                    "value_json TEXT, lamport_ts INTEGER NOT NULL, peer_id TEXT NOT NULL, "
                    "tombstone INTEGER NOT NULL, updated_at TEXT NOT NULL, "
                    "PRIMARY KEY (workspace_id, namespace, entry_key)); "
                    "CREATE INDEX IF NOT EXISTS idx_platform_crdt_ws "
                    "ON platform_crdt_entries(workspace_id, namespace);"
                )

    @property
    def db_path(self) -> Union[str, Path]:
        return self._db_path

    @property
    def journal_mode(self) -> str:
        return self._journal_mode

    def close(self) -> None:
        with self._lock:
            if not self._closed:
                self._conn.close()
                self._closed = True

    def apply_ops(self, workspace_id: str, peer_id: str, operations: List[Dict[str, Any]]) -> Dict[str, Any]:
        ws = str(workspace_id or "").strip()
        clean_peer = str(peer_id or "").strip()
        if not ws:
            raise ValueError("KSpaces CRDT 'workspace_id' must be non-empty.")
        if not clean_peer:
            raise ValueError("KSpaces CRDT 'peer_id' must be non-empty.")
        if not isinstance(operations, list):
            raise ValueError("KSpaces CRDT 'operations' must be a list of operation objects.")

        normalized_ops: List[Tuple[str, str, bool, str, Optional[int]]] = []
        for idx, raw in enumerate(operations):
            if not isinstance(raw, dict):
                raise ValueError(f"CRDT operation at index {idx} must be an object.")
            ns = str(raw.get("namespace") or "workspace").strip() or "workspace"
            key = str(raw.get("key") if raw.get("key") is not None else (raw.get("entry_key") or "")).strip()
            if not key:
                raise ValueError(f"CRDT operation at index {idx} requires a non-empty 'key'.")
            op_kind = str(raw.get("op") or "set").strip().lower()
            if op_kind not in {"set", "remove"}:
                raise ValueError(f"Unsupported CRDT op '{op_kind}'; expected 'set' or 'remove'.")
            raw_ts = raw.get("lamport_ts")
            if raw_ts is not None:
                if isinstance(raw_ts, bool) or not isinstance(raw_ts, int):
                    raise ValueError(f"CRDT operation at index {idx} 'lamport_ts' must be an integer.")
                parsed_ts: Optional[int] = raw_ts if raw_ts > 0 else None
            else:
                parsed_ts = None

            is_tomb = op_kind == "remove"
            inc_val_json = "null" if is_tomb else scrub_crdt_value(raw.get("value"))[1]
            normalized_ops.append((ns, key, is_tomb, inc_val_json, parsed_ts))

        applied_count = 0
        now = _utc_now()
        with self._lock, self._conn:
            max_row = self._conn.execute(
                "SELECT COALESCE(MAX(lamport_ts), 0) AS max_ts FROM platform_crdt_entries WHERE workspace_id=?",
                (ws,),
            ).fetchone()
            current_max_lamport = int(max_row["max_ts"]) if max_row is not None else 0

            for ns, key, inc_tombstone, inc_val_json, explicit_ts in normalized_ops:
                inc_ts = (current_max_lamport + 1) if explicit_ts is None else explicit_ts
                if inc_ts > current_max_lamport:
                    current_max_lamport = inc_ts

                existing = self._conn.execute(
                    "SELECT value_json, lamport_ts, peer_id, tombstone "
                    "FROM platform_crdt_entries WHERE workspace_id=? AND namespace=? AND entry_key=?",
                    (ws, ns, key),
                ).fetchone()

                inc_tomb_int = 1 if inc_tombstone else 0
                if existing is None:
                    self._conn.execute(
                        "INSERT INTO platform_crdt_entries "
                        "(workspace_id, namespace, entry_key, value_json, lamport_ts, peer_id, tombstone, updated_at) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (ws, ns, key, inc_val_json, inc_ts, clean_peer, inc_tomb_int, now),
                    )
                    applied_count += 1
                else:
                    cur_tuple = (
                        int(existing["lamport_ts"]),
                        str(existing["peer_id"]),
                        1 if int(existing["tombstone"]) else 0,
                        str(existing["value_json"] if existing["value_json"] is not None else "null"),
                    )
                    if (inc_ts, clean_peer, inc_tomb_int, inc_val_json) > cur_tuple:
                        self._conn.execute(
                            "UPDATE platform_crdt_entries "
                            "SET value_json=?, lamport_ts=?, peer_id=?, tombstone=?, updated_at=? "
                            "WHERE workspace_id=? AND namespace=? AND entry_key=?",
                            (inc_val_json, inc_ts, clean_peer, inc_tomb_int, now, ws, ns, key),
                        )
                        applied_count += 1

        return {**self.get_state(workspace_id=ws), "peer_id": clean_peer, "applied_count": applied_count}

    def get_state(self, workspace_id: str = "default", namespace: Optional[str] = None) -> Dict[str, Any]:
        ws = str(workspace_id or "default").strip()
        if not ws:
            raise ValueError("KSpaces CRDT 'workspace_id' must be non-empty.")
        clean_ns = str(namespace).strip() if namespace is not None and str(namespace).strip() else None

        with self._lock:
            vc_rows = self._conn.execute(
                "SELECT peer_id, MAX(lamport_ts) AS max_ts FROM platform_crdt_entries "
                "WHERE workspace_id=? GROUP BY peer_id ORDER BY peer_id ASC",
                (ws,),
            ).fetchall()
            sql = (
                "SELECT namespace, entry_key, value_json, lamport_ts, peer_id, tombstone "
                "FROM platform_crdt_entries WHERE workspace_id=?"
            )
            params: Tuple[Any, ...] = (ws, clean_ns) if clean_ns is not None else (ws,)
            entry_rows = self._conn.execute(
                sql + (" AND namespace=?" if clean_ns is not None else "") + " ORDER BY namespace ASC, entry_key ASC",
                params,
            ).fetchall()

        vector_clock: Dict[str, int] = {str(r["peer_id"]): int(r["max_ts"]) for r in vc_rows}
        entries: List[Dict[str, Any]] = []
        active_keys_count = 0
        for r in entry_rows:
            is_tomb = bool(int(r["tombstone"]))
            if not is_tomb:
                active_keys_count += 1
            raw_v = str(r["value_json"]) if r["value_json"] is not None else "null"
            entries.append({
                "namespace": str(r["namespace"]), "key": str(r["entry_key"]),
                "value": None if is_tomb else json.loads(raw_v),
                "lamport_ts": int(r["lamport_ts"]), "peer_id": str(r["peer_id"]), "tombstone": is_tomb,
            })

        state_digest_sha256 = "sha256:" + hashlib.sha256(_canonical_json(entries).encode("utf-8")).hexdigest()
        return {
            "workspace_id": ws, "vector_clock": vector_clock,
            "state_digest_sha256": state_digest_sha256,
            "active_keys_count": active_keys_count, "entries": entries,
        }


kflow_dag_engine = KFlowDagEngine()
kspaces_crdt_engine = KSpacesCrdtEngine()
