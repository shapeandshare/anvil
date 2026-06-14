"""Async SQLAlchemy session management."""

import os
from collections.abc import AsyncGenerator
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

DB_PATH = os.getenv("ANVIL_DB_PATH", str(Path("data/anvil.db").resolve()))
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
    """Configure WAL mode and foreign keys on startup."""
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
    """FastAPI dependency that yields a request-scoped session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
