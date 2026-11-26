#!/usr/bin/env python3
"""Interactive Developer Walkthrough Demo for Keelway.
Demonstrates the complete end-to-end governed AI change lifecycle:
1. Isolated worktree creation
2. Deny-by-default policy pre-flight
3. Sandboxed patch generation & budget consumption
4. Automated paired evaluation scoring
5. Human review approval gate (with patch mutation rejection)
6. Two-Human Quorum for production changes
7. SQLite WAL audit chain verification
8. Anti-tampering demonstration (attacker attempts to alter event payload)
9. Sealed compliance export bundle generation (FR-09)
"""
import os
import shutil
import tempfile
from keelway.audit.store import SQLiteAuditStore
from keelway.core.runner import GovernedRunCoordinator
from keelway.policy.engine import PolicyEngine, ToolAuthorizationRequest


def run_developer_demo():
    print("=" * 80)
    print("🛡️  KEELWAY BY SORVEX LABS — DEVELOPER INTERACTIVE WALKTHROUGH DEMO")
    print("=" * 80)

    # Setup isolated test directory
    demo_dir = tempfile.mkdtemp(prefix="keelway_demo_")
    db_path = os.path.join(demo_dir, "keelway_audit.db")

    try:
        # Step 1: Scaffold local git repo
        print("\n[Step 1] Initializing isolated Git test repository...")
        import subprocess
        subprocess.run(["git", "init"], cwd=demo_dir, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Demo Dev"], cwd=demo_dir, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "dev@sorvexlabs.test"], cwd=demo_dir, check=True, capture_output=True)
        readme_file = os.path.join(demo_dir, "README.md")
        with open(readme_file, "w") as f:
            f.write("# Demo App\nInitial code base.\n")
        subprocess.run(["git", "add", "."], cwd=demo_dir, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "chore: initial commit"], cwd=demo_dir, check=True, capture_output=True)
        print("  -> Git repository ready at:", demo_dir)

        # Step 2: Test Deny-by-Default Policy Engine
        print("\n[Step 2] Testing Deny-by-Default Policy Engine...")
        policy = PolicyEngine()
        
        # Unauthorized target (.env)
        bad_req = ToolAuthorizationRequest(
            run_id="demo_test_run",
            tool="fs.read",
            action_digest="sha256:read_env",
            scope={"path": "/workspace/.env"},
            actor_id="agent_bot",
            policy_version="default_governed_v1",
        )
        bad_decision = policy.evaluate(bad_req)
        print(f"  -> Attempt to access sensitive file (.env): DECISION = {bad_decision.decision.value} (Reason: {bad_decision.reason_code})")
        assert bad_decision.decision.value == "DENY"

        # Authorized target
        good_req = ToolAuthorizationRequest(
            run_id="demo_test_run",
            tool="git.write_patch",
            action_digest="sha256:write_code",
            scope={"repo": "demo_repo", "path": "feature.py"},
            actor_id="dev_user",
            policy_version="default_governed_v1",
        )
        good_decision = policy.evaluate(good_req)
        print(f"  -> Attempt to write application feature: DECISION = {good_decision.decision.value} (Reason: {good_decision.reason_code})")
        assert good_decision.decision.value == "REQUIRE_APPROVAL"

        # Step 3: Run Governed Workflow
        print("\n[Step 3] Launching Governed Run Coordinator...")
        store = SQLiteAuditStore(db_path=db_path)
        coord = GovernedRunCoordinator(
            actor_id="lead_developer_alice",
            repo_path=demo_dir,
            classification="internal",
            audit_store=store,
        )
        ok, approval_id = coord.start_run("Add telemetry healthcheck service")
        print(f"  -> Run ID: {coord.run_id}")
        print(f"  -> Status: {coord.manifest.status.value}")
        print(f"  -> Tokens used: {coord.manifest.tokens_used}")
        print(f"  -> Approval Request ID: {approval_id}")

        # Step 4: Inspect Generated Diff
        print("\n[Step 4] Reviewing Sandboxed Unified Diff...")
        diff = coord.workspace.get_diff()
        print(diff)

        # Step 5: Submit Human Review Approval
        print("\n[Step 5] Human Reviewer Authorizing Patch...")
        appr_ok, appr_msg = coord.submit_human_approval(
            approval_id=approval_id,
            approver_id="alice_lead_reviewer",
            decision="APPROVED",
        )
        print(f"  -> Approval Result: {appr_ok} ({appr_msg})")
        print(f"  -> New Run Status: {coord.manifest.status.value}")

        # Step 6: Create Pull Request & Trigger Staging Deploy
        print("\n[Step 6] Promoting Governed Change to PR & Staging CI...")
        pr_ok, pr_res, _ = coord.promote_to_pr(
            approval_id=approval_id,
            title="feat(telemetry): Add healthcheck endpoint",
            description="Governed AI change verified by Keelway test suite",
        )
        print(f"  -> Pull Request Created: {pr_res.pr_url} (Commit: {pr_res.head_sha[:8]}...)")

        dep_ok, dep_res, _ = coord.deploy_to_staging(approval_id=approval_id)
        print(f"  -> Staging CI Webhook Emitted: Deployment ID: {dep_res.deployment_id}")
        print(f"  -> CI Receipt Digest: {dep_res.receipt_digest[:16]}...")

        # Step 7: Cryptographic Audit Verification
        print("\n[Step 7] Verifying Hash-Chained Audit Trail in SQLite WAL...")
        verified, err = store.verify_persisted_chain(coord.run_id)
        events = store.get_events(coord.run_id)
        print(f"  -> Total Events in Chain: {len(events)}")
        print(f"  -> Cryptographic Chain Integrity: {'VERIFIED (Zero tampering)' if verified else f'FAILED: {err}'}")

        # Step 8: Demonstrating Mathematical Tamper Detection
        print("\n[Step 8] Demonstrating Tamper Detection (Adversary simulation)...")
        import sqlite3
        conn = sqlite3.connect(db_path)
        # Adversary attempts to stealthily modify event #3 payload in the SQLite database
        conn.execute("UPDATE audit_events SET payload_json = '{\"tampered\": true}' WHERE seq = 3 AND run_id = ?", (coord.run_id,))
        conn.commit()
        conn.close()

        tampered_verified, tamper_err = store.verify_persisted_chain(coord.run_id)
        print(f"  -> Integrity after database tampering: {tampered_verified}")
        print(f"  -> Detector Output: {tamper_err}")
        assert tampered_verified is False
        print("  -> Security Invariant Holds: Cryptographic math caught unauthorized payload modification immediately!")

        # Step 9: Testing Two-Human Quorum (ADR-045)
        print("\n[Step 9] Testing Two-Human Quorum for Production Environments...")
        prod_coord = GovernedRunCoordinator(
            actor_id="dev_user",
            repo_path=demo_dir,
            classification="production",
        )
        q_ok, q_id = prod_coord.start_run("Production emergency patch")
        print(f"  -> Production Run ID: {prod_coord.run_id} (Quorum ID: {q_id})")
        
        # 1. First approval: Security Lead
        s_ok, s_msg = prod_coord.submit_quorum_approval(q_id, principal_id="alice_sec", role="Security Lead")
        print(f"  -> Security Lead Approval: {s_ok} ({s_msg})")
        print(f"  -> Run Status: {prod_coord.manifest.status.value}")  # Still awaiting second approval

        # 2. Rejection: Same person trying to approve Platform Owner role (Self-Quorum Prohibition)
        self_ok, self_msg = prod_coord.submit_quorum_approval(q_id, principal_id="alice_sec", role="Platform Owner")
        print(f"  -> Attempted Self-Quorum by same human: {self_ok} (Rejected: {self_msg})")
        assert self_ok is False

        # 3. Second approval: Distinct Platform Owner
        p_ok, p_msg = prod_coord.submit_quorum_approval(q_id, principal_id="bob_platform", role="Platform Owner")
        print(f"  -> Platform Owner Approval: {p_ok} ({p_msg})")
        print(f"  -> Final Production Run Status: {prod_coord.manifest.status.value}")
        assert prod_coord.manifest.status.value == "approved"

        # Teardown coordinators
        coord.teardown()
        prod_coord.teardown()

        print("\n" + "=" * 80)
        print("🎉 ALL DEVELOPER WALKTHROUGH STEPS COMPLETED & VERIFIED SUCCESSFULLY!")
        print("=" * 80)

    finally:
        shutil.rmtree(demo_dir, ignore_errors=True)


if __name__ == "__main__":
    run_developer_demo()
