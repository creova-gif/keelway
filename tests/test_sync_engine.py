"""
Unit tests for Keelway Cross-Machine Sovereign Sync Engine (core/sync/engine.py).
"""
import pytest
from httpx import AsyncClient, ASGITransport
from core.main import app
from core.sync.engine import (
    SovereignSyncEngine,
    encrypt_payload,
    decrypt_payload,
    DEFAULT_SYNC_SECRET,
)
from cli import cmd_sync


def test_encryption_and_tamper_proofing():
    msg = b"Sensitive Agent Task State: File mutated core/orchestration/agent_loop.py"
    enc = encrypt_payload(msg, DEFAULT_SYNC_SECRET)
    assert "ciphertext_b64" in enc
    assert "auth_tag" in enc
    assert "salt_b64" in enc
    assert "nonce_b64" in enc

    # Valid decrypt
    decrypted = decrypt_payload(enc, DEFAULT_SYNC_SECRET)
    assert decrypted == msg

    # Tampered tag
    tampered_enc = dict(enc)
    tampered_enc["auth_tag"] = "0" * 64
    with pytest.raises(ValueError, match="CRYPTOGRAPHIC_INTEGRITY_FAILURE"):
        decrypt_payload(tampered_enc, DEFAULT_SYNC_SECRET)

    # Wrong secret key
    with pytest.raises(ValueError, match="CRYPTOGRAPHIC_INTEGRITY_FAILURE"):
        decrypt_payload(enc, b"wrong_master_secret_key_12345678")


def test_cross_machine_vector_clock_convergence():
    node_1 = SovereignSyncEngine(machine_id="node_alpha", org_id="corp-test")
    node_2 = SovereignSyncEngine(machine_id="node_beta", org_id="corp-test")

    # Node 1 records 2 mutations
    r1 = node_1.record_mutation("task_state", "task_01", {"status": "PLANNING"})
    r2 = node_1.record_mutation("task_state", "task_01", {"status": "EXECUTING"})
    assert r1.lamport_time == 1
    assert r2.lamport_time == 2
    assert node_1.vector_clock["node_alpha"] == 2

    # Node 1 exports envelope
    env_1 = node_1.export_envelope()
    assert env_1.records_count == 2

    # Node 2 imports envelope
    res = node_2.import_envelope(env_1)
    assert res["status"] == "MERGED"
    assert res["new_records_merged"] == 2
    assert node_2.vector_clock["node_alpha"] == 2

    # Node 2 creates concurrent mutation
    r3 = node_2.record_mutation("task_state", "task_01", {"status": "COMPLETED"})
    assert r3.lamport_time > 2

    # Node 2 exports back to Node 1
    env_2 = node_2.export_envelope()
    res_1 = node_1.import_envelope(env_2)
    assert res_1["new_records_merged"] == 1
    assert node_1.vector_clock["node_beta"] == 1
    assert node_1.vector_clock["node_alpha"] == 2


def test_cross_org_rejection():
    node_a = SovereignSyncEngine(machine_id="node_a", org_id="org_alpha")
    node_b = SovereignSyncEngine(machine_id="node_b", org_id="org_beta")

    node_a.record_mutation("task_state", "task_01", {"diff": "+1"})
    env_a = node_a.export_envelope()

    with pytest.raises(PermissionError, match="CROSS_ORG_DENIAL"):
        node_b.import_envelope(env_a)


@pytest.mark.asyncio
async def test_sync_api_endpoints():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Mutate
        res_mut = await client.post("/v1/sync/mutate", json={
            "entity_type": "flight_tape",
            "task_id": "task_api_test",
            "payload": {"step": 1, "action": "grep"}
        })
        assert res_mut.status_code == 200
        assert res_mut.json()["status"] == "RECORDED"

        # 2. Status
        res_st = await client.get("/v1/sync/status")
        assert res_st.status_code == 200
        st = res_st.json()
        assert st["journal_records_total"] >= 1
        assert "vector_clock" in st

        # 3. Export
        res_exp = await client.post("/v1/sync/export")
        assert res_exp.status_code == 200
        exp_data = res_exp.json()
        assert "envelope_id" in exp_data
        assert "ciphertext_b64" in exp_data

        # 4. Import
        res_imp = await client.post("/v1/sync/import", json={"envelope": exp_data})
        assert res_imp.status_code == 200
        assert res_imp.json()["status"] == "MERGED"

        # 5. Records
        res_rec = await client.get("/v1/sync/records")
        assert res_rec.status_code == 200
        records = res_rec.json()
        assert len(records) >= 1


@pytest.mark.asyncio
async def test_sync_cli_commands(tmp_path, capsys):
    # status
    rc_st = await cmd_sync(action="status")
    assert rc_st == 0
    cap_st = capsys.readouterr()
    assert "CROSS-MACHINE SOVEREIGN SYNC" in cap_st.out

    # demo
    rc_demo = await cmd_sync(action="demo")
    assert rc_demo == 0
    cap_demo = capsys.readouterr()
    assert "ALL MACHINES DETERMINISTICALLY SYNCHRONIZED" in cap_demo.out

    # export to file
    out_file = str(tmp_path / "sync_envelope.json")
    rc_exp = await cmd_sync(action="export", out_path=out_file)
    assert rc_exp == 0
    assert (tmp_path / "sync_envelope.json").exists()

    # import from file
    rc_imp = await cmd_sync(action="import", in_path=out_file)
    assert rc_imp == 0
    cap_imp = capsys.readouterr()
    assert "Sync envelope merged successfully" in cap_imp.out

    # editor bridge status
    rc_ed = await cmd_sync(action="editor")
    assert rc_ed == 0
    cap_ed = capsys.readouterr()
    assert "DUAL-MODE EXTERNAL EDITOR SYNC BRIDGE" in cap_ed.out
    assert "Debounce Interval : 150ms" in cap_ed.out
