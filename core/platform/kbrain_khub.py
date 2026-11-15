"""
Phase 10A Sovereign KBrain Hybrid Memory Engine & KHub Air-Gapped Registry (`core.platform.kbrain_khub`).

Persists scope-hierarchic (`local_session < project < team < org`) workspace facts with fail-closed DLP
secret rejection, deterministic conflict detection, P-10 resolution superseding, Hybrid BM25 + Character
3-Gram Cosine Similarity retrieval (`platform_kbrain_facts`), and KHub cryptographic air-gapped `.tar.gz`
mirror roundtrip verification receipts (`platform_khub_mirrors`) in SQLite WAL (`platform_runtime.db`).
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import sqlite3
import tempfile
import threading
from typing import Any, Dict, List, Optional, Pattern, Sequence, Tuple, Union
import uuid

from core.khub.sync import KHubMirror
from core.platform.vault import _resolve_sqlite_target

SCOPE_HIERARCHY: Dict[str, int] = {
    "local_session": 1,
    "project": 2,
    "team": 3,
    "org": 4,
}
VALID_FACT_RESOLUTIONS = frozenset({"approve", "reject"})
_WORKSPACE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_SKILL_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_TOKEN_RE = re.compile(r"[a-z0-9]+")

SECRET_PATTERNS: Tuple[Tuple[str, Pattern[str]], ...] = (
    ("OPENAI_OR_ANTHROPIC_KEY", re.compile(r"\bsk-(?:ant-|proj-|live-|test-)?[A-Za-z0-9_-]{12,}")),
    ("GITHUB_TOKEN", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{16,}")),
    ("AWS_ACCESS_KEY_ID", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("BEARER_TOKEN", re.compile(r"\bBearer\s+[A-Za-z0-9._\-~+/]{16,}=*")),
    ("PEM_PRIVATE_KEY", re.compile(r"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----")),
    (
        "PASSWORD_ASSIGNMENT",
        re.compile(
            r"(?i)\b(?:password|passwd|api[_-]?key|apikey|secret|token|client[_-]?secret)\s*[:=]\s*['\"]?[^\s'\",;]{6,}"
        ),
    ),
    ("DB_URI_CREDENTIALS", re.compile(r"(?i)(?:postgres|postgresql|mysql|mongodb|redis)://[^:\s/]+:[^@\s/]+@")),
    ("SLACK_TOKEN", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}")),
)

_KBRAIN_KHUB_SCHEMA_SQL = (
    "CREATE TABLE IF NOT EXISTS platform_kbrain_facts ("
    "id TEXT NOT NULL, workspace_id TEXT NOT NULL, key TEXT NOT NULL, statement TEXT NOT NULL, "
    "scope TEXT NOT NULL, status TEXT NOT NULL, conflict_with_fact_id TEXT, provenance_uri TEXT NOT NULL, "
    "tags_json TEXT NOT NULL, created_by TEXT NOT NULL, fact_sha256 TEXT NOT NULL, created_at TEXT NOT NULL, "
    "resolved_by TEXT, resolved_at TEXT, PRIMARY KEY(workspace_id, id)); "
    "CREATE INDEX IF NOT EXISTS idx_platform_kbrain_facts_lookup "
    "ON platform_kbrain_facts(workspace_id, scope, key, status); "
    "CREATE TABLE IF NOT EXISTS platform_khub_mirrors ("
    "id INTEGER PRIMARY KEY AUTOINCREMENT, workspace_id TEXT NOT NULL, mirror_format TEXT NOT NULL, "
    "skills_verified INTEGER NOT NULL, catalog_digest_sha256 TEXT NOT NULL, verified_at TEXT NOT NULL); "
    "CREATE INDEX IF NOT EXISTS idx_platform_khub_mirrors_ws "
    "ON platform_khub_mirrors(workspace_id, verified_at);"
)


class SecretLeakDetectedError(ValueError):
    """Raised fail-closed when a KBrain fact contains secret material; never echoes raw secrets."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _clean_workspace_id(workspace_id: str) -> str:
    clean = str(workspace_id or "").strip()
    if not clean or not _WORKSPACE_ID_RE.fullmatch(clean):
        raise ValueError(f"Invalid workspace_id '{workspace_id}'.")
    return clean


