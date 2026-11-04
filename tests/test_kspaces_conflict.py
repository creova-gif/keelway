"""
Automated test suite for Multi-Agent Git Conflict Detection & Autonomous Resolution Engine in KSpaces.
Tests clean merges, non-overlapping additions, overlapping mutation detection, resolution strategies,
REST API (/conflicts/check, /conflicts/resolve, /timeline), and CLI dispatch.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
import pytest
from httpx import ASGITransport, AsyncClient

from cli import build_parser, cmd_space
from core.api import routes
from core.kspaces.conflict import ConflictDetector, ConflictHunk, ConflictReport
from core.kspaces.manager import KSpacesManager, kspaces_manager
from core.main import app
from core.storage.workspace_fs import WorkspaceFilesystem


@pytest.fixture
def workspace_fixture():
    """
    Temporary workspace fixture ensuring routes._workspace_fs is cleanly restored
    in a try...finally block.
    """
    prev_fs = routes._workspace_fs
    tmp_dir = tempfile.mkdtemp(prefix="keelway_conflict_test_")
    fs = WorkspaceFilesystem(root_dir=tmp_dir)
    routes.set_workspace_fs(fs)
    try:
        yield Path(tmp_dir)
    finally:
        routes.set_workspace_fs(prev_fs)
        shutil.rmtree(tmp_dir, ignore_errors=True)


# =====================================================================
# 1. Unit Tests: 3-Way Merge & Classification
# =====================================================================

def test_clean_3way_merge_identical_or_one_sided():
    """Verify clean 3-way merge when changes are identical or one-sided."""
    base = "line1\nline2\nline3\n"
    left = "line1\nline2_modified\nline3\n"
    right = "line1\nline2\nline3\n"  # Right is untouched

    report = ConflictDetector.detect_3way(base, left, right, file_path="config.py")
    assert report.has_conflicts is False
    assert report.auto_resolvable is True
    assert len(report.conflict_files) == 0
    assert report.hunks[0].conflict_type == "clean"
    assert report.hunks[0].resolved_content == left

    # Both made identical changes
    report_identical = ConflictDetector.detect_3way(base, left, left, file_path="config.py")
    assert report_identical.has_conflicts is False
    assert report_identical.auto_resolvable is True
    assert report_identical.hunks[0].resolved_content == left


def test_non_overlapping_additions_auto_resolution():
    """Verify non-overlapping additions (e.g. left adds func A, right adds func B) auto-resolve cleanly."""
    base = "# Module Header\n\ndef core_engine():\n    return 'ready'\n\n# Module Footer\n"
    left = (
        "# Module Header\n\n"
        "def helper_left():\n    return 'left'\n\n"
        "def core_engine():\n    return 'ready'\n\n"
        "# Module Footer\n"
    )
    right = (
        "# Module Header\n\n"
        "def core_engine():\n    return 'ready'\n\n"
        "def helper_right():\n    return 'right'\n\n"
        "# Module Footer\n"
    )

    report = ConflictDetector.detect_3way(base, left, right, file_path="engine.py")
    assert report.has_conflicts is False
    assert report.auto_resolvable is True
    assert any(h.conflict_type == "non_overlapping_addition" for h in report.hunks)

    resolved = ConflictDetector.resolve_3way(base, left, right, strategy="auto")
    assert "def helper_left():" in resolved
    assert "def helper_right():" in resolved
    assert "def core_engine():" in resolved


def test_overlapping_mutation_conflict_detection():
    """Verify overlapping mutations to identical lines are detected with conflict markers."""
    base = "def calculate_tax(rate):\n    return rate * 1.05\n"
    left = "def calculate_tax(rate):\n    return rate * 1.08  # left update\n"
    right = "def calculate_tax(rate):\n    return rate * 1.10  # right update\n"

    report = ConflictDetector.detect_3way(base, left, right, file_path="tax.py")
    assert report.has_conflicts is True
    assert report.auto_resolvable is False
    assert "tax.py" in report.conflict_files

    conflict_hunk = next(h for h in report.hunks if not h.is_clean)
    assert conflict_hunk.conflict_type == "overlapping_mutation"
    assert "<<<<<<< LEFT" in conflict_hunk.resolved_content
    assert "=======" in conflict_hunk.resolved_content
    assert ">>>>>>> RIGHT" in conflict_hunk.resolved_content


def test_resolution_strategies():
    """Test resolution strategies: left, right, base, auto."""
    base = "timeout = 30\n"
    left = "timeout = 60\n"
    right = "timeout = 90\n"

    report = ConflictDetector.detect_3way(base, left, right, file_path="settings.py")
    hunk = report.hunks[0]

    assert ConflictDetector.resolve_hunk(hunk, strategy="left") == left
    assert ConflictDetector.resolve_hunk(hunk, strategy="right") == right
    assert ConflictDetector.resolve_hunk(hunk, strategy="base") == base

    auto_res = ConflictDetector.resolve_hunk(hunk, strategy="auto")
    assert "<<<<<<< LEFT" in auto_res
    assert "timeout = 60" in auto_res
    assert "timeout = 90" in auto_res

    # Test full 3-way text resolution
    assert ConflictDetector.resolve_3way(base, left, right, strategy="left") == left
    assert ConflictDetector.resolve_3way(base, left, right, strategy="right") == right
    assert ConflictDetector.resolve_3way(base, left, right, strategy="base") == base


# =====================================================================
# 2. Manager & Timeline Unit Tests
# =====================================================================

def test_kspaces_manager_timeline(tmp_path: Path):
    """Test recording and retrieving space timeline events with persistence."""
    store_file = tmp_path / "spaces.json"
    mgr = KSpacesManager(persistence_path=store_file)
    mgr.create_space("space_timeline_test", "Timeline Test Space", owner_id="alice")

    ev1 = mgr.record_timeline_event(
        space_id="space_timeline_test",
        actor="alice",
        event_type="branch_created",
        details={"branch": "feature/ui"},
    )
    ev2 = mgr.record_timeline_event(
        space_id="space_timeline_test",
        actor="bob",
        event_type="conflict_check",
        details={"file": "ui.py", "has_conflicts": False},
    )

    timeline = mgr.get_timeline("space_timeline_test")
    assert len(timeline) == 2
    assert timeline[0]["event_id"] == ev1["event_id"]
    assert timeline[1]["event_id"] == ev2["event_id"]

    # Verify reload from disk
    mgr2 = KSpacesManager(persistence_path=store_file)
    reloaded_timeline = mgr2.get_timeline("space_timeline_test")
    assert len(reloaded_timeline) == 2
    assert reloaded_timeline[1]["event_type"] == "conflict_check"


# =====================================================================
# 3. REST API Tests
# =====================================================================

@pytest.mark.asyncio
async def test_kspaces_conflict_and_timeline_rest_api(workspace_fixture: Path):
    """Test /conflicts/check, /conflicts/resolve, and /timeline REST endpoints."""
    import time
    space_id = f"space_conflict_api_{int(time.time() * 1000)}"
    if space_id not in kspaces_manager._spaces:
        kspaces_manager.create_space(space_id, "API Test Space", owner_id="lead_eng")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Test Conflict Check (Non-overlapping)
        check_resp = await client.post(
            f"/v1/kspaces/{space_id}/conflicts/check",
            json={
                "base_text": "A\nB\n",
                "left_text": "A\nB\nL\n",
                "right_text": "R\nA\nB\n",
                "file_path": "app.py",
            },
            headers={"X-Keelway-Actor": "lead_eng", "X-Keelway-Role": "platform_owner"},
        )
        assert check_resp.status_code == 200, check_resp.text
        report_data = check_resp.json()
        assert report_data["has_conflicts"] is False
        assert report_data["auto_resolvable"] is True

        # 2. Test Conflict Check (Overlapping)
        conflict_check_resp = await client.post(
            f"/v1/kspaces/{space_id}/conflicts/check",
            json={
                "base_text": "VAL = 1\n",
                "left_text": "VAL = 2\n",
                "right_text": "VAL = 3\n",
                "file_path": "constants.py",
            },
            headers={"X-Keelway-Actor": "lead_eng", "X-Keelway-Role": "platform_owner"},
        )
        assert conflict_check_resp.status_code == 200
        conflict_data = conflict_check_resp.json()
        assert conflict_data["has_conflicts"] is True
        assert conflict_data["auto_resolvable"] is False

        # 3. Test Conflict Resolve
        resolve_resp = await client.post(
            f"/v1/kspaces/{space_id}/conflicts/resolve",
            json={
                "base_text": "VAL = 1\n",
                "left_text": "VAL = 2\n",
                "right_text": "VAL = 3\n",
                "strategy": "left",
            },
            headers={"X-Keelway-Actor": "lead_eng", "X-Keelway-Role": "platform_owner"},
        )
        assert resolve_resp.status_code == 200
        assert resolve_resp.json()["status"] == "resolved"
        assert resolve_resp.json()["resolved_text"] == "VAL = 2\n"

        # 4. Test Timeline Retrieval
        timeline_resp = await client.get(
            f"/v1/kspaces/{space_id}/timeline",
            headers={"X-Keelway-Actor": "lead_eng", "X-Keelway-Role": "platform_owner"},
        )
        assert timeline_resp.status_code == 200
        events = timeline_resp.json()["events"]
        assert len(events) >= 3  # Recorded conflict_check and conflict_resolved


# =====================================================================
# 4. CLI Tests
# =====================================================================

def test_cli_space_conflict_parser():
    """Verify build_parser wires space conflict and timeline subcommands."""
    parser = build_parser()

    # space conflict
    args_cnf = parser.parse_args([
        "space", "conflict",
        "--base", "base.py",
        "--left", "left.py",
        "--right", "right.py",
        "--strategy", "auto",
    ])
    assert args_cnf.command == "space"
    assert args_cnf.space_command == "conflict"
    assert args_cnf.base == Path("base.py")
    assert args_cnf.left == Path("left.py")
    assert args_cnf.right == Path("right.py")
    assert args_cnf.strategy == "auto"

    # space timeline
    args_tml = parser.parse_args(["space", "timeline", "sp_beta", "--limit", "15"])
    assert args_tml.command == "space"
    assert args_tml.space_command == "timeline"
    assert args_tml.space_id == "sp_beta"
    assert args_tml.limit == 15


def test_cli_space_conflict_and_timeline_execution(tmp_path: Path):
    """Test cmd_space execution for conflict detection and timeline display."""
    base_file = tmp_path / "base.txt"
    left_file = tmp_path / "left.txt"
    right_file = tmp_path / "right.txt"

    # Non-conflicting additions
    base_file.write_text("common\n", encoding="utf-8")
    left_file.write_text("left_add\ncommon\n", encoding="utf-8")
    right_file.write_text("common\nright_add\n", encoding="utf-8")

    rc_clean = cmd_space(
        action="conflict",
        base=base_file,
        left=left_file,
        right=right_file,
        strategy="auto",
    )
    assert rc_clean == 0

    # Overlapping conflict
    left_file.write_text("conflict_left\n", encoding="utf-8")
    right_file.write_text("conflict_right\n", encoding="utf-8")

    rc_conflict = cmd_space(
        action="conflict",
        base=base_file,
        left=left_file,
        right=right_file,
        strategy="auto",
    )
    assert rc_conflict == 1

    # Timeline command
    rc_timeline = cmd_space(action="timeline", space_id="demo_space")
    assert rc_timeline == 0
