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

    def test_sibling_directory_sharing_the_root_prefix_is_blocked(self):
        sibling = Path(str(self.temp_dir) + "-sibling")
        with self.assertRaises(WorkspaceSecurityError):
            self.workspace.resolve_safe_path(f"../{sibling.name}/secret")
        with self.assertRaises(WorkspaceSecurityError):
            self.workspace.resolve_safe_path(str(sibling / "secret"))

    def test_symlink_out_of_the_workspace_is_blocked(self):
        outside = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, outside)
        os.symlink(outside, self.temp_dir / "escape")
        with self.assertRaises(WorkspaceSecurityError):
            self.workspace.resolve_safe_path("escape/secret")
        self.assertEqual(self.workspace.resolve_safe_path(str(self.temp_dir / "a")), self.temp_dir / "a")

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
