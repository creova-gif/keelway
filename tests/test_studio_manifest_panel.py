"""Tests for KEEL-STUDIO-003: Agent Manifest Inspection API & Web Developer Studio Panel."""

from __future__ import annotations

import copy
import json
import re
import secrets
import subprocess
from pathlib import Path
from typing import Any, Dict

from fastapi.testclient import TestClient

from core.agents import manifest as am
from core.api import routes
from core.main import app
from core.storage.workspace_fs import WorkspaceFilesystem

KEELWAY_ROOT = Path(__file__).resolve().parent.parent
STUDIO_HTML = KEELWAY_ROOT / "core" / "studio" / "index.html"
STUDIO_JS = KEELWAY_ROOT / "core" / "studio" / "assets" / "studio.js"


def _sample_manifest(
    name: str = "sample-fixer",
    version: str = "0.1.0",
    **overrides: Any,
) -> Dict[str, Any]:
    base: Dict[str, Any] = {
        "schema": "keelway.agent/v1",
        "name": name,
        "version": version,
        "owner": "secops-team",
        "description": "Repairs failing unit tests within src/.",
        "instructions": "Run pytest, diagnose failure, propose minimal fix in src/.",
        "model": {"routing": "local_only", "preferred_provider": "local"},
        "tools": ["read_file", "edit_file", "run_command"],
        "permissions": {
            "autonomy": "confirm_mutation",
            "read_paths": ["src/**", "tests/**"],
            "write_paths": ["src/**"],
            "commands": ["pytest -q"],
            "network": "none",
        },
        "budget": {"max_usd_per_run": 0.75, "max_steps": 30},
        "sandbox": "worktree",
    }
    base.update(overrides)
    return base


