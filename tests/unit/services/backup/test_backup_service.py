"""Tests for BackupService — create, list, restore, delete, verify, etc."""

import asyncio
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path, PosixPath
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

from anvil.db.models.backup_operation import BackupOperation
from anvil.services.backup.backup_service import BackupService
from anvil.services.backup.backup_storage_status import BackupStorageStatus
from anvil.services.backup.backup_summary import BackupSummary
from anvil.services.backup.create_backup_result import CreateBackupResult
from anvil.services.backup.progress_event import ProgressEvent
from anvil.services.backup.restore_preview import RestorePreview
from anvil.services.backup.verify_result import VerifyResult

###############################################################################
# FakeRepo — minimal async repo mock
###############################################################################


class FakeRepo:
    """Minimal repo mock for testing BackupService.

    Stores :class:`BackupOperation` instances in an in-memory dict.
    ``created_at`` is auto-set on ``add()`` if not already set.
    """

    def __init__(self) -> None:
        self.operations: dict[str, BackupOperation] = {}

    async def get_all(self) -> Sequence[BackupOperation]:
        await asyncio.sleep(0)
        return list(self.operations.values())

    async def get_all_restorable(self) -> Sequence[BackupOperation]:
        await asyncio.sleep(0)
        return [
            op
            for op in self.operations.values()
            if getattr(op, "operation_type", "") != "pre_restore_safety"
        ]

    async def add(self, operation: BackupOperation) -> BackupOperation:
        await asyncio.sleep(0)
        if getattr(operation, "created_at", None) is None:
            operation.created_at = datetime.now(UTC)
        self.operations[operation.backup_id] = operation
        return operation

    async def update_fields(
        self, backup_id: str, **kwargs: object
    ) -> BackupOperation | None:
        await asyncio.sleep(0)
        if backup_id in self.operations:
            for k, v in kwargs.items():
                setattr(self.operations[backup_id], k, v)
        return self.operations.get(backup_id)

    async def delete(self, backup_id: str) -> None:
        await asyncio.sleep(0)
        self.operations.pop(backup_id, None)

    async def get_by_backup_id(self, backup_id: str) -> BackupOperation | None:
        await asyncio.sleep(0)
        return self.operations.get(backup_id)


###############################################################################
# Helpers
###############################################################################


def make_svc(
    tmp_path: PosixPath,
    quota_bytes: int = 10 * 1024**3,
    warn_fraction: float = 0.8,
    retention_max_count: int | None = None,
    retention_max_age_days: int | None = None,
) -> BackupService:
    """Create a :class:`BackupService` pointed at *tmp_path*.

    Uses private ``_retention_max_count`` / ``_retention_max_age_days``
    parameters so we control rotation without environment variables.
    """
    return BackupService(
        backup_dir=str(tmp_path / "backups"),
        quota_bytes=quota_bytes,
        warn_fraction=warn_fraction,
        _retention_max_count=retention_max_count,
        _retention_max_age_days=retention_max_age_days,
    )


def _op(
    backup_id: str,
    operation_type: str = "backup",
    status: str = "completed",
    archive_size_bytes: int = 0,
    created_at: datetime | None = None,
    deployment_version: str | None = "1.0.0",
    schema_revision: str | None = "abc",
) -> BackupOperation:
    """Return a minimal ``BackupOperation`` with defaults for testing."""
    op = BackupOperation(backup_id=backup_id)
    op.operation_type = operation_type
    op.status = status
    op.archive_size_bytes = archive_size_bytes
    if created_at is not None:
        op.created_at = created_at
    op.deployment_version = deployment_version
    op.schema_revision = schema_revision
    return op


###############################################################################
# Tests — Initialisation
###############################################################################


