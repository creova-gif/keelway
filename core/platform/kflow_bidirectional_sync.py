"""
Phase 12A Bidirectional KFlow Code <-> Graph AST Sync Engine (`core.platform.kflow_bidirectional_sync`).

Performs 100% static bidirectional AST/lexer synchronization (`ast.parse` for Python; string/comment-aware
balanced delimiter lexer for TypeScript — zero `eval()` or `exec()`) between developer source code and
deterministic topological KFlow DAG nodes, wave layouts, cycle back-edges, and P-10 human governance locks,
with optional crash-safe SQLite WAL persistence (`platform_studio_kflow_syncs`).
"""

from __future__ import annotations

import ast
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import threading
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union

from core.platform.flight_tape import _clean_workspace_id
from core.platform.kbrain_khub import resolve_kbrain_db_target

MAX_SOURCE_CODE_BYTES = 262_144
VALID_SYNC_DIRECTIONS = frozenset({"code_to_graph", "graph_to_code"})
VALID_SYNC_LANGUAGES = frozenset({"python", "typescript"})
_START_END_TOKENS = frozenset({"START", "__start__", "END", "__end__"})
_P10_COMMENT_RE = re.compile(r"(?i)\bp-?10\b.*(?:gate|approv|human|lock)|human\s+gate\s+required")
_IDENT_CLEAN_RE = re.compile(r"[^A-Za-z0-9_]+")

_TS_BP_DECL_RE = re.compile(r"\b(?:KFLOW_BLUEPRINT|BLUEPRINT)\b[^=\n]*=\s*\[")
_TS_SDK_NODES_RE = re.compile(
    r"\b(?:executeKflowDag|syncKflowStudio|execute_kflow_dag|sync_kflow_studio)\s*\([\s\S]*?\bnodes\s*:\s*\["
)
_TS_ADD_NODE_CALL_RE = re.compile(r"\.addNode\s*\(\s*(['\"`][^'\"`]+['\"`]|[A-Za-z_$][A-Za-z0-9_$]*)")
_TS_ADD_EDGE_CALL_RE = re.compile(
    r"\.addEdge\s*\(\s*(START|END|['\"`][^'\"`]+['\"`])\s*,\s*(START|END|['\"`][^'\"`]+['\"`])\s*\)"
)
_TS_COND_EDGE_CALL_RE = re.compile(r"\.addConditionalEdges\s*\(\s*(START|['\"`][^'\"`]+['\"`]|\w+)\s*,")
_TS_COMPILE_INT_RE = re.compile(r"interrupt(?:Before|After)\s*:\s*\[([^\]]*)\]")
_TS_FUNC_HEADER_RE = re.compile(
    r"(?:(export)\s+)?(?:async\s+)?function\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*\([^)]*\)\s*(?::[^{]+)?\{|"
    r"(?:(export)\s+)?(?:const|let|var)\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*(?::[^=]+)?=\s*(?:async\s*)?\([^)]*\)\s*(?::[^=]+)?=>\s*\{"
)
_TS_INTERRUPT_RE = re.compile(r"\b(?:interrupt|NodeInterrupt)\s*\(")
_TS_STRING_TOKEN_RE = re.compile(r"START|END|['\"`]([^'\"`]+)['\"`]")

_KFLOW_SYNC_SCHEMA_SQL = (
    "CREATE TABLE IF NOT EXISTS platform_studio_kflow_syncs ("
    "id INTEGER PRIMARY KEY AUTOINCREMENT, workspace_id TEXT NOT NULL, workflow_id TEXT NOT NULL, "
    "direction TEXT NOT NULL, language TEXT NOT NULL, nodes_json TEXT NOT NULL, edges_json TEXT NOT NULL, "
    "cycle_back_edges_json TEXT NOT NULL, p10_locked_nodes_json TEXT NOT NULL, source_code TEXT NOT NULL, "
    "sync_sha256 TEXT NOT NULL, synced_at TEXT NOT NULL); "
    "CREATE INDEX IF NOT EXISTS idx_platform_studio_kflow_syncs_ws "
    "ON platform_studio_kflow_syncs(workspace_id, workflow_id, synced_at DESC);"
)


class PayloadTooLargeError(ValueError):
    """Raised when `source_code` exceeds the 262,144-byte static analysis safety ceiling."""


def resolve_studio_db_target(db_path: Optional[Union[str, Path]] = None) -> Tuple[Union[str, Path], str]:
    """Resolve SQLite WAL target honoring explicit `db_path`, `KEELWAY_PLATFORM_DB_PATH`, or runtime defaults."""
    if db_path is not None:
        return resolve_kbrain_db_target(db_path)
    platform_override = os.environ.get("KEELWAY_PLATFORM_DB_PATH", "").strip()
    return resolve_kbrain_db_target(platform_override if platform_override else None)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _humanize_label(raw_id: str) -> str:
    parts = [p for p in re.split(r"[_\-\s]+", raw_id.strip()) if p]
    return " ".join(p.capitalize() for p in parts) if parts else raw_id


def _safe_ident(raw_id: str) -> str:
    cleaned = _IDENT_CLEAN_RE.sub("_", raw_id.strip()).strip("_") or "node"
    return f"n_{cleaned}" if cleaned[0].isdigit() else cleaned


