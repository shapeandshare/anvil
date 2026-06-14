from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from anvil.db.models.training_config import Experiment


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

    async def create_running(
        self,
        config_id: int | None = None,
        run_name: str | None = None,
        mlflow_run_id: str | None = None,
        dataset_id: int | None = None,
        corpus_id: int | None = None,
        engine_backend: str | None = None,
        device: str | None = None,
    ) -> Experiment:
        exp = Experiment(
            config_id=config_id,
            run_name=run_name,
            mlflow_run_id=mlflow_run_id,
            dataset_id=dataset_id,
            corpus_id=corpus_id,
            engine_backend=engine_backend,
            device=device,
            status="running",
            started_at=datetime.now(UTC),
        )
        return await self.add(exp)

    async def mark_finished(
        self,
        experiment_id: int,
        final_loss: float | None = None,
        generated_samples: str | None = None,
        completed_at: datetime | None = None,
    ) -> Experiment:
        exp = await self.get(experiment_id)
        if exp is None:
            raise ValueError(f"Experiment {experiment_id} not found")
        exp.status = "finished"
        exp.final_loss = final_loss
        exp.generated_samples = generated_samples
        exp.completed_at = completed_at or datetime.now(UTC)
        return await self.update(exp)

    async def mark_failed(
        self,
        experiment_id: int,
        error_message: str | None = None,
        completed_at: datetime | None = None,
    ) -> Experiment:
        exp = await self.get(experiment_id)
        if exp is None:
            raise ValueError(f"Experiment {experiment_id} not found")
        exp.status = "failed"
        exp.error_message = error_message
        exp.completed_at = completed_at or datetime.now(UTC)
        return await self.update(exp)

    async def find_orphaned(self) -> Sequence[Experiment]:
        result = await self._session.execute(
            select(Experiment).where(Experiment.status == "running")
        )
        return result.scalars().all()
