# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Async SQLAlchemy session management.

Provides the async engine, session factory, and a FastAPI-compatible
``get_db`` dependency for request-scoped database access.

Module-level Constants
----------------------
DB_PATH : str
    Resolved filesystem path to the SQLite database file.
SQLALCHEMY_DATABASE_URL : str
    Full ``sqlite+aiosqlite:///`` connection URL constructed from
    ``DB_PATH``.
async_engine : AsyncEngine
    The singleton async SQLAlchemy engine with WAL-mode-friendly
    configuration.
AsyncSessionLocal : async_sessionmaker[AsyncSession]
    Factory that produces ``AsyncSession`` instances bound to
    ``async_engine``.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ..config import get_config

cfg = get_config()
DB_PATH = cfg["state_db_path"]
SQLALCHEMY_DATABASE_URL = f"sqlite+aiosqlite:///{DB_PATH}"

async_engine = create_async_engine(
    SQLALCHEMY_DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    connect_args={
        "check_same_thread": False,
    },
)


async def init_engine() -> None:
    """Configure WAL journal mode and enable foreign keys on startup.

    Must be called once during application startup (e.g. in a FastAPI
    lifespan handler) before any database operations are performed.

    Raises
    ------
    sqlalchemy.exc.OperationalError
        If the database file cannot be opened or the pragmas fail.
    """
    async with async_engine.connect() as conn:
        await conn.exec_driver_sql("PRAGMA journal_mode=WAL")
        await conn.exec_driver_sql("PRAGMA foreign_keys=ON")
        await conn.commit()


AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession]:
    """FastAPI dependency that yields a request-scoped database session.

    Yields an ``AsyncSession`` that is automatically committed on
    success or rolled back on exception. The session is always closed
    in the ``finally`` block.

    Yields
    ------
    AsyncSession
        A request-scoped session bound to ``AsyncSessionLocal``.

    Raises
    ------
    Exception
        Re-raises any exception caught during the request after
        rolling back the session.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
