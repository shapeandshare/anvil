"""DemoBootstrapService — orchestrates importing bundled demo data into the database.

This service walks ``data/demo/`` (bundled inside the ``anvil`` package),
discovers subdirectories (corpora) and ``.txt`` files (datasets), and imports
them into the database via the existing corpus and dataset ingestion pipelines.
It is designed to be called from a CLI command (``anvil bootstrap-datasets``),
from ``make setup``, or from app startup.
"""

import asyncio
import importlib.resources as _resources
import time
from collections.abc import Sequence
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models.corpus import Corpus
from ..db.models.dataset import Dataset
from ..db.repositories.corpora import CorpusRepository
from ..db.repositories.datasets import DatasetRepository
from .bootstrap_result import BootstrapResult
from .corpora import CorpusService
from .corpus_loader import CorpusLoader
from .dataset_import import DatasetImportService
from .datasets import DatasetService


# Resolve the bundled demo data directory from the installed package,
# not from the current working directory (which would be empty for pip users).
# We use a function rather than a module-level constant so it can be
# lazily resolved and monkeypatch-friendly for tests.
def _resolve_demo_dir() -> Path:
    """Return the absolute path to the bundled demo data directory."""
    ref = _resources.files("anvil").joinpath("data", "demo")
    return Path(str(ref))


DEMO_DIR = _resolve_demo_dir()
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


class DemoBootstrapService:
    """Orchestrates importing demo data from ``data/demo/`` into the database.

    Typical usage::

        async with AsyncSessionLocal() as session:
            svc = DemoBootstrapService(session)
            result = await svc.bootstrap_all()
            await session.commit()
    """

    def __init__(self, session: AsyncSession):
        """Initialise the bootstrap service.

        Parameters
        ----------
        session : AsyncSession
            SQLAlchemy async session for database access.
        """
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
        """Import all demo corpora and datasets into the database.

        Walks the demo data directory, discovers subdirectories
        (corpora) and ``.txt`` files (datasets), and imports them
        via the existing corpus and dataset ingestion pipelines.
        Skips entities that already exist.

        Returns
        -------
        BootstrapResult
            Outcome with counts of created/skipped entities and
            any error messages.
        """
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
        """Return the default demo corpus (``Demo - medium/alice``).

        Returns
        -------
        Corpus or None
            The default corpus if it exists, ``None`` otherwise.
        """
        return await self._corpus_repo.get_by_name(DEFAULT_CORPUS_NAME)

    async def list_demo_corpora(self) -> Sequence[Corpus]:
        """List all demo corpora (names starting with ``Demo - ``).

        Returns
        -------
        Sequence[Corpus]
            Demo corpus records.
        """
        all_corpora = await self._corpus_repo.get_all()
        return [c for c in all_corpora if c.name.startswith(DEMO_NAME_PREFIX)]

    async def list_demo_datasets(self) -> Sequence[Dataset]:
        """List all demo datasets (names starting with ``Demo - ``).

        Returns
        -------
        Sequence[Dataset]
            Demo dataset records.
        """
        all_datasets = await self._dataset_repo.get_all()
        return [d for d in all_datasets if d.name.startswith(DEMO_NAME_PREFIX)]

    async def get_demo_corpus(self, name: str) -> Corpus | None:
        """Get a demo corpus by its short name (without prefix).

        Parameters
        ----------
        name : str
            Short corpus name (e.g. ``"small/names"``).

        Returns
        -------
        Corpus or None
            The matching corpus record or ``None``.
        """
        return await self._corpus_repo.get_by_name(f"{DEMO_NAME_PREFIX}{name}")

    async def get_demo_dataset(self, name: str) -> Dataset | None:
        """Get a demo dataset by its short name (without prefix).

        Parameters
        ----------
        name : str
            Short dataset name (e.g. ``"small/names"``).

        Returns
        -------
        Dataset or None
            The matching dataset record or ``None``.
        """
        return await self._dataset_repo.get_by_name(f"{DEMO_NAME_PREFIX}{name}")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _bootstrap_corpus(self, item: Path, result: BootstrapResult) -> bool:
        """Import a single demo directory as a corpus.

        Parameters
        ----------
        item : Path
            Path to the directory to import.
        result : BootstrapResult
            Accumulator for results and errors.

        Returns
        -------
        bool
            ``True`` if the corpus was created, ``False`` if skipped
            or failed.
        """
        name = self._corpus_name_for(item)
        existing = await self._corpus_repo.get_by_name(name)
        if existing is not None:
            result.corpora_skipped += 1
            return False

        rel = str(item.relative_to(DEMO_DIR))
        cfg = _CORPUS_CONFIG.get(rel, {})
        try:
            resolved = await asyncio.to_thread(item.resolve)
            corpus = await self._corpus_svc.create(
                name=name,
                root_path=str(resolved),
                description=f"Demo corpus: {item.name}",
                chunking_strategy=cfg.get("strategy", "file"),
                block_size=cfg.get("block_size", 16),
                chunk_overlap=cfg.get("overlap", 0.0),
            )
            await self._corpus_svc.ingest(corpus.id)
            return True
        except Exception as exc:
            result.errors.append(f"Failed to create corpus '{name}': {exc}")
            return False

    async def _bootstrap_dataset(self, item: Path, result: BootstrapResult) -> bool:
        """Import a single ``.txt`` file as a dataset.

        Parameters
        ----------
        item : Path
            Path to the ``.txt`` file to import.
        result : BootstrapResult
            Accumulator for results and errors.

        Returns
        -------
        bool
            ``True`` if the dataset was created, ``False`` if skipped
            or failed.
        """
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
            text = await asyncio.to_thread(item.read_text, encoding="utf-8")
            import_svc = DatasetImportService(self._session, dataset.id)
            await import_svc.commit_import(text, fmt="txt")
            return True
        except Exception as exc:
            result.errors.append(f"Failed to create dataset '{name}': {exc}")
            return False

    @staticmethod
    def _corpus_name_for(item: Path) -> str:
        """Generate the prefixed corpus name for a demo directory.

        Parameters
        ----------
        item : Path
            Path to the corpus directory.

        Returns
        -------
        str
            Prefixed name (e.g. ``"Demo - small/names"``).
        """
        rel = item.relative_to(DEMO_DIR)
        return f"{DEMO_NAME_PREFIX}{rel}"

    @staticmethod
    def _dataset_name_for(item: Path) -> str:
        """Generate the prefixed dataset name for a demo file.

        Parameters
        ----------
        item : Path
            Path to the ``.txt`` file.

        Returns
        -------
        str
            Prefixed name (e.g. ``"Demo - small/names"``).
        """
        rel = item.relative_to(DEMO_DIR)
        stem = rel.with_suffix("")
        return f"{DEMO_NAME_PREFIX}{stem}"

    @staticmethod
    def is_demo_entity(name: str) -> bool:
        """Check whether a name belongs to a demo entity.

        Parameters
        ----------
        name : str
            The entity name to check.

        Returns
        -------
        bool
            ``True`` if the name starts with the demo prefix.
        """
        return name.startswith(DEMO_NAME_PREFIX)
