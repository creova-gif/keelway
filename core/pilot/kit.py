"""
Keelway Customer Pilot Kit: Validation Tooling & Simulation Engine
Enables engineering teams to conduct hypothesis-driven workflow interviews
and run zero-risk pilot simulations on real multi-agent coordination problems.
"""

import hashlib
import json
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.orchestration.agent_loop import AutonomousAgentLoop, AutonomyPolicy
from core.orchestration.flight_recorder import FlightRecorder
from core.orchestration.self_healing import SelfHealingLoop
from core.storage.workspace_fs import WorkspaceFilesystem
from core.sync.bridge import ExternalEditorSyncBridge


@dataclass
class PilotCandidate:
    id: str
    name: str
    title: str
    organization: str
    observed_workflow: str
    wedge_capability: str
    interview_questions: List[str]
    commitment_ask: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


_PILOT_CANDIDATES: List[PilotCandidate] = [
    PilotCandidate(
        id="rigel_rootly",
        name="Rigel St. Pierre",
        title="Engineering Lead / Infrastructure",
        organization="Rootly",
        observed_workflow=(
            "Operating concurrent AI coding agents across shared developer tools, "
            "incident response automation, and fast-moving production repositories."
        ),
        wedge_capability=(
            "Dual-Mode Sovereign IDE with Pessimistic Pause & Prompt: preventing concurrent "
            "agent lease collisions and keeping external VS Code / Cursor workflows in sync."
        ),
        interview_questions=[
            "When your engineers run multiple coding agents concurrently, how do they prevent two agents from modifying the same files or creating merge conflicts?",
            "What happened the last time a developer made a manual edit in VS Code while an agent was actively writing a patch?",
            "How much engineering time per week is spent reviewing non-deterministic agent PRs or recovering broken worktrees?",
            "If an autonomous tool could pause immediately on conflicting external edits and prove exactly what changed via sealed audit tapes, would you test it on one non-critical service?",
        ],
        commitment_ask=(
            "A 30-minute side-by-side workflow test on a real non-critical service to measure "
            "whether Keelway's dual-mode sync bridge eliminates concurrent agent collisions."
        ),
    ),
    PilotCandidate(
        id="platform_lead_cursor",
        name="Enterprise Platform Lead",
        title="Staff Platform / Developer Experience Engineer",
        organization="Scale AI / Developer Tooling",
        observed_workflow=(
            "Supporting 50+ engineers using Cursor and Claude Code simultaneously, facing "
            "worktree fragmentation, lost edits, and unreviewed terminal execution."
        ),
        wedge_capability=(
            "Deterministic State Engine & Worktree Lease Management: single-binary coordination "
            "with zero cloud egress and strict human-in-the-loop approval gates."
        ),
        interview_questions=[
            "How do you currently audit or reproduce actions taken by local AI agents when an engineer's branch breaks CI?",
            "Do your security and compliance teams permit agent tools to execute arbitrary terminal commands without an immutable audit trail?",
            "Have you experienced silent data loss or stale cache bugs when switching between external IDEs and agent subagents?",
        ],
        commitment_ask=(
            "Deploying Keelway in developer mode across 3 engineers for 1 sprint to compare "
            "branch collision rates against their current manual workflow."
        ),
    ),
    PilotCandidate(
        id="fintech_security_architect",
        name="Sovereign Security Architect",
        title="Head of Information Security / Governance",
        organization="Fintech / HealthTech Core",
        observed_workflow=(
            "Strict zero-telemetry and air-gap requirements preventing cloud-hosted coding "
            "assistants from accessing proprietary intellectual property or customer data."
        ),
        wedge_capability=(
            "100% Local Inference & NIST SP 800-53 SC-7 Air-Gap Compliance with SHA-256 sealed "
            "cryptographic flight tapes and CycloneDX v1.5 SBOM provenance."
        ),
        interview_questions=[
            "What compliance controls currently block your engineering teams from adopting cloud AI coding tools like Devin or Claude Code?",
            "How do you prove to internal auditors that proprietary code never traversed an external LLM proxy or CDN?",
            "Would a local-first engine with cryptographically sealed flight tapes satisfy your internal compliance policies?",
        ],
        commitment_ask=(
            "Running `keelway doctor` and an air-gap verification audit in an isolated VPC or "
            "air-gapped environment to confirm zero outbound network egress."
        ),
    ),
    PilotCandidate(
        id="oss_maintainer_lead",
        name="Open Source Maintainer",
        title="Core Maintainer / Tech Lead",
        organization="High-Traffic Open Source Ecosystem",
        observed_workflow=(
            "Triage overload from low-quality AI-generated pull requests, broken unit tests, "
            "and subtle semantic bugs that pass naive linting."
        ),
        wedge_capability=(
            "KFlow DAG Orchestrator & Self-Healing Verification: requiring agents to prove patches "
            "against real test suites before submitting AST diffs."
        ),
        interview_questions=[
            "What percentage of incoming AI-authored PRs break edge-case tests or introduce regressions?",
            "How much time do you spend asking contributors to run tests and fix styling inconsistencies?",
            "Would you adopt a tool that automatically produces verifiable test execution receipts before allowing code proposals?",
        ],
        commitment_ask=(
            "Integrating Keelway's self-healing test verification into PR triage on a pilot repository."
        ),
    ),
    PilotCandidate(
        id="multi_agent_architect",
        name="AI Systems Architect",
        title="Lead AI Engineer / Agent Orchestrator",
        organization="Autonomous Engineering Lab",
        observed_workflow=(
            "Orchestrating teams of specialized agents (architect, coder, reviewer, security) "
            "struggling with prompt drift, circular delegations, and unbounded execution loops."
        ),
        wedge_capability=(
            "KStack Composable Role Skills & KFlow 12-State Deterministic Machine: bounded budgets, "
            "topological dependency execution, and cancelable transitions."
        ),
        interview_questions=[
            "How do you prevent multi-agent loops from burning infinite tokens or entering cyclic stalls?",
            "Can you deterministically replay an agent's failure step-by-step from an immutable recording?",
            "How do you enforce role separation between an architect agent that plans and a coder agent that writes?",
        ],
        commitment_ask=(
            "A benchmark run evaluating KFlow multi-agent task DAGs against their current unstructured agent framework."
        ),
    ),
]


