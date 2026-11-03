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


@pytest.fixture(autouse=True)
def _auth_disabled_unless_marked(request, monkeypatch):
    if request.node.get_closest_marker("auth") is None:
        monkeypatch.setattr(settings, "auth_required", False)

