from collections.abc import Sequence

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from microgpt.db.models.curation import CurationOperation, ImportSource, Sample


class SampleRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get(self, id: int) -> Sample | None:
        return await self._session.get(Sample, id)

    async def get_active_by_dataset(
        self, dataset_id: int, offset: int = 0, limit: int = 50, search: str | None = None
    ) -> tuple[Sequence[Sample], int]:
        query = select(Sample).where(
            Sample.dataset_id == dataset_id, Sample.is_removed == False
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
        self._session.add(sample)
        await self._session.flush()
        await self._session.refresh(sample)
        return sample

    async def add_bulk(self, samples: list[Sample]) -> list[Sample]:
        self._session.add_all(samples)
        await self._session.flush()
        for s in samples:
            await self._session.refresh(s)
        return samples

    async def soft_delete(self, sample_id: int, op_id: int) -> None:
        await self._session.execute(
            update(Sample)
            .where(Sample.id == sample_id)
            .values(is_removed=True, removed_by_op_id=op_id)
        )

    async def soft_delete_bulk(self, sample_ids: list[int], op_id: int) -> int:
        result = await self._session.execute(
            update(Sample)
            .where(Sample.id.in_(sample_ids))
            .values(is_removed=True, removed_by_op_id=op_id)
        )
        return result.rowcount

    async def soft_delete_by_dataset(
        self, dataset_id: int, op_id: int, where_clause=None
    ) -> int:
        stmt = (
            update(Sample)
            .where(Sample.dataset_id == dataset_id, Sample.is_removed == False)
            .values(is_removed=True, removed_by_op_id=op_id)
        )
        if where_clause is not None:
            stmt = stmt.where(where_clause)
        result = await self._session.execute(stmt)
        return result.rowcount

    async def count_active(self, dataset_id: int) -> int:
        result = await self._session.execute(
            select(func.count()).where(
                Sample.dataset_id == dataset_id, Sample.is_removed == False
            )
        )
        return result.scalar() or 0

    async def find_duplicate_hashes(self, dataset_id: int) -> list[tuple[str, int]]:
        result = await self._session.execute(
            select(Sample.content_hash, func.count().label("cnt"))
            .where(Sample.dataset_id == dataset_id, Sample.is_removed == False)
            .group_by(Sample.content_hash)
            .having(func.count() > 1)
        )
        return [(row[0], row[1]) for row in result]

    async def get_active_texts(self, dataset_id: int) -> Sequence[Sample]:
        result = await self._session.execute(
            select(Sample)
            .where(Sample.dataset_id == dataset_id, Sample.is_removed == False)
            .order_by(Sample.index)
        )
        return result.scalars().all()

    async def delete(self, id: int) -> None:
        await self._session.execute(delete(Sample).where(Sample.id == id))


class CurationOperationRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def add(self, op: CurationOperation) -> CurationOperation:
        self._session.add(op)
        await self._session.flush()
        await self._session.refresh(op)
        return op

    async def get_by_dataset(
        self, dataset_id: int
    ) -> Sequence[CurationOperation]:
        result = await self._session.execute(
            select(CurationOperation)
            .where(CurationOperation.dataset_id == dataset_id)
            .order_by(CurationOperation.created_at.desc())
        )
        return result.scalars().all()


class ImportSourceRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def add(self, source: ImportSource) -> ImportSource:
        self._session.add(source)
        await self._session.flush()
        await self._session.refresh(source)
        return source

    async def get_by_dataset(self, dataset_id: int) -> Sequence[ImportSource]:
        result = await self._session.execute(
            select(ImportSource)
            .where(ImportSource.dataset_id == dataset_id)
            .order_by(ImportSource.created_at.desc())
        )
        return result.scalars().all()