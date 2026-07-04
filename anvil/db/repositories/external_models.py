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
        """Fetch an ``ExternalModel`` by primary key.

        Parameters
        ----------
        id : int
            Primary key of the ``ExternalModel``.

        Returns
        -------
        ExternalModel or None
            The model if found, ``None`` otherwise.
        """
        result = await self._session.get(ExternalModel, id)
        return result

    async def get_all(self) -> Sequence[ExternalModel]:
        """Return all ``ExternalModel`` entries ordered by creation time descending.

        Returns
        -------
        Sequence[ExternalModel]
            All entries sorted newest-first.
        """
        result = await self._session.execute(
            select(ExternalModel).order_by(ExternalModel.created_at.desc())
        )
        return result.scalars().all()

    async def add(self, model: ExternalModel) -> ExternalModel:
        """Persist a new ``ExternalModel`` and return it with a refreshed state.

        Parameters
        ----------
        model : ExternalModel
            Unsaved model instance.

        Returns
        -------
        ExternalModel
            The same instance after flush and refresh.
        """
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
        """Look up an ``ExternalModel`` by its source composite key.

        Parameters
        ----------
        source_type : str
            The type of source (e.g. ``"huggingface"``, ``"local"``).
        source_identifier : str
            Unique identifier within the source (e.g. repo ID).
        revision_sha : str
            Git or revision SHA of the source asset.

        Returns
        -------
        ExternalModel or None
            The matching model if found, ``None`` otherwise.
        """
        result = await self._session.execute(
            select(ExternalModel).where(
                ExternalModel.source_type == source_type,
                ExternalModel.source_identifier == source_identifier,
                ExternalModel.revision_sha == revision_sha,
            )
        )
        return result.scalar_one_or_none()

    async def update_fields(self, id: int, **kwargs: Any) -> ExternalModel | None:
        """Update arbitrary fields on an ``ExternalModel`` by primary key.

        Parameters
        ----------
        id : int
            Primary key of the model to update.
        **kwargs : Any
            Field names and values to set on the model.

        Returns
        -------
        ExternalModel or None
            The updated model if found, ``None`` otherwise.
        """
        model = await self._session.get(ExternalModel, id)
        if model is None:
            return None
        for key, value in kwargs.items():
            setattr(model, key, value)
        await self._session.flush()
        await self._session.refresh(model)
        return model

    async def delete(self, id: int) -> None:
        """Delete an ``ExternalModel`` by primary key.

        Parameters
        ----------
        id : int
            Primary key of the model to delete.
        """
        await self._session.execute(delete(ExternalModel).where(ExternalModel.id == id))
