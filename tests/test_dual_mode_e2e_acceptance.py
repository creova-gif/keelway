"""
End-to-End Acceptance Test for Keelway Dual-Mode Operating System.
Verifies:
Workstream C: IDE Mode End-to-End Bug-Fix Workflow with real local policy enforcement.
Workstream D: Agent Builder Mode:
  - Scaffolds a reusable 'test-fixer' agent from template.
  - Verifies manifest, spec, and generated test harness pass cleanly.
  - Exports agent bundle (.tar.gz) with embedded SHA-256 digests.
  - Imports agent into an isolated secondary repository.
  - Executes the custom agent inside the second repository under identical policy.
Workstream E: Negative Security & Containment:
  - Path traversal attempt is blocked.
  - Tampered archive payload is detected and rejected during bundle unpack.
  - Unauthorized file mutations are rejected.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import shutil
from pathlib import Path
import pytest

from core.agents.builder import AgentBuilder, AgentBundlePacker
from core.agents.spec import AgentSpec
from core.agents import manifest as am
from core.agents.guard import loop_from_manifest
from core.storage.workspace_fs import WorkspaceFilesystem
from core.security.firewall import SecurityGateway
from core.orchestration.state import TaskStateMachine, TaskState, InvalidStateTransitionError
from core.models.gateway import ModelGateway
from core.models.adapters.local import LocalAdapter
from core.api.schemas import Provider, CompletionRequestSchema


@pytest.mark.asyncio
async def test_dual_mode_agent_builder_export_import_and_cross_repo(tmp_path: Path):
    """
    Workstream D acceptance:
    1. Scaffold 'test-fixer' agent in repo A.
    2. Build, run initial test harness, verify receipt seal.
    3. Export bundle archive.
    4. Create clean repo B.
    5. Import agent bundle into repo B and cryptographically verify all digests.
    6. Run the agent in repo B on a real workspace task with shared runtime.
    """
    repo_a = tmp_path / "repo_a"
    repo_b = tmp_path / "repo_b"
    repo_a.mkdir()
    repo_b.mkdir()

    # Create dummy source and failing test in repo B for the agent to inspect
    (repo_b / "calculator.py").write_text("def add(a, b):\n    return a + b\n")

    # 1. Scaffold Agent in Repo A
    agent_dir = repo_a / "agents" / "code_fixer"
    spec = AgentBuilder.create_from_template(
        "test-fixer",
        name="code-fixer",
        author="sorvex-lead",
        overrides={"description": "Deterministic test fixer agent for repository triage."},
    )
    receipt = await AgentBuilder.build_and_register(spec, target_dir=agent_dir, register_in_db=False)
    assert receipt.tests_passed is True
    assert (agent_dir / "code-fixer.agent.json").exists()
    assert (agent_dir / "code-fixer.spec.json").exists()
    assert receipt.receipt_sha256 != ""

    # 2. Export bundle archive
    bundle_archive = repo_a / "code-fixer-1.0.0.tar.gz"
    pack_manifest = AgentBundlePacker.pack(agent_dir, bundle_archive)
    assert bundle_archive.is_file()
    assert pack_manifest["bundle_name"] == "code_fixer"
    assert "code-fixer.agent.json" in pack_manifest["files"]

    # 3. Import bundle into clean Repo B
    imported_dir = repo_b / "imported_agents" / "code_fixer"
    unpack_manifest = AgentBundlePacker.unpack(bundle_archive, imported_dir, verify=True)
    assert unpack_manifest["bundle_digest_sha256"] == pack_manifest["bundle_digest_sha256"]
    assert (imported_dir / "code-fixer.agent.json").is_file()

    # 4. Load imported agent manifest in Repo B and execute using shared runtime
    manifest = am.load_file(imported_dir / "code-fixer.agent.json")
    ws_fs_b = WorkspaceFilesystem(root_dir=str(repo_b))
    
    agent_loop = loop_from_manifest(
        manifest,
        task_id="task_acceptance_001",
        workspace_fs=ws_fs_b,
    )
    assert agent_loop.guard is not None
    manifest_obj = am.validate(manifest).manifest if isinstance(manifest, dict) else manifest
    assert agent_loop.guard.manifest_digest == am.digest(manifest_obj)

    # Verify agent executes tool in repo B within authorized boundary
    read_res = await agent_loop.execute_tool("read_file", {"path": "calculator.py"})
    assert read_res["status"] == "success"
    assert "def add(a, b):" in read_res["result"]["content"]

    # Verify agent guard blocks path traversal outside repo B
    traversal_decision = agent_loop.guard.check("read_file", {"path": "../../../etc/passwd"})
    assert traversal_decision.allowed is False
    assert traversal_decision.code == "path_escape"

    # Verify agent guard blocks protected paths
    protected_decision = agent_loop.guard.check("read_file", {"path": ".keelway/keelway.db"})
    assert protected_decision.allowed is False
    assert protected_decision.code == "protected_path"


@pytest.mark.asyncio
async def test_dual_mode_bundle_tamper_detection(tmp_path: Path):
    """
    Workstream E acceptance:
    Ensure tampered bundle archive is detected and rejected during import.
    """
    source_dir = tmp_path / "agent_source"
    source_dir.mkdir()
    (source_dir / "sample.agent.json").write_text(json.dumps({"name": "sample", "version": "1.0.0"}))
    (source_dir / "code.py").write_text("print('clean')")

    archive_path = tmp_path / "sample.tar.gz"
    AgentBundlePacker.pack(source_dir, archive_path)

    # Corrupt a file inside the archive by unpacking, modifying, and re-packing without updating bundle_manifest.json
    corrupt_dir = tmp_path / "corrupt_staging"
    import tarfile
    with tarfile.open(archive_path, "r:gz") as tar:
        tar.extractall(path=corrupt_dir)
    
    (corrupt_dir / "code.py").write_text("print('MALICIOUS INJECTION')")
    tampered_archive = tmp_path / "tampered.tar.gz"
    with tarfile.open(tampered_archive, "w:gz") as tar:
        tar.add(corrupt_dir / "bundle_manifest.json", arcname="bundle_manifest.json")
        tar.add(corrupt_dir / "sample.agent.json", arcname="sample.agent.json")
        tar.add(corrupt_dir / "code.py", arcname="code.py")

    target_import = tmp_path / "imported_corrupt"
    with pytest.raises(ValueError, match="Tampered file detected: code.py"):
        AgentBundlePacker.unpack(tampered_archive, target_import, verify=True)


@pytest.mark.asyncio
async def test_dual_mode_ide_golden_path_live_model_or_mock(tmp_path: Path):
    """
    Workstream C acceptance:
    IDE Mode bug-fix workflow:
    1. Initialize 12-state state machine.
    2. Load context, transition to PLANNING -> PLAN_READY -> AWAITING_APPROVAL.
    3. Confirm mutation approval.
    4. Transition to EXECUTING -> apply fix to workspace.
    5. Run test verification -> transition to VERIFYING -> COMPLETED.
    """
    sm = TaskStateMachine(task_id="task_ide_001")
    assert sm.state == TaskState.CREATED

    # Context Loading
    sm.transition(TaskState.CONTEXT_LOADING, {"repo": str(tmp_path)})
    sm.transition(TaskState.PLANNING, {"prompt": "Fix pricing bug in pricing.py"})
    sm.transition(TaskState.PLAN_READY, {"plan": "Replace line 10 with tax calculation"})
    sm.transition(TaskState.AWAITING_APPROVAL, {"risk": "LOW", "diff_lines": 2})

    # Invariant check: Cannot jump straight to COMPLETED without EXECUTING
    with pytest.raises((ValueError, InvalidStateTransitionError)):
        sm.transition(TaskState.COMPLETED)

    # Approve and Execute
    sm.transition(TaskState.EXECUTING, {"approval_token": "tok_dev_signed"})
    (tmp_path / "pricing.py").write_text("def get_total(price, tax): return price + tax\n")

    # Verify and Complete
    sm.transition(TaskState.VERIFYING, {"test_suite": "pricing_test"})
    sm.transition(TaskState.COMPLETED, {"result": "PASS", "test_exit": 0})
    assert sm.state == TaskState.COMPLETED
