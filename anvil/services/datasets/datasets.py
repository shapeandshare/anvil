"""Dataset CRUD service — manages dataset records and document loading.

Provides the ``DatasetService`` class for creating, reading, updating,
deleting, and searching datasets, as well as loading their sample
content from the file store.
"""

from ...db.models.dataset import Dataset
from ...db.repositories.datasets import DatasetRepository
from ...storage.local import LocalFileStore


class DatasetService:
    """Business logic for dataset CRUD and document loading.

    Wraps a ``DatasetRepository`` and a ``LocalFileStore`` to provide
    higher-level dataset operations with constraint validation and
    MLflow lifecycle event hooks.
    """

    def __init__(self, repo: DatasetRepository, store: LocalFileStore | None = None):
        """Initialise the dataset service.

        Parameters
        ----------
        repo : DatasetRepository
            Repository for dataset persistence.
        store : LocalFileStore, optional
            File store for reading sample content. Defaults to a new
            ``LocalFileStore`` at ``"data/datasets"``.
        """
        self._repo = repo
        self._store = store or LocalFileStore("data/datasets")

    async def list_datasets(self):
        """Return all datasets.

        Returns
        -------
        Sequence[Dataset]
            All dataset records.
        """
        return await self._repo.get_all()

    async def get_dataset(self, id: int):
        """Retrieve a single dataset by ID.

        Parameters
        ----------
        id : int
            The dataset ID.

        Returns
        -------
        Dataset or None
            The dataset record if found, ``None`` otherwise.
        """
        return await self._repo.get(id)

    async def create_dataset(
        self, name: str, description: str | None = None
    ) -> Dataset:
        """Create a new dataset.

        Parameters
        ----------
        name : str
            Human-readable name for the dataset.
        description : str, optional
            Optional description. Defaults to ``None``.

        Returns
        -------
        Dataset
            The newly created dataset record.
        """
        dataset = Dataset(name=name, description=description, filename="", file_path="")
        return await self._repo.add(dataset)

    async def update_dataset(
        self, id: int, name: str | None = None, description: str | None = None
    ) -> Dataset | None:
        """Update a dataset's name and/or description.

        Parameters
        ----------
        id : int
            The dataset ID.
        name : str, optional
            New name. ``None`` means unchanged.
        description : str, optional
            New description. ``None`` means unchanged.

        Returns
        -------
        Dataset or None
            The updated dataset, or ``None`` if not found.
        """
        dataset = await self._repo.get(id)
        if dataset is None:
            return None
        if name is not None:
            dataset.name = name
        if description is not None:
            dataset.description = description
        return await self._repo.update(dataset)

    async def delete_dataset(self, id: int):
        """Delete a dataset by ID.

        Checks for referencing training configs before deletion and
        logs a lifecycle event to MLflow in the background.

        Parameters
        ----------
        id : int
            The dataset ID to delete.

        Raises
        ------
        ValueError
            If one or more training configs reference this dataset.
        """
        configs = await self._repo.has_referencing_configs(id)
        if configs:
            names = [c.name or f"config #{c.id}" for c in configs]
            raise ValueError(
                f"Cannot delete dataset: {len(configs)} training config(s) reference it: {names}"
            )

        # Non-blocking MLflow lifecycle hook
        try:
            from ..tracking.tracking import TrackingService

            tracking_svc = TrackingService()
            if not tracking_svc.is_degraded:
                await tracking_svc.log_dataset_lifecycle_event(
                    dataset_id=id,
                    event_type="delete",
                )
        except Exception:
            pass

        await self._repo.delete(id)

    async def search_datasets(self, query: str):
        """Search datasets by name or description.

        Parameters
        ----------
        query : str
            Search query string.

        Returns
        -------
        Sequence[Dataset]
            Matching dataset records.
        """
        return await self._repo.search(query)

    async def load_docs(self, dataset_id: int) -> list[str]:
        """Load all active sample texts for a dataset.

        Reads each active sample's content from the file store.

        Parameters
        ----------
        dataset_id : int
            The dataset ID.

        Returns
        -------
        list[str]
            All active sample texts.
        """
        from ...db.repositories.curation import SampleRepository

        samples = await SampleRepository(self._repo._session).get_active_texts(
            dataset_id
        )
        texts = []
        for sample in samples:
            text_bytes = b""
            async for chunk in self._store.get(sample.file_path):
                text_bytes += chunk
            texts.append(text_bytes.decode("utf-8"))
        return texts
