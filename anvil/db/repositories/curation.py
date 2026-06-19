"""Repository for the Sample entity.

Provides data access for ``Sample`` persistence using the async
SQLAlchemy repository pattern.

Classes
-------
SampleRepository
    CRUD and query operations for training samples.
"""

from collections.abc import Sequence

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.sample import Sample


class SampleRepository:
    """Repository for ``Sample`` entity CRUD and curation queries.

    Provides methods for adding, retrieving, soft-deleting, and
    querying training samples within a dataset. All operations use
    the injected async session.
    """

    def __init__(self, session: AsyncSession):
        """Initialize the repository with a database session.

        Parameters
        ----------
        session : AsyncSession
            SQLAlchemy async session used for all database operations.
        """
        self._session = session

    async def get(self, id: int) -> Sample | None:
        """Retrieve a sample by its primary key.

        Parameters
        ----------
        id : int
            Primary key of the ``Sample`` to retrieve.

        Returns
        -------
        Sample | None
            The matching ``Sample`` instance, or ``None`` if no record
            exists with the given ``id``.
        """
        return await self._session.get(Sample, id)

    async def get_active_by_dataset(
        self,
        dataset_id: int,
        offset: int = 0,
        limit: int = 50,
        search: str | None = None,
    ) -> tuple[Sequence[Sample], int]:
        """Retrieve active samples for a dataset with pagination and
        optional content hash prefix search.

        Parameters
        ----------
        dataset_id : int
            Primary key of the parent dataset.
        offset : int
            Number of records to skip. Defaults to ``0``.
        limit : int
            Maximum number of records to return. Defaults to ``50``.
        search : str, optional
            If provided, filters samples whose ``content_hash`` starts
            with this value. Defaults to ``None`` (no filter).

        Returns
        -------
        tuple[Sequence[Sample], int]
            A tuple of ``(samples, total_count)`` where ``samples``
            is the paginated list and ``total_count`` is the total
            number of active samples matching the filter.
        """
        query = select(Sample).where(
            Sample.dataset_id == dataset_id, not Sample.is_removed
        )
        count_query = select(func.count()).select_from(query.subquery())

        if search:
            # Search by content_hash prefix or index range — full text search uses file content
            query = query.filter(Sample.content_hash.startswith(search))

        query = query.order_by(Sample.index).offset(offset).limit(limit)
        samples = (await self._session.execute(query)).scalars().all()
        total = (await self._session.execute(count_query)).scalar() or 0
        return samples, total

    async def add(self, sample: Sample) -> Sample:
        """Persist a new sample and return it with a generated primary
        key.

        Parameters
        ----------
        sample : Sample
            The unsaved ``Sample`` instance to add to the database.

        Returns
        -------
        Sample
            The same instance after flush and refresh, with its ``id``
            and server-side defaults populated.
        """
        self._session.add(sample)
        await self._session.flush()
        await self._session.refresh(sample)
        return sample

    async def add_bulk(self, samples: list[Sample]) -> list[Sample]:
        """Persist multiple samples in a single batch.

        Parameters
        ----------
        samples : list[Sample]
            The unsaved ``Sample`` instances to add to the database.

        Returns
        -------
        list[Sample]
            The same instances after flush and refresh, with their
            ``id`` and server-side defaults populated.
        """
        self._session.add_all(samples)
        await self._session.flush()
        for s in samples:
            await self._session.refresh(s)
        return samples

    async def soft_delete(self, sample_id: int, op_id: int) -> None:
        """Mark a single sample as removed without deleting the row.

        Parameters
        ----------
        sample_id : int
            Primary key of the sample to soft-delete.
        op_id : int
            Primary key of the curation operation that caused the
            removal.

        Returns
        -------
        None
        """
        await self._session.execute(
            update(Sample)
            .where(Sample.id == sample_id)
            .values(is_removed=True, removed_by_op_id=op_id)
        )

    async def soft_delete_bulk(self, sample_ids: list[int], op_id: int) -> int:
        """Mark multiple samples as removed in a single statement.

        Parameters
        ----------
        sample_ids : list[int]
            Primary keys of the samples to soft-delete.
        op_id : int
            Primary key of the curation operation that caused the
            removal.

        Returns
        -------
        int
            The number of rows updated.
        """
        result = await self._session.execute(
            update(Sample)
            .where(Sample.id.in_(sample_ids))
            .values(is_removed=True, removed_by_op_id=op_id)
        )
        return result.rowcount

    async def soft_delete_by_dataset(
        self, dataset_id: int, op_id: int, where_clause=None
    ) -> int:
        """Mark all active samples in a dataset as removed, optionally
        restricted by a WHERE clause.

        Parameters
        ----------
        dataset_id : int
            Primary key of the dataset whose samples should be
            soft-deleted.
        op_id : int
            Primary key of the curation operation that caused the
            removal.
        where_clause : BinaryExpression, optional
            Additional SQLAlchemy filter expression to restrict which
            samples are soft-deleted. Defaults to ``None`` (all active
            samples in the dataset are removed).

        Returns
        -------
        int
            The number of rows updated.
        """
        stmt = (
            update(Sample)
            .where(Sample.dataset_id == dataset_id, not Sample.is_removed)
            .values(is_removed=True, removed_by_op_id=op_id)
        )
        if where_clause is not None:
            stmt = stmt.where(where_clause)
        result = await self._session.execute(stmt)
        return result.rowcount

    async def count_active(self, dataset_id: int) -> int:
        """Count the number of active (non-removed) samples in a
        dataset.

        Parameters
        ----------
        dataset_id : int
            Primary key of the dataset.

        Returns
        -------
        int
            The count of active samples.
        """
        result = await self._session.execute(
            select(func.count()).where(
                Sample.dataset_id == dataset_id, not Sample.is_removed
            )
        )
        return result.scalar() or 0

    async def find_duplicate_hashes(self, dataset_id: int) -> list[tuple[str, int]]:
        """Find content hashes that appear more than once in a dataset.

        Parameters
        ----------
        dataset_id : int
            Primary key of the dataset to scan.

        Returns
        -------
        list[tuple[str, int]]
            A list of ``(content_hash, count)`` tuples for hashes
            that appear more than once among active samples.
        """
        result = await self._session.execute(
            select(Sample.content_hash, func.count().label("cnt"))
            .where(Sample.dataset_id == dataset_id, not Sample.is_removed)
            .group_by(Sample.content_hash)
            .having(func.count() > 1)
        )
        return [(row[0], row[1]) for row in result]

    async def get_active_texts(self, dataset_id: int) -> Sequence[Sample]:
        """Retrieve all active samples for a dataset ordered by index.

        Parameters
        ----------
        dataset_id : int
            Primary key of the dataset.

        Returns
        -------
        Sequence[Sample]
            All active ``Sample`` records ordered by ``index``.
        """
        result = await self._session.execute(
            select(Sample)
            .where(Sample.dataset_id == dataset_id, not Sample.is_removed)
            .order_by(Sample.index)
        )
        return result.scalars().all()

    async def delete(self, id: int) -> None:
        """Hard-delete a sample by its primary key.

        Parameters
        ----------
        id : int
            Primary key of the sample to permanently delete.

        Returns
        -------
        None
        """
        await self._session.execute(delete(Sample).where(Sample.id == id))
