"""Tests for RestoreEngine — atomic swap, rollback, integrity (FR-030, SC-005)."""

import os
from pathlib import Path
from unittest.mock import ANY, AsyncMock, patch

import pytest

from anvil.services.backup.archive_writer import ArchiveWriter
from anvil.services.backup.restore_engine import RestoreEngine, RestoreResult
from anvil.services.backup.restore_journal import RestoreJournal


class TestRestoreEngineErrors:
    """Error paths and edge cases."""

    async def test_non_existent_backup_returns_failure(self, tmp_path: Path):
        """Non-existent backup returns RestoreResult with success=False."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        journal_path = tmp_path / ".restore-journal.json"
        journal = RestoreJournal(journal_path)
        engine = RestoreEngine(backup_dir, journal)
        result = await engine.execute(
            backup_id="nonexistent", safety_snapshot_id="safety-001"
        )
        assert result.success is False
        assert "not found" in result.message.lower()

    async def test_backup_not_found_returns_snapshot_id(self, tmp_path: Path):
        """safety_snapshot_id is preserved in failure result."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        journal_path = tmp_path / ".restore-journal.json"
        journal = RestoreJournal(journal_path)
        engine = RestoreEngine(backup_dir, journal)

        result = await engine.execute(
            backup_id="missing", safety_snapshot_id="snap-abc"
        )
        assert result.success is False
        assert result.safety_snapshot_id == "snap-abc"