def _offset_to_line(text: str, offset: int) -> int:
    return 1 + text.count("\n", 0, max(0, min(offset, len(text))))


def _lines_slice_has_p10(lines: Sequence[str], line_start: int, line_end: int) -> bool:
    lo, hi = max(1, line_start) - 1, min(len(lines), max(line_start, line_end))
    return any(_P10_COMMENT_RE.search(lines[i]) for i in range(lo, hi))


def _make_raw_node(nid: str, label: str, agent_id: str, p10: bool, l_start: int, l_end: int) -> Dict[str, Any]:
    return {
        "id": nid, "label": label or _humanize_label(nid), "agent_id": agent_id or "workflow-orchestrator",
        "requires_p10": bool(p10), "line_start": int(l_start), "line_end": int(l_end),
    }


def _ast_const_val(node: Optional[ast.AST]) -> Any:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, (ast.List, ast.Tuple)):
        return [_ast_const_val(elt) for elt in node.elts]
    if isinstance(node, ast.Dict):
        return {
            k_val: _ast_const_val(v_node)
            for k_node, v_node in zip(node.keys, node.values, strict=True)
            if isinstance((k_val := _ast_const_val(k_node)), str)
        }
    return None


def _ast_has_interrupt(node: ast.AST) -> bool:
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call):
            fn = sub.func
            if (isinstance(fn, ast.Name) and fn.id in ("interrupt", "NodeInterrupt")) or (
                isinstance(fn, ast.Attribute) and fn.attr in ("interrupt", "NodeInterrupt")
            ):
                return True
        elif isinstance(sub, ast.Raise) and isinstance(sub.exc, ast.Name) and sub.exc.id == "NodeInterrupt":
            return True
    return False


def _ast_endpoint_name(node: ast.AST) -> Optional[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value.strip()
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute) and node.attr in ("START", "END"):
        return node.attr
    return None


def _find_python_blueprint_list(tree: ast.Module) -> Optional[ast.List]:
    fallback: Optional[ast.List] = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.List):
            names = {t.id for t in node.targets if isinstance(t, ast.Name)}
            if names & {"KFLOW_BLUEPRINT", "BLUEPRINT"}:
                return node.value
            fallback = fallback or (node.value if "nodes" in names else None)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and isinstance(node.value, ast.List):
            if node.target.id in ("KFLOW_BLUEPRINT", "BLUEPRINT"):
                return node.value
            fallback = fallback or (node.value if node.target.id == "nodes" else None)
        elif isinstance(node, ast.Call):
            fn_name = node.func.attr if isinstance(node.func, ast.Attribute) else (node.func.id if isinstance(node.func, ast.Name) else "")
            if fn_name in ("execute_kflow_dag", "sync_kflow_studio", "sync"):
                for kw in node.keywords:
                    if kw.arg == "nodes" and isinstance(kw.value, ast.List):
                        return kw.value
                for arg in node.args:
                    if isinstance(arg, ast.List) and arg.elts and all(isinstance(e, ast.Dict) for e in arg.elts):
                        return arg
    return fallback


