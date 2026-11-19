"""KStack builtin handler registry and /v1/kstack/execute endpoint tests.

Async API tests use asyncio.run in sync wrappers so they execute even when
pytest-asyncio is absent from the environment.
"""

import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from core.main import app
from core.kstack import kstack_registry
from core.kstack.handlers import BUILTIN_HANDLERS


def test_builtin_handlers_registered_for_real_skills():
    for name in BUILTIN_HANDLERS:
        skill = kstack_registry.get_skill(name)
        assert skill is not None, f"handler registered for missing skill {name}"
        assert not skill.revoked


def test_marketplace_advertised_skills_have_contracts():
    for name in ("kstack/wcag-aa", "kstack/finops-forecast"):
        skill = kstack_registry.get_skill(name)
        assert skill is not None, f"marketplace skill {name} has no KStack contract"
        assert len(skill.digest_sha256) == 64
        assert skill.instructions.strip()


def test_manifest_covers_all_builtin_skills():
    ok, errors = kstack_registry.verify_manifest()
    assert ok, errors


def test_handler_input_validation_fails_closed():
    with pytest.raises(ValueError):
        BUILTIN_HANDLERS["kstack/flight-tape-verify"]({})
    with pytest.raises(ValueError):
        BUILTIN_HANDLERS["kstack/mesh-verify"]({"action": "delegate"})
    with pytest.raises(ValueError):
        BUILTIN_HANDLERS["kstack/schedule-ops"]({"action": "create", "flow_id": "x"})


def test_schedule_ops_list_returns_real_state():
    out = BUILTIN_HANDLERS["kstack/schedule-ops"]({"action": "list"})
    assert "schedules" in out and isinstance(out["schedules"], list)


def test_cost_ledger_handler_reports_ledger_fields():
    out = BUILTIN_HANDLERS["kstack/cost-ledger"]({})
    assert out["currency"] == "USD"
    assert "entries_recorded" in out
    assert "total_cost_usd" in out


def test_execute_endpoint_returns_sealed_proof():
    async def _run():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.post(
                "/v1/kstack/execute",
                json={"name": "kstack/sbom-audit", "inputs": {}},
            )
            assert r.status_code == 200
            proof = r.json()["proof"]
            assert proof["skill_name"] == "kstack/sbom-audit"
            assert proof["skill_digest_sha256"] == kstack_registry.get_skill("kstack/sbom-audit").digest_sha256
            assert len(proof["signature_sha256"]) == 64
            assert proof["success"] is True
            assert "component_count" in proof["outputs"]

    asyncio.run(_run())


def test_execute_endpoint_rejects_unknown_skill():
    async def _run():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.post(
                "/v1/kstack/execute",
                json={"name": "kstack/does-not-exist", "inputs": {}},
            )
            assert r.status_code == 404

    asyncio.run(_run())


def test_execute_endpoint_501_without_handler():
    async def _run():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.post(
                "/v1/kstack/execute",
                json={"name": "kstack/plan", "inputs": {}},
            )
            assert r.status_code == 501
            assert "no registered execution handler" in r.json()["detail"].lower()

    asyncio.run(_run())


def test_execute_endpoint_rejects_revoked_skill():
    async def _run():
        skill = kstack_registry.get_skill("kstack/schedule-ops")
        kstack_registry.revoke_skill("kstack/schedule-ops", "test revocation")
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                r = await client.post(
                    "/v1/kstack/execute",
                    json={"name": "kstack/schedule-ops", "inputs": {}},
                )
                assert r.status_code == 403
        finally:
            skill.revoked = False
            skill.revocation_reason = ""

    asyncio.run(_run())


def test_execute_endpoint_records_handler_failure_in_proof():
    async def _run():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.post(
                "/v1/kstack/execute",
                json={"name": "kstack/flight-tape-verify", "inputs": {}},
            )
            assert r.status_code == 200
            proof = r.json()["proof"]
            assert proof["success"] is False
            assert "error" in proof["outputs"]
            assert len(proof["signature_sha256"]) == 64

    asyncio.run(_run())


def test_golden_eval_handler_runs_real_benchmark():
    out = asyncio.run(BUILTIN_HANDLERS["kstack/golden-eval"]({"save_receipt": False}))
    assert out["total_tasks"] == 10
    assert "pass_rate_pct" in out
    assert len(out["receipt_sha256"]) == 64


def test_golden_eval_rejects_unwired_compare():
    async def _run():
        with pytest.raises(ValueError):
            await BUILTIN_HANDLERS["kstack/golden-eval"]({"compare_to": "eval_x"})

    asyncio.run(_run())


def test_sync_dispatch_fails_closed_on_awaitable():
    proof = kstack_registry.execute_skill(
        name="kstack/golden-eval",
        actor="test",
        inputs={"save_receipt": False},
        handler=BUILTIN_HANDLERS["kstack/golden-eval"],
    )
    assert proof.success is False
    assert "awaitable" in proof.outputs["error"]
    coro = None
    # ensure no leaked coroutine warnings path: the recorded error is the honest result
    assert len(proof.signature_sha256) == 64


def test_execute_endpoint_async_handler_sealed_proof():
    async def _run():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.post(
                "/v1/kstack/execute",
                json={"name": "kstack/golden-eval", "inputs": {"save_receipt": False}},
            )
            assert r.status_code == 200
            proof = r.json()["proof"]
            assert proof["success"] is True
            assert proof["outputs"]["total_tasks"] == 10
            assert "pass_rate_pct" in proof["outputs"]
            assert len(proof["signature_sha256"]) == 64

    asyncio.run(_run())