def test_studio_manifests_discovers_workspace_and_registry_without_creating_signing_key(
    tmp_path: Path, monkeypatch
):
    """GET /v1/studio/manifests discovers workspace *.agent.json and DB registry manifests without mutating disk."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(routes, "_workspace_fs", WorkspaceFilesystem(root_dir=str(tmp_path)))

    # 1. Create workspace manifests in supported directories + decoys in .git and node_modules
    examples_dir = tmp_path / "docs" / "spec" / "examples"
    examples_dir.mkdir(parents=True)
    ws_manifest = _sample_manifest(name="ws-example", version="0.2.0")
    (examples_dir / "ws-example.agent.json").write_text(json.dumps(ws_manifest), encoding="utf-8")

    agents_dir = tmp_path / "agents" / "local-reviewer"
    agents_dir.mkdir(parents=True)
    reviewer = _sample_manifest(
        name="local-reviewer",
        version="1.0.0",
        tools=["read_file", "search_codebase"],
        permissions={
            "autonomy": "confirm_all",
            "read_paths": ["core/**"],
            "write_paths": [],
            "commands": [],
            "network": "none",
        },
    )
    (agents_dir / "local-reviewer.agent.json").write_text(json.dumps(reviewer), encoding="utf-8")

    # Ignored directories inside scan tree must never be traversed
    ignored_nm = tmp_path / "agents" / "node_modules" / "pkg"
    ignored_nm.mkdir(parents=True)
    (ignored_nm / "ignored-nm.agent.json").write_text(
        json.dumps(_sample_manifest(name="ignored-nm", version="0.0.1")), encoding="utf-8"
    )
    ignored_git = tmp_path / "agents" / ".git"
    ignored_git.mkdir(parents=True)
    (ignored_git / "ignored-git.agent.json").write_text(
        json.dumps(_sample_manifest(name="ignored-git", version="0.0.1")), encoding="utf-8"
    )

    unique_reg_name = f"reg-auditor-{secrets.token_hex(3)}"
    reg_manifest = _sample_manifest(name=unique_reg_name, version="1.2.3")

    with TestClient(app) as client:
        # Register a manifest into SQLite registry and disable its kill-switch
        reg_resp = client.post("/v1/agents/registry", json={"manifest": reg_manifest})
        assert reg_resp.status_code == 200, reg_resp.text

        toggle_resp = client.post(
            f"/v1/agents/registry/{unique_reg_name}/1.2.3/toggle",
            json={"enabled": False},
        )
        assert toggle_resp.status_code == 200
        assert toggle_resp.json()["enabled"] is False

        # Check /v1/studio/status includes additive manifests_count
        status_resp = client.get("/v1/studio/status")
        assert status_resp.status_code == 200
        status_data = status_resp.json()
        assert status_data["manifests_count"] >= 3

        # Discover manifests via Studio API
        resp = client.get("/v1/studio/manifests")
        assert resp.status_code == 200
        payload = resp.json()

    # Invariant: read-only status & discovery MUST NOT create .keelway/agent_signing.key
    assert not (tmp_path / ".keelway" / "agent_signing.key").exists()
    assert payload["signing_key_present"] is False

    by_key = {(m["source"], m["name"]): m for m in payload["manifests"]}
    assert ("workspace", "ws-example") in by_key
    assert ("workspace", "local-reviewer") in by_key
    assert ("registry", unique_reg_name) in by_key
    assert ("workspace", "ignored-nm") not in by_key
    assert ("workspace", "ignored-git") not in by_key

    ws_item = by_key[("workspace", "ws-example")]
    assert ws_item["id"] == "ws-example@0.2.0"
    assert ws_item["path"] == "docs/spec/examples/ws-example.agent.json"
    assert ws_item["enabled"] is True
    assert ws_item["signature_status"] == "unsigned"
    assert ws_item["digest"].startswith("sha256:")
    assert "Manifest is unsigned" in ws_item["security_warnings"]
    assert ws_item["governance_summary"] == {
        "routing": "local_only",
        "preferred_provider": "local",
        "autonomy": "confirm_mutation",
        "sandbox": "worktree",
        "network": "none",
        "network_allow": [],
        "max_usd_per_run": 0.75,
        "max_steps": 30,
        "tools": ["read_file", "edit_file", "run_command"],
        "mcp_servers": [],
        "read_paths": ["src/**", "tests/**"],
        "write_paths": ["src/**"],
        "commands": ["pytest -q"],
    }

    reg_item = by_key[("registry", unique_reg_name)]
    assert reg_item["id"] == f"{unique_reg_name}@1.2.3"
    assert reg_item["source"] == "registry"
    assert reg_item["path"] is None
    assert reg_item["enabled"] is False
    assert any("kill-switch" in w for w in reg_item["security_warnings"])


def test_studio_manifest_signature_states_and_zero_secret_key_leakage(tmp_path: Path, monkeypatch):
    """Verify unsigned, key_missing, verified, and invalid_signature states without leaking secret key material."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(routes, "_workspace_fs", WorkspaceFilesystem(root_dir=str(tmp_path)))

    raw = _sample_manifest(name="signed-agent", version="2.0.0")
    validated = am.validate(raw).manifest
    assert validated is not None

    # Create a signing key in a separate temporary buffer first to test key_missing before key exists in workspace
    ephemeral_key = secrets.token_bytes(32)
    ephemeral_hex = ephemeral_key.hex()
    signed_with_ephemeral = json.loads(am.to_json(am.sign(validated, ephemeral_key, signed_by="alice@keelway.io")))

    with TestClient(app) as client:
        # 1. Workspace has NO signing key yet -> key_missing (and must NOT create key file!)
        r_missing = client.post("/v1/studio/manifests/inspect", json={"manifest": signed_with_ephemeral})
        assert r_missing.status_code == 200
        d_missing = r_missing.json()
        assert d_missing["valid"] is True
        assert d_missing["signature_status"] == "key_missing"
        assert d_missing["signed_by"] == "alice@keelway.io"
        assert not (tmp_path / ".keelway" / "agent_signing.key").exists()

        # 2. Provision real workspace signing key (.keelway/agent_signing.key)
        ws_key = am.load_or_create_key(tmp_path)
        ws_key_hex = ws_key.hex()
        signed_manifest = am.sign(validated, ws_key, signed_by="security-lead@keelway.io")
        signed_dict = json.loads(am.to_json(signed_manifest))

        # Write verified + tampered files into workspace .keelway/manifests/
        manifests_dir = tmp_path / ".keelway" / "manifests"
        manifests_dir.mkdir(parents=True, exist_ok=True)
        (manifests_dir / "verified.agent.json").write_text(json.dumps(signed_dict), encoding="utf-8")

        tampered_content = copy.deepcopy(signed_dict)
        tampered_content["budget"]["max_steps"] = 250  # Tampered after signing!
        (manifests_dir / "tampered-content.agent.json").write_text(json.dumps(tampered_content), encoding="utf-8")

        tampered_mac = copy.deepcopy(signed_dict)
        tampered_mac["name"] = "signed-agent"
        tampered_mac["signature"]["value"] = "f" * 64
        (manifests_dir / "tampered-mac.agent.json").write_text(json.dumps(tampered_mac), encoding="utf-8")

        # Inspect verified manifest
        r_verified = client.post("/v1/studio/manifests/inspect", json={"manifest": signed_dict})
        assert r_verified.status_code == 200
        d_verified = r_verified.json()
        assert d_verified["valid"] is True
        assert d_verified["signature_status"] == "verified"
        assert d_verified["signed_by"] == "security-lead@keelway.io"
        assert d_verified["key_id"] == am.key_id(ws_key)
        assert ws_key_hex not in r_verified.text

        # Inspect tampered content manifest
        r_tampered = client.post("/v1/studio/manifests/inspect", json={"manifest": tampered_content})
        assert r_tampered.status_code == 200
        d_tampered = r_tampered.json()
        assert d_tampered["valid"] is True
        assert d_tampered["signature_status"] == "invalid_signature"
        assert d_tampered["signature_reason"] == "content_changed_since_signing"
        assert any("Invalid cryptographic signature" in w for w in d_tampered["security_warnings"])
        assert ws_key_hex not in r_tampered.text

        # Inspect manifest signed with wrong key
        r_wrong_key = client.post("/v1/studio/manifests/inspect", json={"manifest": signed_with_ephemeral})
        assert r_wrong_key.status_code == 200
        d_wrong_key = r_wrong_key.json()
        assert d_wrong_key["signature_status"] == "invalid_signature"
        assert d_wrong_key["signature_reason"] == "wrong_key"
        assert ws_key_hex not in r_wrong_key.text
        assert ephemeral_hex not in r_wrong_key.text

        # Verify workspace discovery endpoint reports verified & invalid_signature and never leaks key hex
        r_list = client.get("/v1/studio/manifests")
        assert r_list.status_code == 200
        assert ws_key_hex not in r_list.text
        list_data = r_list.json()
        assert list_data["signing_key_present"] is True
        by_path = {m["path"]: m for m in list_data["manifests"] if m["source"] == "workspace"}
        assert by_path[".keelway/manifests/verified.agent.json"]["signature_status"] == "verified"
        assert by_path[".keelway/manifests/tampered-content.agent.json"]["signature_status"] == "invalid_signature"
        assert by_path[".keelway/manifests/tampered-mac.agent.json"]["signature_status"] == "invalid_signature"


