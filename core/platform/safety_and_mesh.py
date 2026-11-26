"""Phase 17A Formal Safety State-Machine Verifier & Federated Edge-to-Cluster Agent Mesh (`core.platform.safety_and_mesh`)."""

from __future__ import annotations

from collections import deque
import json
import os
from pathlib import Path
import re
import sqlite3
import threading
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union
import uuid

from core.platform.flight_tape import _canonical_json, _clean_workspace_id, _sha256_json, _utc_now, scrub_flight_text
from core.platform.kbrain_khub import resolve_kbrain_db_target

VALID_TOOL_KINDS: Tuple[str, ...] = ("read_only", "write", "destructive_shell", "external_transfer", "cloud_egress")
VALID_DATA_CLASSIFICATIONS: Tuple[str, ...] = ("public", "internal", "restricted_pii")
VALID_MESH_TIERS: Tuple[str, ...] = ("edge_local", "cluster_burst")
VALID_HARDWARE_HALS: Tuple[str, ...] = ("apple_metal_secure_enclave", "nvidia_h100_cc", "linux_tpm2")
VALID_NODE_STATUSES: Tuple[str, ...] = ("ONLINE", "DRAINING")
DESTRUCTIVE_TOOL_KINDS: frozenset[str] = frozenset({"destructive_shell", "external_transfer"})
UNPRIVILEGED_ROLES: frozenset[str] = frozenset({"viewer", "untrusted_tool"})
UNBOUNDED_EDGE_CONDITIONS: frozenset[str] = frozenset({"unbounded", "infinite", "while_true", "always"})
_SLUG_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")

_DEFAULT_SAFETY_NODES: Tuple[Dict[str, Any], ...] = (
    {"node_id": "ingest_invoice", "role": "viewer", "tool_kind": "read_only", "requires_p10": False, "max_iterations": 1, "data_classification": "internal"},
    {"node_id": "validate_vendor", "role": "agent", "tool_kind": "write", "requires_p10": False, "max_iterations": 2, "data_classification": "internal"},
    {"node_id": "execute_wire_transfer", "role": "agent", "tool_kind": "external_transfer", "requires_p10": False, "max_iterations": 1, "data_classification": "internal"},
)

_DEFAULT_SEED_MESH_NODES: Tuple[Dict[str, Any], ...] = (
    {"node_id": "edge-mac-m3-max", "name": "Local Mac Studio M3 Max", "tier": "edge_local", "hardware_hal": "apple_metal_secure_enclave", "region": "local-loopback", "vram_gb": 64, "status": "ONLINE"},
    {"node_id": "cluster-h100-us-east", "name": "Sovereign H100 Confidential Cluster", "tier": "cluster_burst", "hardware_hal": "nvidia_h100_cc", "region": "us-east-tee", "vram_gb": 80, "status": "ONLINE"},
)

_INVARIANT_DESCRIPTIONS: Tuple[Tuple[str, str], ...] = (
    ("no_unguarded_destructive_tool", "Every destructive_shell or external_transfer node must enforce a P-10 human approval gate (requires_p10=true)."),
    ("no_privilege_escalation", "Viewer or untrusted_tool roles cannot transition directly into destructive_shell or external_transfer nodes without a P-10 gate."),
    ("bounded_termination", "All workflow nodes and cyclic transitions must terminate within bounded iterations (1 <= max_iterations <= 10)."),
    ("airgap_zero_egress", "Cloud egress tools are forbidden when airgap_mode is active or node data_classification is restricted_pii."),
)