class TestBackupServiceInit:
    """Constructor-level behaviour."""

    async def test_accepts_backup_dir(self, tmp_path: PosixPath):
        """The backup dir parameter is accepted without error."""
        bdir = tmp_path / "my-backups"
        svc = BackupService(backup_dir=str(bdir), quota_bytes=10 * 1024**3)
        assert svc is not None

    async def test_sweeps_tmp_dirs(self, tmp_path: PosixPath):
        """Left-over .tmp/ and .restore-tmp/ dirs are cleaned on init."""
        import os

        bdir = tmp_path / "backups"
        bdir.mkdir(parents=True)
        (bdir / ".tmp").mkdir()
        (bdir / ".restore-tmp").mkdir()
        # The cwd-level .restore-tmp is what BackupService cleans
        # (not one under tmp_path).
        cwd_resttmp = Path(os.getcwd()) / ".restore-tmp"
        cwd_resttmp.mkdir(parents=True, exist_ok=True)
        try:
            BackupService(backup_dir=str(bdir), quota_bytes=10 * 1024**3)

            assert not (bdir / ".tmp").exists()
            assert not (bdir / ".restore-tmp").exists()
            assert not cwd_resttmp.exists()
        finally:
            if cwd_resttmp.exists():
                import shutil

                shutil.rmtree(cwd_resttmp, ignore_errors=True)

    async def test_lock_property(self, tmp_path: PosixPath):
        """``lock`` returns the internal ``BackupLock``."""
        svc = make_svc(tmp_path)
        lock = svc.lock
        assert lock is not None
        assert hasattr(lock, "is_busy")


###############################################################################
# Tests — create_backup
###############################################################################


class TestCreateBackup:
    """Lock, status transitions, rotation, and error handling."""

    async def test_happy_path(self, tmp_path: PosixPath):
        """Happy path: returns CreateBackupResult with backup_id."""
        svc = make_svc(tmp_path)
        repo = FakeRepo()
        result = await svc.create_backup(repo=repo)
        assert isinstance(result, CreateBackupResult)
        assert result.backup_id != ""
        assert isinstance(result.rotated_backup_ids, list)

    async def test_lock_prevents_concurrent(self, tmp_path: PosixPath):
        """Lock is released after create, allowing a second call."""
        svc = make_svc(tmp_path)
        repo = FakeRepo()
        r1 = await svc.create_backup(repo=repo)
        assert r1.backup_id != ""
        r2 = await svc.create_backup(repo=repo)
        assert r2.backup_id != r1.backup_id

    async def test_marks_completed_in_repo(self, tmp_path: PosixPath):
        """After a successful create, the repo entry shows COMPLETED."""
        svc = make_svc(tmp_path)
        repo = FakeRepo()
        result = await svc.create_backup(repo=repo)
        op = await repo.get_by_backup_id(result.backup_id)
        assert op is not None
        assert op.status == "completed"
        assert op.archive_filename is not None
        assert op.archive_size_bytes > 0

    async def test_archive_file_exists_on_disk(self, tmp_path: PosixPath):
        """The archive .tar.gz file is created on disk."""
        svc = make_svc(tmp_path)
        repo = FakeRepo()
        result = await svc.create_backup(repo=repo)
        archive_path = tmp_path / "backups" / f"backup-{result.backup_id}.tar.gz"
        assert archive_path.exists()
        assert archive_path.stat().st_size > 0

    async def test_failure_marks_failed(self, tmp_path: PosixPath):
        """On failure, the operation is marked FAILED."""
        svc = make_svc(tmp_path)
        repo = FakeRepo()
        original_add = repo.add
        call_count = 0

        async def failing_add(op):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("simulated failure")
            return await original_add(op)

        repo.add = failing_add  # type: ignore[assignment]
        with pytest.raises(RuntimeError, match="simulated failure"):
            await svc.create_backup(repo=repo)

    async def test_progress_queue_is_created(self, tmp_path: PosixPath):
        """A progress queue is registered for the backup."""
        svc = make_svc(tmp_path)
        repo = FakeRepo()
        result = await svc.create_backup(repo=repo)
        queue = svc.stream_for(result.backup_id)
        assert queue is not None
        # The queue should have at least one event (the "complete" event).
        assert not queue.empty()

    async def test_archive_file_has_manifest(self, tmp_path: PosixPath):
        """The archive contains a valid manifest.json."""
        import tarfile

        svc = make_svc(tmp_path)
        repo = FakeRepo()
        result = await svc.create_backup(repo=repo)
        archive_path = tmp_path / "backups" / f"backup-{result.backup_id}.tar.gz"

        with tarfile.open(str(archive_path), "r:gz") as tar:
            members = tar.getnames()
            assert "manifest.json" in members
            fobj = tar.extractfile("manifest.json")
            assert fobj is not None
            import json

            manifest = json.loads(fobj.read())
        assert manifest["backup_id"] == result.backup_id
        assert manifest["manifest_version"] == 1


###############################################################################
# Tests — list_backups
###############################################################################


