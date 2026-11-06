"""Executable release boundary for live model and live OS-isolation proofs.

Profile A may skip these tests. This command does not. Exit 0 only when
every required node passed on this machine. A skip or a missing prerequisite
is UNAVAILABLE/UNRUN and a non-zero exit. A green Profile A run is not this
result.

Exit 0: every required proof passed.
Exit 1: a required proof failed, or the inventory did not collect.
Exit 2: UNAVAILABLE/UNRUN. A prerequisite is absent or a required proof skipped.

Bubblewrap does not satisfy the macOS seatbelt proofs.
"""

from __future__ import annotations

import sys

import pytest

from core.agents.sandbox import SeatbeltBackend
from core.models.adapters.local import LocalAdapter
from tests.package_a_profile import (
    LIVE_MODEL_NAME,
    LIVE_MODEL_PROOFS,
    LIVE_MODEL_URL,
    LIVE_OS_ISOLATION_PROOFS,
    SEATBELT_CONFINEMENT_PROOFS,
    live_os_isolation_status,
)


class _Outcomes:
    def __init__(self) -> None:
        self.status: dict[str, str] = {}

    def pytest_runtest_logreport(self, report) -> None:
        if report.when == "setup" and report.skipped:
            self.status[report.nodeid] = "skipped"
        elif report.when == "call":
            if getattr(report, "wasxfail", False) or report.skipped:
                self.status[report.nodeid] = "skipped"
            elif report.failed:
                self.status[report.nodeid] = "failed"
            elif report.passed:
                self.status.setdefault(report.nodeid, "passed")


def main() -> int:
    blocked: list[str] = []
    adapter = LocalAdapter(base_url=LIVE_MODEL_URL, default_model=LIVE_MODEL_NAME)
    if not adapter.is_available():
        blocked.append(
            f"live model UNAVAILABLE: LocalAdapter.is_available() is false for {LIVE_MODEL_URL} ({LIVE_MODEL_NAME})"
        )
    verified, detail = live_os_isolation_status()
    if not verified:
        blocked.append(f"verified OS isolation UNAVAILABLE: Sandbox.verify() is false ({detail})")
    if not SeatbeltBackend.available():
        blocked.append(
            "seatbelt proofs UNAVAILABLE: SeatbeltBackend.available() is false. "
            "These thirteen proofs need macOS sandbox-exec. Bubblewrap does not prove them."
        )

    required = LIVE_MODEL_PROOFS + LIVE_OS_ISOLATION_PROOFS + SEATBELT_CONFINEMENT_PROOFS
    outcomes = _Outcomes()
    pytest.main(
        [*required, "-p", "no:cacheprovider", "-q", "--tb=line"],
        plugins=[outcomes],
    )
    missing = [nodeid for nodeid in required if nodeid not in outcomes.status]
    skipped = [nodeid for nodeid, status in outcomes.status.items() if status == "skipped"]
    failed = [nodeid for nodeid, status in outcomes.status.items() if status == "failed"]
    passed = [nodeid for nodeid, status in outcomes.status.items() if status == "passed"]

    print("release live verification")
    print(f"required={len(required)} passed={len(passed)} failed={len(failed)} skipped={len(skipped)} missing={len(missing)}")
    for note in blocked:
        print(f"UNAVAILABLE/UNRUN: {note}")
    for nodeid in missing:
        print(f"UNAVAILABLE/UNRUN: not collected {nodeid}")
    for nodeid in skipped:
        print(f"UNAVAILABLE/UNRUN: skipped {nodeid}")
    for nodeid in failed:
        print(f"FAILED: {nodeid}")

    if failed or missing:
        print("release live verification FAILED")
        return 1
    if blocked or skipped:
        print("release live verification UNAVAILABLE/UNRUN")
        return 2
    if len(passed) != len(required):
        print("release live verification FAILED: not every required proof passed")
        return 1
    print("release live verification passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
