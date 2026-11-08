"""
KBrain Knowledge Store with ACL filtering, revisions, provenance, and DLP scanner.
"""

from __future__ import annotations

import json
import re
import time
import uuid
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional, Set, Tuple

from core.kbrain.models import FactRecord, FactStatus, KnowledgeScope


SCOPE_HIERARCHY = {
    KnowledgeScope.LOCAL_SESSION: 1,
    KnowledgeScope.PROJECT: 2,
    KnowledgeScope.TEAM: 3,
    KnowledgeScope.ORG: 4,
}

SECRET_PATTERNS = [
    re.compile(r"sk-(ant-|proj-)?[a-zA-Z0-9_\-]{20,}", re.IGNORECASE),
    re.compile(r"gh[pousr]_[a-zA-Z0-9]{20,}", re.IGNORECASE),
    re.compile(r"bearer\s+[a-zA-Z0-9_\-\.]{20,}", re.IGNORECASE),
    re.compile(r"-----BEGIN (RSA|EC|OPENSSH|DSA|PGP) PRIVATE KEY-----", re.IGNORECASE),
    re.compile(r"(password|secret|token)\s*[:=]\s*['\"][^'\"]{6,}['\"]", re.IGNORECASE),
]


class SecretLeakDetectedError(ValueError):
    """Raised when knowledge fact contains raw secrets or credentials."""
    pass


