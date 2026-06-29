"""Tests for backup & restore API endpoints.

Covers list, create, get, restore, delete, and storage-status routes
against a mocked workbench and backup service.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from anvil.api.app import app
from anvil.api.deps import get_workbench
from anvil.services.backup.backup_storage_status import BackupStorageStatus
from anvil.services.backup.backup_summary import BackupSummary
from anvil.services.backup.create_backup_result import CreateBackupResult


@pytest.fixture
def mock_workbench():
    wb = MagicMock()
    wb.backup_repo = MagicMock()
    wb.audit = MagicMock()
    wb.audit.record = AsyncMock()
    return wb


@pytest.fixture
def mock_backup_service():
    svc = MagicMock()
    svc.create_backup = AsyncMock()
    svc.list_backups = AsyncMock()
    svc.get_backup = AsyncMock()
    svc.restore = AsyncMock()
    svc.delete_backup = AsyncMock()
    svc.storage_status = AsyncMock()
    svc.cleanup_safety = AsyncMock()
    svc.stream_for = MagicMock()
    svc.verify = AsyncMock()
    svc.restore_preview = AsyncMock()
    return svc


@pytest.fixture
def override_dep(mock_workbench, mock_backup_service):
    app.dependency_overrides[get_workbench] = lambda: mock_workbench
    app.state.backup_service = mock_backup_service
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def sample_summary():
    return BackupSummary(
        backup_id="20260101T120000Z-abc123",
        operation_type="backup",
        status="completed",
        created_at=datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC),
        archive_size_bytes=1024,
        deployment_version="1.0.0",
        schema_revision="abc123def",
        age_seconds=3600,
        is_safety_snapshot=False,
        deletable=True,
    )


class TestListBackups:
    async def test_returns_list(
        self, client, mock_workbench, mock_backup_service, sample_summary, override_dep
    ):
        mock_backup_service.list_backups = AsyncMock(return_value=[sample_summary])
        resp = await client.get("/v1/backup")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["backup_id"] == "20260101T120000Z-abc123"
        assert data[0]["status"] == "completed"
        assert data[0]["archive_size_bytes"] == 1024

    async def test_empty_list(
        self, client, mock_workbench, mock_backup_service, override_dep
    ):
        mock_backup_service.list_backups = AsyncMock(return_value=[])
        resp = await client.get("/v1/backup")
        assert resp.status_code == 200
        assert resp.json() == []


class TestCreateBackup:
    async def test_creates_backup(
        self, client, mock_workbench, mock_backup_service, override_dep
    ):
        mock_backup_service.create_backup = AsyncMock(
            return_value=CreateBackupResult(
                backup_id="20260101T120000Z-abc123", rotated_backup_ids=[]
            )
        )
        resp = await client.post("/v1/backup")
        assert resp.status_code == 202
        data = resp.json()
        assert data["backup_id"] == "20260101T120000Z-abc123"
        assert data["status"] == "creating"

    async def test_create_conflict(
        self, client, mock_workbench, mock_backup_service, override_dep
    ):
        mock_backup_service.create_backup = AsyncMock(
            side_effect=RuntimeError(
                "A backup or restore operation is already in progress"
            )
        )
        resp = await client.post("/v1/backup")
        assert resp.status_code == 409
        assert "already in progress" in resp.json()["detail"]


class TestGetBackup:
    async def test_get_existing(
        self, client, mock_workbench, mock_backup_service, sample_summary, override_dep
    ):
        mock_backup_service.get_backup = AsyncMock(return_value=sample_summary)
        resp = await client.get("/v1/backup/20260101T120000Z-abc123")
        assert resp.status_code == 200
        assert resp.json()["backup_id"] == "20260101T120000Z-abc123"

    async def test_get_missing(
        self, client, mock_workbench, mock_backup_service, override_dep
    ):
        mock_backup_service.get_backup = AsyncMock(return_value=None)
        resp = await client.get("/v1/backup/nonexistent")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Backup not found"


class TestRestoreBackup:
    async def test_restore_success(
        self, client, mock_workbench, mock_backup_service, override_dep
    ):
        mock_backup_service.restore = AsyncMock(
            return_value={
                "restore_operation_id": "restore-abc123-20260101T130000Z",
                "safety_snapshot_id": "safety-xyz789",
                "status": "completed",
            }
        )
        resp = await client.post(
            "/v1/backup/20260101T120000Z-abc123/restore",
            json={"confirm": "RESTORE"},
        )
        assert resp.status_code == 202
        data = resp.json()
        assert data["restore_operation_id"] == "restore-abc123-20260101T130000Z"
        assert data["safety_snapshot_id"] == "safety-xyz789"
        assert data["status"] == "completed"

    async def test_restore_bad_confirm(
        self, client, mock_workbench, mock_backup_service, override_dep
    ):
        mock_backup_service.restore = AsyncMock(
            side_effect=ValueError("Confirmation token must be 'RESTORE'")
        )
        resp = await client.post(
            "/v1/backup/20260101T120000Z-abc123/restore",
            json={"confirm": "no"},
        )
        assert resp.status_code == 400
        assert "RESTORE" in resp.json()["detail"]

    async def test_restore_blocked(
        self, client, mock_workbench, mock_backup_service, override_dep
    ):
        mock_backup_service.restore = AsyncMock(
            side_effect=PermissionError("Schema compatibility check failed")
        )
        resp = await client.post(
            "/v1/backup/20260101T120000Z-abc123/restore",
            json={"confirm": "RESTORE"},
        )
        assert resp.status_code == 409

    async def test_restore_already_in_progress(
        self, client, mock_workbench, mock_backup_service, override_dep
    ):
        mock_backup_service.restore = AsyncMock(
            side_effect=RuntimeError(
                "A backup or restore operation is already in progress"
            )
        )
        resp = await client.post(
            "/v1/backup/20260101T120000Z-abc123/restore",
            json={"confirm": "RESTORE"},
        )
        assert resp.status_code == 409


class TestDeleteBackup:
    async def test_delete_success(
        self, client, mock_workbench, mock_backup_service, override_dep
    ):
        mock_backup_service.delete_backup = AsyncMock(return_value=None)
        resp = await client.delete("/v1/backup/20260101T120000Z-abc123")
        assert resp.status_code == 200
        assert resp.json() == {"deleted": "20260101T120000Z-abc123"}

    async def test_delete_not_found(
        self, client, mock_workbench, mock_backup_service, override_dep
    ):
        mock_backup_service.delete_backup = AsyncMock(
            side_effect=ValueError("Backup not found: nonexistent")
        )
        resp = await client.delete("/v1/backup/nonexistent")
        assert resp.status_code == 404

    async def test_delete_forbidden(
        self, client, mock_workbench, mock_backup_service, override_dep
    ):
        mock_backup_service.delete_backup = AsyncMock(
            side_effect=PermissionError("Safety snapshots cannot be deleted")
        )
        resp = await client.delete("/v1/backup/safety-snap-001")
        assert resp.status_code == 403


class TestStorageStatus:
    async def test_returns_storage_info(
        self, client, mock_workbench, mock_backup_service, override_dep
    ):
        mock_backup_service.storage_status = AsyncMock(
            return_value=BackupStorageStatus(
                backup_count=3,
                total_bytes=3072,
                quota_bytes=10 * 1024**3,
                quota_used_fraction=0.000000286,
                over_threshold=False,
                latest_backup_at=datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC),
                oldest_backup_at=datetime(2025, 12, 1, 12, 0, 0, tzinfo=UTC),
            )
        )
        resp = await client.get("/v1/backup/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["backup_count"] == 3
        assert data["total_bytes"] == 3072
        assert data["over_threshold"] is False
        assert data["latest_backup_at"] is not None
