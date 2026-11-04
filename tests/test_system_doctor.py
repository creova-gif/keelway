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
    assert len(report.sections) == 7
    section_names = [s.name for s in report.sections]
    assert "Database Engine" in section_names
    assert "Workspace & Git Context" in section_names
    assert "Model Providers & Gateway" in section_names
    assert "Air-Gap Compliance (NIST SP 800-53 SC-7)" in section_names
    assert "Enterprise Entitlements" in section_names
    assert "Software Bill of Materials (SBOM)" in section_names
    assert "Tier 2 Hardware Security HAL" in section_names

    data = report.to_dict()
    assert "timestamp_utc" in data
    assert "overall_status" in data
    assert "sections" in data
    assert len(data["sections"]) == 7


@pytest.mark.asyncio
async def test_system_doctor_api_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/v1/system/doctor")
        assert resp.status_code == 200
        data = resp.json()
        assert data["overall_status"] in ("HEALTHY", "DEGRADED")
        assert len(data["sections"]) == 7
        assert data["sections"][6]["name"] == "Tier 2 Hardware Security HAL"


@pytest.mark.asyncio
async def test_system_doctor_cli_execution(capsys):
    rc = await cmd_doctor(json_output=False)
    assert rc == 0
    captured = capsys.readouterr()
    assert "Sovereign System Diagnostics" in captured.out
    assert "Tier 2 Hardware Security HAL" in captured.out

    rc_json = await cmd_doctor(json_output=True)
    assert rc_json == 0
    captured_json = capsys.readouterr()
    assert '"overall_status":' in captured_json.out
    assert '"Software Bill of Materials (SBOM)"' in captured_json.out
