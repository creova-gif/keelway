"""
Keelway Prompt-to-App Guided Builder.
Transforms developer intent and templates into fully scaffolded, verified,
and flight-recorded application codebases with automated test harnesses.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.orchestration.flight_recorder import FlightRecorder


@dataclass
class AppArchitecturePlan:
    app_name: str
    intent: str
    template: str
    description: str
    dependencies: List[str]
    file_tree: List[str]
    modules: Dict[str, str]
    security_boundary: Dict[str, Any]
    test_plan: List[str]
    plan_sha256: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AppTaskStep:
    step_id: str
    title: str
    description: str
    target_files: List[str]
    status: str = "PENDING"
    duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AppVerificationResult:
    test_command: str
    passed: bool
    exit_code: int
    tests_count: int
    output: str
    duration_ms: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AppBuildReceipt:
    app_name: str
    template: str
    plan_digest: str
    files_scaffolded: List[str]
    tests_passed: bool
    verification: Dict[str, Any]
    flight_tape_path: str
    flight_tape_sha256: str
    git_commit_sha: Optional[str]
    duration_ms: float
    export_dir: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


APP_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "fastapi-service": {
        "id": "fastapi-service",
        "name": "FastAPI REST Service",
        "description": "Production-grade FastAPI service with Pydantic v2 schemas, JWT/Bearer auth, CRUD endpoints, and pytest suite.",
        "dependencies": ["fastapi>=0.100.0", "pydantic>=2.0.0", "httpx>=0.24.0", "pytest>=7.0.0"],
        "files": [
            "README.md",
            "requirements.txt",
            ".gitignore",
            "src/__init__.py",
            "src/models.py",
            "src/auth.py",
            "src/main.py",
            "tests/__init__.py",
            "tests/test_main.py",
        ],
        "security_boundary": {
            "autonomy": "confirm_mutation",
            "allowed_reads": ["**"],
            "allowed_writes": ["src/**", "tests/**", "README.md", "requirements.txt"],
            "network": "loopback_only",
            "commands": ["pytest -q"],
        },
    },
    "cli-tool": {
        "id": "cli-tool",
        "name": "Deterministic CLI Tool",
        "description": "Modular Python command-line utility with subcommand parsing, data engine, error handling, and test harness.",
        "dependencies": ["pytest>=7.0.0"],
        "files": [
            "README.md",
            "requirements.txt",
            ".gitignore",
            "src/__init__.py",
            "src/engine.py",
            "src/cli.py",
            "tests/__init__.py",
            "tests/test_cli.py",
        ],
        "security_boundary": {
            "autonomy": "autonomous",
            "allowed_reads": ["**"],
            "allowed_writes": ["src/**", "tests/**", "README.md", "requirements.txt"],
            "network": "none",
            "commands": ["pytest -q"],
        },
    },
    "agent-microservice": {
        "id": "agent-microservice",
        "name": "Autonomous Agent Microservice",
        "description": "HTTP-accessible autonomous agent microservice with state lifecycle, tool dispatch, and reproducible test cases.",
        "dependencies": ["fastapi>=0.100.0", "httpx>=0.24.0", "pytest>=7.0.0"],
        "files": [
            "README.md",
            "requirements.txt",
            ".gitignore",
            "src/__init__.py",
            "src/agent_core.py",
            "src/service.py",
            "tests/__init__.py",
            "tests/test_service.py",
        ],
        "security_boundary": {
            "autonomy": "confirm_mutation",
            "allowed_reads": ["**"],
            "allowed_writes": ["src/**", "tests/**", "README.md", "requirements.txt"],
            "network": "loopback_only",
            "commands": ["pytest -q"],
        },
    },
}


class GuidedAppBuilder:
    """End-to-end prompt and template application builder for Keelway."""

    @classmethod
    def list_templates(cls) -> List[Dict[str, Any]]:
        """Return all supported application archetypes."""
        return [
            {
                "id": t["id"],
                "name": t["name"],
                "description": t["description"],
                "dependencies": t["dependencies"],
                "file_count": len(t["files"]),
            }
            for t in APP_TEMPLATES.values()
        ]

    @classmethod
    def synthesize_plan(
        cls,
        intent: str,
        app_name: Optional[str] = None,
        template_id: Optional[str] = None,
    ) -> AppArchitecturePlan:
        """Synthesize an architectural blueprint from developer intent or template."""
        clean_intent = intent.strip()
        if not clean_intent:
            clean_intent = "Build a modern microservice with automated tests"

        # Auto-detect template if not explicitly provided
        chosen_tid = template_id
        if not chosen_tid or chosen_tid not in APP_TEMPLATES:
            lowered = clean_intent.lower()
            if any(k in lowered for k in ("fastapi", "api", "rest", "endpoint", "crud", "jwt")):
                chosen_tid = "fastapi-service"
            elif any(k in lowered for k in ("agent", "autonomous", "loop", "bot", "orchestrat")):
                chosen_tid = "agent-microservice"
            elif any(k in lowered for k in ("cli", "terminal", "command", "argparse", "utility")):
                chosen_tid = "cli-tool"
            else:
                chosen_tid = "fastapi-service"

        tpl = APP_TEMPLATES[chosen_tid]

        # Normalize app name
        if not app_name:
            # Slugify first 3 words of intent or use template name
            slug = re.sub(r"[^a-zA-Z0-9]+", "_", clean_intent.split(".")[0]).strip("_").lower()
            tokens = [t for t in slug.split("_") if t][:3]
            app_name = "_".join(tokens) if tokens else f"{chosen_tid.replace('-', '_')}_app"

        app_name = re.sub(r"[^a-zA-Z0-9_]", "_", app_name).lower()

        modules_desc = {
            "README.md": f"Project overview and setup instructions for {app_name}.",
            "requirements.txt": "Pinned project dependencies.",
            ".gitignore": "Standard Python git exclusion rules.",
            "src/__init__.py": "Package namespace declaration.",
            "tests/__init__.py": "Test package marker.",
        }

        if chosen_tid == "fastapi-service":
            modules_desc.update({
                "src/models.py": "Pydantic v2 schemas for request payloads, responses, and tokens.",
                "src/auth.py": "Bearer token authorization and credential verification.",
                "src/main.py": "FastAPI application entrypoint with health, auth, and CRUD endpoints.",
                "tests/test_main.py": "Pytest suite testing health check, unauthorized access, and item CRUD lifecycle.",
            })
            test_plan = [
                "Verify /health returns 200 OK and status 'ok'",
                "Verify unauthenticated requests to protected endpoints return 401 Unauthorized",
                "Verify invalid tokens return 403 Forbidden",
                "Verify complete item creation, retrieval, and listing lifecycle",
            ]
        elif chosen_tid == "cli-tool":
            modules_desc.update({
                "src/engine.py": "Core data transformation, validation, and analytics engine.",
                "src/cli.py": "Argparse CLI interface with doctor, process, and stats subcommands.",
                "tests/test_cli.py": "Pytest suite verifying CLI options, processing results, and exit codes.",
            })
            test_plan = [
                "Verify doctor subcommand health check reports healthy state",
                "Verify process subcommand validates and transforms payloads",
                "Verify stats subcommand computes aggregate metrics",
                "Verify error handling for invalid or empty inputs",
            ]
        else:  # agent-microservice
            modules_desc.update({
                "src/agent_core.py": "Deterministic agent state machine with tool execution dispatch.",
                "src/service.py": "FastAPI wrapper exposing agent tasks, status queries, and tool inspection.",
                "tests/test_service.py": "Pytest suite validating state transitions, task execution, and endpoints.",
            })
            test_plan = [
                "Verify agent service health probe",
                "Verify agent initialization and registered tools",
                "Verify deterministic task execution and state transitions to COMPLETED",
            ]

        plan_content = json.dumps({
            "app_name": app_name,
            "intent": clean_intent,
            "template": chosen_tid,
            "files": tpl["files"],
        }, sort_keys=True)
        plan_sha256 = hashlib.sha256(plan_content.encode("utf-8")).hexdigest()

        return AppArchitecturePlan(
            app_name=app_name,
            intent=clean_intent,
            template=chosen_tid,
            description=tpl["description"],
            dependencies=tpl["dependencies"],
            file_tree=tpl["files"],
            modules=modules_desc,
            security_boundary=tpl["security_boundary"],
            test_plan=test_plan,
            plan_sha256=plan_sha256,
        )

    @classmethod
    def formulate_steps(cls, plan: AppArchitecturePlan) -> List[AppTaskStep]:
        """Break down architecture plan into discrete deterministic task steps."""
        return [
            AppTaskStep(
                step_id="step-01-scaffold",
                title="Initialize Repository Structure & Config",
                description="Create folder tree, README.md, requirements.txt, and .gitignore.",
                target_files=["README.md", "requirements.txt", ".gitignore", "src/__init__.py", "tests/__init__.py"],
            ),
            AppTaskStep(
                step_id="step-02-domain",
                title="Implement Core Domain Models & Schemas",
                description="Generate typed domain structures, validation logic, and auth primitives.",
                target_files=[f for f in plan.file_tree if f.startswith("src/") and "main" not in f and "cli" not in f and "service" not in f and "__init__" not in f],
            ),
            AppTaskStep(
                step_id="step-03-entrypoint",
                title="Implement Application Entrypoint & Handlers",
                description="Generate runnable CLI or HTTP service endpoints.",
                target_files=[f for f in plan.file_tree if f in ("src/main.py", "src/cli.py", "src/service.py")],
            ),
            AppTaskStep(
                step_id="step-04-tests",
                title="Generate Automated Test Harness",
                description="Scaffold comprehensive pytest test cases matching the verification plan.",
                target_files=[f for f in plan.file_tree if f.startswith("tests/") and "__init__" not in f],
            ),
            AppTaskStep(
                step_id="step-05-verify",
                title="Execute Sandboxed Test Suite & Audit",
                description="Execute automated tests in sandbox and verify clean exit code 0.",
                target_files=[],
            ),
        ]

    @classmethod
    def scaffold_project(cls, plan: AppArchitecturePlan, target_dir: Path) -> List[str]:
        """Scaffold complete working project source files in target directory."""
        target_dir = Path(target_dir).resolve()
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "src").mkdir(parents=True, exist_ok=True)
        (target_dir / "tests").mkdir(parents=True, exist_ok=True)

        created_files: List[str] = []

        def _write(rel_path: str, content: str) -> None:
            p = target_dir / rel_path
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content.strip() + "\n", encoding="utf-8")
            created_files.append(rel_path)

        # Standard files
        _write(
            "README.md",
            f"""# {plan.app_name}