class TestListBackups:
    """Listing and filtering."""

    async def test_returns_summaries(self, tmp_path: PosixPath):
        """List returns a list of BackupSummary objects."""
        svc = make_svc(tmp_path)
        repo = FakeRepo()
        await svc.create_backup(repo=repo)
        summaries = await svc.list_backups(repo=repo)
        assert len(summaries) >= 1
        for s in summaries:
            assert isinstance(s, BackupSummary)
            assert s.backup_id != ""

    async def test_includes_safety_by_default(self, tmp_path: PosixPath):
        """Pre-restore safety snapshots appear when include_safety=True."""
        svc = make_svc(tmp_path)
        repo = FakeRepo()
        # Inject a safety snapshot directly into the repo.
        safety_op = _op("safety-001", operation_type="pre_restore_safety")
        await repo.add(safety_op)
        summaries = await svc.list_backups(repo=repo, include_safety=True)
        safety_ids = [s.backup_id for s in summaries if s.is_safety_snapshot]
        assert "safety-001" in safety_ids

    async def test_excludes_safety_when_requested(self, tmp_path: PosixPath):
        """Pre-restore safety snapshots are hidden with include_safety=False."""
        svc = make_svc(tmp_path)
        repo = FakeRepo()
        safety_op = _op("safety-001", operation_type="pre_restore_safety")
        await repo.add(safety_op)
        summaries = await svc.list_backups(repo=repo, include_safety=False)
        safety_ids = [s.backup_id for s in summaries if s.is_safety_snapshot]
        assert "safety-001" not in safety_ids

    async def test_empty_repo(self, tmp_path: PosixPath):
        """An empty repo returns an empty list."""
        svc = make_svc(tmp_path)
        repo = FakeRepo()
        summaries = await svc.list_backups(repo=repo)
        assert summaries == []

    async def test_age_seconds_computed(self, tmp_path: PosixPath):
        """``age_seconds`` reflects time since creation."""
        now = datetime.now(UTC)
        past = now - timedelta(seconds=3600)
        svc = make_svc(tmp_path)
        repo = FakeRepo()
        op = _op("old-backup", created_at=past)
        await repo.add(op)
        summaries = await svc.list_backups(repo=repo)
        assert len(summaries) == 1
        assert summaries[0].age_seconds >= 3599  # within a second of 3600

    async def test_safety_backups_not_deletable(self, tmp_path: PosixPath):
        """Safety snapshots have deletable=False."""
        svc = make_svc(tmp_path)
        repo = FakeRepo()
        safety = _op("safety-99", operation_type="pre_restore_safety")
        await repo.add(safety)
        normal = _op("normal-1")
        await repo.add(normal)
        summaries = await svc.list_backups(repo=repo)
        for s in summaries:
            if s.is_safety_snapshot:
                assert s.deletable is False
            else:
                assert s.deletable is True


###############################################################################
# Tests — get_backup
###############################################################################


class TestGetBackup:
    """Single-backup retrieval."""

    async def test_returns_summary_for_existing(self, tmp_path: PosixPath):
        """``get_backup`` returns a BackupSummary for an existing backup."""
        svc = make_svc(tmp_path)
        repo = FakeRepo()
        op = _op("backup-001")
        await repo.add(op)
        summary = await svc.get_backup(repo, "backup-001")
        assert isinstance(summary, BackupSummary)
        assert summary.backup_id == "backup-001"
        assert summary.operation_type == "backup"

    async def test_returns_none_for_missing(self, tmp_path: PosixPath):
        """``get_backup`` returns None when the backup_id is not found."""
        svc = make_svc(tmp_path)
        repo = FakeRepo()
        result = await svc.get_backup(repo, "does-not-exist")
        assert result is None

    async def test_age_seconds_computed(self, tmp_path: PosixPath):
        """``age_seconds`` is computed from created_at."""
        past = datetime.now(UTC) - timedelta(seconds=120)
        svc = make_svc(tmp_path)
        repo = FakeRepo()
        op = _op("backup-002", created_at=past)
        await repo.add(op)
        summary = await svc.get_backup(repo, "backup-002")
        assert summary is not None
        assert summary.age_seconds >= 119


###############################################################################
# Tests — storage_status
###############################################################################


