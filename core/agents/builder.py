"""
Keelway Agent Builder.
Automates agent specification, template scaffolding, source generation,
manifest compilation, test harness execution, and evaluation receipt issuance.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.agents import manifest as am
from core.agents.spec import AgentSpec, EvaluationCriteria
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
    "doc-writer": {
        "name": "doc-writer",
        "description": "Inspects AST diffs and code symbols, then synchronizes READMEs, OpenAPI specs, and docs.",
        "instructions": (
            "Analyze recently modified symbols, routes, or CLI commands. Update existing documentation, "
            "Markdown guides, and API schemas to reflect code changes accurately without removing existing comments."
        ),
        "tools": ["read_file", "write_file", "edit_file", "list_dir", "search_codebase"],
        "permissions": {
            "autonomy": "confirm_mutation",
            "read_paths": ["**"],
            "write_paths": ["docs/**", "website/**", "README.md", "openapi.json"],
            "commands": [],
            "network": "none",
        },
        "budget": {"max_usd_per_run": 0.25, "max_steps": 30},
        "evaluation": {"test_command": "pytest -q", "max_latency_ms": 15000, "max_usd_budget": 0.25},
    },
    "dependency-modernizer": {
        "name": "dependency-modernizer",
        "description": "Audits outdated package dependencies, tests semver upgrades in sandbox, and drafts migration.",
        "instructions": (
            "Inspect package manifests (pyproject.toml, package.json). Upgrade target dependency to the latest safe "
            "version, run the test suite in isolation, and adapt breaking API changes if tests fail."
        ),
        "tools": ["read_file", "edit_file", "run_command", "search_codebase", "list_dir"],
        "permissions": {
            "autonomy": "confirm_mutation",
            "read_paths": ["**"],
            "write_paths": ["pyproject.toml", "package.json", "src/**", "core/**", "lib/**"],
            "commands": ["pytest -q", "npm test", "poetry run pytest"],
            "network": "none",
        },
        "budget": {"max_usd_per_run": 0.5, "max_steps": 45},
        "evaluation": {"test_command": "pytest -q", "max_latency_ms": 30000, "max_usd_budget": 0.5},
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
        if compiled_manifest is None:
            raise ValueError("manifest validation produced no manifest")
        manifest_digest = am.digest(compiled_manifest)

        if register_in_db:
            await init_db()
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    try:
                        await register_manifest(session, manifest_dict, owner_override=spec.author)
                    except Exception:
                        pass  # Allow re-building/updating existing

        # 3. Run generated test harness (safe execution without host shell)
        clean_slug = spec.name.replace("-", "_")
        test_file = target_dir / f"test_{clean_slug}.py"
        clean_env, _ = scrub_env(dict(os.environ))
        repo_root = str(Path(__file__).resolve().parent.parent.parent)
        clean_env["PYTHONPATH"] = f"{repo_root}:{os.environ.get('PYTHONPATH', '')}"

        proc = subprocess.run(
            [sys.executable, "-m", "unittest", "-q", test_file.name],
            shell=False,
            cwd=target_dir,
            env=clean_env,
            capture_output=True,
            text=True,
            timeout=30,
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


@dataclass
class AgentBundleManifest:
    bundle_name: str
    version: str
    manifest_digest: str
    created_at_iso: str
    files: Dict[str, str]
    bundle_digest_sha256: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AgentBundlePacker:
    """Packages and unpackages declarative agent distributions with cryptographic digests."""

    @staticmethod
    def pack(source_dir: Path, output_archive: Path) -> Dict[str, Any]:
        import io
        import tarfile
        from datetime import datetime, timezone

        source_dir = Path(source_dir).resolve()
        output_archive = Path(output_archive).resolve()
        output_archive.parent.mkdir(parents=True, exist_ok=True)

        if not source_dir.is_dir():
            raise FileNotFoundError(f"Source directory '{source_dir}' does not exist.")

        file_digests: Dict[str, str] = {}
        for root, _, files in os.walk(source_dir):
            for file in sorted(files):
                if file.endswith((".pyc", ".tar.gz", ".DS_Store")) or file == "bundle_manifest.json":
                    continue
                fpath = Path(root) / file
                rel = str(fpath.relative_to(source_dir))
                file_digests[rel] = hashlib.sha256(fpath.read_bytes()).hexdigest()

        manifest_files = [f for f in file_digests if f.endswith(".agent.json")]
        manifest_digest = file_digests[manifest_files[0]] if manifest_files else ""
        bundle_name = source_dir.name
        created_at_iso = datetime.now(timezone.utc).isoformat()
        canonical_payload = json.dumps(file_digests, sort_keys=True)
        bundle_digest = hashlib.sha256(canonical_payload.encode()).hexdigest()

        bundle_manifest = AgentBundleManifest(
            bundle_name=bundle_name,
            version="1.0.0",
            manifest_digest=manifest_digest,
            created_at_iso=created_at_iso,
            files=file_digests,
            bundle_digest_sha256=bundle_digest,
        )

        with tarfile.open(output_archive, "w:gz") as tar:
            manifest_bytes = json.dumps(bundle_manifest.to_dict(), indent=2).encode("utf-8")
            ti = tarfile.TarInfo(name="bundle_manifest.json")
            ti.size = len(manifest_bytes)
            ti.mtime = int(time.time())
            tar.addfile(ti, io.BytesIO(manifest_bytes))

            for rel in sorted(file_digests.keys()):
                tar.add(source_dir / rel, arcname=rel)

        return bundle_manifest.to_dict()

    @staticmethod
    def unpack(archive_path: Path, destination_dir: Path, verify: bool = True) -> Dict[str, Any]:
        import tarfile

        archive_path = Path(archive_path).resolve()
        destination_dir = Path(destination_dir).resolve()
        destination_dir.mkdir(parents=True, exist_ok=True)

        if not archive_path.is_file():
            raise FileNotFoundError(f"Archive file '{archive_path}' does not exist.")

        with tarfile.open(archive_path, "r:gz") as tar:
            resolved_dest = destination_dir.resolve()
            # Prevent zip-slip (including sibling-prefix bypasses such as /tmp/dest_evil vs /tmp/dest)
            for member in tar.getmembers():
                target_p = (resolved_dest / member.name).resolve()
                if not target_p.is_relative_to(resolved_dest):
                    raise PermissionError(f"Directory traversal attack detected in tar member: {member.name}")

            try:
                bm_file = tar.extractfile("bundle_manifest.json")
                if not bm_file:
                    raise ValueError("bundle_manifest.json not found in archive.")
                bundle_manifest = json.loads(bm_file.read().decode("utf-8"))
            except Exception as e:
                raise ValueError(f"Corrupted or missing bundle_manifest.json: {e}") from e

            try:
                if sys.version_info >= (3, 12):
                    tar.extractall(path=destination_dir, filter="data")
                else:
                    tar.extractall(path=destination_dir)
            except tarfile.FilterError as exc:
                raise PermissionError(f"Directory traversal attack or unsafe tar member detected: {exc}") from exc

        if verify:
            for rel, expected_hash in bundle_manifest.get("files", {}).items():
                fpath = destination_dir / rel
                if not fpath.is_file():
                    raise FileNotFoundError(f"Missing file declared in bundle manifest: {rel}")
                actual_hash = hashlib.sha256(fpath.read_bytes()).hexdigest()
                if actual_hash != expected_hash:
                    raise ValueError(f"Tampered file detected: {rel} (expected {expected_hash}, got {actual_hash})")

        return bundle_manifest

    unpack_bundle = unpack


AgentBuilder.pack_bundle = staticmethod(AgentBundlePacker.pack)  # type: ignore[attr-defined]
AgentBuilder.unpack_bundle = staticmethod(AgentBundlePacker.unpack)  # type: ignore[attr-defined]
