"""Tests for ArchiveWriter — tar.gz creation, manifest, atomicity."""

import json
import tarfile
from pathlib import Path

from anvil.services.backup.archive_writer import ArchiveWriter


class TestArchiveWriter:
    """Verify archive structure, manifest, and atomic write."""

    async def test_creates_tar_gz_with_manifest_as_first_entry(self, tmp_path: Path):
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

    async def test_with_multiple_roots(self, tmp_path: Path):
        """Archive can include files from multiple root directories."""
        root_a = tmp_path / "root_a"
        root_a.mkdir()
        (root_a / "from_a.txt").write_text("aaa")
        root_b = tmp_path / "root_b"
        root_b.mkdir()
        (root_b / "from_b.txt").write_text("bbb")
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()

        writer = ArchiveWriter(backup_dir)
        result = await writer.write(
            backup_id="multi-root",
            roots=[root_a, root_b],
            operation_type="backup",
        )
        archive_path = backup_dir / result["archive_filename"]
        with tarfile.open(archive_path, "r:gz") as tar:
            names = tar.getnames()
        assert any("from_a.txt" in n for n in names)
        assert any("from_b.txt" in n for n in names)

    async def test_with_operation_type_safety(self, tmp_path: Path):
        """Operation type is recorded in manifest."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "f.txt").write_text("safety check")
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()

        writer = ArchiveWriter(backup_dir)
        result = await writer.write(
            backup_id="safety-001",
            roots=[src_dir],
            operation_type="pre_restore_safety",
        )
        archive_path = backup_dir / result["archive_filename"]
        with tarfile.open(archive_path, "r:gz") as tar:
            manifest = json.loads(tar.extractfile("manifest.json").read())
        assert manifest["operation_type"] == "pre_restore_safety"

    async def test_with_progress_callback(self, tmp_path: Path):
        """Progress callback is invoked during archive creation."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "f.txt").write_text("progress test")
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()

        calls: list[tuple[int, str]] = []

        def cb(percent: int, step: str) -> None:
            calls.append((percent, step))

        writer = ArchiveWriter(backup_dir)
        await writer.write(
            backup_id="progress-001",
            roots=[src_dir],
            operation_type="backup",
            progress_callback=cb,
        )
        assert len(calls) > 0
        # Last call should be 100% / "Complete".
        assert calls[-1] == (100, "Complete")
        # All percentages should be in [0, 100].
        for pct, _step in calls:
            assert 0 <= pct <= 100

    async def test_with_schema_revision(self, tmp_path: Path):
        """Schema revision is stored in result metadata and manifest."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "f.txt").write_text("schema rev")
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()

        writer = ArchiveWriter(backup_dir)
        result = await writer.write(
            backup_id="schema-test",
            roots=[src_dir],
            operation_type="backup",
            schema_revision="abc123def456",
        )
        assert result["schema_revision"] == "abc123def456"
        assert result["deployment_version"] != ""

        archive_path = backup_dir / result["archive_filename"]
        with tarfile.open(archive_path, "r:gz") as tar:
            manifest = json.loads(tar.extractfile("manifest.json").read())
        assert manifest["schema_revision"] == "abc123def456"

    async def test_excludes_backup_directory(self, tmp_path: Path):
        """Files inside the backup directory are excluded from the archive."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "legit.txt").write_text("keep me")
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        # Put a file inside the backup dir — it should be excluded.
        (backup_dir / "internal.txt").write_text("drop me")

        writer = ArchiveWriter(backup_dir)
        result = await writer.write(
            backup_id="exclude-test",
            roots=[src_dir, backup_dir],
            operation_type="backup",
        )
        archive_path = backup_dir / result["archive_filename"]
        with tarfile.open(archive_path, "r:gz") as tar:
            names = tar.getnames()
        assert any("legit.txt" in n for n in names)
        # File inside the backup dir should NOT appear in the archive.
        assert not any("internal.txt" in n for n in names)
        # The backup archive itself should not be inside its own archive.
        assert not any(result["archive_filename"] in n for n in names)

    async def test_archive_path_relative_to_cwd(self, tmp_path: Path):
        """Static _archive_path returns relative path when under cwd."""
        # Simulate a path under cwd.
        cwd = tmp_path
        child = tmp_path / "subdir" / "file.txt"
        child.parent.mkdir(parents=True)
        child.write_text("hello")
        result = ArchiveWriter._archive_path(child, cwd)
        assert result == "subdir/file.txt"

    async def test_archive_path_fallback_to_name(self, tmp_path: Path):
        """Static _archive_path falls back to .name when not under cwd."""
        cwd = tmp_path / "some_other_dir"
        file_path = tmp_path / "orphan.txt"
        file_path.write_text("hello")
        result = ArchiveWriter._archive_path(file_path, cwd)
        assert result == "orphan.txt"

    async def test_empty_roots_produces_valid_archive(self, tmp_path: Path):
        """An archive with no roots still produces a valid manifest."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()

        writer = ArchiveWriter(backup_dir)
        result = await writer.write(
            backup_id="empty-roots",
            roots=[],
            operation_type="backup",
        )
        archive_path = backup_dir / result["archive_filename"]
        assert archive_path.exists()
        assert result["total_uncompressed_bytes"] == 0

        with tarfile.open(archive_path, "r:gz") as tar:
            names = tar.getnames()
        assert names == ["manifest.json"]

    async def test_nonexistent_root_skipped_silently(self, tmp_path: Path):
        """A root path that does not exist is skipped (no crash)."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        missing = tmp_path / "does_not_exist"
        assert not missing.exists()

        writer = ArchiveWriter(backup_dir)
        result = await writer.write(
            backup_id="missing-root",
            roots=[missing],
            operation_type="backup",
        )
        archive_path = backup_dir / result["archive_filename"]
        assert archive_path.exists()
        with tarfile.open(archive_path, "r:gz") as tar:
            names = tar.getnames()
        assert names == ["manifest.json"]

    async def test_result_contains_all_expected_keys(self, tmp_path: Path):
        """Return dict has all required metadata keys."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "f.txt").write_text("meta")
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()

        writer = ArchiveWriter(backup_dir)
        result = await writer.write(
            backup_id="meta-test",
            roots=[src_dir],
            operation_type="backup",
            schema_revision="rev1",
        )
        expected_keys = {
            "archive_filename",
            "archive_size_bytes",
            "total_uncompressed_bytes",
            "manifest_sha256",
            "deployment_version",
            "schema_revision",
        }
        assert set(result.keys()) == expected_keys
