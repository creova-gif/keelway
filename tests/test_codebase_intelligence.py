"""
Tests for Keelway Codebase Intelligence & Graph Analysis.
Covers cross-file references, call hierarchy, module dependency graphs, symbol search, and REST API endpoints.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from core.main import app
from core.storage.ast_index import CodebaseSemanticIndex, PythonASTExtractor, TypeScriptRegexExtractor


def test_python_ast_extractor_imports_and_calls():
    code = """
import os
from pathlib import Path
from core.models import cost_ledger

def helper_function(x):
    return x * 2

def main_service():
    val = helper_function(10)
    p = Path(".")
    print(val)
"""
    imports = PythonASTExtractor.extract_imports(code, "sample.py")
    assert any(i["module"] == "os" for i in imports)
    assert any("pathlib" in i["module"] or i["name"] == "Path" for i in imports)
    assert any("core.models" in i["module"] for i in imports)

    calls = PythonASTExtractor.extract_calls(code, "sample.py")
    assert any(c["callee"] == "helper_function" and c["caller"] == "main_service" for c in calls)
    assert any(c["callee"] == "Path" and c["caller"] == "main_service" for c in calls)


def test_typescript_regex_extractor_imports_and_calls():
    ts_code = """
import { useState, useEffect } from 'react';
import axios from 'axios';

export function Component() {
    useState(0);
    fetchData();
}
"""
    imports = TypeScriptRegexExtractor.extract_imports(ts_code, "comp.tsx")
    assert any("react" in i["module"] for i in imports)
    assert any("axios" in i["module"] for i in imports)

    calls = TypeScriptRegexExtractor.extract_calls(ts_code, "comp.tsx")
    assert any(c["callee"] == "useState" for c in calls)
    assert any(c["callee"] == "fetchData" for c in calls)


def test_codebase_index_references_and_hierarchy(tmp_path):
    f1 = tmp_path / "module_a.py"
    f1.write_text("""
def calculate_discount(price):
    return price * 0.9

def apply_promo(price):
    return calculate_discount(price)
""", encoding="utf-8")

    f2 = tmp_path / "module_b.py"
    f2.write_text("""
from module_a import calculate_discount

def checkout():
    total = calculate_discount(100)
    return total
""", encoding="utf-8")

    from core.storage.workspace_fs import WorkspaceFilesystem
    fs = WorkspaceFilesystem(str(tmp_path))
    idx = CodebaseSemanticIndex(workspace_fs=fs)
    idx.index_file("module_a.py")
    idx.index_file("module_b.py")

    # 1. References
    refs = idx.find_references("calculate_discount")
    assert len(refs) >= 3  # definition in a, call in a, import in b, call in b
    assert any(r["kind"] == "definition" and r["file_path"] == "module_a.py" for r in refs)
    assert any(r["kind"] in ("call", "reference") and r["file_path"] == "module_b.py" for r in refs)

    # 2. Call hierarchy
    hierarchy = idx.get_call_hierarchy("calculate_discount")
    assert hierarchy["symbol"] == "calculate_discount"
    callers = [c["caller"] for c in hierarchy["callers"]]
    assert "apply_promo" in callers or "checkout" in callers

    # 3. Definition
    defn = idx.get_definition("calculate_discount")
    assert defn is not None
    assert defn["name"] == "calculate_discount"
    assert defn["file_path"] == "module_a.py"

    # 4. Dependency graph
    graph = idx.get_module_dependency_graph()
    assert "module_a.py" in graph["nodes"]
    assert "module_b.py" in graph["nodes"]
    assert graph["has_cycles"] is False


def test_codebase_api_endpoints():
    client = TestClient(app)
    headers = {"Authorization": "Bearer dev_token"}

    # 1. Repomap
    res = client.get("/v1/codebase/repomap?max_tokens=500", headers=headers)
    assert res.status_code == 200
    assert "repo_map" in res.json()

    # 2. Symbols search
    res = client.get("/v1/codebase/symbols?q=CodeSymbol&top_k=5", headers=headers)
    assert res.status_code == 200
    assert "results" in res.json()

    # 3. References
    res = client.get("/v1/codebase/references?symbol=CodeSymbol", headers=headers)
    assert res.status_code == 200
    assert "references" in res.json()

    # 4. Call hierarchy
    res = client.get("/v1/codebase/hierarchy?symbol=extract_symbols", headers=headers)
    assert res.status_code == 200
    assert "callers" in res.json()
    assert "callees" in res.json()

    # 5. Dependency graph
    res = client.get("/v1/codebase/graph", headers=headers)
    assert res.status_code == 200
    assert "nodes" in res.json()
    assert "edges" in res.json()


def test_cli_code_commands():
    from cli import cmd_code
    # 1. Search
    assert cmd_code(action="search", target="CodeSymbol", top_k=3) == 0
    # 2. References
    assert cmd_code(action="refs", target="CodeSymbol") == 0
    # 3. Hierarchy
    assert cmd_code(action="hierarchy", target="extract_symbols") == 0
    # 4. Graph text and json
    assert cmd_code(action="graph", format_type="text") == 0
    assert cmd_code(action="graph", format_type="json") == 0
    # 5. Definition
    assert cmd_code(action="def", target="CodeSymbol") == 0
    # 6. Repomap
    assert cmd_code(action="repomap", max_tokens=200) == 0