def resolve_kbrain_db_target(db_path: Optional[Union[str, Path]] = None) -> Tuple[Union[str, Path], str]:
    """Resolve SQLite WAL target honoring explicit `db_path`, `KEELWAY_RUNTIME_DB_PATH`, `KEELWAY_STATE_DIR`, or `HOME`."""
    if db_path is not None:
        return _resolve_sqlite_target(db_path)
    runtime_override = os.environ.get("KEELWAY_RUNTIME_DB_PATH", "").strip()
    if runtime_override:
        return _resolve_sqlite_target(runtime_override)
    state_dir = os.environ.get("KEELWAY_STATE_DIR", "").strip()
    if state_dir:
        return _resolve_sqlite_target(Path(state_dir).expanduser() / "platform_runtime.db")
    return _resolve_sqlite_target(None)


def _scan_for_secrets(field_name: str, text: str) -> None:
    for pattern_name, pattern in SECRET_PATTERNS:
        if pattern.search(text):
            raise SecretLeakDetectedError(
                f"DLP blocked secret pattern '{pattern_name}' in KBrain field '{field_name}'; raw secrets are never stored."
            )


def _tokenize_terms(text: str) -> List[str]:
    return _TOKEN_RE.findall(text.lower())


def _char_trigram_counts(text: str) -> Counter[str]:
    tokens = _tokenize_terms(text)
    grams: List[str] = []
    for tok in tokens:
        if len(tok) < 3:
            grams.append(tok)
        else:
            grams.extend(tok[i : i + 3] for i in range(len(tok) - 2))
    return Counter(grams)


def _cosine_similarity(vec_a: Counter[str], vec_b: Counter[str]) -> float:
    if not vec_a or not vec_b:
        return 0.0
    common = set(vec_a.keys()) & set(vec_b.keys())
    if not common:
        return 0.0
    dot = sum(vec_a[g] * vec_b[g] for g in common)
    norm_a = math.sqrt(sum(v * v for v in vec_a.values()))
    norm_b = math.sqrt(sum(v * v for v in vec_b.values()))
    if norm_a <= 0.0 or norm_b <= 0.0:
        return 0.0
    return min(1.0, max(0.0, dot / (norm_a * norm_b)))


