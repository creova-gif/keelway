"""
Keelway Agent Builder.
Automates agent specification, template scaffolding, source generation,
manifest compilation, test harness execution, and evaluation receipt issuance.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.agents import manifest as am
from core.agents.spec import AgentParam, AgentSpec, EvaluationCriteria, StateContract
from core.agents.registry import register_manifest
from core.storage.database import init_db, AsyncSessionLocal
from core.security.env_scrub import scrub_env


BUILTIN_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "test-fixer": {
        "name": "test-fixer",
        "description": "Finds the root cause of failing tests and proposes minimal code fixes.",
        "instructions": (
            "Run the failing test command, inspect the traceback and relevant files, "
            "formulate the minimal targeted patch that restores passing tests, and explain the root cause. "
            "Never modify the test assertions to manufacture an artificial pass."
        ),
        "tools": ["read_file", "edit_file", "run_command", "search_codebase", "list_dir"],
        "permissions": {
            "autonomy": "confirm_mutation",
            "read_paths": ["**"],
            "write_paths": ["src/**", "core/**", "lib/**"],
            "commands": ["pytest -q", "python3 -m unittest -q"],
            "network": "none",
        },
        "budget": {"max_usd_per_run": 0.5, "max_steps": 40},
        "evaluation": {"test_command": "pytest -q", "max_latency_ms": 30000, "max_usd_budget": 0.5},
    },
    "code-reviewer": {
        "name": "code-reviewer",
        "description": "Inspects git diffs and code files for security risks, bugs, and performance regressions.",
        "instructions": (
            "Analyze git diffs and modified files. Identify subtle logic errors, security vulnerabilities, "
            "and performance bottlenecks. Provide constructive, high-confidence feedback. Do not edit files directly."
        ),
        "tools": ["read_file", "list_dir", "search_codebase"],
        "permissions": {
            "autonomy": "autonomous",
            "read_paths": ["**"],
            "write_paths": [],
            "commands": [],
            "network": "none",
        },
        "budget": {"max_usd_per_run": 0.25, "max_steps": 25},
        "evaluation": {"test_command": "pytest -q", "max_latency_ms": 15000, "max_usd_budget": 0.25},
    },
    "security-auditor": {
        "name": "security-auditor",
        "description": "Audits repository for hardcoded secrets, unsafe deserialization, and path traversals.",
        "instructions": (
            "Scan workspace files and commit history for credential leaks, dangerous subprocess calls, "
            "unsafe deserialization, and path traversal vectors. Report exact file locations and remediation steps."
        ),
        "tools": ["read_file", "list_dir", "search_codebase"],
        "permissions": {
            "autonomy": "autonomous",
            "read_paths": ["**"],
            "write_paths": [],
            "commands": [],
            "network": "none",
        },
        "budget": {"max_usd_per_run": 0.3, "max_steps": 30},
        "evaluation": {"test_command": "pytest -q", "max_latency_ms": 20000, "max_usd_budget": 0.3},
    },
    "feature-scaffolder": {
        "name": "feature-scaffolder",
        "description": "Scaffolds new domain models, handlers, and unit tests according to user specification.",
        "instructions": (
            "Create modular, type-annotated domain models, business logic functions, and unit tests. "
            "Ensure all newly created tests pass cleanly before completing the task."
        ),
        "tools": ["read_file", "write_file", "edit_file", "run_command", "list_dir"],
        "permissions": {
            "autonomy": "confirm_mutation",
            "read_paths": ["**"],
            "write_paths": ["src/**", "tests/**", "core/**"],
            "commands": ["pytest -q", "npm test", "cargo test"],
            "network": "none",
        },
        "budget": {"max_usd_per_run": 0.75, "max_steps": 50},
        "evaluation": {"test_command": "pytest -q", "max_latency_ms": 45000, "max_usd_budget": 0.75},
    },
}


@dataclass
class AgentBuildReceipt:
    spec_name: str
    version: str
    manifest_digest: str
    files_created: List[str]
    tests_passed: bool
    test_output: str
    duration_ms: float
    receipt_sha256: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AgentBuilder:
    """Builder engine for Keelway AI Agents."""

    @classmethod
    def list_templates(cls) -> List[Dict[str, Any]]:
        """Return a summary of all built-in agent templates."""
        return [
            {
                "id": k,
                "name": v["name"],
                "description": v["description"],
                "tools": v["tools"],
                "autonomy": v["permissions"]["autonomy"],
                "max_budget_usd": v["budget"]["max_usd_per_run"],
            }
            for k, v in BUILTIN_TEMPLATES.items()
        ]

    @classmethod
    def create_from_template(
        cls,
        template_id: str,
        name: str,
        author: str,
        overrides: Optional[Dict[str, Any]] = None,
    ) -> AgentSpec:
        """Instantiate a typed AgentSpec from a built-in template."""
        if template_id not in BUILTIN_TEMPLATES:
            raise ValueError(f"Unknown template '{template_id}'. Choose from: {list(BUILTIN_TEMPLATES.keys())}")

        tpl = BUILTIN_TEMPLATES[template_id].copy()
        tpl["name"] = name
        tpl["author"] = author

        if overrides:
            for k, v in overrides.items():
                if k in tpl:
                    if isinstance(tpl[k], dict) and isinstance(v, dict):
                        tpl[k].update(v)
                    else:
                        tpl[k] = v

        return AgentSpec(
            name=tpl["name"],
            version=tpl.get("version", "0.1.0"),
            author=tpl["author"],
            description=tpl["description"],
            instructions=tpl["instructions"],
            tools=tpl["tools"],
            permissions=am.Permissions(**tpl["permissions"]),
            budget=am.Budget(**tpl["budget"]),
            evaluation=EvaluationCriteria(**tpl.get("evaluation", {})),
        )

    @classmethod
    def generate_source_artifacts(cls, spec: AgentSpec) -> Dict[str, str]:
        """Generate complete file contents for the scaffolded agent."""
        manifest_dict = spec.to_manifest_dict()
        manifest_json = json.dumps(manifest_dict, indent=2)
        spec_json = spec.to_json(indent=2)

        runner_py = f'''#!/usr/bin/env python3
"""
Autogenerated runner for Keelway Agent: {spec.name}@{spec.version}
Author: {spec.author}
"""
import asyncio
import json
from pathlib import Path
from core.agents import manifest as am
from core.agents.guard import loop_from_manifest
from core.storage.workspace_fs import WorkspaceFilesystem

async def run(task_goal: str, workspace_path: str = "."):
    ws_fs = WorkspaceFilesystem(root_dir=workspace_path)
    manifest_path = Path(__file__).parent / "{spec.name}.agent.json"
    manifest = am.load_file(manifest_path)
    
    agent = loop_from_manifest(manifest, task_id="task_{spec.name}", workspace_fs=ws_fs)
    print(f"[+] Initialized agent '{{manifest.name}}@{{manifest.version}}' (digest: {{agent.guard.manifest_digest[:16]}}...)")
    state = await agent.run(task_goal)
    print(f"[+] Completed execution with status: {{state['status']}}")
    return state

if __name__ == "__main__":
    import sys
    goal = sys.argv[1] if len(sys.argv) > 1 else "{spec.description or 'Execute agent workflow'}"
    asyncio.run(run(goal))
'''

        test_py = f'''"""