def get_pilot_candidates() -> List[PilotCandidate]:
    """Returns the pre-configured target engineering lead personas."""
    return list(_PILOT_CANDIDATES)


def get_pilot_candidate(candidate_id: str) -> Optional[PilotCandidate]:
    """Retrieves a specific pilot candidate by ID."""
    for c in _PILOT_CANDIDATES:
        if c.id == candidate_id:
            return c
    return None


@dataclass
class PilotReceipt:
    receipt_id: str
    candidate_id: str
    candidate_name: str
    organization: str
    timestamp_iso: str
    workspace_path: str
    conflict_detected: bool
    conflict_resolution: str
    tests_passed: bool
    flight_tape_sha256: str
    receipt_sha256: str = ""

    def calculate_sha256(self) -> str:
        d = {
            "receipt_id": self.receipt_id,
            "candidate_id": self.candidate_id,
            "timestamp_iso": self.timestamp_iso,
            "conflict_detected": self.conflict_detected,
            "conflict_resolution": self.conflict_resolution,
            "tests_passed": self.tests_passed,
            "flight_tape_sha256": self.flight_tape_sha256,
        }
        serialized = json.dumps(d, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        if not self.receipt_sha256:
            data["receipt_sha256"] = self.calculate_sha256()
        return data


class PilotSimulationEngine:
    """
    Executes a realistic pilot simulation proving Keelway's primary wedge:
    1. Agent initiates a refactor on an incident router service.
    2. External developer mutates the file concurrently via VS Code / Cursor.
    3. Keelway triggers Pessimistic Pause & Prompt, records tape event, and prompts.
    4. Conflict is visually resolved and unit tests pass 100%.
    5. Sealed cryptographic pilot receipt is generated.
    """

    def __init__(self, workspace_dir: Path, candidate_id: str = "rigel_rootly"):
        self.workspace_dir = Path(workspace_dir).resolve()
        self.candidate = get_pilot_candidate(candidate_id) or _PILOT_CANDIDATES[0]
        self.task_id = f"pilot_{self.candidate.id}_{int(time.time())}"

    def setup_sandbox(self) -> None:
        """Sets up a realistic incident-router service with an automated test suite."""
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init"], cwd=self.workspace_dir, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Pilot Tester"], cwd=self.workspace_dir, check=True)
        subprocess.run(["git", "config", "user.email", "pilot@rootly.test"], cwd=self.workspace_dir, check=True)

        service_code = (
            "def calculate_sla_urgency(severity: int, minutes_open: int) -> int:\n"
            "    # Buggy multiplier returning raw sum instead of weighted factor\n"
            "    return severity + minutes_open\n"
        )
        test_code = (
            "from incident_router import calculate_sla_urgency\n\n"
            "def test_sla_urgency():\n"
            "    # Severity 1 incident open 10 mins should have urgency score 50 (severity * 50)\n"
            "    assert calculate_sla_urgency(1, 10) == 50\n"
        )
        (self.workspace_dir / "incident_router.py").write_text(service_code, encoding="utf-8")
        (self.workspace_dir / "test_incident.py").write_text(test_code, encoding="utf-8")

        subprocess.run(["git", "add", "."], cwd=self.workspace_dir, check=True)
        subprocess.run(["git", "commit", "-m", "initial incident service"], cwd=self.workspace_dir, check=True)

    async def run_simulation(self) -> PilotReceipt:
        """Executes the complete pilot workflow simulation."""
        self.setup_sandbox()

        fs = WorkspaceFilesystem(root_dir=str(self.workspace_dir))
        flight_dir = self.workspace_dir / ".keelway" / "recordings"
        recorder = FlightRecorder(task_id=self.task_id, recordings_dir=flight_dir)
        bridge = ExternalEditorSyncBridge(workspace_root=self.workspace_dir, debounce_ms=10)

        agent = AutonomousAgentLoop(
            task_id=self.task_id,
            workspace_fs=fs,
            policy=AutonomyPolicy.CONFIRM_MUTATION,
            flight_recorder=recorder,
        )

        # Stage 1: Agent starts plan and acquires lease
        agent.initialize_plan("Fix urgency score calculation in calculate_sla_urgency")
        base_content = fs.read_file("incident_router.py")["content"]
        agent_proposed = (
            "def calculate_sla_urgency(severity: int, minutes_open: int) -> int:\n"
            "    return severity * 50\n"
        )
        bridge.acquire_file_lease(
            file_path="incident_router.py",
            agent_id=self.task_id,
            base_content=base_content,
            agent_content=agent_proposed,
        )

        # Stage 2: External developer makes concurrent edit in VS Code / Cursor
        external_content = (
            "def calculate_sla_urgency(severity: int, minutes_open: int) -> int:\n"
            "    # Human hotfix in VS Code: severity multiplier\n"
            "    return severity * 50\n"
        )
        (self.workspace_dir / "incident_router.py").write_text(external_content, encoding="utf-8")
        time.sleep(0.02)  # past 10ms debounce

        # Stage 3: Sync bridge detects concurrent mutation -> triggers Pessimistic Pause
        conflict = bridge.notify_external_change(file_path="incident_router.py", external_content=external_content)
        conflict_detected = conflict is not None

        if conflict:
            recorder.record_concurrent_mutation(
                file_path=conflict.file_path,
                external_content=conflict.external_content,
                agent_content=conflict.agent_content,
                base_content=conflict.base_content,
            )

        # Stage 4: Developer reviews & resolves conflict in favor of verified edit
        resolve_res = bridge.resolve_conflict(file_path="incident_router.py", resolution="keep_external")

        # Stage 5: Execute test suite to confirm zero regressions
        healer = SelfHealingLoop(repo_root=self.workspace_dir)
        test_rc, test_out, _ = await healer.execute_test("pytest -q test_incident.py", cwd=self.workspace_dir)
        tests_passed = (test_rc == 0)

        # Stage 6: Seal flight recorder tape
        recorder.save_tape()
        sealed_recorder = recorder.seal_tape()

        now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        receipt = PilotReceipt(
            receipt_id=f"rcpt_{self.task_id}",
            candidate_id=self.candidate.id,
            candidate_name=self.candidate.name,
            organization=self.candidate.organization,
            timestamp_iso=now_iso,
            workspace_path=str(self.workspace_dir),
            conflict_detected=conflict_detected,
            conflict_resolution=resolve_res.get("resolution", "keep_external"),
            tests_passed=tests_passed,
            flight_tape_sha256=sealed_recorder.tape_sha256,
        )
        receipt.receipt_sha256 = receipt.calculate_sha256()

        receipt_file = self.workspace_dir / ".keelway" / "pilot_receipt.json"
        receipt_file.parent.mkdir(parents=True, exist_ok=True)
        receipt_file.write_text(json.dumps(receipt.to_dict(), indent=2), encoding="utf-8")

        return receipt
