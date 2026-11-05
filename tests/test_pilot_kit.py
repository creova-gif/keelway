"""
Unit & Integration Tests for Keelway Customer Pilot Kit & Simulation Engine.
Verifies:
- All 5 target prospective engineering lead dossiers.
- Mom Test interview protocol generation.
- Zero-risk automated pilot simulation (concurrent lease mutation & pessimistic pause).
- Cryptographic SHA-256 seal of PilotReceipt.
- CLI pilot commands (candidates, interview, run, export).
"""

import json
import pytest
from pathlib import Path

from core.pilot.kit import (
    get_pilot_candidates,
    get_pilot_candidate,
    PilotSimulationEngine,
    PilotReceipt,
)
from cli import cmd_pilot


def test_pilot_candidate_dossiers():
    """Verifies all 5 pre-configured engineering lead candidates exist and have required fields."""
    candidates = get_pilot_candidates()
    assert len(candidates) == 5

    candidate_ids = [c.id for c in candidates]
    assert "rigel_rootly" in candidate_ids
    assert "platform_lead_cursor" in candidate_ids
    assert "fintech_security_architect" in candidate_ids
    assert "oss_maintainer_lead" in candidate_ids
    assert "multi_agent_architect" in candidate_ids

    rigel = get_pilot_candidate("rigel_rootly")
    assert rigel is not None
    assert rigel.name == "Rigel St. Pierre"
    assert rigel.organization == "Rootly"
    assert len(rigel.interview_questions) >= 3
    assert "Dual-Mode" in rigel.wedge_capability
    assert "30-minute" in rigel.commitment_ask


@pytest.mark.asyncio
async def test_pilot_simulation_engine_execution(tmp_path):
    """Verifies that the pilot simulation runs end-to-end and detects concurrent mutation."""
    sim_dir = tmp_path / "pilot_sandbox"
    engine = PilotSimulationEngine(workspace_dir=sim_dir, candidate_id="rigel_rootly")

    receipt = await engine.run_simulation()
    assert isinstance(receipt, PilotReceipt)
    assert receipt.candidate_id == "rigel_rootly"
    assert receipt.conflict_detected is True
    assert receipt.conflict_resolution == "keep_external"
    assert receipt.tests_passed is True
    assert len(receipt.flight_tape_sha256) == 64
    assert len(receipt.receipt_sha256) == 64

    # Verify receipt file was saved to disk
    receipt_file = sim_dir / ".keelway" / "pilot_receipt.json"
    assert receipt_file.exists()
    saved_data = json.loads(receipt_file.read_text(encoding="utf-8"))
    assert saved_data["receipt_sha256"] == receipt.receipt_sha256


@pytest.mark.asyncio
async def test_pilot_cli_commands(tmp_path, capsys):
    """Verifies CLI execution of pilot subcommands."""
    # 1. candidates
    rc_c = await cmd_pilot(action="candidates")
    assert rc_c == 0
    cap_c = capsys.readouterr()
    assert "Rigel St. Pierre" in cap_c.out
    assert "Rootly" in cap_c.out

    # 2. interview
    rc_i = await cmd_pilot(action="interview", candidate_id="rigel_rootly")
    assert rc_i == 0
    cap_i = capsys.readouterr()
    assert "WORKFLOW INTERVIEW PROTOCOL: RIGEL ST. PIERRE" in cap_i.out
    assert "The Mom Test" in cap_i.out

    # 3. run simulation
    sim_out_dir = str(tmp_path / "cli_sim_dir")
    rc_r = await cmd_pilot(action="run", candidate_id="rigel_rootly", target_dir=sim_out_dir)
    assert rc_r == 0
    cap_r = capsys.readouterr()
    assert "Simulation completed successfully" in cap_r.out
    assert "Conflict Detected   : True" in cap_r.out

    # 4. export dossier
    export_file = str(tmp_path / "pilot_dossier.json")
    rc_e = await cmd_pilot(action="export", out_file=export_file)
    assert rc_e == 0
    assert Path(export_file).exists()
    dossier_data = json.loads(Path(export_file).read_text(encoding="utf-8"))
    assert len(dossier_data["candidates"]) == 5
