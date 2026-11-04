"""
Tests for Keelway AgentSpec and AgentBuilder (Section 12 of Master Directive).
Verifies:
1. AgentSpec typed instantiation, validation, and compilation to AgentManifest.
2. Template listing and retrieval.
3. Artifact generation (manifest, spec, runner, unit tests, README).
4. End-to-end scaffolding, manifest registry recording, and test execution receipt.
5. REST API routes for templates and agent scaffolding.
"""
import json
from pathlib import Path
import pytest
from starlette.testclient import TestClient

from core.main import app
from core.agents.spec import AgentParam, AgentSpec
from core.agents.builder import AgentBuilder, BUILTIN_TEMPLATES
from core.storage.workspace_fs import WorkspaceFilesystem
from core.api import routes


@pytest.fixture
def test_client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    routes.set_workspace_fs(WorkspaceFilesystem(root_dir=str(tmp_path)))
    with TestClient(app) as client:
        yield client


def test_agent_spec_compilation():
    spec = AgentSpec(
        name="custom-linter",
        version="1.2.0",
        author="alice",
        description="Scans code for lint violations.",
        instructions="Read files and return lint issues.",
        tools=["read_file", "list_dir"],
    )
    assert spec.schema_id == "keelway.spec/v1"
    manifest_dict = spec.to_manifest_dict()
    assert manifest_dict["schema"] == "keelway.agent/v1"
    assert manifest_dict["name"] == "custom-linter"
    assert manifest_dict["version"] == "1.2.0"
    assert manifest_dict["owner"] == "alice"

    # Validate compiled manifest
    report = spec.validate_manifest()
    assert report.ok is True, f"Validation errors: {report.errors}"


def test_builder_list_templates():
    templates = AgentBuilder.list_templates()
    assert len(templates) >= 4
    template_ids = [t["id"] for t in templates]
    assert "test-fixer" in template_ids
    assert "code-reviewer" in template_ids
    assert "security-auditor" in template_ids
    assert "feature-scaffolder" in template_ids


def test_builder_create_from_template():
    spec = AgentBuilder.create_from_template(
        "security-auditor",
        name="sec-scanner",
        author="sec-team",
        overrides={"description": "Company security audit scanner."},
    )
    assert spec.name == "sec-scanner"
    assert spec.author == "sec-team"
    assert spec.description == "Company security audit scanner."
    assert "search_codebase" in spec.tools
    assert spec.permissions.network == "none"

    report = spec.validate_manifest()
    assert report.ok is True


@pytest.mark.asyncio
async def test_builder_scaffold_and_test_execution(tmp_path):
    target = tmp_path / "agents" / "my_fixer"
    spec = AgentBuilder.create_from_template("test-fixer", name="my-fixer", author="tester")
    
    receipt = await AgentBuilder.build_and_register(spec, target_dir=target, register_in_db=True)
    assert receipt.spec_name == "my-fixer"
    assert receipt.tests_passed is True
    assert len(receipt.files_created) == 5
    assert (target / "my-fixer.agent.json").exists()
    assert (target / "my-fixer.spec.json").exists()
    assert (target / "run_my_fixer.py").exists()
    assert (target / "test_my_fixer.py").exists()
    assert (target / "README.md").exists()
    assert receipt.receipt_sha256 != ""


def test_api_agent_builder_routes(test_client, tmp_path):
    # 1. GET /v1/agent/builder/templates
    t_res = test_client.get("/v1/agent/builder/templates")
    assert t_res.status_code == 200
    t_data = t_res.json()
    assert "templates" in t_data
    assert len(t_data["templates"]) >= 4

    # 2. POST /v1/agent/builder/scaffold
    scaffold_payload = {
        "template_id": "code-reviewer",
        "name": "auto-reviewer",
        "target_dir": "agents/auto_reviewer",
    }
    s_res = test_client.post("/v1/agent/builder/scaffold", json=scaffold_payload)
    assert s_res.status_code == 200
    s_data = s_res.json()
    assert s_data["status"] == "created"
    assert s_data["receipt"]["tests_passed"] is True
    assert (tmp_path / "agents" / "auto_reviewer" / "auto-reviewer.agent.json").exists()
