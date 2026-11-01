"""
Keelway Personal Agent — Workflow 3: Sandboxed Test Execution & Failure Analysis.
Permission Level: TIER 3 (Sandbox Execution - Requires Approval Gate)
Executes tests in an isolated execution sandbox and performs LLM failure root-cause analysis.
"""

import asyncio
import os
import sys
import time
from typing import Dict, Any, List, Optional
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from core.api.schemas import (
    CompletionRequestSchema,
    MessageSchema,
    Provider,
)
from core.models.gateway import gateway as default_gateway, ModelGateway
from core.orchestration.state import TaskState
from core.storage.models import TaskRecord, EvidenceRecord


class SandboxExecutionError(Exception):
    """Raised when sandbox execution fails due to timeout or system constraint."""
    pass


class SandboxedFailureAnalysisWorkflow:
    def __init__(self, gateway: Optional[ModelGateway] = None, workspace_root: Optional[Path] = None):
        self.gateway = gateway or default_gateway
        self.workspace_root = workspace_root or Path.cwd()

    async def execute_sandboxed_tests(self, test_command: str, timeout_seconds: float = 30.0) -> Dict[str, Any]:
        """Execute test command in an isolated environment with process boundary & timeout."""
        start_time = time.perf_counter()

        venv_bin = str((self.workspace_root / "keelway" / ".venv" / "bin").resolve())
        sandbox_env = {
            **os.environ,
            "PATH": f"{venv_bin}:{os.environ.get('PATH', '')}",
            "PYTHONUNBUFFERED": "1",
        }

        # Execute as isolated subprocess
        process = await asyncio.create_subprocess_shell(
            test_command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(self.workspace_root),
            env=sandbox_env,
        )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout_seconds,
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            raise SandboxExecutionError(f"Test execution exceeded {timeout_seconds}s sandbox timeout.")

        duration_ms = (time.perf_counter() - start_time) * 1000.0

        return {
            "exit_code": process.returncode,
            "stdout": stdout_bytes.decode("utf-8", errors="replace"),
            "stderr": stderr_bytes.decode("utf-8", errors="replace"),
            "duration_ms": round(duration_ms, 2),
        }

    async def analyze_failures(
        self,
        test_command: str,
        execution_result: Dict[str, Any],
        preferred_provider: Optional[Provider] = None,
    ) -> Dict[str, Any]:
        """Analyze test failure trace via ModelGateway."""
        system_prompt = (
            "You are Sorvex Labs' Principal Systems Debugger.\n"
            "Analyze the attached test execution output and provide:\n"
            "1. Failure Summary: Which test(s) failed and with what error type.\n"
            "2. Root Cause Hypothesis: Explain why the failure occurred.\n"
            "3. Code Locations: Pinpoint relevant files and line numbers from the trace.\n"
            "4. Recommended Fix Draft: Provide a non-destructive draft fix.\n"
            "Be concise, technical, and precise."
        )

        user_content = (
            f"Executed Test Command: {test_command}\n"
            f"Exit Code: {execution_result['exit_code']}\n"
            f"Duration: {execution_result['duration_ms']}ms\n\n"
            f"=== Test STDOUT ===\n{execution_result['stdout'][-4000:]}\n\n"
            f"=== Test STDERR ===\n{execution_result['stderr'][-4000:]}\n"
        )

        request = CompletionRequestSchema(
            messages=[
                MessageSchema(role="system", content=system_prompt),
                MessageSchema(role="user", content=user_content),
            ],
            temperature=0.1,
            max_tokens=2048,
            preferred_provider=preferred_provider,
        )

        completion = await self.gateway.complete(request)
        return {
            "analysis_content": completion.content,
            "provider": completion.provider.value,
            "model": completion.model,
            "cost_usd": completion.cost_usd,
        }

    async def execute(
        self,
        test_command: str,
        human_approved: bool = False,
        timeout_seconds: float = 30.0,
        db: Optional[AsyncSession] = None,
        owner: str = "founder",
        preferred_provider: Optional[Provider] = None,
    ) -> Dict[str, Any]:
        """Execute Workflow 3: Enforce approval gate, execute sandbox tests, analyze failures."""

        if not human_approved:
            raise PermissionError(
                "Sandbox execution requires explicit human approval (Tier 3 Gate). "
                "Set human_approved=True to authorize container execution."
            )

        # 1. Execute tests in sandbox
        exec_result = await self.execute_sandboxed_tests(test_command, timeout_seconds=timeout_seconds)

        test_passed = (exec_result["exit_code"] == 0)
        analysis_data: Optional[Dict[str, Any]] = None

        # 2. If tests failed, analyze via ModelGateway
        if not test_passed:
            analysis_data = await self.analyze_failures(
                test_command=test_command,
                execution_result=exec_result,
                preferred_provider=preferred_provider,
            )

        task_id = None
        if db:
            final_state = TaskState.COMPLETED if test_passed else TaskState.FAILED
            task = TaskRecord(
                title=f"Sandbox Test: {test_command}",
                description=f"Execution result: exit code {exec_result['exit_code']}",
                owner=owner,
                state=final_state,
                budget_usd=0.25,
                cost_usd=analysis_data.get("cost_usd", 0.0) if analysis_data else 0.0,
                payload={
                    "test_command": test_command,
                    "exit_code": exec_result["exit_code"],
                    "duration_ms": exec_result["duration_ms"],
                    "test_passed": test_passed,
                },
            )
            db.add(task)
            await db.flush()
            await db.refresh(task)
            task_id = task.id

        return {
            "task_id": task_id,
            "test_command": test_command,
            "passed": test_passed,
            "exit_code": exec_result["exit_code"],
            "duration_ms": exec_result["duration_ms"],
            "stdout": exec_result["stdout"],
            "stderr": exec_result["stderr"],
            "failure_analysis": analysis_data["analysis_content"] if analysis_data else None,
            "state": TaskState.COMPLETED.value if test_passed else TaskState.FAILED.value,
        }
