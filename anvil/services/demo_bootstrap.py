"""DemoBootstrapService — orchestrates importing bundled demo data into the database.

This service walks ``data/demo/``, discovers subdirectories (corpora) and ``.txt``
files (datasets), and imports them into the database via the existing corpus and
dataset ingestion pipelines. It is designed to be called from a CLI command
(``anvil bootstrap-datasets``), from ``make setup``, or from app startup.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from anvil.db.models.corpus import Corpus
from anvil.db.models.training_config import Dataset
from anvil.db.repositories.corpora import CorpusRepository
from anvil.db.repositories.datasets import DatasetRepository
from anvil.services.corpus_loader import CorpusLoader
from anvil.services.corpora import CorpusService
from anvil.services.dataset_import import DatasetImportService
from anvil.services.datasets import DatasetService

DEMO_DIR = Path("data/demo")
DEMO_NAME_PREFIX = "Demo - "
DEFAULT_CORPUS_NAME = "Demo - medium/alice"

# Chunking configuration per directory — determines how files are split into
# training documents during corpus ingestion.
_CORPUS_CONFIG: dict[str, dict] = {
    "small/names": {"strategy": "file", "block_size": 16, "overlap": 0.0},
    "small/hello-world": {"strategy": "file", "block_size": 16, "overlap": 0.0},
    "medium/alice": {"strategy": "windowed", "block_size": 64, "overlap": 0.25},
    "large/earnest": {"strategy": "windowed", "block_size": 128, "overlap": 0.25},
}


@dataclass
class BootstrapResult:
    """Outcome of a ``bootstrap_all()`` run."""

    corpora_created: int = 0
    datasets_created: int = 0
    corpora_skipped: int = 0
    datasets_skipped: int = 0
    errors: list[str] = field(default_factory=list)
    total_time_ms: float = 0.0


class DemoBootstrapService:
    """Orchestrates importing demo data from ``data/demo/`` into the database.

    Typical usage::

        async with AsyncSessionLocal() as session:
            svc = DemoBootstrapService(session)
            result = await svc.bootstrap_all()
            await session.commit()
    """

    def __init__(self, session: AsyncSession):
        self._session = session
        self._corpus_repo = CorpusRepository(session)
        self._dataset_repo = DatasetRepository(session)
        self._corpus_loader = CorpusLoader()
        self._corpus_svc = CorpusService(self._corpus_repo, self._corpus_loader)
        self._dataset_svc = DatasetService(self._dataset_repo)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def bootstrap_all(self) -> BootstrapResult:
        start = time.monotonic()
        result = BootstrapResult()

        if not DEMO_DIR.is_dir():
            result.errors.append(f"Demo directory not found: {DEMO_DIR}")
            result.total_time_ms = (time.monotonic() - start) * 1000
            return result

        size_dirs = sorted(
            d for d in DEMO_DIR.iterdir() if d.is_dir() and not d.name.startswith(".")
        )

        for size_dir in size_dirs:
            for item in sorted(size_dir.iterdir()):
                if item.is_dir():
                    ok = await self._bootstrap_corpus(item, result)
                    if ok:
                        result.corpora_created += 1
                elif item.suffix == ".txt":
                    ok = await self._bootstrap_dataset(item, result)
                    if ok:
                        result.datasets_created += 1

        result.total_time_ms = (time.monotonic() - start) * 1000
        return result

    async def get_default_corpus(self) -> Corpus | None:
        return await self._corpus_repo.get_by_name(DEFAULT_CORPUS_NAME)

    async def list_demo_corpora(self) -> Sequence[Corpus]:
        all_corpora = await self._corpus_repo.get_all()
        return [c for c in all_corpora if c.name.startswith(DEMO_NAME_PREFIX)]

    async def list_demo_datasets(self) -> Sequence[Dataset]:
        all_datasets = await self._dataset_repo.get_all()
        return [d for d in all_datasets if d.name.startswith(DEMO_NAME_PREFIX)]

    async def get_demo_corpus(self, name: str) -> Corpus | None:
        return await self._corpus_repo.get_by_name(
            f"{DEMO_NAME_PREFIX}{name}"
        )

    async def get_demo_dataset(self, name: str) -> Dataset | None:
        return await self._dataset_repo.get_by_name(
            f"{DEMO_NAME_PREFIX}{name}"
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _bootstrap_corpus(
        self, item: Path, result: BootstrapResult
    ) -> bool:
        name = self._corpus_name_for(item)
        existing = await self._corpus_repo.get_by_name(name)
        if existing is not None:
            result.corpora_skipped += 1
            return False

        rel = str(item.relative_to(DEMO_DIR))
        cfg = _CORPUS_CONFIG.get(rel, {})
        try:
            corpus = await self._corpus_svc.create(
                name=name,
                root_path=str(item.absolute()),
                description=f"Demo corpus: {item.name}",
                chunking_strategy=cfg.get("strategy", "file"),
                block_size=cfg.get("block_size", 16),
                chunk_overlap=cfg.get("overlap", 0.0),
            )
            await self._corpus_svc.ingest(corpus.id)
            return True
        except Exception as exc:
            result.errors.append(
                f"Failed to create corpus '{name}': {exc}"
            )
            return False

    async def _bootstrap_dataset(
        self, item: Path, result: BootstrapResult
    ) -> bool:
        name = self._dataset_name_for(item)
        existing = await self._dataset_repo.get_by_name(name)
        if existing is not None:
            result.datasets_skipped += 1
            return False

        try:
            dataset = await self._dataset_svc.create_dataset(
                name=name,
                description=f"Demo dataset: {item.stem}",
            )
            text = item.read_text(encoding="utf-8")
            import_svc = DatasetImportService(self._session, dataset.id)
            await import_svc.commit_import(text, fmt="txt")
            return True
        except Exception as exc:
            result.errors.append(
                f"Failed to create dataset '{name}': {exc}"
            )
            return False

    @staticmethod
    def _corpus_name_for(item: Path) -> str:
        rel = item.relative_to(DEMO_DIR)
        return f"{DEMO_NAME_PREFIX}{rel}"

    @staticmethod
    def _dataset_name_for(item: Path) -> str:
        rel = item.relative_to(DEMO_DIR)
        stem = rel.with_suffix("")
        return f"{DEMO_NAME_PREFIX}{stem}"

    @staticmethod
    def is_demo_entity(name: str) -> bool:
        return name.startswith(DEMO_NAME_PREFIX)