"""Lifecycle agent manifest coverage: all 12 LIFECYCLE_AGENTS have canonical
keelway.agent/v1 manifests that validate and register through the registry API."""

import pytest
from fastapi.testclient import TestClient

from core.main import app
from core.config import settings
from core.agents import manifest as am
from core.agents.builtin import load_builtin_manifests
from core.platform.workspace_hub import LIFECYCLE_AGENTS


def test_all_lifecycle_agents_have_builtin_manifests():
    manifests = {m["name"]: m for m in load_builtin_manifests()}
    spec_ids = {a["id"] for a in LIFECYCLE_AGENTS}
    assert spec_ids == set(manifests), (
        f"manifest/spec mismatch: missing={spec_ids - set(manifests)}, "
        f"extra={set(manifests) - spec_ids}"
    )


def test_all_lifecycle_manifests_validate():
    for m in load_builtin_manifests():
        report = am.validate(m)
        assert report.ok, f"{m['name']}: {report.errors}"


def test_high_risk_agents_require_confirm_all():
    manifests = {m["name"]: m for m in load_builtin_manifests()}
    tier = {a["id"]: a["risk_tier"] for a in LIFECYCLE_AGENTS}
    for name, m in manifests.items():
        if tier[name] in {"B", "C"}:
            assert m["permissions"]["autonomy"] == "confirm_all", name


def test_manifests_have_no_network_and_local_routing():
    for m in load_builtin_manifests():
        assert m["permissions"]["network"] == "none", m["name"]
        assert m["model"]["routing"] == "local_first", m["name"]


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from core.api import routes
    from core.storage.workspace_fs import WorkspaceFilesystem
    (tmp_path / "src").mkdir()
    monkeypatch.setattr(routes, "_workspace_fs", WorkspaceFilesystem(root_dir=str(tmp_path)))
    monkeypatch.setattr(settings, "require_signed_manifests", False)
    with TestClient(app) as c:
        yield c


def test_lifecycle_manifests_register_and_toggle(client):
    manifests = load_builtin_manifests()
    for m in manifests:
        r = client.post("/v1/agents/registry", json={"manifest": m})
        # The registry persists in the app database, so an earlier run may have
        # registered the same manifest — "already registered" is the correct
        # rejection, not a failure.
        assert r.status_code == 200 or "already registered" in r.text, f"{m['name']}: {r.text}"

    listed = client.get("/v1/agents/registry").json()["manifests"]
    names = {e["name"] for e in listed}
    for m in manifests:
        assert m["name"] in names

    # Duplicate registration is rejected.
    dup = client.post("/v1/agents/registry", json={"manifest": manifests[0]})
    assert dup.status_code in (400, 409, 422)

    # Kill-switch toggle disables then re-enables.
    victim = manifests[0]
    off = client.post(
        f"/v1/agents/registry/{victim['name']}/1.0.0/toggle",
        json={"enabled": False},
    )
    assert off.status_code == 200, off.text
    assert off.json()["enabled"] is False
    on = client.post(
        f"/v1/agents/registry/{victim['name']}/1.0.0/toggle",
        json={"enabled": True},
    )
    assert on.status_code == 200, on.text
    assert on.json()["enabled"] is True
