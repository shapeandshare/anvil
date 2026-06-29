# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Session-bound AnvilWorkbench — the God Class (Constitution Article VII).

Wraps all anvil services in a single entry point.  DB-backed services
are bound to an ``AsyncSession`` for request-scoped transactions;
stateless services (training, tracking, inference, export) are lazy
properties.  Obtain a workbench via the ``get_workbench`` FastAPI
dependency for request-scoped usage.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession

from .config import get_config
from .db.repositories.asset_download_job_repository import AssetDownloadJobRepository
from .db.repositories.audit_events import AuditEventRepository
from .db.repositories.backup_operations import BackupOperationRepository
from .db.repositories.content_blobs import ContentBlobRepository
from .db.repositories.content_corpora import ContentCorpusRepository
from .db.repositories.content_import_jobs import ContentImportJobRepository
from .db.repositories.content_ingest_sessions import ContentIngestSessionRepository
from .db.repositories.content_locks import ContentLockRepository
from .db.repositories.content_sources import ContentSourceRepository
from .db.repositories.content_versions import ContentVersionRepository
from .db.repositories.corpora import CorpusRepository
from .db.repositories.datasets import DatasetRepository
from .db.repositories.external_models import ExternalModelRepository
from .db.repositories.instance_registry import (
    InstanceRegistryRepository,
    create_registry_session,
)
from .db.repositories.licenses import LicenseRepository
from .db.repositories.model_asset_repository import ModelAssetRepository
from .db.repositories.model_import_jobs import ModelImportJobRepository
from .db.repositories.runtime_config import RuntimeConfigRepository
from .db.repositories.user_secret_repository import UserSecretRepository
from .services._shared.encryption import EncryptionService
from .services._shared.source_type import SourceType
from .services.content.composition_service import CompositionService
from .services.content.corpus_service import CorpusService as ContentCorpusService
from .services.content.import_service import ImportService
from .services.content.ingestion_service import IngestionService
from .services.content.lineage_service import LineageService
from .services.content.local_versioned_content_store import LocalVersionedContentStore
from .services.content.lock_service import LockService
from .services.content.validation_service import ValidationService
from .services.content.versioned_content_store import VersionedContentStore
from .services.datasets.corpora import CorpusService
from .services.datasets.corpus_loader import CorpusLoader
from .services.datasets.dataset_curation import DatasetCurationService
from .services.datasets.dataset_export import DatasetExportService
from .services.datasets.dataset_import import DatasetImportService
from .services.datasets.datasets import DatasetService
from .services.demo.demo_bootstrap import DemoBootstrapService
from .services.governance.audit_action import AuditAction
from .services.governance.audit_outcome import AuditOutcome
from .services.governance.audit_service import AuditService
from .services.governance.governance_service import GovernanceService
from .services.inference.inference import InferenceService
from .services.inference.model_browser import ModelBrowserService
from .services.instances.instance_lifecycle_service import InstanceLifecycleService
from .services.model_import.hf_source import HfHubSource
from .services.model_import.local_source import LocalSource
from .services.model_import.model_asset_service import ModelAssetService
from .services.model_import.model_import_service import ModelImportService
from .services.model_import.user_secret_service import UserSecretService
from .services.runtime_config.runtime_config_service import RuntimeConfigService
from .services.tracking.tracking import TrackingService
from .services.training.training import TrainingService
from .storage.local import LocalFileStore
from .workspace.workspace_paths import WorkspacePaths

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
    paths : WorkspacePaths, optional
        Derived paths from the workspace root.  Set by workspace-
        aware callers; defaults to ``None`` (legacy single-instance
        paths).
    registry_session : AsyncSession, optional
        Session bound to the global registry DB (``~/.anvil/registry.db``).
        Created lazily if omitted.
    """

    # Re-exported audit enums for route-layer consumption
    # without direct import from anvil.services.governance.
    AuditAction: type[AuditAction] = AuditAction
    AuditOutcome: type[AuditOutcome] = AuditOutcome

    def __init__(
        self,
        session: AsyncSession,
        paths: WorkspacePaths | None = None,
        registry_session: AsyncSession | None = None,
    ) -> None:
        self._session = session
        self._paths = paths
        self._registry_session = registry_session
        # DB-backed lazy references.
        self._training: TrainingService | None = None
        self._tracking: TrackingService | None = None
        self._inference: InferenceService | None = None
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
        self._content_composition: CompositionService | None = None
        self._content_lineage: LineageService | None = None
        self._content_imports: ImportService | None = None
        self._content_locks: LockService | None = None
        # Backup & Restore (feature 026).
        self._backup_repo: BackupOperationRepository | None = None
        # Instance lifecycle (feature 028).
        self._instances: InstanceLifecycleService | None = None
        self._instance_registry: InstanceRegistryRepository | None = None
        # Runtime config (feature 037).
        self._runtime_config_repo: RuntimeConfigRepository | None = None
        self._runtime_config: RuntimeConfigService | None = None
        # Model import (feature 040).
        self._external_model_repo: ExternalModelRepository | None = None
        self._model_import_job_repo: ModelImportJobRepository | None = None
        self._model_imports: ModelImportService | None = None
        # HuggingFace Model Browser (feature 041).
        self._model_browser: ModelBrowserService | None = None
        # Model asset storage (feature 042).
        self._model_asset_repo: ModelAssetRepository | None = None
        self._asset_download_job_repo: AssetDownloadJobRepository | None = None
        self._user_secret_repo: UserSecretRepository | None = None
        self._user_secrets: UserSecretService | None = None
        self._model_assets: ModelAssetService | None = None

    # ── Stateless service accessors ─────────────────────────────────────

    @property
    def training(self) -> TrainingService:
        """Return the stateless ``TrainingService``."""
        if self._training is None:
            self._training = TrainingService()
        return self._training

    @property
    def tracking(self) -> TrackingService:
        """Return the stateless ``TrackingService``."""
        if self._tracking is None:
            self._tracking = TrackingService()
        return self._tracking

    @property
    def inference(self) -> InferenceService:
        """Return the stateless ``InferenceService``."""
        if self._inference is None:
            self._inference = InferenceService()
        return self._inference

    # ── Repository helpers ──────────────────────────────────────────────

    @property
    def dataset_repo(self) -> DatasetRepository:
        """Lazily-initialised ``DatasetRepository`` bound to *session*."""
        if self._dataset_repo is None:
            self._dataset_repo = DatasetRepository(self._session)
        return self._dataset_repo

    @property
    def corpus_repo(self) -> CorpusRepository:
        """Lazily-initialised ``CorpusRepository`` bound to *session*."""
        if self._corpus_repo is None:
            self._corpus_repo = CorpusRepository(self._session)
        return self._corpus_repo

    @property
    def store(self) -> LocalFileStore:
        """Lazily-initialised ``LocalFileStore`` rooted at the datasets dir."""
        if self._store is None:
            datasets_path = (
                str(self._paths.datasets_dir)
                if self._paths is not None
                else "data/datasets"
            )
            self._store = LocalFileStore(datasets_path)
        return self._store

    # ── DB-backed domain service accessors ──────────────────────────────

    @property
    def datasets(self) -> DatasetService:
        """Return a ``DatasetService`` wired to *session*."""
        if self._datasets is None:
            self._datasets = DatasetService(self.dataset_repo, self.store)
        return self._datasets

    @property
    def corpora(self) -> CorpusService:
        """Return a ``CorpusService`` wired to *session*."""
        if self._corpora is None:
            self._corpora = CorpusService(self.corpus_repo, CorpusLoader())
        return self._corpora

    def dataset_import(self, dataset_id: int) -> DatasetImportService:
        """Return a fresh ``DatasetImportService`` for a specific dataset.

        This is a factory — not a property — because each import is scoped
        to one dataset and carries mutable state.
        """
        return DatasetImportService(self._session, dataset_id, self.store)

    def dataset_curation(self, dataset_id: int) -> DatasetCurationService:
        """Return a fresh ``DatasetCurationService`` for a specific dataset."""
        return DatasetCurationService(self._session, dataset_id, self.store)

    def dataset_export(self, dataset_id: int) -> DatasetExportService:
        """Return a fresh ``DatasetExportService`` for a specific dataset."""
        return DatasetExportService(self._session, dataset_id, self.store)

    @property
    def demo(self) -> DemoBootstrapService:
        """Return a ``DemoBootstrapService`` wired to *session*."""
        if self._demo is None:
            self._demo = DemoBootstrapService(self._session)
        return self._demo

    # ── Governance accessors ────────────────────────────────────────────

    @property
    def audit(self) -> AuditService:
        """Return the hash-chained ``AuditService`` wired to *session*."""
        if self._audit is None:
            self._audit = AuditService(AuditEventRepository(self._session))
        return self._audit

    @property
    def governance(self) -> GovernanceService:
        """Return the ``GovernanceService`` wired to *session*."""
        if self._governance is None:
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
            self._content_corpus_repo = ContentCorpusRepository(self._session)
        return self._content_corpus_repo

    @property
    def content_source_repo(self) -> ContentSourceRepository:
        """Lazily-initialised ``ContentSourceRepository`` bound to
        *session*.
        """
        if self._content_source_repo is None:
            self._content_source_repo = ContentSourceRepository(self._session)
        return self._content_source_repo

    @property
    def content_version_repo(self) -> ContentVersionRepository:
        """Lazily-initialised ``ContentVersionRepository`` bound to
        *session*.
        """
        if self._content_version_repo is None:
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
            self._content_blob_repo = ContentBlobRepository(self._session)
        return self._content_blob_repo

    @property
    def content_import_job_repo(self) -> ContentImportJobRepository:
        """Lazily-initialised ``ContentImportJobRepository`` bound to
        *session*.
        """
        if self._content_import_job_repo is None:
            self._content_import_job_repo = ContentImportJobRepository(self._session)
        return self._content_import_job_repo

    @property
    def content_lock_repo(self) -> ContentLockRepository:
        """Lazily-initialised ``ContentLockRepository`` bound to
        *session*.
        """
        if self._content_lock_repo is None:
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
            self._content_store = LocalVersionedContentStore(
                content_dir=get_config()["content_dir"],
                db_session=self._session,
            )
        return self._content_store

    @property
    def content_corpora(self) -> ContentCorpusService:
        """Return the content ``CorpusService`` wired to *session*."""
        if self._content_corpora is None:
            self._content_corpora = ContentCorpusService(
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
    def content_composition(self) -> CompositionService:
        """Return the ``CompositionService`` wired to *session*.

        Lazily initialised on first access.  Provides ``preview``
        and ``freeze`` operations for weighted composition versions.
        """
        if self._content_composition is None:
            self._content_composition = CompositionService(
                store=self.content_store,
                version_repo=self.content_version_repo,
                corpus_repo=self.content_corpus_repo,
                db_session=self._session,
            )
        return self._content_composition

    @property
    def content_lineage(self) -> LineageService:
        """Return the ``LineageService`` backed by the content version
        repository.

        Tracks provenance links between MLflow training runs and content
        version snapshots.  Lazily-initialised on first access.
        """
        if self._content_lineage is None:
            self._content_lineage = LineageService(self.content_version_repo)
        return self._content_lineage

    @property
    def content_imports(self) -> ImportService:
        """Lazily-initialised ``ImportService`` wired to *session*."""
        if self._content_imports is None:
            self._content_imports = ImportService(
                import_job_repo=self.content_import_job_repo,
                session_repo=self.content_ingest_session_repo,
                source_repo=self.content_source_repo,
                corpus_repo=self.content_corpus_repo,
                content_store=self.content_store,
                ingestion_service=self.content_ingestion,
            )
        return self._content_imports

    @property
    def content_locks(self) -> LockService:
        """Lazily-initialised ``LockService`` wired to *session*.

        Manages advisory checkout lock lifecycle (acquire, release,
        list active) backed by the ``ContentLockRepository``.
        """
        if self._content_locks is None:
            self._content_locks = LockService(self.content_lock_repo)
        return self._content_locks

    # ── Backup & Restore accessors (feature 026) ─────────────────────────

    @property
    def backup_repo(self) -> BackupOperationRepository:
        """Lazily-initialised ``BackupOperationRepository`` bound to
        *session*.
        """
        if self._backup_repo is None:
            self._backup_repo = BackupOperationRepository(self._session)
        return self._backup_repo

    # ── Instance lifecycle accessors (feature 028) ──────────────────────

    @property
    def instances(self) -> InstanceLifecycleService:
        """Lazily-initialised ``InstanceLifecycleService`` wired to
        *session*.
        """
        if self._instances is None:
            self._instances = InstanceLifecycleService(
                self._session,
                registry_session=self._registry_session,
                audit=self._audit,
            )
        return self._instances

    @property
    def instance_registry(self) -> InstanceRegistryRepository:
        """Lazily-initialised ``InstanceRegistryRepository`` bound to
        the global registry session.
        """
        if self._instance_registry is None:
            # Create registry session lazily if the caller did not
            # provide one.
            if self._registry_session is None:
                self._registry_session = asyncio.run(create_registry_session())
            self._instance_registry = InstanceRegistryRepository(self._registry_session)
        return self._instance_registry

    # ── Runtime config accessors (feature 037) ──────────────────────────

    @property
    def runtime_config_repo(self) -> RuntimeConfigRepository:
        """Lazily-initialised ``RuntimeConfigRepository`` bound to
        *session*.
        """
        if self._runtime_config_repo is None:
            self._runtime_config_repo = RuntimeConfigRepository(self._session)
        return self._runtime_config_repo

    @property
    def runtime_config(self) -> RuntimeConfigService:
        """Lazily-initialised ``RuntimeConfigService`` wired to *session*."""
        if self._runtime_config is None:
            self._runtime_config = RuntimeConfigService(self.runtime_config_repo)
        return self._runtime_config

    # ── Model import accessors (feature 040) ───────────────────────────

    @property
    def external_model_repo(self) -> ExternalModelRepository:
        """Lazily-initialised ``ExternalModelRepository`` bound to *session*."""
        if self._external_model_repo is None:
            self._external_model_repo = ExternalModelRepository(self._session)
        return self._external_model_repo

    @property
    def model_import_job_repo(self) -> ModelImportJobRepository:
        """Lazily-initialised ``ModelImportJobRepository`` bound to *session*."""
        if self._model_import_job_repo is None:
            self._model_import_job_repo = ModelImportJobRepository(self._session)
        return self._model_import_job_repo

    @property
    def model_imports(self) -> ModelImportService:
        """Lazily-initialised ``ModelImportService`` wired to *session*."""
        if self._model_imports is None:
            self._model_imports = ModelImportService(
                self.external_model_repo,
                self.model_import_job_repo,
                {
                    SourceType.HUGGINGFACE: HfHubSource(),
                    SourceType.LOCAL: LocalSource(),
                },
            )
        return self._model_imports

    @property
    def model_browser(self) -> ModelBrowserService:
        """Lazily-initialised ``ModelBrowserService`` for HuggingFace model browsing."""
        if self._model_browser is None:
            self._model_browser = ModelBrowserService()
        return self._model_browser

    # ── Model asset storage (feature 042) ────────────────────────────────

    @property
    def model_asset_repo(self) -> ModelAssetRepository:
        """Lazily-initialised ``ModelAssetRepository`` bound to *session*."""
        if self._model_asset_repo is None:
            self._model_asset_repo = ModelAssetRepository(self._session)
        return self._model_asset_repo

    @property
    def asset_download_job_repo(self) -> AssetDownloadJobRepository:
        """Lazily-initialised ``AssetDownloadJobRepository`` bound to *session*."""
        if self._asset_download_job_repo is None:
            self._asset_download_job_repo = AssetDownloadJobRepository(self._session)
        return self._asset_download_job_repo

    @property
    def user_secret_repo(self) -> UserSecretRepository:
        """Lazily-initialised ``UserSecretRepository`` bound to *session*."""
        if self._user_secret_repo is None:
            self._user_secret_repo = UserSecretRepository(self._session)
        return self._user_secret_repo

    @property
    def user_secrets(self) -> UserSecretService:
        """Lazily-initialised ``UserSecretService`` wired to *session*."""
        if self._user_secrets is None:
            self._user_secrets = UserSecretService(
                self.user_secret_repo,
                EncryptionService(),
            )
        return self._user_secrets

    @property
    def model_assets(self) -> ModelAssetService:
        """Lazily-initialised ``ModelAssetService`` wired to *session*."""
        if self._model_assets is None:
            self._model_assets = ModelAssetService(
                self.model_asset_repo,
                self.asset_download_job_repo,
                self.external_model_repo,
                self.store,
            )
        return self._model_assets

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
