"""
Comprehensive Unit & Integration Test Suite for KStack, KBrain, KHub, KSpaces, and KFlow.
Verifies all 5 priority extension components under Conductor.
"""

import json
import tempfile
import time
from pathlib import Path
import pytest
from httpx import ASGITransport, AsyncClient

from core.main import app
from core.kstack import kstack_registry, parse_skill_markdown, KStackRegistry
from core.kbrain import (
    kbrain_store,
    KBrainStore,
    KnowledgeScope,
    FactStatus,
    SecretLeakDetectedError,
)
from core.khub import khub_importer, KHubImporter, SkillSourceType
from core.kspaces import (
    kspaces_manager,
    KSpacesManager,
    SpaceRole,
    TaskStatus,
)
from core.kflow import (
    kflow_engine,
    KFlowEngine,
    FlowNode,
    FlowStatus,
    BaseShaDriftError,
)


# =====================================================================
# 1. KStack Tests
# =====================================================================

def test_kstack_builtin_skills_loaded():
    skills = kstack_registry.list_skills()
    names = [s.name for s in skills]
    assert "kstack/plan" in names
    assert "kstack/review" in names
    assert "kstack/qa" in names
    assert "kstack/security" in names
    assert "kstack/investigate" in names
    assert "kstack/ship" in names
    assert "kstack/modernize" in names
    assert "kstack/repomap-sync" in names

    plan = kstack_registry.get_skill("kstack/plan")
    assert plan is not None
    assert plan.role == "architect"
    assert "draft" in plan.permissions
    assert len(plan.digest_sha256) == 64

    ship = kstack_registry.get_skill("kstack/ship")
    assert ship is not None
    assert ship.role == "release_lead"
    assert "execute_restricted" in ship.permissions

    inv = kstack_registry.get_skill("kstack/investigate")
    assert inv is not None
    assert inv.role == "debugger"

    mod = kstack_registry.get_skill("kstack/modernize")
    assert mod is not None
    assert mod.role == "engineer"

    sync = kstack_registry.get_skill("kstack/repomap-sync")
    assert sync is not None
    assert sync.role == "general"

    # Keelway-mission skills: agentic capability surface, not generic dev workflow clones
    for name, role in (
        ("kstack/p10-gate", "gatekeeper"),
        ("kstack/airgap-verify", "compliance_auditor"),
        ("kstack/flight-tape-verify", "auditor"),
        ("kstack/worktree-isolate", "operator"),
        ("kstack/approval-grant", "policy_admin"),
        ("kstack/kflow-orchestrate", "orchestrator"),
    ):
        sk = kstack_registry.get_skill(name)
        assert sk is not None, name
        assert sk.role == role
        assert len(sk.digest_sha256) == 64
        assert len(sk.instructions) > 100


def test_kstack_versioned_manifest_integrity():
    """Verify built-in skills match their registered cryptographic digests in manifest.json."""
    ok, errors = kstack_registry.verify_manifest()
    assert ok is True, f"Manifest verification failed: {errors}"
    assert len(errors) == 0


def test_kstack_import_validate_export_and_revocation():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        skill_file = tmp_path / "custom_skill.md"
        content = """---
name: custom/tester
version: 1.0.0
role: engineer
description: Custom test runner
permissions:
  - execute_restricted
inputs:
  suite: Test suite name
outputs:
  passed: Boolean result
---

# Custom Tester Instructions
Execute the tests carefully.
"""
        skill_file.write_text(content, encoding="utf-8")

        # Validate
        is_valid, errors = kstack_registry.validate_skill(content)
        assert is_valid is True
        assert len(errors) == 0

        # Import
        imported = kstack_registry.import_skill(skill_file, pin=True)
        assert imported.name == "custom/tester"
        assert imported.pinned is True

        # Inspect
        info = kstack_registry.inspect_skill("custom/tester")
        assert info["name"] == "custom/tester"

        # Execute & Proof
        proof = kstack_registry.execute_skill(
            name="custom/tester",
            actor="test_runner",
            inputs={"suite": "integration"},
            handler=lambda inp: {"passed": True, "suite": inp["suite"]},
        )
        assert proof.success is True
        assert len(proof.signature_sha256) == 64

        # Export
        out_file = tmp_path / "exported.md"
        kstack_registry.export_skill("custom/tester", out_file)
        assert out_file.exists()
        assert "custom/tester" in out_file.read_text(encoding="utf-8")

        # Revoke
        revoked = kstack_registry.revoke_skill("custom/tester", reason="Decommissioned")
        assert revoked is True
        with pytest.raises(PermissionError):
            kstack_registry.execute_skill("custom/tester", actor="test", inputs={})


