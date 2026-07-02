# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Repository for the ``TeachingSession`` entity.

Provides CRUD operations and domain-specific queries (status-filtered
listing) via the async SQLAlchemy repository pattern.

Classes
-------
TeachingSessionRepository
    Data access for teaching sessions and their associated rounds.
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.teaching_session import TeachingSession


class TeachingSessionRepository:
    """Repository for ``TeachingSession`` entity CRUD operations.

    Supports create, read, update (status and chain-head), list with
    optional status filter and pagination, and delete.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository with a database session.

        Parameters
        ----------
        session : AsyncSession
            SQLAlchemy async session used for all database operations.
        """
        self._session = session

    async def get(self, session_id: int) -> TeachingSession | None:
        """Retrieve a teaching session by its primary key.

        Parameters
        ----------
        session_id : int
            Primary key of the ``TeachingSession`` to retrieve.

        Returns
        -------
        TeachingSession | None
            The matching ``TeachingSession`` instance, or ``None`` if
            no record exists with the given ``session_id``.
        """
        return await self._session.get(TeachingSession, session_id)

    async def add(self, session: TeachingSession) -> TeachingSession:
        """Persist a new teaching session and flush to generate its
        primary key.

        Parameters
        ----------
        session : TeachingSession
            Unsaved ``TeachingSession`` instance to persist.

        Returns
        -------
        TeachingSession
            The persisted instance with a generated ``id``.
        """
        self._session.add(session)
        await self._session.flush()
        return session

    async def list(
        self,
        status: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[Sequence[TeachingSession], int]:
        """List teaching sessions with optional status filter and
        pagination.

        Parameters
        ----------
        status : str or None
            Optional status filter (``draft``, ``active``, ``completed``).
            When ``None``, returns all sessions.
        limit : int
            Maximum number of results to return (default ``20``).
        offset : int
            Number of results to skip (default ``0``).

        Returns
        -------
        tuple[Sequence[TeachingSession], int]
            A tuple of (matching sessions ordered by creation date
            descending, total count matching the filter).
        """
        conditions = [TeachingSession.status == status] if status else []
        count_query = select(func.count(TeachingSession.id)).where(*conditions)
        total_result = await self._session.execute(count_query)
        total: int = total_result.scalar() or 0

        query = (
            select(TeachingSession)
            .where(*conditions)
            .order_by(TeachingSession.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(query)
        return result.scalars().all(), total

    async def update_status(
        self, session_id: int, new_status: str
    ) -> TeachingSession | None:
        """Update the status of a teaching session.

        Parameters
        ----------
        session_id : int
            Primary key of the session to update.
        new_status : str
            New status value (must be a ``TeachingSessionStatus`` value).

        Returns
        -------
        TeachingSession | None
            The updated session, or ``None`` if no session with the
            given ``session_id`` exists.
        """
        stmt = (
            update(TeachingSession)
            .where(TeachingSession.id == session_id)
            .values(status=new_status)
        )
        await self._session.execute(stmt)
        await self._session.flush()
        return await self.get(session_id)

    async def update_current_base_experiment_id(
        self, session_id: int, experiment_id: int
    ) -> TeachingSession | None:
        """Update the chain-head experiment id after a round finalizes.

        Parameters
        ----------
        session_id : int
            Primary key of the session to update.
        experiment_id : int
            The new experiment id (the round that just finalized).

        Returns
        -------
        TeachingSession | None
            The updated session, or ``None`` if no session with the
            given ``session_id`` exists.
        """
        stmt = (
            update(TeachingSession)
            .where(TeachingSession.id == session_id)
            .values(current_base_experiment_id=experiment_id)
        )
        await self._session.execute(stmt)
        await self._session.flush()
        return await self.get(session_id)

    async def delete(self, session_id: int) -> bool:
        """Delete a teaching session by primary key.

        Does NOT cascade to MLflow runs or experiment artifacts (they
        remain independently accessible).

        Parameters
        ----------
        session_id : int
            Primary key of the session to delete.

        Returns
        -------
        bool
            ``True`` if a row was deleted, ``False`` if no session
            existed with the given ``session_id``.
        """
        session = await self.get(session_id)
        if session is None:
            return False
        await self._session.delete(session)
        await self._session.flush()
        return True