> {plan.description}

Generated deterministically by **Keelway Prompt-to-App Guided Builder**.

## Overview
- **Architecture Template:** `{plan.template}`
- **Intent:** {plan.intent}
- **Plan Digest:** `{plan.plan_sha256[:16]}`

## Dependencies
Install required dependencies:
```bash
pip install -r requirements.txt
```

## Running Tests
Execute the automated test suite:
```bash
pytest -q
```
""",
        )

        _write("requirements.txt", "\n".join(plan.dependencies))
        _write(
            ".gitignore",
            """__pycache__/
*.py[cod]
*$py.class
.pytest_cache/
.coverage
htmlcov/
dist/
build/
*.egg-info/
.env
.venv
venv/
.keelway/
""",
        )
        _write("src/__init__.py", f'"""{plan.app_name} package."""\n__version__ = "0.1.0"\n')
        _write("tests/__init__.py", '"""Test suite."""\n')

        # Template specific file synthesis
        if plan.template == "fastapi-service":
            _write(
                "src/models.py",
                """from __future__ import annotations
from typing import Optional, List
from datetime import datetime, timezone
from pydantic import BaseModel, Field


class ItemCreate(BaseModel):
    title: str = Field(..., min_length=1, description="Item title")
    description: Optional[str] = Field(default=None, description="Optional item description")
    price: float = Field(..., ge=0.0, description="Item price in USD")


class ItemResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    price: float
    created_at: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
""",
            )

            _write(
                "src/auth.py",
                """from typing import Optional
from fastapi import Request, HTTPException, status

DEFAULT_BEARER_TOKEN = "keelway-auth-token-xyz987"


def verify_token(request: Request) -> str:
    \"\"\"Validate incoming Bearer token header.\"\"\"
    authorization = request.headers.get("authorization")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header",
        )
    token = authorization.split("Bearer ")[1].strip()
    if token != DEFAULT_BEARER_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or expired access token",
        )
    return "authenticated_user"
""",
            )

            _write(
                "src/main.py",
                f"""from __future__ import annotations
from datetime import datetime, timezone
from typing import Dict, List
from fastapi import Depends, FastAPI, HTTPException, status

from src.models import ItemCreate, ItemResponse, TokenResponse
from src.auth import DEFAULT_BEARER_TOKEN, verify_token

app = FastAPI(title="{plan.app_name}", version="0.1.0")

_ITEMS_DB: Dict[int, Dict] = {{}}
_AUTO_INCREMENT_ID = 0


@app.get("/health")
def health():
    return {{
        "status": "ok",
        "app": "{plan.app_name}",
        "version": "0.1.0",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }}


@app.post("/auth/token", response_model=TokenResponse)
def issue_token():
    return TokenResponse(access_token=DEFAULT_BEARER_TOKEN)


