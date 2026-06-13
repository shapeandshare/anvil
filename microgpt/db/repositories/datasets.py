from collections.abc import Sequence

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from microgpt.db.models.training_config import Dataset, TrainingConfig


class DatasetRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get(self, id: int) -> Dataset | None:
        return await self._session.get(Dataset, id)

    async def get_all(self) -> Sequence[Dataset]:
        result = await self._session.execute(
            select(Dataset).order_by(Dataset.created_at.desc())
        )
        return result.scalars().all()

    async def add(self, dataset: Dataset) -> Dataset:
        self._session.add(dataset)
        await self._session.flush()
        await self._session.refresh(dataset)
        return dataset

    async def update(self, dataset: Dataset) -> Dataset:
        await self._session.flush()
        await self._session.refresh(dataset)
        return dataset

    async def update_fields(self, id: int, **kwargs) -> Dataset | None:
        await self._session.execute(
            update(Dataset).where(Dataset.id == id).values(**kwargs)
        )
        await self._session.flush()
        return await self._session.get(Dataset, id)

    async def search(self, query: str) -> Sequence[Dataset]:
        result = await self._session.execute(
            select(Dataset)
            .where(Dataset.name.ilike(f"%{query}%"))
            .order_by(Dataset.created_at.desc())
        )
        return result.scalars().all()

    async def delete(self, id: int) -> None:
        await self._session.execute(delete(Dataset).where(Dataset.id == id))

    async def has_referencing_configs(self, id: int) -> list[TrainingConfig]:
        result = await self._session.execute(
            select(TrainingConfig).where(TrainingConfig.dataset_id == id)
        )
        return list(result.scalars().all())
