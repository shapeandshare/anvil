"""Async database and content-store test fixtures for content repository integration tests.

Provides an in-memory SQLite async engine + session and a temporary content
directory for ``LocalVersionedContentStore`` tests.
"""

from pathlib import Path
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from anvil.db.base import Base


@pytest_asyncio.fixture
async def content_db(tmp_path: Path) -> AsyncGenerator[AsyncSession, None]:
    """Provide an async session backed by an in-memory SQLite database.

    All tables are created from ``Base.metadata`` before each test and
    dropped after.
    """
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession)
    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest.fixture
def content_dir(tmp_path: Path) -> Path:
    """Return a temporary content directory path."""
    return tmp_path / "content"