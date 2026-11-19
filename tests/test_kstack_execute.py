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
from evals.drift_detector import EvaluationReceiptStore


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


def test_cli_skill_execute_sealed_proof(capsys):
    """`cli.py skill execute` runs the registered handler and prints a sealed proof."""
    import json as _json
    from cli import cmd_skill

    rc = cmd_skill(action="execute", name="kstack/sbom-audit")
    out = capsys.readouterr().out
    assert rc == 0
    proof = _json.loads(out)
    assert proof["skill_name"] == "kstack/sbom-audit"
    assert proof["success"] is True
    assert proof["actor"] == "cli"
    assert proof["signature_sha256"]
    assert proof["outputs"]["sbom"]["bom_format"] == "CycloneDX"


def test_cli_skill_execute_records_actor_and_inputs(capsys):
    import json as _json
    from cli import cmd_skill

    rc = cmd_skill(
        action="execute",
        name="kstack/airgap-verify",
        inputs=_json.dumps({"depth": "shallow"}),
        actor="ci-runner",
    )
    out = capsys.readouterr().out
    assert rc in (0, 1)
    proof = _json.loads(out)
    assert proof["actor"] == "ci-runner"
    assert proof["inputs"] == {"depth": "shallow"}


def test_cli_skill_execute_no_handler_and_unknown(capsys):
    from cli import cmd_skill

    assert cmd_skill(action="execute", name="kstack/plan") == 1
    assert "no registered execution handler" in capsys.readouterr().out
    assert cmd_skill(action="execute", name="kstack/does-not-exist") == 1
    assert "not found" in capsys.readouterr().out


def test_cli_skill_execute_rejects_malformed_inputs(capsys):
    from cli import cmd_skill

    assert cmd_skill(action="execute", name="kstack/sbom-audit", inputs="{bad") == 1
    assert "Invalid --inputs JSON" in capsys.readouterr().out
    assert cmd_skill(action="execute", name="kstack/sbom-audit", inputs="[1,2]") == 1
    assert "JSON object" in capsys.readouterr().out


def test_cli_skill_execute_via_argparse_dispatch(capsys):
    """End-to-end through the parser dispatch: SystemExit carries the proof's exit code."""
    import json as _json
    from cli import main

    with pytest.raises(SystemExit) as exc:
        main(["skill", "execute", "kstack/sbom-audit"])
    assert exc.value.code == 0
    proof = _json.loads(capsys.readouterr().out)
    assert proof["skill_name"] == "kstack/sbom-audit"
    assert proof["success"] is True


def test_golden_eval_compare_to_explicit_baseline(tmp_path):
    """compare_to=<eval_run_id> attaches a DriftAnalysis against the stored baseline."""
    h = BUILTIN_HANDLERS["kstack/golden-eval"]
    receipts_dir = str(tmp_path / "receipts")
    baseline = asyncio.run(h({"receipts_dir": receipts_dir, "model_name": "m-baseline"}))
    candidate = asyncio.run(
        h({"receipts_dir": receipts_dir, "compare_to": baseline["eval_run_id"], "save_receipt": False})
    )
    drift = candidate["drift"]
    assert drift["baseline_run_id"] == baseline["eval_run_id"]
    assert drift["candidate_run_id"] == candidate["eval_run_id"]
    assert drift["drift_severity"] in ("NONE", "LOW", "MEDIUM", "HIGH", "CRITICAL")
    assert drift["baseline_pass_rate"] == baseline["pass_rate_pct"]
    # Candidate was not persisted (save_receipt=False): store still holds exactly one receipt.
    assert len(EvaluationReceiptStore(receipts_dir).list_receipts()) == 1


def test_golden_eval_compare_to_latest_resolves_prior_receipt(tmp_path):
    """compare_to='latest' uses the most recent stored receipt, excluding the candidate itself."""
    h = BUILTIN_HANDLERS["kstack/golden-eval"]
    receipts_dir = str(tmp_path / "receipts")
    first = asyncio.run(h({"receipts_dir": receipts_dir}))
    second = asyncio.run(h({"receipts_dir": receipts_dir}))  # persisted; becomes latest
    assert second["eval_run_id"] != first["eval_run_id"]
    candidate = asyncio.run(
        h({"receipts_dir": receipts_dir, "compare_to": "latest", "save_receipt": False})
    )
    assert candidate["drift"]["baseline_run_id"] == second["eval_run_id"]


def test_golden_eval_compare_to_unknown_baseline_fails_closed(tmp_path):
    """An unresolvable compare_to baseline raises ValueError -> sealed success:false proof."""
    h = BUILTIN_HANDLERS["kstack/golden-eval"]
    receipts_dir = str(tmp_path / "receipts")
    with pytest.raises(ValueError, match="not found"):
        asyncio.run(h({"receipts_dir": receipts_dir, "compare_to": "eval_does_not_exist"}))


def test_golden_eval_compare_to_via_execute_seals_failure(tmp_path):
    """Through execute_skill_async, an unknown baseline is a sealed failed proof, not a raise."""
    h = BUILTIN_HANDLERS["kstack/golden-eval"]
    proof = asyncio.run(
        kstack_registry.execute_skill_async(
            name="kstack/golden-eval",
            actor="test",
            inputs={"receipts_dir": str(tmp_path / "receipts"), "compare_to": "eval_missing"},
            handler=h,
        )
    )
    assert proof.success is False
    assert "not found" in proof.outputs["error"]
