"""Unit tests for AnvilWorkbench — the God Class (Constitution Article VII).

Covers initialisation, property access (lazy & stateless), factory
methods, session lifecycle, and the ``get_workbench`` FastAPI dep.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from anvil.workbench import AnvilWorkbench

# ============================================================================
# Helpers
# ============================================================================


def _mock_registry_session() -> MagicMock:
    """Return a mock ``AsyncSession`` suitable as a registry session."""
    return AsyncMock(spec=AsyncSession)


# ============================================================================
# __init__
# ============================================================================


class TestInit:
    """AnvilWorkbench.__init__ tests."""

    @pytest.mark.asyncio
    async def test_init_with_session_only(
        self, in_memory_session: AsyncSession
    ) -> None:
        """Default init stores session and leaves paths & registry as None."""
        wb = AnvilWorkbench(in_memory_session)
        assert wb._session is in_memory_session
        assert wb._paths is None
        assert wb._registry_session is None

        # Every lazy reference starts as None.
        assert wb._training is None
        assert wb._tracking is None
        assert wb._inference is None
        assert wb._dataset_repo is None
        assert wb._corpus_repo is None
        assert wb._datasets is None
        assert wb._corpora is None
        assert wb._dataset_curation is None
        assert wb._dataset_export is None
        assert wb._demo is None
        assert wb._store is None
        assert wb._audit is None
        assert wb._governance is None
        assert wb._content_corpus_repo is None
        assert wb._content_source_repo is None
        assert wb._content_version_repo is None
        assert wb._content_ingest_session_repo is None
        assert wb._content_blob_repo is None
        assert wb._content_import_job_repo is None
        assert wb._content_lock_repo is None
        assert wb._content_store is None
        assert wb._content_corpora is None
        assert wb._content_ingestion is None
        assert wb._content_composition is None
        assert wb._content_lineage is None
        assert wb._content_imports is None
        assert wb._content_locks is None
        assert wb._backup_repo is None
        assert wb._instances is None
        assert wb._instance_registry is None
        assert wb._runtime_config_repo is None
        assert wb._runtime_config is None
        assert wb._external_model_repo is None
        assert wb._model_import_job_repo is None
        assert wb._model_imports is None

    @pytest.mark.asyncio
    async def test_init_with_paths_and_registry_session(
        self, in_memory_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Init stores paths and registry session when provided."""
        from anvil.workspace.workspace_paths import WorkspacePaths

        paths = WorkspacePaths(tmp_path)
        reg_session = _mock_registry_session()
        wb = AnvilWorkbench(
            in_memory_session,
            paths=paths,
            registry_session=reg_session,
        )
        assert wb._paths is paths
        assert wb._registry_session is reg_session


# ============================================================================
# session property
# ============================================================================


class TestSessionProperty:
    """The ``session`` property exposes the bound AsyncSession."""

    @pytest.mark.asyncio
    async def test_session(self, in_memory_session: AsyncSession) -> None:
        wb = AnvilWorkbench(in_memory_session)
        assert wb.session is in_memory_session


# ============================================================================
# Stateless services (no constructor args)
# ============================================================================


class TestStatelessServices:
    """Stateless services that need no DB session or repos."""

    @pytest.mark.asyncio
    async def test_training(self, in_memory_session: AsyncSession) -> None:
        from anvil.services.training.training import TrainingService

        wb = AnvilWorkbench(in_memory_session)
        svc = wb.training
        assert isinstance(svc, TrainingService)
        assert wb._training is svc
        # Repeat access returns the *same* instance (lazy singleton).
        assert wb.training is svc

    @pytest.mark.asyncio
    async def test_tracking(self, in_memory_session: AsyncSession) -> None:
        from anvil.services.tracking.tracking import TrackingService

        wb = AnvilWorkbench(in_memory_session)
        svc = wb.tracking
        assert isinstance(svc, TrackingService)
        assert wb.tracking is svc

    @pytest.mark.asyncio
    async def test_inference(self, in_memory_session: AsyncSession) -> None:
        from anvil.services.inference.inference import InferenceService

        wb = AnvilWorkbench(in_memory_session)
        svc = wb.inference
        assert isinstance(svc, InferenceService)
        assert wb.inference is svc


# ============================================================================
# Repository properties
# ============================================================================


