"""Tests for RestoreJournal — crash-safe recovery marker (FR-030)."""

from pathlib import Path

from anvil.services.backup.restore_journal import RestoreJournal


class TestRestoreJournal:
    """Write, read, clear, and recover behavior."""

    def test_write_and_read(self, tmp_path: Path):
        journal = RestoreJournal(tmp_path / ".restore-journal.json")
        journal.write(
            restore_operation_id="rest-001",
            source_backup_id="backup-123",
            safety_snapshot_id="safety-456",
            roots=["data", "mlruns"],
        )
        data = journal.read()
        assert data is not None
        assert data["restore_operation_id"] == "rest-001"
        assert data["source_backup_id"] == "backup-123"
        assert data["safety_snapshot_id"] == "safety-456"
        assert "roots" in data
        assert journal.exists()

    def test_clear_removes_journal(self, tmp_path: Path):
        journal = RestoreJournal(tmp_path / ".restore-journal.json")
        journal.write(
            restore_operation_id="rest-001",
            source_backup_id="backup-123",
            safety_snapshot_id="safety-456",
            roots=["data"],
        )
        assert journal.exists()
        journal.clear()
        assert not journal.exists()
        assert journal.read() is None

    def test_read_when_no_journal(self, tmp_path: Path):
        journal = RestoreJournal(tmp_path / ".restore-journal.json")
        assert journal.read() is None
        assert not journal.exists()

    def test_recover_no_journal(self, tmp_path: Path):
        journal = RestoreJournal(tmp_path / ".restore-journal.json")
        result = journal.recover()
        assert result["recovered"] is False

    def test_recover_with_bak_files(self, tmp_path: Path):
        live_dir = tmp_path / "data"
        live_dir.mkdir()
        (live_dir / "test.txt").write_text("original")
        bak_dir = tmp_path / "data.bak"
        bak_dir.mkdir()
        (bak_dir / "test.txt").write_text("backup")

        journal = RestoreJournal(tmp_path / ".restore-journal.json")
        journal.write(
            restore_operation_id="rest-001",
            source_backup_id="backup-123",
            safety_snapshot_id="safety-456",
            roots=[str(live_dir)],
        )
        # Simulate crash: live dir is gone, .bak exists
        import shutil
        shutil.rmtree(live_dir)

        result = journal.recover()
        assert result["recovered"] is True
        assert (live_dir / "test.txt").exists()
        assert (live_dir / "test.txt").read_text() == "backup"

    def test_recover_without_bak_falls_back_to_safety(self, tmp_path: Path):
        journal = RestoreJournal(tmp_path / ".restore-journal.json")
        journal.write(
            restore_operation_id="rest-001",
            source_backup_id="backup-123",
            safety_snapshot_id="safety-456",
            roots=["data"],
        )
        result = journal.recover()
        assert result["safety_snapshot_id"] == "safety-456"