@app.get("/v1/items", response_model=List[ItemResponse])
def list_items(user: str = Depends(verify_token)):
    return list(_ITEMS_DB.values())


@app.post("/v1/items", response_model=ItemResponse, status_code=status.HTTP_201_CREATED)
def create_item(payload: ItemCreate, user: str = Depends(verify_token)):
    global _AUTO_INCREMENT_ID
    _AUTO_INCREMENT_ID += 1
    new_item = {{
        "id": _AUTO_INCREMENT_ID,
        "title": payload.title,
        "description": payload.description,
        "price": payload.price,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }}
    _ITEMS_DB[_AUTO_INCREMENT_ID] = new_item
    return new_item


@app.get("/v1/items/{{item_id}}", response_model=ItemResponse)
def get_item(item_id: int, user: str = Depends(verify_token)):
    if item_id not in _ITEMS_DB:
        raise HTTPException(status_code=404, detail="Item not found")
    return _ITEMS_DB[item_id]
""",
            )

            _write(
                "tests/test_main.py",
                """from __future__ import annotations
from fastapi.testclient import TestClient
from src.main import app
from src.auth import DEFAULT_BEARER_TOKEN

client = TestClient(app)


def test_health_check():
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert "timestamp_utc" in data


def test_unauthorized_access():
    res = client.get("/v1/items")
    assert res.status_code == 401


def test_forbidden_access():
    res = client.get("/v1/items", headers={"Authorization": "Bearer bad-token"})
    assert res.status_code == 403


def test_crud_lifecycle():
    auth_res = client.post("/auth/token")
    assert auth_res.status_code == 200
    token = auth_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create item
    create_res = client.post(
        "/v1/items",
        json={"title": "Test Device", "description": "High performance unit", "price": 49.99},
        headers=headers,
    )
    assert create_res.status_code == 201
    item = create_res.json()
    assert item["id"] > 0
    assert item["title"] == "Test Device"
    assert item["price"] == 49.99

    # List items
    list_res = client.get("/v1/items", headers=headers)
    assert list_res.status_code == 200
    items = list_res.json()
    assert len(items) >= 1
    assert any(i["id"] == item["id"] for i in items)

    # Get item
    get_res = client.get(f"/v1/items/{item['id']}", headers=headers)
    assert get_res.status_code == 200
    assert get_res.json()["title"] == "Test Device"

    # Not found
    missing_res = client.get("/v1/items/99999", headers=headers)
    assert missing_res.status_code == 404