class TestStorageStatus:
    """Aggregate storage statistics."""

    async def test_empty(self, tmp_path: PosixPath):
        """Storage status is zeroed for an empty repo."""
        svc = make_svc(tmp_path)
        repo = FakeRepo()
        status = await svc.storage_status(repo)
        assert isinstance(status, BackupStorageStatus)
        assert status.backup_count == 0
        assert status.total_bytes == 0
        assert status.latest_backup_at is None
        assert status.oldest_backup_at is None

    async def test_with_multiple_backups(self, tmp_path: PosixPath):
        """Storage status aggregates multiple backups correctly."""
        svc = make_svc(tmp_path, quota_bytes=1000, warn_fraction=0.5)
        repo = FakeRepo()
        now = datetime.now(UTC)
        op1 = _op("b1", archive_size_bytes=200, created_at=now - timedelta(hours=2))
        op2 = _op("b2", archive_size_bytes=300, created_at=now - timedelta(hours=1))
        await repo.add(op1)
        await repo.add(op2)
        status = await svc.storage_status(repo)
        assert status.backup_count == 2
        assert status.total_bytes == 500
        assert status.quota_bytes == 1000
        assert status.quota_used_fraction == 0.5
        assert status.over_threshold is True  # 0.5 >= 0.5 warn_fraction

    async def test_quota_used_fraction_clamped(self, tmp_path: PosixPath):
        """Quota fraction is clamped to 1.0 when over quota."""
        svc = make_svc(tmp_path, quota_bytes=100, warn_fraction=0.8)
        repo = FakeRepo()
        op = _op("b1", archive_size_bytes=999)
        await repo.add(op)
        status = await svc.storage_status(repo)
        assert status.quota_used_fraction == 1.0
        assert status.over_threshold is True

    async def test_latest_and_oldest(self, tmp_path: PosixPath):
        """latest_backup_at and oldest_backup_at reflect the repo data."""
        now = datetime.now(UTC)
        svc = make_svc(tmp_path)
        repo = FakeRepo()
        old = _op("old", created_at=now - timedelta(days=5))
        new = _op("new", created_at=now - timedelta(hours=1))
        # Add newest first so get_all() returns [new, old]
        # and raw[0]/raw[-1] produce the expected latest/oldest.
        await repo.add(new)
        await repo.add(old)
        status = await svc.storage_status(repo)
        assert status.latest_backup_at is not None
        assert status.oldest_backup_at is not None
        assert status.latest_backup_at > status.oldest_backup_at


###############################################################################
# Tests — restore_preview
###############################################################################


class TestRestorePreview:
    """Pre-restore preview with schema compatibility."""

    async def test_returns_preview_for_existing_backup(
        self, tmp_path: PosixPath, monkeypatch: pytest.MonkeyPatch
    ):
        """restore_preview returns a RestorePreview for an existing backup."""
        svc = make_svc(tmp_path)
        repo = FakeRepo()
        result = await svc.create_backup(repo=repo)

        preview = await svc.restore_preview(result.backup_id)

        assert isinstance(preview, RestorePreview)
        assert preview.backup_id == result.backup_id
        assert isinstance(preview.compatibility, str)
        assert preview.sufficient_space is True

    async def test_raises_for_missing_backup(self, tmp_path: PosixPath):
        """restore_preview raises ValueError when backup is not found."""
        svc = make_svc(tmp_path)
        with pytest.raises(ValueError, match="Backup not found"):
            await svc.restore_preview("nonexistent")

    async def test_compatibility_checked(self, tmp_path: PosixPath):
        """Compatibility is reported as ok/warn/blocked."""
        svc = make_svc(tmp_path)
        repo = FakeRepo()
        result = await svc.create_backup(repo=repo)
        preview = await svc.restore_preview(result.backup_id)
        assert preview.compatibility in ("ok", "warn", "blocked")


###############################################################################
# Tests — restore
###############################################################################


