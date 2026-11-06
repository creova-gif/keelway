"""Profile A checks that the live-proof inventory stays explicit.

These tests do not run the live proofs and they do not count as release
verification.
"""

from tests import test_agent_sandbox as sandbox_tests
from tests.package_a_profile import (
    REQUIRED_SAFETY_NEGATIVES,
    SEATBELT_CONFINEMENT_PROOFS,
)


def test_seatbelt_inventory_is_marked_separately_from_bubblewrap():
    assert len(SEATBELT_CONFINEMENT_PROOFS) == 13
    assert len(set(SEATBELT_CONFINEMENT_PROOFS)) == 13
    for nodeid in SEATBELT_CONFINEMENT_PROOFS:
        name = nodeid.split("::", 1)[1]
        fn = getattr(sandbox_tests, name)
        marks = getattr(fn, "pytestmark", [])
        if not isinstance(marks, list):
            marks = [marks]
        names = {mark.name for mark in marks}
        assert "live_seatbelt" in names
        reasons = [mark.kwargs.get("reason", "") for mark in marks if mark.name == "skipif"]
        assert any("macOS seatbelt only" in reason for reason in reasons)


def test_required_safety_negatives_are_enumerated():
    assert len(REQUIRED_SAFETY_NEGATIVES) == 22
    assert len(set(REQUIRED_SAFETY_NEGATIVES)) == 22
    assert all(nodeid.startswith("tests/test_package_a_safety_negatives.py::") for nodeid in REQUIRED_SAFETY_NEGATIVES)
