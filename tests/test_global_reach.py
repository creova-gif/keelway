import pytest
from core.storage.crdt import LocalFirstSyncEngine, CRDTMutation
from core.api.telephony import TelephonyAdapter
from core.orchestration.mesh import AgentMeshDispatcher, AgentRole


def test_crdt_local_and_remote_merge():
    node_a = LocalFirstSyncEngine(node_id="laptop_us")
    node_b = LocalFirstSyncEngine(node_id="phone_ke")

    # Local mutation on Node A
    mut_a = node_a.set_value(entity_id="task_1", attribute="state", value="IN_PROGRESS")
    assert node_a.get_value("task_1", "state") == "IN_PROGRESS"

    # Merge on Node B
    merged = node_b.merge_remote_mutation(mut_a)
    assert merged is True
    assert node_b.get_value("task_1", "state") == "IN_PROGRESS"

    # Concurrent write with higher clock on B wins
    node_b.set_value(entity_id="task_1", attribute="state", value="COMPLETED")
    delta_b = node_b.export_delta(since_clock=1)
    assert len(delta_b) == 1
    assert delta_b[0]["value"] == "COMPLETED"


def test_telephony_adapter_ussd_parsing_and_menus():
    # Initial dial
    initial_req = {"sessionId": "sess_123", "phoneNumber": "+254712345678", "text": ""}
    parsed = TelephonyAdapter.parse_africastalking_request(initial_req)
    resp, is_term = TelephonyAdapter.generate_menu_response(parsed["depth"], parsed["latest_input"])
    assert resp.startswith("CON Welcome to Kora")
    assert is_term is False

    # Select Option 2 (System Status)
    status_req = {"sessionId": "sess_123", "phoneNumber": "+254712345678", "text": "2"}
    parsed_status = TelephonyAdapter.parse_africastalking_request(status_req)
    resp_status, is_term_status = TelephonyAdapter.generate_menu_response(parsed_status["depth"], parsed_status["latest_input"])
    assert resp_status.startswith("END Kora Core: ACTIVE")
    assert is_term_status is True
    assert len(resp_status) <= 180


@pytest.mark.asyncio
async def test_agent_mesh_dispatcher_consensus():
    dispatcher = AgentMeshDispatcher()
    result = await dispatcher.dispatch_task(
        task_description="Implement CRDT sync engine",
        files=["core/storage/crdt.py", "core/api/telephony.py"],
    )
    assert result["consensus"] == "APPROVED"
    assert result["pipeline"]["architect"]["architecture_aligned"] is True
    assert result["pipeline"]["security"]["dlp_clean"] is True
    assert result["pipeline"]["verification"]["tests_passed"] is True
    assert dispatcher.agent_registry[AgentRole.ARCHITECT]["tasks_completed"] == 1
