"""Session-bound AnvilWorkbench — the God Class (Constitution Article VII).

Wraps all DB-backed services in a session-bound ``AnvilWorkbench``.
Every request obtains a ``workbench`` instance via the ``get_workbench``
FastAPI dependency and accesses services as ``workbench.datasets``,
``workbench.corpora``, etc. Services are lazily instantiated on first
access so that unused services impose zero overhead.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from .db.repositories.corpora import CorpusRepository
    from .db.repositories.datasets import DatasetRepository
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
    """Session-bound God Class exposing all anvil DB-backed services.

    Every :class:`AnvilWorkbench` is bound to a single
    :class:`AsyncSession` — obtained from the ``get_workbench`` FastAPI
    dependency — and provides lazy accessors for each domain service.

    Parameters
    ----------
    session : AsyncSession
        An async SQLAlchemy session, scoped to the current request (or CLI
        command). Services created via the accessors share this session so
        audit writes, provenance updates, etc. participate in the same
        transaction (FR-011).
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        # Lazily-initialised service / repository references.
        self._training: TrainingService | None = None
        self._dataset_repo: DatasetRepository | None = None
        self._corpus_repo: CorpusRepository | None = None
        self._datasets: DatasetService | None = None
        self._corpora: CorpusService | None = None
        self._dataset_curation: DatasetCurationService | None = None
        self._dataset_export: DatasetExportService | None = None
        self._demo: DemoBootstrapService | None = None
        self._store: LocalFileStore | None = None
        # Governance services (registered by T024).
        self._audit: AuditService | None = None
        self._governance: GovernanceService | None = None

    # ── High-level stateless accessors ──────────────────────────────────

    @property
    def training(self) -> TrainingService:
        """Return the stateless ``TrainingService`` (no session needed)."""
        if self._training is None:
            from .services.training.training import TrainingService

            self._training = TrainingService()
        return self._training

    # ── Repository helpers (shared across multiple domain services) ─────

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

    # ── Domain-service accessors ────────────────────────────────────────

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
            from .services.datasets.corpus_loader import CorpusLoader
            from .services.datasets.corpora import CorpusService

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
