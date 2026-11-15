"""
Phase 14 Verification Suite (`KEEL-DEBUG-021`) — Live Step-Through Debugger Engine, Conditional
Gutter Breakpoints, Paused Frame Stepping (`step_over`, `step_into`, `continue`), Pre-Storage DLP
State Mutation Guard, 4D Routing CodeLens + IDE Bridge URIs, 5-Role RBAC FastAPI Routes (`280`
OpenAPI paths), and Sovereign `keelway debug` CLI Parity.
"""

from __future__ import annotations

import json
from pathlib import Path
import sqlite3

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
import pytest

from cli import main as cli_main
from core.api.platform_debugger_routes import (
    get_step_debugger_engine,
    platform_debugger_router,
)
from core.api.platform_runtime_routes import (
    get_rbac_controller,
    router as platform_runtime_router,
)
from core.main import app as live_app
from core.platform.rbac_webhooks import WorkspaceRbacController
from core.platform.step_debugger import (
    DebuggerPolicyViolationError,
    SQLiteStepDebuggerEngine,
)
from core.security.auth import launch_token


def test_all_six_breakpoint_conditions_and_workspace_isolation(tmp_path: Path) -> None:
    db_file = tmp_path / "bp_conditions.db"
    eng = SQLiteStepDebuggerEngine(db_path=db_file)
    try:
        # 1. No breakpoints -> runs all 3 default steps to COMPLETED
        clean_run = eng.start_session(workspace_id="ws-a", workflow_id="WF-01")
        assert clean_run["status"] == "COMPLETED"
        assert clean_run["current_step_index"] == 2
        assert clean_run["total_steps"] == 3
        assert len(clean_run["frame_sha256"]) == 64
        assert clean_run["variables"]["approved"] is False

        # 2. cost_usd_gt (step 1 verify_ledger has cost_usd=0.31 > 0.25)
        bp_cost = eng.set_breakpoint(
            workspace_id="ws-a", workflow_id="WF-01", condition_type="cost_usd_gt", threshold=0.25
        )
        s_cost = eng.start_session(workspace_id="ws-a", workflow_id="WF-01")
        assert s_cost["status"] == "PAUSED" and s_cost["current_step_index"] == 1
        assert s_cost["hit_breakpoint_id"] == bp_cost["breakpoint_id"]
        assert "cost_usd_gt" in str(s_cost["hit_reason"])
        assert eng.delete_breakpoint(workspace_id="ws-a", breakpoint_id=bp_cost["breakpoint_id"])["deleted"] is True

        # 3. hybrid_score_lt (step 1 verify_ledger has hybrid_score=0.42 < 0.50)
        bp_score = eng.set_breakpoint(
            workspace_id="ws-a", workflow_id="WF-01", condition_type="hybrid_score_lt", threshold=0.50
        )
        s_score = eng.start_session(workspace_id="ws-a", workflow_id="WF-01")
        assert s_score["status"] == "PAUSED" and s_score["current_step_index"] == 1
        assert "hybrid_score_lt" in str(s_score["hit_reason"])
        eng.delete_breakpoint(workspace_id="ws-a", breakpoint_id=bp_score["breakpoint_id"])

        # 4. before_shell_tool (step 1 tool_name="shell_exec")
        bp_shell = eng.set_breakpoint(
            workspace_id="ws-a", workflow_id="WF-01", condition_type="before_shell_tool"
        )
        s_shell = eng.start_session(workspace_id="ws-a", workflow_id="WF-01")
        assert s_shell["status"] == "PAUSED" and s_shell["active_step"]["tool_name"] == "shell_exec"
        eng.delete_breakpoint(workspace_id="ws-a", breakpoint_id=bp_shell["breakpoint_id"])

        # 5. before_p10_gate (step 2 approve_payout has requires_p10=True)
        bp_p10 = eng.set_breakpoint(
            workspace_id="ws-a", workflow_id="WF-01", condition_type="before_p10_gate"
        )
        s_p10 = eng.start_session(workspace_id="ws-a", workflow_id="WF-01")
        assert s_p10["status"] == "PAUSED" and s_p10["current_step_index"] == 2
        assert s_p10["active_step"]["node_id"] == "approve_payout"
        eng.delete_breakpoint(workspace_id="ws-a", breakpoint_id=bp_p10["breakpoint_id"])

        # 6. line_match + node_id filter (line 21 + approve_payout) & disabled breakpoint skip
        eng.set_breakpoint(
            workspace_id="ws-a", workflow_id="WF-01", condition_type="always", enabled=False
        )
        bp_line = eng.set_breakpoint(
            workspace_id="ws-a", workflow_id="WF-01", node_id="approve_payout", line_number=21, condition_type="line_match"
        )
        s_line = eng.start_session(workspace_id="ws-a", workflow_id="WF-01")
        assert s_line["status"] == "PAUSED" and s_line["current_step_index"] == 2
        assert s_line["hit_breakpoint_id"] == bp_line["breakpoint_id"]
        eng.delete_breakpoint(workspace_id="ws-a", breakpoint_id=bp_line["breakpoint_id"])

        # 7. always on step 0 + workspace isolation
        bp_always = eng.set_breakpoint(workspace_id="ws-a", workflow_id="WF-01", condition_type="always")
        s_always = eng.start_session(workspace_id="ws-a", workflow_id="WF-01")
        assert s_always["status"] == "PAUSED" and s_always["current_step_index"] == 0
        assert eng.list_breakpoints(workspace_id="ws-b")["count"] == 0
        with pytest.raises(KeyError):
            eng.delete_breakpoint(workspace_id="ws-b", breakpoint_id=bp_always["breakpoint_id"])
    finally:
        eng.close()


