from microgpt.db.repositories.datasets import DatasetRepository
from microgpt.db.models.training_config import Dataset
from microgpt.storage.local import LocalFileStore


class DatasetService:
    def __init__(self, repo: DatasetRepository, store: LocalFileStore | None = None):
        self._repo = repo
        self._store = store or LocalFileStore("data/datasets")

    async def list_datasets(self):
        return await self._repo.get_all()

    async def get_dataset(self, id: int):
        return await self._repo.get(id)

    async def create_dataset(self, name: str, description: str | None = None) -> Dataset:
        dataset = Dataset(name=name, description=description, filename="", file_path="")
        return await self._repo.add(dataset)

    async def update_dataset(self, id: int, name: str | None = None, description: str | None = None) -> Dataset | None:
        dataset = await self._repo.get(id)
        if dataset is None:
            return None
        if name is not None:
            dataset.name = name
        if description is not None:
            dataset.description = description
        return await self._repo.update(dataset)

    async def delete_dataset(self, id: int):
        configs = await self._repo.has_referencing_configs(id)
        if configs:
            names = [c.name or f"config #{c.id}" for c in configs]
            raise ValueError(
                f"Cannot delete dataset: {len(configs)} training config(s) reference it: {names}"
            )
        await self._repo.delete(id)

    async def search_datasets(self, query: str):
        return await self._repo.search(query)

    async def load_docs(self, dataset_id: int) -> list[str]:
        from microgpt.db.repositories.curation import SampleRepository

        samples = await SampleRepository(self._repo._session).get_active_texts(dataset_id)
        texts = []
        for sample in samples:
            text_bytes = b""
            async for chunk in self._store.get(sample.file_path):
                text_bytes += chunk
            texts.append(text_bytes.decode("utf-8"))
        return texts