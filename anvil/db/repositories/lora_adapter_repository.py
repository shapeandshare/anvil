"""Repository for ``LoRAAdapter`` CRUD operations."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.lora_adapter import LoRAAdapter


class LoRAAdapterRepository:
    """Async CRUD repository for ``LoRAAdapter`` entries.

    Parameters
    ----------
    session : AsyncSession
        SQLAlchemy async session bound to the application database.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_model(self, model_id: int) -> Sequence[LoRAAdapter]:
        """Return all adapters for a given external model.

        Parameters
        ----------
        model_id : int
            Foreign key to ``ExternalModel``.

        Returns
        -------
        Sequence[LoRAAdapter]
            All adapter rows for the model, ordered by creation time.
        """
        stmt = (
            select(LoRAAdapter)
            .where(LoRAAdapter.external_model_id == model_id)
            .order_by(LoRAAdapter.id)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_by_adapter_id(
        self, model_id: int, adapter_id: str
    ) -> LoRAAdapter | None:
        """Look up a single adapter by its scoped identifier.

        Parameters
        ----------
        model_id : int
            FK to ``ExternalModel``.
        adapter_id : str
            The adapter's scoped identifier (e.g. ``"run_42"``).

        Returns
        -------
        LoRAAdapter | None
            The matching adapter, or ``None`` if not found.
        """
        stmt = (
            select(LoRAAdapter)
            .where(
                LoRAAdapter.external_model_id == model_id,
                LoRAAdapter.adapter_id == adapter_id,
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def add(self, adapter: LoRAAdapter) -> LoRAAdapter:
        """Persist a new LoRA adapter row.

        Parameters
        ----------
        adapter : LoRAAdapter
            Unsaved adapter instance.

        Returns
        -------
        LoRAAdapter
            The saved adapter with generated fields populated.
        """
        self._session.add(adapter)
        await self._session.flush()
        await self._session.refresh(adapter)
        return adapter

    async def mark_merged(self, model_id: int, adapter_id: str) -> LoRAAdapter | None:
        """Set the ``merged_at`` timestamp on a completed merge.

        Parameters
        ----------
        model_id : int
            FK to ``ExternalModel``.
        adapter_id : str
            The adapter's scoped identifier.

        Returns
        -------
        LoRAAdapter | None
            The updated adapter, or ``None`` if not found.
        """
        adapter = await self.get_by_adapter_id(model_id, adapter_id)
        if adapter is None:
            return None

        adapter.merged_at = datetime.now(timezone.utc)  # noqa: UP017
        await self._session.flush()
        await self._session.refresh(adapter)
        return adapter