class KBrainStore:
    """Thread-safe, scope-governed knowledge and fact memory engine."""

    def __init__(self, persistence_path: Optional[Path] = None):
        self._lock = Lock()
        self._facts: Dict[str, FactRecord] = {}
        self.persistence_path = persistence_path or Path(".keelway/kbrain/facts.json")
        if self.persistence_path and self.persistence_path.exists():
            self._load()

    def _scan_for_secrets(self, text: str) -> None:
        for pat in SECRET_PATTERNS:
            if pat.search(text):
                raise SecretLeakDetectedError("Security violation: Statement contains potential raw secret or credential.")

    def _load(self) -> None:
        try:
            with open(self.persistence_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for item in data.get("facts", []):
                    item["scope"] = KnowledgeScope(item["scope"])
                    item["status"] = FactStatus(item["status"])
                    fact = FactRecord(**item)
                    self._facts[fact.id] = fact
        except Exception:
            pass

    def _save(self) -> None:
        if not self.persistence_path:
            return
        try:
            self.persistence_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.persistence_path, "w", encoding="utf-8") as f:
                json.dump({"facts": [f.to_dict() for f in self._facts.values()]}, f, indent=2)
        except Exception:
            pass

    def record_fact(
        self,
        key: str,
        statement: str,
        scope: KnowledgeScope = KnowledgeScope.PROJECT,
        provenance_uri: str = "",
        provenance_reason: str = "",
        created_by: str = "system",
        auto_approve: bool = False,
    ) -> FactRecord:
        """Record a new scope-governed fact with secret verification and conflict checks."""
        self._scan_for_secrets(statement)

        fact_id = f"kb_fact_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"
        status = FactStatus.APPROVED if auto_approve else FactStatus.PROPOSED
        approved_by = created_by if auto_approve else None

        fact = FactRecord(
            id=fact_id,
            scope=scope,
            key=key,
            statement=statement,
            provenance_uri=provenance_uri or "user_instruction",
            provenance_reason=provenance_reason or "Direct user assertion",
            status=status,
            revision=1,
            created_by=created_by,
            approved_by=approved_by,
        )
        fact.sha256 = fact.calculate_sha256()

        with self._lock:
            # Check for conflicting active statements with the same key
            conflicts = [
                f for f in self._facts.values()
                if f.key == key
                and f.scope == scope
                and f.status in (FactStatus.APPROVED, FactStatus.PROPOSED)
                and f.statement.strip().lower() != statement.strip().lower()
            ]
            if conflicts:
                fact.status = FactStatus.CONFLICT

            self._facts[fact.id] = fact
            self._save()

        return fact

    def approve_fact(self, fact_id: str, approved_by: str) -> FactRecord:
        with self._lock:
            fact = self._facts.get(fact_id)
            if not fact:
                raise KeyError(f"Fact '{fact_id}' not found")
            fact.status = FactStatus.APPROVED
            fact.approved_by = approved_by
            fact.updated_at_utc = time.time()
            self._save()
            return fact

    def correct_fact(
        self,
        fact_id: str,
        new_statement: str,
        reason: str,
        user: str,
    ) -> FactRecord:
        """Create a new revision correcting an existing fact and marking old as CORRECTED."""
        self._scan_for_secrets(new_statement)

        with self._lock:
            old_fact = self._facts.get(fact_id)
            if not old_fact:
                raise KeyError(f"Fact '{fact_id}' not found")

            old_fact.status = FactStatus.CORRECTED
            new_id = f"kb_fact_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"
            old_fact.superseded_by = new_id

            new_fact = FactRecord(
                id=new_id,
                scope=old_fact.scope,
                key=old_fact.key,
                statement=new_statement,
                provenance_uri=old_fact.provenance_uri,
                provenance_reason=f"Corrected by {user}: {reason}",
                status=FactStatus.APPROVED,
                revision=old_fact.revision + 1,
                created_by=user,
                approved_by=user,
            )
            new_fact.sha256 = new_fact.calculate_sha256()
            self._facts[new_id] = new_fact
            self._save()
            return new_fact

    def withdraw_fact(self, fact_id: str, reason: str, user: str) -> FactRecord:
        """Mark a fact as withdrawn so it is excluded from future retrieval."""
        with self._lock:
            fact = self._facts.get(fact_id)
            if not fact:
                raise KeyError(f"Fact '{fact_id}' not found")
            fact.status = FactStatus.WITHDRAWN
            fact.provenance_reason += f" | Withdrawn by {user}: {reason}"
            fact.updated_at_utc = time.time()
            self._save()
            return fact

    def promote_scope(self, fact_id: str, target_scope: KnowledgeScope, user: str) -> FactRecord:
        """Explicitly share a fact to a higher scope (e.g. project -> team -> org)."""
        with self._lock:
            fact = self._facts.get(fact_id)
            if not fact:
                raise KeyError(f"Fact '{fact_id}' not found")
            curr_level = SCOPE_HIERARCHY.get(fact.scope, 1)
            target_level = SCOPE_HIERARCHY.get(target_scope, 1)
            if target_level <= curr_level:
                raise ValueError(f"Cannot promote fact from scope '{fact.scope.value}' to '{target_scope.value}'")
            fact.scope = target_scope
            fact.provenance_reason += f" | Promoted to {target_scope.value} by {user}"
            fact.updated_at_utc = time.time()
            self._save()
            return fact

    def query_facts(
        self,
        max_scope: KnowledgeScope = KnowledgeScope.PROJECT,
        key: Optional[str] = None,
        search_text: Optional[str] = None,
        include_unapproved: bool = False,
    ) -> List[FactRecord]:
        """Query facts strictly respecting ACL scope boundary."""
        allowed_level = SCOPE_HIERARCHY.get(max_scope, 1)
        with self._lock:
            results = []
            for fact in self._facts.values():
                fact_level = SCOPE_HIERARCHY.get(fact.scope, 1)
                # ACL filter: fact scope must be accessible at allowed level
                if fact_level > allowed_level:
                    continue
                # Status filter: omit withdrawn
                if fact.status == FactStatus.WITHDRAWN:
                    continue
                if not include_unapproved and fact.status not in (FactStatus.APPROVED, FactStatus.PROPOSED):
                    continue
                if key and fact.key != key:
                    continue
                if search_text:
                    st = search_text.lower()
                    if st not in fact.statement.lower() and st not in fact.key.lower():
                        continue
                results.append(fact)
            return sorted(results, key=lambda f: (f.key, f.revision), reverse=True)

    def export_scope(self, scope: KnowledgeScope) -> str:
        with self._lock:
            facts = [f.to_dict() for f in self._facts.values() if f.scope == scope and f.status != FactStatus.WITHDRAWN]
            return json.dumps({"scope": scope.value, "count": len(facts), "facts": facts}, indent=2)

    def delete_scope(self, scope: KnowledgeScope) -> int:
        with self._lock:
            to_delete = [fid for fid, f in self._facts.items() if f.scope == scope]
            for fid in to_delete:
                del self._facts[fid]
            self._save()
            return len(to_delete)


# Singleton instance
kbrain_store = KBrainStore()
