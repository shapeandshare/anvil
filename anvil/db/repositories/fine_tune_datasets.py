# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Repository for ``FineTuneDataset`` CRUD operations."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...services._shared.fine_tune_dataset_status import FineTuneDatasetStatus
from ..models.fine_tune_dataset import FineTuneDataset


class FineTuneDatasetRepository:
    """Async CRUD repository for ``FineTuneDataset`` entries.

    Parameters
    ----------
    session : AsyncSession
        SQLAlchemy async session bound to the application database.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, id: int) -> FineTuneDataset | None:
        """Retrieve a fine-tune dataset by primary key.

        Parameters
        ----------
        id : int
            Dataset primary key.

        Returns
        -------
        FineTuneDataset | None
            The matching entry, or ``None`` if not found.
        """
        return await self._session.get(FineTuneDataset, id)

    async def add(self, ftd: FineTuneDataset) -> FineTuneDataset:
        """Persist a new fine-tune dataset entry.

        Parameters
        ----------
        ftd : FineTuneDataset
            Unsaved instance.

        Returns
        -------
        FineTuneDataset
            The saved entry with generated fields populated.
        """
        self._session.add(ftd)
        await self._session.flush()
        await self._session.refresh(ftd)
        return ftd

    async def get_active_for_dataset(self, dataset_id: int) -> FineTuneDataset | None:
        """Return the currently-preparing fine-tune dataset for a source dataset.

        Only entries with ``status = "preparing"`` are considered active.
        This enforces the one-active-preparation-per-dataset rule.

        Parameters
        ----------
        dataset_id : int
            Source dataset primary key.

        Returns
        -------
        FineTuneDataset | None
            The active preparation entry, or ``None`` if none in progress.
        """
        result = await self._session.execute(
            select(FineTuneDataset).where(
                and_(
                    FineTuneDataset.dataset_id == dataset_id,
                    FineTuneDataset.status == FineTuneDatasetStatus.PREPARING,
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_all(
        self,
        *,
        dataset_id: int | None = None,
        status: str | None = None,
        base_model_ref: int | None = None,
    ) -> Sequence[FineTuneDataset]:
        """List fine-tune datasets with optional filters.

        Parameters
        ----------
        dataset_id : int, optional
            Filter by source dataset.
        status : str, optional
            Filter by job status.
        base_model_ref : int, optional
            Filter by base model.

        Returns
        -------
        Sequence[FineTuneDataset]
            Matching entries ordered by creation time (newest first).
        """
        stmt = select(FineTuneDataset).order_by(FineTuneDataset.created_at.desc())
        conditions = []
        if dataset_id is not None:
            conditions.append(FineTuneDataset.dataset_id == dataset_id)
        if status is not None:
            conditions.append(FineTuneDataset.status == status)
        if base_model_ref is not None:
            conditions.append(FineTuneDataset.base_model_ref == base_model_ref)
        if conditions:
            stmt = stmt.where(and_(*conditions))
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def update_status(
        self,
        id: int,
        status: str,
        *,
        record_count: int | None = None,
        prepared_file_path: str | None = None,
        summary_json: str | None = None,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
    ) -> FineTuneDataset | None:
        """Update the status and metadata of a fine-tune dataset entry.

        Parameters
        ----------
        id : int
            Entry primary key.
        status : str
            New status value (``FineTuneDatasetStatus``).
        record_count : int, optional
            Number of successfully prepared records.
        prepared_file_path : str, optional
            Path to the prepared JSONL file.
        summary_json : str, optional
            JSON summary with ``total``/``succeeded``/``failed`` counts.
        started_at : datetime, optional
            When the preparation job started.
        finished_at : datetime, optional
            When the preparation job finished.

        Returns
        -------
        FineTuneDataset | None
            The updated entry, or ``None`` if not found.
        """
        entry = await self._session.get(FineTuneDataset, id)
        if entry is None:
            return None
        entry.status = status
        if record_count is not None:
            entry.record_count = record_count
        if prepared_file_path is not None:
            entry.prepared_file_path = prepared_file_path
        if summary_json is not None:
            entry.summary_json = summary_json
        if started_at is not None:
            entry.started_at = started_at
        if finished_at is not None:
            entry.finished_at = finished_at
        await self._session.flush()
        await self._session.refresh(entry)
        return entry