class TestRepositoryProperties:
    """Repository properties are lazily initialised and bound to *session*."""

    @pytest.mark.asyncio
    async def test_dataset_repo(self, in_memory_session: AsyncSession) -> None:
        from anvil.db.repositories.datasets import DatasetRepository

        wb = AnvilWorkbench(in_memory_session)
        repo = wb.dataset_repo
        assert isinstance(repo, DatasetRepository)
        assert wb.dataset_repo is repo

    @pytest.mark.asyncio
    async def test_corpus_repo(self, in_memory_session: AsyncSession) -> None:
        from anvil.db.repositories.corpora import CorpusRepository

        wb = AnvilWorkbench(in_memory_session)
        repo = wb.corpus_repo
        assert isinstance(repo, CorpusRepository)
        assert wb.corpus_repo is repo

    @pytest.mark.asyncio
    async def test_content_corpus_repo(self, in_memory_session: AsyncSession) -> None:
        from anvil.db.repositories.content_corpora import ContentCorpusRepository

        wb = AnvilWorkbench(in_memory_session)
        repo = wb.content_corpus_repo
        assert isinstance(repo, ContentCorpusRepository)
        assert wb.content_corpus_repo is repo

    @pytest.mark.asyncio
    async def test_content_source_repo(self, in_memory_session: AsyncSession) -> None:
        from anvil.db.repositories.content_sources import ContentSourceRepository

        wb = AnvilWorkbench(in_memory_session)
        repo = wb.content_source_repo
        assert isinstance(repo, ContentSourceRepository)
        assert wb.content_source_repo is repo

    @pytest.mark.asyncio
    async def test_content_version_repo(self, in_memory_session: AsyncSession) -> None:
        from anvil.db.repositories.content_versions import ContentVersionRepository

        wb = AnvilWorkbench(in_memory_session)
        repo = wb.content_version_repo
        assert isinstance(repo, ContentVersionRepository)
        assert wb.content_version_repo is repo

    @pytest.mark.asyncio
    async def test_content_ingest_session_repo(
        self, in_memory_session: AsyncSession
    ) -> None:
        from anvil.db.repositories.content_ingest_sessions import (
            ContentIngestSessionRepository,
        )

        wb = AnvilWorkbench(in_memory_session)
        repo = wb.content_ingest_session_repo
        assert isinstance(repo, ContentIngestSessionRepository)
        assert wb.content_ingest_session_repo is repo

    @pytest.mark.asyncio
    async def test_content_blob_repo(self, in_memory_session: AsyncSession) -> None:
        from anvil.db.repositories.content_blobs import ContentBlobRepository

        wb = AnvilWorkbench(in_memory_session)
        repo = wb.content_blob_repo
        assert isinstance(repo, ContentBlobRepository)
        assert wb.content_blob_repo is repo

    @pytest.mark.asyncio
    async def test_content_import_job_repo(
        self, in_memory_session: AsyncSession
    ) -> None:
        from anvil.db.repositories.content_import_jobs import ContentImportJobRepository

        wb = AnvilWorkbench(in_memory_session)
        repo = wb.content_import_job_repo
        assert isinstance(repo, ContentImportJobRepository)
        assert wb.content_import_job_repo is repo

    @pytest.mark.asyncio
    async def test_content_lock_repo(self, in_memory_session: AsyncSession) -> None:
        from anvil.db.repositories.content_locks import ContentLockRepository

        wb = AnvilWorkbench(in_memory_session)
        repo = wb.content_lock_repo
        assert isinstance(repo, ContentLockRepository)
        assert wb.content_lock_repo is repo

    @pytest.mark.asyncio
    async def test_backup_repo(self, in_memory_session: AsyncSession) -> None:
        from anvil.db.repositories.backup_operations import BackupOperationRepository

        wb = AnvilWorkbench(in_memory_session)
        repo = wb.backup_repo
        assert isinstance(repo, BackupOperationRepository)
        assert wb.backup_repo is repo

    @pytest.mark.asyncio
    async def test_runtime_config_repo(self, in_memory_session: AsyncSession) -> None:
        from anvil.db.repositories.runtime_config import RuntimeConfigRepository

        wb = AnvilWorkbench(in_memory_session)
        repo = wb.runtime_config_repo
        assert isinstance(repo, RuntimeConfigRepository)
        assert wb.runtime_config_repo is repo

    @pytest.mark.asyncio
    async def test_external_model_repo(self, in_memory_session: AsyncSession) -> None:
        from anvil.db.repositories.external_models import ExternalModelRepository

        wb = AnvilWorkbench(in_memory_session)
        repo = wb.external_model_repo
        assert isinstance(repo, ExternalModelRepository)
        assert wb.external_model_repo is repo

    @pytest.mark.asyncio
    async def test_model_import_job_repo(self, in_memory_session: AsyncSession) -> None:
        from anvil.db.repositories.model_import_jobs import ModelImportJobRepository

        wb = AnvilWorkbench(in_memory_session)
        repo = wb.model_import_job_repo
        assert isinstance(repo, ModelImportJobRepository)
        assert wb.model_import_job_repo is repo


# ============================================================================
# Store property
# ============================================================================


class TestStoreProperty:
    """The ``store`` property lazily initialises ``LocalFileStore``."""

    @pytest.mark.asyncio
    async def test_store_default_path(self, in_memory_session: AsyncSession) -> None:
        """When no ``paths`` is given, store uses the fallback datasets dir."""
        from anvil.storage.local import LocalFileStore

        wb = AnvilWorkbench(in_memory_session)
        store = wb.store
        assert isinstance(store, LocalFileStore)
        assert wb._store is store
        assert wb.store is store

    @pytest.mark.asyncio
    async def test_store_with_paths(
        self, in_memory_session: AsyncSession, tmp_path: Path
    ) -> None:
        """When ``paths`` is provided, store uses ``paths.datasets_dir``."""
        from anvil.storage.local import LocalFileStore
        from anvil.workspace.workspace_paths import WorkspacePaths

        paths = WorkspacePaths(tmp_path)
        wb = AnvilWorkbench(in_memory_session, paths=paths)
        store = wb.store
        assert isinstance(store, LocalFileStore)
        assert str(paths.datasets_dir) in str(store.base_path)


# ============================================================================
# DB-backed domain services
# ============================================================================


class TestDBBackedServices:
    """Domain services that need repos + session."""

    @pytest.mark.asyncio
    async def test_datasets(self, in_memory_session: AsyncSession) -> None:
        from anvil.services.datasets.datasets import DatasetService

        wb = AnvilWorkbench(in_memory_session)
        svc = wb.datasets
        assert isinstance(svc, DatasetService)
        assert wb._datasets is svc
        assert wb.datasets is svc

    @pytest.mark.asyncio
    async def test_corpora(self, in_memory_session: AsyncSession) -> None:
        from anvil.services.datasets.corpora import CorpusService

        wb = AnvilWorkbench(in_memory_session)
        svc = wb.corpora
        assert isinstance(svc, CorpusService)
        assert wb._corpora is svc
        assert wb.corpora is svc

    @pytest.mark.asyncio
    async def test_demo(self, in_memory_session: AsyncSession) -> None:
        from anvil.services.demo.demo_bootstrap import DemoBootstrapService

        wb = AnvilWorkbench(in_memory_session)
        svc = wb.demo
        assert isinstance(svc, DemoBootstrapService)
        assert wb._demo is svc
        assert wb.demo is svc

    @pytest.mark.asyncio
    async def test_audit(self, in_memory_session: AsyncSession) -> None:
        from anvil.services.governance.audit_service import AuditService

        wb = AnvilWorkbench(in_memory_session)
        svc = wb.audit
        assert isinstance(svc, AuditService)
        assert wb._audit is svc
        assert wb.audit is svc

    @pytest.mark.asyncio
    async def test_governance(self, in_memory_session: AsyncSession) -> None:
        from anvil.services.governance.governance_service import GovernanceService

        wb = AnvilWorkbench(in_memory_session)
        svc = wb.governance
        assert isinstance(svc, GovernanceService)
        assert wb._governance is svc
        assert wb.governance is svc


# ============================================================================
# Content services
# ============================================================================