# =====================================================================
# 2. KBrain Tests
# =====================================================================

def test_kbrain_secret_leak_prevention():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = KBrainStore(persistence_path=Path(tmpdir) / "facts.json")

        # Must reject OpenAI API key
        with pytest.raises(SecretLeakDetectedError):
            store.record_fact("openai_key", "sk-1234567890abcdef1234567890abcdef")

        # Must reject GitHub token
        with pytest.raises(SecretLeakDetectedError):
            store.record_fact("gh_token", "ghp_1234567890abcdef1234567890abcdef")

        # Must reject Bearer token
        with pytest.raises(SecretLeakDetectedError):
            store.record_fact("auth_hdr", "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xyz")


def test_kbrain_acl_revisions_conflicts_and_withdrawal():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = KBrainStore(persistence_path=Path(tmpdir) / "facts.json")

        # 1. Record local session fact
        f_local = store.record_fact(
            key="temp_debug",
            statement="Debug flag is enabled",
            scope=KnowledgeScope.LOCAL_SESSION,
            auto_approve=True,
        )

        # 2. Record project fact
        f_proj = store.record_fact(
            key="db_port",
            statement="Database runs on 5432",
            scope=KnowledgeScope.PROJECT,
            auto_approve=True,
        )

        # 3. Record team fact
        f_team = store.record_fact(
            key="deploy_policy",
            statement="Deploy requires 2 signers",
            scope=KnowledgeScope.TEAM,
            auto_approve=True,
        )

        # ACL Filtering: query with max_scope=LOCAL_SESSION should only see local
        local_view = store.query_facts(max_scope=KnowledgeScope.LOCAL_SESSION)
        assert len(local_view) == 1
        assert local_view[0].key == "temp_debug"

        # Query with max_scope=PROJECT should see LOCAL_SESSION and PROJECT (not TEAM)
        proj_view = store.query_facts(max_scope=KnowledgeScope.PROJECT)
        keys_proj = [f.key for f in proj_view]
        assert "temp_debug" in keys_proj
        assert "db_port" in keys_proj
        assert "deploy_policy" not in keys_proj

        # 4. Correction (creates revision 2)
        f_corrected = store.correct_fact(
            fact_id=f_proj.id,
            new_statement="Database runs on port 5433",
            reason="Port conflict with host postgres",
            user="alice",
        )
        assert f_corrected.revision == 2
        assert f_corrected.statement == "Database runs on port 5433"

        # Old fact should be marked CORRECTED
        old_fact = store._facts[f_proj.id]
        assert old_fact.status == FactStatus.CORRECTED
        assert old_fact.superseded_by == f_corrected.id

        # 5. Withdrawal
        store.withdraw_fact(f_local.id, reason="Session ended", user="alice")
        after_withdrawn = store.query_facts(max_scope=KnowledgeScope.LOCAL_SESSION)
        assert len(after_withdrawn) == 0

        # 6. Scope Promotion
        promoted = store.promote_scope(f_corrected.id, target_scope=KnowledgeScope.TEAM, user="alice")
        assert promoted.scope == KnowledgeScope.TEAM


# =====================================================================
# 3. KHub Tests
# =====================================================================