def test_stepping_mutation_dlp_rejection_and_sqlite_wal_persistence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_file = tmp_path / "wal_debugger.db"
    monkeypatch.setenv("KEELWAY_PLATFORM_DB_PATH", str(db_file))
    eng1 = SQLiteStepDebuggerEngine()
    raw_secrets = [
        "sk-live-secret1234567890abcdef",
        "AKIAIOSFODNN7EXAMPLE",
        "ghp_1234567890abcdef1234567890",
        "-----BEGIN RSA PRIVATE KEY-----",
    ]
    try:
        assert Path(str(eng1.db_path)) == db_file
        bp1 = eng1.set_breakpoint(workspace_id="ws-wal", workflow_id="WF-STEP", condition_type="always")
        bp_p10 = eng1.set_breakpoint(workspace_id="ws-wal", workflow_id="WF-STEP", condition_type="before_p10_gate")
        sess = eng1.start_session(workspace_id="ws-wal", workflow_id="WF-STEP")
        sid = sess["session_id"]
        sha0 = sess["frame_sha256"]
        assert sess["status"] == "PAUSED" and sess["current_step_index"] == 0 and sess["step_depth"] == 0

        # Delete `always` bp so `continue` later only stops on `before_p10_gate` (step 2)
        eng1.delete_breakpoint(workspace_id="ws-wal", breakpoint_id=bp1["breakpoint_id"])

        # step_into -> depth 1 sub-frame added to call_stack
        into1 = eng1.step_session(workspace_id="ws-wal", session_id=sid, action="step_into")
        assert into1["step_depth"] == 1 and len(into1["call_stack"]) == 2
        assert into1["call_stack"][1]["node_id"] == "triage_claim:kbrain_query"
        assert into1["frame_sha256"] != sha0

        # second step_into -> resets depth=0 and advances to step 1
        into2 = eng1.step_session(workspace_id="ws-wal", session_id=sid, action="step_into")
        assert into2["step_depth"] == 0 and into2["current_step_index"] == 1
        assert into2["active_step"]["node_id"] == "verify_ledger"

        # mutate_state (clean patch) -> updates variables, increments mutation_count, keeps step 1
        mut = eng1.step_session(
            workspace_id="ws-wal", session_id=sid, action="mutate_state", state_patch={"override_route": "keelway-core:7b"}
        )
        assert mut["current_step_index"] == 1 and mut["mutation_count"] == 1
        assert mut["variables"]["override_route"] == "keelway-core:7b"
        assert mut["mutations"] == [{"seq": 1, "patched_keys": ["override_route"], "at_step": 1}]

        # DLP rejection on all 4 secret classes -> never persisted to SQLite
        for secret_val in raw_secrets:
            with pytest.raises(DebuggerPolicyViolationError):
                eng1.step_session(
                    workspace_id="ws-wal", session_id=sid, action="mutate_state", state_patch={"leak": secret_val}
                )

        # continue -> advances from step 1 and pauses on step 2 (bp_p10)
        cont1 = eng1.step_session(workspace_id="ws-wal", session_id=sid, action="continue")
        assert cont1["status"] == "PAUSED" and cont1["current_step_index"] == 2
        assert cont1["hit_breakpoint_id"] == bp_p10["breakpoint_id"]

        # step_over past final step -> COMPLETED
        done = eng1.step_session(workspace_id="ws-wal", session_id=sid, action="step_over")
        assert done["status"] == "COMPLETED" and done["current_step_index"] == 2
    finally:
        eng1.close()

    # Re-instantiate engine from disk to verify WAL persistence + zero leaked secrets
    eng2 = SQLiteStepDebuggerEngine(db_path=db_file)
    try:
        listed = eng2.list_sessions(workspace_id="ws-wal")
        assert listed["count"] == 1
        reloaded = listed["sessions"][0]
        assert reloaded["status"] == "COMPLETED" and reloaded["mutation_count"] == 1
        assert reloaded["variables"]["override_route"] == "keelway-core:7b"

        with sqlite3.connect(str(db_file)) as raw_conn:
            mode = raw_conn.execute("PRAGMA journal_mode").fetchone()[0]
            assert str(mode).lower() == "wal"
            dump_text = "\n".join(raw_conn.iterdump())
            for secret_val in raw_secrets:
                assert secret_val not in dump_text
    finally:
        eng2.close()