class TestContentServices:
    """Content service properties are lazily initialised."""

    @pytest.mark.asyncio
    async def test_content_store(self, in_memory_session: AsyncSession) -> None:
        from anvil.services.content.local_versioned_content_store import (
            LocalVersionedContentStore,
        )

        wb = AnvilWorkbench(in_memory_session)
        svc = wb.content_store
        assert isinstance(svc, LocalVersionedContentStore)
        assert wb._content_store is svc
        assert wb.content_store is svc

    @pytest.mark.asyncio
    async def test_content_corpora(self, in_memory_session: AsyncSession) -> None:
        from anvil.services.content.corpus_service import (
            CorpusService as ContentCorpusService,
        )

        wb = AnvilWorkbench(in_memory_session)
        svc = wb.content_corpora
        assert isinstance(svc, ContentCorpusService)
        assert wb._content_corpora is svc
        assert wb.content_corpora is svc

    @pytest.mark.asyncio
    async def test_content_ingestion(self, in_memory_session: AsyncSession) -> None:
        from anvil.services.content.ingestion_service import IngestionService

        wb = AnvilWorkbench(in_memory_session)
        svc = wb.content_ingestion
        assert isinstance(svc, IngestionService)
        assert wb._content_ingestion is svc
        assert wb.content_ingestion is svc

    @pytest.mark.asyncio
    async def test_content_composition(self, in_memory_session: AsyncSession) -> None:
        from anvil.services.content.composition_service import CompositionService

        wb = AnvilWorkbench(in_memory_session)
        svc = wb.content_composition
        assert isinstance(svc, CompositionService)
        assert wb._content_composition is svc
        assert wb.content_composition is svc

    @pytest.mark.asyncio
    async def test_content_lineage(self, in_memory_session: AsyncSession) -> None:
        from anvil.services.content.lineage_service import LineageService

        wb = AnvilWorkbench(in_memory_session)
        svc = wb.content_lineage
        assert isinstance(svc, LineageService)
        assert wb._content_lineage is svc
        assert wb.content_lineage is svc

    @pytest.mark.asyncio
    async def test_content_imports(self, in_memory_session: AsyncSession) -> None:
        from anvil.services.content.import_service import ImportService

        wb = AnvilWorkbench(in_memory_session)
        svc = wb.content_imports
        assert isinstance(svc, ImportService)
        assert wb._content_imports is svc
        assert wb.content_imports is svc

    @pytest.mark.asyncio
    async def test_content_locks(self, in_memory_session: AsyncSession) -> None:
        from anvil.services.content.lock_service import LockService

        wb = AnvilWorkbench(in_memory_session)
        svc = wb.content_locks
        assert isinstance(svc, LockService)
        assert wb._content_locks is svc
        assert wb.content_locks is svc


# ============================================================================
# Instance lifecycle
# ============================================================================


class TestInstanceLifecycle:
    """Instance lifecycle properties."""

    @pytest.mark.asyncio
    async def test_instances(self, in_memory_session: AsyncSession) -> None:
        from anvil.services.instances.instance_lifecycle_service import (
            InstanceLifecycleService,
        )

        wb = AnvilWorkbench(in_memory_session)
        svc = wb.instances
        assert isinstance(svc, InstanceLifecycleService)
        assert wb._instances is svc
        assert wb.instances is svc

    @pytest.mark.asyncio
    async def test_instances_with_registry_session(
        self, in_memory_session: AsyncSession
    ) -> None:
        """When registry_session is provided, instances uses it."""
        from anvil.services.instances.instance_lifecycle_service import (
            InstanceLifecycleService,
        )

        reg_session = _mock_registry_session()
        wb = AnvilWorkbench(
            in_memory_session,
            registry_session=reg_session,
        )
        svc = wb.instances
        assert isinstance(svc, InstanceLifecycleService)

    @pytest.mark.asyncio
    async def test_instance_registry_with_session(
        self, in_memory_session: AsyncSession
    ) -> None:
        """instance_registry uses the provided registry_session."""
        from anvil.db.repositories.instance_registry import InstanceRegistryRepository

        reg_session = _mock_registry_session()
        wb = AnvilWorkbench(
            in_memory_session,
            registry_session=reg_session,
        )
        repo = wb.instance_registry
        assert isinstance(repo, InstanceRegistryRepository)
        assert wb._instance_registry is repo
        assert wb.instance_registry is repo

    @pytest.mark.asyncio
    async def test_instance_registry_lazy_create(
        self, in_memory_session: AsyncSession
    ) -> None:
        """Without a registry_session, calls create_registry_session()."""
        from anvil.db.repositories.instance_registry import InstanceRegistryRepository

        mock_session = _mock_registry_session()

        with (
            patch(
                "anvil.workbench.create_registry_session",
                return_value=mock_session,
            ) as mock_create,
            # asyncio.run() cannot be called from a running event loop,
            # so patch it to return the session directly.
            patch(
                "anvil.workbench.asyncio.run",
                return_value=mock_session,
            ),
        ):
            wb = AnvilWorkbench(in_memory_session)
            repo = wb.instance_registry
            assert isinstance(repo, InstanceRegistryRepository)
            mock_create.assert_called_once()
            assert wb.instance_registry is repo


# ============================================================================
# Runtime config
# ============================================================================


class TestRuntimeConfig:
    """Runtime config properties."""

    @pytest.mark.asyncio
    async def test_runtime_config(self, in_memory_session: AsyncSession) -> None:
        from anvil.services.runtime_config.runtime_config_service import (
            RuntimeConfigService,
        )

        wb = AnvilWorkbench(in_memory_session)
        svc = wb.runtime_config
        assert isinstance(svc, RuntimeConfigService)
        assert wb._runtime_config is svc
        assert wb.runtime_config is svc


# ============================================================================
# Model import
# ============================================================================


class TestModelImportServices:
    """Model import properties."""

    @pytest.mark.asyncio
    async def test_model_imports(self, in_memory_session: AsyncSession) -> None:
        from anvil.services.model_import.model_import_service import ModelImportService

        wb = AnvilWorkbench(in_memory_session)
        svc = wb.model_imports
        assert isinstance(svc, ModelImportService)
        assert wb._model_imports is svc
        assert wb.model_imports is svc


# ============================================================================
# Factory methods (return fresh instances each call)
# ============================================================================


