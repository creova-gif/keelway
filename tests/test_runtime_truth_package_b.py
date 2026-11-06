"""Focused regression checks for foundation repair package B.

These tests exercise the four runtime paths in this package: evidence claims,
Studio benchmark and keyword-planner labels, mesh dispatch, and chat provider
failures. They do not certify the product.
"""

import json
import subprocess
from pathlib import Path

import pytest

from core.eval.evidence_room import EvidenceRoomPipeline
from core.orchestration.mesh import AgentMeshDispatcher

KEELWAY_ROOT = Path(__file__).parent.parent
STUDIO_JS = KEELWAY_ROOT / "core" / "studio" / "assets" / "studio.js"
EVIDENCE_PY = KEELWAY_ROOT / "core" / "eval" / "evidence_room.py"
MESH_PY = KEELWAY_ROOT / "core" / "orchestration" / "mesh.py"
CHAT_PY = KEELWAY_ROOT / "core" / "orchestration" / "chat.py"


def _node_studio(expression: str):
    """Evaluate one expression against the Studio helpers loaded in test mode."""
    script = r"""
const fs = require('fs');
const studioPath = process.argv[1];
const expression = process.argv[2];
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
const studio = fs.readFileSync(studioPath, 'utf8');
const loaded = new Function(studio + '\n; return {' +
  'KEYWORD_PLANNER_LABEL: window.KEYWORD_PLANNER_LABEL,' +
  'speculativeViewNotRun: window.speculativeViewNotRun,' +
  'speculativeViewFromFailure: window.speculativeViewFromFailure,' +
  'speculativeViewFromResponse: window.speculativeViewFromResponse,' +
  'evidenceMetricMark: window.evidenceMetricMark,' +
  'classifyComposerResult: window.classifyComposerResult' +
'};')();
const value = Function('api', 'return (' + expression + ');')(loaded);
process.stdout.write(JSON.stringify(value));
"""
    completed = subprocess.run(
        ["node", "-e", script, str(STUDIO_JS), expression],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)


def test_package_b_sources_do_not_keep_the_fabricated_claims():
    evidence = EVIDENCE_PY.read_text(encoding="utf-8")
    mesh = MESH_PY.read_text(encoding="utf-8")
    chat = CHAT_PY.read_text(encoding="utf-8")
    studio = STUDIO_JS.read_text(encoding="utf-8")

    assert "745" not in evidence
    assert "is_verified=True" not in evidence
    assert "100% Pass@1" not in evidence
    assert '"APPROVED"' not in mesh
    assert "tests_passed\": True" not in mesh
    assert "test_count\": 40" not in mesh
    for banned in (
        "keelway-offline-engine",
        "keelway-offline-planner",
        "keelway-offline-patcher",
        "latency_ms = 2.0",
        "pricing.py",
        "No conflicting dependencies found",
    ):
        assert banned not in chat
    for banned in ("mockStream", "2.74", "81.3", "148.5", "63.5", "x VERIFIED", "Evidence verified 100%"):
        assert banned not in studio
    assert "Keyword/manual planned-tool path" in studio


def test_studio_benchmark_helpers_do_not_invent_metrics():
    missing = _node_studio("api.speculativeViewFromResponse({})")
    assert missing["verified"] is False
    assert missing["badge"] == "NOT VERIFIED"
    assert missing["speedup"] is None
    assert missing["acceptancePct"] is None
    assert missing["proposed"] is None
    assert missing["accepted"] is None
    assert missing["latencySaved"] is None
    assert missing["latencyPct"] is None
    assert missing["tokenStream"] is None
    assert "synthetic" in missing["notice"].lower() or "no token stream" in missing["notice"].lower()

    failure = _node_studio("api.speculativeViewFromFailure()")
    assert failure["badge"] == "ERROR"
    assert failure["verified"] is False
    assert failure["speedup"] is None
    assert failure["tokenStream"] is None
    assert "no metrics were measured" in failure["notice"].lower()

    not_run = _node_studio("api.speculativeViewNotRun()")
    assert not_run["badge"] == "NOT RUN"
    assert not_run["speedup"] is None

    reported = _node_studio(
        "api.speculativeViewFromResponse({ speculative_result: { effective_speedup_ratio: 1.25, acceptance_rate: 0.5, draft_tokens_proposed: 4, draft_tokens_accepted: 2, token_stream: [{ token: 'x', status: 'accepted', step: 0, draft_index: 0 }] }, latency_reduction_pct: 10 })"
    )
    assert reported["speedup"] == 1.25
    assert reported["acceptancePct"] == 50
    assert reported["proposed"] == 4
    assert reported["accepted"] == 2
    assert reported["verified"] is False
    assert reported["badge"] == "NOT VERIFIED"
    assert reported["tokenStream"][0]["token"] == "x"
    assert "not marked as measured" in reported["notice"].lower()


