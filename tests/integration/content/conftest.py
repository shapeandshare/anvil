# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Async database and content-store test fixtures for content repository integration tests.

Provides an in-memory SQLite async engine + session and a temporary content
directory for ``LocalVersionedContentStore`` tests.
"""

import importlib
import pkgutil
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import anvil.db.models as _models_pkg
from anvil.db.base import Base


def _register_all_models() -> None:
    """Import every ORM model module so ``Base.metadata`` is complete.

    The models package keeps a bare ``__init__`` (Constitution Article VI),
    so tables only register on import. Production uses Alembic migrations;
    tests using ``Base.metadata.create_all`` must import every model first.
    """
    for module in pkgutil.iter_modules(_models_pkg.__path__):
        importlib.import_module(f"{_models_pkg.__name__}.{module.name}")


@pytest_asyncio.fixture
async def content_db(tmp_path: Path) -> AsyncGenerator[AsyncSession, None]:
    """Provide an async session backed by an in-memory SQLite database.

    All tables are created from ``Base.metadata`` before each test and
    dropped after.
    """
    _register_all_models()
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