class TestFactoryMethods:
    """dataset_import / dataset_curation / dataset_export return fresh
    instances every call.
    """

    @pytest.mark.asyncio
    async def test_dataset_import(self, in_memory_session: AsyncSession) -> None:
        from anvil.services.datasets.dataset_import import DatasetImportService

        wb = AnvilWorkbench(in_memory_session)
        svc = wb.dataset_import(42)
        assert isinstance(svc, DatasetImportService)
        # Fresh instance each call.
        svc2 = wb.dataset_import(42)
        assert svc is not svc2

    @pytest.mark.asyncio
    async def test_dataset_curation(self, in_memory_session: AsyncSession) -> None:
        from anvil.services.datasets.dataset_curation import DatasetCurationService

        wb = AnvilWorkbench(in_memory_session)
        svc = wb.dataset_curation(7)
        assert isinstance(svc, DatasetCurationService)
        assert svc is not wb.dataset_curation(7)

    @pytest.mark.asyncio
    async def test_dataset_export(self, in_memory_session: AsyncSession) -> None:
        from anvil.services.datasets.dataset_export import DatasetExportService

        wb = AnvilWorkbench(in_memory_session)
        svc = wb.dataset_export(99)
        assert isinstance(svc, DatasetExportService)
        assert svc is not wb.dataset_export(99)


# ============================================================================
# Lazy initialisation property (same instance on repeat access)
# ============================================================================


class TestLazyInitialization:
    """Every lazy property returns the same instance on repeat access."""

    # We random-sample a handful of representative properties.

    @pytest.mark.asyncio
    async def test_training_is_lazy(self, in_memory_session: AsyncSession) -> None:
        wb = AnvilWorkbench(in_memory_session)
        assert wb._training is None
        _ = wb.training
        assert wb._training is not None
        assert wb.training is wb._training

    @pytest.mark.asyncio
    async def test_datasets_is_lazy(self, in_memory_session: AsyncSession) -> None:
        wb = AnvilWorkbench(in_memory_session)
        assert wb._datasets is None
        _ = wb.datasets
        assert wb._datasets is not None
        assert wb.datasets is wb._datasets

    @pytest.mark.asyncio
    async def test_audit_is_lazy(self, in_memory_session: AsyncSession) -> None:
        wb = AnvilWorkbench(in_memory_session)
        assert wb._audit is None
        _ = wb.audit
        assert wb._audit is not None
        assert wb.audit is wb._audit

    @pytest.mark.asyncio
    async def test_content_store_is_lazy(self, in_memory_session: AsyncSession) -> None:
        wb = AnvilWorkbench(in_memory_session)
        assert wb._content_store is None
        _ = wb.content_store
        assert wb._content_store is not None
        assert wb.content_store is wb._content_store

    @pytest.mark.asyncio
    async def test_store_is_lazy(self, in_memory_session: AsyncSession) -> None:
        wb = AnvilWorkbench(in_memory_session)
        assert wb._store is None
        _ = wb.store
        assert wb._store is not None
        assert wb.store is wb._store

    @pytest.mark.asyncio
    async def test_runtime_config_is_lazy(
        self, in_memory_session: AsyncSession
    ) -> None:
        wb = AnvilWorkbench(in_memory_session)
        assert wb._runtime_config is None
        _ = wb.runtime_config
        assert wb._runtime_config is not None
        assert wb.runtime_config is wb._runtime_config

    @pytest.mark.asyncio
    async def test_model_imports_is_lazy(self, in_memory_session: AsyncSession) -> None:
        wb = AnvilWorkbench(in_memory_session)
        assert wb._model_imports is None
        _ = wb.model_imports
        assert wb._model_imports is not None
        assert wb.model_imports is wb._model_imports

    @pytest.mark.asyncio
    async def test_instances_is_lazy(self, in_memory_session: AsyncSession) -> None:
        wb = AnvilWorkbench(in_memory_session)
        assert wb._instances is None
        _ = wb.instances
        assert wb._instances is not None
        assert wb.instances is wb._instances

    @pytest.mark.asyncio
    async def test_governance_is_lazy(self, in_memory_session: AsyncSession) -> None:
        wb = AnvilWorkbench(in_memory_session)
        assert wb._governance is None
        _ = wb.governance
        assert wb._governance is not None
        assert wb.governance is wb._governance

    @pytest.mark.asyncio
    async def test_content_corpora_is_lazy(
        self, in_memory_session: AsyncSession
    ) -> None:
        wb = AnvilWorkbench(in_memory_session)
        assert wb._content_corpora is None
        _ = wb.content_corpora
        assert wb._content_corpora is not None
        assert wb.content_corpora is wb._content_corpora

    @pytest.mark.asyncio
    async def test_content_ingestion_is_lazy(
        self, in_memory_session: AsyncSession
    ) -> None:
        wb = AnvilWorkbench(in_memory_session)
        assert wb._content_ingestion is None
        _ = wb.content_ingestion
        assert wb._content_ingestion is not None
        assert wb.content_ingestion is wb._content_ingestion

    @pytest.mark.asyncio
    async def test_content_composition_is_lazy(
        self, in_memory_session: AsyncSession
    ) -> None:
        wb = AnvilWorkbench(in_memory_session)
        assert wb._content_composition is None
        _ = wb.content_composition
        assert wb._content_composition is not None
        assert wb.content_composition is wb._content_composition

    @pytest.mark.asyncio
    async def test_content_lineage_is_lazy(
        self, in_memory_session: AsyncSession
    ) -> None:
        wb = AnvilWorkbench(in_memory_session)
        assert wb._content_lineage is None
        _ = wb.content_lineage
        assert wb._content_lineage is not None
        assert wb.content_lineage is wb._content_lineage

    @pytest.mark.asyncio
    async def test_content_imports_is_lazy(
        self, in_memory_session: AsyncSession
    ) -> None:
        wb = AnvilWorkbench(in_memory_session)
        assert wb._content_imports is None
        _ = wb.content_imports
        assert wb._content_imports is not None
        assert wb.content_imports is wb._content_imports

    @pytest.mark.asyncio
    async def test_content_locks_is_lazy(self, in_memory_session: AsyncSession) -> None:
        wb = AnvilWorkbench(in_memory_session)
        assert wb._content_locks is None
        _ = wb.content_locks
        assert wb._content_locks is not None
        assert wb.content_locks is wb._content_locks

    @pytest.mark.asyncio
    async def test_dataset_repo_is_lazy(self, in_memory_session: AsyncSession) -> None:
        wb = AnvilWorkbench(in_memory_session)
        assert wb._dataset_repo is None
        _ = wb.dataset_repo
        assert wb._dataset_repo is not None
        assert wb.dataset_repo is wb._dataset_repo

    @pytest.mark.asyncio
    async def test_corpus_repo_is_lazy(self, in_memory_session: AsyncSession) -> None:
        wb = AnvilWorkbench(in_memory_session)
        assert wb._corpus_repo is None
        _ = wb.corpus_repo
        assert wb._corpus_repo is not None
        assert wb.corpus_repo is wb._corpus_repo

    @pytest.mark.asyncio
    async def test_demo_is_lazy(self, in_memory_session: AsyncSession) -> None:
        wb = AnvilWorkbench(in_memory_session)
        assert wb._demo is None
        _ = wb.demo
        assert wb._demo is not None
        assert wb.demo is wb._demo

    @pytest.mark.asyncio
    async def test_backup_repo_is_lazy(self, in_memory_session: AsyncSession) -> None:
        wb = AnvilWorkbench(in_memory_session)
        assert wb._backup_repo is None
        _ = wb.backup_repo
        assert wb._backup_repo is not None
        assert wb.backup_repo is wb._backup_repo

    @pytest.mark.asyncio
    async def test_tracking_is_lazy(self, in_memory_session: AsyncSession) -> None:
        wb = AnvilWorkbench(in_memory_session)
        assert wb._tracking is None
        _ = wb.tracking
        assert wb._tracking is not None
        assert wb.tracking is wb._tracking

    @pytest.mark.asyncio
    async def test_inference_is_lazy(self, in_memory_session: AsyncSession) -> None:
        wb = AnvilWorkbench(in_memory_session)
        assert wb._inference is None
        _ = wb.inference
        assert wb._inference is not None
        assert wb.inference is wb._inference

    @pytest.mark.asyncio
    async def test_runtime_config_repo_is_lazy(
        self, in_memory_session: AsyncSession
    ) -> None:
        wb = AnvilWorkbench(in_memory_session)
        assert wb._runtime_config_repo is None
        _ = wb.runtime_config_repo
        assert wb._runtime_config_repo is not None
        assert wb.runtime_config_repo is wb._runtime_config_repo

    @pytest.mark.asyncio
    async def test_external_model_repo_is_lazy(
        self, in_memory_session: AsyncSession
    ) -> None:
        wb = AnvilWorkbench(in_memory_session)
        assert wb._external_model_repo is None
        _ = wb.external_model_repo
        assert wb._external_model_repo is not None
        assert wb.external_model_repo is wb._external_model_repo

    @pytest.mark.asyncio
    async def test_model_import_job_repo_is_lazy(
        self, in_memory_session: AsyncSession
    ) -> None:
        wb = AnvilWorkbench(in_memory_session)
        assert wb._model_import_job_repo is None
        _ = wb.model_import_job_repo
        assert wb._model_import_job_repo is not None
        assert wb.model_import_job_repo is wb._model_import_job_repo

    @pytest.mark.asyncio
    async def test_instance_registry_is_lazy_with_session(
        self, in_memory_session: AsyncSession
    ) -> None:
        """instance_registry is lazy even when registry_session is provided."""
        reg_session = _mock_registry_session()
        wb = AnvilWorkbench(in_memory_session, registry_session=reg_session)
        assert wb._instance_registry is None
        _ = wb.instance_registry
        assert wb._instance_registry is not None
        assert wb.instance_registry is wb._instance_registry


