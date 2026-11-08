"""
Unit tests for Keelway System Diagnostics & Pre-Flight Doctor (core/system/doctor.py).
"""
import pytest
from httpx import AsyncClient, ASGITransport
from core.main import app
from core.system.doctor import SystemDoctor, SystemDoctorReport
from cli import cmd_doctor


@pytest.mark.asyncio
async def test_system_doctor_run_diagnostics():
    report = await SystemDoctor.run_diagnostics()
    assert isinstance(report, SystemDoctorReport)
    assert report.overall_status in ("HEALTHY", "DEGRADED")
    assert len(report.sections) == 10
    section_names = [s.name for s in report.sections]
    assert "Database Engine" in section_names
    assert "Workspace & Git Context" in section_names
    assert "Model Providers & Gateway" in section_names
    assert "Air-Gap Compliance (NIST SP 800-53 SC-7)" in section_names
    assert "Enterprise Entitlements" in section_names
    assert "Software Bill of Materials (SBOM)" in section_names
    assert "Tier 2 Hardware Security HAL" in section_names
    assert "KStack Skills Catalog" in section_names
    assert "Agent Builder Templates" in section_names
    assert "Sandbox Backend Status" in section_names

    # Verify KStack Skills Catalog section
    kstack_sec = next(s for s in report.sections if s.name == "KStack Skills Catalog")
    assert kstack_sec.status == "OK"
    assert kstack_sec.details["skills_verified"] == 8
    assert kstack_sec.details["total_required"] == 8
    assert kstack_sec.details["manifest_integrity"] == "VERIFIED"
    expected_skills = [
        "plan",
        "investigate",
        "review",
        "qa",
        "security",
        "ship",
        "modernize",
        "repomap-sync",
    ]
    for skill_name in expected_skills:
        assert skill_name in kstack_sec.details["skills"]
        assert "VALID" in kstack_sec.details["skills"][skill_name]

    # Verify Agent Builder Templates section
    tpl_sec = next(s for s in report.sections if s.name == "Agent Builder Templates")
    assert tpl_sec.status == "OK"
    assert tpl_sec.details["templates_verified"] == 6
    assert tpl_sec.details["total_required"] == 6
    expected_templates = [
        "test-fixer",
        "code-reviewer",
        "security-auditor",
        "feature-scaffolder",
        "doc-writer",
        "dependency-modernizer",
    ]
    for tpl_name in expected_templates:
        assert tpl_name in tpl_sec.details["templates"]
        assert "VERIFIED" in tpl_sec.details["templates"][tpl_name]

    # Verify Sandbox Backend Status section
    sbx_sec = next(s for s in report.sections if s.name == "Sandbox Backend Status")
    assert sbx_sec.status in ("OK", "WARN")
    assert sbx_sec.details["active_backend"] in ("seatbelt", "bubblewrap", "none")
    assert "confinement_verified" in sbx_sec.details
    assert "isolation_mode" in sbx_sec.details

    data = report.to_dict()
    assert "timestamp_utc" in data
    assert "overall_status" in data
    assert "sections" in data
    assert len(data["sections"]) == 10


@pytest.mark.asyncio
async def test_system_doctor_api_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/v1/system/doctor")
        assert resp.status_code == 200
        data = resp.json()
        assert data["overall_status"] in ("HEALTHY", "DEGRADED")
        assert len(data["sections"]) == 10
        assert data["sections"][6]["name"] == "Tier 2 Hardware Security HAL"
        assert data["sections"][7]["name"] == "KStack Skills Catalog"
        assert data["sections"][8]["name"] == "Agent Builder Templates"
        assert data["sections"][9]["name"] == "Sandbox Backend Status"


@pytest.mark.asyncio
async def test_system_doctor_cli_execution(capsys):
    rc = await cmd_doctor(json_output=False)
    assert rc == 0
    captured = capsys.readouterr()
    assert "Sovereign System Diagnostics" in captured.out
    assert "Tier 2 Hardware Security HAL" in captured.out
    assert "KStack Skills Catalog" in captured.out
    assert "Agent Builder Templates" in captured.out
    assert "Sandbox Backend Status" in captured.out
    assert "10/10 Dimensions Evaluated" in captured.out

    rc_json = await cmd_doctor(json_output=True)
    assert rc_json == 0
    captured_json = capsys.readouterr()
    assert '"overall_status":' in captured_json.out
    assert '"Software Bill of Materials (SBOM)"' in captured_json.out
    assert '"KStack Skills Catalog"' in captured_json.out
    assert '"Agent Builder Templates"' in captured_json.out
    assert '"Sandbox Backend Status"' in captured_json.out