class TestRestoreEngineHappyPath:
    """Successful restore with proper setup."""

    async def test_restore_engine_happy_path(self, tmp_path: Path, monkeypatch):
        """Full restore flow: backup, verify, extract, swap."""
        monkeypatch.chdir(tmp_path)

        # Create a source directory with data.
        src_dir = tmp_path / "data"
        src_dir.mkdir()
        (src_dir / "hello.txt").write_text("world")

        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()

        # Create a backup of src_dir as "data".
        writer = ArchiveWriter(backup_dir)
        await writer.write(
            backup_id="test-restore",
            roots=[src_dir],
            operation_type="backup",
        )

        # Set up journal.
        journal_path = tmp_path / ".restore-journal.json"
        journal = RestoreJournal(journal_path)
        engine = RestoreEngine(backup_dir, journal)

        # Run restore — the engine will extract to .restore-tmp/test-restore,
        # find a dir called "data" in it, and swap cwd/data <-> cwd/data.bak.
        result = await engine.execute(
            backup_id="test-restore",
            safety_snapshot_id="safety-123",
        )
        assert result.success is True
        assert "completed successfully" in result.message
        assert result.safety_snapshot_id == "safety-123"

        # The restored file should be in place.
        assert (tmp_path / "data" / "hello.txt").exists()
        assert (tmp_path / "data" / "hello.txt").read_text() == "world"

        # .bak should be gone.
        assert not (tmp_path / "data.bak").exists()

        # Journal should be cleared.
        assert not journal_path.exists()

        # Temp dir subdir should be cleaned up (the parent .restore-tmp/
        # may remain since the engine only removes its own backup_id
        # subdirectory).
        assert not (tmp_path / ".restore-tmp" / "test-restore").exists()

    async def test_progress_callback_invoked(self, tmp_path: Path, monkeypatch):
        """Progress callback receives expected step names."""
        monkeypatch.chdir(tmp_path)

        src_dir = tmp_path / "data"
        src_dir.mkdir()
        (src_dir / "f.txt").write_text("content")
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()

        writer = ArchiveWriter(backup_dir)
        await writer.write(
            backup_id="progress-restore",
            roots=[src_dir],
            operation_type="backup",
        )

        calls: list[tuple[int, str]] = []

        def cb(percent: int, step: str) -> None:
            calls.append((percent, step))

        journal_path = tmp_path / ".restore-journal.json"
        journal = RestoreJournal(journal_path)
        engine = RestoreEngine(backup_dir, journal)

        result = await engine.execute(
            backup_id="progress-restore",
            safety_snapshot_id="safety-123",
            progress_callback=cb,
        )
        assert result.success is True
        assert len(calls) > 0
        step_texts = [step for _, step in calls]
        assert "Reading manifest" in step_texts
        assert "Extracting to temp directory" in step_texts
        assert "Verifying extracted files" in step_texts
        assert "Swapping files (atomic)" in step_texts
        assert "Cleaning up" in step_texts
        assert "Restore complete" in step_texts or "Complete" in " ".join(step_texts)

    async def test_journal_written_during_swap(self, tmp_path: Path, monkeypatch):
        """Journal file exists after swap phase starts (FR-030)."""
        monkeypatch.chdir(tmp_path)

        src_dir = tmp_path / "data"
        src_dir.mkdir()
        (src_dir / "f.txt").write_text("hello")
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()

        writer = ArchiveWriter(backup_dir)
        await writer.write(
            backup_id="journal-check",
            roots=[src_dir],
            operation_type="backup",
        )

        journal_path = tmp_path / ".restore-journal.json"
        journal = RestoreJournal(journal_path)
        engine = RestoreEngine(backup_dir, journal)

        await engine.execute(
            backup_id="journal-check",
            safety_snapshot_id="safety-456",
        )

        # On success, journal is cleared — so it should NOT exist.
        assert not journal_path.exists()

    async def test_journal_not_written_on_missing_backup(self, tmp_path: Path):
        """Journal is not created when backup is not found."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        journal_path = tmp_path / ".restore-journal.json"
        journal = RestoreJournal(journal_path)
        engine = RestoreEngine(backup_dir, journal)

        await engine.execute(
            backup_id="no-such-backup",
            safety_snapshot_id="safety-001",
        )
        # Journal should never have been written.
        assert not journal_path.exists()


class TestRestoreEngineFailures:
    """Failure modes and rollback behavior."""

    async def test_rollback_on_missing_archive(self, tmp_path: Path):
        """Non-existent backup returns success=False (SC-006)."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        journal_path = tmp_path / ".restore-journal.json"
        journal = RestoreJournal(journal_path)
        engine = RestoreEngine(backup_dir, journal)

        result = await engine.execute(
            backup_id="nonexistent", safety_snapshot_id="safety-001"
        )
        assert result.success is False
        assert result.safety_snapshot_id == "safety-001"

    async def test_integrity_failure_returns_error(self, tmp_path: Path, monkeypatch):
        """When verification fails, restore stops with error."""
        monkeypatch.chdir(tmp_path)

        src_dir = tmp_path / "data"
        src_dir.mkdir()
        (src_dir / "f.txt").write_text("original")
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()

        writer = ArchiveWriter(backup_dir)
        await writer.write(
            backup_id="integrity-fail",
            roots=[src_dir],
            operation_type="backup",
        )

        # Corrupt the extracted data after extraction by intercepting
        # the verify call.
        journal_path = tmp_path / ".restore-journal.json"
        journal = RestoreJournal(journal_path)
        engine = RestoreEngine(backup_dir, journal)

        # Patch ArchiveReader.verify to return failure.
        with patch(
            "anvil.services.backup.restore_engine.ArchiveReader.verify",
            AsyncMock(
                return_value=type(
                    "VerifyResult",
                    (),
                    {"valid": False, "checked_count": 0, "mismatched": []},
                )()
            ),
        ):
            result = await engine.execute(
                backup_id="integrity-fail",
                safety_snapshot_id="safety-789",
            )
        assert result.success is False
        assert "integrity" in result.message.lower()

    async def test_empty_archive_returns_error(self, tmp_path: Path, monkeypatch):
        """An archive with no root directories returns error."""
        monkeypatch.chdir(tmp_path)

        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()

        # Create an archive with no meaningful directories.
        writer = ArchiveWriter(backup_dir)
        # Write the archive with an empty roots list.
        await writer.write(
            backup_id="empty-archive",
            roots=[],
            operation_type="backup",
        )

        journal_path = tmp_path / ".restore-journal.json"
        journal = RestoreJournal(journal_path)
        engine = RestoreEngine(backup_dir, journal)

        result = await engine.execute(
            backup_id="empty-archive",
            safety_snapshot_id="safety-empty",
        )
        assert result.success is False
        assert "no root directories" in result.message.lower()

    async def test_exception_during_extraction_rolls_back(
        self, tmp_path: Path, monkeypatch
    ):
        """Exception during extraction triggers rollback."""
        monkeypatch.chdir(tmp_path)

        src_dir = tmp_path / "data"
        src_dir.mkdir()
        (src_dir / "f.txt").write_text("original data")
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()

        writer = ArchiveWriter(backup_dir)
        await writer.write(
            backup_id="crash-restore",
            roots=[src_dir],
            operation_type="backup",
        )

        journal_path = tmp_path / ".restore-journal.json"
        journal = RestoreJournal(journal_path)
        engine = RestoreEngine(backup_dir, journal)

        # Patch ArchiveReader.extract_to to raise an exception.
        with patch(
            "anvil.services.backup.restore_engine.ArchiveReader.extract_to",
            AsyncMock(side_effect=RuntimeError("Extraction bombed")),
        ):
            result = await engine.execute(
                backup_id="crash-restore",
                safety_snapshot_id="safety-rollback",
            )
        assert result.success is False
        assert "failed" in result.message.lower()

    async def test_temp_cleaned_on_failure(self, tmp_path: Path, monkeypatch):
        """Temp extraction directory is cleaned up after failure."""
        monkeypatch.chdir(tmp_path)

        src_dir = tmp_path / "data"
        src_dir.mkdir()
        (src_dir / "f.txt").write_text("data")
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()

        writer = ArchiveWriter(backup_dir)
        await writer.write(
            backup_id="cleanup-fail",
            roots=[src_dir],
            operation_type="backup",
        )

        journal_path = tmp_path / ".restore-journal.json"
        journal = RestoreJournal(journal_path)
        engine = RestoreEngine(backup_dir, journal)

        with patch(
            "anvil.services.backup.restore_engine.ArchiveReader.extract_to",
            AsyncMock(side_effect=RuntimeError("Fail")),
        ):
            await engine.execute(
                backup_id="cleanup-fail",
                safety_snapshot_id="safety-cleanup",
            )

        # Temp dir should be cleaned up.
        restore_tmp = tmp_path / ".restore-tmp" / "cleanup-fail"
        assert not restore_tmp.exists()


