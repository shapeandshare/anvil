"""FastAPI dependency injection.

Provides reusable FastAPI dependencies such as database session access
and a session-bound :class:`AnvilWorkbench`. Dependencies are consumed
by route handlers via ``Depends()``.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from ..db.session import get_db
from ..workbench import AnvilWorkbench

# Import get_db_session for downstream convenience.
__all__ = ["get_db_session", "get_workbench"]


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


async def get_workbench() -> AsyncGenerator[AnvilWorkbench]:
    """Provide a session-bound ``AnvilWorkbench`` as a FastAPI dependency.

    Yields a new :class:`AnvilWorkbench` bound to a request-scoped
    ``AsyncSession``.  Services obtained from the workbench share this
    session, so audit writes, provenance updates, etc. participate in
    the same transaction (FR-011).

    Yields
    ------
    AnvilWorkbench
        A workbench instance ready to serve the current request.
    """
    async for session in get_db():
        yield AnvilWorkbench(session)
