# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Repository for ``ExternalModel`` CRUD operations."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.external_model import ExternalModel


class ExternalModelRepository:
    """Async CRUD repository for ``ExternalModel`` entries.

    Parameters
    ----------
    session : AsyncSession
        SQLAlchemy async session bound to the application database.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, id: int) -> ExternalModel | None:
        """Retrieve an external model by primary key.

        Parameters
        ----------
        id : int
            Model primary key.

        Returns
        -------
        ExternalModel | None
            The matching model, or ``None`` if not found.
        """
        return await self._session.get(ExternalModel, id)

    async def get_all(self) -> Sequence[ExternalModel]:
        """Return all external models ordered by creation time (newest first).

        Returns
        -------
        Sequence[ExternalModel]
            All registered external models.
        """
        result = await self._session.execute(
            select(ExternalModel).order_by(ExternalModel.created_at.desc())
        )
        return result.scalars().all()

    async def add(self, model: ExternalModel) -> ExternalModel:
        """Persist a new external model entry.

        Parameters
        ----------
        model : ExternalModel
            Unsaved model instance.

        Returns
        -------
        ExternalModel
            The saved model with generated fields populated.
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
        """Look up a model by the canonical identity triple.

        Parameters
        ----------
        source_type : str
            Source type value.
        source_identifier : str
            Source-specific identifier.
        revision_sha : str
            Source revision SHA.

        Returns
        -------
        ExternalModel | None
            Matching model, or ``None`` if no entry exists with that
            identity triple.
        """
        result = await self._session.execute(
            select(ExternalModel).where(
                ExternalModel.source_type == source_type,
                ExternalModel.source_identifier == source_identifier,
                ExternalModel.revision_sha == revision_sha,
            )
        )
        return result.scalar_one_or_none()

    async def update_fields(
        self, id: int, **kwargs: Any
    ) -> ExternalModel | None:
        """Update one or more fields on an external model entry.

        Parameters
        ----------
        id : int
            Model primary key.
        **kwargs : Any
            Column-value pairs to update.

        Returns
        -------
        ExternalModel | None
            The updated model, or ``None`` if not found.
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
        """Delete an external model entry by primary key.

        Parameters
        ----------
        id : int
            Model primary key.
        """
        await self._session.execute(
            delete(ExternalModel).where(ExternalModel.id == id)
        )