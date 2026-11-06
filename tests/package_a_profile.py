"""Profile A prerequisite checks. Owned by foundation-repair package A.

The default suite is Profile A: it must stay hermetic on a Linux runner that
has no reachable local model and no verified OS confinement. A confinement
binary that fails ``Sandbox.verify()`` is not enough. The live integrations
stay in the tree. Profile A skips one only when its own prerequisite is
absent, and the skip message is the reason. A skip is not a pass and is not
live verification.

The executable release boundary is ``python -m tests.release_live_gate``.
It exits 0 only when every required live proof passed. A skipped proof or a
missing prerequisite is UNAVAILABLE/UNRUN and a non-zero exit. Profile A
staying green would still not mean that command passed.

- Live model: ``LocalAdapter.is_available()`` is true for
  ``http://localhost:11434`` and ``qwen3.5:latest``.
- Live OS isolation: ``Sandbox.verify()`` succeeds. The three product
  integrations may use seatbelt or bubblewrap. The thirteen
  ``live_seatbelt`` proofs are macOS ``sandbox-exec`` only; bubblewrap does
  not satisfy them.

Profile A itself remains ``pytest -v`` with no marker deselection. Tests
marked ``safety_negative`` are mandatory in Profile A and must not be skipped.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest

from core.agents.sandbox import Sandbox
from core.models.adapters.local import LocalAdapter

LIVE_MODEL_URL = "http://localhost:11434"
LIVE_MODEL_NAME = "qwen3.5:latest"
_ISOLATION_PROBE: tuple[bool, str] | None = None


def skip_unless_live_local_model() -> None:
    """Skip only when the Slice 2 local model is not actually reachable."""
    adapter = LocalAdapter(base_url=LIVE_MODEL_URL, default_model=LIVE_MODEL_NAME)
    if adapter.is_available():
        return
    pytest.skip(
        "Profile A: live-model integration prerequisite absent: "
        f"LocalAdapter.is_available() is false for {LIVE_MODEL_URL} "
        f"model {LIVE_MODEL_NAME}. "
        "Release gate: this test must be run again and must pass where that "
        "local model answers. A skip is not a pass and does not release."
    )


def live_os_isolation_status() -> tuple[bool, str]:
    """True only when this machine's sandbox self-test passes.

    A present but unverified ``bwrap`` or ``sandbox-exec`` is not a
    prerequisite. GitHub-hosted Ubuntu has been observed with ``bwrap``
    installed while ``Sandbox.verify()`` still reports escapes.
    """
    global _ISOLATION_PROBE
    if _ISOLATION_PROBE is None:
        probe = Path(tempfile.mkdtemp(prefix="keelway-profile-a-"))
        try:
            _ISOLATION_PROBE = Sandbox(probe).verify()
        finally:
            shutil.rmtree(probe, ignore_errors=True)
    return _ISOLATION_PROBE


LIVE_MODEL_PROOFS = (
    "tests/test_slice2_ide_usability_e2e.py::test_slice2_end_to_end_ide_usability_and_real_local_model",
)

LIVE_OS_ISOLATION_PROOFS = (
    "tests/test_dual_mode_e2e_acceptance.py::test_dual_mode_agent_builder_export_import_and_cross_repo",
    "tests/test_slice3_agent_builder_e2e.py::test_slice3_agent_builder_scaffold_pack_import_cross_repo",
    "tests/test_slice4_security_offline.py::test_malformed_tool_execution_resilience",
)

# macOS seatbelt only. A verified Linux bubblewrap run does not cover these.
SEATBELT_CONFINEMENT_PROOFS = (
    "tests/test_agent_sandbox.py::test_self_test_passes_on_this_machine",
    "tests/test_agent_sandbox.py::test_secrets_in_the_parent_environment_do_not_reach_commands",
    "tests/test_agent_sandbox.py::test_cannot_read_or_write_outside_the_workspace",
    "tests/test_agent_sandbox.py::test_can_do_normal_work_inside_the_workspace",
    "tests/test_agent_sandbox.py::test_keelway_state_and_git_internals_are_protected_inside_the_workspace",
    "tests/test_agent_sandbox.py::test_no_network_even_to_loopback",
    "tests/test_agent_sandbox.py::test_subprocesses_stay_confined",
    "tests/test_agent_sandbox.py::test_commands_are_not_run_through_a_shell",
    "tests/test_agent_sandbox.py::test_timeout_kills_the_whole_process_group",
    "tests/test_agent_sandbox.py::test_output_is_capped_and_missing_commands_are_reported",
    "tests/test_agent_sandbox.py::test_loop_runs_allowed_commands_in_the_sandbox_with_a_scrubbed_env",
    "tests/test_agent_sandbox.py::test_autonomous_agent_may_run_commands_only_because_the_sandbox_is_verified",
    "tests/test_agent_sandbox.py::test_workspace_sandbox_cannot_fall_back_to_a_host_command",
)

REQUIRED_SAFETY_NEGATIVES = (
    "tests/test_package_a_safety_negatives.py::test_missing_or_invalid_auth_cannot_create_a_run_or_mutate_a_repo[missing]",
    "tests/test_package_a_safety_negatives.py::test_missing_or_invalid_auth_cannot_create_a_run_or_mutate_a_repo[invalid]",
    "tests/test_package_a_safety_negatives.py::test_missing_or_invalid_auth_cannot_enqueue_a_job[missing]",
    "tests/test_package_a_safety_negatives.py::test_missing_or_invalid_auth_cannot_enqueue_a_job[invalid]",
    "tests/test_package_a_safety_negatives.py::test_missing_or_invalid_auth_cannot_poll_a_job[missing]",
    "tests/test_package_a_safety_negatives.py::test_missing_or_invalid_auth_cannot_poll_a_job[shape-only]",
    "tests/test_package_a_safety_negatives.py::test_shape_only_token_cannot_poll_a_studio_runner_job",
    "tests/test_package_a_safety_negatives.py::test_missing_or_invalid_auth_cannot_write_a_workspace_file[missing]",
    "tests/test_package_a_safety_negatives.py::test_missing_or_invalid_auth_cannot_write_a_workspace_file[invalid]",
    "tests/test_package_a_safety_negatives.py::test_missing_or_invalid_auth_cannot_commit_or_run_a_terminal[missing]",
    "tests/test_package_a_safety_negatives.py::test_missing_or_invalid_auth_cannot_commit_or_run_a_terminal[invalid]",
    "tests/test_package_a_safety_negatives.py::test_unverified_isolation_cannot_fall_back_to_a_host_command",
    "tests/test_package_a_safety_negatives.py::test_authenticated_terminal_cannot_fall_back_to_a_host_command",
    "tests/test_package_a_safety_negatives.py::test_manifest_without_verified_isolation_does_not_run_a_host_command",
    "tests/test_package_a_safety_negatives.py::test_source_default_approval_key_cannot_record_an_approval",
    "tests/test_package_a_safety_negatives.py::test_source_default_quorum_key_cannot_approve_a_quorum",
    "tests/test_package_a_safety_negatives.py::test_source_default_billing_webhook_rejects_its_own_signature",
    "tests/test_package_a_safety_negatives.py::test_source_default_billing_webhook_rejects_an_unsigned_event",
    "tests/test_package_a_safety_negatives.py::test_source_default_entitlement_key_cannot_register_a_certificate",
    "tests/test_package_a_safety_negatives.py::test_source_default_entitlement_key_cannot_grant_features",
    "tests/test_package_a_safety_negatives.py::test_source_default_payment_secret_cannot_create_a_runnable_intent",
    "tests/test_package_a_safety_negatives.py::test_source_default_github_webhook_cannot_process_an_event",
)


def skip_unless_live_os_isolation() -> None:
    """Skip only when this machine cannot verify OS command confinement."""
    ok, detail = live_os_isolation_status()
    if ok:
        return
    pytest.skip(
        "Profile A: live-OS-isolation integration prerequisite absent: "
        f"Sandbox.verify() is false ({detail}). "
        "Release gate: this test must be run again and must pass where "
        "Sandbox.verify() succeeds (macOS seatbelt or Linux bubblewrap). "
        "A skip is not a pass and does not release."
    )