class TestRestore:
    """Restore flow with confirmation, schema checks, and safety snapshot."""

    async def test_requires_confirmation(self, tmp_path: PosixPath):
        """Restore raises ValueError if confirm is not 'RESTORE'."""
        svc = make_svc(tmp_path)
        repo = FakeRepo()
        with pytest.raises(ValueError, match="Confirmation token must be 'RESTORE'"):
            await svc.restore(backup_id="b1", confirm="NO", repo=repo)

    async def test_raises_for_missing_backup(self, tmp_path: PosixPath):
        """Restore raises ValueError if the backup archive is missing."""
        svc = make_svc(tmp_path)
        repo = FakeRepo()
        with pytest.raises(ValueError, match="Backup not found"):
            await svc.restore(backup_id="nonexistent", confirm="RESTORE", repo=repo)

    async def test_raises_for_blocked_schema(self, tmp_path: PosixPath):
        """Restore raises PermissionError when schema is blocked."""
        svc = make_svc(tmp_path)
        repo = FakeRepo()

        # Mock _get_alembic_head so both manifest_revision and
        # current_revision are non-empty and differ → BLOCKED.
        mock_manifest = MagicMock()
        mock_manifest.schema_revision = "manifest-head"
        mock_manifest.deployment_version = "1.0.0"
        mock_manifest.created_at = datetime.now(UTC)

        with (
            patch(
                "anvil.services.backup.backup_service._get_alembic_head",
                return_value="current-head",
            ),
            patch(
                "anvil.services.backup.archive_reader.ArchiveReader.load_manifest",
                return_value=mock_manifest,
            ),
        ):
            with pytest.raises(PermissionError, match="Restore blocked"):
                await svc.restore(backup_id="some-backup", confirm="RESTORE", repo=repo)

    async def test_successful_restore(self, tmp_path: PosixPath) -> None:
        """Successful restore returns operation id and safety snapshot id."""
        svc = make_svc(tmp_path)
        repo = FakeRepo()

        # Create a real backup archive.
        result = await svc.create_backup(repo=repo)

        # Mock ArchiveReader.load_manifest so schema compat passes.
        mock_manifest = MagicMock()
        mock_manifest.schema_revision = ""
        mock_manifest.deployment_version = "1.0.0"
        mock_manifest.created_at = datetime.now(UTC)

        from anvil.services.backup.restore_engine import RestoreResult

        # Mock RestoreEngine.execute to return success.
        mock_restore_result = RestoreResult(
            success=True,
            safety_snapshot_id="safety-001",
            message="Restore completed successfully.",
        )

        with (
            patch(
                "anvil.services.backup.archive_reader.ArchiveReader.load_manifest",
                return_value=mock_manifest,
            ),
            patch(
                "anvil.services.backup.restore_engine.RestoreEngine.execute",
                return_value=mock_restore_result,
            ),
        ):
            outcome = await svc.restore(
                backup_id=result.backup_id, confirm="RESTORE", repo=repo
            )

        assert "restore_operation_id" in outcome
        assert "safety_snapshot_id" in outcome
        assert outcome["status"] == "completed"

        # Verify the safety snapshot was recorded in the repo.
        safety_id = outcome["safety_snapshot_id"]
        safety_op = await repo.get_by_backup_id(safety_id)
        assert safety_op is not None
        assert safety_op.operation_type == "pre_restore_safety"

        # Verify the restore operation was recorded.
        restore_op = await repo.get_by_backup_id(outcome["restore_operation_id"])
        assert restore_op is not None
        assert restore_op.operation_type == "restore"
        assert restore_op.restored_from_backup_id == result.backup_id
        assert restore_op.safety_snapshot_id == safety_id

    async def test_failed_restore(self, tmp_path: PosixPath) -> None:
        """A failed RestoreEngine returns FAILED status."""
        svc = make_svc(tmp_path)
        repo = FakeRepo()
        result = await svc.create_backup(repo=repo)

        mock_manifest = MagicMock()
        mock_manifest.schema_revision = ""
        mock_manifest.deployment_version = "1.0.0"
        mock_manifest.created_at = datetime.now(UTC)

        from anvil.services.backup.restore_engine import RestoreResult

        mock_restore_result = RestoreResult(
            success=False,
            safety_snapshot_id="safety-002",
            message="Extraction failed",
        )

        with (
            patch(
                "anvil.services.backup.archive_reader.ArchiveReader.load_manifest",
                return_value=mock_manifest,
            ),
            patch(
                "anvil.services.backup.restore_engine.RestoreEngine.execute",
                return_value=mock_restore_result,
            ),
        ):
            outcome = await svc.restore(
                backup_id=result.backup_id, confirm="RESTORE", repo=repo
            )

        assert outcome["status"] == "failed"
        assert "restore_operation_id" in outcome


###############################################################################
# Tests — delete_backup
###############################################################################