def test_codelens_ast_symbols_breakpoint_counts_and_bridge_uris(tmp_path: Path) -> None:
    eng = SQLiteStepDebuggerEngine(db_path=tmp_path / "codelens.db")
    try:
        eng.set_breakpoint(
            workspace_id="ws-ide", workflow_id="WF-IDE-01", node_id="verify_ledger", line_number=14, condition_type="before_shell_tool"
        )
        default_cl = eng.get_codelens(workspace_id="ws-ide", workflow_id="WF-IDE-01", file_path="workflows/refund_agent.py")
        bridge = default_cl["bridge"]
        assert bridge["protocol_version"] == "2026-11-15"
        assert bridge["extension_id"] == "keelway.vscode-keelway"
        assert bridge["loopback_origin_policy"] == "extension-host-bearer-only"
        assert bridge["vscode_attach_uri"] == "vscode://keelway.vscode-keelway/attach?port=7420&workspace=ws-ide&workflow=WF-IDE-01"
        assert bridge["cursor_attach_uri"] == "cursor://keelway.vscode-keelway/attach?port=7420&workspace=ws-ide&workflow=WF-IDE-01"
        by_sym = {item["symbol"]: item for item in default_cl["lenses"]}
        assert set(by_sym.keys()) == {"triage_claim", "verify_ledger", "approve_payout"}
        assert by_sym["verify_ledger"]["attached_breakpoints"] == 1
        assert by_sym["approve_payout"]["model_checkpoint"] == "claude-3-7-sonnet"

        custom_py = (
            "def ingest_claim(state):\n"
            "    return state\n\n"
            "def shell_audit_step(state):\n"
            "    return state\n\n"
            "def approve_p10_wire(state):\n"
            "    return state\n"
        )
        parsed_cl = eng.get_codelens(
            workspace_id="ws-ide", workflow_id="WF-IDE-01", file_path="workflows/custom.py", source_code=custom_py
        )
        assert [item["symbol"] for item in parsed_cl["lenses"]] == [
            "ingest_claim", "shell_audit_step", "approve_p10_wire"
        ]
        assert "P-10-Gated" in parsed_cl["lenses"][2]["provenance_4d"]
    finally:
        eng.close()


