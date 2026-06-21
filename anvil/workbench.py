"""Session-bound AnvilWorkbench — the God Class (Constitution Article VII).

Wraps all anvil services in a single entry point.  DB-backed services
are bound to an ``AsyncSession`` for request-scoped transactions;
stateless services (training, tracking, inference, export) are lazy
properties.  Obtain a workbench via the ``get_workbench`` FastAPI
dependency for request-scoped usage.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from .db.repositories.content_blobs import ContentBlobRepository
    from .db.repositories.content_corpora import ContentCorpusRepository
    from .db.repositories.content_import_jobs import ContentImportJobRepository
    from .db.repositories.content_ingest_sessions import ContentIngestSessionRepository
    from .db.repositories.content_locks import ContentLockRepository
    from .db.repositories.content_sources import ContentSourceRepository
    from .db.repositories.content_versions import ContentVersionRepository
    from .db.repositories.corpora import CorpusRepository
    from .db.repositories.datasets import DatasetRepository
    from .services.content.corpus_service import CorpusService as ContentCorpusService
    from .services.content.ingestion_service import IngestionService
    from .services.content.lineage_service import LineageService
    from .services.content.versioned_content_store import VersionedContentStore
    from .services.datasets.corpora import CorpusService
    from .services.datasets.dataset_curation import DatasetCurationService
    from .services.datasets.dataset_export import DatasetExportService
    from .services.datasets.dataset_import import DatasetImportService
    from .services.datasets.datasets import DatasetService
    from .services.demo.demo_bootstrap import DemoBootstrapService
    from .services.governance.audit_service import AuditService
    from .services.governance.governance_service import GovernanceService
    from .services.training.training import TrainingService
    from .storage.local import LocalFileStore

__all__ = ["AnvilWorkbench"]


class AnvilWorkbench:
    """Session-bound God Class exposing all anvil services.

    Parameters
    ----------
    session : AsyncSession
        Async SQLAlchemy session, scoped to the current request.
        Services created via lazy accessors share this session so
        audit writes, provenance updates, etc. participate in the
        same transaction.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        # DB-backed lazy references.
        self._training: TrainingService | None = None
        self._dataset_repo: DatasetRepository | None = None
        self._corpus_repo: CorpusRepository | None = None
        self._datasets: DatasetService | None = None
        self._corpora: CorpusService | None = None
        self._dataset_curation: DatasetCurationService | None = None
        self._dataset_export: DatasetExportService | None = None
        self._demo: DemoBootstrapService | None = None
        self._store: LocalFileStore | None = None
        self._audit: AuditService | None = None
        self._governance: GovernanceService | None = None
        # Content repository lazy references.
        self._content_corpus_repo: ContentCorpusRepository | None = None
        self._content_source_repo: ContentSourceRepository | None = None
        self._content_version_repo: ContentVersionRepository | None = None
        self._content_ingest_session_repo: ContentIngestSessionRepository | None = None
        self._content_blob_repo: ContentBlobRepository | None = None
        self._content_import_job_repo: ContentImportJobRepository | None = None
        self._content_lock_repo: ContentLockRepository | None = None
        self._content_store: VersionedContentStore | None = None
        self._content_corpora: ContentCorpusService | None = None
        self._content_ingestion: IngestionService | None = None
        self._content_composition: object | None = None  # will be CompositionService
        self._content_lineage: LineageService | None = None
        self._content_imports: object | None = None  # will be ImportService
        self._content_locks: object | None = None  # will be LockService

    # ── Stateless service accessors ─────────────────────────────────────

    @property
    def training(self) -> TrainingService:
        """Return the stateless ``TrainingService``."""
        if self._training is None:
            from .services.training.training import TrainingService

            self._training = TrainingService()
        return self._training

    # ── Repository helpers ──────────────────────────────────────────────

    @property
    def dataset_repo(self) -> DatasetRepository:
        """Lazily-initialised ``DatasetRepository`` bound to *session*."""
        if self._dataset_repo is None:
            from .db.repositories.datasets import DatasetRepository

            self._dataset_repo = DatasetRepository(self._session)
        return self._dataset_repo

    @property
    def corpus_repo(self) -> CorpusRepository:
        """Lazily-initialised ``CorpusRepository`` bound to *session*."""
        if self._corpus_repo is None:
            from .db.repositories.corpora import CorpusRepository

            self._corpus_repo = CorpusRepository(self._session)
        return self._corpus_repo

    @property
    def store(self) -> LocalFileStore:
        """Lazily-initialised ``LocalFileStore`` at ``data/datasets``."""
        if self._store is None:
            from .storage.local import LocalFileStore

            self._store = LocalFileStore("data/datasets")
        return self._store

    # ── DB-backed domain service accessors ──────────────────────────────

    @property
    def datasets(self) -> DatasetService:
        """Return a ``DatasetService`` wired to *session*."""
        if self._datasets is None:
            from .services.datasets.datasets import DatasetService

            self._datasets = DatasetService(self.dataset_repo, self.store)
        return self._datasets

    @property
    def corpora(self) -> CorpusService:
        """Return a ``CorpusService`` wired to *session*."""
        if self._corpora is None:
            from .services.datasets.corpora import CorpusService
            from .services.datasets.corpus_loader import CorpusLoader

            self._corpora = CorpusService(self.corpus_repo, CorpusLoader())
        return self._corpora

    def dataset_import(self, dataset_id: int) -> DatasetImportService:
        """Return a fresh ``DatasetImportService`` for a specific dataset.

        This is a factory — not a property — because each import is scoped
        to one dataset and carries mutable state.
        """
        from .services.datasets.dataset_import import DatasetImportService

        return DatasetImportService(self._session, dataset_id, self.store)

    def dataset_curation(self, dataset_id: int) -> DatasetCurationService:
        """Return a ``DatasetCurationService`` for a specific dataset."""
        if self._dataset_curation is None:
            from .services.datasets.dataset_curation import DatasetCurationService

            self._dataset_curation = DatasetCurationService(
                self._session, dataset_id, self.store
            )
        return self._dataset_curation

    def dataset_export(self, dataset_id: int) -> DatasetExportService:
        """Return a ``DatasetExportService`` for a specific dataset."""
        if self._dataset_export is None:
            from .services.datasets.dataset_export import DatasetExportService

            self._dataset_export = DatasetExportService(
                self._session, dataset_id, self.store
            )
        return self._dataset_export

    @property
    def demo(self) -> DemoBootstrapService:
        """Return a ``DemoBootstrapService`` wired to *session*."""
        if self._demo is None:
            from .services.demo.demo_bootstrap import DemoBootstrapService

            self._demo = DemoBootstrapService(self._session)
        return self._demo

    # ── Governance accessors ────────────────────────────────────────────

    @property
    def audit(self) -> AuditService:
        """Return the hash-chained ``AuditService`` wired to *session*."""
        if self._audit is None:
            from .db.repositories.audit_events import AuditEventRepository
            from .services.governance.audit_service import AuditService

            self._audit = AuditService(AuditEventRepository(self._session))
        return self._audit

    @property
    def governance(self) -> GovernanceService:
        """Return the ``GovernanceService`` wired to *session*."""
        if self._governance is None:
            from .db.repositories.licenses import LicenseRepository
            from .services.governance.governance_service import GovernanceService

            self._governance = GovernanceService(
                LicenseRepository(self._session),
                self.audit,
            )
        return self._governance

    # ── Content repository accessors ────────────────────────────────────

    @property
    def content_corpus_repo(self) -> ContentCorpusRepository:
        """Lazily-initialised ``ContentCorpusRepository`` bound to
        *session*.
        """
        if self._content_corpus_repo is None:
            from .db.repositories.content_corpora import ContentCorpusRepository

            self._content_corpus_repo = ContentCorpusRepository(self._session)
        return self._content_corpus_repo

    @property
    def content_source_repo(self) -> ContentSourceRepository:
        """Lazily-initialised ``ContentSourceRepository`` bound to
        *session*.
        """
        if self._content_source_repo is None:
            from .db.repositories.content_sources import ContentSourceRepository

            self._content_source_repo = ContentSourceRepository(self._session)
        return self._content_source_repo

    @property
    def content_version_repo(self) -> ContentVersionRepository:
        """Lazily-initialised ``ContentVersionRepository`` bound to
        *session*.
        """
        if self._content_version_repo is None:
            from .db.repositories.content_versions import ContentVersionRepository

            self._content_version_repo = ContentVersionRepository(self._session)
        return self._content_version_repo

    @property
    def content_ingest_session_repo(
        self,
    ) -> ContentIngestSessionRepository:
        """Lazily-initialised ``ContentIngestSessionRepository`` bound
        to *session*.
        """
        if self._content_ingest_session_repo is None:
            from .db.repositories.content_ingest_sessions import (
                ContentIngestSessionRepository,
            )

            self._content_ingest_session_repo = ContentIngestSessionRepository(
                self._session
            )
        return self._content_ingest_session_repo

    @property
    def content_blob_repo(self) -> ContentBlobRepository:
        """Lazily-initialised ``ContentBlobRepository`` bound to
        *session*.
        """
        if self._content_blob_repo is None:
            from .db.repositories.content_blobs import ContentBlobRepository

            self._content_blob_repo = ContentBlobRepository(self._session)
        return self._content_blob_repo

    @property
    def content_import_job_repo(self) -> ContentImportJobRepository:
        """Lazily-initialised ``ContentImportJobRepository`` bound to
        *session*.
        """
        if self._content_import_job_repo is None:
            from .db.repositories.content_import_jobs import ContentImportJobRepository

            self._content_import_job_repo = ContentImportJobRepository(self._session)
        return self._content_import_job_repo

    @property
    def content_lock_repo(self) -> ContentLockRepository:
        """Lazily-initialised ``ContentLockRepository`` bound to
        *session*.
        """
        if self._content_lock_repo is None:
            from .db.repositories.content_locks import ContentLockRepository

            self._content_lock_repo = ContentLockRepository(self._session)
        return self._content_lock_repo

    @property
    def content_store(self) -> VersionedContentStore:
        """Lazily-initialised ``LocalVersionedContentStore`` bound to
        *session*.

        Returns the local implementation; this is the injection seam
        for a future SaaS-backed ``VersionedContentStore``.
        """
        if self._content_store is None:
            from .services.content.local_versioned_content_store import (
                LocalVersionedContentStore,
            )

            self._content_store = LocalVersionedContentStore(
                db_session=self._session,
            )
        return self._content_store

    @property
    def content_corpora(self) -> ContentCorpusService:
        """Return the content ``CorpusService`` wired to *session*."""
        if self._content_corpora is None:
            from .services.content.corpus_service import CorpusService

            self._content_corpora = CorpusService(
                self.content_corpus_repo,
                self.content_source_repo,
                self.content_version_repo,
                self._session,
                self.content_store,
            )
        return self._content_corpora

    @property
    def content_ingestion(self) -> IngestionService:
        """Return the content ``IngestionService`` wired to *session*."""
        if self._content_ingestion is None:
            from .services.content.ingestion_service import IngestionService
            from .services.content.validation_service import ValidationService

            self._content_ingestion = IngestionService(
                self.content_ingest_session_repo,
                self.content_version_repo,
                self.content_blob_repo,
                self.content_corpus_repo,
                self.content_source_repo,
                self.content_store,
                ValidationService(),
            )
        return self._content_ingestion

    @property
    def content_composition(self) -> object:  # will be CompositionService
        """Lazily-initialised content composition service."""
        if self._content_composition is None:
            # Placeholder — implemented by a future US.
            self._content_composition = object()
        return self._content_composition

    @property
    def content_lineage(self) -> LineageService:
        """Return the ``LineageService`` backed by the content version
        repository.

        Tracks provenance links between MLflow training runs and content
        version snapshots.  Lazily-initialised on first access.
        """
        if self._content_lineage is None:
            from .services.content.lineage_service import LineageService

            self._content_lineage = LineageService(self.content_version_repo)
        return self._content_lineage

    @property
    def content_imports(self) -> object:  # will be ImportService
        """Lazily-initialised content import service."""
        if self._content_imports is None:
            # Placeholder — implemented by a future US.
            self._content_imports = object()
        return self._content_imports

    @property
    def content_locks(self) -> object:  # will be LockService
        """Lazily-initialised content lock service."""
        if self._content_locks is None:
            # Placeholder — implemented by a future US.
            self._content_locks = object()
        return self._content_locks

    # ── Session lifecycle ───────────────────────────────────────────────

    @property
    def session(self) -> AsyncSession:
        """Expose the bound session for callers that need it directly."""
        return self._session

    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[AnvilWorkbench, None]:
        """Context manager that commits on success, rolls back on error."""
        try:
            yield self
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise
