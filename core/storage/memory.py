"""
Keelway Memory Service with Hybrid Semantic & Lexical Retrieval (RAG).
Provides persistent storage, vector embedding generation, and hybrid relevance scoring.
"""

import math
import re
import hashlib
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple

from core.storage.embedding import EmbeddingProvider, cosine_similarity, compute_lexical_score

try:
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy import select, delete, func
    from core.storage.models import MemoryRecord, utc_now
except ImportError:
    AsyncSession = None  # type: ignore
    select = delete = func = MemoryRecord = utc_now = None  # type: ignore


class MemoryService:
    """Manages agent memory records across scopes (project, user, research, global)."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def store(
        self,
        key: str,
        content: str,
        scope: str = "project",
        provenance_uri: Optional[str] = None,
        metadata_json: Optional[Dict[str, Any]] = None,
        auto_embed: bool = True,
    ) -> MemoryRecord:
        """Upsert a memory record by scope and key with automated vector embedding."""
        embedding = EmbeddingProvider.get_dense_embedding(f"{key} {content}") if auto_embed else None

        query = select(MemoryRecord).where(
            MemoryRecord.scope == scope,
            MemoryRecord.key == key,
        )
        result = await self.db.execute(query)
        existing = result.scalar_one_or_none()

        if existing:
            existing.content = content
            existing.provenance_uri = provenance_uri
            existing.vector_embedding = embedding
            existing.metadata_json = metadata_json or existing.metadata_json or {}
            existing.updated_at = utc_now()
            await self.db.flush()
            await self.db.refresh(existing)
            return existing

        new_record = MemoryRecord(
            scope=scope,
            key=key,
            content=content,
            provenance_uri=provenance_uri,
            vector_embedding=embedding,
            metadata_json=metadata_json or {},
        )
        self.db.add(new_record)
        await self.db.flush()
        await self.db.refresh(new_record)
        return new_record

    async def get(self, key: str, scope: str = "project") -> Optional[MemoryRecord]:
        """Fetch a specific memory record by key and scope."""
        query = select(MemoryRecord).where(
            MemoryRecord.scope == scope,
            MemoryRecord.key == key,
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def search(
        self,
        query_text: str,
        scope: Optional[str] = None,
        limit: int = 10,
    ) -> List[MemoryRecord]:
        """Standard keyword-based search with updated_at descending sort."""
        stmt = select(MemoryRecord)
        if scope:
            stmt = stmt.where(MemoryRecord.scope == scope)

        tokens = [t.strip().lower() for t in query_text.split() if len(t.strip()) > 1]
        if tokens:
            for token in tokens:
                stmt = stmt.where(
                    func.lower(MemoryRecord.content).contains(token) |
                    func.lower(MemoryRecord.key).contains(token)
                )

        stmt = stmt.order_by(MemoryRecord.updated_at.desc()).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def search_hybrid(
        self,
        query_text: str,
        scope: Optional[str] = None,
        alpha: float = 0.5,  # 0.0 = pure vector, 1.0 = pure lexical, 0.5 = balanced
        threshold: float = 0.2,
        limit: int = 10,
    ) -> List[Tuple[MemoryRecord, float]]:
        """
        Hybrid search combining Lexical Token Overlap and Dense Vector Cosine Similarity.
        Returns list of (MemoryRecord, hybrid_score) sorted by score descending.
        """
        stmt = select(MemoryRecord)
        if scope:
            stmt = stmt.where(MemoryRecord.scope == scope)

        result = await self.db.execute(stmt)
        all_candidates = list(result.scalars().all())

        if not all_candidates:
            return []

        query_embedding = EmbeddingProvider.get_dense_embedding(query_text)
        scored: List[Tuple[MemoryRecord, float]] = []

        for record in all_candidates:
            lex_score = compute_lexical_score(query_text, f"{record.key} {record.content}")
            vec_score = 0.0
            if record.vector_embedding:
                vec_score = cosine_similarity(query_embedding, record.vector_embedding)
            else:
                rec_emb = EmbeddingProvider.get_dense_embedding(f"{record.key} {record.content}")
                vec_score = cosine_similarity(query_embedding, rec_emb)

            # Combined hybrid score
            hybrid_score = (alpha * lex_score) + ((1.0 - alpha) * vec_score)
            if hybrid_score >= threshold:
                scored.append((record, hybrid_score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:limit]

    async def ingest_file(
        self,
        file_path: Path,
        scope: str = "project",
        chunk_lines: int = 40,
    ) -> List[MemoryRecord]:
        """
        Chunks a text/code/markdown file into memories with precise line-level provenance.
        """
        if not file_path.exists() or not file_path.is_file():
            raise FileNotFoundError(f"File not found: {file_path}")

        lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
        records = []
        base_name = file_path.name

        for i in range(0, len(lines), chunk_lines):
            chunk = lines[i : i + chunk_lines]
            chunk_content = "\n".join(chunk).strip()
            if not chunk_content:
                continue

            start_line = i + 1
            end_line = min(i + chunk_lines, len(lines))
            key = f"{base_name}#L{start_line}-L{end_line}"
            provenance = f"file://{file_path.resolve()}#L{start_line}-L{end_line}"

            meta = {
                "file_path": str(file_path.resolve()),
                "filename": base_name,
                "start_line": start_line,
                "end_line": end_line,
                "total_lines": len(lines),
            }

            rec = await self.store(
                key=key,
                content=chunk_content,
                scope=scope,
                provenance_uri=provenance,
                metadata_json=meta,
                auto_embed=True,
            )
            records.append(rec)

        return records

    async def delete(self, key: str, scope: str = "project") -> bool:
        """Delete a memory record by key and scope."""
        stmt = delete(MemoryRecord).where(
            MemoryRecord.scope == scope,
            MemoryRecord.key == key,
        )
        result = await self.db.execute(stmt)
        await self.db.flush()
        return result.rowcount > 0

    async def list_by_scope(self, scope: str = "project", limit: int = 50) -> List[MemoryRecord]:
        """List all memories within a given scope."""
        stmt = select(MemoryRecord).where(
            MemoryRecord.scope == scope
        ).order_by(MemoryRecord.updated_at.desc()).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