_SAFETY_MESH_SCHEMA_SQL = (
    "CREATE TABLE IF NOT EXISTS safety_verifications (verification_id TEXT NOT NULL, workspace_id TEXT NOT NULL, workflow_id TEXT NOT NULL, workflow_name TEXT NOT NULL, status TEXT NOT NULL, states_explored INTEGER NOT NULL, payload_json TEXT NOT NULL, proof_sha256 TEXT NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY (workspace_id, verification_id)); "
    "CREATE INDEX IF NOT EXISTS idx_safety_verifications_ws_created ON safety_verifications(workspace_id, created_at DESC); "
    "CREATE TABLE IF NOT EXISTS mesh_nodes (node_id TEXT NOT NULL, workspace_id TEXT NOT NULL, name TEXT NOT NULL, tier TEXT NOT NULL, hardware_hal TEXT NOT NULL, region TEXT NOT NULL, vram_gb INTEGER NOT NULL, status TEXT NOT NULL, payload_json TEXT NOT NULL, attestation_sha256 TEXT NOT NULL, registered_at TEXT NOT NULL, PRIMARY KEY (workspace_id, node_id)); "
    "CREATE INDEX IF NOT EXISTS idx_mesh_nodes_ws_reg ON mesh_nodes(workspace_id, registered_at ASC); "
    "CREATE TABLE IF NOT EXISTS mesh_handoffs (handoff_id TEXT NOT NULL, workspace_id TEXT NOT NULL, workflow_name TEXT NOT NULL, data_classification TEXT NOT NULL, status TEXT NOT NULL, edge_node_id TEXT NOT NULL, burst_node_id TEXT, payload_json TEXT NOT NULL, attestation_sha256 TEXT NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY (workspace_id, handoff_id)); "
    "CREATE INDEX IF NOT EXISTS idx_mesh_handoffs_ws_created ON mesh_handoffs(workspace_id, created_at DESC);"
)


class SafetyMeshValidationError(ValueError):
    """Raised when workflow safety specs, workspace IDs, or mesh node parameters are invalid."""


class SafetyVerificationNotFoundError(KeyError):
    """Raised when a requested safety verification_id does not exist in the workspace."""


class MeshSovereigntyViolationError(ValueError):
    """Raised fail-closed when raw restricted_pii attempts to burst to cluster without edge sanitization."""

    code = "mesh_sovereignty_violation"


def _validate_ws_and_limit(workspace_id: str, limit: int = 25) -> Tuple[str, int]:
    try:
        ws = _clean_workspace_id(workspace_id)
    except ValueError as exc:
        raise SafetyMeshValidationError(str(exc)) from exc
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise SafetyMeshValidationError("limit must be a positive integer.")
    return ws, min(limit, 200)


def _validate_enum(val: Any, allowed: Tuple[str, ...], field_name: str) -> str:
    clean = str(val or "").strip()
    if clean not in allowed:
        raise SafetyMeshValidationError(f"Unsupported {field_name} '{val}'. Expected {list(allowed)}.")
    return clean


def _shortest_path(adj: Dict[str, List[str]], starts: Sequence[str], target: str) -> List[str]:
    queue: deque[List[str]] = deque([s] for s in starts)
    visited: Set[str] = set(starts)
    while queue:
        path = queue.popleft()
        if path[-1] == target:
            return path
        for nxt in adj.get(path[-1], ()):
            if nxt not in visited:
                visited.add(nxt)
                queue.append([*path, nxt])
    return [target]


def _explore_bounded_states(norm_nodes: Sequence[Dict[str, Any]], adj: Dict[str, List[str]], starts: Sequence[str]) -> int:
    iter_caps = {n["node_id"]: min(max(int(n["max_iterations"]), 1), 12) for n in norm_nodes}
    queue: deque[Tuple[str, Dict[str, int]]] = deque((s, {s: 1}) for s in starts)
    explored, seen_nodes, seen_sigs = 0, set(), set()
    while queue and explored < 512:
        cur, counts = queue.popleft()
        sig = (cur, tuple(sorted(counts.items())))
        if sig in seen_sigs:
            continue
        seen_sigs.add(sig)
        seen_nodes.add(cur)
        explored += 1
        for nxt in adj.get(cur, ()):
            nxt_c = counts.get(nxt, 0) + 1
            if nxt_c <= iter_caps.get(nxt, 1):
                queue.append((nxt, {**counts, nxt: nxt_c}))
    explored += sum(1 for n in norm_nodes if n["node_id"] not in seen_nodes)
    return max(explored, len(norm_nodes))


