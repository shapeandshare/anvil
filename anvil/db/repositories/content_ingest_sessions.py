# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""ContentIngestSessionRepository — data access for isolated content
staging sessions.

Provides CRUD operations and domain-specific queries (status filtering,
active session tracking) for the ``IngestSession`` entity via the async
SQLAlchemy repository pattern.
"""

from collections.abc import Sequence
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.content_ingest_session import IngestSession


class ContentIngestSessionRepository:
    """Repository for ``IngestSession`` entity CRUD and status
    management.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository with a database session.

        Parameters
        ----------
        session : AsyncSession
            SQLAlchemy async session used for all database operations.
        """
        self._session = session

    async def get(self, id: int) -> IngestSession | None:
        """Retrieve an ingest session by its primary key.

        Parameters
        ----------
        id : int
            The primary key of the session to retrieve.

        Returns
        -------
        IngestSession | None
            The matching ``IngestSession`` instance, or ``None`` if no
            record exists with the given ``id``.
        """
        return await self._session.get(IngestSession, id)

    async def add(self, session: IngestSession) -> IngestSession:
        """Persist a new ingest session and return it with a generated
        primary key.

        Parameters
        ----------
        session : IngestSession
            The unsaved ``IngestSession`` instance to add to the database.

        Returns
        -------
        IngestSession
            The same instance after flush and refresh, with its ``id``
            and server-side defaults populated.
        """
        self._session.add(session)
        await self._session.flush()
        await self._session.refresh(session)
        return session

    async def update_status(
        self, id: int, status: str, problems: str | None = None
    ) -> None:
        """Update the status of an ingest session.

        Parameters
        ----------
        id : int
            Primary key of the session to update.
        status : str
            New status value from ``IngestStatus``.
        problems : str, optional
            Optional JSON-serialised validation problems to record on
            the session. Defaults to ``None``.

        Returns
        -------
        None
        """
        values: dict[str, Any] = {"status": status}
        if problems is not None:
            values["problems_json"] = problems
        await self._session.execute(
            update(IngestSession).where(IngestSession.id == id).values(**values)
        )

    async def set_accepted_version(self, id: int, version_id: int) -> None:
        """Record the accepted version for a completed ingest session.

        Parameters
        ----------
        id : int
            Primary key of the session to update.
        version_id : int
            Primary key of the ``ContentVersion`` that was accepted.

        Returns
        -------
        None
        """
        await self._session.execute(
            update(IngestSession)
            .where(IngestSession.id == id)
            .values(accepted_version_id=version_id)
        )

    async def list_by_status(self, status: str) -> Sequence[IngestSession]:
        """List all ingest sessions with a given status.

        Parameters
        ----------
        status : str
            Status value from ``IngestStatus`` to filter by.

        Returns
        -------
        Sequence[IngestSession]
            All matching ``IngestSession`` records, ordered by creation
            date descending.
        """
        result = await self._session.execute(
            select(IngestSession)
            .where(IngestSession.status == status)
            .order_by(IngestSession.created_at.desc())
        )
        return result.scalars().all()

    async def get_by_accepted_version(self, version_id: int) -> IngestSession | None:
        """Retrieve the ingest session that accepted a given version.

        Looks up the ``IngestSession`` whose ``accepted_version_id``
        matches *version_id*.  Returns ``None`` if no such session
        exists (e.g. for compositions or frozen versions created
        outside an ingestion flow).

        Parameters
        ----------
        version_id : int
            Primary key of the ``ContentVersion`` that was accepted.

        Returns
        -------
        IngestSession or None
            The matching ``IngestSession``, or ``None``.
        """
        result = await self._session.execute(
            select(IngestSession).where(IngestSession.accepted_version_id == version_id)
        )
        return result.scalar_one_or_none()

    async def list_active(self) -> Sequence[IngestSession]:
        """List all currently active ingest sessions (status not
        ``ACCEPTED`` or ``FAILED``).

        Returns
        -------
        Sequence[IngestSession]
            Active ``IngestSession`` records, ordered by creation date
            descending.
        """
        result = await self._session.execute(
            select(IngestSession)
            .where(IngestSession.status.notin_(["ACCEPTED", "FAILED"]))
            .order_by(IngestSession.created_at.desc())
        )
        return result.scalars().all()
