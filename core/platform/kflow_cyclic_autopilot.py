"""
Phase 15A Cyclic KFlow Engine, Bounded Reflection Loops, Dynamic Fan-Out Shards,
Saga Compensation & Cost-Latency-Privacy Autopilot (`core.platform.kflow_cyclic_autopilot`).
"""

from __future__ import annotations

from collections import deque
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

VALID_LOOP_CONDITIONS: Tuple[str, ...] = ("critic_score_lt", "retry_on_error", "until_converged")
VALID_PRIVACY_POLICIES: Tuple[str, ...] = ("hybrid_balanced", "airgap_strict", "eu_residency")
_SECRET_DLP_PATTERNS: Tuple[Pattern[str], ...] = (
    re.compile(r"sk-(?:proj-|live-|test-)?[A-Za-z0-9_-]{12,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
)
_DEFAULT_CYCLIC_NODES: Tuple[Dict[str, Any], ...] = (
    {"id": "draft_patch", "agent_id": "code-synthesizer", "model": "claude-3-7-sonnet", "depends_on": [], "fan_out_items": 3, "timeout_ms": 4000, "compensation_handler": "revert_worktree", "base_cost_usd": 0.045, "ttft_ms": 340, "requires_p10": False},
    {"id": "critic_verify", "agent_id": "critic-verifier", "model": "gpt-4.1", "depends_on": ["draft_patch"], "fan_out_items": 1, "timeout_ms": 3000, "compensation_handler": "discard_candidate", "base_cost_usd": 0.035, "ttft_ms": 290, "requires_p10": False},
    {"id": "publish_release", "agent_id": "release-guard", "model": "keelway-core:7b", "depends_on": ["critic_verify"], "fan_out_items": 1, "timeout_ms": 2500, "compensation_handler": "rollback_tag", "base_cost_usd": 0.0, "ttft_ms": 135, "requires_p10": False},
)
_DEFAULT_LOOP_EDGES: Tuple[Dict[str, Any], ...] = (
    {"from_node": "critic_verify", "to_node": "draft_patch", "condition": "critic_score_lt", "threshold": 0.85, "max_iterations": 3},
)
_CYCLIC_SCHEMA_SQL = (
    "CREATE TABLE IF NOT EXISTS kflow_cyclic_runs ("
    "run_id TEXT NOT NULL, workspace_id TEXT NOT NULL, workflow_id TEXT NOT NULL, status TEXT NOT NULL, "
    "payload_json TEXT NOT NULL, run_sha256 TEXT NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY (workspace_id, run_id)); "
    "CREATE INDEX IF NOT EXISTS idx_kflow_cyclic_runs_ws_time ON kflow_cyclic_runs(workspace_id, created_at DESC); "
    "CREATE TABLE IF NOT EXISTS kflow_autopilot_simulations ("
    "simulation_id TEXT NOT NULL, workspace_id TEXT NOT NULL, workflow_id TEXT NOT NULL, privacy_policy TEXT NOT NULL, "
    "payload_json TEXT NOT NULL, simulation_sha256 TEXT NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY (workspace_id, simulation_id)); "
    "CREATE INDEX IF NOT EXISTS idx_kflow_autopilot_sims_ws_time ON kflow_autopilot_simulations(workspace_id, created_at DESC);"
)


class CyclicKFlowValidationError(ValueError):
    """Raised when a cyclic KFlow graph, loop bound, shard count, or autopilot parameter is invalid."""


class CyclicKFlowPolicyViolationError(ValueError):
    """Raised when cyclic workflow initial_state contains raw secret material blocked by DLP."""


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
            raise CyclicKFlowPolicyViolationError(
                "DLP policy violation: raw secret token detected in initial_state; execution rejected before SQLite persistence."
            )


def _is_opencore_model(model: str) -> bool:
    return str(model or "").strip().lower().startswith(("keelway-", "qwen", "llama"))


def _default_model_cost(model: str) -> float:
    if _is_opencore_model(model):
        return 0.0
    return 0.045 if "claude" in str(model or "").strip().lower() else 0.035


def _select_opencore_target(node: Dict[str, Any]) -> str:
    hint = f"{node.get('id', '')} {node.get('agent_id', '')}".lower()
    return "qwen2.5-coder:7b" if any(tok in hint for tok in ("code", "synth", "patch", "draft")) else "keelway-core:7b"


def _require_int_range(val: Any, low: int, high: Optional[int], label: str) -> int:
    if isinstance(val, bool) or int(val) < low or (high is not None and int(val) > high):
        bound = f"between {low} and {high}" if high is not None else f">= {low}"
        raise CyclicKFlowValidationError(f"{label} must be {bound}.")
    return int(val)


def _normalize_and_validate_graph(
    nodes: Optional[Sequence[Dict[str, Any]]],
    loop_edges: Optional[Sequence[Dict[str, Any]]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[str]]:
    if nodes is None:
        raw_nodes: List[Dict[str, Any]] = [dict(n, depends_on=list(n["depends_on"])) for n in _DEFAULT_CYCLIC_NODES]
    elif not isinstance(nodes, (list, tuple)) or len(nodes) == 0:
        raise CyclicKFlowValidationError("Cyclic KFlow 'nodes' must be a non-empty list.")
    else:
        raw_nodes = list(nodes)

    norm_nodes: List[Dict[str, Any]] = []
    seen_ids: set[str] = set()
    for raw in raw_nodes:
        if not isinstance(raw, dict):
            raise CyclicKFlowValidationError("Each node entry must be a JSON object.")
        nid = str(raw.get("id") if raw.get("id") is not None else raw.get("node_id") or "").strip()
        if not nid or nid in seen_ids:
            raise CyclicKFlowValidationError(f"Invalid or duplicate node id '{nid}'.")
        seen_ids.add(nid)

        fan_out = _require_int_range(raw.get("fan_out_items", 1), 1, 16, f"Node '{nid}' fan_out_items")
        timeout_ms = _require_int_range(raw.get("timeout_ms", 3000), 50, None, f"Node '{nid}' timeout_ms")
        raw_deps = raw.get("depends_on") or []
        if not isinstance(raw_deps, (list, tuple)):
            raise CyclicKFlowValidationError(f"Node '{nid}' depends_on must be a list of node IDs.")
        deps = [str(d).strip() for d in raw_deps if str(d).strip()]

        model = str(raw.get("model") or "keelway-core:7b").strip() or "keelway-core:7b"
        raw_cost = raw.get("base_cost_usd")
        cost_usd = round(float(raw_cost) if raw_cost is not None and not isinstance(raw_cost, bool) else _default_model_cost(model), 6)
        if cost_usd < 0.0:
            raise CyclicKFlowValidationError(f"Node '{nid}' base_cost_usd must be >= 0.0.")
        raw_ttft = raw.get("ttft_ms")
        ttft_ms = int(raw_ttft) if raw_ttft is not None and not isinstance(raw_ttft, bool) else (135 if _is_opencore_model(model) else 320)
        comp = str(raw.get("compensation_handler") or f"compensate_{nid}").strip() or f"compensate_{nid}"
        norm_nodes.append({
            "id": nid, "agent_id": str(raw.get("agent_id") or "governed-agent").strip() or "governed-agent",
            "model": model, "depends_on": deps, "fan_out_items": fan_out, "timeout_ms": timeout_ms,
            "compensation_handler": comp, "base_cost_usd": cost_usd, "ttft_ms": max(1, ttft_ms),
            "requires_p10": bool(raw.get("requires_p10", False)),
        })

    in_degree: Dict[str, int] = {n["id"]: 0 for n in norm_nodes}
    adj: Dict[str, List[str]] = {n["id"]: [] for n in norm_nodes}
    for n in norm_nodes:
        nid = n["id"]
        for dep in n["depends_on"]:
            if dep not in seen_ids or dep == nid:
                raise CyclicKFlowValidationError(f"Node '{nid}' has invalid depends_on '{dep}'.")
            adj[dep].append(nid)
            in_degree[nid] += 1

    queue: deque[str] = deque(n["id"] for n in norm_nodes if in_degree[n["id"]] == 0)
    topological_spine: List[str] = []
    while queue:
        curr = queue.popleft()
        topological_spine.append(curr)
        for nxt in adj[curr]:
            in_degree[nxt] -= 1
            if in_degree[nxt] == 0:
                queue.append(nxt)

    if len(topological_spine) != len(norm_nodes):
        raise CyclicKFlowValidationError(
            "Unguarded cycle detected in forward depends_on spine; cyclic back-edges must be declared in loop_edges."
        )

    spine_pos = {nid: idx for idx, nid in enumerate(topological_spine)}
    if loop_edges is None:
        raw_edges = [dict(e) for e in _DEFAULT_LOOP_EDGES] if (nodes is None or {"critic_verify", "draft_patch"}.issubset(seen_ids)) else []
    elif not isinstance(loop_edges, (list, tuple)):
        raise CyclicKFlowValidationError("loop_edges must be a list of loop edge objects.")
    else:
        raw_edges = list(loop_edges)

    norm_edges: List[Dict[str, Any]] = []
    for edge in raw_edges:
        if not isinstance(edge, dict):
            raise CyclicKFlowValidationError("Each loop_edge must be a JSON object.")
        from_node, to_node = str(edge.get("from_node") or "").strip(), str(edge.get("to_node") or "").strip()
        if from_node not in seen_ids or to_node not in seen_ids:
            raise CyclicKFlowValidationError(f"Unknown loop_edge node reference '{from_node}' -> '{to_node}'.")
        if spine_pos[to_node] > spine_pos[from_node]:
            raise CyclicKFlowValidationError(f"Invalid loop_edge '{from_node}' -> '{to_node}': must target upstream or self node.")
        cond = str(edge.get("condition") or "").strip()
        if cond not in VALID_LOOP_CONDITIONS:
            raise CyclicKFlowValidationError(f"Invalid loop condition '{cond}'. Expected {list(VALID_LOOP_CONDITIONS)}.")
        max_it = _require_int_range(edge.get("max_iterations", 3), 1, 10, "loop_edge max_iterations")
        raw_thr = edge.get("threshold", 0.85)
        if isinstance(raw_thr, bool) or float(raw_thr) < 0.0 or float(raw_thr) > 1.0:
            raise CyclicKFlowValidationError("loop_edge threshold must be between 0.0 and 1.0.")
        norm_edges.append({
            "from_node": from_node, "to_node": to_node, "condition": cond,
            "threshold": round(float(raw_thr), 4), "max_iterations": max_it,
        })

    node_by_id = {n["id"]: n for n in norm_nodes}
    return [node_by_id[nid] for nid in topological_spine], norm_edges, topological_spine


class SQLiteCyclicKFlowEngine:
    """Thread-safe SQLite WAL engine for cyclic KFlow execution, saga compensation, and cost-privacy autopilot."""

    def __init__(self, db_path: Optional[Union[str, Path]] = None) -> None:
        self._lock = threading.RLock()
        self._explicit_db_path, self._conn, self._active_target = db_path, None, None
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
        for pragma in ("PRAGMA journal_mode=WAL", "PRAGMA synchronous=NORMAL", "PRAGMA foreign_keys=ON"):
            conn.execute(pragma)
        with conn:
            conn.executescript(_CYCLIC_SCHEMA_SQL)
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

    def _list_table_payloads(self, table: str, workspace_id: str, workflow_id: Optional[str], limit: int) -> Tuple[str, List[Dict[str, Any]]]:
        ws = _clean_workspace_id(workspace_id)
        cap = min(_require_int_range(limit, 1, None, "limit"), 200)
        clean_wf = str(workflow_id).strip() if workflow_id is not None and str(workflow_id).strip() else None
        sql = f"SELECT payload_json FROM {table} WHERE workspace_id=?" + (" AND workflow_id=?" if clean_wf else "") + " ORDER BY created_at DESC, rowid DESC LIMIT ?"
        params: Tuple[Any, ...] = (ws, clean_wf, cap) if clean_wf else (ws, cap)
        with self._lock:
            rows = self._ensure_conn().execute(sql, params).fetchall()
        return ws, [json.loads(str(r["payload_json"])) for r in rows]

    def validate_cyclic_graph(
        self, workspace_id: str = "default", workflow_id: str = "WF-CYCLIC-01",
        nodes: Optional[Sequence[Dict[str, Any]]] = None, loop_edges: Optional[Sequence[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        ws = _clean_workspace_id(workspace_id)
        wf = str(workflow_id or "WF-CYCLIC-01").strip() or "WF-CYCLIC-01"
        spine_nodes, norm_edges, topological_spine = _normalize_and_validate_graph(nodes, loop_edges)
        spine_pos = {nid: idx for idx, nid in enumerate(topological_spine)}
        visits = {nid: 1 for nid in topological_spine}
        for edge in norm_edges:
            for idx in range(spine_pos[edge["to_node"]], spine_pos[edge["from_node"]] + 1):
                visits[topological_spine[idx]] = max(visits[topological_spine[idx]], int(edge["max_iterations"]))
        spec_sha256 = hashlib.sha256(_canonical_json([ws, wf, spine_nodes, norm_edges]).encode("utf-8")).hexdigest()
        return {
            "workspace_id": ws, "workflow_id": wf, "valid": True, "node_count": len(spine_nodes),
            "loop_edge_count": len(norm_edges), "max_worst_case_steps": sum(visits.values()),
            "topological_spine": topological_spine, "compensation_handlers": [n["compensation_handler"] for n in spine_nodes],
            "spec_sha256": spec_sha256,
        }

    def execute_cyclic_graph(
        self, workspace_id: str = "default", workflow_id: str = "WF-CYCLIC-01",
        nodes: Optional[Sequence[Dict[str, Any]]] = None, loop_edges: Optional[Sequence[Dict[str, Any]]] = None,
        max_iterations_override: Optional[int] = None, critic_threshold: float = 0.85,
        fan_out_shards: Optional[int] = None, simulate_timeout: bool = False,
        initial_state: Optional[Dict[str, Any]] = None, approved_node_ids: Optional[Sequence[str]] = None,
    ) -> Dict[str, Any]:
        ws = _clean_workspace_id(workspace_id)
        wf = str(workflow_id or "WF-CYCLIC-01").strip() or "WF-CYCLIC-01"
        _assert_no_dlp_secrets(initial_state)
        if max_iterations_override is not None:
            _require_int_range(max_iterations_override, 1, 10, "max_iterations_override")
        if fan_out_shards is not None:
            _require_int_range(fan_out_shards, 1, 16, "fan_out_shards")
        if isinstance(critic_threshold, bool) or float(critic_threshold) < 0.0 or float(critic_threshold) > 1.0:
            raise CyclicKFlowValidationError("critic_threshold must be between 0.0 and 1.0.")

        spine_nodes, norm_edges, topological_spine = _normalize_and_validate_graph(nodes, loop_edges)
        spine_pos = {nid: idx for idx, nid in enumerate(topological_spine)}
        eff_max_iter = int(max_iterations_override) if max_iterations_override is not None else (int(norm_edges[0]["max_iterations"]) if norm_edges else 1)
        eff_thr = round(float(critic_threshold), 4) if float(critic_threshold) != 0.85 or not norm_edges else round(float(norm_edges[0]["threshold"]), 4)
        eff_shards = int(fan_out_shards) if fan_out_shards is not None else max(int(n["fan_out_items"]) for n in spine_nodes)
        approved_set = {str(x).strip() for x in (approved_node_ids or []) if str(x).strip()}

        iteration_trace: List[Dict[str, Any]] = []
        compensation_log: List[Dict[str, Any]] = []
        held_node_id = next((n["id"] for n in spine_nodes if n["requires_p10"] and n["id"] not in approved_set), None)
        converged, final_score, iterations_executed = False, 0.0, 0

        if held_node_id is not None:
            status = "HELD_P10"
        elif simulate_timeout:
            iterations_executed = 1
            loop_end = spine_pos[norm_edges[0]["from_node"]] if norm_edges else len(spine_nodes) - 1
            visited = spine_nodes[: loop_end + 1]
            for idx, n in enumerate(visited):
                is_last = idx == len(visited) - 1
                sh = eff_shards if int(n["fan_out_items"]) > 1 else int(n["fan_out_items"])
                iteration_trace.append({
                    "iteration": 1, "node_id": n["id"], "agent_id": n["agent_id"], "model": n["model"],
                    "critic_score": 0.0, "shard_count": sh, "status": "TIMED_OUT" if is_last else "COMPLETED",
                    "cost_usd": round(float(n["base_cost_usd"]), 6), "latency_ms": int(n["timeout_ms"]) if is_last else int(n["ttft_ms"]),
                })
            compensation_log = [
                {"node_id": n["id"], "handler": n["compensation_handler"], "reason": "timeout_exceeded", "status": "ROLLED_BACK"}
                for n in reversed(visited)
            ]
            status = "COMPENSATED"
        else:
            if norm_edges:
                idx_to, idx_from = min(spine_pos[e["to_node"]] for e in norm_edges), max(spine_pos[e["from_node"]] for e in norm_edges)
                pre_nodes, loop_nodes, post_nodes = spine_nodes[:idx_to], spine_nodes[idx_to : idx_from + 1], spine_nodes[idx_from + 1 :]
            else:
                pre_nodes, loop_nodes, post_nodes = [], spine_nodes, []

            visited_order: List[Dict[str, Any]] = []
            seen_visited: set[str] = set()

            def _run_node(n: Dict[str, Any], it_num: int, c_score: float) -> None:
                base_sh = int(n["fan_out_items"])
                sh = eff_shards if (fan_out_shards is not None and (base_sh > 1 or n == loop_nodes[0])) else base_sh
                iteration_trace.append({
                    "iteration": it_num, "node_id": n["id"], "agent_id": n["agent_id"], "model": n["model"],
                    "critic_score": c_score, "shard_count": sh, "status": "COMPLETED",
                    "cost_usd": round(float(n["base_cost_usd"]) * (sh / max(1, base_sh)), 6),
                    "latency_ms": int(n["ttft_ms"]) + max(0, sh - 1) * 20,
                })
                if n["id"] not in seen_visited:
                    seen_visited.add(n["id"])
                    visited_order.append(n)

            for n in pre_nodes:
                _run_node(n, 1, 0.74)
            for i in range(1, eff_max_iter + 1):
                iterations_executed = i
                final_score = round(min(0.96, 0.58 + 0.16 * i), 4)
                for n in loop_nodes:
                    _run_node(n, i, final_score)
                if not norm_edges or final_score >= eff_thr:
                    converged = True
                    break
            if converged:
                for n in post_nodes:
                    _run_node(n, iterations_executed, final_score)
                status = "CONVERGED"
            else:
                compensation_log = [
                    {"node_id": n["id"], "handler": n["compensation_handler"], "reason": "max_iterations_exhausted", "status": "ROLLED_BACK"}
                    for n in reversed(visited_order)
                ]
                status = "COMPENSATED"

        total_cost = round(sum(float(t["cost_usd"]) for t in iteration_trace), 6)
        total_latency = sum(int(t["latency_ms"]) for t in iteration_trace)
        run_id, created_at = f"cyc-{uuid.uuid4().hex[:12]}", _utc_now()
        run_sha256 = hashlib.sha256(
            _canonical_json([ws, wf, status, iterations_executed, converged, final_score, iteration_trace, compensation_log, held_node_id]).encode("utf-8")
        ).hexdigest()
        record: Dict[str, Any] = {
            "run_id": run_id, "workspace_id": ws, "workflow_id": wf, "status": status,
            "iterations_executed": iterations_executed, "max_iterations": eff_max_iter,
            "converged": converged, "final_critic_score": final_score, "critic_threshold": eff_thr,
            "fan_out_shards": eff_shards, "total_cost_usd": total_cost, "total_latency_ms": total_latency,
            "iteration_trace": iteration_trace, "compensation_log": compensation_log,
            "held_node_id": held_node_id, "run_sha256": run_sha256, "created_at": created_at,
        }
        with self._lock:
            conn = self._ensure_conn()
            with conn:
                conn.execute("INSERT INTO kflow_cyclic_runs VALUES (?, ?, ?, ?, ?, ?, ?)", (run_id, ws, wf, status, _canonical_json(record), run_sha256, created_at))
        return record

    def list_cyclic_runs(self, workspace_id: str = "default", workflow_id: Optional[str] = None, limit: int = 25) -> Dict[str, Any]:
        ws, runs = self._list_table_payloads("kflow_cyclic_runs", workspace_id, workflow_id, limit)
        return {"workspace_id": ws, "count": len(runs), "runs": runs}

    def get_cyclic_run(self, workspace_id: str = "default", run_id: str = "") -> Optional[Dict[str, Any]]:
        ws, clean_id = _clean_workspace_id(workspace_id), str(run_id or "").strip()
        if not clean_id:
            return None
        with self._lock:
            row = self._ensure_conn().execute("SELECT payload_json FROM kflow_cyclic_runs WHERE workspace_id=? AND run_id=?", (ws, clean_id)).fetchone()
        return json.loads(str(row["payload_json"])) if row is not None else None

    def simulate_autopilot(
        self, workspace_id: str = "default", workflow_id: str = "WF-CYCLIC-01",
        nodes: Optional[Sequence[Dict[str, Any]]] = None, loop_edges: Optional[Sequence[Dict[str, Any]]] = None,
        budget_cap_usd: float = 0.15, privacy_policy: str = "hybrid_balanced", expected_loop_multiplier: int = 2,
    ) -> Dict[str, Any]:
        ws = _clean_workspace_id(workspace_id)
        wf = str(workflow_id or "WF-CYCLIC-01").strip() or "WF-CYCLIC-01"
        policy = str(privacy_policy or "").strip()
        if policy not in VALID_PRIVACY_POLICIES:
            raise CyclicKFlowValidationError(f"Unsupported privacy_policy '{policy}'. Expected {list(VALID_PRIVACY_POLICIES)}.")
        if isinstance(budget_cap_usd, bool) or float(budget_cap_usd) < 0.0:
            raise CyclicKFlowValidationError("budget_cap_usd must be >= 0.0.")
        _require_int_range(expected_loop_multiplier, 1, None, "expected_loop_multiplier")

        spine_nodes, _, _ = _normalize_and_validate_graph(nodes, loop_edges)
        mult, cap_usd = max(int(expected_loop_multiplier), 2), round(float(budget_cap_usd), 6)
        draft_plan: List[Dict[str, Any]] = []
        for idx, n in enumerate(spine_nodes):
            orig_model, is_local = n["model"], _is_opencore_model(n["model"])
            orig_cost = 0.0 if is_local else float(n["base_cost_usd"] or _default_model_cost(orig_model))
            draft_plan.append({
                "idx": idx, "node": n, "orig_model": orig_model, "is_local": is_local,
                "orig_cost": round(orig_cost, 6), "orig_ttft": int(n["ttft_ms"]),
                "rewritten": False, "selected_model": orig_model, "reason": "retained: within policy and P95 budget envelope",
            })

        baseline_p50 = round(sum(d["orig_cost"] for d in draft_plan), 6)
        baseline_p95 = round(baseline_p50 * mult, 6)
        baseline_ttft = sum(d["orig_ttft"] for d in draft_plan)
        violations_resolved = 0

        if policy in ("airgap_strict", "eu_residency"):
            p_reason = "airgap_strict: zero-egress OpenCore enforcement" if policy == "airgap_strict" else "eu_residency: sovereign local checkpoint"
            for d in draft_plan:
                if not d["is_local"]:
                    d["rewritten"], d["selected_model"], d["reason"] = True, _select_opencore_target(d["node"]), p_reason
                    violations_resolved += 1

        def _curr_p95() -> float:
            return round(sum((0.0 if d["rewritten"] else d["orig_cost"]) * mult for d in draft_plan), 6)

        if _curr_p95() > cap_usd:
            for cand in sorted((d for d in draft_plan if not d["is_local"] and not d["rewritten"]), key=lambda item: (-item["orig_cost"], item["idx"])):
                if _curr_p95() <= cap_usd:
                    break
                cand["rewritten"], cand["selected_model"] = True, _select_opencore_target(cand["node"])
                cand["reason"] = "budget_cap_usd: P95 spend autopilot fallback"
                violations_resolved += 1

        node_plan: List[Dict[str, Any]] = []
        opt_ttft = 0
        for d in draft_plan:
            p50_c = 0.0 if d["rewritten"] else d["orig_cost"]
            opt_ttft += 135 if d["rewritten"] else d["orig_ttft"]
            node_plan.append({
                "node_id": d["node"]["id"], "original_model": d["orig_model"], "selected_model": d["selected_model"],
                "rewritten": d["rewritten"], "reason": d["reason"], "p50_cost_usd": p50_c,
                "p95_cost_usd": round(p50_c * mult, 6),
                "data_boundary": "local_metal_zero_egress" if (d["is_local"] or d["rewritten"]) else "frontier_cloud",
            })

        opt_p50 = round(sum(item["p50_cost_usd"] for item in node_plan), 6)
        opt_p95 = round(sum(item["p95_cost_usd"] for item in node_plan), 6)
        savings_pct = round(((baseline_p95 - opt_p95) / baseline_p95) * 100.0, 2) if baseline_p95 > 0 else 0.0
        sim_id, created_at = f"apsim-{uuid.uuid4().hex[:12]}", _utc_now()
        sim_sha256 = hashlib.sha256(_canonical_json([ws, wf, policy, cap_usd, mult, node_plan, opt_p95]).encode("utf-8")).hexdigest()
        simulation: Dict[str, Any] = {
            "simulation_id": sim_id, "workspace_id": ws, "workflow_id": wf, "privacy_policy": policy,
            "budget_cap_usd": cap_usd, "expected_loop_multiplier": mult, "baseline_p50_usd": baseline_p50,
            "baseline_p95_usd": baseline_p95, "baseline_ttft_ms": baseline_ttft, "optimized_p50_usd": opt_p50,
            "optimized_p95_usd": opt_p95, "savings_pct": savings_pct, "optimized_ttft_ms": opt_ttft,
            "privacy_compliant": True, "violations_resolved": violations_resolved, "node_plan": node_plan,
            "simulation_sha256": sim_sha256, "created_at": created_at,
        }
        with self._lock:
            conn = self._ensure_conn()
            with conn:
                conn.execute("INSERT INTO kflow_autopilot_simulations VALUES (?, ?, ?, ?, ?, ?, ?)", (sim_id, ws, wf, policy, _canonical_json(simulation), sim_sha256, created_at))
        return simulation

    def list_autopilot_simulations(self, workspace_id: str = "default", workflow_id: Optional[str] = None, limit: int = 25) -> Dict[str, Any]:
        ws, sims = self._list_table_payloads("kflow_autopilot_simulations", workspace_id, workflow_id, limit)
        return {"workspace_id": ws, "count": len(sims), "simulations": sims}


cyclic_kflow_engine = SQLiteCyclicKFlowEngine()
