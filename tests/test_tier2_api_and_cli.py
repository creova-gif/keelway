"""Tests for Tier 2 Hardware Security Verification API and CLI commands.
Verifies GET /v1/tier2/status, POST /v1/tier2/verify (Dual-WORM, TPM, PIV, Recovery),
GET /v1/audit/export, and CLI tier2 subcommands.
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from core.main import app
from core.storage.database import init_db
from cli import cmd_tier2


@pytest_asyncio.fixture(autouse=True)
async def setup_database():
    await init_db()


@pytest.mark.asyncio
async def test_tier2_status_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/v1/tier2/status")
        assert res.status_code == 200
        data = res.json()
        assert data["tier"] == 2
        assert data["security_level"] == "hardware_attested"
        verifiers = data["verifiers"]
        assert "dual_worm" in verifiers
        assert "tpm" in verifiers
        assert "piv" in verifiers
        assert "recovery" in verifiers
        assert verifiers["dual_worm"]["status"] == "active"
        assert verifiers["tpm"]["pcr_replay_supported"] is True
        assert verifiers["piv"]["crl_max_staleness_hours"] == 72
        assert verifiers["recovery"]["quorum"] == "2-of-3"


@pytest.mark.asyncio
async def test_audit_export_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/v1/audit/export")
        assert res.status_code == 200
        assert "application/x-ndjson" in res.headers["content-type"]
        text = res.text
        assert "keelway.record/v1" in text

        # Test download flag
        res_dl = await client.get("/v1/audit/export?download=true")
        assert res_dl.status_code == 200
        assert "attachment" in res_dl.headers.get("content-disposition", "")


@pytest.mark.asyncio
async def test_cli_tier2_commands():
    # Test status
    rc_status = await cmd_tier2("status")
    assert rc_status == 0

    # Test verify all
    rc_verify_all = await cmd_tier2("verify", "all")
    assert rc_verify_all == 0

    # Test verify individual subsystems
    assert await cmd_tier2("verify", "worm") == 0
    assert await cmd_tier2("verify", "tpm") == 0
    assert await cmd_tier2("verify", "piv") == 0
    assert await cmd_tier2("verify", "recovery") == 0

    # Test demo
    rc_demo = await cmd_tier2("demo")
    assert rc_demo == 0
