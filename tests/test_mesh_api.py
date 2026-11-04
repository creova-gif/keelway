"""
Tests for Keelway Local Team Mesh and Quorum API routes.
"""

import time
import pytest
from httpx import ASGITransport, AsyncClient
from core.main import app
from core.security.auth import launch_token


@pytest.fixture
def owner_headers():
    return {"Authorization": f"Bearer {launch_token()}"}


@pytest.mark.asyncio
async def test_mesh_api_lifecycle(owner_headers):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Mesh status probe
        res = await client.get("/v1/mesh/status", headers=owner_headers)
        assert res.status_code == 200
        data = res.json()
        assert "local_node" in data
        assert "total_pooled_vram_mb" in data

        # 2. Register peer heartbeat
        hb_payload = {
            "node_id": "api_peer_studio",
            "hostname": "studio-workstation.local",
            "lan_ip": "192.168.1.180",
            "port": 7420,
            "available_vram_mb": 32768,
            "active_tasks": 0,
            "tailscale_ip": "100.64.2.10",
        }
        res_hb = await client.post("/v1/mesh/heartbeat", json=hb_payload, headers=owner_headers)
        assert res_hb.status_code == 200
        hb_data = res_hb.json()
        assert hb_data["status"] == "registered"
        assert hb_data["peer"]["hostname"] == "studio-workstation.local"

        # 3. List mesh peers
        res_peers = await client.get("/v1/mesh/peers", headers=owner_headers)
        assert res_peers.status_code == 200
        peers_data = res_peers.json()
        assert any(p["node_id"] == "api_peer_studio" for p in peers_data["peers"])

        # 4. Delegate task across mesh
        del_payload = {
            "intent": "Run distributed speculative batch inference",
            "min_vram_mb": 16000,
            "payload": {"batch_size": 32},
        }
        res_del = await client.post("/v1/mesh/delegate", json=del_payload, headers=owner_headers)
        assert res_del.status_code == 200
        del_data = res_del.json()
        assert del_data["status"] == "ok"
        receipt = del_data["receipt"]
        assert receipt["target_node_id"] == "api_peer_studio"
        assert receipt["status"] == "delegated"
        assert len(receipt["signature"]) > 10

        # 5. Prune mesh peers
        res_prune = await client.post("/v1/mesh/prune", json={"timeout_sec": 300.0}, headers=owner_headers)
        assert res_prune.status_code == 200
        assert "pruned_count" in res_prune.json()


@pytest.mark.asyncio
async def test_agent_run_quorum_api(owner_headers):
    tid = f"api_prod_task_{time.time_ns()}"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Launch production-scoped governed agent task
        task_payload = {
            "task_id": tid,
            "goal": "Apply emergency kernel patch",
            "governed": True,
            "environment": "production",
            "policy": "confirm_mutation",
        }
        res = await client.post("/v1/agent/run", json=task_payload, headers=owner_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["task_id"] == tid

        # Step mutating tool to trigger quorum
        step_payload = {
            "tool_name": "write_file",
            "arguments": {"path": "src/patch.py", "content": "# safe patch"},
        }
        res_step = await client.post(f"/v1/agent/step/{task_payload['task_id']}", json=step_payload, headers=owner_headers)
        assert res_step.status_code == 200
        step_data = res_step.json()
        assert step_data.get("step_result", {}).get("status") == "paused_for_quorum"

        # Submit Security Lead approval via quorum-approve endpoint
        q_sec = {
            "principal_id": "alice_sec",
            "role": "Security Lead",
        }
        res_q_sec = await client.post(f"/v1/agent/quorum-approve/{task_payload['task_id']}", json=q_sec, headers=owner_headers)
        assert res_q_sec.status_code == 200
        assert res_q_sec.json()["quorum_result"]["status"] == "pending_remaining_approvers"

        # Submit Platform Owner approval via quorum-approve endpoint
        q_plat = {
            "principal_id": "bob_plat",
            "role": "Platform Owner",
        }
        res_q_plat = await client.post(f"/v1/agent/quorum-approve/{task_payload['task_id']}", json=q_plat, headers=owner_headers)
        assert res_q_plat.status_code == 200
        assert res_q_plat.json()["quorum_result"]["status"] == "fully_approved"
