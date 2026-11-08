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
            value: '',
            dataset: {{}},
            attributes: {{}},
            children: [],
            offsetWidth: 10,
            offsetHeight: 10,
            getClientRects: () => [{{ width: 10, height: 10 }}],
            contains: (child) => true,
            focus: () => {{ global.document.activeElement = el; }},
            scrollIntoView: () => {{}},
            append: (...c) => {{ el.children.push(...c); }},
            replaceChildren: (...c) => {{ el.children = c; }},
            addEventListener: () => {{}},
            removeEventListener: () => {{}},
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
            querySelector: (sel) => {{
                if (sel.startsWith('#')) {{
                    const id = sel.slice(1);
                    return el.children.find(c => (c.attributes && c.attributes['id'] === id) || c.id === id) || null;
                }}
                return null;
            }},
            querySelectorAll: (sel) => el.children.filter(c => c.className && c.className.includes('proof-strip-stage'))
        }};
        return el;
    }}

    global.Node = class Node {{}};
    global.window = {{
        __TEST_MODE__: true,
        addEventListener: () => {{}}
    }};
    global.location = {{ search: '', hash: '' }};
    global.navigator = {{ userAgent: 'node' }};
    const mockBody = mockElement('body');
    global.document = {{
        documentElement: {{ dataset: {{}}, dir: 'ltr' }},
        activeElement: null,
        body: mockBody,
        getElementById: (id) => elements[id] || (elements[id] = mockElement('div')),
        createElement: (tag) => mockElement(tag),
        createTextNode: (t) => t,
        querySelectorAll: () => [],
        addEventListener: () => {{}}
    }};
    global.localStorage = {{
        getItem: () => null,
        setItem: () => {{}}
    }};
    global.$ = (id) => global.document.getElementById(id);
    global.state = {{ agentTask: null, agentState: null }};

    // Extract PROOF_STAGES, getIdeStageData, getBuilderStageData from studio.js
    const evalScope = new Function('require', studioJsCode + `\\n; return {{
        PROOF_STAGES: window.PROOF_STAGES,
        getIdeStageData: window.getIdeStageData,
        getBuilderStageData: window.getBuilderStageData,
        renderUnifiedProofStrip: window.renderUnifiedProofStrip,
        openPalette: window.openPalette,
        closePalette: window.closePalette,
        paletteKey: window.paletteKey,
        toggleLabsDrawer: window.toggleLabsDrawer,
        trapFocus: window.trapFocus
    }};`);

    const extracted = evalScope(require);

    // Read input from stdin if present
    let parsedInput = null;
    try {{
        const raw = fs.readFileSync(0, 'utf-8');
        if (raw && raw.trim()) parsedInput = JSON.parse(raw);
    }} catch (e) {{}}

    // Run user test code
    const testFn = new Function('PROOF_STAGES', 'getIdeStageData', 'getBuilderStageData', 'renderUnifiedProofStrip', 'mockElement', 'inputData', 'helpers', `
        {js_code}
    `);

    const output = testFn(extracted.PROOF_STAGES, extracted.getIdeStageData, extracted.getBuilderStageData, extracted.renderUnifiedProofStrip, mockElement, parsedInput, extracted);
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
    # Changed expectation: a status name is not inspection, authorization, test, or seal evidence.
    assert res["created"] == ["active", "not_run", "not_run", "not_run", "not_run", "not_run"]
    assert res["planning"] == ["not_run", "active", "not_run", "not_run", "not_run", "not_run"]
    assert res["planReady"] == ["not_run", "passed", "not_run", "not_run", "not_run", "not_run"]
    assert res["executing"] == ["not_run", "passed", "not_run", "active", "not_run", "not_run"]
    assert res["verifying"] == ["not_run", "passed", "not_run", "passed", "active", "not_run"]
    assert res["completed"] == ["not_run", "passed", "not_run", "passed", "passed", "passed"]


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
    assert "Verified" not in res["ideEgress"]
    assert res["ideAirgap"] is True
    assert res["builderModel"] == "Not reported"
    assert res["builderEgress"] == "Not checked"


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

    # Inspect and authorize stay not_run: a scaffold receipt is not an egress check or an approval.
    assert res["successStatuses"] == ["not_run", "passed", "not_run", "passed", "passed", "passed"]
    assert res["failedStatuses"] == ["not_run", "passed", "not_run", "not_run", "failed", "failed"]
    assert res["successAutonomy"] == "mutation_gated"
    assert "Receipt recorded" in res["successDistributable"]
    assert res["failedDistributable"] == "Not sealed"


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