class _SQLiteWalBase:
    """Shared dynamic SQLite WAL connection lifecycle for KBrain and KHub runtime stores."""

    def __init__(self, db_path: Optional[Union[str, Path]] = None) -> None:
        self._lock = threading.RLock()
        self._explicit_db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._active_target: Optional[str] = None
        self._db_path: Union[str, Path] = ":memory:"
        self._closed = False
        with self._lock:
            self._ensure_conn()

    def _ensure_conn(self) -> sqlite3.Connection:
        resolved_path, connect_target = resolve_kbrain_db_target(self._explicit_db_path)
        if self._conn is not None and not self._closed and self._active_target == connect_target:
            return self._conn
        if self._conn is not None and not self._closed:
            self._conn.close()
        conn = sqlite3.connect(connect_target, check_same_thread=False, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        with conn:
            conn.executescript(_KBRAIN_KHUB_SCHEMA_SQL)
        self._conn, self._active_target, self._db_path, self._closed = conn, connect_target, resolved_path, False
        return conn

    @property
    def db_path(self) -> Union[str, Path]:
        with self._lock:
            if self._explicit_db_path is None and not self._closed:
                self._ensure_conn()
            return self._db_path

    def close(self) -> None:
        with self._lock:
            if self._conn is not None and not self._closed:
                self._conn.close()
                self._closed = True


class SQLiteKBrainEngine(_SQLiteWalBase):
    """Scope-aware KBrain hybrid BM25 + 3-gram cosine memory engine with fail-closed DLP & P-10 conflict governance."""

    @staticmethod
    def _row_to_fact(row: sqlite3.Row) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "id": str(row["id"]),
            "workspace_id": str(row["workspace_id"]),
            "key": str(row["key"]),
            "statement": str(row["statement"]),
            "scope": str(row["scope"]),
            "status": str(row["status"]),
            "conflict_with_fact_id": str(row["conflict_with_fact_id"]) if row["conflict_with_fact_id"] else None,
            "provenance_uri": str(row["provenance_uri"]),
            "tags": json.loads(str(row["tags_json"])),
            "created_by": str(row["created_by"]),
            "fact_sha256": str(row["fact_sha256"]),
            "created_at": str(row["created_at"]),
        }
        if row["resolved_by"] is not None:
            out["resolved_by"] = str(row["resolved_by"])
        if row["resolved_at"] is not None:
            out["resolved_at"] = str(row["resolved_at"])
        return out

    def record_fact(
        self,
        workspace_id: str,
        key: str,
        statement: str,
        scope: str = "project",
        provenance_uri: str = "workspace",
        tags: Optional[Sequence[str]] = None,
        created_by: str = "owner",
        auto_approve: bool = True,
    ) -> Dict[str, Any]:
        ws = _clean_workspace_id(workspace_id)
        clean_key = str(key or "").strip()
        clean_stmt = str(statement or "").strip()
        clean_scope = str(scope or "").strip().lower()
        clean_prov = str(provenance_uri or "workspace").strip() or "workspace"
        clean_creator = str(created_by or "owner").strip() or "owner"

        if not clean_key:
            raise ValueError("KBrain fact 'key' must be non-empty.")
        if not clean_stmt:
            raise ValueError("KBrain fact 'statement' must be non-empty.")
        if clean_scope not in SCOPE_HIERARCHY:
            raise ValueError(f"Unsupported KBrain scope '{scope}'. Expected one of {list(SCOPE_HIERARCHY)}.")

        _scan_for_secrets("key", clean_key)
        _scan_for_secrets("statement", clean_stmt)
        _scan_for_secrets("provenance_uri", clean_prov)

        clean_tags: List[str] = []
        for raw_tag in tags or []:
            tag_val = str(raw_tag or "").strip()
            if tag_val:
                _scan_for_secrets("tags", tag_val)
                if tag_val not in clean_tags:
                    clean_tags.append(tag_val)

        fact_id = f"fact-{uuid.uuid4().hex[:12]}"
        created_at = _utc_now()
        canonical_payload = _canonical_json(
            {
                "workspace_id": ws,
                "key": clean_key,
                "statement": clean_stmt,
                "scope": clean_scope,
                "provenance_uri": clean_prov,
                "tags": clean_tags,
            }
        )
        fact_sha256 = "sha256:" + hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()
        norm_stmt = clean_stmt.lower()

        with self._lock:
            conn = self._ensure_conn()
            active_rows = conn.execute(
                "SELECT id, statement FROM platform_kbrain_facts "
                "WHERE workspace_id=? AND scope=? AND key=? AND status IN ('approved', 'proposed') "
                "ORDER BY created_at DESC, rowid DESC",
                (ws, clean_scope, clean_key),
            ).fetchall()

            conflict_id: Optional[str] = None
            for existing in active_rows:
                if str(existing["statement"]).strip().lower() != norm_stmt:
                    conflict_id = str(existing["id"])
                    break

            if conflict_id is not None:
                status_val = "conflict"
            else:
                status_val = "approved" if bool(auto_approve) else "proposed"

            with conn:
                conn.execute(
                    "INSERT INTO platform_kbrain_facts ("
                    "id, workspace_id, key, statement, scope, status, conflict_with_fact_id, "
                    "provenance_uri, tags_json, created_by, fact_sha256, created_at, resolved_by, resolved_at"
                    ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL)",
                    (
                        fact_id,
                        ws,
                        clean_key,
                        clean_stmt,
                        clean_scope,
                        status_val,
                        conflict_id,
                        clean_prov,
                        _canonical_json(clean_tags),
                        clean_creator,
                        fact_sha256,
                        created_at,
                    ),
                )
            inserted = conn.execute(
                "SELECT * FROM platform_kbrain_facts WHERE workspace_id=? AND id=?",
                (ws, fact_id),
            ).fetchone()
        return self._row_to_fact(inserted)  # type: ignore[arg-type]

    def search_facts(
        self,
        workspace_id: str,
        query: str = "",
        max_scope: str = "org",
        include_conflicts: bool = False,
        limit: int = 10,
    ) -> Dict[str, Any]:
        ws = _clean_workspace_id(workspace_id)
        clean_max_scope = str(max_scope or "").strip().lower()
        if clean_max_scope not in SCOPE_HIERARCHY:
            raise ValueError(f"Unsupported KBrain max_scope '{max_scope}'. Expected one of {list(SCOPE_HIERARCHY)}.")
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1 or limit > 200:
            raise ValueError("KBrain search 'limit' must be an integer between 1 and 200.")

        ceiling = SCOPE_HIERARCHY[clean_max_scope]
        allowed_scopes = [s for s, lvl in SCOPE_HIERARCHY.items() if lvl <= ceiling]
        allowed_statuses = ("approved", "proposed", "conflict") if include_conflicts else ("approved",)
        scope_placeholders = ",".join("?" for _ in allowed_scopes)
        status_placeholders = ",".join("?" for _ in allowed_statuses)

        with self._lock:
            rows = self._ensure_conn().execute(
                f"SELECT * FROM platform_kbrain_facts "
                f"WHERE workspace_id=? AND scope IN ({scope_placeholders}) AND status IN ({status_placeholders}) "
                f"ORDER BY created_at DESC, rowid DESC",
                (ws, *allowed_scopes, *allowed_statuses),
            ).fetchall()

        facts = [self._row_to_fact(r) for r in rows]
        raw_query = str(query or "")
        if raw_query.strip() == "":
            results = [
                {**fact, "bm25_score": 1.0, "ngram_cosine_score": 1.0, "hybrid_score": 1.0}
                for fact in facts
            ]
            return {
                "workspace_id": ws,
                "query": raw_query,
                "max_scope": clean_max_scope,
                "total_matches": len(results),
                "results": results[:limit],
            }

        if not facts:
            return {
                "workspace_id": ws,
                "query": raw_query,
                "max_scope": clean_max_scope,
                "total_matches": 0,
                "results": [],
            }

        q_terms = _tokenize_terms(raw_query)
        q_unique = list(dict.fromkeys(q_terms))
        q_trigrams = _char_trigram_counts(raw_query)

        doc_texts = [f"{f['key']} {f['statement']} {' '.join(f['tags'])}" for f in facts]
        doc_tokens = [_tokenize_terms(t) for t in doc_texts]
        doc_term_freqs = [Counter(toks) for toks in doc_tokens]
        doc_lengths = [len(toks) for toks in doc_tokens]
        n_docs = len(facts)
        avgdl = max(1.0, sum(doc_lengths) / n_docs)

        k1 = 1.5
        b = 0.75
        df_map: Dict[str, int] = {
            term: sum(1 for tf in doc_term_freqs if tf.get(term, 0) > 0)
            for term in q_unique
        }

        raw_bm25_scores: List[float] = []
        for idx, tf in enumerate(doc_term_freqs):
            dl = doc_lengths[idx]
            score = 0.0
            for term in q_unique:
                freq = tf.get(term, 0)
                if freq <= 0:
                    continue
                df = df_map[term]
                idf = math.log(1.0 + (n_docs - df + 0.5) / (df + 0.5))
                denom = freq + k1 * (1.0 - b + b * (dl / avgdl))
                score += idf * ((freq * (k1 + 1.0)) / denom)
            raw_bm25_scores.append(score)

        max_bm25 = max(raw_bm25_scores) if raw_bm25_scores else 0.0
        scored_results: List[Dict[str, Any]] = []
        for idx, fact in enumerate(facts):
            bm25_norm = round((raw_bm25_scores[idx] / max_bm25) if max_bm25 > 0.0 else 0.0, 4)
            ngram_cos = round(_cosine_similarity(q_trigrams, _char_trigram_counts(doc_texts[idx])), 4)
            hybrid = round(0.65 * bm25_norm + 0.35 * ngram_cos, 4)
            if hybrid > 0.0:
                scored_results.append(
                    {
                        **fact,
                        "bm25_score": bm25_norm,
                        "ngram_cosine_score": ngram_cos,
                        "hybrid_score": hybrid,
                    }
                )

        scored_results.sort(key=lambda item: (item["hybrid_score"], item["bm25_score"], item["created_at"]), reverse=True)
        return {
            "workspace_id": ws,
            "query": raw_query,
            "max_scope": clean_max_scope,
            "total_matches": len(scored_results),
            "results": scored_results[:limit],
        }

    def resolve_fact(
        self,
        workspace_id: str,
        fact_id: str,
        resolution: str,
        approver_id: str = "owner",
    ) -> Dict[str, Any]:
        ws = _clean_workspace_id(workspace_id)
        clean_id = str(fact_id or "").strip()
        clean_res = str(resolution or "").strip().lower()
        clean_approver = str(approver_id or "owner").strip() or "owner"

        if clean_res not in VALID_FACT_RESOLUTIONS:
            raise ValueError(f"Unsupported resolution '{resolution}'. Expected 'approve' or 'reject'.")
        if not clean_id:
            raise KeyError("KBrain 'fact_id' must be non-empty.")

        now = _utc_now()
        with self._lock:
            conn = self._ensure_conn()
            existing = conn.execute(
                "SELECT * FROM platform_kbrain_facts WHERE workspace_id=? AND id=?",
                (ws, clean_id),
            ).fetchone()
            if existing is None:
                raise KeyError(f"KBrain fact '{clean_id}' not found in workspace '{ws}'.")

            with conn:
                if clean_res == "approve":
                    conn.execute(
                        "UPDATE platform_kbrain_facts SET status='superseded', resolved_by=?, resolved_at=? "
                        "WHERE workspace_id=? AND scope=? AND key=? AND id!=? AND status IN ('approved', 'proposed', 'conflict')",
                        (clean_approver, now, ws, str(existing["scope"]), str(existing["key"]), clean_id),
                    )
                    conn.execute(
                        "UPDATE platform_kbrain_facts SET status='approved', conflict_with_fact_id=NULL, "
                        "resolved_by=?, resolved_at=? WHERE workspace_id=? AND id=?",
                        (clean_approver, now, ws, clean_id),
                    )
                else:
                    conn.execute(
                        "UPDATE platform_kbrain_facts SET status='rejected', resolved_by=?, resolved_at=? "
                        "WHERE workspace_id=? AND id=?",
                        (clean_approver, now, ws, clean_id),
                    )
            updated = conn.execute(
                "SELECT * FROM platform_kbrain_facts WHERE workspace_id=? AND id=?",
                (ws, clean_id),
            ).fetchone()
        return self._row_to_fact(updated)  # type: ignore[arg-type]


