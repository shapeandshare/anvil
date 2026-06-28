# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Dataset CRUD service — manages dataset records and document loading.

Provides the ``DatasetService`` class for creating, reading, updating,
deleting, and searching datasets, as well as loading their sample
content from the file store.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from ...db.models.dataset import Dataset
from ...db.repositories.curation import SampleRepository
from ...db.repositories.datasets import DatasetRepository
from ...storage.local import LocalFileStore
from ..governance.audit_action import AuditAction
from ..governance.audit_outcome import AuditOutcome

if TYPE_CHECKING:
    from ...workspace.workspace_paths import WorkspacePaths
    from ..governance.audit_service import AuditService


class DatasetService:
    """Business logic for dataset CRUD and document loading.

    Wraps a ``DatasetRepository`` and a ``LocalFileStore`` to provide
    higher-level dataset operations with constraint validation and
    MLflow lifecycle event hooks.
    """

    def __init__(
        self,
        repo: DatasetRepository,
        store: LocalFileStore | None = None,
        paths: WorkspacePaths | None = None,
    ):
        """Initialise the dataset service.

        Parameters
        ----------
        repo : DatasetRepository
            Repository for dataset persistence.
        store : LocalFileStore, optional
            File store for reading sample content.  When ``None`` and
            *paths* is provided the store is rooted at
            ``paths.datasets_dir``, otherwise it falls back to
            ``"data/datasets"``.
        paths : WorkspacePaths, optional
            When provided with no explicit *store*, the store is created
            from ``paths.datasets_dir``.
        """
        self._repo = repo
        if store is not None:
            self._store = store
        elif paths is not None:
            self._store = LocalFileStore(str(paths.datasets_dir))
        else:
            self._store = LocalFileStore("data/datasets")

    async def list_datasets(self) -> Sequence[Dataset]:
        """Return all datasets.

        Returns
        -------
        Sequence[Dataset]
            All dataset records.
        """
        return await self._repo.get_all()

    async def get_dataset(self, dataset_id: int) -> Dataset | None:
        """Retrieve a single dataset by ID.

        Parameters
        ----------
        dataset_id : int
            The dataset ID.

        Returns
        -------
        Dataset or None
            The dataset record if found, ``None`` otherwise.
        """
        return await self._repo.get(dataset_id)

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
        self, dataset_id: int, name: str | None = None, description: str | None = None
    ) -> Dataset | None:
        """Update a dataset's name and/or description.

        Parameters
        ----------
        dataset_id : int
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
        dataset = await self._repo.get(dataset_id)
        if dataset is None:
            return None
        if name is not None:
            dataset.name = name
        if description is not None:
            dataset.description = description
        return await self._repo.update(dataset)

    async def delete_dataset(
        self, dataset_id: int, audit: AuditService | None = None
    ) -> None:
        """Delete a dataset by ID.

        Checks for referencing training configs before deletion and
        records a ``delete`` audit event.

        Parameters
        ----------
        dataset_id : int
            The dataset ID to delete.
        audit : AuditService, optional
            The hash-chained audit service. If provided, a ``delete``
            event is appended to the audit trail.

        Raises
        ------
        ValueError
            If one or more training configs reference this dataset.
        """
        configs = await self._repo.has_referencing_configs(dataset_id)
        if configs:
            names = [c.name or f"config #{c.id}" for c in configs]
            raise ValueError(
                f"Cannot delete dataset: {len(configs)} training config(s) reference it: {names}"
            )

        if audit is not None:
            await audit.record(
                action_type=AuditAction.DELETE.value,
                target_type="dataset",
                target_id=str(dataset_id),
                actor="system",
                outcome=AuditOutcome.SUCCESS.value,
            )

        await self._repo.delete(dataset_id)

    async def search_datasets(self, query: str) -> Sequence[Dataset]:
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
        samples = await SampleRepository(
            self._repo._session
        ).get_active_texts(  # pylint: disable=protected-access
            dataset_id
        )
        texts = []
        for sample in samples:
            text_bytes = b""
            async for chunk in self._store.get(sample.file_path):
                text_bytes += chunk
            texts.append(text_bytes.decode("utf-8"))
        return texts