@pytest.mark.asyncio
async def test_fastapi_debugger_routes_5_role_rbac_dlp_422_and_openapi_280(tmp_path: Path) -> None:
    db_file = tmp_path / "api_phase14.db"
    dbg_eng = SQLiteStepDebuggerEngine(db_path=db_file)
    rbac = WorkspaceRbacController(db_path=db_file)

    test_app = FastAPI()
    test_app.include_router(platform_runtime_router)
    test_app.include_router(platform_debugger_router)
    test_app.dependency_overrides[get_step_debugger_engine] = lambda: dbg_eng
    test_app.dependency_overrides[get_rbac_controller] = lambda: rbac

    token = launch_token()
    role_headers = {
        r: {"Authorization": f"Bearer {token}", "X-Keelway-Role": r, "X-Keelway-Actor": f"{r}-actor"}
        for r in ("owner", "admin", "builder", "operator", "viewer")
    }
    try:
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            # Viewer blocked (403) on all mutating routes; Operator blocked on workflows:write
            assert (await client.post("/v1/platform/debugger/breakpoints", headers=role_headers["viewer"], json={"workspace_id": "default", "condition_type": "always"})).status_code == 403
            assert (await client.post("/v1/platform/debugger/breakpoints", headers=role_headers["operator"], json={"workspace_id": "default", "condition_type": "always"})).status_code == 403
            assert (await client.post("/v1/platform/debugger/sessions", headers=role_headers["viewer"], json={"workspace_id": "default"})).status_code == 403

            # Builder sets breakpoint (workflows:write -> 200)
            bp_res = await client.post(
                "/v1/platform/debugger/breakpoints",
                headers=role_headers["builder"],
                json={"workspace_id": "default", "workflow_id": "WF-API", "condition_type": "cost_usd_gt", "threshold": 0.25},
            )
            assert bp_res.status_code == 200
            bp_id = bp_res.json()["breakpoint_id"]

            # Viewer can read breakpoints & codelens (workspace:read -> 200)
            assert (await client.get("/v1/platform/debugger/breakpoints?workspace_id=default", headers=role_headers["viewer"])).json()["count"] == 1
            cl_res = await client.get("/v1/platform/debugger/codelens?workspace_id=default&workflow_id=WF-API", headers=role_headers["viewer"])
            assert cl_res.status_code == 200 and len(cl_res.json()["lenses"]) == 3

            # Operator starts & steps session (agents:execute -> 200), Viewer denied on step (403)
            sess_res = await client.post(
                "/v1/platform/debugger/sessions", headers=role_headers["operator"], json={"workspace_id": "default", "workflow_id": "WF-API"}
            )
            assert sess_res.status_code == 200 and sess_res.json()["status"] == "PAUSED"
            sid = sess_res.json()["session_id"]

            assert (await client.post(f"/v1/platform/debugger/sessions/{sid}/step", headers=role_headers["viewer"], json={"workspace_id": "default", "action": "step_over"})).status_code == 403
            assert (await client.get("/v1/platform/debugger/sessions?workspace_id=default", headers=role_headers["viewer"])).json()["count"] == 1

            # DLP secret in state_patch -> HTTP 422 with code="policy_violation"
            dlp_res = await client.post(
                f"/v1/platform/debugger/sessions/{sid}/step",
                headers=role_headers["admin"],
                json={"workspace_id": "default", "action": "mutate_state", "state_patch": {"api_key": "sk-proj-secret1234567890"}},
            )
            assert dlp_res.status_code == 422
            assert dlp_res.json()["code"] == "policy_violation"

            # Invalid action -> 422; Unknown session/breakpoint -> 404
            assert (await client.post(f"/v1/platform/debugger/sessions/{sid}/step", headers=role_headers["owner"], json={"workspace_id": "default", "action": "teleport"})).status_code == 422
            assert (await client.post("/v1/platform/debugger/sessions/dbg-missing/step", headers=role_headers["owner"], json={"workspace_id": "default", "action": "step_over"})).status_code == 404
            assert (await client.delete("/v1/platform/debugger/breakpoints/bp-missing?workspace_id=default", headers=role_headers["builder"])).status_code == 404

            # Step over & delete breakpoint
            step_ok = await client.post(
                f"/v1/platform/debugger/sessions/{sid}/step", headers=role_headers["operator"], json={"workspace_id": "default", "action": "step_over"}
            )
            assert step_ok.status_code == 200 and step_ok.json()["current_step_index"] == 2
            del_ok = await client.delete(f"/v1/platform/debugger/breakpoints/{bp_id}?workspace_id=default", headers=role_headers["builder"])
            assert del_ok.status_code == 200 and del_ok.json()["deleted"] is True

        openapi_paths = live_app.openapi()["paths"]
        assert len(openapi_paths) == 280
        for route in (
            "/v1/platform/debugger/breakpoints",
            "/v1/platform/debugger/breakpoints/{breakpoint_id}",
            "/v1/platform/debugger/sessions",
            "/v1/platform/debugger/sessions/{session_id}/step",
            "/v1/platform/debugger/codelens",
        ):
            assert route in openapi_paths
    finally:
        dbg_eng.close()
        rbac.close()