def test_studio_inspect_manifest_rejects_invalid_schemas_and_flags_security_warnings(
    tmp_path: Path, monkeypatch
):
    """POST /v1/studio/manifests/inspect catches unknown fields, path traversal, shell operators, and posture risks."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(routes, "_workspace_fs", WorkspaceFilesystem(root_dir=str(tmp_path)))

    with TestClient(app) as client:
        # 1. Unknown field rejected (extra="forbid")
        unknown_field_manifest = _sample_manifest()
        unknown_field_manifest["unexpected_backdoor"] = True
        r_extra = client.post("/v1/studio/manifests/inspect", json={"manifest": unknown_field_manifest})
        assert r_extra.status_code == 200
        d_extra = r_extra.json()
        assert d_extra["valid"] is False
        assert any("unexpected_backdoor" in err for err in d_extra["errors"])
        assert d_extra["digest"] is None

        # 2. Path traversal "../" and protected ".keelway/" rejected
        traversal_manifest = _sample_manifest()
        traversal_manifest["permissions"]["write_paths"] = ["../escape/**"]
        r_trav = client.post("/v1/studio/manifests/inspect", json={"manifest": traversal_manifest})
        assert r_trav.status_code == 200
        assert r_trav.json()["valid"] is False
        assert any("relative to the workspace" in err for err in r_trav.json()["errors"])

        protected_manifest = _sample_manifest()
        protected_manifest["permissions"]["read_paths"] = [".keelway/agent_signing.key"]
        r_prot = client.post("/v1/studio/manifests/inspect", json={"manifest": protected_manifest})
        assert r_prot.status_code == 200
        assert r_prot.json()["valid"] is False
        assert any("protected" in err for err in r_prot.json()["errors"])

        # 3. Shell metacharacter ";" rejected
        shell_meta_manifest = _sample_manifest()
        shell_meta_manifest["permissions"]["commands"] = ["pytest -q; cat /etc/passwd"]
        r_shell = client.post("/v1/studio/manifests/inspect", json={"manifest": shell_meta_manifest})
        assert r_shell.status_code == 200
        assert r_shell.json()["valid"] is False
        assert any("shell operators" in err for err in r_shell.json()["errors"])

        # 4. Malformed JSON string input handled cleanly without 500
        r_bad_json = client.post("/v1/studio/manifests/inspect", json={"manifest": "{not valid json"})
        assert r_bad_json.status_code == 200
        assert r_bad_json.json()["valid"] is False
        assert any("Invalid JSON" in err for err in r_bad_json.json()["errors"])

        # 5. Valid manifest with network="allowlist" + autonomous file mutation emits security warnings
        risky_manifest = _sample_manifest(
            name="autonomous-net-agent",
            permissions={
                "autonomy": "autonomous",
                "read_paths": ["src/**"],
                "write_paths": ["src/**"],
                "commands": ["pytest -q"],
                "network": "allowlist",
                "network_allow": ["api.github.com"],
            },
        )
        r_risky = client.post("/v1/studio/manifests/inspect", json={"manifest": risky_manifest})
        assert r_risky.status_code == 200
        d_risky = r_risky.json()
        assert d_risky["valid"] is True
        warnings_joined = " | ".join(d_risky["security_warnings"])
        assert "allowlist" in warnings_joined
        assert "network == 'none'" in warnings_joined or "network to 'none'" in warnings_joined
        assert "Autonomous file mutation enabled" in warnings_joined
        assert "Manifest is unsigned" in warnings_joined


def test_studio_html_has_manifest_inspector_landmarks_and_strict_csp():
    """Verify Studio HTML exposes the Manifest Inspector panel, validator drawer, and obeys CSP."""
    with TestClient(app) as client:
        resp = client.get("/studio")
        assert resp.status_code == 200
        html = resp.text

    expected_landmarks = (
        'id="rail-manifests-btn"',
        'data-section="manifests"',
        'id="sec-manifests"',
        'id="studio-manifests-panel"',
        'id="manifests-list"',
        'id="manifest-detail-pane"',
        'id="manifest-digest-value"',
        'id="manifest-autonomy-sandbox"',
        'id="manifest-security-warnings"',
        'id="manifest-canonical-json"',
        'id="manifest-validator-drawer"',
        'id="manifest-validator-input"',
        'id="manifest-validator-run-btn"',
        'Validate Custom Manifest JSON',
    )
    for landmark in expected_landmarks:
        assert landmark in html, f"Missing Studio landmark: {landmark}"

    # Extract #studio-manifests-panel block and verify zero inline onclick handlers
    panel_start = html.index('id="sec-manifests"')
    panel_end = html.index("<!-- SECONDARY DEVELOPER LABS DRAWER")
    manifests_section_html = html[panel_start:panel_end]
    assert not re.search(r"\bon\w+\s*=", manifests_section_html), (
        "Manifest Inspector HTML must not contain inline event handlers under strict script-src 'self' CSP"
    )


def test_studio_js_syntax_and_manifest_badge_helpers():
    """Verify studio.js passes `node --check` and exports accurate Manifest Inspector badge helpers."""
    syntax_check = subprocess.run(
        ["node", "--check", str(STUDIO_JS)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert syntax_check.returncode == 0, syntax_check.stderr

    eval_script = r"""
