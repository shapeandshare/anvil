from microgpt.db.models.training_config import Experiment
from microgpt.db.repositories import ExperimentRepository


class ExperimentService:
    def __init__(self, repo: ExperimentRepository):
        self._repo = repo

    async def list_experiments(self):
        return await self._repo.get_all()

    async def get_experiment(self, id: int):
        return await self._repo.get(id)

    async def delete_experiment(self, id: int):
        await self._repo.delete(id)

    async def create_experiment(
        self, config_id: int, dataset_id: int | None = None
    ) -> Experiment:
        exp = Experiment(config_id=config_id, dataset_id=dataset_id, status="running")
        return await self._repo.add(exp)
