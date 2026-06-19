"""Async SQLAlchemy session management."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from anvil.config import get_config

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
