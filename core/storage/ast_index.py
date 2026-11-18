"""
Keelway Codebase Semantic Indexer & Repository Map (RepoMap).
Performs AST-level symbol extraction (classes, methods, signatures, imports),
maintains an incremental SHA-256 hash cache, and generates condensed repo maps
and vector-indexed symbol search for prompt context augmentation.
"""

import ast
import hashlib
import json
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, Any, List, Optional, Set, Tuple

from core.storage.embedding import EmbeddingProvider, cosine_similarity, compute_lexical_score
from core.storage.workspace_fs import WorkspaceFilesystem


@dataclass
class CodeSymbol:
    name: str
    kind: str  # "class" | "function" | "method" | "interface" | "type" | "import"
    file_path: str
    line_number: int
    end_line: int
    signature: str = ""
    docstring: Optional[str] = None
    parent_symbol: Optional[str] = None
    embedding: Optional[List[float]] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d.pop("embedding", None)  # Omit raw vector in JSON serialization
        return d


class PythonASTExtractor:
    """Extracts symbols and signatures from Python source using standard library AST."""

    @staticmethod
    def extract_symbols(source_code: str, file_path: str) -> List[CodeSymbol]:
        symbols: List[CodeSymbol] = []
        try:
            tree = ast.parse(source_code, filename=file_path)
        except SyntaxError:
            return symbols

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef):
                doc = ast.get_docstring(node)
                class_sym = CodeSymbol(
                    name=node.name,
                    kind="class",
                    file_path=file_path,
                    line_number=node.lineno,
                    end_line=getattr(node, "end_lineno", node.lineno),
                    signature=f"class {node.name}" + (f"({', '.join(b.id for b in node.bases if isinstance(b, ast.Name))})" if node.bases else ""),
                    docstring=doc,
                )
                symbols.append(class_sym)

                # Extract methods
                for class_node in ast.iter_child_nodes(node):
                    if isinstance(class_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        method_doc = ast.get_docstring(class_node)
                        async_pfx = "async " if isinstance(class_node, ast.AsyncFunctionDef) else ""
                        args_list = [a.arg for a in class_node.args.args]
                        sig = f"{async_pfx}def {class_node.name}({', '.join(args_list)})"
                        symbols.append(
                            CodeSymbol(
                                name=class_node.name,
                                kind="method",
                                file_path=file_path,
                                line_number=class_node.lineno,
                                end_line=getattr(class_node, "end_lineno", class_node.lineno),
                                signature=sig,
                                docstring=method_doc,
                                parent_symbol=node.name,
                            )
                        )

            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                fn_doc = ast.get_docstring(node)
                async_pfx = "async " if isinstance(node, ast.AsyncFunctionDef) else ""
                args_list = [a.arg for a in node.args.args]
                symbols.append(
                    CodeSymbol(
                        name=node.name,
                        kind="function",
                        file_path=file_path,
                        line_number=node.lineno,
                        end_line=getattr(node, "end_lineno", node.lineno),
                        signature=f"{async_pfx}def {node.name}({', '.join(args_list)})",
                        docstring=fn_doc,
                    )
                )

        return symbols

    @staticmethod
    def extract_imports(source_code: str, file_path: str) -> List[Dict[str, Any]]:
        imports: List[Dict[str, Any]] = []
        try:
            tree = ast.parse(source_code, filename=file_path)
        except SyntaxError:
            return imports

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append({
                        "module": alias.name,
                        "name": alias.asname or alias.name,
                        "line": node.lineno,
                    })
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                for alias in node.names:
                    full_name = f"{mod}.{alias.name}" if mod else alias.name
                    imports.append({
                        "module": mod,
                        "name": alias.name,
                        "full_import": full_name,
                        "line": node.lineno,
                    })
        return imports

    @staticmethod
    def extract_calls(source_code: str, file_path: str) -> List[Dict[str, Any]]:
        calls: List[Dict[str, Any]] = []
        try:
            tree = ast.parse(source_code, filename=file_path)
        except SyntaxError:
            return calls

        class CallVisitor(ast.NodeVisitor):
            def __init__(self):
                self.current_caller: Optional[str] = None
                self.found_calls: List[Dict[str, Any]] = []

            def visit_FunctionDef(self, node):
                prev = self.current_caller
                self.current_caller = node.name
                self.generic_visit(node)
                self.current_caller = prev

            def visit_AsyncFunctionDef(self, node):
                prev = self.current_caller
                self.current_caller = node.name
                self.generic_visit(node)
                self.current_caller = prev

            def visit_Call(self, node):
                callee_name = ""
                if isinstance(node.func, ast.Name):
                    callee_name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    callee_name = node.func.attr
                if callee_name:
                    self.found_calls.append({
                        "caller": self.current_caller or "<module>",
                        "callee": callee_name,
                        "line": node.lineno,
                    })
                self.generic_visit(node)

        v = CallVisitor()
        v.visit(tree)
        return v.found_calls


class TypeScriptRegexExtractor:
    """Extracts symbols from TypeScript and JavaScript using structural regex grammar."""

    CLASS_RE = re.compile(r"^(?:export\s+)?class\s+([A-Za-z0-9_$]+)(?:\s+extends\s+[A-Za-z0-9_$.]+)?", re.MULTILINE)
    INTERFACE_RE = re.compile(r"^(?:export\s+)?interface\s+([A-Za-z0-9_$]+)", re.MULTILINE)
    TYPE_RE = re.compile(r"^(?:export\s+)?type\s+([A-Za-z0-9_$]+)\s*=", re.MULTILINE)
    FUNCTION_RE = re.compile(r"^(?:export\s+)?(?:async\s+)?function\s+([A-Za-z0-9_$]+)\s*\(([^)]*)\)", re.MULTILINE)
    ARROW_RE = re.compile(r"^(?:export\s+)?const\s+([A-Za-z0-9_$]+)\s*=\s*(?:async\s*)?\(([^)]*)\)\s*(?::\s*[^=]+)?=>", re.MULTILINE)
    IMPORT_RE = re.compile(r"^(?:import\s+(?:(?:\{[^}]*\}|\*\s+as\s+[A-Za-z0-9_$]+|[A-Za-z0-9_$]+)\s*,?\s*)*(?:from\s+)?['\"]([^'\"]+)['\"])", re.MULTILINE)
    CALL_RE = re.compile(r"\b([A-Za-z0-9_$]+)\s*\(", re.MULTILINE)

    @classmethod
    def extract_symbols(cls, source_code: str, file_path: str) -> List[CodeSymbol]:
        symbols: List[CodeSymbol] = []
        lines = source_code.splitlines()

        for idx, line in enumerate(lines, 1):
            sline = line.strip()
            # Class
            m = cls.CLASS_RE.match(sline)
            if m:
                symbols.append(CodeSymbol(name=m.group(1), kind="class", file_path=file_path, line_number=idx, end_line=idx, signature=sline))
                continue

            # Interface
            m = cls.INTERFACE_RE.match(sline)
            if m:
                symbols.append(CodeSymbol(name=m.group(1), kind="interface", file_path=file_path, line_number=idx, end_line=idx, signature=sline))
                continue

            # Type
            m = cls.TYPE_RE.match(sline)
            if m:
                symbols.append(CodeSymbol(name=m.group(1), kind="type", file_path=file_path, line_number=idx, end_line=idx, signature=sline))
                continue

            # Function
            m = cls.FUNCTION_RE.match(sline)
            if m:
                symbols.append(CodeSymbol(name=m.group(1), kind="function", file_path=file_path, line_number=idx, end_line=idx, signature=sline))
                continue

            # Arrow function
            m = cls.ARROW_RE.match(sline)
            if m:
                symbols.append(CodeSymbol(name=m.group(1), kind="function", file_path=file_path, line_number=idx, end_line=idx, signature=sline))

        return symbols

    @classmethod
    def extract_imports(cls, source_code: str, file_path: str) -> List[Dict[str, Any]]:
        imports: List[Dict[str, Any]] = []
        for idx, line in enumerate(source_code.splitlines(), 1):
            m = cls.IMPORT_RE.match(line.strip())
            if m:
                imports.append({"module": m.group(1), "name": m.group(1).split("/")[-1], "line": idx})
        return imports

    @classmethod
    def extract_calls(cls, source_code: str, file_path: str) -> List[Dict[str, Any]]:
        calls: List[Dict[str, Any]] = []
        current_fn = "<module>"
        for idx, line in enumerate(source_code.splitlines(), 1):
            s = line.strip()
            fn_m = cls.FUNCTION_RE.match(s) or cls.ARROW_RE.match(s)
            if fn_m:
                current_fn = fn_m.group(1)
            for m in cls.CALL_RE.finditer(s):
                callee = m.group(1)
                if callee not in ("if", "for", "while", "switch", "catch", "function", "import"):
                    calls.append({"caller": current_fn, "callee": callee, "line": idx})
        return calls


class CodebaseSemanticIndex:
    """Maintains indexed AST symbols, vector embeddings, call hierarchy, and dependency graphs across workspace files."""

    def __init__(self, workspace_fs: Optional[WorkspaceFilesystem] = None):
        self.fs = workspace_fs or WorkspaceFilesystem()
        self.symbols: Dict[str, List[CodeSymbol]] = {}  # file_path -> symbols
        self.file_hashes: Dict[str, str] = {}           # file_path -> sha256
        self.file_contents: Dict[str, str] = {}         # file_path -> full content
        self.file_imports: Dict[str, List[Dict[str, Any]]] = {}  # file_path -> imports
        self.file_calls: Dict[str, List[Dict[str, Any]]] = {}    # file_path -> calls

    def index_file(self, relative_path: str) -> List[CodeSymbol]:
        """Extracts and vector-indexes symbols for a single file if changed."""
        try:
            file_data = self.fs.read_file(relative_path)
            content = file_data.get("content", "")
            if file_data.get("is_binary"):
                return []
        except Exception:
            return []

        # Check hash
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        if self.file_hashes.get(relative_path) == content_hash and relative_path in self.symbols:
            return self.symbols[relative_path]

        symbols: List[CodeSymbol] = []
        imports: List[Dict[str, Any]] = []
        calls: List[Dict[str, Any]] = []

        if relative_path.endswith(".py"):
            symbols = PythonASTExtractor.extract_symbols(content, relative_path)
            imports = PythonASTExtractor.extract_imports(content, relative_path)
            calls = PythonASTExtractor.extract_calls(content, relative_path)
        elif relative_path.endswith((".ts", ".tsx", ".js", ".jsx")):
            symbols = TypeScriptRegexExtractor.extract_symbols(content, relative_path)
            imports = TypeScriptRegexExtractor.extract_imports(content, relative_path)
            calls = TypeScriptRegexExtractor.extract_calls(content, relative_path)

        # Generate dense embeddings for each symbol
        for sym in symbols:
            embed_text = f"{sym.kind} {sym.name} {sym.signature} {sym.docstring or ''}"
            sym.embedding = EmbeddingProvider.get_dense_embedding(embed_text)

        self.symbols[relative_path] = symbols
        self.file_hashes[relative_path] = content_hash
        self.file_contents[relative_path] = content
        self.file_imports[relative_path] = imports
        self.file_calls[relative_path] = calls
        return symbols

    def index_workspace(self, max_files: int = 500) -> Dict[str, Any]:
        """Indexes all supported code files in the workspace."""
        requested_budget = max(1, int(max_files))
        code_budget = max(requested_budget, 350) if requested_budget >= 100 else requested_budget
        tree_res = self.fs.get_file_tree(max_depth=4, max_files=max(code_budget * 5, 1500))
        total_files = 0
        indexed_symbols_count = 0

        def _walk(node: Dict[str, Any]):
            nonlocal total_files, indexed_symbols_count
            if total_files >= code_budget:
                return
            if node.get("type") == "file":
                p = node.get("path", "")
                if p.endswith((".py", ".ts", ".tsx", ".js", ".jsx")):
                    syms = self.index_file(p)
                    total_files += 1
                    indexed_symbols_count += len(syms)
            elif node.get("type") == "directory":
                for child in node.get("children", []):
                    if total_files >= code_budget:
                        break
                    _walk(child)

        _walk(tree_res.get("tree", {}))

        return {
            "total_files_indexed": total_files,
            "total_symbols_indexed": indexed_symbols_count,
            "cached_files_count": len(self.file_hashes),
        }

    def generate_repo_map(self, max_tokens: int = 1500) -> str:
        """
        Generates a condensed, formatted repository map fitting within an LLM token budget.
        Similar to Aider / Cursor's codebase outline.
        """
        lines: List[str] = []
        for path, sym_list in sorted(self.symbols.items()):
            if not sym_list:
                continue

            lines.append(f"{path}:")
            for sym in sym_list:
                if sym.kind == "class":
                    lines.append(f"  class {sym.name}:")
                elif sym.kind == "method":
                    lines.append(f"    {sym.signature}")
                elif sym.kind in ("function", "interface", "type"):
                    lines.append(f"  {sym.signature}")

        full_map = "\n".join(lines)
        # Rough token approximation (4 chars per token)
        char_limit = max_tokens * 4
        if len(full_map) > char_limit:
            full_map = full_map[:char_limit] + "\n  ... [truncated for context window]"
        return full_map

    def search_symbols(
        self,
        query: str,
        top_k: int = 10,
        semantic_weight: float = 0.6,
        lexical_weight: float = 0.4,
    ) -> List[Dict[str, Any]]:
        """
        Hybrid semantic and lexical search across all indexed codebase symbols.
        Returns rank-ordered matches with line numbers, signatures, and scores.
        """
        if not query.strip():
            return []

        query_vec = EmbeddingProvider.get_dense_embedding(query)
        scored: List[Tuple[float, CodeSymbol]] = []

        for sym_list in self.symbols.values():
            for sym in sym_list:
                sem_score = cosine_similarity(query_vec, sym.embedding) if sym.embedding else 0.0
                target_text = f"{sym.name} {sym.signature} {sym.docstring or ''}"
                lex_score = compute_lexical_score(query, target_text)

                combined = (sem_score * semantic_weight) + (lex_score * lexical_weight)
                if combined > 0.05:
                    scored.append((combined, sym))

        scored.sort(key=lambda x: x[0], reverse=True)

        results = []
        for score, sym in scored[:top_k]:
            results.append({
                "score": round(score, 4),
                "name": sym.name,
                "kind": sym.kind,
                "file_path": sym.file_path,
                "line_number": sym.line_number,
                "signature": sym.signature,
                "docstring": sym.docstring,
                "parent_symbol": sym.parent_symbol,
            })
        return results

    def find_references(self, symbol_name: str) -> List[Dict[str, Any]]:
        """Finds all occurrences, call sites, imports, and definitions of a symbol across the workspace."""
        if not symbol_name or not symbol_name.strip():
            return []
        sym = symbol_name.strip()
        pattern = re.compile(r"\b" + re.escape(sym) + r"\b")
        references: List[Dict[str, Any]] = []

        # Find exact symbol definition lines
        def_lines: Dict[str, Set[int]] = {}
        for path, syms in self.symbols.items():
            def_lines[path] = {s.line_number for s in syms if s.name == sym}

        for path, content in self.file_contents.items():
            lines = content.splitlines()
            for line_no, line in enumerate(lines, 1):
                if pattern.search(line):
                    is_def = line_no in def_lines.get(path, set())
                    kind = "definition" if is_def else "reference"
                    stripped = line.strip()
                    if not is_def:
                        if stripped.startswith(("import ", "from ")):
                            kind = "import"
                        elif "(" in stripped:
                            kind = "call"
                    references.append({
                        "file_path": path,
                        "line_number": line_no,
                        "snippet": stripped,
                        "kind": kind,
                    })
        return references

    def get_call_hierarchy(self, symbol_name: str) -> Dict[str, Any]:
        """Returns incoming callers and outgoing callees for a given function or method."""
        sym = symbol_name.strip()
        callers: List[Dict[str, Any]] = []
        callees: List[Dict[str, Any]] = []

        for path, calls in self.file_calls.items():
            for c in calls:
                if c["callee"] == sym:
                    callers.append({
                        "caller": c["caller"],
                        "file_path": path,
                        "line_number": c["line"],
                    })
                if c["caller"] == sym:
                    callees.append({
                        "callee": c["callee"],
                        "file_path": path,
                        "line_number": c["line"],
                    })
        return {
            "symbol": sym,
            "callers": callers,
            "callees": callees,
        }

    def get_module_dependency_graph(self) -> Dict[str, Any]:
        """Constructs a directed module dependency graph across indexed files with cycle detection."""
        nodes = sorted(list(self.symbols.keys()))
        edges: List[Dict[str, Any]] = []
        adjacency: Dict[str, List[str]] = {n: [] for n in nodes}

        # Build module mapping (e.g. core/storage/ast_index.py -> core.storage.ast_index)
        mod_to_file: Dict[str, str] = {}
        for n in nodes:
            clean = n.replace("/", ".").replace("\\", ".")
            if clean.endswith(".py"):
                clean = clean[:-3]
            elif clean.endswith((".ts", ".js")):
                clean = clean[:-3]
            mod_to_file[clean] = n
            mod_to_file[Path(n).stem] = n

        for src, imps in self.file_imports.items():
            for imp in imps:
                raw_mod = imp.get("module", "")
                target_file = mod_to_file.get(raw_mod) or mod_to_file.get(raw_mod.split(".")[-1])
                if target_file and target_file != src:
                    edge = {"source": src, "target": target_file, "module": raw_mod}
                    if edge not in edges:
                        edges.append(edge)
                        if target_file not in adjacency[src]:
                            adjacency[src].append(target_file)

        # Detect cycles using DFS
        cycles: List[List[str]] = []
        visited: Dict[str, int] = {n: 0 for n in nodes}

        def dfs(curr: str, path: List[str]):
            visited[curr] = 1
            path.append(curr)
            for neighbor in adjacency.get(curr, []):
                if visited.get(neighbor) == 1:
                    cycle_start = path.index(neighbor)
                    cycles.append(path[cycle_start:] + [neighbor])
                elif visited.get(neighbor) == 0:
                    dfs(neighbor, path)
            path.pop()
            visited[curr] = 2

        for n in nodes:
            if visited[n] == 0:
                dfs(n, [])

        return {
            "nodes": nodes,
            "edges": edges,
            "has_cycles": len(cycles) > 0,
            "cycles": cycles,
        }

    def get_definition(self, symbol_name: str) -> Optional[Dict[str, Any]]:
        """Returns the precise definition location and signature of a symbol."""
        sym = symbol_name.strip()
        candidates: List[CodeSymbol] = []
        for sym_list in self.symbols.values():
            for s in sym_list:
                if s.name == sym:
                    candidates.append(s)

        if not candidates:
            return None
        candidates.sort(key=lambda s: 0 if s.kind in ("class", "function", "interface") else 1)
        return candidates[0].to_dict()