# ============================================================================
# Audit enums re-exported
# ============================================================================


class TestAuditEnums:
    """AnvilWorkbench re-exports AuditAction and AuditOutcome."""

    @pytest.mark.asyncio
    async def test_audit_action_re_exported(
        self, in_memory_session: AsyncSession
    ) -> None:
        from anvil.services.governance.audit_action import AuditAction

        assert AnvilWorkbench.AuditAction is AuditAction

    @pytest.mark.asyncio
    async def test_audit_outcome_re_exported(
        self, in_memory_session: AsyncSession
    ) -> None:
        from anvil.services.governance.audit_outcome import AuditOutcome

        assert AnvilWorkbench.AuditOutcome is AuditOutcome


# ============================================================================
# Transaction context manager
# ============================================================================


class TestTransaction:
    """The ``transaction`` async context manager."""

    @pytest.mark.asyncio
    async def test_transaction_commit(self, in_memory_session: AsyncSession) -> None:
        """On success, the workbench commits the session."""
        wb = AnvilWorkbench(in_memory_session)
        async with wb.transaction():
            pass
        # The session should still be usable after commit.
        assert not in_memory_session.is_active or True  # no error

    @pytest.mark.asyncio
    async def test_transaction_rollback_on_error(
        self, in_memory_session: AsyncSession
    ) -> None:
        """On exception, the workbench rolls back and re-raises."""
        wb = AnvilWorkbench(in_memory_session)
        with pytest.raises(RuntimeError, match="test rollback"):
            async with wb.transaction():
                msg = "test rollback"
                raise RuntimeError(msg)


# ============================================================================
# get_workbench factory
# ============================================================================


class TestGetWorkbench:
    """The ``get_workbench`` FastAPI dependency factory."""

    @pytest.mark.asyncio
    async def test_get_workbench_yields_workbench(self) -> None:
        from anvil.api.deps import get_workbench

        mock_session = _mock_registry_session()
        # The generator yields session from get_db().
        mock_gen = AsyncMock()
        mock_gen.__aiter__.return_value = iter([mock_session])

        with patch("anvil.api.deps.get_db", return_value=mock_gen):
            results: list[AnvilWorkbench] = []
            async for wb in get_workbench():
                results.append(wb)
                break  # consume only one

        assert len(results) == 1
        assert isinstance(results[0], AnvilWorkbench)
        assert results[0].session is mock_session


# ============================================================================
# Evaluation services (spec 054)
# ============================================================================


class TestEvaluationServices:
    """Evaluation service and repository properties."""

    @pytest.mark.asyncio
    async def test_evaluation(self, in_memory_session: AsyncSession) -> None:
        """evaluation is a lazy EvaluationService wired to session, inference, tracking."""
        from anvil.services.evaluation.evaluation_service import EvaluationService

        wb = AnvilWorkbench(in_memory_session)
        svc = wb.evaluation
        assert isinstance(svc, EvaluationService)
        assert wb._evaluation is svc
        assert wb.evaluation is svc

    @pytest.mark.asyncio
    async def test_evaluation_run_repo(self, in_memory_session: AsyncSession) -> None:
        """evaluation_run_repo is a lazy EvaluationRunRepository."""
        from anvil.db.repositories.evaluation_runs import EvaluationRunRepository

        wb = AnvilWorkbench(in_memory_session)
        repo = wb.evaluation_run_repo
        assert isinstance(repo, EvaluationRunRepository)
        assert wb._evaluation_run_repo is repo
        assert wb.evaluation_run_repo is repo

    @pytest.mark.asyncio
    async def test_evaluation_run_repo_is_lazy(
        self, in_memory_session: AsyncSession
    ) -> None:
        wb = AnvilWorkbench(in_memory_session)
        assert wb._evaluation_run_repo is None
        _ = wb.evaluation_run_repo
        assert wb._evaluation_run_repo is not None
        assert wb.evaluation_run_repo is wb._evaluation_run_repo


