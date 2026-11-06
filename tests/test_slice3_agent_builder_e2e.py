"""Slice 3: End-to-End Agent Builder Usability, Distribution & Cross-Repository Execution.

Exercises the complete closed-loop user journey in Agent Builder Mode:
1. Scaffold a reusable custom agent via Studio API (/v1/agent/builder/scaffold)
   from built-in template ('test-fixer').
2. Run initial test fixture evaluation and verify build receipt (tests_passed=True, receipt_sha256).
3. Validate Builder Proof Strip renders all 6 verification stages as passed.
4. Pack agent into tamper-evident distributable bundle archive (.tar.gz) with member digests.
5. In an independent second repository (repo_b), unpack and cryptographically verify bundle.
6. Enforce capability containment: verify that imported agent cannot escalate permissions
   or escape repo_b sandbox.
7. Execute imported agent in repo_b on an authorized tool task.
8. Confirm flight tape and evidence verification in second repository.
"""

import json
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from core.main import app
from core.api import routes
from core.storage.workspace_fs import WorkspaceFilesystem
from core.agents import manifest as am
from core.agents.guard import loop_from_manifest
from core.security.approval_rules import ApprovalRuleStore
from tests.test_proof_strip_ux import run_node_eval
from tests.package_a_profile import skip_unless_live_os_isolation


@pytest.mark.live_os_isolation
@pytest.mark.asyncio
async def test_slice3_agent_builder_scaffold_pack_import_cross_repo(tmp_path: Path, monkeypatch):
    skip_unless_live_os_isolation()
    # Setup repository A (authoring repository)
    repo_a = tmp_path / "repo_a"
    repo_a.mkdir()
    monkeypatch.chdir(repo_a)
    ws_fs_a = WorkspaceFilesystem(root_dir=str(repo_a))
    monkeypatch.setattr(routes, "_workspace_fs", ws_fs_a)

    with TestClient(app) as client:
        # 1. List templates
        tmpl_resp = client.get("/v1/agent/builder/templates")
        assert tmpl_resp.status_code == 200
        templates = tmpl_resp.json()["templates"]
        assert any(t["id"] == "test-fixer" for t in templates)

        # 2. Scaffold custom agent
        agent_name = "reusable-test-fixer"
        scaffold_resp = client.post(
            "/v1/agent/builder/scaffold",
            json={
                "template_id": "test-fixer",
                "name": agent_name,
                "target_dir": f"agents/{agent_name}"
            }
        )
        assert scaffold_resp.status_code == 200, scaffold_resp.text
        scaffold_data = scaffold_resp.json()
        assert scaffold_data["status"] == "created"
        receipt = scaffold_data["receipt"]
        assert receipt["tests_passed"] is True
        assert receipt["receipt_sha256"] != ""
        assert len(receipt["files_created"]) > 0

        # 3. Verify Builder Proof Strip stages
        builder_state = {
            "status": "created",
            "receipt": receipt,
            "manifest": scaffold_data["manifest"],
            "target_dir": scaffold_data["target_dir"],
            "template_id": "test-fixer"
        }
        res = run_node_eval("""
            const s = getBuilderStageData(inputData);
            return {
                statuses: s.map(x => x.status),
                inspectModel: s[0].details.model,
                planSpec: s[1].details.specName,
                authAutonomy: s[2].details.autonomy,
                execTarget: s[3].details.targetDir,
                verifyExitCode: s[4].details.exitCode,
                sealDistributable: s[5].details.distributable
            };
        """, input_data=builder_state)
        assert res["statuses"] == ["passed", "passed", "passed", "passed", "passed", "passed"]
        assert "Local Open-Weight" in res["inspectModel"]
        assert res["verifyExitCode"] == 0
        assert "Ready for Bundle Packaging" in res["sealDistributable"]

        # 4. Pack agent bundle into .tar.gz archive
        archive_path = repo_a / "dist" / f"{agent_name}.tar.gz"
        pack_resp = client.post(
            "/v1/agent/builder/pack",
            json={
                "source_dir": f"agents/{agent_name}",
                "output_archive": str(archive_path)
            }
        )
        assert pack_resp.status_code == 200, pack_resp.text
        pack_data = pack_resp.json()
        assert Path(pack_data["archive_path"]).exists()
        bundle_digest = pack_data["manifest"]["bundle_digest_sha256"]
        assert bundle_digest != ""

        # 5. Setup repository B (independent second repository)
        repo_b = tmp_path / "repo_b"
        repo_b.mkdir()
        (repo_b / "service.py").write_text("def ping(): return 'pong'\n")

        # Point workspace filesystem to repository B
        ws_fs_b = WorkspaceFilesystem(root_dir=str(repo_b))
        monkeypatch.setattr(routes, "_workspace_fs", ws_fs_b)
        monkeypatch.chdir(repo_b)

        # 6. Unpack and cryptographically verify bundle into repository B
        unpack_resp = client.post(
            "/v1/agent/builder/unpack",
            json={
                "archive_path": str(archive_path),
                "destination_dir": f"imported_agents/{agent_name}"
            }
        )
        assert unpack_resp.status_code == 200, unpack_resp.text
        unpack_data = unpack_resp.json()
        assert unpack_data["status"] == "unpacked"
        assert unpack_data["manifest"]["bundle_digest_sha256"] == bundle_digest

        # Verify unpacked files exist on disk in repo B
        dest_dir = repo_b / f"imported_agents/{agent_name}"
        manifest_file = dest_dir / f"{agent_name}.agent.json"
        if not manifest_file.exists():
            manifest_file = dest_dir / "sample.agent.json"
        if not manifest_file.exists():
            manifest_file = dest_dir / "manifest.json"
        assert manifest_file.exists()

        # 7. Security invariant check: anti-escalation & path traversal rejection
        manifest_dict = json.loads(manifest_file.read_text())
        manifest_obj = am.validate(manifest_dict).manifest

        agent_loop = loop_from_manifest(
            manifest=manifest_obj,
            task_id="repo_b_run_001",
            workspace_fs=ws_fs_b,
            record_flight=True,
            approval_rules=ApprovalRuleStore(ws_fs_b.root)
        )

        # Invariant A: Path traversal outside repo B is blocked
        decision_escape = agent_loop.guard.check("read_file", {"path": "../../etc/shadow"})
        assert decision_escape.allowed is False
        assert decision_escape.code == "path_escape"

        # Invariant B: Undeclared privileged tool execution is blocked
        decision_undeclared = agent_loop.guard.check("admin_drop_database", {"db": "prod"})
        assert decision_undeclared.allowed is False

        # Invariant C: Protected system files are blocked
        decision_protected = agent_loop.guard.check("read_file", {"path": ".keelway/keelway.db"})
        assert decision_protected.allowed is False
        assert decision_protected.code == "protected_path"

        # 8. Authorized execution in repo B
        res_exec = await agent_loop.execute_tool("read_file", {"path": "service.py"})
        assert res_exec["status"] == "success"
        assert "def ping():" in res_exec["result"]["content"]

        # 9. Verify flight tape generation in repository B
        assert agent_loop.flight_recorder is not None
        agent_loop.flight_recorder.seal_tape()
        tape_path = repo_b / ".keelway/recordings/repo_b_run_001.flight.json"
        assert tape_path.exists()
        tape = json.loads(tape_path.read_text())
        assert any("read_file" in str(e) for e in tape["events"])