def _extract_python_code_to_graph(source_code: str) -> Tuple[List[Dict[str, Any]], List[Tuple[str, str]]]:
    tree, lines = ast.parse(source_code), source_code.splitlines()
    func_defs = {s.name: s for s in ast.walk(tree) if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef))}
    top_funcs = [s for s in tree.body if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef)) and not s.name.startswith("__")]
    fn_calls = {n: {c.func.id for c in ast.walk(fn) if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)} for n, fn in func_defs.items()}
    interrupt_fns = {n for n, fn in func_defs.items() if _ast_has_interrupt(fn) or _lines_slice_has_p10(lines, fn.lineno, getattr(fn, "end_lineno", None) or fn.lineno)}
    while any(fn not in interrupt_fns and (cs & interrupt_fns) and not interrupt_fns.add(fn) for fn, cs in fn_calls.items()):  # type: ignore[func-returns-value]
        pass

    bp_list = _find_python_blueprint_list(tree)
    if bp_list is not None and bp_list.elts and all(isinstance(e, ast.Dict) for e in bp_list.elts):
        extracted_nodes: List[Dict[str, Any]] = []
        directed_edges: List[Tuple[str, str]] = []
        for idx, elt in enumerate(bp_list.elts):
            parsed = _ast_const_val(elt)
            if not isinstance(parsed, dict):
                continue
            nid = str(parsed.get("id") or f"step_{idx + 1}").strip()
            raw_deps = parsed.get("depends_on") if isinstance(parsed.get("depends_on"), list) else parsed.get("dependsOn")
            l_start, l_end = int(elt.lineno), int(getattr(elt, "end_lineno", None) or elt.lineno)
            req_p10 = bool(parsed.get("requires_p10") or parsed.get("requiresP10") or parsed.get("p10")) or _lines_slice_has_p10(lines, l_start, l_end) or nid in interrupt_fns or f"step_{_safe_ident(nid)}" in interrupt_fns
            extracted_nodes.append(_make_raw_node(nid, str(parsed.get("label") or _humanize_label(nid)).strip(), str(parsed.get("agent_id") or parsed.get("agentId") or "workflow-orchestrator").strip(), req_p10, l_start, l_end))
            directed_edges.extend((str(d).strip(), nid) for d in (raw_deps or []) if str(d).strip())
        if extracted_nodes:
            return extracted_nodes, directed_edges

    lg_nodes: Dict[str, Dict[str, Any]] = {}
    lg_order: List[str] = []
    lg_edges: List[Tuple[str, str]] = []
    compile_p10: Set[str] = set()
    has_graph_api = False

    def _ensure_lg(nid: str, l_start: int, l_end: int, p10: bool = False, agent_id: str = "langgraph-node") -> None:
        if not nid or nid in _START_END_TOKENS:
            return
        if nid not in lg_nodes:
            lg_order.append(nid)
            lg_nodes[nid] = _make_raw_node(nid, _humanize_label(nid), agent_id, p10, l_start, l_end)
        elif p10:
            lg_nodes[nid]["requires_p10"] = True

    for call in sorted((c for c in ast.walk(tree) if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)), key=lambda c: int(getattr(c, "lineno", 0))):
        method = getattr(call.func, "attr", "")
        c_start = int(getattr(call, "lineno", 1))
        c_end = int(getattr(call, "end_lineno", None) or c_start)

        if method == "node":
            has_graph_api = True
            kw_map = {kw.arg: _ast_const_val(kw.value) for kw in call.keywords if kw.arg}
            if call.args and isinstance(call.args[0], ast.Dict) and isinstance((d_arg := _ast_const_val(call.args[0])), dict):
                kw_map = {**d_arg, **kw_map}
            nid = str(kw_map.get("id") or "").strip()
            if nid:
                lbl = str(kw_map.get("label") or _humanize_label(nid)).strip()
                ag = str(kw_map.get("agent_id") or kw_map.get("agentId") or "workflow-orchestrator").strip()
                p10 = bool(kw_map.get("requires_p10") or kw_map.get("requiresP10")) or _lines_slice_has_p10(lines, c_start, c_end)
                if nid not in lg_nodes:
                    lg_order.append(nid)
                lg_nodes[nid] = _make_raw_node(nid, lbl, ag, p10, c_start, c_end)
                deps = kw_map.get("depends_on") if isinstance(kw_map.get("depends_on"), list) else kw_map.get("dependsOn")
                lg_edges.extend((str(d).strip(), nid) for d in (deps or []) if str(d).strip())
        elif method in ("cycle", "add_cycle_policy", "addCycle"):
            has_graph_api = True
            kw_map = {kw.arg: _ast_const_val(kw.value) for kw in call.keywords if kw.arg}
            src: Optional[str] = str(kw_map.get("from_node") or kw_map.get("from") or "").strip()
            dst: Optional[str] = str(kw_map.get("to_node") or kw_map.get("to") or "").strip()
            if src and dst:
                lg_edges.append((src, dst))
        elif method == "add_node" and call.args:
            has_graph_api = True
            if len(call.args) == 1 and isinstance(call.args[0], ast.Name):
                nid, handler_name = call.args[0].id, call.args[0].id
                handler_node: Optional[ast.expr] = call.args[0]
            else:
                cand_nid = _ast_endpoint_name(call.args[0])
                if not cand_nid:
                    continue
                nid = cand_nid
                handler_node = call.args[1] if len(call.args) >= 2 else None
                handler_name = handler_node.id if isinstance(handler_node, ast.Name) else nid
            fn_def = func_defs.get(handler_name)
            n_start = int(fn_def.lineno) if fn_def is not None else c_start
            n_end = int(getattr(fn_def, "end_lineno", None) or fn_def.lineno) if fn_def is not None else c_end
            is_p10 = handler_name in interrupt_fns or (handler_node is not None and _ast_has_interrupt(handler_node)) or _lines_slice_has_p10(lines, c_start, c_end)
            _ensure_lg(nid, n_start, n_end, is_p10, agent_id=handler_name)
        elif method == "add_edge" and len(call.args) >= 2:
            has_graph_api = True
            src, dst = _ast_endpoint_name(call.args[0]), _ast_endpoint_name(call.args[1])
            _ensure_lg(src or "", c_start, c_end)
            _ensure_lg(dst or "", c_start, c_end)
            if src and dst and src not in _START_END_TOKENS and dst not in _START_END_TOKENS:
                lg_edges.append((src, dst))
        elif method == "add_conditional_edges" and len(call.args) >= 2:
            has_graph_api = True
            src = _ast_endpoint_name(call.args[0])
            if not src or src in _START_END_TOKENS:
                continue
            _ensure_lg(src, c_start, c_end)
            targets: List[str] = []
            map_arg = call.args[2] if len(call.args) >= 3 else next((kw.value for kw in call.keywords if kw.arg in ("path_map", "then")), None)
            if isinstance(map_arg, ast.Dict):
                targets.extend(r for v in map_arg.values if (r := _ast_endpoint_name(v)))
            elif isinstance(map_arg, (ast.List, ast.Tuple, ast.Set)):
                targets.extend(r for e in map_arg.elts if (r := _ast_endpoint_name(e)))
            elif isinstance(call.args[1], ast.Name) and call.args[1].id in func_defs:
                targets.extend(
                    r for ret in ast.walk(func_defs[call.args[1].id])
                    if isinstance(ret, ast.Return) and ret.value is not None and (r := _ast_endpoint_name(ret.value))
                )
            for tgt in targets:
                if tgt not in _START_END_TOKENS:
                    _ensure_lg(tgt, c_start, c_end)
                    lg_edges.append((src, tgt))
        elif method == "compile":
            for kw in call.keywords:
                if kw.arg in ("interrupt_before", "interrupt_after") and isinstance(kw.value, (ast.List, ast.Tuple)):
                    compile_p10.update(r for elt in kw.value.elts if (r := _ast_endpoint_name(elt)))

    if has_graph_api and lg_order:
        for p10_id in compile_p10:
            if p10_id in lg_nodes:
                lg_nodes[p10_id]["requires_p10"] = True
        return [lg_nodes[nid] for nid in lg_order], lg_edges

    public_funcs = [f for f in top_funcs if not f.name.startswith("_")] or top_funcs
    if len(public_funcs) >= 3 and public_funcs[-1].name == "main":
        if len(fn_calls.get("main", set()) & {f.name for f in public_funcs[:-1]}) >= 2:
            public_funcs = public_funcs[:-1]
    if not public_funcs:
        raise ValueError("No KFlow blueprint, StateGraph nodes, or step functions found in Python source_code.")

    fn_names = {f.name for f in public_funcs}
    fn_nodes = [
        _make_raw_node(f.name, _humanize_label(f.name), "python-step-agent", f.name in interrupt_fns, int(f.lineno), int(getattr(f, "end_lineno", None) or f.lineno))
        for f in public_funcs
    ]
    inter_edges = [(callee, f.name) for f in public_funcs for callee in sorted(fn_calls.get(f.name, set()) & fn_names) if callee != f.name]
    if not inter_edges:
        inter_edges = [(fn_nodes[i - 1]["id"], fn_nodes[i]["id"]) for i in range(1, len(fn_nodes))]
    return fn_nodes, inter_edges


