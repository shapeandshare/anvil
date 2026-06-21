# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Repository for the ``Dataset`` entity.

Provides CRUD operations and domain-specific queries (search,
referencing config checks) via the async SQLAlchemy repository
pattern.

Classes
-------
DatasetRepository
    Data access for training datasets and their associated
    configuration references.
"""

from collections.abc import Sequence

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.dataset import Dataset
from ..models.training_config import TrainingConfig


class DatasetRepository:
    """Repository for ``Dataset`` entity CRUD and search operations.

    Supports create, read, update, delete, name-based lookup, text
    search, and detection of referencing training configurations.
    """

    def __init__(self, session: AsyncSession):
        """Initialize the repository with a database session.

        Parameters
        ----------
        session : AsyncSession
            SQLAlchemy async session used for all database operations.
        """
        self._session = session

    async def get(self, id: int) -> Dataset | None:
        """Retrieve a dataset by its primary key.

        Parameters
        ----------
        id : int
            Primary key of the ``Dataset`` to retrieve.

        Returns
        -------
        Dataset | None
            The matching ``Dataset`` instance, or ``None`` if no
            record exists with the given ``id``.
        """
        return await self._session.get(Dataset, id)

    async def get_all(self) -> Sequence[Dataset]:
        """Retrieve all datasets, ordered by creation date descending.

        Returns
        -------
        Sequence[Dataset]
            All ``Dataset`` records, sorted with the most recently
            created first.
        """
        result = await self._session.execute(
            select(Dataset).order_by(Dataset.created_at.desc())
        )
        return result.scalars().all()

    async def add(self, dataset: Dataset) -> Dataset:
        """Persist a new dataset and return it with a generated primary
        key.

        Parameters
        ----------
        dataset : Dataset
            The unsaved ``Dataset`` instance to add to the database.

        Returns
        -------
        Dataset
            The same instance after flush and refresh, with its ``id``
            and server-side defaults populated.
        """
        self._session.add(dataset)
        await self._session.flush()
        await self._session.refresh(dataset)
        return dataset

    async def get_by_name(self, name: str) -> Dataset | None:
        """Retrieve a dataset by its unique name.

        Parameters
        ----------
        name : str
            The exact name of the dataset to look up.

        Returns
        -------
        Dataset | None
            The matching ``Dataset`` instance, or ``None`` if no
            record exists with the given ``name``.
        """
        result = await self._session.execute(
            select(Dataset).where(Dataset.name == name)
        )
        return result.scalar_one_or_none()

    async def count_by_origin(self, origin: str) -> int:
        """Count datasets with the given origin value.

        Parameters
        ----------
        origin : str
            The origin value to count (e.g., ``"bundled"`` or ``"user"``).

        Returns
        -------
        int
            Number of datasets with this origin.
        """
        stmt = select(func.count()).where(Dataset.origin == origin)
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def update(self, dataset: Dataset) -> Dataset:
        """Persist in-memory changes to an existing dataset.

        Parameters
        ----------
        dataset : Dataset
            A previously persisted ``Dataset`` instance whose
            attributes have been modified.

        Returns
        -------
        Dataset
            The same instance after flush and refresh, reflecting
            updated server-side state.
        """
        await self._session.flush()
        await self._session.refresh(dataset)
        return dataset

    async def update_fields(self, id: int, **kwargs) -> Dataset | None:
        """Update specific fields on a dataset by primary key.

        Parameters
        ----------
        id : int
            Primary key of the dataset to update.
        **kwargs
            Column-value pairs to apply as the update payload.

        Returns
        -------
        Dataset | None
            The refreshed ``Dataset`` instance after the update, or
            ``None`` if no record exists with the given ``id``.
        """
        await self._session.execute(
            update(Dataset).where(Dataset.id == id).values(**kwargs)
        )
        await self._session.flush()
        return await self._session.get(Dataset, id)

    async def search(self, query: str) -> Sequence[Dataset]:
        """Search datasets by name (case-insensitive partial match).

        Parameters
        ----------
        query : str
            The search string to match against dataset names.

        Returns
        -------
        Sequence[Dataset]
            Matching ``Dataset`` records ordered by creation date
            descending.
        """
        result = await self._session.execute(
            select(Dataset)
            .where(Dataset.name.ilike(f"%{query}%"))
            .order_by(Dataset.created_at.desc())
        )
        return result.scalars().all()

    async def delete(self, id: int) -> None:
        """Hard-delete a dataset by its primary key.

        Parameters
        ----------
        id : int
            Primary key of the dataset to permanently delete.

        Returns
        -------
        None
        """
        await self._session.execute(delete(Dataset).where(Dataset.id == id))

    async def has_referencing_configs(self, id: int) -> list[TrainingConfig]:
        """Check if any training configurations reference a dataset.

        Parameters
        ----------
        id : int
            Primary key of the dataset to check.

        Returns
        -------
        list[TrainingConfig]
            A list of ``TrainingConfig`` records that reference the
            dataset. An empty list means no configurations reference
            it.
        """
        result = await self._session.execute(
            select(TrainingConfig).where(TrainingConfig.dataset_id == id)
        )
        return list(result.scalars().all())