Verification test harness for Keelway Agent: {spec.name}@{spec.version}
"""
import json
import unittest
from pathlib import Path
from core.agents import manifest as am
from core.agents.spec import AgentSpec

class Test{spec.name.replace("-", " ").title().replace(" ", "")}Agent(unittest.TestCase):
    def test_manifest_validation(self):
        manifest_path = Path(__file__).parent / "{spec.name}.agent.json"
        self.assertTrue(manifest_path.exists(), "Manifest file was not generated.")
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        report = am.validate(data)
        self.assertTrue(report.ok, f"Manifest validation failed: {{report.errors}}")
        self.assertEqual(report.manifest.name, "{spec.name}")
        self.assertEqual(report.manifest.version, "{spec.version}")

    def test_spec_integrity(self):
        spec_path = Path(__file__).parent / "{spec.name}.spec.json"
        self.assertTrue(spec_path.exists(), "Spec file was not generated.")
        spec = AgentSpec.from_json(spec_path.read_text(encoding="utf-8"))
        self.assertEqual(spec.name, "{spec.name}")
        compiled = spec.to_manifest_dict()
        self.assertEqual(compiled["name"], "{spec.name}")

if __name__ == "__main__":
    unittest.main()
'''

        readme_md = f'''# {spec.name} (v{spec.version})

> {spec.description or "Keelway Autonomous Agent"}

- **Author:** {spec.author}
- **Autonomy Policy:** `{spec.permissions.autonomy}`
- **Max Budget:** `${spec.budget.max_usd_per_run:.2f}` (up to {spec.budget.max_steps} steps)
- **Allowed Tools:** `{", ".join(spec.tools)}`

## Quick Start

```bash
# Run the agent test harness
python3 -m unittest -q test_{spec.name.replace('-', '_')}.py

# Execute the agent
python3 run_{spec.name.replace('-', '_')}.py "Your task description"
```
'''

        clean_slug = spec.name.replace("-", "_")
        return {
            f"{spec.name}.agent.json": manifest_json,
            f"{spec.name}.spec.json": spec_json,
            f"run_{clean_slug}.py": runner_py,
            f"test_{clean_slug}.py": test_py,
            "README.md": readme_md,
        }

    @classmethod
    async def build_and_register(
        cls,
        spec: AgentSpec,
        target_dir: Path,
        register_in_db: bool = True,
    ) -> AgentBuildReceipt:
        """Write artifacts to target directory, register in DB, and execute test harness."""
        start_t = time.perf_counter()
        target_dir = Path(target_dir).resolve()
        target_dir.mkdir(parents=True, exist_ok=True)

        # 1. Generate artifacts
        artifacts = cls.generate_source_artifacts(spec)
        files_created = []
        for filename, content in artifacts.items():
            fpath = target_dir / filename
            fpath.write_text(content, encoding="utf-8")
            files_created.append(str(fpath.relative_to(target_dir)))

        # 2. Register manifest in DB
        manifest_dict = spec.to_manifest_dict()
        compiled_manifest = am.validate(manifest_dict).manifest
        manifest_digest = am.digest(compiled_manifest)

        if register_in_db:
            await init_db()
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    try:
                        await register_manifest(session, manifest_dict, owner_override=spec.author)
                    except Exception:
                        pass  # Allow re-building/updating existing

        # 3. Run generated test harness
        clean_slug = spec.name.replace("-", "_")
        test_file = target_dir / f"test_{clean_slug}.py"
        test_cmd = f'"{sys.executable}" -m unittest -q {test_file.name}'
        clean_env, _ = scrub_env(dict(os.environ))
        repo_root = str(Path(__file__).resolve().parent.parent.parent)
        clean_env["PYTHONPATH"] = f"{repo_root}:{os.environ.get('PYTHONPATH', '')}"

        proc = subprocess.run(
            test_cmd,
            shell=True,
            cwd=target_dir,
            env=clean_env,
            capture_output=True,
            text=True,
        )

        dur_ms = (time.perf_counter() - start_t) * 1000
        tests_passed = (proc.returncode == 0)
        test_output = proc.stdout + proc.stderr

        # 4. Generate receipt seal
        seal_payload = f"{spec.name}:{spec.version}:{manifest_digest}:{tests_passed}:{dur_ms}"
        receipt_sha256 = hashlib.sha256(seal_payload.encode()).hexdigest()

        return AgentBuildReceipt(
            spec_name=spec.name,
            version=spec.version,
            manifest_digest=manifest_digest,
            files_created=files_created,
            tests_passed=tests_passed,
            test_output=test_output.strip() or "OK",
            duration_ms=dur_ms,
            receipt_sha256=receipt_sha256,
        )
