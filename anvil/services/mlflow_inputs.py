from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path
from typing import Any

import mlflow.data
from mlflow.data.meta_dataset import MetaDataset
from mlflow.data.sources import LocalArtifactDatasetSource  # type: ignore[attr-defined]
from sqlalchemy.ext.asyncio import AsyncSession

from anvil.db.repositories.corpora import CorpusRepository
from anvil.db.repositories.datasets import DatasetRepository


class MlflowInputResolver:
    def __init__(self, session: AsyncSession):
        self._session = session

    @staticmethod
    def content_digest(docs: list[str]) -> str:
        h = hashlib.sha256()
        for doc in docs:
            h.update(doc.encode())
        return h.hexdigest()

    async def resolve_dataset(
        self, dataset_id: int, role: str = "training"
    ) -> tuple[Any, str]:
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

        if docs:
            import pandas as pd

            df = pd.DataFrame({"text": docs})
            mlflow_ds = mlflow.data.from_pandas(  # type: ignore[attr-defined]
                df,
                source=LocalArtifactDatasetSource(ds.file_path),
                name=name,
                digest=digest,
            )
        else:
            mlflow_ds = MetaDataset(  # type: ignore[abstract]
                source=LocalArtifactDatasetSource(ds.file_path),
                name=name,
                digest=digest,
            )

        return mlflow_ds, digest

    async def resolve_corpus(self, corpus_id: int) -> tuple[Any, list[str], str]:
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
                            pass
            return docs, artifact_paths

        docs, artifact_paths = await asyncio.get_event_loop().run_in_executor(
            None, _load
        )
        digest = MlflowInputResolver.content_digest(docs)

        meta_ds = MetaDataset(  # type: ignore[abstract]
            source=LocalArtifactDatasetSource(corpus.root_path),
            name=f"corpus_{corpus_id}",
            digest=digest,
        )

        return meta_ds, artifact_paths, digest
