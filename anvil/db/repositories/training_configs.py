# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Repository for the ``TrainingConfig`` entity.

Provides CRUD operations for training configuration records via
the async SQLAlchemy repository pattern.

Classes
-------
TrainingConfigRepository
    Data access for training configuration metadata.
"""

from collections.abc import Sequence

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.training_config import TrainingConfig


class TrainingConfigRepository:
    """Repository for ``TrainingConfig`` entity CRUD operations.

    Supports create, read, and delete operations for training
    configuration records that define model hyperparameters and
    associated dataset references.
    """

    def __init__(self, session: AsyncSession):
        """Initialize the repository with a database session.

        Parameters
        ----------
        session : AsyncSession
            SQLAlchemy async session used for all database operations.
        """
        self._session = session

    async def get(self, id: int) -> TrainingConfig | None:
        """Retrieve a training config by its primary key.

        Parameters
        ----------
        id : int
            Primary key of the ``TrainingConfig`` to retrieve.

        Returns
        -------
        TrainingConfig | None
            The matching ``TrainingConfig`` instance, or ``None`` if
            no record exists with the given ``id``.
        """
        return await self._session.get(TrainingConfig, id)

    async def get_all(self) -> Sequence[TrainingConfig]:
        """Retrieve all training configs.

        Returns
        -------
        Sequence[TrainingConfig]
            All ``TrainingConfig`` records in the database.
        """
        result = await self._session.execute(select(TrainingConfig))
        return result.scalars().all()

    async def add(self, config: TrainingConfig) -> TrainingConfig:
        """Persist a new training config and return it with a generated
        primary key.

        Parameters
        ----------
        config : TrainingConfig
            The unsaved ``TrainingConfig`` instance to add to the
            database.

        Returns
        -------
        TrainingConfig
            The same instance after flush and refresh, with its ``id``
            and server-side defaults populated.
        """
        self._session.add(config)
        await self._session.flush()
        await self._session.refresh(config)
        return config

    async def delete(self, id: int) -> None:
        """Hard-delete a training config by its primary key.

        Parameters
        ----------
        id : int
            Primary key of the training config to permanently delete.

        Returns
        -------
        None
        """
        await self._session.execute(
            delete(TrainingConfig).where(TrainingConfig.id == id)
        )
