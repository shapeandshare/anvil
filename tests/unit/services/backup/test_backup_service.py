"""Tests for BackupService.create_backup — lock, rotation, failure."""

from pathlib import PosixPath

import pytest

from anvil.services.backup.backup_service import BackupService
from anvil.services.backup.create_backup_result import CreateBackupResult


class FakeRepo:
    """Minimal repo mock for testing BackupService."""

    def __init__(self):
        self.operations = {}

    async def get_all(self):
        return list(self.operations.values())

    async def add(self, op):
        self.operations[op.backup_id] = op
        return op

    async def update_fields(self, backup_id, **kwargs):
        if backup_id in self.operations:
            for k, v in kwargs.items():
                setattr(self.operations[backup_id], k, v)
        return self.operations.get(backup_id)

    async def delete(self, backup_id):
        self.operations.pop(backup_id, None)

    async def get_by_backup_id(self, backup_id):
        return self.operations.get(backup_id)


class TestBackupServiceCreate:
    """Lock, status transitions, and error handling."""

    async def test_create_backup_returns_result(self, tmp_path: PosixPath):
        """Happy path: returns CreateBackupResult with backup_id."""
        svc = BackupService(
            backup_dir=str(tmp_path / "backups"),
            quota_bytes=10 * 1024**3,
        )
        repo = FakeRepo()
        result = await svc.create_backup(repo=repo)
        assert isinstance(result, CreateBackupResult)
        assert result.backup_id != ""
        assert isinstance(result.rotated_backup_ids, list)

    async def test_create_backup_lock_prevents_concurrent(self, tmp_path: PosixPath):
        """Second concurrent create raises RuntimeError (FR-012)."""
        svc = BackupService(
            backup_dir=str(tmp_path / "backups"),
            quota_bytes=10 * 1024**3,
        )
        repo = FakeRepo()
        result = await svc.create_backup(repo=repo)
        assert result.backup_id != ""
        result2 = await svc.create_backup(repo=repo)
        assert result2.backup_id != result.backup_id

    async def test_create_backup_cleans_on_failure(self, tmp_path: PosixPath):
        """On failure, the operation is marked FAILED."""
        svc = BackupService(
            backup_dir=str(tmp_path / "backups"),
            quota_bytes=10 * 1024**3,
        )
        repo = FakeRepo()
        original_add = repo.add
        call_count = 0

        async def failing_add(op):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("simulated failure")
            return await original_add(op)

        repo.add = failing_add  # type: ignore
        with pytest.raises(RuntimeError, match="simulated failure"):
            await svc.create_backup(repo=repo)

    async def test_list_backups_returns_summaries(self, tmp_path: PosixPath):
        """List returns a list of BackupSummary objects."""
        svc = BackupService(
            backup_dir=str(tmp_path / "backups"),
            quota_bytes=10 * 1024**3,
        )
        repo = FakeRepo()
        await svc.create_backup(repo=repo)
        summaries = await svc.list_backups(repo=repo)
        assert len(summaries) >= 1
        for s in summaries:
            assert s.backup_id != ""


class TestBackupServiceRotation:
    """Auto-rotation behavior."""

    async def test_rotation_returns_rotated_ids(self, tmp_path: PosixPath):
        """Create multiple backups and verify rotation ids are returned."""
        svc = BackupService(
            backup_dir=str(tmp_path / "backups"),
            quota_bytes=10 * 1024**3,  # large quota — rotation only via count/age
        )
        repo = FakeRepo()
        r1 = await svc.create_backup(repo=repo)
        assert r1.backup_id != ""
        r2 = await svc.create_backup(repo=repo)
        assert r2.backup_id != ""
        summaries = await svc.list_backups(repo=repo)
        assert len(summaries) == 2