def test_khub_rule_only_separation_and_drift_tracking():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / ".cursor/skills").mkdir(parents=True)
        (root / ".cursor/rules").mkdir(parents=True)
        (root / ".claude/skills").mkdir(parents=True)

        # Create an executable skill
        skill_file = root / ".cursor/skills/code_formatter.md"
        skill_file.write_text("# Formatter\nRun code formatting on git diff.", encoding="utf-8")

        # Create a rule-only file
        rule_file = root / ".cursor/rules/style_guide.md"
        rule_file.write_text("# Style Guide\nAlways use 4 spaces for indentation.", encoding="utf-8")

        importer = KHubImporter(pinned_dir=root / "pinned")
        scanned = importer.scan_directory(root)
        assert len(scanned) == 2

        skill_item = next(s for s in scanned if s.source_type == SkillSourceType.CURSOR_SKILL)
        rule_item = next(s for s in scanned if s.source_type == SkillSourceType.CURSOR_RULE)

        assert skill_item.is_rule_only is False
        assert rule_item.is_rule_only is True

        # Rule-only cannot be approved as an executable skill
        with pytest.raises(ValueError, match="Cannot execute a rule-only"):
            importer.approve_imported_skill(rule_item.id)

        # Executable skill can be approved
        assert importer.approve_imported_skill(skill_item.id) is True
        assert skill_item.approved_by_user is True

        # Drift tracking: modify upstream file
        time.sleep(0.01)
        skill_file.write_text("# Formatter v2\nUpdated instructions.", encoding="utf-8")
        has_drift, original_hash, current_hash = importer.check_upstream_drift(skill_item.id)
        assert has_drift is True
        assert original_hash != current_hash


# =====================================================================
# 4. KSpaces Tests
# =====================================================================

def test_kspaces_roles_agent_identities_and_merge_gate():
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = KSpacesManager(persistence_path=Path(tmpdir) / "spaces.json")
        space = manager.create_space("space_checkout", "Checkout Service", owner_id="alice")

        # Add member with CONTRIBUTOR role
        manager.add_member("space_checkout", user_id="bob", role=SpaceRole.CONTRIBUTOR, caller_id="alice")
        # Add member with AGENT_MANAGER role
        manager.add_member("space_checkout", user_id="charlie", role=SpaceRole.AGENT_MANAGER, caller_id="alice")

        # Register agent service identity
        agent = manager.register_agent_identity(
            space_id="space_checkout",
            name="checkout_coder",
            owner_user_id="alice",
            role_description="Automated feature implementation agent",
            allowed_tools=["read_file", "edit_file"],
            ttl_seconds=3600,
        )
        assert agent.is_valid() is True
        assert agent.owner_user_id == "alice"

        # Create task
        task = manager.create_task(
            space_id="space_checkout",
            title="Implement coupon code validation",
            branch_name="feature/coupons",
            base_commit_sha="a1b2c3d4",
            caller_id="bob",
            assigned_to=agent.agent_id,
        )
        assert task.assigned_to == agent.agent_id

        # Add source line review comment
        comment = manager.add_review_comment(
            space_id="space_checkout",
            task_id=task.task_id,
            author_id="alice",
            file_path="src/coupons.py",
            line_number=24,
            body="Check for expired coupon timestamps before applying discount.",
        )
        assert comment.line_number == 24
        assert len(task.comments) == 1

        # Contributor (bob) CANNOT approve merge
        with pytest.raises(PermissionError, match="Only Space Owner or Agent Manager"):
            manager.approve_merge("space_checkout", task.task_id, manager_id="bob")

        # Agent Manager (charlie) CAN approve merge
        merged = manager.approve_merge("space_checkout", task.task_id, manager_id="charlie")
        assert merged is True
        assert task.status == TaskStatus.MERGED
        assert task.approved_for_merge_by == "charlie"

        # Cross-tenant denial: stranger cannot access space
        with pytest.raises(PermissionError):
            manager.get_space("space_checkout", caller_id="stranger_eve")


# =====================================================================
# 5. KFlow Tests
# =====================================================================

