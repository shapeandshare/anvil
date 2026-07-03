# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""MLflow input resolvers — converts anvil datasets/corpora to MLflow dataset objects.

Provides the ``MlflowInputResolver`` class that bridges anvil's dataset
and corpus records to MLflow's ``Dataset`` entity for experiment input
tracking.
"""

import asyncio
import hashlib
import logging
from pathlib import Path

from mlflow.entities import Dataset
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.repositories.corpora import CorpusRepository
from ...db.repositories.datasets import DatasetRepository

logger = logging.getLogger(__name__)


class MlflowInputResolver:
    """Resolves anvil dataset/corpus records to MLflow dataset inputs.

    Creates ``mlflow.entities.Dataset`` objects with source, digest, and
    name for MLflow experiment input tracking. Supports both datasets
    (flat sample lists) and corpora (directory of files).
    """

    def __init__(self, session: AsyncSession):
        """Initialise the resolver.

        Parameters
        ----------
        session : AsyncSession
            SQLAlchemy async session for database access.
        """
        self._session = session

    @staticmethod
    def content_digest(docs: list[str]) -> str:
        """Compute a SHA-256 content digest from a list of documents.

        Parameters
        ----------
        docs : list[str]
            Document strings to hash.

        Returns
        -------
        str
            Hex-encoded SHA-256 digest.
        """
        h = hashlib.sha256()
        for doc in docs:
            h.update(doc.encode())
        return h.hexdigest()

    async def resolve_dataset(
        self, dataset_id: int, role: str = "training"
    ) -> tuple[Dataset, str]:
        """Resolve a dataset record to an MLflow dataset input.

        Loads sample texts, computes a content digest, and creates
        an MLflow ``Dataset`` entity with ``"local"`` source type.

        Parameters
        ----------
        dataset_id : int
            The dataset ID.
        role : str
            Role label for the input (e.g. ``"training"``).
            Defaults to ``"training"``.

        Returns
        -------
        tuple[Dataset, str]
            Tuple of (``Dataset`` entity, content digest string).

        Raises
        ------
        ValueError
            If the dataset is not found.
        """
        repo = DatasetRepository(self._session)
        ds = await repo.get(dataset_id)
        if ds is None:
            raise ValueError(f"Dataset {dataset_id} not found")

        docs: list[str] = []
        try:

            def _read_file() -> list[str]:
                return sorted(Path(ds.file_path).read_text("utf-8").splitlines())

            docs = await asyncio.get_event_loop().run_in_executor(None, _read_file)
        except Exception:
            docs = []

        digest = MlflowInputResolver.content_digest(docs)
        name = f"{ds.name}@v{ds.id}"

        mlflow_ds = Dataset(
            name=name,
            digest=digest,
            source_type="local",
            source=ds.file_path,
        )

        return mlflow_ds, digest

    async def resolve_corpus(self, corpus_id: int) -> tuple[Dataset, list[str], str]:
        """Resolve a corpus record to an MLflow dataset input.

        Loads all file contents from the corpus directory, computes
        a content digest, and creates an MLflow ``Dataset`` entity
        with ``"local"`` source type.

        Parameters
        ----------
        corpus_id : int
            The corpus ID.

        Returns
        -------
        tuple[Dataset, list[str], str]
            Tuple of (``Dataset`` entity, list of artifact file paths,
            content digest string).

        Raises
        ------
        ValueError
            If the corpus is not found.
        """
        repo = CorpusRepository(self._session)
        corpus = await repo.get(corpus_id)
        if corpus is None:
            raise ValueError(f"Corpus {corpus_id} not found")

        root = Path(corpus.root_path)

        def _load() -> tuple[list[str], list[str]]:
            docs: list[str] = []
            artifact_paths: list[str] = []
            if root.exists():
                for p in sorted(root.rglob("*")):
                    if p.is_file():
                        try:
                            text = p.read_text("utf-8")
                            docs.append(text)
                            artifact_paths.append(str(p))
                        except Exception:
                            logger.debug(
                                "Skipping unreadable corpus file %s",
                                p,
                                exc_info=True,
                            )
                            pass
            return docs, artifact_paths

        docs, artifact_paths = await asyncio.get_event_loop().run_in_executor(
            None, _load
        )
        digest = MlflowInputResolver.content_digest(docs)

        mlflow_ds = Dataset(
            name=f"corpus_{corpus_id}",
            digest=digest,
            source_type="local",
            source=corpus.root_path,
        )

        return mlflow_ds, artifact_paths, digest