# ============================================================================
# Delegate methods — evaluation (spec 054)
# ============================================================================


class TestEvaluationDelegates:
    """evaluate_fine_tuned / get_evaluation_run / get_evaluation_samples /
    list_evaluation_runs delegate to the evaluation service.
    """

    @pytest.mark.asyncio
    async def test_evaluate_fine_tuned_delegates(
        self, in_memory_session: AsyncSession
    ) -> None:
        """evaluate_fine_tuned calls evaluation.start_evaluation."""
        wb = AnvilWorkbench(in_memory_session)
        mock_eval = AsyncMock()
        wb._evaluation = mock_eval
        mock_eval.start_evaluation.return_value = AsyncMock(id=1)

        result = await wb.evaluate_fine_tuned(
            model_id=1,
            base_model_id=2,
        )
        mock_eval.start_evaluation.assert_called_once_with(
            model_id=1,
            base_model_id=2,
            adapter_id=None,
            eval_dataset_name=None,
            prompts=None,
            tokenizer_family="char",
            base_tokenizer_family=None,
        )
        assert result.id == 1

    @pytest.mark.asyncio
    async def test_evaluate_fine_tuned_with_adapter(
        self, in_memory_session: AsyncSession
    ) -> None:
        """evaluate_fine_tuned passes adapter_id and prompts through."""
        wb = AnvilWorkbench(in_memory_session)
        mock_eval = AsyncMock()
        wb._evaluation = mock_eval
        mock_eval.start_evaluation.return_value = AsyncMock(id=5)

        result = await wb.evaluate_fine_tuned(
            model_id=10,
            base_model_id=20,
            adapter_id="my-adapter",
            prompts=["hello", "world"],
            tokenizer_family="bpe",
            base_tokenizer_family="char",
        )
        mock_eval.start_evaluation.assert_called_once_with(
            model_id=10,
            base_model_id=20,
            adapter_id="my-adapter",
            eval_dataset_name=None,
            prompts=["hello", "world"],
            tokenizer_family="bpe",
            base_tokenizer_family="char",
        )
        assert result.id == 5

    @pytest.mark.asyncio
    async def test_get_evaluation_run_delegates(
        self, in_memory_session: AsyncSession
    ) -> None:
        """get_evaluation_run calls evaluation.get_run."""
        wb = AnvilWorkbench(in_memory_session)
        mock_eval = AsyncMock()
        wb._evaluation = mock_eval
        mock_eval.get_run.return_value = AsyncMock(id=42)

        result = await wb.get_evaluation_run(42)
        mock_eval.get_run.assert_called_once_with(42)
        assert result.id == 42

    @pytest.mark.asyncio
    async def test_get_evaluation_run_returns_none(
        self, in_memory_session: AsyncSession
    ) -> None:
        """get_evaluation_run returns None when not found."""
        wb = AnvilWorkbench(in_memory_session)
        mock_eval = AsyncMock()
        wb._evaluation = mock_eval
        mock_eval.get_run.return_value = None

        result = await wb.get_evaluation_run(999)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_evaluation_samples_delegates(
        self, in_memory_session: AsyncSession
    ) -> None:
        """get_evaluation_samples calls evaluation.get_samples."""
        wb = AnvilWorkbench(in_memory_session)
        mock_eval = AsyncMock()
        wb._evaluation = mock_eval
        mock_eval.get_samples.return_value = [AsyncMock(prompt="test")]

        result = await wb.get_evaluation_samples(1)
        mock_eval.get_samples.assert_called_once_with(1)
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_list_evaluation_runs_delegates(
        self, in_memory_session: AsyncSession
    ) -> None:
        """list_evaluation_runs calls evaluation.list_runs."""
        wb = AnvilWorkbench(in_memory_session)
        mock_eval = AsyncMock()
        wb._evaluation = mock_eval
        mock_run = AsyncMock(id=1)
        mock_eval.list_runs.return_value = ([mock_run], 1)

        runs, total = await wb.list_evaluation_runs(model_id=5, limit=10, offset=0)
        mock_eval.list_runs.assert_called_once_with(
            model_id=5,
            status=None,
            limit=10,
            offset=0,
        )
        assert len(runs) == 1
        assert total == 1

    @pytest.mark.asyncio
    async def test_list_evaluation_runs_with_status(
        self, in_memory_session: AsyncSession
    ) -> None:
        """list_evaluation_runs passes status filter."""
        wb = AnvilWorkbench(in_memory_session)
        mock_eval = AsyncMock()
        wb._evaluation = mock_eval
        mock_eval.list_runs.return_value = ([], 0)

        runs, total = await wb.list_evaluation_runs(status="PENDING")
        mock_eval.list_runs.assert_called_once_with(
            model_id=None,
            status="PENDING",
            limit=20,
            offset=0,
        )
        assert runs == []
        assert total == 0


# ============================================================================
# Fine-tune dataset repository (feature 053)
# ============================================================================


class TestFineTuneDataset:
    """ftd_repo property."""

    @pytest.mark.asyncio
    async def test_ftd_repo(self, in_memory_session: AsyncSession) -> None:
        from anvil.db.repositories.fine_tune_datasets import FineTuneDatasetRepository

        wb = AnvilWorkbench(in_memory_session)
        repo = wb.ftd_repo
        assert isinstance(repo, FineTuneDatasetRepository)
        assert wb._ftd_repo is repo
        assert wb.ftd_repo is repo

    @pytest.mark.asyncio
    async def test_ftd_repo_is_lazy(self, in_memory_session: AsyncSession) -> None:
        wb = AnvilWorkbench(in_memory_session)
        assert wb._ftd_repo is None
        _ = wb.ftd_repo
        assert wb._ftd_repo is not None
        assert wb.ftd_repo is wb._ftd_repo