const fs = require('fs');
const studioPath = process.argv[1];
global.window = { __TEST_MODE__: true, addEventListener() {} };
global.localStorage = { getItem: () => null, setItem() {}, removeItem() {} };
global.navigator = { language: 'en' };
global.location = { search: '', hash: '', pathname: '/' };
global.history = { replaceState() {} };
global.document = {
  documentElement: { lang: 'en', dir: 'ltr', dataset: {} },
  getElementById: () => null,
  querySelector: () => null,
  querySelectorAll: () => [],
  createElement() { return { className: '', textContent: '', classList: { add() {}, remove() {} } }; },
  addEventListener() {},
};
const src = fs.readFileSync(studioPath, 'utf8');
new Function(src)();
const out = {
  verified: window.manifestSignatureBadgeSpec('verified').label,
  unsigned: window.manifestSignatureBadgeSpec('unsigned').label,
  invalid: window.manifestSignatureBadgeSpec('invalid_signature').label,
  keyMissing: window.manifestSignatureBadgeSpec('key_missing').label,
  ksOn: window.manifestKillSwitchBadgeSpec(true).label,
  ksOff: window.manifestKillSwitchBadgeSpec(false).label,
  routeLocal: window.manifestRoutingBadgeSpec('local_only').label,
};
process.stdout.write(JSON.stringify(out));
"""
    proc = subprocess.run(
        ["node", "-e", eval_script, str(STUDIO_JS)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    badges = json.loads(proc.stdout)
    assert badges == {
        "verified": "VERIFIED",
        "unsigned": "UNSIGNED",
        "invalid": "INVALID",
        "keyMissing": "KEY MISSING",
        "ksOn": "ENABLED",
        "ksOff": "DISABLED",
        "routeLocal": "local_only",
    }
