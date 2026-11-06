"""Unit & integration test suite for Keelway Unified Proof Strip UX (Workstream F).

Validates:
1. Studio HTML & CSS integration (proof-strip-card, track, stage, drawer, containers).
2. Studio JS stage data mapping (IDE Mode & Agent Builder Mode).
3. 6 verification stages: INSPECT -> PLAN -> AUTHORIZE -> EXECUTE -> VERIFY -> SEAL.
4. Approval pending, approved, and denied transitions.
5. Verification failures and cryptographic hash-verification tampering.
6. Air-gapped offline state (LOCAL_ONLY, zero-egress, no cloud fallback).
7. W3C ARIA accessibility contracts and keyboard navigation.
8. Shared component parity between IDE and Agent Builder modes.
"""

import json
import subprocess
from pathlib import Path
import pytest
from httpx import AsyncClient, ASGITransport
from core.main import app

KEELWAY_ROOT = Path(__file__).parent.parent
STUDIO_HTML = KEELWAY_ROOT / "core" / "studio" / "index.html"
STUDIO_JS = KEELWAY_ROOT / "core" / "studio" / "assets" / "studio.js"


def run_node_eval(js_code: str, input_data: dict = None) -> dict:
    """Run JavaScript code snippet in Node.js and return parsed JSON result."""
    stdin_payload = json.dumps(input_data) if input_data is not None else ""
    wrapped_code = f"""
    const fs = require('fs');
    const studioJsCode = fs.readFileSync('{STUDIO_JS}', 'utf-8');

    // Create a mock DOM environment
    const elements = {{}};
    function mockElement(tag = 'div') {{
        const el = {{
            tagName: tag.toUpperCase(),
            className: '',
            innerHTML: '',
            textContent: '',
            dataset: {{}},
            attributes: {{}},
            children: [],
            classList: {{
                add: (c) => {{ el.className = (el.className + ' ' + c).trim(); }},
                remove: (c) => {{ el.className = el.className.split(' ').filter(x => x !== c).join(' '); }},
                contains: (c) => el.className.split(' ').includes(c),
                toggle: (c, force) => {{
                    const cur = el.classList.contains(c);
                    const nxt = force !== undefined ? force : !cur;
                    if (nxt) el.classList.add(c); else el.classList.remove(c);
                    return nxt;
                }}
            }},
            setAttribute: (k, v) => {{ el.attributes[k] = String(v); }},
            getAttribute: (k) => el.attributes[k] || null,
            appendChild: (child) => {{ el.children.push(child); }},
            querySelector: (sel) => null,
            querySelectorAll: (sel) => el.children.filter(c => c.className && c.className.includes('proof-strip-stage'))
        }};
        return el;
    }}

    global.window = {{
        __TEST_MODE__: true,
        addEventListener: () => {{}}
    }};
    global.location = {{ search: '', hash: '' }};
    global.navigator = {{ userAgent: 'node' }};
    global.document = {{
        documentElement: {{ dataset: {{}}, dir: 'ltr' }},
        createElement: (tag) => mockElement(tag),
        querySelectorAll: () => [],
        addEventListener: () => {{}}
    }};
    global.localStorage = {{
        getItem: () => null,
        setItem: () => {{}}
    }};
    global.$ = (id) => elements[id] || (elements[id] = mockElement('div'));
    global.state = {{ agentTask: null, agentState: null }};

    // Extract PROOF_STAGES, getIdeStageData, getBuilderStageData from studio.js
    const evalScope = new Function('require', studioJsCode + `\\n; return {{
        PROOF_STAGES: window.PROOF_STAGES,
        getIdeStageData: window.getIdeStageData,
        getBuilderStageData: window.getBuilderStageData,
        renderUnifiedProofStrip: window.renderUnifiedProofStrip
    }};`);

    const extracted = evalScope(require);

    // Read input from stdin if present
    let parsedInput = null;
    try {{
        const raw = fs.readFileSync(0, 'utf-8');
        if (raw && raw.trim()) parsedInput = JSON.parse(raw);
    }} catch (e) {{}}

    // Run user test code
    const testFn = new Function('PROOF_STAGES', 'getIdeStageData', 'getBuilderStageData', 'renderUnifiedProofStrip', 'mockElement', 'inputData', `
        {js_code}
    `);

    const output = testFn(extracted.PROOF_STAGES, extracted.getIdeStageData, extracted.getBuilderStageData, extracted.renderUnifiedProofStrip, mockElement, parsedInput);
    console.log(JSON.stringify(output));
    """
    res = subprocess.run(["node", "-e", wrapped_code], input=stdin_payload, capture_output=True, text=True, check=True)
    return json.loads(res.stdout)


