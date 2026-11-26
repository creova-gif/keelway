"""
Keelway Autonomous Self-Healing Verification Loop.
Detects test and build failures, performs AST fault localization,
explores candidate patches in isolated worktrees, and verifies zero-regression repair.
"""

import ast
import asyncio
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

from core.security.env_scrub import scrub_env
from core.orchestration.worktree import EphemeralWorktreeManager, WorktreeSession


@dataclass
class DiagnosticFailure:
    """Represents a localized test or compile failure."""
    file_path: str
    line_number: int
    function_or_symbol: Optional[str]
    exception_type: str
    error_message: str
    raw_output: str


@dataclass
class RepairResult:
    """Outcome of an autonomous repair attempt."""
    success: bool
    attempts: int
    original_failure: Optional[DiagnosticFailure]
    applied_patch: Optional[str]
    verification_output: str
    diff: Optional[str] = None


class SelfHealingLoop:
    """Autonomous closed-loop test-and-repair engine for sovereign developer workspaces."""

    def __init__(self, repo_root: Optional[Path] = None, worktree_manager: Optional[EphemeralWorktreeManager] = None):
        self.repo_root = repo_root or Path.cwd()
        self.worktree_manager = worktree_manager or EphemeralWorktreeManager(self.repo_root)

    def parse_test_failure(self, output: str) -> Optional[DiagnosticFailure]:
        """Parses stdout/stderr from pytest, vitest, or standard compilers to extract failure coordinates."""
        # 1. Python Pytest / Traceback pattern
        # Look for: File "path/to/file.py", line 42, in test_something
        py_matches = list(re.finditer(r'File ["\']([^"\']+\.py)["\'], line (\d+)(?:, in ([^\n,]+))?', output))
        if py_matches:
            # Grab the last frame in the stack trace (closest to error location)
            last_match = py_matches[-1]
            file_path = last_match.group(1)
            line_no = int(last_match.group(2))
            symbol = last_match.group(3).strip() if last_match.group(3) else None

            # Extract exception type and message
            exc_match = re.search(r'([A-Za-z_][A-Za-z0-9_]*Error|[A-Za-z_][A-Za-z0-9_]*Exception|AssertionError):\s*(.*)', output)
            exc_type = exc_match.group(1) if exc_match else "AssertionError"
            exc_msg = exc_match.group(2).strip() if exc_match else "Test assertion failed"

            return DiagnosticFailure(
                file_path=file_path,
                line_number=line_no,
                function_or_symbol=symbol,
                exception_type=exc_type,
                error_message=exc_msg,
                raw_output=output[:1000]
            )

        # 2. JavaScript / TypeScript pattern: at functionName (path/to/file.ts:42:10)
        js_match = re.search(r'at (?:([A-Za-z0-9_.]+) )?\(?([^:\s()]+\.(?:js|ts|jsx|tsx)):(\d+):\d+\)?', output)
        if js_match:
            raw_sym = js_match.group(1)
            symbol = raw_sym.split(".")[-1] if raw_sym else None
            file_path = js_match.group(2)
            line_no = int(js_match.group(3))
            return DiagnosticFailure(
                file_path=file_path,
                line_number=line_no,
                function_or_symbol=symbol,
                exception_type="JavaScriptRuntimeError",
                error_message="Runtime exception or failed assertion in test runner",
                raw_output=output[:1000]
            )

        # Generic assertion failure pattern
        if "FAILED" in output or "AssertionError" in output:
            return DiagnosticFailure(
                file_path="unknown",
                line_number=1,
                function_or_symbol=None,
                exception_type="GeneralFailure",
                error_message=output.strip()[-200:],
                raw_output=output[:1000]
            )

        return None

    def locate_faulty_ast(self, file_path: Path, line_number: int) -> Dict[str, Any]:
        """Uses AST parsing to locate the enclosing function or class definition."""
        if not file_path.exists():
            return {"error": "File does not exist", "context": ""}

        content = file_path.read_text(encoding="utf-8", errors="replace")
        lines = content.splitlines()

        if file_path.suffix == ".py":
            try:
                tree = ast.parse(content)
                target_node = None
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                        start_line = getattr(node, "lineno", 1)
                        end_line = getattr(node, "end_lineno", len(lines))
                        if start_line <= line_number <= end_line:
                            target_node = node

                if target_node:
                    start_idx = target_node.lineno - 1
                    end_idx = target_node.end_lineno
                    return {
                        "symbol": target_node.name,
                        "type": type(target_node).__name__,
                        "start_line": target_node.lineno,
                        "end_line": target_node.end_lineno,
                        "code_block": "\n".join(lines[start_idx:end_idx]),
                    }
            except SyntaxError:
                pass

        # Fallback context window: line_number +/- 15 lines
        start_idx = max(0, line_number - 15)
        end_idx = min(len(lines), line_number + 15)
        return {
            "symbol": None,
            "type": "ContextWindow",
            "start_line": start_idx + 1,
            "end_line": end_idx,
            "code_block": "\n".join(lines[start_idx:end_idx]),
        }

    async def execute_test(self, test_cmd: str, cwd: Optional[Path] = None) -> Tuple[int, str, str]:
        """Runs a test command in the given directory using the active Python virtual environment."""
        target_dir = cwd or self.repo_root
        import sys

        # Resolve python executable: check virtual environment in workspace, adjacent venvs, or sys.prefix
        py_exe = sys.executable
        candidate_venvs = [
            target_dir / ".venv" / "bin" / "python",
            target_dir.parent / "keelway-ai.nosync" / ".venv" / "bin" / "python",
            target_dir.parent / "kora-ai.nosync" / ".venv" / "bin" / "python",
            Path(os.environ.get("VIRTUAL_ENV", "")) / "bin" / "python"
        ]
        for cv in candidate_venvs:
            if cv.exists() and os.access(cv, os.X_OK):
                py_exe = str(cv)
                break

        if test_cmd.startswith("pytest ") or test_cmd == "pytest":
            rest = test_cmd[6:].strip() if test_cmd.startswith("pytest ") else ""
            test_cmd = f"{py_exe} -m pytest {rest}".strip()
        elif test_cmd.startswith("python3 ") or test_cmd.startswith("python "):
            parts = test_cmd.split(" ", 1)
            test_cmd = f"{py_exe} {parts[1]}"

        sub_env, _ = scrub_env(os.environ)  # patched code runs in these tests: it must not see API keys
        py_bin_dir = str(Path(py_exe).parent)
        sub_env["PATH"] = f"{py_bin_dir}:{sub_env.get('PATH', '')}"
        sub_env["PYTHONPATH"] = f"{target_dir}:{sub_env.get('PYTHONPATH', '')}"

        proc = await asyncio.create_subprocess_shell(
            test_cmd,
            cwd=str(target_dir),
            env=sub_env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        return (
            proc.returncode if proc.returncode is not None else -1,
            stdout.decode(errors="replace"),
            stderr.decode(errors="replace"),
        )

    def apply_patch_to_file(self, file_path: Path, old_block: str, new_block: str) -> bool:
        """Surgically replaces the faulty code block in the target file."""
        if not file_path.exists():
            return False
        content = file_path.read_text(encoding="utf-8")
        if old_block in content:
            updated = content.replace(old_block, new_block, 1)
            file_path.write_text(updated, encoding="utf-8")
            return True
        return False

    async def run_repair_cycle(
        self,
        test_cmd: str,
        patch_generator_fn: Optional[Any] = None,
        max_attempts: int = 3,
    ) -> RepairResult:
        """
        Executes the closed-loop repair cycle:
        1. Run test command. If passes, return success immediately.
        2. If fails, parse error and extract faulty AST block.
        3. Spin up an isolated Ephemeral Worktree.
        4. Apply candidate patch and rerun test.
        5. Verify that error is resolved. If verified, propagate back to main repo.
        """
        code, stdout, stderr = await self.execute_test(test_cmd)
        combined_out = stdout + "\n" + stderr

        if code == 0:
            return RepairResult(
                success=True,
                attempts=0,
                original_failure=None,
                applied_patch=None,
                verification_output="Suite already passing cleanly. No repair needed."
            )

        diag = self.parse_test_failure(combined_out)
        if not diag:
            return RepairResult(
                success=False,
                attempts=1,
                original_failure=None,
                applied_patch=None,
                verification_output=f"Could not parse diagnostic coordinates from failure output:\n{combined_out[:400]}"
            )

        # Resolve relative file path against repo root
        raw_path = Path(diag.file_path)
        if raw_path.is_absolute():
            try:
                rel_path = raw_path.relative_to(self.repo_root)
                abs_path = self.repo_root / rel_path
            except ValueError:
                abs_path = raw_path
                rel_path = Path(raw_path.name)
        else:
            rel_path = raw_path
            abs_path = self.repo_root / rel_path

        ast_info = self.locate_faulty_ast(abs_path, diag.line_number)

        # Isolated Worktree session
        session: Optional[WorktreeSession] = None
        try:
            session = await self.worktree_manager.create_worktree(f"repair_{os.getpid()}")
            worktree_file = session.worktree_dir / rel_path

            for attempt in range(1, max_attempts + 1):
                # Generate candidate patch
                if patch_generator_fn:
                    candidate_fix = await patch_generator_fn(diag, ast_info, attempt)
                else:
                    # Default heuristic fallback patch (used for self-contained testing)
                    candidate_fix = None

                if candidate_fix and worktree_file.exists():
                    old_code = ast_info.get("code_block", "")
                    if old_code:
                        self.apply_patch_to_file(worktree_file, old_code, candidate_fix)

                    # Rerun test in the worktree
                    cmd_in_worktree = test_cmd.replace(str(self.repo_root), str(session.worktree_dir))
                    retry_code, retry_out, retry_err = await session.run_command(cmd_in_worktree)
                    if retry_code == 0:
                        # Patch is verified! Apply to the actual main repo file
                        self.apply_patch_to_file(abs_path, old_code, candidate_fix)
                        return RepairResult(
                            success=True,
                            attempts=attempt,
                            original_failure=diag,
                            applied_patch=candidate_fix,
                            verification_output=f"Patch verified in isolated worktree on attempt {attempt}.",
                            diff=f"--- {diag.file_path}\n+++ {diag.file_path}\n"
                        )

            return RepairResult(
                success=False,
                attempts=max_attempts,
                original_failure=diag,
                applied_patch=None,
                verification_output=f"Exhausted {max_attempts} attempts without verified resolution."
            )
        finally:
            if session:
                await self.worktree_manager.cleanup_worktree(session)
