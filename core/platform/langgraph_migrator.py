"""
Phase 11A Static LangGraph-to-KFlow AST & Regex Migrator (`core.platform.langgraph_migrator`).

Performs 100% static code analysis (`ast.parse` for Python; deterministic comment-stripped regex
parsing for TypeScript) — NEVER invoking `eval`, `exec`, or `subprocess` — to convert cyclic
LangGraph `StateGraph` definitions into bounded, P-10-governed `KFlowDagEngine` blueprints.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from core.platform.flight_tape import _clean_workspace_id

MAX_MIGRATION_SOURCE_BYTES = 262_144

_START_ALIASES = frozenset({"START", "__start__"})
_END_ALIASES = frozenset({"END", "__end__"})

_LEGACY_ANTI_PATTERNS: Tuple[Tuple[str, str], ...] = (
    (
        "LLMChain",
        "Legacy 'LLMChain' detected: replace wrapper chain with a native Keelway KFlow DAG task node.",
    ),
    (
        "AgentExecutor",
        "Legacy 'AgentExecutor' detected: migrate unbounded agent loop to KFlow DAG with bounded loop policy.",
    ),
    (
        "ConversationChain",
        "Legacy 'ConversationChain' detected: replace mutable chain buffer with scope-governed KBrain memory.",
    ),
    (
        "initialize_agent",
        "Legacy 'initialize_agent' factory detected: migrate to declarative Keelway agent manifest + KFlow DAG.",
    ),
    (
        "initializeAgentExecutorWithOptions",
        "Legacy 'initializeAgentExecutorWithOptions' detected: migrate to typed KFlow blueprint.",
    ),
    (
        "langchain.chains",
        "Legacy 'langchain.chains' import detected: remove deprecated chain abstractions in favor of KFlow steps.",
    ),
    (
        "langchain/chains",
        "Legacy 'langchain/chains' import detected: remove deprecated chain abstractions in favor of KFlow steps.",
    ),
)

_TS_BLOCK_COMMENT_RE = re.compile(r"/\*[\s\S]*?\*/")
_TS_LINE_COMMENT_RE = re.compile(r"//[^\r\n]*")
_TS_STATE_GRAPH_RE = re.compile(r"new\s+StateGraph\s*(?:<[^>]+>)?\s*\(\s*([A-Za-z0-9_$]+)?")
_TS_ADD_NODE_RE = re.compile(
    r"\.addNode\s*\(\s*['\"`]([^'\"`]+)['\"`]\s*,\s*([A-Za-z0-9_$]+|\([^)]*\)\s*=>\s*\{[\s\S]*?\}|async\s*\([^)]*\)\s*=>\s*\{[\s\S]*?\}|function[^)]*\)\s*\{[\s\S]*?\})"
)
_TS_ADD_EDGE_RE = re.compile(
    r"\.addEdge\s*\(\s*(START|END|['\"`][^'\"`]+['\"`])\s*,\s*(START|END|['\"`][^'\"`]+['\"`])\s*\)"
)
_TS_COND_EDGE_OBJ_RE = re.compile(
    r"\.addConditionalEdges\s*\(\s*(START|['\"`][^'\"`]+['\"`])\s*,\s*([A-Za-z0-9_$]+|[^{,]+)\s*,\s*\{([\s\S]*?)\}\s*\)"
)
_TS_COND_EDGE_ARR_RE = re.compile(
    r"\.addConditionalEdges\s*\(\s*(START|['\"`][^'\"`]+['\"`])\s*,\s*([A-Za-z0-9_$]+|[^\[,]+)\s*,\s*\[([\s\S]*?)\]\s*\)"
)
_TS_KV_PAIR_RE = re.compile(r"(['\"`]?[A-Za-z0-9_$-]+['\"`]?)\s*:\s*(START|END|['\"`][^'\"`]+['\"`])")
_TS_TOKEN_ITEM_RE = re.compile(r"(START|END|['\"`][^'\"`]+['\"`])")
_TS_FUNC_DECL_RE = re.compile(
    r"(?:async\s+)?function\s+([A-Za-z0-9_$]+)\s*\([^)]*\)\s*\{([\s\S]*?)\n\}|"
    r"(?:const|let|var)\s+([A-Za-z0-9_$]+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>\s*\{([\s\S]*?)\}"
)
_TS_COMPILE_INTERRUPT_RE = re.compile(r"interrupt(?:Before|After)\s*:\s*\[([^\]]*)\]")
_TS_INTERRUPT_CALL_RE = re.compile(r"\b(?:interrupt|NodeInterrupt)\s*\(")


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _normalize_endpoint(raw: str) -> str:
    val = raw.strip().strip("'\"`")
    if val in _START_ALIASES:
        return "START"
    if val in _END_ALIASES:
        return "END"
    return val


def _slugify_workflow_name(raw_name: Optional[str], fallback_hint: Optional[str] = None) -> str:
    candidate = str(raw_name or "").strip() or str(fallback_hint or "").strip() or "langgraph-migrated-workflow"
    slug = re.sub(r"[^a-z0-9]+", "-", candidate.lower()).strip("-")
    return slug or "langgraph-migrated-workflow"


def _ast_contains_interrupt(node: ast.AST) -> bool:
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call):
            fn = sub.func
            if isinstance(fn, ast.Name) and fn.id in ("interrupt", "NodeInterrupt"):
                return True
            if isinstance(fn, ast.Attribute) and fn.attr in ("interrupt", "NodeInterrupt"):
                return True
        elif isinstance(sub, ast.Raise) and sub.exc is not None:
            if isinstance(sub.exc, ast.Name) and sub.exc.id == "NodeInterrupt":
                return True
    return False


def _ast_called_names(node: ast.AST) -> Set[str]:
    names: Set[str] = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name):
            names.add(sub.func.id)
    return names


def _resolve_ast_endpoint(expr: ast.AST) -> Optional[str]:
    if isinstance(expr, ast.Constant) and isinstance(expr.value, str):
        return _normalize_endpoint(expr.value)
    if isinstance(expr, ast.Name) and expr.id in ("START", "END"):
        return expr.id
    if isinstance(expr, ast.Attribute) and expr.attr in ("START", "END"):
        return expr.attr
    return None


def _resolve_ast_endpoint_list(expr: ast.AST) -> List[str]:
    single = _resolve_ast_endpoint(expr)
    if single is not None:
        return [single]
    if isinstance(expr, (ast.List, ast.Tuple, ast.Set)):
        out: List[str] = []
        for elt in expr.elts:
            resolved = _resolve_ast_endpoint(elt)
            if resolved:
                out.append(resolved)
        return out
    return []


def _extract_router_return_targets(fn_node: ast.AST) -> List[str]:
    targets: List[str] = []
    for sub in ast.walk(fn_node):
        if isinstance(sub, ast.Return) and sub.value is not None:
            for cand in _resolve_ast_endpoint_list(sub.value):
                if cand not in targets:
                    targets.append(cand)
            if isinstance(sub.value, ast.IfExp):
                for branch in (sub.value.body, sub.value.orelse):
                    for cand in _resolve_ast_endpoint_list(branch):
                        if cand not in targets:
                            targets.append(cand)
    return targets


def _collect_legacy_warnings_python(tree: ast.AST) -> List[str]:
    found_tokens: Set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found_tokens.add(alias.name)
                for part in alias.name.split("."):
                    found_tokens.add(part)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            found_tokens.add(mod)
            if mod.startswith("langchain.chains"):
                found_tokens.add("langchain.chains")
            for alias in node.names:
                found_tokens.add(alias.name)
        elif isinstance(node, ast.Name):
            found_tokens.add(node.id)
        elif isinstance(node, ast.Attribute):
            found_tokens.add(node.attr)

    warnings: List[str] = []
    for symbol, message in _LEGACY_ANTI_PATTERNS:
        if symbol in found_tokens and message not in warnings:
            warnings.append(message)
    return warnings


def _parse_python_langgraph(
    source_code: str,
) -> Tuple[List[Dict[str, str]], List[Dict[str, Any]], Set[str], List[str], Optional[str]]:
    try:
        tree = ast.parse(source_code)
    except SyntaxError as exc:
        line_info = f" at line {exc.lineno}" if exc.lineno else ""
        raise ValueError(f"Invalid Python syntax{line_info}: {exc.msg}") from exc

    func_defs: Dict[str, ast.AST] = {}
    interrupt_funcs: Set[str] = set()
    func_calls: Dict[str, Set[str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            func_defs[node.name] = node
            func_calls[node.name] = _ast_called_names(node)
            if _ast_contains_interrupt(node):
                interrupt_funcs.add(node.name)

    changed = True
    while changed:
        changed = False
        for fname, callees in func_calls.items():
            if fname not in interrupt_funcs and (callees & interrupt_funcs):
                interrupt_funcs.add(fname)
                changed = True

    raw_nodes: List[Dict[str, str]] = []
    seen_nodes: Set[str] = set()
    raw_edges: List[Dict[str, Any]] = []
    p10_nodes: Set[str] = set()
    state_hint: Optional[str] = None

    def _ensure_node(nid: str, handler: str = "") -> None:
        if nid in ("START", "END") or not nid:
            return
        if nid not in seen_nodes:
            seen_nodes.add(nid)
            raw_nodes.append({"id": nid, "handler": handler or nid})

    for stmt in ast.walk(tree):
        if not isinstance(stmt, ast.Call):
            continue
        func = stmt.func
        if isinstance(func, ast.Name) and func.id == "StateGraph" and stmt.args:
            arg0 = stmt.args[0]
            if isinstance(arg0, ast.Name):
                state_hint = arg0.id
        elif isinstance(func, ast.Attribute) and func.attr == "StateGraph" and stmt.args:
            arg0 = stmt.args[0]
            if isinstance(arg0, ast.Name):
                state_hint = arg0.id

        if not isinstance(func, ast.Attribute):
            continue
        method = func.attr

        if method == "add_node" and stmt.args:
            if len(stmt.args) == 1 and isinstance(stmt.args[0], ast.Name):
                nid = stmt.args[0].id
                handler_name = nid
                handler_ast: Optional[ast.AST] = stmt.args[0]
            else:
                resolved_nid = _resolve_ast_endpoint(stmt.args[0])
                if not resolved_nid:
                    continue
                nid = resolved_nid
                handler_ast = stmt.args[1] if len(stmt.args) >= 2 else None
                handler_name = handler_ast.id if isinstance(handler_ast, ast.Name) else nid
            _ensure_node(nid, handler_name)
            if handler_name in interrupt_funcs or (handler_ast is not None and _ast_contains_interrupt(handler_ast)):
                p10_nodes.add(nid)

        elif method == "add_edge" and len(stmt.args) >= 2:
            sources = _resolve_ast_endpoint_list(stmt.args[0])
            target = _resolve_ast_endpoint(stmt.args[1])
            if target:
                for src in sources:
                    _ensure_node(src)
                    _ensure_node(target)
                    raw_edges.append({"source": src, "target": target, "conditional": False, "condition": None})

        elif method == "set_entry_point" and stmt.args:
            target = _resolve_ast_endpoint(stmt.args[0])
            if target:
                _ensure_node(target)
                raw_edges.append({"source": "START", "target": target, "conditional": False, "condition": None})

        elif method == "set_finish_point" and stmt.args:
            src = _resolve_ast_endpoint(stmt.args[0])
            if src:
                _ensure_node(src)
                raw_edges.append({"source": src, "target": "END", "conditional": False, "condition": None})

        elif method == "add_conditional_edges" and len(stmt.args) >= 2:
            src = _resolve_ast_endpoint(stmt.args[0])
            if not src:
                continue
            _ensure_node(src)
            router_arg = stmt.args[1]
            router_name = router_arg.id if isinstance(router_arg, ast.Name) else "router"
            map_arg: Optional[ast.AST] = stmt.args[2] if len(stmt.args) >= 3 else None
            if map_arg is None:
                for kw in stmt.keywords:
                    if kw.arg in ("path_map", "then"):
                        map_arg = kw.value
                        break

            if isinstance(map_arg, ast.Dict):
                for k_ast, v_ast in zip(map_arg.keys, map_arg.values):
                    if v_ast is None:
                        continue
                    target = _resolve_ast_endpoint(v_ast)
                    cond_key = _resolve_ast_endpoint(k_ast) if k_ast is not None else "branch"
                    if target:
                        _ensure_node(target)
                        raw_edges.append(
                            {
                                "source": src,
                                "target": target,
                                "conditional": True,
                                "condition": f"{router_name}:{cond_key or 'branch'}",
                            }
                        )
            elif isinstance(map_arg, (ast.List, ast.Tuple, ast.Set)):
                for target in _resolve_ast_endpoint_list(map_arg):
                    _ensure_node(target)
                    raw_edges.append(
                        {"source": src, "target": target, "conditional": True, "condition": f"{router_name}:{target}"}
                    )
            elif router_name in func_defs:
                for target in _extract_router_return_targets(func_defs[router_name]):
                    _ensure_node(target)
                    raw_edges.append(
                        {"source": src, "target": target, "conditional": True, "condition": f"{router_name}:{target}"}
                    )

        elif method == "compile":
            for kw in stmt.keywords:
                if kw.arg in ("interrupt_before", "interrupt_after") and kw.value is not None:
                    for gated_nid in _resolve_ast_endpoint_list(kw.value):
                        if gated_nid not in ("START", "END"):
                            _ensure_node(gated_nid)
                            p10_nodes.add(gated_nid)

    warnings = _collect_legacy_warnings_python(tree)
    return raw_nodes, raw_edges, p10_nodes, warnings, state_hint


def _parse_typescript_langgraph(
    source_code: str,
) -> Tuple[List[Dict[str, str]], List[Dict[str, Any]], Set[str], List[str], Optional[str]]:
    clean = _TS_BLOCK_COMMENT_RE.sub("", source_code)
    clean = _TS_LINE_COMMENT_RE.sub("", clean)

    state_match = _TS_STATE_GRAPH_RE.search(clean)
    state_hint = state_match.group(1) if state_match and state_match.group(1) else None

    interrupt_funcs: Set[str] = set()
    for fm in _TS_FUNC_DECL_RE.finditer(clean):
        fname = fm.group(1) or fm.group(3) or ""
        fbody = fm.group(2) or fm.group(4) or ""
        if fname and _TS_INTERRUPT_CALL_RE.search(fbody):
            interrupt_funcs.add(fname)

    raw_nodes: List[Dict[str, str]] = []
    seen_nodes: Set[str] = set()
    raw_edges: List[Dict[str, Any]] = []
    p10_nodes: Set[str] = set()

    def _ensure_node(nid: str, handler: str = "") -> None:
        if nid in ("START", "END") or not nid:
            return
        if nid not in seen_nodes:
            seen_nodes.add(nid)
            raw_nodes.append({"id": nid, "handler": handler or nid})

    for nm in _TS_ADD_NODE_RE.finditer(clean):
        nid = _normalize_endpoint(nm.group(1))
        rhs = nm.group(2).strip()
        handler = rhs if re.fullmatch(r"[A-Za-z0-9_$]+", rhs) else nid
        _ensure_node(nid, handler)
        if handler in interrupt_funcs or _TS_INTERRUPT_CALL_RE.search(rhs):
            p10_nodes.add(nid)

    for em in _TS_ADD_EDGE_RE.finditer(clean):
        src = _normalize_endpoint(em.group(1))
        dst = _normalize_endpoint(em.group(2))
        _ensure_node(src)
        _ensure_node(dst)
        raw_edges.append({"source": src, "target": dst, "conditional": False, "condition": None})

    for cm in _TS_COND_EDGE_OBJ_RE.finditer(clean):
        src = _normalize_endpoint(cm.group(1))
        router_raw = cm.group(2).strip()
        router_name = router_raw if re.fullmatch(r"[A-Za-z0-9_$]+", router_raw) else "router"
        _ensure_node(src)
        for kv in _TS_KV_PAIR_RE.finditer(cm.group(3)):
            cond_key = _normalize_endpoint(kv.group(1))
            dst = _normalize_endpoint(kv.group(2))
            _ensure_node(dst)
            raw_edges.append(
                {"source": src, "target": dst, "conditional": True, "condition": f"{router_name}:{cond_key}"}
            )

    for am in _TS_COND_EDGE_ARR_RE.finditer(clean):
        src = _normalize_endpoint(am.group(1))
        router_raw = am.group(2).strip()
        router_name = router_raw if re.fullmatch(r"[A-Za-z0-9_$]+", router_raw) else "router"
        _ensure_node(src)
        for tok in _TS_TOKEN_ITEM_RE.finditer(am.group(3)):
            dst = _normalize_endpoint(tok.group(1))
            _ensure_node(dst)
            raw_edges.append({"source": src, "target": dst, "conditional": True, "condition": f"{router_name}:{dst}"})

    for im in _TS_COMPILE_INTERRUPT_RE.finditer(clean):
        for tok in _TS_TOKEN_ITEM_RE.finditer(im.group(1)):
            gated_nid = _normalize_endpoint(tok.group(1))
            if gated_nid not in ("START", "END"):
                _ensure_node(gated_nid)
                p10_nodes.add(gated_nid)

    warnings: List[str] = []
    for symbol, message in _LEGACY_ANTI_PATTERNS:
        if re.search(rf"(?<![A-Za-z0-9_]){re.escape(symbol)}(?![A-Za-z0-9_])", clean) and message not in warnings:
            warnings.append(message)

    return raw_nodes, raw_edges, p10_nodes, warnings, state_hint


def _detect_cycles_and_back_edges(
    node_ids: List[str],
    edges: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], Set[Tuple[str, str]]]:
    adj: Dict[str, List[str]] = {nid: [] for nid in node_ids}
    entry_nodes: List[str] = []
    for e in edges:
        src, dst = e["source"], e["target"]
        if src == "START" and dst in adj and dst not in entry_nodes:
            entry_nodes.append(dst)
        elif src in adj and dst in adj and dst not in adj[src]:
            adj[src].append(dst)

    roots = entry_nodes + [nid for nid in node_ids if nid not in entry_nodes]
    visited: Set[str] = set()
    on_stack: List[str] = []
    on_stack_set: Set[str] = set()
    back_edges: Set[Tuple[str, str]] = set()
    policies: List[Dict[str, Any]] = []
    seen_cycles: Set[Tuple[str, ...]] = set()

    def _dfs(u: str) -> None:
        visited.add(u)
        on_stack.append(u)
        on_stack_set.add(u)
        for v in adj.get(u, []):
            if v in on_stack_set:
                back_edges.add((u, v))
                idx = on_stack.index(v)
                cycle_path = on_stack[idx:] + [v]
                cycle_key = tuple(cycle_path)
                if cycle_key not in seen_cycles:
                    seen_cycles.add(cycle_key)
                    policies.append(
                        {
                            "cycle_path": cycle_path,
                            "from_node": u,
                            "to_node": v,
                            "back_edge": {"source": u, "target": v},
                            "max_iterations": 5,
                            "timeout_seconds": 60,
                        }
                    )
            elif v not in visited:
                _dfs(v)
        on_stack.pop()
        on_stack_set.remove(u)

    for root in roots:
        if root not in visited:
            _dfs(root)

    return policies, back_edges


def _build_topological_kflow_blueprint(
    nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
    back_edges: Set[Tuple[str, str]],
) -> List[Dict[str, Any]]:
    if not nodes:
        return []
    order = [n["id"] for n in nodes]
    by_id = {n["id"]: n for n in nodes}
    deps: Dict[str, List[str]] = {nid: [] for nid in order}
    retry_sources: Dict[str, List[str]] = {}

    for e in edges:
        src, dst = e["source"], e["target"]
        if src in ("START", "END") or dst in ("START", "END"):
            continue
        if (src, dst) in back_edges:
            retry_sources.setdefault(dst, [])
            if src not in retry_sources[dst]:
                retry_sources[dst].append(src)
        elif src in by_id and dst in by_id and src not in deps[dst]:
            deps[dst].append(src)

    in_deg: Dict[str, int] = {nid: len(deps[nid]) for nid in order}
    children: Dict[str, List[str]] = {nid: [] for nid in order}
    for nid in order:
        for d in deps[nid]:
            children[d].append(nid)

    topo: List[str] = []
    ready = [nid for nid in order if in_deg[nid] == 0]
    while ready:
        cur = ready.pop(0)
        topo.append(cur)
        newly_ready: Set[str] = set()
        for ch in children[cur]:
            in_deg[ch] -= 1
            if in_deg[ch] == 0:
                newly_ready.add(ch)
        for nid in order:
            if nid in newly_ready and nid not in ready:
                ready.append(nid)

    for nid in order:
        if nid not in topo:
            topo.append(nid)

    blueprint: List[Dict[str, Any]] = []
    for nid in topo:
        n_meta = by_id[nid]
        is_p10 = bool(n_meta["requires_p10"])
        entry: Dict[str, Any] = {
            "id": nid,
            "label": n_meta["label"],
            "agent_id": "p10-governance-gate" if is_p10 else "workflow-orchestrator",
            "kind": n_meta["kind"],
            "depends_on": deps[nid],
            "requires_p10": is_p10,
        }
        if nid in retry_sources:
            entry["bounded_retry"] = {
                "max_iterations": 5,
                "timeout_seconds": 60,
                "retry_from": retry_sources[nid],
            }
        blueprint.append(entry)
    return blueprint


def _render_sdk_snippet(
    workspace_id: str,
    workflow_name: str,
    blueprint: List[Dict[str, Any]],
    p10_gates: List[str],
) -> str:
    bp_literal = json.dumps(blueprint, indent=4)
    p10_comment = (
        f"# P-10 human governance gates injected for: {', '.join(p10_gates)}\n" if p10_gates else ""
    )
    return (
        "from core.sdk.client import KeelwayClient\n\n"
        f"{p10_comment}"
        f"KFLOW_BLUEPRINT = {bp_literal}\n\n"
        "with KeelwayClient() as client:\n"
        "    run = client.platform.execute_kflow_dag(\n"
        f'        workspace_id="{workspace_id}",\n'
        f'        workflow_id="{workflow_name}",\n'
        "        nodes=KFLOW_BLUEPRINT,\n"
        "        token_budget=25000,\n"
        "    )\n"
        '    print(run["run_id"], run["status"])\n'
    )


class LangGraphMigrator:
    """Deterministic, zero-execution static AST/Regex migrator from LangGraph `StateGraph` to KFlow DAG."""

    def migrate_source(
        self,
        source_code: str,
        source_language: str = "python",
        workflow_name: Optional[str] = None,
        workspace_id: str = "default",
    ) -> Dict[str, Any]:
        ws = _clean_workspace_id(workspace_id)
        if not isinstance(source_code, str) or not source_code.strip():
            raise ValueError("source_code must be a non-empty string.")
        encoded_bytes = len(source_code.encode("utf-8"))
        if encoded_bytes > MAX_MIGRATION_SOURCE_BYTES:
            raise ValueError(
                f"source_code exceeds maximum static analysis limit of {MAX_MIGRATION_SOURCE_BYTES} bytes."
            )

        lang_raw = str(source_language or "python").strip().lower()
        if lang_raw in ("python", "py"):
            lang = "python"
            raw_nodes, edges, p10_set, warnings, state_hint = _parse_python_langgraph(source_code)
        elif lang_raw in ("typescript", "ts"):
            lang = "typescript"
            raw_nodes, edges, p10_set, warnings, state_hint = _parse_typescript_langgraph(source_code)
        else:
            raise ValueError(f"Unsupported source_language '{source_language}'. Expected 'python' or 'typescript'.")

        wf_name = _slugify_workflow_name(workflow_name, state_hint)
        p10_gates_injected = [n["id"] for n in raw_nodes if n["id"] in p10_set]
        nodes: List[Dict[str, Any]] = [
            {
                "id": n["id"],
                "label": n["id"],
                "handler": n["handler"],
                "kind": "p10_human_gate" if n["id"] in p10_set else "task",
                "requires_p10": n["id"] in p10_set,
            }
            for n in raw_nodes
        ]

        bounded_loop_policies, back_edges = _detect_cycles_and_back_edges([n["id"] for n in nodes], edges)
        annotated_edges = [{**e, "is_back_edge": (e["source"], e["target"]) in back_edges} for e in edges]
        kflow_blueprint = _build_topological_kflow_blueprint(nodes, annotated_edges, back_edges)
        generated_sdk_code = _render_sdk_snippet(ws, wf_name, kflow_blueprint, p10_gates_injected)

        migration_sha256 = "sha256:" + hashlib.sha256(
            _canonical_json(
                {
                    "bounded_loop_policies": bounded_loop_policies,
                    "edges": annotated_edges,
                    "kflow_blueprint": kflow_blueprint,
                    "legacy_warnings": warnings,
                    "nodes": nodes,
                    "p10_gates_injected": p10_gates_injected,
                    "source_language": lang,
                    "workflow_name": wf_name,
                    "workspace_id": ws,
                }
            ).encode("utf-8")
        ).hexdigest()

        return {
            "workspace_id": ws,
            "workflow_name": wf_name,
            "source_language": lang,
            "nodes": nodes,
            "edges": annotated_edges,
            "cycles_detected": len(bounded_loop_policies),
            "bounded_loop_policies": bounded_loop_policies,
            "p10_gates_injected": p10_gates_injected,
            "legacy_warnings": warnings,
            "kflow_blueprint": kflow_blueprint,
            "generated_sdk_code": generated_sdk_code,
            "migration_sha256": migration_sha256,
        }


langgraph_migrator = LangGraphMigrator()