def _skip_quoted_string(text: str, quote_idx: int, *, check_unterminated: bool = False) -> int:
    q, start_line, i, n = text[quote_idx], _offset_to_line(text, quote_idx), quote_idx + 1, len(text)
    while i < n:
        if text[i] == "\\":
            i += 2
            continue
        if text[i] == q:
            return i + 1
        if check_unterminated and text[i] == "\n" and q != "`":
            raise SyntaxError(f"Unterminated string literal at line {start_line}")
        i += 1
    if check_unterminated:
        raise SyntaxError(f"Unterminated string literal starting at line {start_line}")
    return n


def _strip_ts_and_validate_delims(source: str) -> str:
    """Strip TS comments to spaces preserving `\n` offsets, and check balanced `{`/`(`/ `[`."""
    out, n, i = list(source), len(source), 0
    stack: List[Tuple[str, int]] = []
    matching = {"}": "{", ")": "(", "]": "["}
    while i < n:
        ch, nxt = source[i], (source[i + 1] if i + 1 < n else "")
        if ch == "/" and nxt == "/":
            while i < n and source[i] != "\n":
                out[i] = " "
                i += 1
            continue
        if ch == "/" and nxt == "*":
            start_line = _offset_to_line(source, i)
            out[i] = out[i + 1] = " "
            i += 2
            while i < n and not (source[i] == "*" and i + 1 < n and source[i + 1] == "/"):
                if source[i] != "\n":
                    out[i] = " "
                i += 1
            if i >= n:
                raise SyntaxError(f"Unclosed block comment starting at line {start_line}")
            out[i] = out[i + 1] = " "
            i += 2
            continue
        if ch in ("'", '"', "`"):
            i = _skip_quoted_string(source, i, check_unterminated=True)
            continue
        if ch in ("{", "(", "["):
            stack.append((ch, _offset_to_line(source, i)))
        elif ch in ("}", ")", "]"):
            if not stack or stack[-1][0] != matching[ch]:
                raise SyntaxError(f"Unexpected closing '{ch}' at line {_offset_to_line(source, i)}")
            stack.pop()
        i += 1
    if stack:
        raise SyntaxError(f"Unclosed '{stack[-1][0]}' starting at line {stack[-1][1]}")
    return "".join(out)


def _find_matching_delim_in_cleaned(cleaned: str, open_idx: int, open_ch: str, close_ch: str) -> int:
    depth, i, n = 0, open_idx, len(cleaned)
    while i < n:
        ch = cleaned[i]
        if ch in ("'", '"', "`"):
            i = _skip_quoted_string(cleaned, i)
            continue
        depth += 1 if ch == open_ch else (-1 if ch == close_ch else 0)
        if depth == 0:
            return i
        i += 1
    raise SyntaxError(f"Unclosed '{open_ch}' in TypeScript source")