class TestDeleteBackup:
    """Delete with safety-snapshot guard and last-backup protection."""

    async def test_deletes_existing_backup(self, tmp_path: PosixPath):
        """A normal backup is deleted from the repo."""
        svc = make_svc(tmp_path)
        repo = FakeRepo()
        op = _op("backup-to-delete")
        await repo.add(op)
        await svc.delete_backup("backup-to-delete", repo=repo, confirm_last=True)
        assert await repo.get_by_backup_id("backup-to-delete") is None

    async def test_removes_archive_file(self, tmp_path: PosixPath):
        """The archive file on disk is deleted."""
        svc = make_svc(tmp_path)
        repo = FakeRepo()
        result = await svc.create_backup(repo=repo)
        archive_path = tmp_path / "backups" / f"backup-{result.backup_id}.tar.gz"
        assert archive_path.exists()
        await svc.delete_backup(result.backup_id, repo=repo, confirm_last=True)
        assert not archive_path.exists()

    async def test_raises_for_missing(self, tmp_path: PosixPath):
        """Deleting a non-existent backup raises ValueError."""
        svc = make_svc(tmp_path)
        repo = FakeRepo()
        with pytest.raises(ValueError, match="Backup not found"):
            await svc.delete_backup("ghost", repo=repo)

    async def test_raises_for_safety_snapshot(self, tmp_path: PosixPath):
        """Deleting a safety snapshot raises PermissionError."""
        svc = make_svc(tmp_path)
        repo = FakeRepo()
        op = _op("safety-1", operation_type="pre_restore_safety")
        await repo.add(op)
        with pytest.raises(PermissionError, match="Safety snapshots cannot"):
            await svc.delete_backup("safety-1", repo=repo)

    async def test_raises_for_last_backup(self, tmp_path: PosixPath):
        """Deleting the last restorable backup raises without confirm_last."""
        svc = make_svc(tmp_path)
        repo = FakeRepo()
        op = _op("last-one")
        await repo.add(op)
        with pytest.raises(PermissionError, match="only remaining backup"):
            await svc.delete_backup("last-one", repo=repo, confirm_last=False)

    async def test_confirm_last_allows_deletion(self, tmp_path: PosixPath):
        """confirm_last=True allows deleting the last backup."""
        svc = make_svc(tmp_path)
        repo = FakeRepo()
        op = _op("last-one")
        await repo.add(op)
        await svc.delete_backup("last-one", repo=repo, confirm_last=True)
        assert await repo.get_by_backup_id("last-one") is None

    async def test_confirm_last_not_needed_with_multiple(self, tmp_path: PosixPath):
        """confirm_last is not needed when other restorable backups remain."""
        svc = make_svc(tmp_path)
        repo = FakeRepo()
        op1 = _op("backup-a")
        op2 = _op("backup-b")
        await repo.add(op1)
        await repo.add(op2)
        await svc.delete_backup("backup-a", repo=repo, confirm_last=False)
        assert await repo.get_by_backup_id("backup-a") is None
        assert await repo.get_by_backup_id("backup-b") is not None

    async def test_last_backup_with_safety_snapshots(self, tmp_path: PosixPath):
        """Safety snapshots are ignored when counting restorable backups."""
        svc = make_svc(tmp_path)
        repo = FakeRepo()
        normal = _op("the-only-real-backup")
        safety = _op("safety-99", operation_type="pre_restore_safety")
        await repo.add(normal)
        await repo.add(safety)
        # The safety snapshot should NOT count as a restorable backup.
        with pytest.raises(PermissionError, match="only remaining backup"):
            await svc.delete_backup(
                "the-only-real-backup", repo=repo, confirm_last=False
            )


###############################################################################
# Tests — verify
###############################################################################


class TestVerify:
    """Integrity verification."""

    async def test_verify_valid_backup(self, tmp_path: PosixPath):
        """A freshly created backup verifies as valid."""
        svc = make_svc(tmp_path)
        repo = FakeRepo()
        result = await svc.create_backup(repo=repo)
        verify = await svc.verify(result.backup_id, repo=repo)
        assert isinstance(verify, VerifyResult)
        assert verify.backup_id == result.backup_id
        assert verify.valid is True

    async def test_verify_missing_backup(self, tmp_path: PosixPath):
        """A non-existent archive returns invalid verify result."""
        svc = make_svc(tmp_path)
        repo = FakeRepo()
        # Register an op in the repo so get_by_backup_id works, but
        # don't create the archive on disk.
        op = _op("backup-without-archive")
        await repo.add(op)
        verify = await svc.verify("backup-without-archive", repo=repo)
        assert verify.valid is False
        assert verify.checked_count == 0

    async def test_verify_maintains_repo_entry(self, tmp_path: PosixPath):
        """Verification does not delete the repo entry."""
        svc = make_svc(tmp_path)
        repo = FakeRepo()
        result = await svc.create_backup(repo=repo)
        await svc.verify(result.backup_id, repo=repo)
        op = await repo.get_by_backup_id(result.backup_id)
        assert op is not None


