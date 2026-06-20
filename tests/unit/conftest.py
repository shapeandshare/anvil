"""pytest fixtures for unit tests — in-memory database sessions.

Provides the ``in_memory_session`` fixture used by all repository and
service-layer unit tests.  Each test gets a fresh SQLite in-memory
database with all tables created, preventing test-to-test interference
and avoiding the need for each test file to define its own session
fixture.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# Import all model modules so their tables register with Base.metadata.
# Each sub-module must be explicitly imported (models/__init__.py is bare).
from anvil.db.models import (  # noqa: F401  # isort: skip
    audit_event,
    corpus,
    corpus_file,
    curation_operation,
    dataset,
    import_source,
    license_entry,
    registry,
    sample,
    training_config,
)
from anvil.db.base import Base


@pytest.fixture
async def in_memory_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide an ``AsyncSession`` backed by a fresh in-memory SQLite DB.

    Creates all ORM tables before the test and drops them afterward,
    giving each test complete isolation.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        echo=False,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()