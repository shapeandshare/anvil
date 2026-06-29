# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Repository for ``AssetDownloadJob`` CRUD operations."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.asset_download_job import AssetDownloadJob

"""Repository for ``AssetDownloadJob`` CRUD operations."""


class AssetDownloadJobRepository:
    """Async CRUD repository for ``AssetDownloadJob`` entries.

    Parameters
    ----------
    session : AsyncSession
        SQLAlchemy async session bound to the application database.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, id: int) -> AssetDownloadJob | None:
        """Retrieve a download job by primary key.

        Parameters
        ----------
        id : int
            Job primary key.

        Returns
        -------
        AssetDownloadJob | None
            The matching job, or ``None`` if not found.
        """
        return await self._session.get(AssetDownloadJob, id)

    async def add(self, job: AssetDownloadJob) -> AssetDownloadJob:
        """Persist a new download job.

        Parameters
        ----------
        job : AssetDownloadJob
            Unsaved job instance.

        Returns
        -------
        AssetDownloadJob
            The saved job with generated fields populated.
        """
        self._session.add(job)
        await self._session.flush()
        await self._session.refresh(job)
        return job

    async def update_status(
        self,
        id: int,
        status: str,
        *,
        error_code: str | None = None,
        error_message: str | None = None,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
    ) -> AssetDownloadJob | None:
        """Update the status and related fields of a download job.

        Parameters
        ----------
        id : int
            Job primary key.
        status : str
            New job status value.
        error_code : str | None
            Typed error code if the job failed.
        error_message : str | None
            Human-readable error detail.
        started_at : datetime | None
            When download began.
        finished_at : datetime | None
            When download completed or failed.

        Returns
        -------
        AssetDownloadJob | None
            The updated job, or ``None`` if not found.
        """
        job = await self._session.get(AssetDownloadJob, id)
        if job is None:
            return None
        job.status = status
        if error_code is not None:
            job.error_code = error_code
        if error_message is not None:
            job.error_message = error_message
        if started_at is not None:
            job.started_at = started_at
        if finished_at is not None:
            job.finished_at = finished_at
        await self._session.flush()
        await self._session.refresh(job)
        return job

    async def get_active_for_model(self, external_model_id: int) -> bool:
        """Return ``True`` if the model has any in-flight download job.

        An in-flight job has status ``"queued"`` or ``"downloading"``.
        Used by the service layer for the model-level lock (FR-010c).

        Parameters
        ----------
        external_model_id : int
            FK to ``ExternalModel``.

        Returns
        -------
        bool
            ``True`` if an active job exists for the model.
        """
        stmt = (
            select(AssetDownloadJob)
            .where(
                AssetDownloadJob.external_model_id == external_model_id,
                AssetDownloadJob.status.in_(["queued", "downloading"]),
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None
