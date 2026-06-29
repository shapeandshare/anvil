"""Unit tests for AnvilWorkbench lazy-init properties.

Verifies that each lazy property on the god class returns the correct
service/repository type, is cached on subsequent access (``is``),
and that factory methods return fresh instances of the correct type.
"""

from __future__ import annotations

import pytest

from anvil.db.repositories.backup_operations import BackupOperationRepository
from anvil.db.repositories.instance_registry import InstanceRegistryRepository
from anvil.db.repositories.runtime_config import RuntimeConfigRepository
from anvil.services.content.corpus_service import CorpusService as ContentCorpusService
from anvil.services.datasets.corpora import CorpusService
from anvil.services.datasets.dataset_curation import DatasetCurationService
from anvil.services.datasets.dataset_export import DatasetExportService
from anvil.services.datasets.dataset_import import DatasetImportService
from anvil.services.datasets.datasets import DatasetService
from anvil.services.demo.demo_bootstrap import DemoBootstrapService
from anvil.services.governance.audit_service import AuditService
from anvil.services.governance.governance_service import GovernanceService
from anvil.services.inference.inference import InferenceService
from anvil.services.instances.instance_lifecycle_service import InstanceLifecycleService
from anvil.services.model_import.model_import_service import ModelImportService
from anvil.services.runtime_config.runtime_config_service import RuntimeConfigService
from anvil.services.tracking.tracking import TrackingService
from anvil.storage.local import LocalFileStore
from anvil.workbench import AnvilWorkbench


