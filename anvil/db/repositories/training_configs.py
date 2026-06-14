from collections.abc import Sequence

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from anvil.db.models.training_config import TrainingConfig


class TrainingConfigRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get(self, id: int) -> TrainingConfig | None:
        return await self._session.get(TrainingConfig, id)

    async def get_all(self) -> Sequence[TrainingConfig]:
        result = await self._session.execute(select(TrainingConfig))
        return result.scalars().all()

    async def add(self, config: TrainingConfig) -> TrainingConfig:
        self._session.add(config)
        await self._session.flush()
        await self._session.refresh(config)
        return config

    async def delete(self, id: int) -> None:
        await self._session.execute(
            delete(TrainingConfig).where(TrainingConfig.id == id)
        )
