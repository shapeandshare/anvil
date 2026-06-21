# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Repository for the ImportSource entity.

Provides data access for ``ImportSource`` persistence using the
async SQLAlchemy repository pattern.

Classes
-------
ImportSourceRepository
    Persistence for import source tracking.
"""

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.import_source import ImportSource


class ImportSourceRepository:
    """Repository for ``ImportSource`` entity persistence.

    Provides methods for recording and querying the provenance of
    sample data imported into a dataset.
    """

    def __init__(self, session: AsyncSession):
        """Initialize the repository with a database session.

        Parameters
        ----------
        session : AsyncSession
            SQLAlchemy async session used for all database operations.
        """
        self._session = session

    async def add(self, source: ImportSource) -> ImportSource:
        """Persist a new import source and return it with a generated
        primary key.

        Parameters
        ----------
        source : ImportSource
            The unsaved ``ImportSource`` instance to add.

        Returns
        -------
        ImportSource
            The same instance after flush and refresh, with its ``id``
            and server-side defaults populated.
        """
        self._session.add(source)
        await self._session.flush()
        await self._session.refresh(source)
        return source

    async def get_by_dataset(self, dataset_id: int) -> Sequence[ImportSource]:
        """Retrieve all import sources for a dataset, ordered by
        creation date descending.

        Parameters
        ----------
        dataset_id : int
            Primary key of the dataset.

        Returns
        -------
        Sequence[ImportSource]
            The matching ``ImportSource`` records, most recent first.
        """
        result = await self._session.execute(
            select(ImportSource)
            .where(ImportSource.dataset_id == dataset_id)
            .order_by(ImportSource.created_at.desc())
        )
        return result.scalars().all()
