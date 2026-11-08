"""
KStack Skills Registry and Workflow Engine.
Provides inspect, import, validate, list, pin, export, and revoke operations.
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple

from core.kstack.models import SkillContract, SkillDefinition, SkillExecutionProof


BUILTIN_SKILLS_DIR = Path(__file__).parent / "skills"


def parse_skill_markdown(content: str, source_uri: str = "") -> SkillDefinition:
    """Parse SKILL.md frontmatter and body into a SkillDefinition."""
    frontmatter_match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL)
    if not frontmatter_match:
        raise ValueError("Invalid SKILL.md: Missing YAML frontmatter delimited by '---'")

    raw_yaml = frontmatter_match.group(1)
    body = frontmatter_match.group(2).strip()

    # Lightweight robust parser for key-value and list frontmatter
    metadata: Dict[str, Any] = {}
    current_key: Optional[str] = None
    current_dict: Optional[Dict[str, str]] = None
    current_list: Optional[List[str]] = None

    for line in raw_yaml.split("\n"):
        line = line.rstrip()
        if not line or line.startswith("#"):
            continue

        if re.match(r"^[a-zA-Z0-9_-]+:\s*$", line):
            # Start of dict or list section
            k = line.split(":")[0].strip()
            current_key = k
            if k in ("inputs", "outputs"):
                current_dict = {}
                metadata[k] = current_dict
                current_list = None
            else:
                current_list = []
                metadata[k] = current_list
                current_dict = None
        elif current_dict is not None and re.match(r"^\s+[a-zA-Z0-9_-]+:", line):
            sub_k, sub_v = line.strip().split(":", 1)
            current_dict[sub_k.strip()] = sub_v.strip()
        elif current_list is not None and line.strip().startswith("- "):
            current_list.append(line.strip()[2:].strip())
        elif ":" in line:
            current_key = None
            current_dict = None
            current_list = None
            k, v = line.split(":", 1)
            metadata[k.strip()] = v.strip()

    name = metadata.get("name", "unnamed-skill")
    version = metadata.get("version", "1.0.0")
    role = metadata.get("role", "general")
    description = metadata.get("description", "")
    permissions = metadata.get("permissions", ["read"])
    if isinstance(permissions, str):
        permissions = [permissions]

    inputs = metadata.get("inputs", {})
    outputs = metadata.get("outputs", {})
    contract = SkillContract(inputs=inputs, outputs=outputs)

    skill = SkillDefinition(
        name=name,
        version=version,
        role=role,
        description=description,
        permissions=permissions,
        contract=contract,
        instructions=body,
        source_uri=source_uri,
        pinned=True,
    )
    skill.digest_sha256 = skill.calculate_digest()
    return skill


class KStackRegistry:
    """Thread-safe registry for KStack role skills."""

    def __init__(self, storage_dir: Optional[Path] = None):
        self._lock = Lock()
        self.storage_dir = storage_dir or Path(".keelway/kstack")
        self._skills: Dict[str, SkillDefinition] = {}
        self._load_builtins()

    def _load_builtins(self) -> None:
        if not BUILTIN_SKILLS_DIR.exists():
            return
        for skill_dir in BUILTIN_SKILLS_DIR.iterdir():
            if skill_dir.is_dir():
                skill_file = skill_dir / "SKILL.md"
                if skill_file.exists():
                    try:
                        content = skill_file.read_text(encoding="utf-8")
                        skill = parse_skill_markdown(content, source_uri=str(skill_file))
                        self._skills[skill.name] = skill
                    except Exception:
                        pass

    def list_skills(self, include_revoked: bool = False) -> List[SkillDefinition]:
        with self._lock:
            skills = list(self._skills.values())
            if not include_revoked:
                skills = [s for s in skills if not s.revoked]
            return sorted(skills, key=lambda s: s.name)

    def get_skill(self, name: str) -> Optional[SkillDefinition]:
        with self._lock:
            return self._skills.get(name)

    def inspect_skill(self, name: str) -> Dict[str, Any]:
        skill = self.get_skill(name)
        if not skill:
            raise KeyError(f"Skill '{name}' not found in KStack registry")
        return skill.to_dict()

    def validate_skill(self, content: str) -> Tuple[bool, List[str]]:
        errors: List[str] = []
        try:
            skill = parse_skill_markdown(content)
            if not skill.name or skill.name == "unnamed-skill":
                errors.append("Skill 'name' is required in frontmatter")
            if not skill.instructions:
                errors.append("Skill instructions body cannot be empty")
            valid_roles = {
                "architect",
                "reviewer",
                "qa_lead",
                "sec_lead",
                "engineer",
                "debugger",
                "release_lead",
                "general",
            }
            if skill.role not in valid_roles:
                errors.append(f"Invalid role '{skill.role}', expected one of {sorted(valid_roles)}")
        except Exception as e:
            errors.append(str(e))
        return (len(errors) == 0, errors)

    def import_skill(self, skill_md_path: Path, pin: bool = True) -> SkillDefinition:
        if not skill_md_path.exists():
            raise FileNotFoundError(f"Skill file not found: {skill_md_path}")
        content = skill_md_path.read_text(encoding="utf-8")
        is_valid, errors = self.validate_skill(content)
        if not is_valid:
            raise ValueError(f"Skill validation failed: {'; '.join(errors)}")

        skill = parse_skill_markdown(content, source_uri=str(skill_md_path.resolve()))
        skill.pinned = pin

        with self._lock:
            self._skills[skill.name] = skill

        # Persist copy to storage_dir if configured
        if self.storage_dir:
            try:
                dest = self.storage_dir / "imported" / f"{skill.name.replace('/', '_')}.md"
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(content, encoding="utf-8")
            except Exception:
                pass
        return skill

    def pin_skill(self, name: str, pinned: bool = True) -> bool:
        with self._lock:
            if name in self._skills:
                self._skills[name].pinned = pinned
                return True
            return False

    def revoke_skill(self, name: str, reason: str = "security revocation") -> bool:
        with self._lock:
            if name in self._skills:
                self._skills[name].revoked = True
                self._skills[name].revocation_reason = reason
                return True
            return False

    def export_skill(self, name: str, out_path: Path) -> Path:
        skill = self.get_skill(name)
        if not skill:
            raise KeyError(f"Skill '{name}' not found")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        # Reconstruct standard SKILL.md
        frontmatter = {
            "name": skill.name,
            "version": skill.version,
            "role": skill.role,
            "description": skill.description,
            "permissions": skill.permissions,
            "inputs": skill.contract.inputs,
            "outputs": skill.contract.outputs,
        }
        yaml_lines = ["---"]
        yaml_lines.append(f"name: {skill.name}")
        yaml_lines.append(f"version: {skill.version}")
        yaml_lines.append(f"role: {skill.role}")
        yaml_lines.append(f"description: {skill.description}")
        yaml_lines.append("permissions:")
        for p in skill.permissions:
            yaml_lines.append(f"  - {p}")
        yaml_lines.append("inputs:")
        for k, v in skill.contract.inputs.items():
            yaml_lines.append(f"  {k}: {v}")
        yaml_lines.append("outputs:")
        for k, v in skill.contract.outputs.items():
            yaml_lines.append(f"  {k}: {v}")
        yaml_lines.append("---\n")
        full_content = "\n".join(yaml_lines) + skill.instructions
        out_path.write_text(full_content, encoding="utf-8")
        return out_path

    def export_manifest(self, out_path: Optional[Path] = None) -> Dict[str, Any]:
        """Export canonical versioned skills manifest to JSON."""
        target_path = out_path or (Path(__file__).parent / "manifest.json")
        skills_data = []
        for s in self.list_skills(include_revoked=True):
            d = s.to_dict()
            # Normalize source_uri to relative path if within repository
            if "skills/" in d["source_uri"]:
                rel = d["source_uri"].split("core/kstack/")[-1]
                d["source_uri"] = f"core/kstack/{rel}"
            skills_data.append(d)

        manifest = {
            "version": "1.0.0",
            "format": "kstack_skills_manifest_v1",
            "skills_count": len(skills_data),
            "generated_at_utc": time.time(),
            "skills": skills_data,
        }
        target_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return manifest

    def verify_manifest(self, manifest_path: Optional[Path] = None) -> Tuple[bool, List[str]]:
        """Verify all skills match their cryptographic digest recorded in manifest.json."""
        target_path = manifest_path or (Path(__file__).parent / "manifest.json")
        if not target_path.exists():
            return False, [f"Manifest file not found: {target_path}"]

        try:
            data = json.loads(target_path.read_text(encoding="utf-8"))
        except Exception as e:
            return False, [f"Failed to parse manifest JSON: {e}"]

        errors: List[str] = []
        manifest_skills = {item["name"]: item for item in data.get("skills", [])}

        for skill in self.list_skills(include_revoked=False):
            if skill.name not in manifest_skills:
                errors.append(f"Skill '{skill.name}' is missing from manifest.json")
                continue
            expected_digest = manifest_skills[skill.name].get("digest_sha256")
            actual_digest = skill.calculate_digest()
            if actual_digest != expected_digest:
                errors.append(
                    f"Digest mismatch for '{skill.name}': manifest={expected_digest}, actual={actual_digest}"
                )

        return (len(errors) == 0, errors)

    def execute_skill(
        self,
        name: str,
        actor: str,
        inputs: Dict[str, Any],
        handler: Optional[Any] = None,
    ) -> SkillExecutionProof:
        skill = self.get_skill(name)
        if not skill:
            raise KeyError(f"Skill '{name}' not found")
        if skill.revoked:
            raise PermissionError(f"Skill '{name}' is revoked: {skill.revocation_reason}")

        t0 = time.time()
        outputs: Dict[str, Any] = {}
        success = True
        try:
            if handler:
                outputs = handler(inputs)
            else:
                outputs = {"status": "executed", "echo_inputs": inputs}
        except Exception as e:
            success = False
            outputs = {"error": str(e)}

        duration_ms = round((time.time() - t0) * 1000, 2)
        exec_id = f"ksexec_{name.replace('/', '_')}_{int(t0 * 1000)}"
        proof = SkillExecutionProof(
            execution_id=exec_id,
            skill_name=skill.name,
            skill_digest_sha256=skill.digest_sha256,
            actor=actor,
            inputs=inputs,
            outputs=outputs,
            permissions_used=list(skill.permissions),
            success=success,
            duration_ms=duration_ms,
            timestamp_utc=t0,
        )
        proof.seal()
        return proof


# Singleton instance
kstack_registry = KStackRegistry()
