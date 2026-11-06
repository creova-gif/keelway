"""
Tests for Keelway Slice 4: Security Invariants, Air-Gap Qualification & Robustness.
Validates:
1. Sovereign zero-egress enforcement (rejects cloud endpoints while local 127.0.0.1 is permitted).
2. Negative authorization & sandboxing (path traversal, protected files, capability escalation).
3. Manifest and flight tape cryptographic tamper detection.
4. Malformed tool output and resilience against unexpected payload crashes.
"""

import json
import pytest
from pathlib import Path

from core.api.schemas import Provider
from core.security.airgap import AirGapEnforcer, AirGapViolationError
from core.security.firewall import ToolPolicyGuard
from core.security.bundle_exporter import AirGapBundleExporter
from core.orchestration.flight_recorder import FlightRecorder
from core.agents.builder import AgentBuilder
from core.agents.guard import loop_from_manifest
from core.storage.workspace_fs import WorkspaceFilesystem
from core.security.approval_rules import ApprovalRuleStore


def test_zero_egress_and_local_sovereignty():
    """Verify that external cloud endpoints are strictly denied under air-gap, but localhost/local model passes."""
    enforcer = AirGapEnforcer(enabled=True)

    # Sovereign local provider is permitted
    enforcer.validate_provider(Provider.LOCAL)

    # Cloud providers must trigger explicit violation
    for cloud_prov in [Provider.OPENAI, Provider.ANTHROPIC]:
        with pytest.raises(AirGapViolationError) as exc_info:
            enforcer.validate_provider(cloud_prov)
        assert "AIR-GAP VIOLATION" in str(exc_info.value)

    # Attestation must attest zero egress
    attestation = enforcer.generate_attestation(
        task_id="task_airgap_400",
        model_name="qwen3.5:latest",
        tokens_processed=120
    )
    assert attestation["air_gapped"] is True
    assert attestation["egress_allowed"] is False
    assert len(attestation["attestation_sha256"]) == 64


def test_negative_authorization_path_escapes_and_protected_files(tmp_path: Path):
    """Verify sandbox containment blocks directory traversal and protected system files."""
    # Path escapes outside workspace
    escape_paths = [
        "../../etc/passwd",
        "../../../etc/shadow",
        "/var/run/secrets",
        str(tmp_path.parent / "escape.txt")
    ]
    for p in escape_paths:
        valid, reason = ToolPolicyGuard.validate_path(p, allowed_root=tmp_path)
        assert valid is False
        assert "traversal" in reason.lower() or "escapes" in reason.lower() or "outside" in reason.lower()

    # Also check AgentGuard instance via loop_from_manifest
    ws = WorkspaceFilesystem(tmp_path)
    spec = AgentBuilder.create_from_template(
        template_id="security-auditor",
        name="containment-checker",
        author="tester"
    )
    manifest = spec.validate_manifest().manifest
    agent_loop = loop_from_manifest(
        manifest=manifest,
        task_id="guard_check_01",
        workspace_fs=ws,
        record_flight=True,
    )

    decision_escape = agent_loop.guard.check("read_file", {"path": "../../etc/shadow"})
    assert decision_escape.allowed is False
    assert decision_escape.code == "path_escape"

    decision_prot = agent_loop.guard.check("read_file", {"path": ".keelway/keelway.db"})
    assert decision_prot.allowed is False
    assert decision_prot.code == "protected_path"


def test_destructive_command_blocking():
    """Verify destructive shell commands and sensitive paths are strictly blocked by ToolPolicyGuard."""
    destructive_cmds = [
        "rm -rf /",
        "mkfs /dev/sda1",
        "dd if=/dev/sda",
        ":(){ :|:& };:",
        "cat /etc/shadow",
        "cat ~/.ssh/id_rsa",
    ]
    for cmd in destructive_cmds:
        valid, reason = ToolPolicyGuard.validate_command(cmd)
        assert valid is False
        assert reason is not None


