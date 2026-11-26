"""
Comprehensive tests for Customer Runner Spool & Offline Sync Engine.
Tests durable spooling, cryptographic receipts, REST API endpoints, and CLI dispatch.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from cli import build_parser, cmd_runner
from core.api import routes
from core.main import app
from core.runner import RunnerSpoolManager, SpoolBatchReceipt
from core.storage.workspace_fs import WorkspaceFilesystem


@pytest.fixture
def workspace_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Safely isolates workspace filesystem and restores state in a try...finally block."""
    prev_fs = routes._workspace_fs
    monkeypatch.chdir(tmp_path)
    routes.set_workspace_fs(WorkspaceFilesystem(root_dir=str(tmp_path)))
    try:
        yield tmp_path
    finally:
        routes.set_workspace_fs(prev_fs)


def test_runner_spool_enqueue_and_hashing(tmp_path: Path):
    """Test enqueuing items, deterministic canonical SHA-256 calculation, and persistence."""
    spool_file = tmp_path / "spool.json"
    mgr = RunnerSpoolManager(persistence_path=spool_file)

    payload = {"run_id": "run-001", "task": "Run tests", "status": "QUEUED"}
    item = mgr.enqueue_item("runner_east_01", "job_receipt", payload)

    assert item.item_id.startswith("spool_")
    assert item.runner_id == "runner_east_01"
    assert item.item_type == "job_receipt"
    assert item.payload == payload
    assert item.synced is False

    expected_hash = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    assert item.sha256 == expected_hash

    # Verify reload from disk
    mgr2 = RunnerSpoolManager(persistence_path=spool_file)
    assert item.item_id in mgr2.items
    loaded = mgr2.items[item.item_id]
    assert loaded.sha256 == expected_hash
    assert loaded.synced is False


def test_runner_spool_pending_and_marking_synced(tmp_path: Path):
    """Test pending retrieval, limit slicing, marking synced, status, and flushing."""
    spool_file = tmp_path / "spool.json"
    mgr = RunnerSpoolManager(persistence_path=spool_file)

    # Enqueue 3 items for runner_1, 2 items for runner_2
    i1 = mgr.enqueue_item("runner_1", "log", {"msg": "log1"})
    time.sleep(0.01)
    i2 = mgr.enqueue_item("runner_1", "log", {"msg": "log2"})
    time.sleep(0.01)
    i3 = mgr.enqueue_item("runner_1", "receipt", {"msg": "log3"})

    mgr.enqueue_item("runner_2", "log", {"msg": "r2_log1"})
    mgr.enqueue_item("runner_2", "log", {"msg": "r2_log2"})

    pending_r1 = mgr.get_pending_items("runner_1")
    assert len(pending_r1) == 3
    assert [x.item_id for x in pending_r1] == [i1.item_id, i2.item_id, i3.item_id]

    pending_r2 = mgr.get_pending_items("runner_2")
    assert len(pending_r2) == 2

    # Limit parameter
    limited = mgr.get_pending_items("runner_1", limit=2)
    assert len(limited) == 2
    assert [x.item_id for x in limited] == [i1.item_id, i2.item_id]

    # Mark 1 item synced
    marked = mgr.mark_synced([i1.item_id])
    assert marked == 1
    assert len(mgr.get_pending_items("runner_1")) == 2

    # Duplicate mark returns 0
    assert mgr.mark_synced([i1.item_id]) == 0

    # Status check
    status = mgr.get_status("runner_1")
    assert status == {
        "runner_id": "runner_1",
        "pending_count": 2,
        "total_spooled": 3,
    }

    # Flush remaining
    flushed = mgr.flush("runner_1")
    assert flushed == 2
    assert mgr.get_status("runner_1")["pending_count"] == 0
    assert mgr.get_status("runner_1")["total_spooled"] == 3