def _parse_ts_blueprint_objects(source: str, cleaned: str, arr_open_idx: int) -> Tuple[List[Dict[str, Any]], List[Tuple[str, str]]]:
    arr_close_idx = _find_matching_delim_in_cleaned(cleaned, arr_open_idx, "[", "]")
    nodes: List[Dict[str, Any]] = []
    edges: List[Tuple[str, str]] = []
    i, idx_counter = arr_open_idx + 1, 0
    while i < arr_close_idx:
        if cleaned[i] != "{":
            i += 1
            continue
        obj_end = _find_matching_delim_in_cleaned(cleaned, i, "{", "}")
        obj_clean, obj_orig = cleaned[i : obj_end + 1], source[i : obj_end + 1]
        idx_counter += 1
        id_m = re.search(r"\bid\s*:\s*['\"`]([^'\"`]+)['\"`]", obj_clean)
        nid = id_m.group(1).strip() if id_m else f"step_{idx_counter}"
        lbl_m = re.search(r"\blabel\s*:\s*['\"`]([^'\"`]+)['\"`]", obj_clean)
        ag_m = re.search(r"\b(?:agent_id|agentId)\s*:\s*['\"`]([^'\"`]+)['\"`]", obj_clean)
        dep_m = re.search(r"\b(?:depends_on|dependsOn)\s*:\s*\[([^\]]*)\]", obj_clean)
        deps = [m.group(1).strip() for m in re.finditer(r"['\"`]([^'\"`]+)['\"`]", dep_m.group(1)) if m.group(1).strip()] if dep_m else []
        p10_m = re.search(r"\b(?:requires_p10|requiresP10|p10)\s*:\s*(true|false)\b", obj_clean)
        req_p10 = (p10_m is not None and p10_m.group(1) == "true") or bool(_P10_COMMENT_RE.search(obj_orig))
        nodes.append(
            _make_raw_node(
                nid,
                lbl_m.group(1).strip() if lbl_m else _humanize_label(nid),
                ag_m.group(1).strip() if ag_m else "workflow-orchestrator",
                req_p10,
                _offset_to_line(source, i),
                _offset_to_line(source, obj_end),
            )
        )
        edges.extend((d, nid) for d in deps)
        i = obj_end + 1
    return nodes, edges


def _extract_typescript_code_to_graph(source_code: str) -> Tuple[List[Dict[str, Any]], List[Tuple[str, str]]]:
    cleaned = _strip_ts_and_validate_delims(source_code)
    bp_match = _TS_BP_DECL_RE.search(cleaned) or _TS_SDK_NODES_RE.search(cleaned)
    if bp_match:
        bp_nodes, bp_edges = _parse_ts_blueprint_objects(source_code, cleaned, bp_match.end() - 1)
        if bp_nodes:
            return bp_nodes, bp_edges

    ts_funcs: Dict[str, Dict[str, Any]] = {}
    ordered_funcs: List[Dict[str, Any]] = []
    for fm in _TS_FUNC_HEADER_RE.finditer(cleaned):
        fname = fm.group(2) or fm.group(4)
        brace_open = fm.end() - 1
        brace_close = _find_matching_delim_in_cleaned(cleaned, brace_open, "{", "}")
        has_p10 = bool(_TS_INTERRUPT_RE.search(cleaned[brace_open : brace_close + 1]) or _P10_COMMENT_RE.search(source_code[fm.start() : brace_close + 1]))
        fn_info = {
            "name": fname, "exported": bool(fm.group(1) or fm.group(3)), "requires_p10": has_p10,
            "line_start": _offset_to_line(source_code, fm.start()), "line_end": _offset_to_line(source_code, brace_close),
        }
        ts_funcs[fname] = fn_info
        ordered_funcs.append(fn_info)

    lg_nodes: Dict[str, Dict[str, Any]] = {}
    lg_order: List[str] = []
    lg_edges: List[Tuple[str, str]] = []
    has_lg = False

    def _ensure_ts(nid: str, l_start: int, l_end: int, p10: bool = False, agent_id: str = "langgraph-ts-node") -> None:
        if not nid or nid in _START_END_TOKENS:
            return
        if nid not in lg_nodes:
            lg_order.append(nid)
            lg_nodes[nid] = _make_raw_node(nid, _humanize_label(nid), agent_id, p10, l_start, l_end)
        elif p10:
            lg_nodes[nid]["requires_p10"] = True

    for nm in _TS_ADD_NODE_CALL_RE.finditer(cleaned):
        has_lg = True
        paren_open = cleaned.find("(", nm.start())
        paren_close = _find_matching_delim_in_cleaned(cleaned, paren_open, "(", ")")
        raw_tok = nm.group(1).strip().strip("'\"`")
        ident_m = re.match(r",\s*([A-Za-z_$][A-Za-z0-9_$]*)\s*$", cleaned[nm.end() : paren_close].lstrip())
        handler_name = ident_m.group(1) if ident_m else raw_tok
        fn_meta = ts_funcs.get(handler_name)
        l_start = fn_meta["line_start"] if fn_meta else _offset_to_line(source_code, nm.start())
        l_end = fn_meta["line_end"] if fn_meta else _offset_to_line(source_code, paren_close)
        is_p10 = bool(fn_meta and fn_meta["requires_p10"]) or bool(_TS_INTERRUPT_RE.search(cleaned[nm.start() : paren_close + 1])) or bool(_P10_COMMENT_RE.search(source_code[nm.start() : paren_close + 1]))
        _ensure_ts(raw_tok, l_start, l_end, is_p10, agent_id=handler_name)

    for em in _TS_ADD_EDGE_CALL_RE.finditer(cleaned):
        has_lg = True
        src, dst, ln = em.group(1).strip().strip("'\"`"), em.group(2).strip().strip("'\"`"), _offset_to_line(source_code, em.start())
        _ensure_ts(src, ln, ln)
        _ensure_ts(dst, ln, ln)
        if src not in _START_END_TOKENS and dst not in _START_END_TOKENS:
            lg_edges.append((src, dst))

    for cm in _TS_COND_EDGE_CALL_RE.finditer(cleaned):
        has_lg = True
        paren_open = cleaned.find("(", cm.start())
        paren_close = _find_matching_delim_in_cleaned(cleaned, paren_open, "(", ")")
        src = cm.group(1).strip().strip("'\"`")
        if src in _START_END_TOKENS:
            continue
        ln, rest = _offset_to_line(source_code, cm.start()), cleaned[cm.end() : paren_close]
        _ensure_ts(src, ln, ln)
        brace_idx, bracket_idx = rest.find("{"), rest.find("[")
        if brace_idx != -1:
            map_body = rest[brace_idx + 1 : _find_matching_delim_in_cleaned(rest, brace_idx, "{", "}")]
            for kv in re.finditer(r":\s*(START|END|['\"`][^'\"`]+['\"`])", map_body):
                tgt = kv.group(1).strip().strip("'\"`")
                if tgt not in _START_END_TOKENS:
                    _ensure_ts(tgt, ln, ln)
                    lg_edges.append((src, tgt))
        elif bracket_idx != -1:
            arr_body = rest[bracket_idx + 1 : _find_matching_delim_in_cleaned(rest, bracket_idx, "[", "]")]
            for tok_m in _TS_STRING_TOKEN_RE.finditer(arr_body):
                tgt = (tok_m.group(1) or tok_m.group(0)).strip().strip("'\"`")
                if tgt not in _START_END_TOKENS:
                    _ensure_ts(tgt, ln, ln)
                    lg_edges.append((src, tgt))

    for im in _TS_COMPILE_INT_RE.finditer(cleaned):
        for tok_m in re.finditer(r"['\"`]([^'\"`]+)['\"`]", im.group(1)):
            if (nid := tok_m.group(1).strip()) in lg_nodes:
                lg_nodes[nid]["requires_p10"] = True

    if has_lg and lg_order:
        return [lg_nodes[nid] for nid in lg_order], lg_edges

    exported = [f for f in ordered_funcs if f["exported"]] or ordered_funcs
    if not exported:
        raise ValueError("No KFLOW_BLUEPRINT, StateGraph nodes, or step functions found in TypeScript source_code.")
    step_nodes = [_make_raw_node(f["name"], _humanize_label(f["name"]), "typescript-step-agent", f["requires_p10"], f["line_start"], f["line_end"]) for f in exported]
    return step_nodes, [(step_nodes[i - 1]["id"], step_nodes[i]["id"]) for i in range(1, len(step_nodes))]


