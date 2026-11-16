import asyncio
import os
import tempfile
import pytest

# Ensure tests default to an isolated test database in a writable directory
if "DATABASE_URL" not in os.environ:
    _test_db = os.path.join(tempfile.gettempdir(), "keelway_test.db")
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_test_db}"

from core.config import settings


def pytest_configure(config):
    config.addinivalue_line("markers", "auth: run with API token auth enforced (disabled by default in tests)")
    config.addinivalue_line(
        "markers",
        "live_model: genuine local-model integration; Profile A skips only when that model is absent",
    )
    config.addinivalue_line(
        "markers",
        "live_os_isolation: genuine OS-isolation integration; Profile A skips only when Sandbox.verify() is false",
    )
    config.addinivalue_line(
        "markers",
        "live_seatbelt: macOS seatbelt confinement proof; bubblewrap does not satisfy it",
    )
    config.addinivalue_line(
        "markers",
        "safety_negative: mandatory Profile A fail-closed check; never skip, xfail, or deselect",
    )


_SAFETY_VIOLATIONS: list[str] = []


def _full_profile_a_run(config) -> bool:
    """The applicable Profile A check is a full suite run, not a single-file debug invocation."""
    args = [arg for arg in config.args if not str(arg).startswith("-")]
    return not args or args in (["tests"], ["tests/"])


def pytest_deselected(items):
    if not items or not _full_profile_a_run(items[0].config):
        return
    for item in items:
        if item.get_closest_marker("safety_negative") is not None:
            _SAFETY_VIOLATIONS.append(f"deselected {item.nodeid}")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if item.get_closest_marker("safety_negative") is None:
        return
    if not _full_profile_a_run(item.config):
        return
    if report.when not in ("setup", "call"):
        return
    kind = None
    if getattr(report, "wasxfail", False):
        kind = "xfail"
    elif report.skipped:
        kind = "skipped"
    if kind is None:
        return
    entry = f"{kind} {item.nodeid}"
    if entry not in _SAFETY_VIOLATIONS:
        _SAFETY_VIOLATIONS.append(entry)


def pytest_sessionfinish(session, exitstatus):
    if not _full_profile_a_run(session.config):
        return
    from tests.package_a_profile import REQUIRED_SAFETY_NEGATIVES

    collected = {item.nodeid for item in session.items}
    missing = [nodeid for nodeid in REQUIRED_SAFETY_NEGATIVES if nodeid not in collected]
    violations = [f"missing {nodeid}" for nodeid in missing] + list(_SAFETY_VIOLATIONS)
    if not violations:
        return
    session.exitstatus = 1
    reporter = session.config.pluginmanager.get_plugin("terminalreporter")
    if reporter is not None:
        reporter.write_sep("!", "safety_negative checks were skipped, xfailed, deselected, or not collected")
        for line in violations:
            reporter.write_line(line)


@pytest.fixture(scope="session", autouse=True)
def _ensure_test_db_schema():
    """Ensure SQLAlchemy tables (including kora_audit_events) exist on fresh CI SQLite files."""
    from core.storage.database import init_db

    asyncio.run(init_db())


@pytest.fixture(autouse=True)
def _auth_disabled_unless_marked(request, monkeypatch):
    if request.node.get_closest_marker("auth") is None:
        monkeypatch.setattr(settings, "auth_required", False)