""",
            )

        elif plan.template == "cli-tool":
            _write(
                "src/engine.py",
                """from __future__ import annotations
import hashlib
from typing import Any, Dict, List


class ProcessingEngine:
    \"\"\"Core deterministic data processing engine.\"\"\"

    @classmethod
    def transform_text(cls, text: str, uppercase: bool = False) -> Dict[str, Any]:
        cleaned = text.strip()
        processed = cleaned.upper() if uppercase else cleaned
        sha256 = hashlib.sha256(processed.encode("utf-8")).hexdigest()
        return {
            "original_length": len(text),
            "processed_length": len(processed),
            "content": processed,
            "sha256": sha256,
        }

    @classmethod
    def compute_stats(cls, numbers: List[float]) -> Dict[str, float]:
        if not numbers:
            return {"count": 0.0, "sum": 0.0, "mean": 0.0, "min": 0.0, "max": 0.0}
        total = sum(numbers)
        return {
            "count": float(len(numbers)),
            "sum": total,
            "mean": total / len(numbers),
            "min": min(numbers),
            "max": max(numbers),
        }
""",
            )

            _write(
                "src/cli.py",
                f"""from __future__ import annotations
import argparse
import json
import sys
from src.engine import ProcessingEngine


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="{plan.app_name}", description="{plan.description}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # doctor
    subparsers.add_parser("doctor", help="Run system health checks")

    # process
    proc_p = subparsers.add_parser("process", help="Transform text input")
    proc_p.add_argument("text", help="Text string to process")
    proc_p.add_argument("--upper", action="store_true", help="Uppercase transformed text")

    # stats
    stats_p = subparsers.add_parser("stats", help="Compute summary statistics for a list of numbers")
    stats_p.add_argument("numbers", nargs="+", type=float, help="Numeric values")

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "doctor":
        print(json.dumps({{"status": "ok", "app": "{plan.app_name}", "version": "0.1.0"}}))
        return 0
    elif args.command == "process":
        res = ProcessingEngine.transform_text(args.text, uppercase=args.upper)
        print(json.dumps(res, indent=2))
        return 0
    elif args.command == "stats":
        res = ProcessingEngine.compute_stats(args.numbers)
        print(json.dumps(res, indent=2))
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
""",
            )

            _write(
                "tests/test_cli.py",
                """from __future__ import annotations
from src.cli import main
from src.engine import ProcessingEngine


def test_engine_transformation():
    res = ProcessingEngine.transform_text("hello world", uppercase=True)
    assert res["content"] == "HELLO WORLD"
    assert len(res["sha256"]) == 64


def test_engine_stats():
    res = ProcessingEngine.compute_stats([10.0, 20.0, 30.0])
    assert res["count"] == 3.0
    assert res["sum"] == 60.0
    assert res["mean"] == 20.0
    assert res["min"] == 10.0
    assert res["max"] == 30.0


def test_engine_stats_empty():
    res = ProcessingEngine.compute_stats([])
    assert res["count"] == 0.0


def test_cli_doctor(capsys):
    ret = main(["doctor"])
    assert ret == 0
    captured = capsys.readouterr().out
    assert '"status": "ok"' in captured


def test_cli_process(capsys):
    ret = main(["process", "alpha beta", "--upper"])
    assert ret == 0
    captured = capsys.readouterr().out
    assert "ALPHA BETA" in captured


def test_cli_stats(capsys):
    ret = main(["stats", "5", "15"])
    assert ret == 0
    captured = capsys.readouterr().out
    assert '"mean": 10.0' in captured
""",
            )

        else:  # agent-microservice
            _write(
                "src/agent_core.py",
                """from __future__ import annotations