def _compute_layout_and_cycles(
    raw_nodes: Sequence[Dict[str, Any]], directed_edges: Sequence[Tuple[str, str]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, str]]]:
    node_order: List[str] = []
    by_id: Dict[str, Dict[str, Any]] = {}
    for idx, raw in enumerate(raw_nodes):
        nid = str(raw.get("id") or f"step_{idx + 1}").strip()
        if not nid or nid in by_id:
            raise ValueError(f"Invalid or duplicate node id '{nid}' at index {idx}.")
        node_order.append(nid)
        by_id[nid] = dict(raw, id=nid)

    valid_ids = set(node_order)
    dedup_edges: List[Tuple[str, str]] = []
    seen_pairs: Set[Tuple[str, str]] = set()
    adj: Dict[str, List[str]] = {nid: [] for nid in node_order}
    incoming: Dict[str, List[str]] = {nid: [] for nid in node_order}
    for u, v in directed_edges:
        if u in valid_ids and v in valid_ids and (u, v) not in seen_pairs:
            seen_pairs.add((u, v))
            dedup_edges.append((u, v))
            adj[u].append(v)
            incoming[v].append(u)

    color: Dict[str, int] = {nid: 0 for nid in node_order}
    back_set: Set[Tuple[str, str]] = set()
    cycle_back_edges: List[Dict[str, str]] = []

    def _dfs(u: str) -> None:
        color[u] = 1
        for v in adj[u]:
            if u == v or color[v] == 1:
                if (u, v) not in back_set:
                    back_set.add((u, v))
                    cycle_back_edges.append({"from": u, "to": v})
            elif color[v] == 0:
                _dfs(v)
        color[u] = 2

    for nid in node_order:
        if color[nid] == 0:
            _dfs(nid)

    memo_wave: Dict[str, int] = {}

    def _wave_of(nid: str) -> int:
        if nid not in memo_wave:
            parents = [p for p in incoming[nid] if (p, nid) not in back_set]
            memo_wave[nid] = 0 if not parents else 1 + max(_wave_of(p) for p in parents)
        return memo_wave[nid]

    wave_lanes: Dict[int, int] = {}
    normalized_nodes: List[Dict[str, Any]] = []
    for nid in node_order:
        raw_n, w = by_id[nid], _wave_of(nid)
        lane_idx = wave_lanes.get(w, 0)
        wave_lanes[w] = lane_idx + 1
        normalized_nodes.append({
            "id": nid, "label": str(raw_n.get("label") or _humanize_label(nid)).strip() or nid,
            "agent_id": str(raw_n.get("agent_id") or "workflow-orchestrator").strip() or "workflow-orchestrator",
            "depends_on": [p for p in incoming[nid] if (p, nid) not in back_set],
            "requires_p10": bool(raw_n.get("requires_p10", False)),
            "line_start": int(raw_n.get("line_start", 1)), "line_end": int(raw_n.get("line_end", 1)),
            "wave": w, "x": 80 + w * 220, "y": 76 + lane_idx * 110,
        })
    return normalized_nodes, [{"from": u, "to": v, "is_cycle": (u, v) in back_set} for u, v in dedup_edges], cycle_back_edges