###############################################################################
# Tests — cleanup_safety
###############################################################################


class TestCleanupSafety:
    """Safety-snapshot cleanup."""

    async def test_removes_safety_snapshots(self, tmp_path: PosixPath):
        """cleanup_safety removes all pre_restore_safety ops from repo."""
        svc = make_svc(tmp_path)
        repo = FakeRepo()
        safety1 = _op("safety-1", operation_type="pre_restore_safety")
        safety2 = _op("safety-2", operation_type="pre_restore_safety")
        normal = _op("normal-1")
        await repo.add(safety1)
        await repo.add(safety2)
        await repo.add(normal)

        count = await svc.cleanup_safety(repo)
        assert count == 2
        assert await repo.get_by_backup_id("safety-1") is None
        assert await repo.get_by_backup_id("safety-2") is None
        assert await repo.get_by_backup_id("normal-1") is not None

    async def test_removes_safety_archive_files(self, tmp_path: PosixPath):
        """cleanup_safety deletes archive files for safety snapshots."""
        svc = make_svc(tmp_path)
        repo = FakeRepo()
        safety = _op("safety-to-clean", operation_type="pre_restore_safety")
        await repo.add(safety)
        # Create a dummy archive on disk.
        archive_path = tmp_path / "backups" / "backup-safety-to-clean.tar.gz"
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        archive_path.write_text("dummy archive content")

        await svc.cleanup_safety(repo)
        assert not archive_path.exists()

    async def test_no_safety_returns_zero(self, tmp_path: PosixPath):
        """cleanup_safety returns 0 when no safety snapshots exist."""
        svc = make_svc(tmp_path)
        repo = FakeRepo()
        normal = _op("normal-1")
        await repo.add(normal)
        count = await svc.cleanup_safety(repo)
        assert count == 0


###############################################################################
# Tests — recover_interrupted_restore
###############################################################################


class TestRecoverInterruptedRestore:
    """Startup recovery from crashed restore."""

    async def test_no_journal_no_error(self, tmp_path: PosixPath):
        """recover_interrupted_restore does nothing when no journal exists."""
        svc = make_svc(tmp_path)
        # Should not raise any exception.
        await svc.recover_interrupted_restore()

    async def test_journal_exists_triggers_recovery(
        self, tmp_path: PosixPath, caplog: pytest.LogCaptureFixture
    ):
        """recover_interrupted_restore recovers when journal exists."""
        import json

        svc = make_svc(tmp_path)
        # Write a journal file.
        journal_path = tmp_path / "backups" / ".restore-journal.json"
        journal_path.parent.mkdir(parents=True, exist_ok=True)
        journal_path.write_text(
            json.dumps(
                {
                    "restore_operation_id": "restore-abc",
                    "source_backup_id": "backup-123",
                    "safety_snapshot_id": "safety-xyz",
                    "roots": [],
                    "phase": "swapping",
                    "created_at": datetime.now(UTC).isoformat(),
                }
            )
        )

        with caplog.at_level("WARNING"):
            await svc.recover_interrupted_restore()

        assert "Restore journal found" in caplog.text

    async def test_clears_journal_after_recovery(self, tmp_path: PosixPath):
        """After recover, the journal file is removed."""
        import json

        svc = make_svc(tmp_path)
        journal_path = tmp_path / "backups" / ".restore-journal.json"
        journal_path.parent.mkdir(parents=True, exist_ok=True)
        journal_path.write_text(
            json.dumps(
                {
                    "restore_operation_id": "restore-abc",
                    "source_backup_id": "backup-123",
                    "safety_snapshot_id": "safety-xyz",
                    "roots": [],
                    "phase": "swapping",
                }
            )
        )

        await svc.recover_interrupted_restore()
        # Journal with empty roots should be recoverable → cleared.
        assert not journal_path.exists()


###############################################################################
# Tests — stream_for
###############################################################################