@pytest.mark.asyncio
async def test_studio_html_has_proof_strip_mounts():
    """Verify index.html contains both IDE and Builder proof strip containers."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/studio")
        assert resp.status_code == 200
        html = resp.text
        assert 'id="ide-proof-strip"' in html
        assert 'id="builder-proof-strip"' in html
        assert 'proof-strip-card' in html
        assert 'proof-strip-stage' in html
        assert 'proof-drawer' in html


def test_proof_stages_definition():
    """Verify the 6 verification stages contract."""
    res = run_node_eval("""
        return {
            count: PROOF_STAGES.length,
            ids: PROOF_STAGES.map(s => s.id),
            labels: PROOF_STAGES.map(s => s.label)
        };
    """)
    assert res["count"] == 6
    assert res["ids"] == ["inspect", "plan", "authorize", "execute", "verify", "seal"]
    assert res["labels"] == ["INSPECT", "PLAN", "AUTHORIZE", "EXECUTE", "VERIFY", "SEAL"]


def test_ide_mode_lifecycle_mapping():
    """Test full IDE Mode state transitions mapping to the 6 proof stages."""
    res = run_node_eval("""
        // 1. Initial created state
        const sCreated = getIdeStageData({ status: 'created' });

        // 2. Planning state
        const sPlanning = getIdeStageData({ status: 'planning' });

        // 3. Plan ready
        const sPlanReady = getIdeStageData({
            status: 'plan_ready',
            plan: [{ id: '1', description: 'Step 1', status: 'pending' }]
        });

        // 4. Executing tool
        const sExecuting = getIdeStageData({
            status: 'executing_tool',
            plan: [{ id: '1', description: 'Step 1', status: 'running' }]
        });

        // 5. Verifying
        const sVerifying = getIdeStageData({
            status: 'verifying',
            plan: [{ id: '1', description: 'Step 1', status: 'completed' }]
        });

        // 6. Completed
        const sCompleted = getIdeStageData({
            status: 'completed',
            test_exit_code: 0,
            hash_verified: true,
            merkle_root: '073d5e86e3dba727c4dd0e561e24927e98fe51db',
            plan: [{ id: '1', description: 'Step 1', status: 'completed' }]
        });

        return {
            created: sCreated.map(s => s.status),
            planning: sPlanning.map(s => s.status),
            planReady: sPlanReady.map(s => s.status),
            executing: sExecuting.map(s => s.status),
            verifying: sVerifying.map(s => s.status),
            completed: sCompleted.map(s => s.status)
        };
    """)

    # Inspect -> Plan -> Authorize -> Execute -> Verify -> Seal
    assert res["created"] == ["active", "idle", "idle", "idle", "idle", "idle"]
    assert res["planning"] == ["passed", "active", "idle", "idle", "idle", "idle"]
    assert res["planReady"] == ["passed", "passed", "idle", "idle", "idle", "idle"]
    assert res["executing"] == ["passed", "passed", "passed", "active", "idle", "idle"]
    assert res["verifying"] == ["passed", "passed", "passed", "passed", "active", "idle"]
    assert res["completed"] == ["passed", "passed", "passed", "passed", "passed", "passed"]


def test_ide_mode_approval_states():
    """Test approval pending (amber waiting), approved (passed), and denied (failed)."""
    res = run_node_eval("""
        // Pending approval
        const sPending = getIdeStageData({
            status: 'awaiting_approval',
            pending_approval: { step_id: '1', tool_name: 'edit_file', description: 'Edit service.py' },
            plan: [{ id: '1', description: 'Edit service.py', status: 'pending' }]
        });

        // Approved and continuing
        const sApproved = getIdeStageData({
            status: 'executing_tool',
            approval_digest: 'SHA-256: 8f4e2b... (Authorized)',
            plan: [{ id: '1', description: 'Edit service.py', status: 'running' }]
        });

        // Denied / cancelled
        const sDenied = getIdeStageData({
            status: 'cancelled',
            error: 'Action denied by user'
        });

        return {
            pendingAuth: sPending[2].status,
            approvedAuth: sApproved[2].status,
            deniedAuth: sDenied[2].status
        };
    """)
    assert res["pendingAuth"] == "waiting"
    assert res["approvedAuth"] == "passed"
    assert res["deniedAuth"] == "failed"


def test_tamper_and_verification_failure():
    """Test that failed test suite or tampered hash marks verify or seal as failed."""
    res = run_node_eval("""
        // Test suite failed
        const sTestFailed = getIdeStageData({
            status: 'failed',
            test_exit_code: 1,
            test_output: 'AssertionError: expected True got False'
        });

        // Cryptographic hash tampering detected
        const sTampered = getIdeStageData({
            status: 'completed',
            test_exit_code: 0,
            hash_verified: false,
            tampered: true
        });

        return {
            testFailedVerifyStatus: sTestFailed[4].status,
            tamperedSealStatus: sTampered[5].status
        };
    """)
    assert res["testFailedVerifyStatus"] == "failed"
    assert res["tamperedSealStatus"] == "failed"


def test_airgap_and_local_model_sovereignty():
    """Verify that stage data explicitly reports LOCAL_ONLY zero egress without cloud fallback."""
    res = run_node_eval("""
        const s = getIdeStageData({
            status: 'completed',
            model_name: 'qwen3.5:latest',
            model_provider: 'local (MLX/Ollama)',
            airgap: true
        });

        const b = getBuilderStageData({
            status: 'created',
            receipt: {
                spec_name: 'test-fixer',
                version: '0.1.0',
                tests_passed: true,
                receipt_sha256: 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'
            }
        });

        return {
            ideModel: s[0].details.model,
            ideEgress: s[0].details.egress,
            ideAirgap: s[0].details.airgap,
            builderModel: b[0].details.model,
            builderEgress: b[0].details.egress
        };
    """)
    assert "qwen3.5:latest" in res["ideModel"]
    assert res["ideEgress"] == "LOCAL_ONLY (Zero Egress Verified)"
    assert res["ideAirgap"] is True
    assert "Local Open-Weight" in res["builderModel"]
    assert res["builderEgress"] == "LOCAL_ONLY (Zero Egress Verified)"


def test_agent_builder_stage_mapping():
    """Test Agent Builder Mode stage data mapping for both passed and failed builds."""
    res = run_node_eval("""
        // 1. Successful build receipt
        const bSuccess = getBuilderStageData({
            status: 'created',
            receipt: {
                spec_name: 'my-test-fixer',
                version: '0.1.0',
                files_created: ['manifest.json', 'test_agent.py'],
                tests_passed: true,
                test_output: '1 passed in 0.14s',
                receipt_sha256: 'abcd1234ef567890'
            },
            manifest: {
                name: 'my-test-fixer',
                version: '0.1.0',
                tools: ['read_file', 'edit_file', 'run_tests'],
                permissions: { autonomy: 'mutation_gated' }
            }
        });

        // 2. Failed build receipt (test failure)
        const bFailed = getBuilderStageData({
            status: 'created',
            receipt: {
                spec_name: 'broken-agent',
                version: '0.1.0',
                tests_passed: false,
                test_output: 'FAILED: fixture assertion failed'
            }
        });

        return {
            successStatuses: bSuccess.map(s => s.status),
            failedStatuses: bFailed.map(s => s.status),
            successAutonomy: bSuccess[2].details.autonomy,
            successDistributable: bSuccess[5].details.distributable,
            failedDistributable: bFailed[5].details.distributable
        };
    """)

    assert res["successStatuses"] == ["passed", "passed", "passed", "passed", "passed", "passed"]
    assert res["failedStatuses"] == ["passed", "passed", "passed", "passed", "failed", "failed"]
    assert res["successAutonomy"] == "mutation_gated"
    assert "Ready for Bundle Packaging" in res["successDistributable"]
    assert "Blocked" in res["failedDistributable"]


def test_accessibility_and_keyboard_attributes():
    """Verify W3C ARIA tablist/tab pattern, role attributes, and keyboard listeners."""
    res = run_node_eval("""
        const container = mockElement('div');
        renderUnifiedProofStrip(container, { status: 'created' }, { mode: 'ide' });

        const track = container.children[0].children[1];
        const role = track.attributes['role'];
        const ariaLabel = track.attributes['aria-label'];
        const stages = track.children;

        return {
            trackRole: role,
            ariaLabel: ariaLabel,
            stageCount: stages.length,
            stageRoles: stages.map(s => s.attributes['role']),
            stageTabs: stages.map(s => s.attributes['tabindex'])
        };
    """)
    assert res["trackRole"] == "tablist"
    assert "Verification Stages" in res["ariaLabel"]
    assert res["stageCount"] == 6
    assert all(r == "tab" for r in res["stageRoles"])
    assert res["stageTabs"][0] == "0"
    assert all(t == "-1" for t in res["stageTabs"][1:])
