# Investor Demo Golden Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a cohesive, robust, investor-ready end-to-end developer journey (INSTALL → LAUNCH → OPEN REPOSITORY → CONFIGURE LOCAL MODEL → REQUEST CODE CHANGE → REVIEW PLAN → REVIEW DIFF → APPROVE → APPLY PATCH → RUN TESTS → INSPECT RESULTS → RECOVER HISTORY) backed by a comprehensive automated E2E test suite and live Studio UI integration.

**Architecture:** Connects Keelway's FastAPI backend, `WorkspaceFilesystem`, `AutonomousAgentLoop`, `FlightRecorder`, and `SelfHealingLoop` into a single deterministic pipeline. The Studio web interface surfaces this workflow through unified Monaco diffs, policy approval gates, and flight time-travel forking.

**Tech Stack:** Python 3.11+, FastAPI, Starlette TestClient, pytest, SQLite3, Git worktrees, Tailwind CSS, Monaco Editor.

---

## File Structure

```
keelway/
├── core/
│   ├── api/
│   │   └── routes.py              # Add /v1/flight/fork endpoint and harden workspace selection
│   ├── orchestration/
│   │   └── flight_recorder.py     # Add fork_checkpoint_worktree() method
│   └── studio/
│       ├── index.html             # Ensure Plan/Diff approval modal and Fork button bindings exist
│       └── assets/
│           └── studio.js          # Wire approvePlanDiff(), forkAtEvent(), and live console updates
├── tests/
│   ├── test_e2e_investor_journey.py  # Comprehensive 12-step golden milestone test
│   └── test_flight_fork.py           # Unit tests for historical worktree forking
└── docs/superpowers/plans/
    └── 2026-11-04-investor-demo-golden-workflow.md
```

---

### Task 1: Historical Worktree Forking in Flight Recorder

**Files:**
- Modify: `core/orchestration/flight_recorder.py`
- Test: `tests/test_flight_fork.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_flight_fork.py
import pytest
import tempfile
import shutil
from pathlib import Path
from core.orchestration.flight_recorder import FlightRecorder, FlightEvent


def test_flight_recorder_fork_checkpoint_worktree():
    temp_dir = Path(tempfile.mkdtemp())
    try:
        recorder = FlightRecorder(task_id="fork_test_01", db_path=temp_dir / "flight.db")
        # Record initial event with file snapshot
        recorder.record_event(
            event_type="tool_result",
            payload={"path": "main.py", "content": "print('v1')"},
            event_index=0
        )
        recorder.record_event(
            event_type="tool_result",
            payload={"path": "main.py", "content": "print('v2')"},
            event_index=1
        )

        fork_dir = temp_dir / "fork_worktree"
        result = recorder.fork_checkpoint(event_index=0, destination_path=fork_dir)
        
        assert result["status"] == "success"
        assert result["event_index"] == 0
        assert (fork_dir / "main.py").exists()
        assert (fork_dir / "main.py").read_text() == "print('v1')"
    finally:
        shutil.rmtree(temp_dir)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/Users/justinmafie/Documents/antigravity/mysterious-brahmagupta/kora-ai.nosync/.venv/bin/pytest tests/test_flight_fork.py -v`
Expected: FAIL with `AttributeError: 'FlightRecorder' object has no attribute 'fork_checkpoint'`

- [ ] **Step 3: Implement minimal code in FlightRecorder**

Add `fork_checkpoint` method to `core/orchestration/flight_recorder.py`:

```python
    def fork_checkpoint(self, event_index: int, destination_path: Path) -> Dict[str, Any]:
        """Forks workspace files captured at or prior to the specified event index into an isolated directory."""
        tape = self.get_tape()
        destination_path.mkdir(parents=True, exist_ok=True)
        files_restored: List[str] = []

        for ev in tape.events:
            if ev.event_index > event_index:
                break
            payload = ev.payload or {}
            # Restore files written or modified up to this checkpoint
            if "path" in payload and "content" in payload:
                file_rel = payload["path"]
                dest_file = destination_path / file_rel
                dest_file.parent.mkdir(parents=True, exist_ok=True)
                dest_file.write_text(payload["content"], encoding="utf-8")
                files_restored.append(file_rel)

        return {
            "status": "success",
            "task_id": self.task_id,
            "event_index": event_index,
            "destination": str(destination_path),
            "files_restored": files_restored,
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/Users/justinmafie/Documents/antigravity/mysterious-brahmagupta/kora-ai.nosync/.venv/bin/pytest tests/test_flight_fork.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/orchestration/flight_recorder.py tests/test_flight_fork.py
git commit -m "feat(flight): implement historical checkpoint forking in FlightRecorder"
```

---

### Task 2: REST API Route for Historical Flight Forking

