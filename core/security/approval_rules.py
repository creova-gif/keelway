"""Standing ("allow always") approvals: one tool plus one path pattern or exact command, per workspace."""
from __future__ import annotations

import fnmatch
import json
import os
import secrets
import time
from functools import lru_cache
from dataclasses import asdict, dataclass, fields
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List, Optional, Tuple

PATH_TOOLS = {"edit_file", "write_file"}
COMMAND_TOOLS = {"run_command"}
SCOPABLE_TOOLS = PATH_TOOLS | COMMAND_TOOLS
# Keelway's own state (including this rule file) and git internals never get standing approvals.
PROTECTED_PREFIXES = (".keelway", ".kora", ".git")


class ApprovalRuleError(ValueError):
    """Raised when a standing approval would be unscoped or unsafe."""


@dataclass
class ApprovalRule:
    id: str
    tool_name: str
    scope: str
    created_by: str
    created_at: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _normalize_path(path: Any) -> Optional[str]:
    p = PurePosixPath(str(path or "").replace("\\", "/"))
    if p.is_absolute() or ".." in p.parts:
        return None
    text = str(p)
    return None if text in ("", ".") else text


def _is_protected(path: str) -> bool:
    """Any `.keelway`/`.kora`/`.git` segment, at any depth (nested repos and submodules included)."""
    return any(part in PROTECTED_PREFIXES for part in PurePosixPath(path).parts)


def validate_scope(tool_name: str, scope: Any) -> str:
    """Return the normalised scope, or raise if it is not narrow enough to remember."""
    if tool_name not in SCOPABLE_TOOLS:
        raise ApprovalRuleError(f"'{tool_name}' cannot have a standing approval.")
    text = str(scope or "").strip()
    if tool_name in COMMAND_TOOLS:
        if not text:
            raise ApprovalRuleError("A command rule needs the exact command.")
        return text
    norm = _normalize_path(text)
    if norm is None:
        raise ApprovalRuleError("Path rules must be relative to the workspace and stay inside it.")
    if not norm.strip("*?[]/."):
        raise ApprovalRuleError("That pattern matches every file; scope it to a file or folder.")
    if _is_protected(norm):
        raise ApprovalRuleError("Keelway and git internals always ask first.")
    return norm


def _glob_match(path_parts: tuple, pattern_parts: tuple) -> bool:
    """Segment-wise glob: `*` stays inside one directory, a `**` segment spans any number of them."""
    pat = tuple(p for i, p in enumerate(pattern_parts) if not (p == "**" and i and pattern_parts[i - 1] == "**"))

    @lru_cache(maxsize=None)
    def match(i: int, j: int) -> bool:
        if j == len(pat):
            return i == len(path_parts)
        if pat[j] == "**":
            return match(i, j + 1) or (i < len(path_parts) and match(i + 1, j))
        return i < len(path_parts) and fnmatch.fnmatchcase(path_parts[i], pat[j]) and match(i + 1, j + 1)

    return match(0, 0)


def rule_matches(rule: ApprovalRule, tool_name: str, arguments: Dict[str, Any]) -> bool:
    if rule.tool_name != tool_name:
        return False
    if tool_name in COMMAND_TOOLS:
        return str(arguments.get("command", "")).strip() == rule.scope
    path = _normalize_path(arguments.get("path"))
    return path is not None and not _is_protected(path) and _glob_match(PurePosixPath(path).parts, PurePosixPath(rule.scope).parts)


class ApprovalRuleStore:
    """Rules live in <workspace>/.keelway/approval_rules.json so they are local and reviewable."""

    def __init__(self, workspace_root: Any):
        self.path = Path(workspace_root) / ".keelway" / "approval_rules.json"

    def list(self) -> List[ApprovalRule]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return []
        raw_rules = data.get("rules") if isinstance(data, dict) else None
        if not isinstance(raw_rules, list):
            return []
        names = [f.name for f in fields(ApprovalRule)]
        rules = []
        for raw in raw_rules:
            try:
                rules.append(ApprovalRule(**{name: raw[name] for name in names}))
            except (KeyError, TypeError):
                continue
        return rules

    def _save(self, rules: List[ApprovalRule]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(f"{self.path.name}.tmp{os.getpid()}")
        tmp.write_text(json.dumps({"version": 1, "rules": [r.to_dict() for r in rules]}, indent=2), encoding="utf-8")
        os.replace(tmp, self.path)

    def add(self, tool_name: str, scope: Any, created_by: str) -> Tuple[ApprovalRule, bool]:
        """Returns (rule, created); an identical existing rule is returned with created=False."""
        scope = validate_scope(tool_name, scope)
        rules = self.list()
        for rule in rules:
            if rule.tool_name == tool_name and rule.scope == scope:
                return rule, False
        rule = ApprovalRule(id=f"rule_{secrets.token_hex(6)}", tool_name=tool_name, scope=scope, created_by=created_by, created_at=time.time())
        self._save(rules + [rule])
        return rule, True

    def remove(self, rule_id: str) -> Optional[ApprovalRule]:
        rules = self.list()
        gone = next((r for r in rules if r.id == rule_id), None)
        if gone:
            self._save([r for r in rules if r.id != rule_id])
        return gone

    def _resolved_relative(self, path: Any) -> Optional[str]:
        """The path the filesystem will actually touch, relative to the workspace (symlinks followed)."""
        norm = _normalize_path(path)
        if norm is None:
            return None
        root = self.path.parent.parent.resolve()
        try:
            return (root / norm).resolve().relative_to(root).as_posix()
        except (ValueError, OSError):
            return None

    def match(self, tool_name: str, arguments: Dict[str, Any]) -> Optional[ApprovalRule]:
        if tool_name in PATH_TOOLS:
            real = self._resolved_relative(arguments.get("path"))
            if real is None or real == "." or _is_protected(real):
                return None
            checks = [arguments, {**arguments, "path": real}]
        else:
            checks = [arguments]
        return next((r for r in self.list() if all(rule_matches(r, tool_name, a) for a in checks)), None)
