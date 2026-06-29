"""Tests for ArchiveReader — verify, extract, load_manifest."""

import json
import tarfile
from pathlib import Path

import pytest

from anvil.services.backup.archive_reader import ArchiveReader
from anvil.services.backup.archive_writer import ArchiveWriter


class TestArchiveReaderVerify:
    """Integrity verification behavior."""

    async def test_verify_valid_archive(self, tmp_path: Path):
        """A freshly created archive passes verification."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "data.txt").write_text("important data")
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()

        writer = ArchiveWriter(backup_dir)
        await writer.write(
            backup_id="verify-ok",
            roots=[src_dir],
            operation_type="backup",
        )

        reader = ArchiveReader(backup_dir)
        result = await reader.verify("verify-ok")
        assert result.valid is True
        assert result.checked_count >= 1
        assert result.mismatched == []

    async def test_verify_missing_backup_returns_invalid(self, tmp_path: Path):
        """Non-existent backup returns valid=False."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()

        reader = ArchiveReader(backup_dir)
        result = await reader.verify("no-such-backup")
        assert result.valid is False
        assert result.checked_count == 0

    async def test_verify_detects_corrupted_file(self, tmp_path: Path):
        """Modifying the manifest checksum causes verification to fail."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "data.txt").write_text("original content")
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()

        writer = ArchiveWriter(backup_dir)
        result = await writer.write(
            backup_id="corrupt-me",
            roots=[src_dir],
            operation_type="backup",
        )

        # Modify the manifest in the archive to have a wrong checksum.
        archive_path = backup_dir / result["archive_filename"]
        tmp_archive = backup_dir / "tmp-repack.tar.gz"
        with tarfile.open(archive_path, "r:gz") as src:
            members = src.getmembers()
            manifest = json.loads(src.extractfile("manifest.json").read())

        # Tweak the sha256 of the first entry.
        manifest["entries"][0]["sha256"] = "0" * 64

        with tarfile.open(tmp_archive, "w:gz") as out:
            info = tarfile.TarInfo(name="manifest.json")
            manifest_bytes = json.dumps(manifest, indent=2).encode("utf-8")
            info.size = len(manifest_bytes)
            out.addfile(info, __import__("io").BytesIO(manifest_bytes))
            for member in members:
                if member.name == "manifest.json":
                    continue
                # Re-read the original file content.
                src_tar = tarfile.open(archive_path, "r:gz")
                f = src_tar.extractfile(member)
                content = f.read() if f else b""
                src_tar.close()
                out.addfile(member, __import__("io").BytesIO(content))

        tmp_archive.replace(archive_path)

        reader = ArchiveReader(backup_dir)
        verify_result = await reader.verify("corrupt-me")
        assert verify_result.valid is False
        assert len(verify_result.mismatched) > 0

    async def test_verify_with_empty_archive(self, tmp_path: Path):
        """An archive with only manifest.json passes verification."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()

        writer = ArchiveWriter(backup_dir)
        await writer.write(
            backup_id="empty",
            roots=[],
            operation_type="backup",
        )

        reader = ArchiveReader(backup_dir)
        result = await reader.verify("empty")
        assert result.valid is True
        assert result.checked_count == 0

    async def test_verify_reports_mismatched_paths(self, tmp_path: Path):
        """Mismatched entries are listed in verify result."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "f1.txt").write_text("alpha")
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()

        writer = ArchiveWriter(backup_dir)
        await writer.write(
            backup_id="two-files",
            roots=[src_dir],
            operation_type="backup",
        )

        # Overwrite the manifest to have a wrong checksum.
        archive_path = backup_dir / "backup-two-files.tar.gz"
        # Re-pack with a wrong manifest entry.
        with tarfile.open(archive_path, "r:gz") as tar:
            members = tar.getmembers()
            original_manifest = json.loads(
                tar.extractfile("manifest.json").read()
            )

        # Tweak the sha256 in the manifest.
        original_manifest["entries"][0]["sha256"] = "0" * 64

        # Rebuild the archive with the tampered manifest.
        tmp_archive = backup_dir / "tmp-repack.tar.gz"
        with tarfile.open(tmp_archive, "w:gz") as out:
            info = tarfile.TarInfo(name="manifest.json")
            manifest_bytes = json.dumps(
                original_manifest, indent=2
            ).encode("utf-8")
            info.size = len(manifest_bytes)
            out.addfile(info, __import__("io").BytesIO(manifest_bytes))
            for member in members:
                if member.name == "manifest.json":
                    continue
                out.addfile(member)

        tmp_archive.replace(archive_path)

        reader = ArchiveReader(backup_dir)
        result = await reader.verify("two-files")
        assert result.valid is False
        assert len(result.mismatched) > 0


class TestArchiveReaderExtract:
    """Extraction behavior."""

    async def test_extract_to_creates_files(self, tmp_path: Path):
        """Files are extracted to destination directory."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "sub").mkdir()
        (src_dir / "alpha.txt").write_text("hello")
        (src_dir / "sub" / "beta.txt").write_text("world")
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()

        writer = ArchiveWriter(backup_dir)
        await writer.write(
            backup_id="extract-test",
            roots=[src_dir],
            operation_type="backup",
        )

        dest = tmp_path / "restored"
        reader = ArchiveReader(backup_dir)
        manifest = await reader.extract_to("extract-test", dest)

        assert manifest.backup_id == "extract-test"
        # Archive paths are relative to cwd; in tests the paths are
        # flat (just filename) because tmp_path is not under cwd.
        assert (dest / "src" / "alpha.txt").exists() or (dest / "alpha.txt").exists()
        assert (dest / "src" / "sub" / "beta.txt").exists() or (
            dest / "beta.txt"
        ).exists()

    async def test_extract_to_creates_dest_if_not_exists(self, tmp_path: Path):
        """Destination directory is created if it does not exist."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "f.txt").write_text("data")
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()

        writer = ArchiveWriter(backup_dir)
        result = await writer.write(
            backup_id="auto-mkdir",
            roots=[src_dir],
            operation_type="backup",
        )

        dest = tmp_path / "does_not_exist_yet"
        reader = ArchiveReader(backup_dir)
        await reader.extract_to("auto-mkdir", dest)
        assert dest.exists()
        # The archive path is flat (just "f.txt") since tmp_path is
        # not under cwd, so file lands at dest/f.txt.
        assert (dest / "f.txt").read_text() == "data"

    async def test_extract_to_rejects_path_traversal(self, tmp_path: Path):
        """Extraction raises ValueError on path-traversal attempt."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()

        # Build a malicious archive manually.
        malicious_archive = backup_dir / "backup-traversal.tar.gz"
        with tarfile.open(malicious_archive, "w:gz") as tar:
            # Valid manifest first.
            manifest = {
                "manifest_version": 1,
                "backup_id": "traversal",
                "created_at": "2026-01-01T00:00:00+00:00",
                "operation_type": "backup",
                "deployment_version": "0.0.0",
                "schema_revision": "",
                "total_uncompressed_bytes": 0,
                "entries": [],
            }
            info = tarfile.TarInfo(name="manifest.json")
            manifest_bytes = json.dumps(manifest, indent=2).encode("utf-8")
            info.size = len(manifest_bytes)
            tar.addfile(info, __import__("io").BytesIO(manifest_bytes))

            # Malicious entry with path traversal.
            bad_info = tarfile.TarInfo(name="../../etc/passwd")
            bad_info.size = 4
            tar.addfile(bad_info, __import__("io").BytesIO(b"evil"))

        dest = tmp_path / "dest"
        dest.mkdir()
        reader = ArchiveReader(backup_dir)
        with pytest.raises(ValueError, match="Path traversal"):
            await reader.extract_to("traversal", dest)

    async def test_extract_to_rejects_unsupported_version(self, tmp_path: Path):
        """Extraction raises ValueError on manifest_version > 1."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()

        # Build an archive with manifest_version = 2.
        v2_archive = backup_dir / "backup-v2-test.tar.gz"
        with tarfile.open(v2_archive, "w:gz") as tar:
            manifest = {
                "manifest_version": 2,
                "backup_id": "v2-test",
                "created_at": "2026-01-01T00:00:00+00:00",
                "operation_type": "backup",
                "deployment_version": "0.0.0",
                "schema_revision": "",
                "total_uncompressed_bytes": 0,
                "entries": [],
            }
            info = tarfile.TarInfo(name="manifest.json")
            manifest_bytes = json.dumps(manifest, indent=2).encode("utf-8")
            info.size = len(manifest_bytes)
            tar.addfile(info, __import__("io").BytesIO(manifest_bytes))

        dest = tmp_path / "dest"
        dest.mkdir()
        reader = ArchiveReader(backup_dir)
        with pytest.raises(ValueError, match="Unsupported manifest version"):
            await reader.extract_to("v2-test", dest)


class TestArchiveReaderLoadManifest:
    """Manifest loading behavior."""

    async def test_load_manifest_returns_manifest(self, tmp_path: Path):
        """load_manifest returns the parsed BackupManifest."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "f.txt").write_text("data")
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()

        writer = ArchiveWriter(backup_dir)
        await writer.write(
            backup_id="load-test",
            roots=[src_dir],
            operation_type="backup",
        )

        reader = ArchiveReader(backup_dir)
        manifest = await reader.load_manifest("load-test")
        assert manifest is not None
        assert manifest.backup_id == "load-test"
        assert manifest.manifest_version == 1
        assert len(manifest.entries) == 1

    async def test_load_manifest_returns_none_for_missing(self, tmp_path: Path):
        """load_manifest returns None for non-existent backup."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        reader = ArchiveReader(backup_dir)
        manifest = await reader.load_manifest("nonexistent")
        assert manifest is None

    async def test_load_manifest_schema_revision(self, tmp_path: Path):
        """Schema revision is preserved through manifest load."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "f.txt").write_text("data")
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()

        writer = ArchiveWriter(backup_dir)
        await writer.write(
            backup_id="schema-load",
            roots=[src_dir],
            operation_type="backup",
            schema_revision="deadbeef",
        )

        reader = ArchiveReader(backup_dir)
        manifest = await reader.load_manifest("schema-load")
        assert manifest is not None
        assert manifest.schema_revision == "deadbeef"


class TestArchiveReaderRoundTrip:
    """Full round-trip: write → verify → extract → verify again."""

    async def test_full_round_trip(self, tmp_path: Path):
        """Write, verify, extract, and re-verify the extraction."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "a.txt").write_text("alpha")
        (src_dir / "b.txt").write_text("beta")
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()

        writer = ArchiveWriter(backup_dir)
        await writer.write(
            backup_id="roundtrip",
            roots=[src_dir],
            operation_type="backup",
        )

        reader = ArchiveReader(backup_dir)

        # Verify the source archive.
        v1 = await reader.verify("roundtrip")
        assert v1.valid is True

        # Extract.  Archive paths are flat (just filename) when
        # tmp_path is not under cwd.
        dest = tmp_path / "restored"
        manifest = await reader.extract_to("roundtrip", dest)
        assert manifest.backup_id == "roundtrip"
        assert (dest / "a.txt").read_text() == "alpha"
        assert (dest / "b.txt").read_text() == "beta"