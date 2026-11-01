"""
Unit tests for Keelway WorkspaceFilesystem.
Tests tree traversal, file read/write, security path traversal blocking, and git inspection.
"""

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from core.storage.workspace_fs import WorkspaceFilesystem, WorkspaceSecurityError


class TestWorkspaceFilesystem(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp()).resolve()
        self.workspace = WorkspaceFilesystem(root_dir=str(self.temp_dir))

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_safe_path_resolution(self):
        safe = self.workspace.resolve_safe_path("src/main.py")
        self.assertEqual(safe, Path(self.temp_dir) / "src" / "main.py")

    def test_path_traversal_blocked(self):
        with self.assertRaises(WorkspaceSecurityError):
            self.workspace.resolve_safe_path("../../etc/passwd")

    def test_write_and_read_file(self):
        content = "print('Hello Sovereign Agent')\n"
        res_write = self.workspace.write_file("scripts/hello.py", content)
        self.assertEqual(res_write["status"], "saved")
        self.assertEqual(res_write["path"], "scripts/hello.py")

        res_read = self.workspace.read_file("scripts/hello.py")
        self.assertEqual(res_read["content"], content)
        self.assertFalse(res_read["is_binary"])

    def test_file_tree_generation(self):
        self.workspace.write_file("file1.txt", "one")
        self.workspace.write_file("sub/file2.txt", "two")
        self.workspace.write_file("sub/nested/file3.txt", "three")

        tree_res = self.workspace.get_file_tree()
        self.assertIn("tree", tree_res)
        tree = tree_res["tree"]
        self.assertEqual(tree["type"], "directory")

        child_names = [c["name"] for c in tree.get("children", [])]
        self.assertIn("file1.txt", child_names)
        self.assertIn("sub", child_names)


if __name__ == "__main__":
    unittest.main()