def test_studio_labels_keyword_plans_and_model_failures():
    label = _node_studio("api.KEYWORD_PLANNER_LABEL")
    assert "keyword/manual" in label.lower()
    assert "not model-driven" in label.lower()

    agent = _node_studio("api.classifyComposerResult('agent', { task_id: 'task_real' })")
    assert agent["keywordManual"] is True
    assert agent["allowServerStep"] is True
    assert agent["toastKind"] == "warn"
    assert agent["label"] == label

    unavailable = _node_studio(
        "api.classifyComposerResult('plan', { status: 'unavailable', available: false, structured_plan: { planning_source: 'keyword_manual', steps: ['a'] } })"
    )
    assert unavailable["unavailable"] is True
    assert unavailable["keywordManual"] is True
    assert unavailable["allowServerStep"] is False
    assert unavailable["toastKind"] == "err"

    model_plan = _node_studio(
        "api.classifyComposerResult('ask', { status: 'ok', available: true, model: 'local-model', latency_ms: 12 })"
    )
    assert model_plan["unavailable"] is False
    assert model_plan["keywordManual"] is False

    not_run = _node_studio("api.evidenceMetricMark({ is_verified: false, observed_value: { status: 'not_run' } })")
    assert not_run == {"mark": "NOT RUN", "verified": False}
    verified = _node_studio("api.evidenceMetricMark({ is_verified: true, observed_value: { status: 'executed' } })")
    assert verified["mark"] == "VERIFIED"
    failed = _node_studio("api.evidenceMetricMark({ is_verified: false, observed_value: { status: 'executed' } })")
    assert failed["mark"] == "UNVERIFIED"


@pytest.mark.asyncio
async def test_mesh_dispatch_does_not_report_executed_success():
    result = await AgentMeshDispatcher().dispatch_task("Review the patch", ["core/orchestration/mesh.py"])
    assert result["consensus"] == "NOT_EXECUTED"
    assert result["pipeline"]["security"]["dlp_clean"] is None
    assert result["pipeline"]["verification"]["tests_passed"] is None
    assert result["independently_approved"] is False


def test_evidence_room_leaves_unrun_checks_unverified():
    pkg = EvidenceRoomPipeline.assemble_package(repo_root=KEELWAY_ROOT)
    by_name = {metric["name"]: metric for metric in pkg.metrics}
    for name in (
        "Automated Pytest Suite",
        "Standalone Reference Core Engine",
        "Milestone M1 Developer Workflow",
        "Tier 2 Hardware Security HAL",
        "Sovereign Pre-Flight System Doctor",
        "Cross-Machine Sovereign Sync Engine",
    ):
        metric = by_name[name]
        assert metric["is_verified"] is False
        assert metric["observed_value"]["status"] == "not_run"
        assert metric["observed_value"]["count"] is None
    airgap = by_name["NIST SP 800-53 SC-7 Air-Gap Audit"]
    assert airgap["is_verified"] is False
    assert airgap["observed_value"]["status"] in {"executed", "error"}
    sbom = by_name["CycloneDX SBOM & Provenance"]
    assert sbom["is_verified"] is False
    if sbom["observed_value"]["status"] == "executed":
        assert isinstance(sbom["observed_value"]["components"], int)
        assert "independent release verification" in sbom["claim"]
    assert pkg.summary["all_verified"] is False
    assert "745" not in json.dumps(pkg.to_dict())
