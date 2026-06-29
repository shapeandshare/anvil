"""Tests for DatasetService — CRUD and document loading.

Uses mock repository/store to unit test the DatasetService class.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from anvil.db.models.dataset import Dataset
from anvil.services.datasets.datasets import DatasetService
from anvil.services.governance.audit_action import AuditAction
from anvil.services.governance.audit_outcome import AuditOutcome


@pytest.fixture
def mock_repo():
    repo = MagicMock()
    repo.get_all = AsyncMock(return_value=[])
    repo.get = AsyncMock(return_value=None)
    repo.add = AsyncMock()
    repo.update = AsyncMock()
    repo.delete = AsyncMock()
    repo.search = AsyncMock(return_value=[])
    repo.has_referencing_configs = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def service(mock_repo):
    return DatasetService(repo=mock_repo)


class TestListDatasets:
    async def test_empty(self, service, mock_repo):
        result = await service.list_datasets()
        assert result == []
        mock_repo.get_all.assert_awaited_once()

    async def test_returns_datasets(self, service, mock_repo):
        ds = Dataset(id=1, name="test", description="desc", filename="f", file_path="p")
        mock_repo.get_all.return_value = [ds]
        result = await service.list_datasets()
        assert len(result) == 1
        assert result[0].name == "test"


class TestGetDataset:
    async def test_found(self, service, mock_repo):
        ds = Dataset(id=1, name="test", description="desc", filename="f", file_path="p")
        mock_repo.get.return_value = ds
        result = await service.get_dataset(1)
        assert result is not None
        assert result.id == 1

    async def test_not_found(self, service, mock_repo):
        mock_repo.get.return_value = None
        result = await service.get_dataset(999)
        assert result is None


class TestCreateDataset:
    async def test_creates_with_name(self, service, mock_repo):
        ds = Dataset(id=1, name="new-ds", description=None, filename="", file_path="")
        mock_repo.add.return_value = ds
        result = await service.create_dataset(name="new-ds")
        assert result.name == "new-ds"
        mock_repo.add.assert_awaited_once()

    async def test_creates_with_description(self, service, mock_repo):
        ds = Dataset(id=2, name="ds", description="my desc", filename="", file_path="")
        mock_repo.add.return_value = ds
        result = await service.create_dataset(name="ds", description="my desc")
        assert result.description == "my desc"


class TestUpdateDataset:
    async def test_updates_name(self, service, mock_repo):
        ds = Dataset(id=1, name="old", description="desc", filename="f", file_path="p")
        mock_repo.get.return_value = ds
        ds.name = "new"
        mock_repo.update.return_value = ds
        result = await service.update_dataset(1, name="new")
        assert result is not None
        assert result.name == "new"

    async def test_updates_description(self, service, mock_repo):
        ds = Dataset(id=1, name="ds", description="old", filename="f", file_path="p")
        mock_repo.get.return_value = ds
        ds.description = "new"
        mock_repo.update.return_value = ds
        result = await service.update_dataset(1, description="new")
        assert result is not None
        assert result.description == "new"

    async def test_not_found(self, service, mock_repo):
        mock_repo.get.return_value = None
        result = await service.update_dataset(999, name="x")
        assert result is None


class TestDeleteDataset:
    async def test_delete_without_configs(self, service, mock_repo):
        mock_repo.has_referencing_configs.return_value = []
        await service.delete_dataset(1)
        mock_repo.delete.assert_awaited_once_with(1)

    async def test_delete_with_configs_raises(self, service, mock_repo):
        cfg = MagicMock()
        cfg.name = "my-config"
        cfg.id = 1
        mock_repo.has_referencing_configs.return_value = [cfg]
        with pytest.raises(ValueError, match="Cannot delete dataset"):
            await service.delete_dataset(1)

    async def test_delete_with_audit(self, service, mock_repo):
        mock_repo.has_referencing_configs.return_value = []
        audit = MagicMock()
        audit.record = AsyncMock()
        await service.delete_dataset(1, audit=audit)
        audit.record.assert_awaited_once_with(
            action_type=AuditAction.DELETE.value,
            target_type="dataset",
            target_id="1",
            actor="system",
            outcome=AuditOutcome.SUCCESS.value,
        )


class TestSearchDatasets:
    async def test_search(self, service, mock_repo):
        mock_repo.search.return_value = [
            Dataset(id=1, name="found", description=None, filename="f", file_path="p")
        ]
        result = await service.search_datasets("query")
        assert len(result) == 1


class TestConstructor:
    def test_with_explicit_store(self, mock_repo):
        store = MagicMock()
        svc = DatasetService(repo=mock_repo, store=store)
        assert svc._store is store

    def test_with_paths(self, mock_repo):
        paths = MagicMock()
        paths.datasets_dir = "/tmp/datasets"
        svc = DatasetService(repo=mock_repo, paths=paths)
        assert svc._store is not None
