from collections.abc import Sequence

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from microgpt.db.models.training_config import Experiment


class ExperimentRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get(self, id: int) -> Experiment | None:
        return await self._session.get(Experiment, id)

    async def get_all(self) -> Sequence[Experiment]:
        result = await self._session.execute(
            select(Experiment).order_by(Experiment.created_at.desc())
        )
        return result.scalars().all()

    async def add(self, experiment: Experiment) -> Experiment:
        self._session.add(experiment)
        await self._session.flush()
        await self._session.refresh(experiment)
        return experiment

    async def update(self, experiment: Experiment) -> Experiment:
        await self._session.flush()
        await self._session.refresh(experiment)
        return experiment

    async def delete(self, id: int) -> None:
        await self._session.execute(delete(Experiment).where(Experiment.id == id))