class SQLiteKHubRegistry(_SQLiteWalBase):
    """Air-gapped KHub skill catalog inspector & `.tar.gz` cryptographic mirror verifier."""

    def __init__(
        self,
        db_path: Optional[Union[str, Path]] = None,
        skills_dir: Optional[Union[str, Path]] = None,
    ) -> None:
        super().__init__(db_path=db_path)
        self._skills_dir = (
            Path(skills_dir).resolve()
            if skills_dir is not None
            else (Path(__file__).resolve().parent.parent / "kstack" / "skills")
        )

    @staticmethod
    def _parse_skill_metadata(skill_dir: Path, fallback_id: str) -> Tuple[str, str, str]:
        skill_md = skill_dir / "SKILL.md"
        name = fallback_id
        description = ""
        version = "1.0.0"
        if not skill_md.is_file():
            return name, description, version

        lines = skill_md.read_text(encoding="utf-8", errors="replace").splitlines()
        idx = 0
        if lines and lines[0].strip() == "---":
            idx = 1
            while idx < len(lines) and lines[idx].strip() != "---":
                line = lines[idx].strip()
                if ":" in line:
                    k, v = line.split(":", 1)
                    k_clean, v_clean = k.strip().lower(), v.strip().strip("'\"")
                    if k_clean == "name" and v_clean:
                        name = v_clean
                    elif k_clean == "description" and v_clean:
                        description = v_clean
                    elif k_clean == "version" and v_clean:
                        version = v_clean
                idx += 1
            idx += 1

        for body_line in lines[idx:]:
            stripped = body_line.strip()
            if stripped.startswith("#"):
                heading = stripped.lstrip("#").strip()
                if heading:
                    name = heading
                break
        return name, description, version

    @staticmethod
    def _compute_skill_tree_digest(skill_dir: Path) -> Tuple[str, int]:
        ignored_suffixes = (".pyc", ".tar.gz", ".skill.tar.gz", ".DS_Store")
        ignored_names = {"skill_manifest.json", ".git"}
        file_digests: Dict[str, str] = {}
        for root, _, files in os.walk(skill_dir):
            for fname in sorted(files):
                if fname in ignored_names or any(fname.endswith(sfx) for sfx in ignored_suffixes):
                    continue
                fpath = Path(root) / fname
                if fpath.is_symlink():
                    continue
                rel = str(fpath.relative_to(skill_dir)).replace("\\", "/")
                file_digests[rel] = hashlib.sha256(fpath.read_bytes()).hexdigest()
        canonical = json.dumps(file_digests, sort_keys=True)
        return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest(), len(file_digests)

    def list_skills(self, workspace_id: str = "default") -> Dict[str, Any]:
        ws = _clean_workspace_id(workspace_id)
        skills: List[Dict[str, Any]] = []
        if self._skills_dir.is_dir():
            for sdir in sorted(p for p in self._skills_dir.iterdir() if p.is_dir() and not p.name.startswith(".")):
                skill_id = sdir.name
                name, description, version = self._parse_skill_metadata(sdir, skill_id)
                digest, files_count = self._compute_skill_tree_digest(sdir)
                skills.append(
                    {
                        "skill_id": skill_id,
                        "name": name,
                        "description": description,
                        "version": version or "1.0.0",
                        "source": "kstack_builtin",
                        "bundle_digest_sha256": digest,
                        "files_count": files_count,
                        "air_gap_compliant": True,
                    }
                )

        catalog_payload = _canonical_json([s["bundle_digest_sha256"] for s in skills])
        catalog_digest = "sha256:" + hashlib.sha256(catalog_payload.encode("utf-8")).hexdigest()
        return {
            "workspace_id": ws,
            "total_skills": len(skills),
            "air_gap_compliant": True,
            "catalog_digest_sha256": catalog_digest,
            "skills": skills,
        }

    def verify_airgap_mirror(
        self,
        workspace_id: str = "default",
        skill_ids: Optional[Sequence[str]] = None,
    ) -> Dict[str, Any]:
        ws = _clean_workspace_id(workspace_id)
        if not self._skills_dir.is_dir():
            raise FileNotFoundError(f"KStack skills directory '{self._skills_dir}' does not exist.")

        requested: List[str] = []
        if skill_ids is not None:
            for raw_id in skill_ids:
                sid = str(raw_id or "").strip()
                if not sid:
                    continue
                if not _SKILL_ID_RE.fullmatch(sid) or not (self._skills_dir / sid).is_dir():
                    raise ValueError(f"Unknown skill_id '{sid}' in KHub catalog.")
                if sid not in requested:
                    requested.append(sid)

        with tempfile.TemporaryDirectory(prefix="khub_airgap_roundtrip_") as tmp_dir:
            tmp_root = Path(tmp_dir).resolve()
            if requested:
                staged_dir = tmp_root / "staged_skills"
                staged_dir.mkdir(parents=True, exist_ok=True)
                for sid in requested:
                    shutil.copytree(self._skills_dir / sid, staged_dir / sid)
                source_skills_dir = staged_dir
            else:
                source_skills_dir = self._skills_dir

            export_tar_path = tmp_root / "khub-airgap-mirror.tar.gz"
            import_dir = tmp_root / "imported_skills"
            KHubMirror.export_mirror(export_tar_path, skills_dir=source_skills_dir, as_archive=True)
            import_res = KHubMirror.import_mirror(export_tar_path, destination_dir=import_dir, verify=True)

        raw_digest = str(import_res.get("catalog_digest_sha256", "")).removeprefix("sha256:")
        catalog_digest_sha256 = f"sha256:{raw_digest}"
        total_imported = int(import_res.get("total_imported", 0))
        now_iso = _utc_now()
        mirror_format = "khub-airgap-mirror-v1"

        with self._lock:
            conn = self._ensure_conn()
            with conn:
                conn.execute(
                    "INSERT INTO platform_khub_mirrors ("
                    "workspace_id, mirror_format, skills_verified, catalog_digest_sha256, verified_at"
                    ") VALUES (?, ?, ?, ?, ?)",
                    (ws, mirror_format, total_imported, catalog_digest_sha256, now_iso),
                )

        return {
            "workspace_id": ws,
            "verified": True,
            "mirror_format": mirror_format,
            "skills_verified": total_imported,
            "catalog_digest_sha256": catalog_digest_sha256,
            "verified_at": now_iso,
        }


kbrain_engine = SQLiteKBrainEngine()
khub_registry = SQLiteKHubRegistry()