def test_proof_strip_arrow_navigation_and_tab_sync():
    """Verify arrow navigation advances tabs, updates tabindex, aria-selected, and opens drawer."""
    res = run_node_eval("""
        const container = mockElement('div');
        renderUnifiedProofStrip(container, { status: 'created' }, { mode: 'ide' });

        const track = container.children[0].children[1];
        const drawer = container.children[0].children[2];
        const stages = track.children;

        const initialTabs = stages.map(s => s.attributes['tabindex']);
        const initialSelected = stages.map(s => s.attributes['aria-selected']);

        // Navigate forward with ArrowRight
        let prevented = false;
        stages[0].onkeydown({ key: 'ArrowRight', preventDefault: () => { prevented = true; } });
        const afterRightTabs = stages.map(s => s.attributes['tabindex']);
        const afterRightSelected = stages.map(s => s.attributes['aria-selected']);

        // Navigate backward with ArrowLeft
        stages[1].onkeydown({ key: 'ArrowLeft', preventDefault: () => {} });
        const afterLeftTabs = stages.map(s => s.attributes['tabindex']);

        // Navigate to End
        stages[0].onkeydown({ key: 'End', preventDefault: () => {} });
        const afterEndTabs = stages.map(s => s.attributes['tabindex']);

        // Navigate to Home
        stages[5].onkeydown({ key: 'Home', preventDefault: () => {} });
        const afterHomeTabs = stages.map(s => s.attributes['tabindex']);

        // Escape closes drawer
        stages[0].onkeydown({ key: 'Escape', preventDefault: () => {} });
        const drawerClosed = drawer.className.includes('hidden');

        return {
            trackId: track.attributes['id'] || track.id,
            prevented,
            initialTabs,
            initialSelected,
            afterRightTabs,
            afterRightSelected,
            afterLeftTabs,
            afterEndTabs,
            afterHomeTabs,
            drawerClosed
        };
    """)
    assert res["trackId"] == "proof-strip"
    assert res["prevented"] is True
    assert res["initialTabs"] == ["0", "-1", "-1", "-1", "-1", "-1"]
    assert res["afterRightTabs"] == ["-1", "0", "-1", "-1", "-1", "-1"]
    assert res["afterRightSelected"] == ["false", "true", "false", "false", "false", "false"]
    assert res["afterLeftTabs"] == ["0", "-1", "-1", "-1", "-1", "-1"]
    assert res["afterEndTabs"] == ["-1", "-1", "-1", "-1", "-1", "0"]
    assert res["afterHomeTabs"] == ["0", "-1", "-1", "-1", "-1", "-1"]
    assert res["drawerClosed"] is True


def test_command_palette_accessibility_and_dismiss():
    """Verify Command Palette keyboard navigation, focus trapping, and Esc dismissal."""
    html = STUDIO_HTML.read_text(encoding="utf-8")
    assert 'id="palette"' in html
    idx = html.index('id="palette"')
    snippet = html[idx:idx + 250]
    assert 'role="dialog"' in snippet
    assert 'aria-modal="true"' in snippet

    res = run_node_eval("""
        const pal = $('palette');
        const input = $('palette-input');

        const triggerButton = mockElement('button');
        triggerButton.id = 'palette-trigger-btn';
        global.document.activeElement = triggerButton;

        // Open palette
        helpers.openPalette();
        const isOpen = !pal.className.includes('hidden');
        const inputFocused = (global.document.activeElement === input);
        const ariaHiddenOpen = pal.attributes['aria-hidden'];

        // Arrow down
        let preventedDown = false;
        helpers.paletteKey({ key: 'ArrowDown', preventDefault: () => { preventedDown = true; } });

        // Escape closes and restores focus
        let preventedEsc = false;
        helpers.paletteKey({ key: 'Escape', preventDefault: () => { preventedEsc = true; }, stopPropagation: () => {} });
        const isClosedAfterEsc = pal.className.includes('hidden');
        const ariaHiddenClosed = pal.attributes['aria-hidden'];
        const focusRestored = (global.document.activeElement === triggerButton);

        return {
            isOpen,
            inputFocused,
            ariaHiddenOpen,
            preventedDown,
            preventedEsc,
            isClosedAfterEsc,
            ariaHiddenClosed,
            focusRestored
        };
    """)
    assert res["isOpen"] is True
    assert res["inputFocused"] is True
    assert res["ariaHiddenOpen"] == "false"
    assert res["preventedDown"] is True
    assert res["preventedEsc"] is True
    assert res["isClosedAfterEsc"] is True
    assert res["ariaHiddenClosed"] == "true"
    assert res["focusRestored"] is True


def test_modal_dialogs_aria_modal_and_focus_trap():
    """Verify all modal dialogs have aria-modal='true' and focus trap cleanly wraps Tab."""
    html = STUDIO_HTML.read_text(encoding="utf-8")
    assert 'id="palette"' in html
    assert 'id="labs-drawer"' in html
    assert 'id="signin"' in html
    assert 'id="onboard"' in html
    assert 'id="always-form"' in html

    for modal_id in ['id="palette"', 'id="labs-drawer"', 'id="signin"', 'id="onboard"', 'id="always-form"']:
        idx = html.index(modal_id)
        snippet = html[idx:idx + 350]
        assert 'aria-modal="true"' in snippet, f"{modal_id} missing aria-modal='true'"

    res = run_node_eval("""
        const container = mockElement('div');
        const btn1 = mockElement('button');
        const btn2 = mockElement('button');
        const btn3 = mockElement('button');
        container.children = [btn1, btn2, btn3];
        container.querySelectorAll = () => [btn1, btn2, btn3];

        // 1. Tab forward from last element wraps to first
        global.document.activeElement = btn3;
        let prevented1 = false;
        helpers.trapFocus(container, { key: 'Tab', shiftKey: false, preventDefault: () => { prevented1 = true; } });
        const wrappedToFirst = (global.document.activeElement === btn1);

        // 2. Shift+Tab backward from first element wraps to last
        global.document.activeElement = btn1;
        let prevented2 = false;
        helpers.trapFocus(container, { key: 'Tab', shiftKey: true, preventDefault: () => { prevented2 = true; } });
        const wrappedToLast = (global.document.activeElement === btn3);

        return {
            prevented1,
            wrappedToFirst,
            prevented2,
            wrappedToLast
        };
    """)
    assert res["prevented1"] is True
    assert res["wrappedToFirst"] is True
    assert res["prevented2"] is True
    assert res["wrappedToLast"] is True


def test_focus_visible_design_tokens():
    """Verify :focus-visible rules match Keelway's accent token and prevent outline cutoff."""
    html = STUDIO_HTML.read_text(encoding="utf-8")
    assert ":focus-visible" in html
    assert "rgb(var(--accent))" in html
    assert "outline-offset: -1px" in html or "outline-offset: -2px" in html
    assert ".proof-strip-stage:focus-visible" in html
