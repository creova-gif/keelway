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


class TypeScriptRegexExtractor:
    """Extracts symbols from TypeScript and JavaScript using structural regex grammar."""

    CLASS_RE = re.compile(r"^(?:export\s+)?class\s+([A-Za-z0-9_$]+)(?:\s+extends\s+[A-Za-z0-9_$.]+)?", re.MULTILINE)
    INTERFACE_RE = re.compile(r"^(?:export\s+)?interface\s+([A-Za-z0-9_$]+)", re.MULTILINE)
    TYPE_RE = re.compile(r"^(?:export\s+)?type\s+([A-Za-z0-9_$]+)\s*=", re.MULTILINE)
    FUNCTION_RE = re.compile(r"^(?:export\s+)?(?:async\s+)?function\s+([A-Za-z0-9_$]+)\s*\(([^)]*)\)", re.MULTILINE)
    ARROW_RE = re.compile(r"^(?:export\s+)?const\s+([A-Za-z0-9_$]+)\s*=\s*(?:async\s*)?\(([^)]*)\)\s*(?::\s*[^=]+)?=>", re.MULTILINE)

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


class CodebaseSemanticIndex:
    """Maintains indexed AST symbols, vector embeddings, and condensed RepoMap across workspace files."""

    def __init__(self, workspace_fs: Optional[WorkspaceFilesystem] = None):
        self.fs = workspace_fs or WorkspaceFilesystem()
        self.symbols: Dict[str, List[CodeSymbol]] = {}  # file_path -> symbols
        self.file_hashes: Dict[str, str] = {}           # file_path -> sha256

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
        if relative_path.endswith(".py"):
            symbols = PythonASTExtractor.extract_symbols(content, relative_path)
        elif relative_path.endswith((".ts", ".tsx", ".js", ".jsx")):
            symbols = TypeScriptRegexExtractor.extract_symbols(content, relative_path)

        # Generate dense embeddings for each symbol
        for sym in symbols:
            embed_text = f"{sym.kind} {sym.name} {sym.signature} {sym.docstring or ''}"
            sym.embedding = EmbeddingProvider.get_dense_embedding(embed_text)

        self.symbols[relative_path] = symbols
        self.file_hashes[relative_path] = content_hash
        return symbols

    def index_workspace(self, max_files: int = 200) -> Dict[str, Any]:
        """Indexes all supported code files in the workspace."""
        tree_res = self.fs.get_file_tree(max_depth=4, max_files=max_files)
        total_files = 0
        indexed_symbols_count = 0

        def _walk(node: Dict[str, Any]):
            nonlocal total_files, indexed_symbols_count
            if node.get("type") == "file":
                p = node.get("path", "")
                if p.endswith((".py", ".ts", ".tsx", ".js", ".jsx")):
                    syms = self.index_file(p)
                    total_files += 1
                    indexed_symbols_count += len(syms)
            elif node.get("type") == "directory":
                for child in node.get("children", []):
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
