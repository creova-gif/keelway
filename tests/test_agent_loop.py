"""
Unit tests for Kora AI AutonomousAgentLoop.
Tests tool execution, planning state machine, human-in-the-loop approval, and flight recording.
"""

import asyncio
import os
import shutil
import tempfile
import unittest

from core.storage.workspace_fs import WorkspaceFilesystem
from core.orchestration.agent_loop import (
    AutonomousAgentLoop,
    AgentLoopStatus,
    AutonomyPolicy,
)


class TestAutonomousAgentLoop(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.fs = WorkspaceFilesystem(root_dir=self.temp_dir)
        self.agent = AutonomousAgentLoop(
            task_id="test_task_01",
            workspace_fs=self.fs,
            policy=AutonomyPolicy.CONFIRM_MUTATION,
            record_flight=False,
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    async def test_read_tool_runs_unprompted(self):
        # Create file first
        self.fs.write_file("config.json", '{"version": 1}')
        
        # read_file is non-mutating, so should run immediately
        res = await self.agent.execute_tool("read_file", {"path": "config.json"})
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["result"]["content"], '{"version": 1}')

    async def test_mutation_requires_approval_under_confirm_policy(self):
        # write_file is mutating
        res = await self.agent.execute_tool("write_file", {"path": "out.txt", "content": "data"})
        self.assertEqual(res["status"], "paused_for_approval")
        self.assertEqual(self.agent.status, AgentLoopStatus.AWAITING_APPROVAL)
        self.assertIsNotNone(self.agent.pending_approval)

        # Approve execution
        app_res = await self.agent.approve_pending(approved=True)
        self.assertEqual(app_res["status"], "success")
        self.assertTrue((self.fs.root / "out.txt").exists())

    async def test_autonomous_policy_runs_mutations_without_pause(self):
        auto_agent = AutonomousAgentLoop(
            task_id="auto_task_02",
            workspace_fs=self.fs,
            policy=AutonomyPolicy.AUTONOMOUS,
            record_flight=False,
        )
        res = await auto_agent.execute_tool("write_file", {"path": "auto.txt", "content": "auto-content"})
        self.assertEqual(res["status"], "success")
        self.assertTrue((self.fs.root / "auto.txt").exists())

    async def test_edit_file_tool(self):
        self.fs.write_file("main.py", "def add(a, b):\n    return a - b\n")
        auto_agent = AutonomousAgentLoop(
            task_id="auto_task_03",
            workspace_fs=self.fs,
            policy=AutonomyPolicy.AUTONOMOUS,
            record_flight=False,
        )
        res = await auto_agent.execute_tool(
            "edit_file",
            {"path": "main.py", "target": "return a - b", "replacement": "return a + b"},
        )
        self.assertEqual(res["status"], "success")
        updated = self.fs.read_file("main.py")["content"]
        self.assertIn("return a + b", updated)

    async def test_plan_lifecycle(self):
        self.agent.initialize_plan("Fix calculation bug", ["Find file", "Apply patch", "Run tests"])
        state = self.agent.get_state()
        self.assertEqual(len(state["plan"]), 3)
        self.assertEqual(state["plan"][0]["status"], "pending")


if __name__ == "__main__":
    unittest.main()