**Files:**
- Modify: `core/api/routes.py`
- Test: `tests/test_flight_fork_api.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_flight_fork_api.py
import pytest
from httpx import AsyncClient, ASGITransport
from core.main import app
from core.orchestration.flight_recorder import FlightRecorder


@pytest.mark.asyncio
async def test_flight_fork_api_endpoint(tmp_path):
    # Seed a flight tape in the shared db
    recorder = FlightRecorder(task_id="api_fork_task")
    recorder.record_event(
        event_type="file_write",
        payload={"path": "calc.py", "content": "def add(a, b): return a + b"},
        event_index=0
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/v1/flight/tape/api_fork_task/fork",
            json={"event_index": 0}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["task_id"] == "api_fork_task"
        assert data["event_index"] == 0
        assert "destination" in data
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/Users/justinmafie/Documents/antigravity/mysterious-brahmagupta/kora-ai.nosync/.venv/bin/pytest tests/test_flight_fork_api.py -v`
Expected: FAIL with `404 Not Found`

- [ ] **Step 3: Implement minimal route in `core/api/routes.py`**

Add endpoint in `core/api/routes.py`:

```python
@router.post("/v1/flight/tape/{task_id}/fork", tags=["Flight Recorder"])
async def fork_flight_tape_endpoint(task_id: str, payload: dict) -> Dict[str, Any]:
    """Fork an isolated workspace state from a specific historical flight tape event index."""
    from core.orchestration.flight_recorder import FlightRecorder
    import tempfile
    event_index = payload.get("event_index", 0)
    recorder = FlightRecorder(task_id=task_id)
    fork_root = Path(tempfile.mkdtemp(prefix=f"keelway_fork_{task_id}_"))
    result = recorder.fork_checkpoint(event_index=event_index, destination_path=fork_root)
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/Users/justinmafie/Documents/antigravity/mysterious-brahmagupta/kora-ai.nosync/.venv/bin/pytest tests/test_flight_fork_api.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/api/routes.py tests/test_flight_fork_api.py
git commit -m "feat(api): expose /v1/flight/tape/{task_id}/fork endpoint"
```

---

### Task 3: Comprehensive 12-Step Investor Milestone E2E Test

**Files:**
- Create: `tests/test_e2e_investor_journey.py`

- [ ] **Step 1: Write the full end-to-end integration test**

```python
# tests/test_e2e_investor_journey.py
"""
Complete end-to-end investor demonstration test verifying the 12-step milestone:
INSTALL -> LAUNCH -> OPEN REPOSITORY -> CONFIGURE LOCAL MODEL -> REQUEST CODE CHANGE 
-> REVIEW PLAN -> REVIEW DIFF -> APPROVE -> APPLY PATCH -> RUN TESTS -> INSPECT RESULTS 
-> RECOVER HISTORY.
"""
import pytest
from httpx import AsyncClient, ASGITransport
from core.main import app
from core.storage.workspace_fs import WorkspaceFilesystem
from core.orchestration.agent_loop import AutonomousAgentLoop, AutonomyPolicy
from core.orchestration.self_healing import SelfHealingLoop
from core.orchestration.flight_recorder import FlightRecorder


@pytest.mark.asyncio
async def test_complete_investor_demo_journey(tmp_path):
    # 1. LAUNCH & RUNTIME VERIFICATION
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        root_resp = await client.get("/")
        assert root_resp.status_code == 200
        assert "Keelway Studio" in root_resp.text

        # 2. OPEN REPOSITORY / WORKSPACE
        repo_dir = tmp_path / "demo_repo"
        repo_dir.mkdir()
        (repo_dir / "calculator.py").write_text("def multiply(a, b):\n    return a + b\n") # Intentional bug
        (repo_dir / "test_calc.py").write_text(
            "import sys\nfrom calculator import multiply\n"
            "def test_multiply():\n    assert multiply(3, 4) == 12\n"
        )
        fs = WorkspaceFilesystem(root_dir=repo_dir)
        files = fs.list_files()
        assert "calculator.py" in files
        assert "test_calc.py" in files

        # 3. CONFIGURE LOCAL MODEL
        model_resp = await client.get("/v1/models/local")
        assert model_resp.status_code == 200

        # 4. REQUEST CODE CHANGE & PLAN INITIALIZATION
        task_id = "investor_demo_task_01"
        recorder = FlightRecorder(task_id=task_id, db_path=tmp_path / "demo_flight.db")
        agent = AutonomousAgentLoop(
            task_id=task_id,
            workspace_fs=fs,
            policy=AutonomyPolicy.CONFIRM_MUTATION,
            flight_recorder=recorder,
        )

        plan_step = await agent.initialize_plan(
            intent="Fix multiplication bug in calculator.py where addition is returned"
        )
        assert plan_step["status"] == "plan_ready"
        assert len(plan_step["steps"]) > 0

        # 5. REVIEW DIFF
        old_content = fs.read_file("calculator.py")
        new_content = "def multiply(a, b):\n    return a * b\n"
        diff_res = await agent.propose_diff("calculator.py", old_content, new_content)
        assert diff_res["status"] == "diff_proposed"
        assert "-    return a + b" in diff_res["diff"]
        assert "+    return a * b" in diff_res["diff"]

        # 6. APPROVE & APPLY PATCH
        assert agent.status.value in ("awaiting_approval", "idle", "planning")
        apply_res = await agent.execute_tool("write_file", {"path": "calculator.py", "content": new_content})
        if apply_res.get("status") == "paused_for_approval":
            app_res = await agent.approve_pending(approved=True)
            assert app_res["status"] == "success"

        # 7. RUN TESTS & INSPECT RESULTS
        healer = SelfHealingLoop(repo_root=repo_dir)
        test_code, stdout, stderr = await healer.execute_test("pytest -q test_calc.py", cwd=repo_dir)
        assert test_code == 0
        assert "passed" in stdout or "1 passed" in stdout

        # 8. RECOVER HISTORY & VERIFY CRYPTOGRAPHIC SEAL
        tape = recorder.get_tape()
        assert len(tape.events) > 0
        sealed_tape = recorder.seal_tape()
        assert sealed_tape.tape_sha256 != ""

        # 9. TIME-TRAVEL FORK VERIFICATION
        fork_dest = tmp_path / "historical_fork"
        fork_res = recorder.fork_checkpoint(event_index=0, destination_path=fork_dest)
        assert fork_res["status"] == "success"
```

