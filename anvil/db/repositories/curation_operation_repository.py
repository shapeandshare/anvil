"""Repository for the CurationOperation entity.

Provides data access for ``CurationOperation`` persistence using the
async SQLAlchemy repository pattern.

Classes
-------
CurationOperationRepository
    Persistence for curation operation metadata.
"""

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.curation_operation import CurationOperation


class CurationOperationRepository:
    """Repository for ``CurationOperation`` entity persistence.

    Provides methods for recording and querying curation operations
    (e.g. sample removals) associated with datasets.
    """

    def __init__(self, session: AsyncSession):
        """Initialize the repository with a database session.

        Parameters
        ----------
        session : AsyncSession
            SQLAlchemy async session used for all database operations.
        """
        self._session = session

    async def add(self, op: CurationOperation) -> CurationOperation:
        """Persist a new curation operation and return it with a
        generated primary key.

        Parameters
        ----------
        op : CurationOperation
            The unsaved ``CurationOperation`` instance to add.

        Returns
        -------
        CurationOperation
            The same instance after flush and refresh, with its ``id``
            and server-side defaults populated.
        """
        self._session.add(op)
        await self._session.flush()
        await self._session.refresh(op)
        return op

    async def get_by_dataset(self, dataset_id: int) -> Sequence[CurationOperation]:
        """Retrieve all curation operations for a dataset, ordered by
        creation date descending.

        Parameters
        ----------
        dataset_id : int
            Primary key of the dataset.

        Returns
        -------
        Sequence[CurationOperation]
            The matching ``CurationOperation`` records, most recent
            first.
        """
        result = await self._session.execute(
            select(CurationOperation)
            .where(CurationOperation.dataset_id == dataset_id)
            .order_by(CurationOperation.created_at.desc())
        )
        return result.scalars().all()