def test_kflow_dag_execution_base_sha_and_proof_packet():
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = KFlowEngine(storage_dir=Path(tmpdir) / "flows")

        nodes = [
            FlowNode(
                node_id="plan_step",
                name="Synthesize Plan",
                assigned_role="architect",
                tool="kstack/plan",
                inputs={"goal": "Fix discount logic"},
                exact_base_sha="commit_sha_12345",
            ),
            FlowNode(
                node_id="edit_step",
                name="Apply Mutation",
                assigned_role="coder",
                tool="edit_file",
                inputs={"path": "pricing.py"},
                dependencies=["plan_step"],
                exact_base_sha="commit_sha_12345",
            ),
            FlowNode(
                node_id="test_step",
                name="Run Test Suite",
                assigned_role="qa_lead",
                tool="run_tests",
                inputs={"cmd": "pytest tests/"},
                dependencies=["edit_step"],
                exact_base_sha="commit_sha_12345",
            ),
        ]

        dag = engine.create_dag("flow_checkout_fix", goal="Fix discount logic", nodes=nodes, max_fanout=2)
        assert dag.status == FlowStatus.PENDING

        # Acquire worktree lease
        lease_id = engine.acquire_worktree_lease("flow_checkout_fix", "worktree/branch_agent_1")
        assert len(lease_id) > 0

        # Collision test: competing flow cannot lock the same branch
        with pytest.raises(PermissionError, match="locked by active lease"):
            engine.acquire_worktree_lease("competing_flow", "worktree/branch_agent_1")

        # Drift test: executing with mismatched base SHA raises BaseShaDriftError
        with pytest.raises(BaseShaDriftError):
            engine.execute_dag("flow_checkout_fix", current_git_head_sha="commit_sha_DRIFTED_67890")

        # Reset node states for valid run
        for n in dag.nodes.values():
            n.status = FlowStatus.PENDING

        # Valid execution with correct approved base commit
        proof = engine.execute_dag("flow_checkout_fix", current_git_head_sha="commit_sha_12345")
        assert proof.all_tests_passed is True
        assert proof.nodes_executed == 3
        assert len(proof.proof_sha256) == 64
        assert dag.status == FlowStatus.COMPLETED

        # Release lease
        released = engine.release_worktree_lease("worktree/branch_agent_1")
        assert released is True


# =====================================================================
# 6. REST API Endpoints Verification
# =====================================================================

@pytest.mark.asyncio
async def test_kstack_kbrain_khub_kspaces_api_routes():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # GET /v1/kstack/skills
        r_skills = await client.get("/v1/kstack/skills")
        assert r_skills.status_code == 200
        skills_data = r_skills.json()
        assert len(skills_data) >= 4
        assert any(s["name"] == "kstack/plan" for s in skills_data)

        # GET /v1/kstack/skill/kstack/plan
        r_insp = await client.get("/v1/kstack/skill/kstack/plan")
        assert r_insp.status_code == 200
        assert r_insp.json()["role"] == "architect"

        # POST /v1/kbrain/fact
        r_fact = await client.post(
            "/v1/kbrain/fact",
            json={
                "key": "api_contract_v1",
                "statement": "All API endpoints require Authorization Bearer or studio link token",
                "scope": "project",
                "provenance_reason": "API Specification WP04",
            },
        )
        assert r_fact.status_code == 200
        fact_res = r_fact.json()
        assert fact_res["key"] == "api_contract_v1"

        # GET /v1/kbrain/facts
        r_facts = await client.get("/v1/kbrain/facts?scope=project&key=api_contract_v1")
        assert r_facts.status_code == 200
        assert len(r_facts.json()) >= 1

        # GET /v1/khub/skills
        r_hub = await client.get("/v1/khub/skills")
        assert r_hub.status_code == 200

        # POST /v1/kspaces
        unique_space_id = f"api_test_space_{int(time.time() * 1000)}"
        r_space = await client.post(
            "/v1/kspaces",
            json={"space_id": unique_space_id, "name": "API Test Space"},
        )
        assert r_space.status_code == 200
        assert r_space.json()["space_id"] == unique_space_id
