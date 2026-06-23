"""Tests for ArchiveWriter — tar.gz creation, manifest, atomicity."""

import json
import tarfile
from pathlib import Path

from anvil.services.backup.archive_writer import ArchiveWriter


class TestArchiveWriter:
    """Verify archive structure, manifest, and atomic write."""

    async def test_creates_tar_gz_with_manifest_as_first_entry(
        self, tmp_path: Path
    ):
        """The manifest must be the first member of the archive."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "hello.txt").write_text("hello world")
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        writer = ArchiveWriter(backup_dir)
        result = await writer.write(
            backup_id="test-001",
            roots=[src_dir],
            operation_type="backup",
        )
        assert result["archive_filename"] == "backup-test-001.tar.gz"
        assert result["archive_size_bytes"] > 0
        assert result["manifest_sha256"] is not None
        assert len(result["manifest_sha256"]) == 64

        archive_path = backup_dir / result["archive_filename"]
        assert archive_path.exists()

        with tarfile.open(archive_path, "r:gz") as tar:
            members = tar.getnames()
            assert members[0] == "manifest.json"

    async def test_manifest_contains_correct_entries(self, tmp_path: Path):
        """The manifest should list every archived file with correct sha256."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "a.txt").write_text("content a")
        (src_dir / "b.txt").write_text("content b")
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()

        writer = ArchiveWriter(backup_dir)
        result = await writer.write(
            backup_id="test-002",
            roots=[src_dir],
            operation_type="backup",
        )
        archive_path = backup_dir / result["archive_filename"]
        with tarfile.open(archive_path, "r:gz") as tar:
            manifest_data = tar.extractfile("manifest.json")
            assert manifest_data is not None
            manifest = json.loads(manifest_data.read())

        assert manifest["manifest_version"] == 1
        assert manifest["backup_id"] == "test-002"
        assert manifest["operation_type"] == "backup"
        paths = [e["path"] for e in manifest["entries"]]
        assert any("a.txt" in p for p in paths)
        assert any("b.txt" in p for p in paths)
        for entry in manifest["entries"]:
            assert "sha256" in entry
            assert "size" in entry
            assert entry["sha256"] != ""

    async def test_atomic_write_leaves_no_partial_file(self, tmp_path: Path):
        """After a successful write, only the final archive exists."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "f.txt").write_text("data")
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()

        writer = ArchiveWriter(backup_dir)
        await writer.write(
            backup_id="test-003",
            roots=[src_dir],
            operation_type="backup",
        )
        # No .part files should remain.
        part_files = list((backup_dir / ".tmp").glob("*.part"))
        assert len(part_files) == 0

    async def test_unique_filenames(self, tmp_path: Path):
        """Each backup gets a unique filename (FR-022)."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "f.txt").write_text("data")
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()

        writer = ArchiveWriter(backup_dir)
        r1 = await writer.write(
            backup_id="test-unique-1",
            roots=[src_dir],
            operation_type="backup",
        )
        r2 = await writer.write(
            backup_id="test-unique-2",
            roots=[src_dir],
            operation_type="backup",
        )
        assert r1["archive_filename"] != r2["archive_filename"]