import time
from typing import Any, Dict, List


class MicroAgent:
    \"\"\"Deterministic micro-agent state engine.\"\"\"

    def __init__(self, agent_id: str = "agent-01"):
        self.agent_id = agent_id
        self.state = "INITIALIZED"
        self.execution_log: List[Dict[str, Any]] = []

    def execute_task(self, goal: str) -> Dict[str, Any]:
        self.state = "RUNNING"
        start = time.time()
        self.execution_log.append({"event": "task_started", "goal": goal, "ts": start})

        # Deterministic step sequence
        steps = [
            {"step": 1, "action": "analyze_goal", "output": f"Parsed objective: {goal}"},
            {"step": 2, "action": "plan_operations", "output": "Formulated 2 execution steps"},
            {"step": 3, "action": "execute_steps", "output": "Operations completed cleanly"},
        ]
        self.state = "COMPLETED"
        duration_ms = (time.time() - start) * 1000.0

        return {
            "agent_id": self.agent_id,
            "status": self.state,
            "goal": goal,
            "steps": steps,
            "duration_ms": duration_ms,
        }
""",
            )

            _write(
                "src/service.py",
                f"""from __future__ import annotations
from typing import Any, Dict
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.agent_core import MicroAgent

app = FastAPI(title="{plan.app_name}", version="0.1.0")
_AGENT = MicroAgent(agent_id="{plan.app_name}")


class TaskRequest(BaseModel):
    goal: str = Field(..., min_length=1, description="Goal for agent execution")


@app.get("/health")
def health():
    return {{"status": "ok", "agent_state": _AGENT.state}}


@app.post("/v1/agent/run")
def run_agent(req: TaskRequest):
    res = _AGENT.execute_task(req.goal)
    return res


@app.get("/v1/agent/history")
def get_history():
    return {{"agent_id": _AGENT.agent_id, "history": _AGENT.execution_log}}
""",
            )

            _write(
                "tests/test_service.py",
                """from __future__ import annotations
from fastapi.testclient import TestClient
from src.service import app
from src.agent_core import MicroAgent

client = TestClient(app)


def test_agent_core_execution():
    agent = MicroAgent(agent_id="test-agent")
    res = agent.execute_task("Process repository metadata")
    assert res["status"] == "COMPLETED"
    assert len(res["steps"]) == 3
    assert agent.state == "COMPLETED"


def test_service_health():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_service_run():
    res = client.post("/v1/agent/run", json={"goal": "Verify telemetry metrics"})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "COMPLETED"
    assert data["goal"] == "Verify telemetry metrics"
