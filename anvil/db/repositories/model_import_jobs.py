# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Repository for ``ModelImportJob`` CRUD operations."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.model_import_job import ModelImportJob


class ModelImportJobRepository:
    """Async CRUD repository for ``ModelImportJob`` entries.

    Parameters
    ----------
    session : AsyncSession
        SQLAlchemy async session bound to the application database.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, id: int) -> ModelImportJob | None:
        """Retrieve an import job by primary key.

        Parameters
        ----------
        id : int
            Job primary key.

        Returns
        -------
        ModelImportJob | None
            The matching job, or ``None`` if not found.
        """
        return await self._session.get(ModelImportJob, id)

    async def list_all(self) -> Sequence[ModelImportJob]:
        """Return all import jobs ordered by creation time (newest first).

        Returns
        -------
        Sequence[ModelImportJob]
            All import job entries.
        """
        result = await self._session.execute(
            select(ModelImportJob).order_by(ModelImportJob.created_at.desc())
        )
        return result.scalars().all()

    async def add(self, job: ModelImportJob) -> ModelImportJob:
        """Persist a new import job.

        Parameters
        ----------
        job : ModelImportJob
            Unsaved job instance.

        Returns
        -------
        ModelImportJob
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
        external_model_id: int | None = None,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
    ) -> ModelImportJob | None:
        """Update the status and related fields of an import job.

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
        external_model_id : int | None
            FK to ``ExternalModel`` on successful completion.
        started_at : datetime | None
            When resolution began.
        finished_at : datetime | None
            When resolution completed or failed.

        Returns
        -------
        ModelImportJob | None
            The updated job, or ``None`` if not found.
        """
        job = await self._session.get(ModelImportJob, id)
        if job is None:
            return None
        job.status = status
        if error_code is not None:
            job.error_code = error_code
        if error_message is not None:
            job.error_message = error_message
        if external_model_id is not None:
            job.external_model_id = external_model_id
        if started_at is not None:
            job.started_at = started_at
        if finished_at is not None:
            job.finished_at = finished_at
        await self._session.flush()
        await self._session.refresh(job)
        return job
