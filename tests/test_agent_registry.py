import copy
import json
from pathlib import Path

import pytest

from core.agents import manifest as am
from core.agents.registry import ManifestDisabled, ManifestRegistry, ManifestVersionConflict

EXAMPLE = Path(__file__).resolve().parent.parent / "docs" / "spec" / "examples" / "test-fixer.agent.json"


def manifest(**changes):
    data = json.loads(EXAMPLE.read_text())
    data.update(changes)
    return am.validate(data).manifest


def test_registry_stores_immutable_versions_and_lists_metadata(tmp_path):
    registry = ManifestRegistry(tmp_path)
    first = registry.register(manifest(), "owner")
    assert first.enabled is True
    assert registry.get("test-fixer", "0.1.0").manifest.instructions == first.manifest.instructions
    assert registry.list()[0].summary()["digest"] == am.digest(first.manifest)
    assert (tmp_path / ".keelway" / "agent_registry.json").stat().st_mode & 0o077 == 0

    # Identical registration is idempotent; the same version cannot be silently replaced.
    again = registry.register(manifest(), "someone-else", enabled=False)
    assert again.created_by == "owner" and again.enabled is True
    changed = copy.deepcopy(manifest().model_dump(mode="json", by_alias=True))
    changed["instructions"] = "Different instructions"
    with pytest.raises(ManifestVersionConflict):
        registry.register(am.validate(changed).manifest, "owner")


def test_kill_switch_blocks_resolution_until_reenabled(tmp_path):
    registry = ManifestRegistry(tmp_path)
    registry.register(manifest(), "owner")
    assert registry.resolve("test-fixer", "0.1.0").enabled
    assert registry.set_enabled("test-fixer", "0.1.0", False).enabled is False
    with pytest.raises(ManifestDisabled):
        registry.resolve("test-fixer", "0.1.0")
    assert registry.set_enabled("test-fixer", "0.1.0", True).enabled is True