def _synthesize_code_from_graph(workflow_id: str, language: str, layout_nodes: List[Dict[str, Any]]) -> Tuple[str, List[Dict[str, Any]]]:
    is_py = language == "python"
    lines: List[str] = (
        [f'"""Keelway Studio KFlow Blueprint — {workflow_id}."""', "", "from typing import Any, Dict", "", "from core.sdk.client import KeelwayClient", ""]
        if is_py else ['import { KeelwayClient } from "@keelway/sdk";']
    )
    for n in layout_nodes:
        ident, p10 = _safe_ident(n["id"]), n["requires_p10"]
        if is_py:
            lines.extend(["", f"def step_{ident}(state: Dict[str, Any]) -> Dict[str, Any]:", f'    """{n["label"]} (agent: {n["agent_id"]})."""'])
            if p10:
                lines.append("    # P-10 human gate required")
            lines.extend([f'    return {{"step": {json.dumps(n["id"])}, "requires_p10": {"True" if p10 else "False"}, "state": state}}', ""])
        else:
            lines.extend(["", f"export async function step_{ident}(state: Record<string, unknown>): Promise<Record<string, unknown>> {{"])
            if p10:
                lines.append("  // P-10 human gate required")
            lines.extend([f"  return {{ step: {json.dumps(n['id'])}, requires_p10: {'true' if p10 else 'false'}, state }};", "}"])
    lines.extend(["", "KFLOW_BLUEPRINT = [" if is_py else "export const KFLOW_BLUEPRINT = ["])
    for n in layout_nodes:
        start_ln, p10 = len(lines) + 1, n["requires_p10"]
        if is_py:
            tag = "  # P-10 human gate required" if p10 else ""
            lines.extend(["    {", f'        "id": {json.dumps(n["id"])},', f'        "label": {json.dumps(n["label"])},', f'        "agent_id": {json.dumps(n["agent_id"])},', f'        "depends_on": {json.dumps(n["depends_on"])},', f'        "requires_p10": {"True" if p10 else "False"},{tag}', "    },"])
        else:
            tag = " // P-10 human gate required" if p10 else ""
            lines.extend(["  {", f"    id: {json.dumps(n['id'])},", f"    label: {json.dumps(n['label'])},", f"    agent_id: {json.dumps(n['agent_id'])},", f"    depends_on: {json.dumps(n['depends_on'])},", f"    requires_p10: {'true' if p10 else 'false'},{tag}", "  },"])
        n["line_start"], n["line_end"] = start_ln, len(lines)
    lines.extend(
        ["]", "", "", 'def build_studio_client(base_url: str = "http://127.0.0.1:8000") -> KeelwayClient:', "    return KeelwayClient(base_url=base_url)"]
        if is_py else ["];", "", 'export function createStudioClient(baseUrl = "http://127.0.0.1:8000"): KeelwayClient {', "  return new KeelwayClient({ baseUrl });", "}"]
    )
    return "\n".join(lines) + "\n", layout_nodes


