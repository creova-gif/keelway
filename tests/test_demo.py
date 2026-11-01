import json
import subprocess
import sys

import pytest

from core import demo


def test_prepare_workspace_writes_buggy_sample_and_is_idempotent(tmp_path):
    root = demo.prepare_workspace(tmp_path / "d")
    assert demo.BUGGY_LINE in (root / "pricing.py").read_text()
    assert set(demo.FILES) <= {p.name for p in root.iterdir()}
    (root / ".kora").mkdir()
    (root / demo.SEEDED_MARKER).write_text("1\n")
    (root / "pricing.py").write_text("edited")
    assert demo.prepare_workspace(root) == root
    assert (root / "pricing.py").read_text() == "edited"


def test_refuses_non_demo_folders(tmp_path):
    (tmp_path / "keep.txt").write_text("mine")
    with pytest.raises(SystemExit):
        demo.prepare_workspace(tmp_path)
    with pytest.raises(SystemExit):
        demo.prepare_workspace(tmp_path, reset=True)
    assert (tmp_path / "keep.txt").exists()


def test_seed_records_a_real_sealed_tape_in_its_own_db(tmp_path):
    root = demo.prepare_workspace(tmp_path / "d")
    (root / ".kora").mkdir()
    subprocess.run(
        [sys.executable, "-c", "import asyncio, pathlib; from core.demo import seed; asyncio.run(seed(pathlib.Path.cwd()))"],
        cwd=root, env=demo._demo_env(root), check=True, capture_output=True,
    )
    assert (root / ".kora" / "demo.db").exists()
    assert (root / "money.py").exists()
    tape = json.loads((root / ".kora" / "recordings" / f"{demo.PAST_TASK_ID}.flight.json").read_text())
    kinds = [e["event_type"] for e in tape["events"]]
    assert kinds[0] == "plan_initialized"
    assert "approval_granted" in kinds and "tool:write_file" in kinds
    assert len(tape["tape_sha256"]) == 64


def test_reset_refuses_a_marked_folder_with_foreign_files(tmp_path):
    (tmp_path / ".kora").mkdir()
    (tmp_path / demo.SEEDED_MARKER).write_text("1\n")
    (tmp_path / "src").mkdir()
    with pytest.raises(SystemExit):
        demo.prepare_workspace(tmp_path, reset=True)
    assert (tmp_path / "src").exists()
