"""
Tests for Keelway Prompt-to-App Guided Builder (WP09 / Section 12).
Verifies template catalog, architecture plan synthesis, step formulation,
end-to-end project scaffolding, automated pytest verification, and flight tape sealing.
"""
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from core.orchestration.guided_builder import (
    APP_TEMPLATES,
    AppArchitecturePlan,
    AppTaskStep,
    AppVerificationResult,
    AppBuildReceipt,
    GuidedAppBuilder,
)
from core.main import app


def test_list_templates():
    templates = GuidedAppBuilder.list_templates()
    assert len(templates) >= 3
    ids = {t["id"] for t in templates}
    assert "fastapi-service" in ids
    assert "cli-tool" in ids
    assert "agent-microservice" in ids
    for t in templates:
        assert "name" in t
        assert "description" in t
        assert "dependencies" in t
        assert t["file_count"] >= 5


def test_synthesize_plan_intent_detection():
    # FastAPI detection
    plan1 = GuidedAppBuilder.synthesize_plan("Build an inventory REST API with JWT auth")
    assert plan1.template == "fastapi-service"
    assert "src/models.py" in plan1.file_tree
    assert len(plan1.plan_sha256) == 64

    # CLI detection
    plan2 = GuidedAppBuilder.synthesize_plan("Build a terminal CLI utility for batch processing")
    assert plan2.template == "cli-tool"
    assert "src/cli.py" in plan2.file_tree

    # Agent detection
    plan3 = GuidedAppBuilder.synthesize_plan("Scaffold an autonomous agent microservice")
    assert plan3.template == "agent-microservice"
    assert "src/agent_core.py" in plan3.file_tree


def test_synthesize_plan_explicit_slug():
    plan = GuidedAppBuilder.synthesize_plan(
        intent="Custom analytics engine",
        app_name="Super_Analytics-v2!",
        template_id="cli-tool",
    )
    assert plan.app_name == "super_analytics_v2_"
    assert plan.template == "cli-tool"
    assert len(plan.test_plan) >= 3


def test_formulate_steps():
    plan = GuidedAppBuilder.synthesize_plan("Build inventory API")
    steps = GuidedAppBuilder.formulate_steps(plan)
    assert len(steps) == 5
    assert steps[0].step_id == "step-01-scaffold"
    assert steps[-1].step_id == "step-05-verify"


def test_build_and_verify_fastapi(tmp_path):
    target = tmp_path / "fastapi_app"
    receipt = GuidedAppBuilder.build_and_export(
        intent="FastAPI service with item management",
        app_name="fastapi_app",
        template_id="fastapi-service",
        target_dir=target,
        run_verification=True,
        init_git=True,
    )
    assert receipt.tests_passed is True
    assert receipt.verification["tests_count"] == 4
    assert (target / "src" / "main.py").exists()
    assert (target / "tests" / "test_main.py").exists()
    assert (target / "build_receipt.json").exists()
    assert len(receipt.flight_tape_sha256) == 64
    assert Path(receipt.flight_tape_path).exists()


def test_build_and_verify_cli_tool(tmp_path):
    target = tmp_path / "cli_app"
    receipt = GuidedAppBuilder.build_and_export(
        intent="CLI utility for data processing",
        app_name="cli_app",
        template_id="cli-tool",
        target_dir=target,
        run_verification=True,
        init_git=False,
    )
    assert receipt.tests_passed is True
    assert receipt.verification["tests_count"] == 6
    assert (target / "src" / "cli.py").exists()
    assert (target / "tests" / "test_cli.py").exists()


def test_build_and_verify_agent_microservice(tmp_path):
    target = tmp_path / "agent_app"
    receipt = GuidedAppBuilder.build_and_export(
        intent="Autonomous agent service",
        app_name="agent_app",
        template_id="agent-microservice",
        target_dir=target,
        run_verification=True,
        init_git=False,
    )
    assert receipt.tests_passed is True
    assert receipt.verification["tests_count"] == 3
    assert (target / "src" / "agent_core.py").exists()
    assert (target / "tests" / "test_service.py").exists()


def test_api_builder_endpoints(tmp_path):
    client = TestClient(app)

    # 1. List templates
    res_list = client.get("/v1/builder/app/templates")
    assert res_list.status_code == 200
    templates = res_list.json()
    assert any(t["id"] == "fastapi-service" for t in templates)

    # 2. Synthesize plan
    res_plan = client.post(
        "/v1/builder/app/plan",
        json={"intent": "Build an e-commerce order service", "template_id": "fastapi-service"},
    )
    assert res_plan.status_code == 200
    plan_data = res_plan.json()
    assert plan_data["template"] == "fastapi-service"
    assert "src/models.py" in plan_data["file_tree"]
    assert "plan_sha256" in plan_data

    # 3. Generate app
    target = tmp_path / "api_generated_app"
    res_gen = client.post(
        "/v1/builder/app/generate",
        json={
            "intent": "E-commerce order service",
            "app_name": "order_service",
            "template_id": "fastapi-service",
            "target_dir": str(target),
            "run_verification": True,
            "init_git": False,
        },
    )
    assert res_gen.status_code == 200
    gen_data = res_gen.json()
    assert gen_data["tests_passed"] is True
    assert gen_data["verification"]["tests_count"] == 4
    assert len(gen_data["flight_tape_sha256"]) == 64