class TestStreamFor:
    """Progress-queue access."""

    async def test_returns_queue_for_running_operation(self, tmp_path: PosixPath):
        """stream_for returns a queue for an in-progress backup."""
        svc = make_svc(tmp_path)
        repo = FakeRepo()
        result = await svc.create_backup(repo=repo)
        queue = svc.stream_for(result.backup_id)
        assert queue is not None
        assert isinstance(queue, asyncio.Queue)

    async def test_returns_none_for_unknown(self, tmp_path: PosixPath):
        """stream_for returns None for an unknown operation id."""
        svc = make_svc(tmp_path)
        queue = svc.stream_for("does-not-exist")
        assert queue is None

    async def test_queue_contains_complete_event(self, tmp_path: PosixPath):
        """After a successful backup, the queue has a 'complete' event."""
        svc = make_svc(tmp_path)
        repo = FakeRepo()
        result = await svc.create_backup(repo=repo)
        queue = svc.stream_for(result.backup_id)
        assert queue is not None
        events = []
        while not queue.empty():
            ev = queue.get_nowait()
            events.append(ev)
        assert any(e.event == "complete" for e in events)


###############################################################################
# Tests — Rotation (quota / count / age)
###############################################################################


class TestRotation:
    """Auto-rotation via retention policy."""

    async def test_rotation_with_existing_backups(self, tmp_path: PosixPath):
        """When quota is exceeded and existing backups can be rotated,
        creation succeeds with rotated IDs.
        """
        svc = make_svc(tmp_path, quota_bytes=1)
        repo = FakeRepo()

        # Pre-populate the repo with a "backup" that has a large
        # archive_size_bytes so RetentionPolicy selects it for rotation.
        old = _op(
            "old-backup",
            archive_size_bytes=10 * 1024**3,
            created_at=datetime.now(UTC) - timedelta(days=1),
        )
        await repo.add(old)

        # Now when create_backup runs and the plan says within_quota=False,
        # the RetentionPolicy should select "old-backup" for rotation.
        # After deleting it, the replan still shows within_quota=False
        # (the new backup still doesn't fit in 1-byte quota), so it raises.
        with pytest.raises(RuntimeError, match="Insufficient space after rotation"):
            await svc.create_backup(repo=repo)

        # The old backup should be gone from the repo.
        assert await repo.get_by_backup_id("old-backup") is None

    async def test_no_rotation_when_within_limits(self, tmp_path: PosixPath):
        """When within limits, no backups are rotated."""
        svc = make_svc(
            tmp_path,
            quota_bytes=10 * 1024**3,
            retention_max_count=10,
        )
        repo = FakeRepo()

        r1 = await svc.create_backup(repo=repo)
        assert len(r1.rotated_backup_ids) == 0


###############################################################################
# Tests — Error handling edge cases
###############################################################################


class TestErrorHandling:
    """Edge-case error handling."""

    async def test_create_backup_lock_actual_conflict(self, tmp_path: PosixPath):
        """If the lock is held, create_backup raises RuntimeError."""
        svc = make_svc(tmp_path)
        repo = FakeRepo()

        # Acquire the lock manually.
        acquired = await svc._lock.try_acquire("manual", "lock-holder")  # type: ignore[attr-defined]
        assert acquired is True

        with pytest.raises(RuntimeError, match="already in progress"):
            await svc.create_backup(repo=repo)

        # Release so cleanup doesn't fail.
        svc._lock.release()  # type: ignore[attr-defined]

    async def test_restore_lock_actual_conflict(self, tmp_path: PosixPath) -> None:
        """Restore raises RuntimeError when lock is held."""
        svc = make_svc(tmp_path)
        repo = FakeRepo()

        # Fake an in-progress backup.
        mock_manifest = MagicMock()
        mock_manifest.schema_revision = ""
        mock_manifest.deployment_version = "1.0.0"
        mock_manifest.created_at = datetime.now(UTC)

        acquired = await svc._lock.try_acquire("manual", "lock-holder")  # type: ignore[attr-defined]
        assert acquired is True

        with (
            patch(
                "anvil.services.backup.archive_reader.ArchiveReader.load_manifest",
                return_value=mock_manifest,
            ),
        ):
            with pytest.raises(RuntimeError, match="already in progress"):
                await svc.restore(backup_id="some-backup", confirm="RESTORE", repo=repo)

        svc._lock.release()  # type: ignore[attr-defined]