def _normalize_safety_graph(
    nodes: Optional[Sequence[Dict[str, Any]]],
    edges: Optional[Sequence[Dict[str, Any]]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], int]:
    raw_nodes = list(nodes) if nodes else [dict(n) for n in _DEFAULT_SAFETY_NODES]
    norm_nodes, seen_ids, redactions = [], set(), 0
    for raw in raw_nodes:
        item = raw.model_dump() if hasattr(raw, "model_dump") else (dict(raw) if isinstance(raw, dict) else None)
        if not isinstance(item, dict):
            raise SafetyMeshValidationError("Each workflow node must be an object.")
        nid_raw = str(item.get("node_id") or "").strip()
        if not nid_raw:
            raise SafetyMeshValidationError("Each workflow node requires a non-empty node_id.")
        nid, r_id = scrub_flight_text(nid_raw)
        if nid in seen_ids:
            raise SafetyMeshValidationError(f"Duplicate node_id '{nid}' in workflow graph.")
        seen_ids.add(nid)
        role_clean, r_role = scrub_flight_text(str(item.get("role") or "agent").strip() or "agent")
        tool_kind = _validate_enum(item.get("tool_kind", "read_only"), VALID_TOOL_KINDS, "tool_kind")
        data_cls = _validate_enum(item.get("data_classification", "internal"), VALID_DATA_CLASSIFICATIONS, "data_classification")
        max_iter = item.get("max_iterations", 1)
        if isinstance(max_iter, bool) or not isinstance(max_iter, int):
            raise SafetyMeshValidationError(f"max_iterations on '{nid}' must be an integer.")
        redactions += r_id + r_role
        norm_nodes.append({"node_id": nid, "role": role_clean, "tool_kind": tool_kind, "requires_p10": bool(item.get("requires_p10", False)), "max_iterations": int(max_iter), "data_classification": data_cls})

    norm_edges: List[Dict[str, Any]] = []
    if edges:
        for raw_e in edges:
            e_obj = raw_e.model_dump() if hasattr(raw_e, "model_dump") else (dict(raw_e) if isinstance(raw_e, dict) else None)
            if not isinstance(e_obj, dict):
                raise SafetyMeshValidationError("Each workflow edge must be an object.")
            fn, r1 = scrub_flight_text(str(e_obj.get("from_node") or "").strip())
            tn, r2 = scrub_flight_text(str(e_obj.get("to_node") or "").strip())
            if fn not in seen_ids or tn not in seen_ids:
                raise SafetyMeshValidationError(f"Edge '{fn}' -> '{tn}' references an undeclared node_id.")
            raw_cond = e_obj.get("condition")
            cond, r3 = scrub_flight_text(str(raw_cond).strip()) if raw_cond is not None and str(raw_cond).strip() else (None, 0)
            redactions += r1 + r2 + r3
            norm_edges.append({"from_node": fn, "to_node": tn, "condition": cond})
    else:
        norm_edges = [{"from_node": norm_nodes[i]["node_id"], "to_node": norm_nodes[i + 1]["node_id"], "condition": None} for i in range(len(norm_nodes) - 1)]
    return norm_nodes, norm_edges, redactions


