"""
Unit tests for Kora AI CodebaseSemanticIndex and AST Symbol Extraction.
Tests Python and TypeScript symbol parsing, incremental hashing, repo map generation, and hybrid search.
"""

import shutil
import tempfile
import unittest
from pathlib import Path

from core.storage.workspace_fs import WorkspaceFilesystem
from core.storage.ast_index import (
    CodebaseSemanticIndex,
    PythonASTExtractor,
    TypeScriptRegexExtractor,
)


class TestASTIndex(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp()).resolve()
        self.fs = WorkspaceFilesystem(root_dir=str(self.temp_dir))
        self.index = CodebaseSemanticIndex(workspace_fs=self.fs)

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_python_ast_extractor(self):
        code = '''
"""Module docstring."""

class QuantumEngine:
    """Manages quantum state registers."""
    def __init__(self, qubits: int):
        self.qubits = qubits

    async def collapse_state(self, seed: int) -> bool:
        """Collapses superposition."""
        return True

def calculate_hamiltonian(matrix):
    return matrix
'''
        symbols = PythonASTExtractor.extract_symbols(code, "quantum.py")
        names = [s.name for s in symbols]
        self.assertIn("QuantumEngine", names)
        self.assertIn("collapse_state", names)
        self.assertIn("calculate_hamiltonian", names)

        # Check docstrings & signatures
        engine_sym = next(s for s in symbols if s.name == "QuantumEngine")
        self.assertEqual(engine_sym.docstring, "Manages quantum state registers.")

        collapse_sym = next(s for s in symbols if s.name == "collapse_state")
        self.assertEqual(collapse_sym.parent_symbol, "QuantumEngine")
        self.assertIn("async def collapse_state(self, seed)", collapse_sym.signature)

    def test_typescript_regex_extractor(self):
        code = '''
export interface UserSession {
  id: string;
  token: string;
}

export type AuthStatus = "authenticated" | "anonymous";

export class SessionManager {
  private active = false;
}

export async function verifyToken(token: string) {
  return true;
}
'''
        symbols = TypeScriptRegexExtractor.extract_symbols(code, "auth.ts")
        names = [s.name for s in symbols]
        self.assertIn("UserSession", names)
        self.assertIn("AuthStatus", names)
        self.assertIn("SessionManager", names)
        self.assertIn("verifyToken", names)

    def test_workspace_indexing_and_repo_map(self):
        self.fs.write_file(
            "src/service.py",
            "class PaymentService:\n    def charge(self, amount):\n        return True\n",
        )
        self.fs.write_file(
            "src/utils.py",
            "def sanitize_input(text):\n    return text.strip()\n",
        )

        res = self.index.index_workspace()
        self.assertEqual(res["total_files_indexed"], 2)
        self.assertGreaterEqual(res["total_symbols_indexed"], 3)

        repo_map = self.index.generate_repo_map()
        self.assertIn("src/service.py:", repo_map)
        self.assertIn("class PaymentService:", repo_map)
        self.assertIn("def charge(self, amount)", repo_map)
        self.assertIn("def sanitize_input(text)", repo_map)

    def test_semantic_symbol_search(self):
        self.fs.write_file(
            "ledger.py",
            "class SovereignLedger:\n    '''Handles tamper-proof settlement records.'''\n    def record_transaction(self, tx_id):\n        pass\n",
        )
        self.fs.write_file(
            "crypto.py",
            "class CipherSuite:\n    '''Encrypts data with AES-GCM.'''\n    def encrypt_payload(self, data):\n        pass\n",
        )
        self.index.index_workspace()

        # Query semantic concepts
        results_tx = self.index.search_symbols("transaction settlement ledger", top_k=3)
        self.assertTrue(len(results_tx) > 0)
        self.assertEqual(results_tx[0]["file_path"], "ledger.py")

        results_crypto = self.index.search_symbols("encrypt cipher AES", top_k=3)
        self.assertTrue(len(results_crypto) > 0)
        self.assertEqual(results_crypto[0]["file_path"], "crypto.py")


if __name__ == "__main__":
    unittest.main()
