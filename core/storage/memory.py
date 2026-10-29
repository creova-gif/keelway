"""
Kora AI Memory Service.
Provides persistent storage, retrieval, and lexical/semantic indexing for agent memory.
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func

from core.storage.models import MemoryRecord, utc_now


class MemoryService:
    """Manages agent memory records across scopes (project, user, global)."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def store(
        self,
        key: str,
        content: str,
        scope: str = "project",
        provenance_uri: Optional[str] = None,
    ) -> MemoryRecord:
        """Upsert a memory record by scope and key."""
        query = select(MemoryRecord).where(
            MemoryRecord.scope == scope,
            MemoryRecord.key == key,
        )
        result = await self.db.execute(query)
        existing = result.scalar_one_or_none()

        if existing:
            existing.content = content
            existing.provenance_uri = provenance_uri
            existing.updated_at = utc_now()
            await self.db.flush()
            await self.db.refresh(existing)
            return existing

        new_record = MemoryRecord(
            scope=scope,
            key=key,
            content=content,
            provenance_uri=provenance_uri,
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
        """Search memory content by substring/keyword match with relevance ordering."""
        stmt = select(MemoryRecord)
        if scope:
            stmt = stmt.where(MemoryRecord.scope == scope)

        tokens = [t.strip().lower() for t in query_text.split() if len(t.strip()) > 1]
        if tokens:
            # Build case-insensitive substring filters
            for token in tokens:
                stmt = stmt.where(
                    func.lower(MemoryRecord.content).contains(token) |
                    func.lower(MemoryRecord.key).contains(token)
                )

        stmt = stmt.order_by(MemoryRecord.updated_at.desc()).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

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
