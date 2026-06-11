from collections.abc import Sequence

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from microgpt.db.models.training_config import Dataset


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

    async def delete(self, id: int) -> None:
        await self._session.execute(delete(Dataset).where(Dataset.id == id))