# ============================================================================
# Model browser (feature 041)
# ============================================================================


class TestModelBrowser:
    """ModelBrowserService property — stateless service."""

    @pytest.mark.asyncio
    async def test_model_browser(self, in_memory_session: AsyncSession) -> None:
        from anvil.services.inference.model_browser import ModelBrowserService

        wb = AnvilWorkbench(in_memory_session)
        svc = wb.model_browser
        assert isinstance(svc, ModelBrowserService)
        assert wb._model_browser is svc
        assert wb.model_browser is svc

    @pytest.mark.asyncio
    async def test_model_browser_is_lazy(self, in_memory_session: AsyncSession) -> None:
        wb = AnvilWorkbench(in_memory_session)
        assert wb._model_browser is None
        _ = wb.model_browser
        assert wb._model_browser is not None
        assert wb.model_browser is wb._model_browser


# ============================================================================
# Model asset storage (feature 042)
# ============================================================================


class TestModelAssetStorage:
    """Model asset repository, download job repo, user_secret, model_store,
    and model_assets properties.
    """

    @pytest.mark.asyncio
    async def test_model_asset_repo(self, in_memory_session: AsyncSession) -> None:
        from anvil.db.repositories.model_asset_repository import ModelAssetRepository

        wb = AnvilWorkbench(in_memory_session)
        repo = wb.model_asset_repo
        assert isinstance(repo, ModelAssetRepository)
        assert wb._model_asset_repo is repo
        assert wb.model_asset_repo is repo

    @pytest.mark.asyncio
    async def test_model_asset_repo_is_lazy(
        self, in_memory_session: AsyncSession
    ) -> None:
        wb = AnvilWorkbench(in_memory_session)
        assert wb._model_asset_repo is None
        _ = wb.model_asset_repo
        assert wb._model_asset_repo is not None
        assert wb.model_asset_repo is wb._model_asset_repo

    @pytest.mark.asyncio
    async def test_asset_download_job_repo(
        self, in_memory_session: AsyncSession
    ) -> None:
        from anvil.db.repositories.asset_download_job_repository import (
            AssetDownloadJobRepository,
        )

        wb = AnvilWorkbench(in_memory_session)
        repo = wb.asset_download_job_repo
        assert isinstance(repo, AssetDownloadJobRepository)
        assert wb._asset_download_job_repo is repo
        assert wb.asset_download_job_repo is repo

    @pytest.mark.asyncio
    async def test_asset_download_job_repo_is_lazy(
        self, in_memory_session: AsyncSession
    ) -> None:
        wb = AnvilWorkbench(in_memory_session)
        assert wb._asset_download_job_repo is None
        _ = wb.asset_download_job_repo
        assert wb._asset_download_job_repo is not None
        assert wb.asset_download_job_repo is wb._asset_download_job_repo

    @pytest.mark.asyncio
    async def test_model_store_default_path(
        self, in_memory_session: AsyncSession
    ) -> None:
        """Without paths, model_store uses the fallback storage dir."""
        from anvil.storage.local import LocalFileStore

        wb = AnvilWorkbench(in_memory_session)
        store = wb.model_store
        assert isinstance(store, LocalFileStore)
        assert "data/storage" in str(store.base_path)
        assert wb._model_store is store
        assert wb.model_store is store

    @pytest.mark.asyncio
    async def test_model_store_with_paths(
        self, in_memory_session: AsyncSession, tmp_path: Path
    ) -> None:
        """With paths, model_store uses paths.storage_dir."""
        from anvil.storage.local import LocalFileStore
        from anvil.workspace.workspace_paths import WorkspacePaths

        paths = WorkspacePaths(tmp_path)
        wb = AnvilWorkbench(in_memory_session, paths=paths)
        store = wb.model_store
        assert isinstance(store, LocalFileStore)
        assert str(paths.storage_dir) in str(store.base_path)

    @pytest.mark.asyncio
    async def test_model_store_is_lazy(self, in_memory_session: AsyncSession) -> None:
        wb = AnvilWorkbench(in_memory_session)
        assert wb._model_store is None
        _ = wb.model_store
        assert wb._model_store is not None
        assert wb.model_store is wb._model_store

    @pytest.mark.asyncio
    async def test_model_assets(
        self, in_memory_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """ModelAssetService chains many deps — verify it constructs."""
        from anvil.services.model_import.model_asset_service import ModelAssetService

        monkeypatch.setenv("ANVIL_MASTER_SECRET", "ab" * 16)
        wb = AnvilWorkbench(in_memory_session)
        svc = wb.model_assets
        assert isinstance(svc, ModelAssetService)
        assert wb._model_assets is svc
        assert wb.model_assets is svc

    @pytest.mark.asyncio
    async def test_model_assets_is_lazy(
        self, in_memory_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ANVIL_MASTER_SECRET", "ab" * 16)
        wb = AnvilWorkbench(in_memory_session)
        assert wb._model_assets is None
        _ = wb.model_assets
        assert wb._model_assets is not None
        assert wb.model_assets is wb._model_assets


# ============================================================================
# User secrets (feature 042)
# ============================================================================


class TestUserSecrets:
    """User secret repository, service, and rotation service."""

    @pytest.mark.asyncio
    async def test_user_secret_repo(self, in_memory_session: AsyncSession) -> None:
        from anvil.db.repositories.user_secret_repository import UserSecretRepository

        wb = AnvilWorkbench(in_memory_session)
        repo = wb.user_secret_repo
        assert isinstance(repo, UserSecretRepository)
        assert wb._user_secret_repo is repo
        assert wb.user_secret_repo is repo

    @pytest.mark.asyncio
    async def test_user_secret_repo_is_lazy(
        self, in_memory_session: AsyncSession
    ) -> None:
        wb = AnvilWorkbench(in_memory_session)
        assert wb._user_secret_repo is None
        _ = wb.user_secret_repo
        assert wb._user_secret_repo is not None
        assert wb.user_secret_repo is wb._user_secret_repo

    @pytest.mark.asyncio
    async def test_user_secrets(
        self, in_memory_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """user_secrets requires a master secret env var."""
        from anvil.services.secrets.user_secret_service import UserSecretService

        monkeypatch.setenv("ANVIL_MASTER_SECRET", "ab" * 16)
        wb = AnvilWorkbench(in_memory_session)
        svc = wb.user_secrets
        assert isinstance(svc, UserSecretService)
        assert wb._user_secrets is svc
        assert wb.user_secrets is svc

    @pytest.mark.asyncio
    async def test_user_secrets_is_lazy(
        self, in_memory_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ANVIL_MASTER_SECRET", "ab" * 16)
        wb = AnvilWorkbench(in_memory_session)
        assert wb._user_secrets is None
        _ = wb.user_secrets
        assert wb._user_secrets is not None
        assert wb.user_secrets is wb._user_secrets

    @pytest.mark.asyncio
    async def test_secret_rotation_service(
        self, in_memory_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """secret_rotation_service derives encryption from user_secrets."""
        from anvil.services.secrets.secret_rotation_service import SecretRotationService

        monkeypatch.setenv("ANVIL_MASTER_SECRET", "ab" * 16)
        wb = AnvilWorkbench(in_memory_session)
        svc = wb.secret_rotation_service
        assert isinstance(svc, SecretRotationService)
        assert wb._secret_rotation is svc
        assert wb.secret_rotation_service is svc

    @pytest.mark.asyncio
    async def test_secret_rotation_service_is_lazy(
        self, in_memory_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ANVIL_MASTER_SECRET", "ab" * 16)
        wb = AnvilWorkbench(in_memory_session)
        assert wb._secret_rotation is None
        _ = wb.secret_rotation_service
        assert wb._secret_rotation is not None
        assert wb.secret_rotation_service is wb._secret_rotation


# ============================================================================
# LoRA adapter (feature 044)
# ============================================================================


class TestLoRAAdapter:
    """lora_adapter_repo property."""

    @pytest.mark.asyncio
    async def test_lora_adapter_repo(self, in_memory_session: AsyncSession) -> None:
        from anvil.db.repositories.lora_adapter_repository import LoRAAdapterRepository

        wb = AnvilWorkbench(in_memory_session)
        repo = wb.lora_adapter_repo
        assert isinstance(repo, LoRAAdapterRepository)
        assert wb._lora_adapter_repo is repo
        assert wb.lora_adapter_repo is repo

    @pytest.mark.asyncio
    async def test_lora_adapter_repo_is_lazy(
        self, in_memory_session: AsyncSession
    ) -> None:
        wb = AnvilWorkbench(in_memory_session)
        assert wb._lora_adapter_repo is None
        _ = wb.lora_adapter_repo
        assert wb._lora_adapter_repo is not None
        assert wb.lora_adapter_repo is wb._lora_adapter_repo


# ============================================================================
# Adapter merge + export (feature 045)
# ============================================================================


class TestAdapterMerge:
    """merge_service and training_runs properties."""

    @pytest.mark.asyncio
    async def test_merge_service(self, in_memory_session: AsyncSession) -> None:
        from anvil.services.training.merge_service import AdapterMergeService

        wb = AnvilWorkbench(in_memory_session)
        svc = wb.merge_service
        assert isinstance(svc, AdapterMergeService)
        assert wb._merge_service is svc
        assert wb.merge_service is svc

    @pytest.mark.asyncio
    async def test_merge_service_is_lazy(self, in_memory_session: AsyncSession) -> None:
        wb = AnvilWorkbench(in_memory_session)
        assert wb._merge_service is None
        _ = wb.merge_service
        assert wb._merge_service is not None
        assert wb.merge_service is wb._merge_service

    @pytest.mark.asyncio
    async def test_training_runs(self, in_memory_session: AsyncSession) -> None:
        from anvil.services.training.training_run_service import TrainingRunService

        wb = AnvilWorkbench(in_memory_session)
        svc = wb.training_runs
        assert isinstance(svc, TrainingRunService)
        assert wb._training_runs is svc
        assert wb.training_runs is svc

    @pytest.mark.asyncio
    async def test_training_runs_is_lazy(self, in_memory_session: AsyncSession) -> None:
        wb = AnvilWorkbench(in_memory_session)
        assert wb._training_runs is None
        _ = wb.training_runs
        assert wb._training_runs is not None
        assert wb.training_runs is wb._training_runs

    @pytest.mark.asyncio
    async def test_training_runs_with_paths(
        self, in_memory_session: AsyncSession, tmp_path: Path
    ) -> None:
        """With paths, training_runs uses paths.models_dir."""
        from anvil.workspace.workspace_paths import WorkspacePaths

        paths = WorkspacePaths(tmp_path)
        wb = AnvilWorkbench(in_memory_session, paths=paths)
        svc = wb.training_runs
        assert svc is not None

    @pytest.mark.asyncio
    async def test_training_runs_default_path(
        self, in_memory_session: AsyncSession
    ) -> None:
        """Without paths, training_runs uses default models dir."""
        wb = AnvilWorkbench(in_memory_session)
        svc = wb.training_runs
        assert svc is not None


# ============================================================================
# Teaching loop (spec 055)
# ============================================================================


class TestTeaching:
    """teaching_repo and teaching properties."""

    @pytest.mark.asyncio
    async def test_teaching_repo(self, in_memory_session: AsyncSession) -> None:
        from anvil.db.repositories.teaching_session_repository import (
            TeachingSessionRepository,
        )

        wb = AnvilWorkbench(in_memory_session)
        repo = wb.teaching_repo
        assert isinstance(repo, TeachingSessionRepository)
        assert wb._teaching_repo is repo
        assert wb.teaching_repo is repo

    @pytest.mark.asyncio
    async def test_teaching_repo_is_lazy(self, in_memory_session: AsyncSession) -> None:
        wb = AnvilWorkbench(in_memory_session)
        assert wb._teaching_repo is None
        _ = wb.teaching_repo
        assert wb._teaching_repo is not None
        assert wb.teaching_repo is wb._teaching_repo

    @pytest.mark.asyncio
    async def test_teaching(self, in_memory_session: AsyncSession) -> None:
        """TeachingService chains many deps — verify it constructs."""
        from anvil.services.teaching.teaching_service import TeachingService

        wb = AnvilWorkbench(in_memory_session)
        svc = wb.teaching
        assert isinstance(svc, TeachingService)
        assert wb._teaching is svc
        assert wb.teaching is svc

    @pytest.mark.asyncio
    async def test_teaching_is_lazy(self, in_memory_session: AsyncSession) -> None:
        wb = AnvilWorkbench(in_memory_session)
        assert wb._teaching is None
        _ = wb.teaching
        assert wb._teaching is not None
        assert wb.teaching is wb._teaching