class KFlowBidirectionalSyncEngine:
    """Static AST/Lexer Code <-> Graph synchronization engine with optional SQLite WAL persistence."""

    def __init__(self, db_path: Optional[Union[str, Path]] = None) -> None:
        self._lock, self._explicit_db_path = threading.RLock(), db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._active_target: Optional[str] = None
        self._db_path: Union[str, Path] = ":memory:"
        self._closed = False

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
            conn.executescript(_KFLOW_SYNC_SCHEMA_SQL)
        self._conn, self._active_target, self._db_path, self._closed = conn, connect_target, resolved_path, False
        return conn

    @property
    def db_path(self) -> Union[str, Path]:
        with self._lock:
            if not self._closed:
                self._ensure_conn()
            return self._db_path

    def close(self) -> None:
        with self._lock:
            if self._conn is not None and not self._closed:
                self._conn.close()
                self._closed = True

    def sync(
        self, workspace_id: str = "default", direction: str = "code_to_graph", language: str = "python",
        workflow_id: str = "WF-STUDIO-01", source_code: Optional[str] = None,
        nodes: Optional[List[Dict[str, Any]]] = None, persist: bool = False,
    ) -> Dict[str, Any]:
        ws, wf_id = _clean_workspace_id(workspace_id), str(workflow_id or "WF-STUDIO-01").strip() or "WF-STUDIO-01"
        norm_dir, norm_lang = str(direction or "").strip().lower(), str(language or "").strip().lower()
        if norm_dir not in VALID_SYNC_DIRECTIONS or norm_lang not in VALID_SYNC_LANGUAGES:
            raise ValueError(f"Unsupported direction='{direction}' or language='{language}'.")
        raw_source = source_code or ""
        if len(raw_source.encode("utf-8")) > MAX_SOURCE_CODE_BYTES:
            raise PayloadTooLargeError("source_code exceeds 262144 byte limit")

        if norm_dir == "code_to_graph":
            if not raw_source.strip():
                raise ValueError("source_code must be non-empty when direction='code_to_graph'.")
            raw_nodes, dir_edges = _extract_python_code_to_graph(raw_source) if norm_lang == "python" else _extract_typescript_code_to_graph(raw_source)
            normalized_nodes, edges, cycle_back_edges = _compute_layout_and_cycles(raw_nodes, dir_edges)
            final_source_code = raw_source
        else:
            if not isinstance(nodes, list) or not nodes:
                raise ValueError("nodes must be a non-empty list when direction='graph_to_code'.")
            prepared_nodes, dir_edges = [], []
            for idx, item in enumerate(nodes):
                if not isinstance(item, dict) or not str(item.get("id") or "").strip():
                    raise ValueError(f"Node at index {idx} must be a dictionary with a non-empty 'id'.")
                nid = str(item["id"]).strip()
                raw_deps = item.get("depends_on") if isinstance(item.get("depends_on"), list) else item.get("dependsOn")
                prepared_nodes.append(_make_raw_node(nid, str(item.get("label") or _humanize_label(nid)).strip(), str(item.get("agent_id") or item.get("agentId") or "workflow-orchestrator").strip(), bool(item.get("requires_p10") or item.get("requiresP10") or item.get("p10")), 1, 1))
                dir_edges.extend((str(d).strip(), nid) for d in (raw_deps or []) if str(d).strip())
            normalized_nodes, edges, cycle_back_edges = _compute_layout_and_cycles(prepared_nodes, dir_edges)
            final_source_code, normalized_nodes = _synthesize_code_from_graph(wf_id, norm_lang, normalized_nodes)
            if len(final_source_code.encode("utf-8")) > MAX_SOURCE_CODE_BYTES:
                raise PayloadTooLargeError("source_code exceeds 262144 byte limit")

        p10_locked_nodes = [n["id"] for n in normalized_nodes if n["requires_p10"]]
        sync_sha256 = "sha256:" + hashlib.sha256(_canonical_json({"cycle_back_edges": cycle_back_edges, "direction": norm_dir, "edges": edges, "language": norm_lang, "nodes": normalized_nodes, "p10_locked_nodes": p10_locked_nodes, "source_code": final_source_code, "workflow_id": wf_id, "workspace_id": ws}).encode("utf-8")).hexdigest()

        if persist:
            with self._lock:
                conn = self._ensure_conn()
                with conn:
                    conn.execute(
                        "INSERT INTO platform_studio_kflow_syncs (workspace_id, workflow_id, direction, language, nodes_json, edges_json, cycle_back_edges_json, p10_locked_nodes_json, source_code, sync_sha256, synced_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (ws, wf_id, norm_dir, norm_lang, _canonical_json(normalized_nodes), _canonical_json(edges), _canonical_json(cycle_back_edges), _canonical_json(p10_locked_nodes), final_source_code, sync_sha256, _utc_now()),
                    )
        return {"workspace_id": ws, "workflow_id": wf_id, "direction": norm_dir, "language": norm_lang, "nodes": normalized_nodes, "edges": edges, "cycle_back_edges": cycle_back_edges, "p10_locked_nodes": p10_locked_nodes, "source_code": final_source_code, "persisted": bool(persist), "sync_sha256": sync_sha256}

    def list_syncs(self, workspace_id: str = "default", workflow_id: Optional[str] = None, limit: int = 20) -> Dict[str, Any]:
        ws, cap = _clean_workspace_id(workspace_id), max(1, min(int(limit), 200))
        with self._lock:
            conn = self._ensure_conn()
            sql = "SELECT * FROM platform_studio_kflow_syncs WHERE workspace_id=?" + (" AND workflow_id=?" if workflow_id else "") + " ORDER BY id DESC LIMIT ?"
            rows = conn.execute(sql, (ws, str(workflow_id).strip(), cap) if workflow_id else (ws, cap)).fetchall()
        items = [{"workspace_id": str(r["workspace_id"]), "workflow_id": str(r["workflow_id"]), "direction": str(r["direction"]), "language": str(r["language"]), "nodes": json.loads(str(r["nodes_json"])), "edges": json.loads(str(r["edges_json"])), "cycle_back_edges": json.loads(str(r["cycle_back_edges_json"])), "p10_locked_nodes": json.loads(str(r["p10_locked_nodes_json"])), "source_code": str(r["source_code"]), "sync_sha256": str(r["sync_sha256"]), "synced_at": str(r["synced_at"])} for r in rows]
        return {"workspace_id": ws, "count": len(items), "syncs": items}


kflow_bidirectional_sync_engine = KFlowBidirectionalSyncEngine()