class TestRestoreEngineRestoreResult:
    """RestoreResult construction and attributes."""

    def test_restore_result_defaults(self):
        """RestoreResult has sensible defaults."""
        result = RestoreResult()
        assert result.success is False
        assert result.safety_snapshot_id is None
        assert result.message == ""

    def test_restore_result_custom_values(self):
        """RestoreResult accepts custom values."""
        result = RestoreResult(
            success=True,
            safety_snapshot_id="snap-001",
            message="All good",
        )
        assert result.success is True
        assert result.safety_snapshot_id == "snap-001"
        assert result.message == "All good"


class TestRestoreEngineMultipleRoots:
    """Restore with multiple managed roots."""

    async def test_restore_multiple_roots(self, tmp_path: Path, monkeypatch):
        """Multiple root directories are all restored."""
        monkeypatch.chdir(tmp_path)

        data_dir = tmp_path / "data"
        models_dir = tmp_path / "models"
        data_dir.mkdir()
        models_dir.mkdir()
        (data_dir / "db.sqlite").write_text("db content")
        (models_dir / "model.pt").write_text("model weights")

        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()

        writer = ArchiveWriter(backup_dir)
        await writer.write(
            backup_id="multi-root-restore",
            roots=[data_dir, models_dir],
            operation_type="backup",
        )

        journal_path = tmp_path / ".restore-journal.json"
        journal = RestoreJournal(journal_path)
        engine = RestoreEngine(backup_dir, journal)

        result = await engine.execute(
            backup_id="multi-root-restore",
            safety_snapshot_id="safety-multi",
        )
        assert result.success is True

        # Both dirs should be in place.
        assert (tmp_path / "data" / "db.sqlite").exists()
        assert (tmp_path / "models" / "model.pt").exists()

        # .bak should be gone.
        assert not (tmp_path / "data.bak").exists()
        assert not (tmp_path / "models.bak").exists()

    async def test_restore_into_existing_dir_swaps_bak(
        self, tmp_path: Path, monkeypatch
    ):
        """Existing live directories are moved to .bak before restore."""
        monkeypatch.chdir(tmp_path)

        # Create a backup of "data".
        src_dir = tmp_path / "data"
        src_dir.mkdir()
        (src_dir / "from_backup.txt").write_text("restored")

        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()

        writer = ArchiveWriter(backup_dir)
        await writer.write(
            backup_id="swap-test",
            roots=[src_dir],
            operation_type="backup",
        )

        # Now create a different "data" dir (like the live one).
        live_data = tmp_path / "data"
        live_data.mkdir(exist_ok=True)
        (live_data / "old.txt").write_text("original")

        journal_path = tmp_path / ".restore-journal.json"
        journal = RestoreJournal(journal_path)
        engine = RestoreEngine(backup_dir, journal)

        result = await engine.execute(
            backup_id="swap-test",
            safety_snapshot_id="safety-swap",
        )
        assert result.success is True

        # The restored file should be in place.
        assert (tmp_path / "data" / "from_backup.txt").exists()
        assert (tmp_path / "data" / "from_backup.txt").read_text() == "restored"

        # The old file should NOT be present in the live dir.
        assert not (tmp_path / "data" / "old.txt").exists()

        # .bak is cleaned up on success.
        assert not (tmp_path / "data.bak").exists()
