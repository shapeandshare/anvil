"""Repository for ``ExternalModel`` CRUD — LEGACY, scheduled for removal.

This module is retained as a stub to avoid breaking US2-dependent
services during the transition. New code MUST NOT use this module.

.. deprecated::
    Use ``CatalogIdentityRepository`` + ``ModelCatalogService`` instead.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.external_model import ExternalModel


class ExternalModelRepository:
    """Async CRUD repository for ``ExternalModel`` entries (LEGACY).

    .. deprecated::
        Use ``CatalogIdentityRepository`` instead.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, id: int) -> ExternalModel | None:
        result = await self._session.get(ExternalModel, id)
        return result

    async def get_all(self) -> Sequence[ExternalModel]:
        result = await self._session.execute(
            select(ExternalModel).order_by(ExternalModel.created_at.desc())
        )
        return result.scalars().all()

    async def add(self, model: ExternalModel) -> ExternalModel:
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return model

    async def find_by_source(
        self,
        source_type: str,
        source_identifier: str,
        revision_sha: str,
    ) -> ExternalModel | None:
        result = await self._session.execute(
            select(ExternalModel).where(
                ExternalModel.source_type == source_type,
                ExternalModel.source_identifier == source_identifier,
                ExternalModel.revision_sha == revision_sha,
            )
        )
        return result.scalar_one_or_none()

    async def update_fields(self, id: int, **kwargs: Any) -> ExternalModel | None:
        model = await self._session.get(ExternalModel, id)
        if model is None:
            return None
        for key, value in kwargs.items():
            setattr(model, key, value)
        await self._session.flush()
        await self._session.refresh(model)
        return model

    async def delete(self, id: int) -> None:
        await self._session.execute(delete(ExternalModel).where(ExternalModel.id == id))