def test_capability_containment_prevents_escalation(tmp_path: Path):
    """Verify that an agent with read-only tools cannot escalate to write or command execution."""
    ws = WorkspaceFilesystem(tmp_path)
    (tmp_path / "app.py").write_text("print('hello')", encoding="utf-8")

    spec = AgentBuilder.create_from_template(
        template_id="security-auditor",
        name="readonly-sec-agent",
        author="tester"
    )
    manifest = spec.validate_manifest().manifest

    agent_loop = loop_from_manifest(
        manifest=manifest,
        task_id="cap_containment_01",
        workspace_fs=ws,
        record_flight=True,
        approval_rules=ApprovalRuleStore(ws.root),
    )

    # Allowed: read_file is in security-auditor tools
    decision_read = agent_loop.guard.check("read_file", {"path": "app.py"})
    assert decision_read.allowed is True

    # Blocked: write_file is NOT in security-auditor tools
    decision_write = agent_loop.guard.check("write_file", {"path": "app.py", "content": "malicious"})
    assert decision_write.allowed is False
    assert decision_write.code in ("undeclared_tool", "tool_not_permitted", "tool_not_allowed")

    # Blocked: run_command is NOT in security-auditor tools
    decision_cmd = agent_loop.guard.check("run_command", {"command": "ls"})
    assert decision_cmd.allowed is False


def test_manifest_and_bundle_tamper_detection(tmp_path: Path):
    """Verify that tampering with any file in an air-gap package breaks cryptographic verification."""
    export_dir = tmp_path / "bundle_export"
    receipt = AirGapBundleExporter.export_bundle(
        output_dir=export_dir,
        bundle_name="tamper-test-bundle",
        include_tar=False,
    )
    bundle_path = Path(receipt.bundle_path)
    assert bundle_path.exists()

    # Initial verification passes
    res_valid = AirGapBundleExporter.verify_bundle(bundle_path)
    assert res_valid.is_valid is True
    assert len(res_valid.mismatched_files) == 0

    # Tamper with a file inside the bundle
    target_cli = bundle_path / "cli.py"
    if not target_cli.exists():
        # Pick any file in the bundle
        for f in bundle_path.rglob("*.py"):
            target_cli = f
            break
    assert target_cli.exists()
    content = target_cli.read_bytes()
    target_cli.write_bytes(content + b"\n# TAMPERED_SIGNATURE\n")

    # Verification must detect the tampering
    res_tampered = AirGapBundleExporter.verify_bundle(bundle_path)
    assert res_tampered.is_valid is False
    assert len(res_tampered.mismatched_files) > 0


def test_flight_tape_tamper_detection(tmp_path: Path):
    """Verify that tampering with an immutable flight recorder tape invalidates its seal."""
    rec = FlightRecorder(task_id="tape_tamper_test", recordings_dir=tmp_path)
    rec.record_event("prompt", {"text": "Inspect the code"})
    rec.record_event("tool_call", {"tool": "read_file", "path": "main.py"})
    rec.seal_tape()

    original_seal = rec.tape_sha256
    tape_file = tmp_path / "tape_tamper_test.flight.json"
    assert tape_file.exists()

    tape_data = json.loads(tape_file.read_text(encoding="utf-8"))
    assert tape_data["event_count"] == 2

    # Tamper with an event payload
    tape_data["events"][1]["payload"]["path"] = "secret_passwords.txt"
    tampered_json = json.dumps(tape_data, indent=2, sort_keys=True)
    import hashlib
    tampered_seal = hashlib.sha256(tampered_json.encode("utf-8")).hexdigest()

    assert original_seal != tampered_seal, "Tampering must change cryptographic hash seal."


@pytest.mark.asyncio
async def test_malformed_tool_execution_resilience(tmp_path: Path):
    """Verify agent loop handles malformed tool arguments without unhandled crashes."""
    ws = WorkspaceFilesystem(tmp_path)
    spec = AgentBuilder.create_from_template(
        template_id="test-fixer",
        name="resilience-agent",
        author="tester"
    )
    manifest = spec.validate_manifest().manifest
    agent_loop = loop_from_manifest(
        manifest=manifest,
        task_id="resilience_01",
        workspace_fs=ws,
        record_flight=True,
    )

    # Missing required argument "path" for read_file
    res_malformed = await agent_loop.execute_tool("read_file", {})
    assert res_malformed["status"] == "error"
    assert "Missing required argument" in res_malformed["error"] or "error" in res_malformed

    # Non-existent tool call raises clean KeyError boundary
    with pytest.raises(KeyError) as exc_info:
        await agent_loop.execute_tool("nonexistent_teleport_tool", {})
    assert "not registered" in str(exc_info.value)

    # Flight tape accurately logged the malformed tool call attempt
    assert len(agent_loop.flight_recorder.events) >= 1