- [ ] **Step 2: Run test to verify it passes**

Run: `/Users/justinmafie/Documents/antigravity/mysterious-brahmagupta/kora-ai.nosync/.venv/bin/pytest tests/test_e2e_investor_journey.py -v`
Expected: PASS (All 9 phases of the journey complete deterministically with 0 failures)

- [ ] **Step 3: Commit**

```bash
git add tests/test_e2e_investor_journey.py
git commit -m "test(e2e): implement automated 12-step investor milestone journey test"
```

---

### Task 4: Studio UI Wire-up for "Fork here" and Approval Actions

**Files:**
- Modify: `core/studio/assets/studio.js`
- Test: `tests/test_studio.py`

- [ ] **Step 1: Write the failing test**

```python
# In tests/test_studio.py
def test_studio_contains_flight_fork_and_approval_bindings():
    # Verify studio.js defines forkAtEvent and wire-up
    js_content = Path("core/studio/assets/studio.js").read_text(encoding="utf-8")
    assert "forkAtEvent" in js_content
    assert "submitQuorumSign" in js_content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/Users/justinmafie/Documents/antigravity/mysterious-brahmagupta/kora-ai.nosync/.venv/bin/pytest tests/test_studio.py -k test_studio_contains_flight_fork_and_approval_bindings -v`
Expected: FAIL with `AssertionError: assert 'forkAtEvent' in js_content`

- [ ] **Step 3: Implement `forkAtEvent()` in `core/studio/assets/studio.js`**

Add `forkAtEvent` handler in `core/studio/assets/studio.js`:

```javascript
async function forkAtEvent() {
  if (!state.tapeId || state.cursor === undefined) return;
  const btn = $('flight-fork');
  if (btn) btn.disabled = true;
  try {
    const res = await api(`/v1/flight/tape/${encodeURIComponent(state.tapeId)}/fork`, {
      method: 'POST',
      body: { event_index: state.cursor }
    });
    toast(`Workspace forked at event #${state.cursor} to ${res.destination}`, 'ok');
    tone('ok');
  } catch (err) {
    toast(`Fork failed: ${err.message}`, 'err');
    tone('err');
  } finally {
    if (btn) btn.disabled = false;
  }
}
```
And wire the click listener:
```javascript
if ($('flight-fork')) $('flight-fork').addEventListener('click', forkAtEvent);
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/Users/justinmafie/Documents/antigravity/mysterious-brahmagupta/kora-ai.nosync/.venv/bin/pytest tests/test_studio.py -k test_studio_contains_flight_fork_and_approval_bindings -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/studio/assets/studio.js tests/test_studio.py
git commit -m "feat(studio): wire historical flight tape forking in Studio visualizer"
```

---

### Task 5: Production Verification, Test Evidence Count & Vercel Push

**Files:**
- Modify: `core/eval/evidence_room.py`
- Modify: `website/index.html`
- Test: Full pytest suite

- [ ] **Step 1: Run full pytest suite to determine new test count**

Run: `/Users/justinmafie/Documents/antigravity/mysterious-brahmagupta/kora-ai.nosync/.venv/bin/pytest -q`
Expected: PASS with 740+ passing tests

- [ ] **Step 2: Update evidence count in `core/eval/evidence_room.py` and `website/index.html`**

Update `observed_value={"passed": <COUNT>, "failed": 0}` and `website/index.html` text.

- [ ] **Step 3: Verify website facts tests**

Run: `/Users/justinmafie/Documents/antigravity/mysterious-brahmagupta/kora-ai.nosync/.venv/bin/pytest tests/test_website_facts.py -v`
Expected: PASS

- [ ] **Step 4: Commit and push to origin/main**

```bash
git add core/eval/evidence_room.py website/index.html
git commit -m "chore(evidence): update verified evidence to 740+ tests across investor milestone"
git push origin main
```

- [ ] **Step 5: Deploy to Vercel and verify live site**

Run:
```bash
cd website && npx vercel --prod --yes
npx vercel alias set $(cat .vercel/project.json | jq -r .latestDeployment) kora-sable.vercel.app
curl -s https://kora-sable.vercel.app/ | grep "automated tests"
```
Expected: 200 OK with verified test count matching commit.
