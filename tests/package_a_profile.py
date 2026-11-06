"""Profile A prerequisite checks. Owned by foundation-repair package A.

The default suite is Profile A: it must stay hermetic on a Linux runner that
has no reachable local model and no verified OS confinement. A confinement
binary that fails ``Sandbox.verify()`` is not enough. The live integrations
stay in the tree. Profile A skips one only when its own prerequisite is
absent, and the skip message is the reason. A skip is not a pass.

Release gate, separate from Profile A: those integrations must be executed
and must pass on a host that actually has the prerequisite.

- Live model: ``LocalAdapter.is_available()`` is true for
  ``http://localhost:11434`` and ``qwen3.5:latest``.
  ``pytest -v -m live_model`` passes only when that model answers.
- Live OS isolation: macOS ``sandbox-exec`` (seatbelt) or Linux ``bwrap``
  (bubblewrap) is present, and ``Sandbox.verify()`` succeeds.
  ``pytest -v -m live_os_isolation`` passes only on that host.

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
