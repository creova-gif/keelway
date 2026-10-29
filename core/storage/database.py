"""
Database connection and session lifecycle for Kora AI Core.
"""

from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text

from core.config import settings
from core.storage.models import Base

# Dynamic engine configuration (SQLite for local/test, PostgreSQL for production)
is_sqlite = settings.database_url.startswith("sqlite")

engine_kwargs = {
    "echo": (settings.log_level.upper() == "DEBUG"),
}

if is_sqlite:
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    engine_kwargs["pool_pre_ping"] = True
    engine_kwargs["pool_size"] = 10
    engine_kwargs["max_overflow"] = 20

engine = create_async_engine(settings.database_url, **engine_kwargs)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for yielding an async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def check_db_health() -> bool:
    """Verifies database connectivity."""
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            return result.scalar() == 1
    except Exception:
        return False


async def init_db() -> None:
    """Initialize tables in local/test development with automatic column migration."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        if is_sqlite:
            try:
                res = await conn.execute(text("PRAGMA table_info(kora_memories)"))
                columns = [row[1] for row in res.fetchall()]
                if "vector_embedding" not in columns:
                    await conn.execute(text("ALTER TABLE kora_memories ADD COLUMN vector_embedding JSON"))
                if "metadata_json" not in columns:
                    await conn.execute(text("ALTER TABLE kora_memories ADD COLUMN metadata_json JSON DEFAULT '{}'"))
            except Exception:
                pass


async def close_db() -> None:
    """Close and dispose database engine connections."""
    await engine.dispose()
