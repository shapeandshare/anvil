from microgpt.db.repositories.datasets import DatasetRepository
from microgpt.storage.local import LocalFileStore


class DatasetService:
    def __init__(self, repo: DatasetRepository, store: LocalFileStore | None = None):
        self._repo = repo
        self._store = store or LocalFileStore("data/datasets")

    async def list_datasets(self):
        return await self._repo.get_all()

    async def get_dataset(self, id: int):
        return await self._repo.get(id)

    async def delete_dataset(self, id: int):
        await self._repo.delete(id)
