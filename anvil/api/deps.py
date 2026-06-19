"""FastAPI dependency injection.

Provides reusable FastAPI dependencies such as database session access.
Dependencies are consumed by route handlers via ``Depends()``.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from ..db.session import get_db


async def get_db_session() -> AsyncGenerator[AsyncSession]:
    """Provide an async SQLAlchemy session as a FastAPI dependency.

    Yields an ``AsyncSession`` from the global engine, one per request.
    The caller is responsible for committing or rolling back the session.

    Yields
    ------
    AsyncSession
        An async SQLAlchemy session bound to the application engine.
    """
    async for session in get_db():
        yield session
