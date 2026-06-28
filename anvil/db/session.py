# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Async SQLAlchemy session management.

Provides the async engine, session factory, and a FastAPI-compatible
``get_db`` dependency for request-scoped database access.

Module-level Variables
----------------------
async_engine : AsyncEngine
    The singleton async SQLAlchemy engine with WAL-mode-friendly
    configuration.  Initialised lazily on first module import from
    ``get_config()["state_db_path"]`` (default boot path), or
    explicitly via ``reinit_engine()`` for workspace-based instances.
AsyncSessionLocal : async_sessionmaker[AsyncSession]
    Factory that produces ``AsyncSession`` instances bound to
    ``async_engine``.

Starting with the v2.0 (feature-028) refactoring, the engine is NOT
created at import time — it is deferred to ``_bootstrap_engine()``
which auto-runs on the first module import so backward compatibility
is preserved for the default (single-instance) path.  Workspace-aware
callers use ``reinit_engine(db_path)`` to redirect the engine to a
per-instance SQLite database.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from typing import cast

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from ..config import get_config

logger = logging.getLogger(__name__)

# ── Module-level globals (set by _bootstrap_engine / reinit_engine) ──

_engine: AsyncEngine | None = None
_session_maker: async_sessionmaker[AsyncSession] | None = None


def _bootstrap_engine(db_path: str | None = None) -> None:
    """Create (or recreate) the async engine and session factory.

    Parameters
    ----------
    db_path : str, optional
        Absolute path to the SQLite database file.  Falls back to
        ``get_config()["state_db_path"]`` when ``None`` (the default
        single-instance boot path).
    """
    global _engine, _session_maker

    if db_path is None:
        db_path = get_config()["state_db_path"]

    url = f"sqlite+aiosqlite:///{db_path}"
    _engine = create_async_engine(
        url,
        echo=False,
        pool_pre_ping=True,
        connect_args={"check_same_thread": False},
    )

    _session_maker = async_sessionmaker(
        bind=_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )


# Auto-initialise from defaults on first module import (backward compat).
_bootstrap_engine()

# Public aliases (cast to assured type since _bootstrap_engine ran).
async_engine: AsyncEngine = cast("AsyncEngine", _engine)
"""Asynchronous SQLAlchemy engine, created by _bootstrap_engine()."""
AsyncSessionLocal: async_sessionmaker[AsyncSession] = cast(
    "async_sessionmaker[AsyncSession]", _session_maker
)
"""Async session factory, created by _bootstrap_engine()."""


async def init_engine() -> None:
    """Configure WAL journal mode and enable foreign keys on startup.
    ...
    """
    assert _engine is not None  # assured by _bootstrap_engine on import
    async with _engine.connect() as conn:
        await conn.exec_driver_sql("PRAGMA journal_mode=WAL")
        await conn.exec_driver_sql("PRAGMA foreign_keys=ON")
        await conn.commit()


async def reinit_engine(db_path: str) -> None:
    """Reinitialise the engine with a new database path.

    Disposes the existing engine (if any) and creates a fresh one
    targeted at ``db_path``, then runs the WAL initialisation.
    This is the entry point for workspace-based instances that need
    a per-workspace SQLite database (feature-028).

    Parameters
    ----------
    db_path : str
        Absolute path to the per-instance SQLite database file.
    """
    global _engine, _session_maker, async_engine, AsyncSessionLocal

    # Dispose the old engine if it exists.
    if _engine is not None:
        await _engine.dispose()

    _bootstrap_engine(db_path)
    async_engine = cast("AsyncEngine", _engine)
    AsyncSessionLocal = cast("async_sessionmaker[AsyncSession]", _session_maker)
    await init_engine()


async def get_db() -> AsyncGenerator[AsyncSession]:
    """FastAPI dependency that yields a request-scoped database session.
    ...
    """
    assert _session_maker is not None  # assured by _bootstrap_engine on import
    async with _session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
