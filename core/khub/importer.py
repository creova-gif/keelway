"""
KHub Universal Skills Importer.
Safely imports skills from .claude/skills, .cursor/skills, .cursor/rules, .agents/skills, .codex/skills.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple

from core.khub.models import ImportedSkill, SkillSourceType


class KHubImporter:
    """Universal Skills & Tools Importer with read-only ingestion, rule separation, and drift tracking."""

    def __init__(self, pinned_dir: Optional[Path] = None):
        self._lock = Lock()
        self.pinned_dir = pinned_dir or Path(".keelway/khub/pinned")
        self._imported: Dict[str, ImportedSkill] = {}

    def scan_directory(self, root_dir: Path) -> List[ImportedSkill]:
        """Scan a repository or config root for portable skills and rules in read-only mode."""
        found: List[ImportedSkill] = []
        if not root_dir.exists():
            return found

        scan_targets = [
            (".claude/skills", SkillSourceType.CLAUDE_SKILL, False),
            (".cursor/skills", SkillSourceType.CURSOR_SKILL, False),
            (".cursor/rules", SkillSourceType.CURSOR_RULE, True),  # Rule-only, not executable skill!
            (".agents/skills", SkillSourceType.AGENTS_SKILL, False),
            (".codex/skills", SkillSourceType.CODEX_SKILL, False),
        ]

        for rel_path, src_type, is_rule in scan_targets:
            target_path = root_dir / rel_path
            if target_path.exists() and target_path.is_dir():
                for item in target_path.rglob("*.md"):
                    if item.is_file():
                        try:
                            skill = self.import_file(item, src_type=src_type, is_rule_only=is_rule)
                            found.append(skill)
                        except Exception:
                            pass
        return found

    def import_file(
        self,
        file_path: Path,
        src_type: SkillSourceType = SkillSourceType.CLAUDE_SKILL,
        is_rule_only: bool = False,
    ) -> ImportedSkill:
        """Import a single skill or rule file in read-only mode with SHA-256 fingerprint."""
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        content = file_path.read_text(encoding="utf-8")
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        name = file_path.stem

        # Assess permissions declared in frontmatter or text
        permissions: List[str] = ["read"]
        if "execute" in content.lower() or "run_command" in content.lower():
            permissions.append("execute_restricted")
        if "push" in content.lower() or "merge" in content.lower() or "deploy" in content.lower():
            permissions.append("external_privileged")

        skill_id = f"{src_type.value}_{name}_{digest[:10]}"
        imported = ImportedSkill(
            id=skill_id,
            name=name,
            source_type=src_type,
            source_path=str(file_path.resolve()),
            content=content,
            digest_sha256=digest,
            is_rule_only=is_rule_only,
            permissions_required=permissions,
            version_pinned=True,
            upstream_has_drift=False,
            approved_by_user=False,  # Requires explicit human approval before execution!
        )

        with self._lock:
            self._imported[imported.id] = imported

            # Persist pinned snapshot
            if self.pinned_dir:
                try:
                    self.pinned_dir.mkdir(parents=True, exist_ok=True)
                    pin_file = self.pinned_dir / f"{skill_id}.pin.md"
                    pin_file.write_text(content, encoding="utf-8")
                except Exception:
                    pass

        return imported

    def approve_imported_skill(self, skill_id: str) -> bool:
        """Explicit human approval enabling an imported skill to be executed."""
        with self._lock:
            skill = self._imported.get(skill_id)
            if not skill:
                raise KeyError(f"Imported skill '{skill_id}' not found")
            if skill.is_rule_only:
                raise ValueError("Cannot execute a rule-only (.cursor/rules) definition as an executable skill.")
            skill.approved_by_user = True
            return True

    def check_upstream_drift(self, skill_id: str) -> Tuple[bool, str, str]:
        """Check whether the upstream source file on disk has changed since pinning."""
        with self._lock:
            skill = self._imported.get(skill_id)
            if not skill:
                raise KeyError(f"Imported skill '{skill_id}' not found")

            src_path = Path(skill.source_path)
            if not src_path.exists():
                skill.upstream_has_drift = True
                return (True, skill.digest_sha256, "FILE_DELETED")

            current_content = src_path.read_text(encoding="utf-8")
            current_digest = hashlib.sha256(current_content.encode("utf-8")).hexdigest()
            has_drift = (current_digest != skill.digest_sha256)
            skill.upstream_has_drift = has_drift
            return (has_drift, skill.digest_sha256, current_digest)

    def list_imported(self) -> List[ImportedSkill]:
        with self._lock:
            return list(self._imported.values())

    def get_imported(self, skill_id: str) -> Optional[ImportedSkill]:
        with self._lock:
            return self._imported.get(skill_id)


# Singleton instance
khub_importer = KHubImporter()