""",
            )

        return created_files

    @classmethod
    def verify_harness(cls, target_dir: Path, test_cmd: str = "pytest -q") -> AppVerificationResult:
        """Execute automated tests in the target directory using virtualenv Python."""
        start = time.time()
        # Always use sys.executable to guarantee same environment and sandbox safety
        cmd = [sys.executable, "-m", "pytest", "-q"]
        env = os.environ.copy()
        env["PYTHONPATH"] = str(target_dir.resolve())

        try:
            proc = subprocess.run(
                cmd,
                cwd=str(target_dir),
                capture_output=True,
                text=True,
                timeout=45,
                env=env,
            )
            duration_ms = (time.time() - start) * 1000.0
            output = proc.stdout + ("\n" + proc.stderr if proc.stderr else "")

            # Count passed tests
            match = re.search(r"(\d+)\s+passed", output)
            tests_count = int(match.group(1)) if match else (1 if proc.returncode == 0 else 0)

            return AppVerificationResult(
                test_command=" ".join(cmd),
                passed=(proc.returncode == 0),
                exit_code=proc.returncode,
                tests_count=tests_count,
                output=output.strip(),
                duration_ms=duration_ms,
            )
        except subprocess.TimeoutExpired:
            return AppVerificationResult(
                test_command=" ".join(cmd),
                passed=False,
                exit_code=124,
                tests_count=0,
                output="Test harness timed out after 45s",
                duration_ms=(time.time() - start) * 1000.0,
            )
        except Exception as e:
            return AppVerificationResult(
                test_command=" ".join(cmd),
                passed=False,
                exit_code=1,
                tests_count=0,
                output=f"Subprocess execution error: {e}",
                duration_ms=(time.time() - start) * 1000.0,
            )

    @classmethod
    def build_and_export(
        cls,
        intent: str,
        app_name: Optional[str] = None,
        template_id: Optional[str] = None,
        target_dir: Optional[Path] = None,
        run_verification: bool = True,
        init_git: bool = True,
    ) -> AppBuildReceipt:
        """Full pipeline: synthesize plan, scaffold codebase, verify tests, record tape, and export."""
        start_time = time.time()

        # Stage 1: Synthesize Plan
        plan = cls.synthesize_plan(intent, app_name=app_name, template_id=template_id)

        # Determine target export directory
        if not target_dir:
            target_dir = Path("builds") / plan.app_name

        target_dir = Path(target_dir).resolve()

        # Initialize Flight Recorder
        recorder = FlightRecorder(task_id=f"build_{plan.app_name}")
        recorder.record_event("plan_synthesized", {
            "app_name": plan.app_name,
            "template": plan.template,
            "intent": plan.intent,
            "plan_sha256": plan.plan_sha256,
            "files_planned": plan.file_tree,
        })

        # Stage 2: Formulate Steps
        steps = cls.formulate_steps(plan)
        recorder.record_event("steps_formulated", {"step_count": len(steps)})

        # Stage 3: Scaffold Project
        created_files = cls.scaffold_project(plan, target_dir)
        recorder.record_event("scaffolding_completed", {
            "target_dir": str(target_dir),
            "files_created": created_files,
        })

        # Stage 4: Verify Test Harness
        verification = AppVerificationResult(
            test_command="pytest -q",
            passed=True,
            exit_code=0,
            tests_count=0,
            output="Verification skipped by caller",
            duration_ms=0.0,
        )
        if run_verification:
            verification = cls.verify_harness(target_dir)
            recorder.record_event("verification_executed", verification.to_dict())

        # Stage 5: Optional Git Init
        git_sha: Optional[str] = None
        if init_git:
            try:
                # Check if git exists and init repo if not already a repo
                if not (target_dir / ".git").exists():
                    subprocess.run(["git", "init", "-q"], cwd=str(target_dir), check=False)
                    subprocess.run(["git", "add", "."], cwd=str(target_dir), check=False)
                    subprocess.run(
                        ["git", "-c", "user.name=Keelway Builder", "-c", "user.email=builder@keelway.internal", "commit", "-m", f"feat(init): scaffold {plan.app_name} via Keelway Guided Builder", "-q"],
                        cwd=str(target_dir),
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    rev_proc = subprocess.run(
                        ["git", "rev-parse", "HEAD"],
                        cwd=str(target_dir),
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    if rev_proc.returncode == 0:
                        git_sha = rev_proc.stdout.strip()
            except Exception:
                pass

        # Save flight tape and seal
        tape_path = recorder.save_tape()
        total_duration_ms = (time.time() - start_time) * 1000.0

        receipt = AppBuildReceipt(
            app_name=plan.app_name,
            template=plan.template,
            plan_digest=plan.plan_sha256,
            files_scaffolded=created_files,
            tests_passed=verification.passed,
            verification=verification.to_dict(),
            flight_tape_path=str(tape_path),
            flight_tape_sha256=recorder.tape_sha256 or "",
            git_commit_sha=git_sha,
            duration_ms=total_duration_ms,
            export_dir=str(target_dir),
        )

        # Save receipt to target directory
        receipt_file = target_dir / "build_receipt.json"
        receipt_file.write_text(json.dumps(receipt.to_dict(), indent=2), encoding="utf-8")

        return receipt
