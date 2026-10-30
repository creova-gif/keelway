"""
Standard library unit tests for Kora AI Autonomous Self-Healing Verification Loop.
Runs in clean zero-dependency environments.
"""

import asyncio
import sys
import tempfile
import unittest
from pathlib import Path
from core.orchestration.self_healing import SelfHealingLoop, DiagnosticFailure


class TestSelfHealingLoop(unittest.TestCase):
    def test_parse_pytest_traceback(self):
        sample_pytest_output = """
============================= FAILURES =============================
___________________________ test_calculation ___________________________

    def test_calculation():
>       assert multiply(3, 4) == 10
E       AssertionError: assert 12 == 10

kora/math/ops.py:42: AssertionError
=========================== short test summary info ===========================
FAILED kora/math/ops.py::test_calculation - AssertionError: assert 12 == 10
File "kora/math/ops.py", line 42, in test_calculation
"""
        loop = SelfHealingLoop()
        diag = loop.parse_test_failure(sample_pytest_output)

        self.assertIsNotNone(diag)
        self.assertEqual(diag.file_path, "kora/math/ops.py")
        self.assertEqual(diag.line_number, 42)
        self.assertEqual(diag.function_or_symbol, "test_calculation")
        self.assertEqual(diag.exception_type, "AssertionError")

    def test_parse_js_traceback(self):
        sample_js_output = """
FAIL src/calc.test.ts
  ✕ multiplies correctly (5ms)

  ● multiplies correctly

    expect(received).toBe(expected) // Object.is equality

    Expected: 10
    Received: 12

      at Object.testCalculation (src/calc.ts:25:9)
"""
        loop = SelfHealingLoop()
        diag = loop.parse_test_failure(sample_js_output)

        self.assertIsNotNone(diag)
        self.assertEqual(diag.file_path, "src/calc.ts")
        self.assertEqual(diag.line_number, 25)
        self.assertEqual(diag.function_or_symbol, "testCalculation")
        self.assertEqual(diag.exception_type, "JavaScriptRuntimeError")

    def test_locate_faulty_ast_python(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            source_file = tmp_path / "service.py"
            source_file.write_text(
                "import os\n\n"
                "def process_data(data):\n"
                "    value = data['count']\n"
                "    result = value * 2\n"
                "    return result\n\n"
                "def helper():\n"
                "    return True\n",
                encoding="utf-8"
            )

            loop = SelfHealingLoop(repo_root=tmp_path)
            ast_info = loop.locate_faulty_ast(source_file, line_number=4)

            self.assertEqual(ast_info["symbol"], "process_data")
            self.assertEqual(ast_info["type"], "FunctionDef")
            self.assertEqual(ast_info["start_line"], 3)
            self.assertEqual(ast_info["end_line"], 6)
            self.assertIn("value = data['count']", ast_info["code_block"])

    def test_self_healing_closed_loop_repair(self):
        async def _run_async_test():
            with tempfile.TemporaryDirectory() as tmpdir:
                tmp_path = Path(tmpdir)
                script = tmp_path / "app.py"
                script.write_text(
                    "def compute():\n"
                    "    return 10\n\n"
                    "if __name__ == '__main__':\n"
                    "    assert compute() == 20\n",
                    encoding="utf-8"
                )

                loop = SelfHealingLoop(repo_root=tmp_path)

                async def dummy_patch_gen(diag, ast_info, attempt):
                    return "def compute():\n    return 20"

                test_cmd = f"{sys.executable} {script}"
                result = await loop.run_repair_cycle(
                    test_cmd=test_cmd,
                    patch_generator_fn=dummy_patch_gen,
                    max_attempts=2
                )

                self.assertTrue(result.success)
                self.assertEqual(result.attempts, 1)
                self.assertIn("def compute():\n    return 20", script.read_text(encoding="utf-8"))

        asyncio.run(_run_async_test())


if __name__ == "__main__":
    unittest.main()