def test_runner_spool_process_sync_batch_and_receipt(tmp_path: Path):
    """Test batch sync processing, composite batch SHA-256 computation, and receipt generation."""
    spool_file = tmp_path / "spool.json"
    mgr = RunnerSpoolManager(persistence_path=spool_file)

    item1 = mgr.enqueue_item("runner_sync", "metric", {"cpu": 45.2})
    item2 = mgr.enqueue_item("runner_sync", "metric", {"cpu": 48.0})

    batch_payload = [item1.to_dict(), item2.to_dict()]
    receipt = mgr.process_sync_batch("runner_sync", batch_payload)

    assert receipt.batch_id.startswith("batch_")
    assert receipt.runner_id == "runner_sync"
    assert receipt.item_count == 2
    assert receipt.accepted_count == 2
    assert len(receipt.receipt_sha256) == 64

    expected_batch_hash = hashlib.sha256(
        json.dumps(batch_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    assert receipt.receipt_sha256 == expected_batch_hash

    # Both items should now be marked synced
    assert mgr.items[item1.item_id].synced is True
    assert mgr.items[item2.item_id].synced is True

    # Test serialization
    r_dict = receipt.to_dict()
    assert r_dict["batch_id"] == receipt.batch_id
    r_obj = SpoolBatchReceipt.from_dict(r_dict)
    assert r_obj.batch_id == receipt.batch_id
    assert r_obj.receipt_sha256 == receipt.receipt_sha256


def test_runner_spool_rest_api_endpoints(workspace_env: Path):
    """Test /v1/runner/spool/sync and /v1/runner/spool/status/{runner_id} endpoints."""
    spool_dir = workspace_env / ".keelway" / "runner_spool"
    spool_dir.mkdir(parents=True, exist_ok=True)
    spool_file = spool_dir / "spool.json"

    mgr = RunnerSpoolManager(persistence_path=spool_file)
    item = mgr.enqueue_item("runner_api_node", "eval_result", {"score": 0.98})

    with TestClient(app) as client:
        # 1. Check initial status
        res_status = client.get("/v1/runner/spool/status/runner_api_node")
        assert res_status.status_code == 200
        data_status = res_status.json()
        assert data_status["runner_id"] == "runner_api_node"
        assert data_status["pending_count"] == 1
        assert data_status["total_spooled"] == 1

        # 2. Sync batch
        sync_payload = {
            "runner_id": "runner_api_node",
            "items": [item.to_dict()],
        }
        res_sync = client.post("/v1/runner/spool/sync", json=sync_payload)
        assert res_sync.status_code == 200
        data_sync = res_sync.json()
        assert data_sync["runner_id"] == "runner_api_node"
        assert data_sync["item_count"] == 1
        assert data_sync["accepted_count"] == 1
        assert "receipt_sha256" in data_sync

        # 3. Check status after sync
        res_status2 = client.get("/v1/runner/spool/status/runner_api_node")
        assert res_status2.status_code == 200
        assert res_status2.json()["pending_count"] == 0
        assert res_status2.json()["total_spooled"] == 1

        # 4. Error validation
        err1 = client.post("/v1/runner/spool/sync", json={"items": []})
        assert err1.status_code == 400

        err2 = client.post("/v1/runner/spool/sync", json={"runner_id": "r1", "items": "not-a-list"})
        assert err2.status_code == 400


def test_runner_spool_cli_dispatch(tmp_path: Path):
    """Test CLI parser and cmd_runner status and flush dispatch."""
    parser = build_parser()

    # Parser test: runner spool status
    args_st = parser.parse_args(["runner", "spool", "status", "--runner-id", "runner_cli_node"])
    assert args_st.command == "runner"
    assert args_st.runner_command == "spool"
    assert args_st.spool_command == "status"
    assert args_st.runner_id == "runner_cli_node"

    # Parser test: runner spool flush
    args_fl = parser.parse_args(["runner", "spool", "flush", "--runner-id", "runner_cli_node"])
    assert args_fl.command == "runner"
    assert args_fl.runner_command == "spool"
    assert args_fl.spool_command == "flush"
    assert args_fl.runner_id == "runner_cli_node"

    # Execution test with isolated file
    spool_file = tmp_path / "cli_spool.json"
    mgr = RunnerSpoolManager(persistence_path=spool_file)
    mgr.enqueue_item("runner_cli_node", "log", {"text": "hello from CLI"})

    rc_status = cmd_runner("status", runner_id="runner_cli_node", persistence_path=spool_file)
    assert rc_status == 0

    rc_flush = cmd_runner("flush", runner_id="runner_cli_node", persistence_path=spool_file)
    assert rc_flush == 0

    reloaded_mgr = RunnerSpoolManager(persistence_path=spool_file)
    assert reloaded_mgr.get_status("runner_cli_node")["pending_count"] == 0

    rc_invalid = cmd_runner("unknown_action", runner_id="runner_cli_node", persistence_path=spool_file)
    assert rc_invalid == 1
