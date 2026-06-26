# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""ContentImportJobRepository — data access for declarative import
configurations.

Provides CRUD operations and status management for the ``ImportJob``
entity via the async SQLAlchemy repository pattern.
"""

from collections.abc import Sequence
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.content_import_job import ImportJob


class ContentImportJobRepository:
    """Repository for ``ImportJob`` entity CRUD and status management."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository with a database session.

        Parameters
        ----------
        session : AsyncSession
            SQLAlchemy async session used for all database operations.
        """
        self._session = session

    async def get(self, id: int) -> ImportJob | None:
        """Retrieve an import job by its primary key.

        Parameters
        ----------
        id : int
            The primary key of the job to retrieve.

        Returns
        -------
        ImportJob | None
            The matching ``ImportJob`` instance, or ``None`` if no
            record exists with the given ``id``.
        """
        return await self._session.get(ImportJob, id)

    async def get_all(self) -> Sequence[ImportJob]:
        """Retrieve all import jobs ordered by creation time (newest
        first).

        Returns
        -------
        Sequence[ImportJob]
            All persisted ``ImportJob`` records.
        """
        result = await self._session.execute(
            select(ImportJob).order_by(ImportJob.id.desc())
        )
        return result.scalars().all()

    async def add(self, job: ImportJob) -> ImportJob:
        """Persist a new import job and return it with a generated
        primary key.

        Parameters
        ----------
        job : ImportJob
            The unsaved ``ImportJob`` instance to add to the database.

        Returns
        -------
        ImportJob
            The same instance after flush and refresh, with its ``id``
            and server-side defaults populated.
        """
        self._session.add(job)
        await self._session.flush()
        await self._session.refresh(job)
        return job

    async def update_status(
        self, id: int, status: str, message: str | None = None
    ) -> None:
        """Update the status of an import job.

        Parameters
        ----------
        id : int
            Primary key of the job to update.
        status : str
            New status value from ``IngestStatus``.
        message : str, optional
            Optional status or error message. Defaults to ``None``.

        Returns
        -------
        None
        """
        values: dict[str, Any] = {"status": status}
        if message is not None:
            values["message"] = message
        await self._session.execute(
            update(ImportJob).where(ImportJob.id == id).values(**values)
        )