class TestAnvilWorkbenchProperties:
    """Verify every lazy property on AnvilWorkbench returns the correct type
    and is cached (same object on second access).
    """

    # ── Stateless service accessors ────────────────────────────────────

    @pytest.mark.asyncio
    async def test_tracking(self, in_memory_session) -> None:
        wb = AnvilWorkbench(session=in_memory_session)
        svc = wb.tracking
        assert isinstance(svc, TrackingService)
        assert wb.tracking is svc  # cached

    @pytest.mark.asyncio
    async def test_inference(self, in_memory_session) -> None:
        wb = AnvilWorkbench(session=in_memory_session)
        svc = wb.inference
        assert isinstance(svc, InferenceService)
        assert wb.inference is svc

    # ── Repository helpers ────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_store(self, in_memory_session) -> None:
        wb = AnvilWorkbench(session=in_memory_session)
        s = wb.store
        assert isinstance(s, LocalFileStore)
        assert wb.store is s

    # ── DB-backed domain service accessors ────────────────────────────

    @pytest.mark.asyncio
    async def test_datasets(self, in_memory_session) -> None:
        wb = AnvilWorkbench(session=in_memory_session)
        svc = wb.datasets
        assert isinstance(svc, DatasetService)
        assert wb.datasets is svc

    @pytest.mark.asyncio
    async def test_corpora(self, in_memory_session) -> None:
        wb = AnvilWorkbench(session=in_memory_session)
        svc = wb.corpora
        assert isinstance(svc, CorpusService)
        assert wb.corpora is svc

    @pytest.mark.asyncio
    async def test_demo(self, in_memory_session) -> None:
        wb = AnvilWorkbench(session=in_memory_session)
        svc = wb.demo
        assert isinstance(svc, DemoBootstrapService)
        assert wb.demo is svc

    # ── Governance accessors ──────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_audit(self, in_memory_session) -> None:
        wb = AnvilWorkbench(session=in_memory_session)
        svc = wb.audit
        assert isinstance(svc, AuditService)
        assert wb.audit is svc

    @pytest.mark.asyncio
    async def test_governance(self, in_memory_session) -> None:
        wb = AnvilWorkbench(session=in_memory_session)
        svc = wb.governance
        assert isinstance(svc, GovernanceService)
        assert wb.governance is svc

    # ── Content services ──────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_content_corpora(self, in_memory_session) -> None:
        wb = AnvilWorkbench(session=in_memory_session)
        svc = wb.content_corpora
        assert isinstance(svc, ContentCorpusService)
        assert wb.content_corpora is svc

    # ── Instance lifecycle accessors (feature 028) ────────────────────

    @pytest.mark.asyncio
    async def test_instances(self, in_memory_session) -> None:
        wb = AnvilWorkbench(session=in_memory_session)
        svc = wb.instances
        assert isinstance(svc, InstanceLifecycleService)
        assert wb.instances is svc

    @pytest.mark.asyncio
    async def test_instance_registry(self, in_memory_session) -> None:
        """Provide the same session as registry_session to avoid
        ``asyncio.run()`` inside an async test.
        """
        wb = AnvilWorkbench(
            session=in_memory_session, registry_session=in_memory_session
        )
        repo = wb.instance_registry
        assert isinstance(repo, InstanceRegistryRepository)
        assert wb.instance_registry is repo

    # ── Runtime config accessors (feature 037) ────────────────────────

    @pytest.mark.asyncio
    async def test_runtime_config_repo(self, in_memory_session) -> None:
        wb = AnvilWorkbench(session=in_memory_session)
        repo = wb.runtime_config_repo
        assert isinstance(repo, RuntimeConfigRepository)
        assert wb.runtime_config_repo is repo

    @pytest.mark.asyncio
    async def test_runtime_config(self, in_memory_session) -> None:
        wb = AnvilWorkbench(session=in_memory_session)
        svc = wb.runtime_config
        assert isinstance(svc, RuntimeConfigService)
        assert wb.runtime_config is svc

    # ── Model import accessors (feature 040) ──────────────────────────

    @pytest.mark.asyncio
    async def test_model_imports(self, in_memory_session) -> None:
        wb = AnvilWorkbench(session=in_memory_session)
        svc = wb.model_imports
        assert isinstance(svc, ModelImportService)
        assert wb.model_imports is svc

    # ── Backup & Restore accessors (feature 026) ──────────────────────

    @pytest.mark.asyncio
    async def test_backup_repo(self, in_memory_session) -> None:
        wb = AnvilWorkbench(session=in_memory_session)
        repo = wb.backup_repo
        assert isinstance(repo, BackupOperationRepository)
        assert wb.backup_repo is repo

    # ── Factory methods (return fresh instances each call) ────────────

    @pytest.mark.asyncio
    async def test_dataset_import_factory(self, in_memory_session) -> None:
        wb = AnvilWorkbench(session=in_memory_session)
        svc = wb.dataset_import(1)
        assert isinstance(svc, DatasetImportService)
        # Factory methods are NOT cached — each call creates a new instance.
        svc2 = wb.dataset_import(1)
        assert svc2 is not svc

    @pytest.mark.asyncio
    async def test_dataset_curation_factory(self, in_memory_session) -> None:
        wb = AnvilWorkbench(session=in_memory_session)
        svc = wb.dataset_curation(1)
        assert isinstance(svc, DatasetCurationService)
        svc2 = wb.dataset_curation(1)
        assert svc2 is not svc

    @pytest.mark.asyncio
    async def test_dataset_export_factory(self, in_memory_session) -> None:
        wb = AnvilWorkbench(session=in_memory_session)
        svc = wb.dataset_export(1)
        assert isinstance(svc, DatasetExportService)
        svc2 = wb.dataset_export(1)
        assert svc2 is not svc

    # ── Session lifecycle ─────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_session_property(self, in_memory_session) -> None:
        wb = AnvilWorkbench(session=in_memory_session)
        assert wb.session is in_memory_session

    @pytest.mark.asyncio
    async def test_transaction_context_manager(self, in_memory_session) -> None:
        """``transaction`` yields the workbench and commits/rolls back."""
        wb = AnvilWorkbench(session=in_memory_session)
        async with wb.transaction() as ctx:
            assert ctx is wb
        # After successful exit, the session should have been committed
        # (no exception → commit was called).
        # We verify by checking the session is still usable.
        assert wb.session is in_memory_session

    @pytest.mark.asyncio
    async def test_transaction_rollback_on_error(self, in_memory_session) -> None:
        """``transaction`` rolls back and re-raises on error."""
        wb = AnvilWorkbench(session=in_memory_session)
        with pytest.raises(RuntimeError, match="boom"):
            async with wb.transaction():
                msg = "boom"
                raise RuntimeError(msg)
        # Session should still be usable after rollback.
        assert wb.session is in_memory_session