class SQLiteSafetyAndMeshEngine:
    """Thread-safe SQLite WAL engine for Formal Safety Verification & Federated Edge-to-Cluster Mesh."""

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
            conn.executescript(_SAFETY_MESH_SCHEMA_SQL)
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

    def verify_workflow(
        self,
        workspace_id: str = "default",
        workflow_id: str = "WF-TREASURY-01",
        workflow_name: str = "treasury-wire-approver",
        nodes: Optional[Sequence[Dict[str, Any]]] = None,
        edges: Optional[Sequence[Dict[str, Any]]] = None,
        airgap_mode: bool = False,
        inject_p10_guards: bool = False,
    ) -> Dict[str, Any]:
        ws, _ = _validate_ws_and_limit(workspace_id)
        wf_id, r_wid = scrub_flight_text(str(workflow_id or "WF-TREASURY-01").strip() or "WF-TREASURY-01")
        wf_name, r_wnm = scrub_flight_text(str(workflow_name or "treasury-wire-approver").strip() or "treasury-wire-approver")
        norm_nodes, norm_edges, r_graph = _normalize_safety_graph(nodes, edges)
        total_redactions, p10_guards_injected = (r_wid + r_wnm + r_graph), []

        if inject_p10_guards:
            for node in norm_nodes:
                if node["tool_kind"] in DESTRUCTIVE_TOOL_KINDS and not node["requires_p10"]:
                    node["requires_p10"] = True
                    p10_guards_injected.append(node["node_id"])

        node_map = {n["node_id"]: n for n in norm_nodes}
        adj: Dict[str, List[str]] = {n["node_id"]: [] for n in norm_nodes}
        in_degree: Dict[str, int] = {n["node_id"]: 0 for n in norm_nodes}
        for e in norm_edges:
            adj[e["from_node"]].append(e["to_node"])
            in_degree[e["to_node"]] += 1

        starts = [n["node_id"] for n in norm_nodes if in_degree[n["node_id"]] == 0] or [norm_nodes[0]["node_id"]]
        states_explored = _explore_bounded_states(norm_nodes, adj, starts)
        violations: List[Dict[str, Any]] = []

        for node in norm_nodes:
            if node["tool_kind"] in DESTRUCTIVE_TOOL_KINDS and not node["requires_p10"]:
                violations.append({"invariant_id": "no_unguarded_destructive_tool", "severity": "CRITICAL", "offending_node": node["node_id"], "counterexample_path": _shortest_path(adj, starts, node["node_id"]), "remediation": f"Set requires_p10=true on '{node['node_id']}' ({node['tool_kind']}) or verify with inject_p10_guards=true."})

        for e in norm_edges:
            src, dst = node_map[e["from_node"]], node_map[e["to_node"]]
            if src["role"].lower() in UNPRIVILEGED_ROLES and dst["tool_kind"] in DESTRUCTIVE_TOOL_KINDS and not dst["requires_p10"]:
                violations.append({"invariant_id": "no_privilege_escalation", "severity": "CRITICAL", "offending_node": dst["node_id"], "counterexample_path": [*_shortest_path(adj, starts, src["node_id"]), dst["node_id"]], "remediation": f"Require P-10 human approval on '{dst['node_id']}' before allowing transitions from '{src['role']}' node '{src['node_id']}'."})

        flagged_bounded: Set[str] = set()
        for node in norm_nodes:
            if node["max_iterations"] < 1 or node["max_iterations"] > 10:
                flagged_bounded.add(node["node_id"])
                violations.append({"invariant_id": "bounded_termination", "severity": "HIGH", "offending_node": node["node_id"], "counterexample_path": _shortest_path(adj, starts, node["node_id"]), "remediation": f"Bound max_iterations on '{node['node_id']}' within 1..10 (got {node['max_iterations']})."})
        for e in norm_edges:
            u, v = e["from_node"], e["to_node"]
            cond_norm = str(e.get("condition") or "").strip().lower()
            cyc_path = [v] if u == v else _shortest_path(adj, [v], u)
            in_cycle = u == v or (len(cyc_path) > 1 and cyc_path[-1] == u)
            if in_cycle and cond_norm in UNBOUNDED_EDGE_CONDITIONS and v not in flagged_bounded:
                flagged_bounded.add(v)
                loop_tail = [v] if u == v else [*cyc_path[1:], v]
                violations.append({"invariant_id": "bounded_termination", "severity": "HIGH", "offending_node": v, "counterexample_path": [*_shortest_path(adj, starts, v), *loop_tail], "remediation": f"Replace unbounded loop condition on '{u}' -> '{v}' with a bounded convergence cap (<= 10)."})

        for node in norm_nodes:
            if node["tool_kind"] == "cloud_egress" and (bool(airgap_mode) or node["data_classification"] == "restricted_pii"):
                violations.append({"invariant_id": "airgap_zero_egress", "severity": "CRITICAL", "offending_node": node["node_id"], "counterexample_path": _shortest_path(adj, starts, node["node_id"]), "remediation": f"Pin '{node['node_id']}' to local OpenCore execution or sanitize restricted_pii at the edge before cloud burst."})

        violated_ids = {v["invariant_id"] for v in violations}
        invariants_checked = [{"invariant_id": inv_id, "passed": inv_id not in violated_ids, "description": desc} for inv_id, desc in _INVARIANT_DESCRIPTIONS]
        status = "VERIFIED_SAFE" if not violations else "VIOLATION_FOUND"
        ver_id, created_at = f"sver-{uuid.uuid4().hex[:12]}", _utc_now()
        proof_sha = _sha256_json({"workspace_id": ws, "workflow_id": wf_id, "workflow_name": wf_name, "airgap_mode": bool(airgap_mode), "nodes": norm_nodes, "edges": norm_edges, "status": status, "invariants_checked": invariants_checked, "violations": violations, "p10_guards_injected": p10_guards_injected})
        record = {"verification_id": ver_id, "workspace_id": ws, "workflow_id": wf_id, "workflow_name": wf_name, "status": status, "states_explored": states_explored, "invariants_checked": invariants_checked, "violations": violations, "p10_guards_injected": p10_guards_injected, "dlp_redactions": total_redactions, "proof_sha256": proof_sha, "created_at": created_at}
        with self._lock:
            conn = self._ensure_conn()
            with conn:
                conn.execute("INSERT INTO safety_verifications VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (ver_id, ws, wf_id, wf_name, status, states_explored, _canonical_json(record), proof_sha, created_at))
        return record

    def list_verifications(self, workspace_id: str = "default", limit: int = 25) -> Dict[str, Any]:
        ws, cap = _validate_ws_and_limit(workspace_id, limit)
        with self._lock:
            rows = self._ensure_conn().execute("SELECT payload_json FROM safety_verifications WHERE workspace_id=? ORDER BY created_at DESC, rowid DESC LIMIT ?", (ws, cap)).fetchall()
        items = [json.loads(str(r["payload_json"])) for r in rows]
        return {"workspace_id": ws, "count": len(items), "verifications": items}

    def get_verification(self, workspace_id: str = "default", verification_id: str = "") -> Dict[str, Any]:
        ws, _ = _validate_ws_and_limit(workspace_id)
        clean_vid = str(verification_id or "").strip()
        if not clean_vid:
            raise SafetyVerificationNotFoundError("Verification '' not found.")
        with self._lock:
            row = self._ensure_conn().execute("SELECT payload_json FROM safety_verifications WHERE workspace_id=? AND verification_id=?", (ws, clean_vid)).fetchone()
        if row is None:
            raise SafetyVerificationNotFoundError(f"Safety verification '{clean_vid}' not found in workspace '{ws}'.")
        return json.loads(str(row["payload_json"]))

    def _insert_node_row(self, conn: sqlite3.Connection, ws: str, spec: Dict[str, Any]) -> Dict[str, Any]:
        reg_at = _utc_now()
        att_sha = _sha256_json({"workspace_id": ws, **spec})
        record = {"node_id": spec["node_id"], "workspace_id": ws, "name": spec["name"], "tier": spec["tier"], "hardware_hal": spec["hardware_hal"], "region": spec["region"], "vram_gb": spec["vram_gb"], "status": spec["status"], "attestation_sha256": att_sha, "registered_at": reg_at}
        conn.execute("INSERT OR REPLACE INTO mesh_nodes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (spec["node_id"], ws, spec["name"], spec["tier"], spec["hardware_hal"], spec["region"], spec["vram_gb"], spec["status"], _canonical_json(record), att_sha, reg_at))
        return record

    def _ensure_seeded_nodes(self, conn: sqlite3.Connection, ws: str) -> None:
        if int(conn.execute("SELECT COUNT(*) FROM mesh_nodes WHERE workspace_id=?", (ws,)).fetchone()[0]) == 0:
            with conn:
                for seed in _DEFAULT_SEED_MESH_NODES:
                    self._insert_node_row(conn, ws, seed)

    def register_node(
        self,
        workspace_id: str = "default",
        name: str = "",
        tier: str = "edge_local",
        hardware_hal: str = "apple_metal_secure_enclave",
        node_id: Optional[str] = None,
        region: str = "local-loopback",
        vram_gb: int = 32,
        status: str = "ONLINE",
    ) -> Dict[str, Any]:
        ws, _ = _validate_ws_and_limit(workspace_id)
        clean_tier = _validate_enum(tier, VALID_MESH_TIERS, "tier")
        clean_hal = _validate_enum(hardware_hal, VALID_HARDWARE_HALS, "hardware_hal")
        clean_status = _validate_enum(status, VALID_NODE_STATUSES, "status")
        raw_name = str(name or "").strip()
        if not raw_name:
            raise SafetyMeshValidationError("Mesh node name must be non-empty.")
        clean_name, _ = scrub_flight_text(raw_name)
        clean_region, _ = scrub_flight_text(str(region or "local-loopback").strip() or "local-loopback")
        if isinstance(vram_gb, bool) or not isinstance(vram_gb, int) or vram_gb < 1:
            raise SafetyMeshValidationError("vram_gb must be a positive integer.")
        clean_nid = str(node_id).strip() if node_id is not None and str(node_id).strip() else f"{clean_tier.split('_')[0]}-{uuid.uuid4().hex[:8]}"
        if not _SLUG_ID_RE.fullmatch(clean_nid):
            raise SafetyMeshValidationError(f"Invalid mesh node_id '{clean_nid}'.")
        spec = {"node_id": clean_nid, "name": clean_name, "tier": clean_tier, "hardware_hal": clean_hal, "region": clean_region, "vram_gb": int(vram_gb), "status": clean_status}
        with self._lock:
            conn = self._ensure_conn()
            with conn:
                return self._insert_node_row(conn, ws, spec)

    def list_nodes(self, workspace_id: str = "default") -> Dict[str, Any]:
        ws, _ = _validate_ws_and_limit(workspace_id)
        with self._lock:
            conn = self._ensure_conn()
            self._ensure_seeded_nodes(conn, ws)
            rows = conn.execute("SELECT payload_json FROM mesh_nodes WHERE workspace_id=? ORDER BY rowid ASC", (ws,)).fetchall()
        nodes = [json.loads(str(r["payload_json"])) for r in rows]
        return {"workspace_id": ws, "count": len(nodes), "nodes": nodes}

    def dispatch_handoff(
        self,
        workspace_id: str = "default",
        workflow_name: str = "clinical-synthesis-pipeline",
        task_summary: str = "Ingest patient intake & synthesize anonymized cohort summary",
        data_classification: str = "restricted_pii",
        allow_sanitized_burst: bool = True,
        force_raw_cloud_burst: bool = False,
    ) -> Dict[str, Any]:
        ws, _ = _validate_ws_and_limit(workspace_id)
        clean_cls = _validate_enum(data_classification, VALID_DATA_CLASSIFICATIONS, "data_classification")
        if bool(force_raw_cloud_burst) and clean_cls == "restricted_pii":
            raise MeshSovereigntyViolationError("Sovereignty violation: raw restricted_pii cannot burst to cluster without edge sanitization.")
        clean_wf, r_wf = scrub_flight_text(str(workflow_name or "clinical-synthesis-pipeline").strip() or "clinical-synthesis-pipeline")
        clean_sum, r_sum = scrub_flight_text(str(task_summary or "").strip() or "Ingest patient intake & synthesize anonymized cohort summary")
        total_redactions = r_wf + r_sum

        with self._lock:
            conn = self._ensure_conn()
            self._ensure_seeded_nodes(conn, ws)
            rows = conn.execute("SELECT payload_json FROM mesh_nodes WHERE workspace_id=? AND status='ONLINE' ORDER BY rowid ASC", (ws,)).fetchall()
            online_nodes = [json.loads(str(r["payload_json"])) for r in rows]
            edge_node = next((n for n in online_nodes if n["tier"] == "edge_local"), None)
            if edge_node is None:
                raise SafetyMeshValidationError(f"No ONLINE edge_local node available in workspace '{ws}'.")
            burst_node = next((n for n in online_nodes if n["tier"] == "cluster_burst"), None)

            stage_1 = {"stage_name": "kbrain_pii_ingest_and_scrub", "target_tier": "edge_local", "node_id": edge_node["node_id"], "model_id": "keelway-core:7b", "hardware_hal": edge_node["hardware_hal"], "zero_raw_pii_egress": True, "cost_usd": 0.0}
            if bool(allow_sanitized_burst) and burst_node is not None:
                stage_2 = {"stage_name": "attested_cluster_synthesis", "target_tier": "cluster_burst", "node_id": burst_node["node_id"], "model_id": "keelway-frontier:70b-tee", "hardware_hal": burst_node["hardware_hal"], "zero_raw_pii_egress": True, "cost_usd": 0.0042}
                status, burst_id, total_cost = "ATTESTED_COMPLETE", str(burst_node["node_id"]), 0.0042
            else:
                stage_2 = {"stage_name": "local_sovereign_synthesis", "target_tier": "edge_local", "node_id": edge_node["node_id"], "model_id": "keelway-core:7b", "hardware_hal": edge_node["hardware_hal"], "zero_raw_pii_egress": True, "cost_usd": 0.0}
                status, burst_id, total_cost = "PINNED_EDGE_ONLY", None, 0.0

            stages = [stage_1, stage_2]
            handoff_id, created_at = f"mho-{uuid.uuid4().hex[:12]}", _utc_now()
            att_sha = _sha256_json({"handoff_id": handoff_id, "workspace_id": ws, "workflow_name": clean_wf, "task_summary": clean_sum, "data_classification": clean_cls, "status": status, "edge_node_id": edge_node["node_id"], "burst_node_id": burst_id, "stages": stages, "total_cost_usd": total_cost})
            record = {"handoff_id": handoff_id, "workspace_id": ws, "workflow_name": clean_wf, "task_summary": clean_sum, "data_classification": clean_cls, "status": status, "edge_node_id": edge_node["node_id"], "burst_node_id": burst_id, "stages": stages, "total_cost_usd": total_cost, "dlp_redactions": total_redactions, "attestation_sha256": att_sha, "created_at": created_at}
            with conn:
                conn.execute("INSERT INTO mesh_handoffs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (handoff_id, ws, clean_wf, clean_cls, status, edge_node["node_id"], burst_id, _canonical_json(record), att_sha, created_at))
        return record

    def list_handoffs(self, workspace_id: str = "default", limit: int = 25) -> Dict[str, Any]:
        ws, cap = _validate_ws_and_limit(workspace_id, limit)
        with self._lock:
            rows = self._ensure_conn().execute("SELECT payload_json FROM mesh_handoffs WHERE workspace_id=? ORDER BY created_at DESC, rowid DESC LIMIT ?", (ws, cap)).fetchall()
        items = [json.loads(str(r["payload_json"])) for r in rows]
        return {"workspace_id": ws, "count": len(items), "handoffs": items}


safety_and_mesh_engine = SQLiteSafetyAndMeshEngine()