def test_sovereign_cli_keelway_debug_end_to_end(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    db_file = str(tmp_path / "cli_phase14.db")

    assert cli_main(["debug", "breakpoint", "set", "--workflow-id", "WF-CLI", "--condition", "cost_usd_gt", "--threshold", "0.25", "--workspace", "ws-cli", "--db-path", db_file, "--json"]) == 0
    bp = json.loads(capsys.readouterr().out)
    assert bp["condition_type"] == "cost_usd_gt" and bp["breakpoint_id"].startswith("bp-")

    assert cli_main(["debug", "breakpoint", "list", "--workflow-id", "WF-CLI", "--workspace", "ws-cli", "--db-path", db_file, "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["count"] == 1

    assert cli_main(["debug", "session", "start", "--workflow-id", "WF-CLI", "--workspace", "ws-cli", "--db-path", db_file, "--json"]) == 0
    started = json.loads(capsys.readouterr().out)
    sid = started["session_id"]
    assert started["status"] == "PAUSED" and started["current_step_index"] == 1

    assert cli_main(["debug", "session", "list", "--limit", "10", "--workspace", "ws-cli", "--db-path", db_file, "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["count"] == 1

    assert cli_main(["debug", "session", "step", "--session-id", sid, "--action", "mutate_state", "--patch-json", '{"route":"local"}', "--workspace", "ws-cli", "--db-path", db_file, "--json"]) == 0
    mutated = json.loads(capsys.readouterr().out)
    assert mutated["mutation_count"] == 1 and mutated["variables"]["route"] == "local"

    # Secret in CLI --patch-json -> fails closed with exit code 1
    assert cli_main(["debug", "session", "step", "--session-id", sid, "--action", "mutate_state", "--patch-json", '{"k":"sk-live-secret1234567890"}', "--workspace", "ws-cli", "--db-path", db_file, "--json"]) == 1
    err_payload = json.loads(capsys.readouterr().out)
    assert err_payload["code"] == "policy_violation"

    assert cli_main(["debug", "session", "step", "--session-id", sid, "--action", "continue", "--workspace", "ws-cli", "--db-path", db_file, "--json"]) == 0
    finished = json.loads(capsys.readouterr().out)
    assert finished["status"] == "COMPLETED"

    assert cli_main(["debug", "codelens", "--workflow-id", "WF-CLI", "--file", "workflows/refund_agent.py", "--workspace", "ws-cli", "--db-path", db_file, "--json"]) == 0
    cl = json.loads(capsys.readouterr().out)
    assert len(cl["lenses"]) == 3 and cl["bridge"]["extension_id"] == "keelway.vscode-keelway"

    assert cli_main(["debug", "breakpoint", "rm", "--breakpoint-id", bp["breakpoint_id"], "--workspace", "ws-cli", "--db-path", db_file, "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["deleted"] is True
