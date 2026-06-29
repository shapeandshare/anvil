# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for RetentionService — garbage collection and cleanup.

Tests cover ``collect_garbage()`` with real in-memory DB tables and a
temp directory for on-disk blob/staging files.  Repositories are real
(not mocked) so that SQL correctness is verified; file operations use
``tmp_path``.

Test scenarios
--------------
- No blobs or sessions to clean (empty corpus)
- Blobs protected by :class:`VersionRunRef`
- Blobs protected by :class:`ContentTag` with ``gc_protected=True``
- Unreferenced blob metadata + file removal
- Expired FAILED session cleanup
- Active / recent FAILED sessions preserved
- Mixed: protected versions + unreferenced blobs + expired sessions
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

# Import all model modules so their tables register on Base.metadata
# before the in_memory_session fixture creates them.
from anvil.db.models.content_blob import ContentBlob
from anvil.db.models.content_entry import ContentEntry
from anvil.db.models.content_ingest_session import IngestSession
from anvil.db.models.content_tag import ContentTag
from anvil.db.models.content_version import ContentVersion
from anvil.db.models.content_version_run_ref import VersionRunRef
from anvil.db.repositories.content_blobs import ContentBlobRepository
from anvil.db.repositories.content_corpora import ContentCorpusRepository
from anvil.db.repositories.content_ingest_sessions import ContentIngestSessionRepository
from anvil.db.repositories.content_versions import ContentVersionRepository
from anvil.services.content.ingest_status import IngestStatus
from anvil.services.content.retention_service import RetentionService


@pytest.fixture
def content_dir(tmp_path: Path) -> Path:
    """Return a temp content directory with ``blobs/`` and ``staging/``
    subdirectories.
    """
    blobs_dir = tmp_path / "blobs"
    staging_dir = tmp_path / "staging"
    blobs_dir.mkdir(parents=True)
    staging_dir.mkdir()
    return tmp_path


@pytest.fixture
def service(in_memory_session: AsyncSession, content_dir: Path) -> RetentionService:
    """Build a ``RetentionService`` with real repos and the in-memory
    DB session.
    """
    return RetentionService(
        corpus_repo=ContentCorpusRepository(in_memory_session),
        version_repo=ContentVersionRepository(in_memory_session),
        blob_repo=ContentBlobRepository(in_memory_session),
        session_repo=ContentIngestSessionRepository(in_memory_session),
        db_session=in_memory_session,
        content_dir=str(content_dir),
    )


def _blob_path(content_dir: Path, h: str) -> Path:
    """Return the on-disk path for a blob hash within `content_dir`."""
    return content_dir / "blobs" / h[:2] / h


def _place_blob(content_dir: Path, h: str) -> None:
    """Create a blob file on disk at the expected sharded path."""
    parent = content_dir / "blobs" / h[:2]
    parent.mkdir(parents=True, exist_ok=True)
    parent.joinpath(h).write_text("data")


def _place_staging(content_dir: Path, staging_key: str) -> None:
    """Create a staging directory."""
    d = content_dir / "staging" / staging_key
    d.mkdir(parents=True, exist_ok=True)
    d.joinpath("some_file").write_text("staged")


########################################################################
# Tests: no data
########################################################################


class TestEmptyCorpus:
    """GC on an empty content store."""

    async def test_collect_garbage_empty(self, service: RetentionService) -> None:
        """collect_garbage on an empty DB and empty disk returns zeroes."""
        result = await service.collect_garbage()
        assert result == {
            "blobs_removed": 0,
            "versions_protected": 0,
            "sessions_cleaned": 0,
        }


########################################################################
# Tests: protected versions (run refs and tags)
########################################################################


class TestProtectedVersions:
    """Versions retain their blobs via VersionRunRef or ContentTag."""

    async def test_protected_by_run_ref(
        self,
        in_memory_session: AsyncSession,
        service: RetentionService,
        content_dir: Path,
    ) -> None:
        """A version with a VersionRunRef is retention-protected; its
        blobs are kept.
        """
        # --- seed ---
        blob_hash = "a" * 64
        _place_blob(content_dir, blob_hash)
        blob = ContentBlob(content_hash=blob_hash, size_bytes=10)
        in_memory_session.add(blob)

        v = ContentVersion(corpus_id=1, version_number=1, manifest_digest="d1")
        in_memory_session.add(v)
        await in_memory_session.flush()
        await in_memory_session.refresh(v)

        entry = ContentEntry(version_id=v.id, path="f.txt", content_hash=blob_hash)
        in_memory_session.add(entry)

        ref = VersionRunRef(
            version_id=v.id, mlflow_run_id="run1", corpus_ref="corpus:1"
        )
        in_memory_session.add(ref)
        await in_memory_session.flush()

        result = await service.collect_garbage()
        assert result["versions_protected"] == 1
        assert result["blobs_removed"] == 0

    async def test_protected_by_gc_tag(
        self,
        in_memory_session: AsyncSession,
        service: RetentionService,
        content_dir: Path,
    ) -> None:
        """A version with a gc_protected ContentTag retains its blobs."""
        blob_hash = "b" * 64
        _place_blob(content_dir, blob_hash)
        blob = ContentBlob(content_hash=blob_hash, size_bytes=10)
        in_memory_session.add(blob)

        v = ContentVersion(corpus_id=2, version_number=1, manifest_digest="d2")
        in_memory_session.add(v)
        await in_memory_session.flush()
        await in_memory_session.refresh(v)

        entry = ContentEntry(version_id=v.id, path="g.txt", content_hash=blob_hash)
        in_memory_session.add(entry)

        tag = ContentTag(version_id=v.id, name="protected", gc_protected=True)
        in_memory_session.add(tag)
        await in_memory_session.flush()

        result = await service.collect_garbage()
        assert result["versions_protected"] == 1
        assert result["blobs_removed"] == 0

    async def test_unprotected_version_blobs_removed(
        self,
        in_memory_session: AsyncSession,
        service: RetentionService,
        content_dir: Path,
    ) -> None:
        """A version with NO run ref and NO gc_protected tag is NOT
        protected — its blobs ARE removed.
        """
        blob_hash = "c" * 64
        _place_blob(content_dir, blob_hash)
        blob = ContentBlob(content_hash=blob_hash, size_bytes=10)
        in_memory_session.add(blob)

        v = ContentVersion(corpus_id=3, version_number=1, manifest_digest="d3")
        in_memory_session.add(v)
        await in_memory_session.flush()
        await in_memory_session.refresh(v)

        entry = ContentEntry(version_id=v.id, path="u.txt", content_hash=blob_hash)
        in_memory_session.add(entry)
        await in_memory_session.flush()

        result = await service.collect_garbage()
        assert result["versions_protected"] == 0
        assert result["blobs_removed"] == 1
        # on-disk file should also be gone
        assert not _blob_path(content_dir, blob_hash).exists()

    async def test_tag_with_gc_protected_false(
        self,
        in_memory_session: AsyncSession,
        service: RetentionService,
        content_dir: Path,
    ) -> None:
        """A ContentTag with gc_protected=False does NOT protect the
        version.
        """
        blob_hash = "d" * 64
        _place_blob(content_dir, blob_hash)
        blob = ContentBlob(content_hash=blob_hash, size_bytes=10)
        in_memory_session.add(blob)

        v = ContentVersion(corpus_id=4, version_number=1, manifest_digest="d4")
        in_memory_session.add(v)
        await in_memory_session.flush()
        await in_memory_session.refresh(v)

        entry = ContentEntry(version_id=v.id, path="nt.txt", content_hash=blob_hash)
        in_memory_session.add(entry)

        tag = ContentTag(version_id=v.id, name="noprotect", gc_protected=False)
        in_memory_session.add(tag)
        await in_memory_session.flush()

        result = await service.collect_garbage()
        assert result["versions_protected"] == 0
        assert result["blobs_removed"] == 1


########################################################################
# Tests: stale ingest session cleanup
########################################################################


class TestStaleSessionCleanup:
    """Aged-out FAILED sessions get their staging areas removed."""

    async def test_expired_failed_session_cleaned(
        self,
        in_memory_session: AsyncSession,
        service: RetentionService,
        content_dir: Path,
    ) -> None:
        """A FAILED session closed >30 days ago is cleaned."""
        old = datetime.now() - timedelta(days=31)
        sess = IngestSession(
            corpus_id=1,
            source_id=1,
            staging_key="old-session",
            status=IngestStatus.FAILED,
            closed_at=old,
        )
        in_memory_session.add(sess)
        await in_memory_session.flush()
        _place_staging(content_dir, "old-session")

        result = await service.collect_garbage()
        assert result["sessions_cleaned"] == 1
        assert not (content_dir / "staging" / "old-session").exists()

    async def test_recent_failed_session_preserved(
        self,
        in_memory_session: AsyncSession,
        service: RetentionService,
        content_dir: Path,
    ) -> None:
        """A FAILED session closed only 1 day ago is NOT cleaned."""
        recent = datetime.now() - timedelta(days=1)
        sess = IngestSession(
            corpus_id=2,
            source_id=1,
            staging_key="recent-session",
            status=IngestStatus.FAILED,
            closed_at=recent,
        )
        in_memory_session.add(sess)
        await in_memory_session.flush()
        _place_staging(content_dir, "recent-session")

        result = await service.collect_garbage()
        assert result["sessions_cleaned"] == 0
        assert (content_dir / "staging" / "recent-session").exists()

    async def test_open_session_not_cleaned(
        self,
        in_memory_session: AsyncSession,
        service: RetentionService,
        content_dir: Path,
    ) -> None:
        """An OPEN session (not FAILED) is never cleaned regardless of
        age.
        """
        old = datetime.now() - timedelta(days=60)
        sess = IngestSession(
            corpus_id=3,
            source_id=1,
            staging_key="open-old",
            status=IngestStatus.OPEN,
            closed_at=old,
        )
        in_memory_session.add(sess)
        await in_memory_session.flush()
        _place_staging(content_dir, "open-old")

        result = await service.collect_garbage()
        assert result["sessions_cleaned"] == 0

    async def test_failed_session_no_closed_at(
        self,
        in_memory_session: AsyncSession,
        service: RetentionService,
        content_dir: Path,
    ) -> None:
        """A FAILED session with closed_at=None is NOT cleaned."""
        sess = IngestSession(
            corpus_id=4,
            source_id=1,
            staging_key="no-close",
            status=IngestStatus.FAILED,
            closed_at=None,
        )
        in_memory_session.add(sess)
        await in_memory_session.flush()
        _place_staging(content_dir, "no-close")

        result = await service.collect_garbage()
        assert result["sessions_cleaned"] == 0


########################################################################
# Tests: unreferenced blob removal
########################################################################


class TestUnreferencedBlobs:
    """Blobs whose hashes aren't in any protected version are removed."""

    async def test_orphan_blob_removed(
        self,
        in_memory_session: AsyncSession,
        service: RetentionService,
        content_dir: Path,
    ) -> None:
        """A blob with no version entries at all is removed."""
        h = "e" * 64
        _place_blob(content_dir, h)
        blob = ContentBlob(content_hash=h, size_bytes=20)
        in_memory_session.add(blob)
        await in_memory_session.flush()

        result = await service.collect_garbage()
        assert result["blobs_removed"] == 1
        assert not _blob_path(content_dir, h).exists()

    async def test_blob_with_no_disk_file(
        self,
        in_memory_session: AsyncSession,
        service: RetentionService,
        content_dir: Path,
    ) -> None:
        """An orphan blob with no on-disk file still removes the DB row
        (disk unlink is skipped).
        """
        h = "f" * 64
        blob = ContentBlob(content_hash=h, size_bytes=20)
        in_memory_session.add(blob)
        await in_memory_session.flush()

        result = await service.collect_garbage()
        assert result["blobs_removed"] == 1
        # DB row is deleted: verify via subsequent get_all
        hashes = await ContentBlobRepository(in_memory_session).get_all_content_hashes()
        assert h not in hashes

    async def test_multiple_protected_and_orphan_blobs(
        self,
        in_memory_session: AsyncSession,
        service: RetentionService,
        content_dir: Path,
    ) -> None:
        """Mix of protected and orphan blobs: only orphanes removed."""
        keep_h = "g" * 64
        orphan_h = "h" * 64
        _place_blob(content_dir, keep_h)
        _place_blob(content_dir, orphan_h)

        blob_keep = ContentBlob(content_hash=keep_h, size_bytes=10)
        blob_orphan = ContentBlob(content_hash=orphan_h, size_bytes=10)
        in_memory_session.add_all([blob_keep, blob_orphan])

        v = ContentVersion(corpus_id=5, version_number=1, manifest_digest="d5")
        in_memory_session.add(v)
        await in_memory_session.flush()
        await in_memory_session.refresh(v)

        entry = ContentEntry(version_id=v.id, path="k.txt", content_hash=keep_h)
        in_memory_session.add(entry)
        ref = VersionRunRef(
            version_id=v.id, mlflow_run_id="run2", corpus_ref="corpus:5"
        )
        in_memory_session.add(ref)
        await in_memory_session.flush()

        result = await service.collect_garbage()
        assert result["versions_protected"] == 1
        assert result["blobs_removed"] == 1
        assert _blob_path(content_dir, keep_h).exists()
        assert not _blob_path(content_dir, orphan_h).exists()


########################################################################
# Tests: blob disk file removal edge cases
########################################################################


class TestDiskCleanup:
    """Edge cases around deleting blob files from disk."""

    async def test_blob_missing_disk_file_does_not_raise(
        self,
        in_memory_session: AsyncSession,
        service: RetentionService,
        content_dir: Path,
    ) -> None:
        """If an orphan blob's disk file is already missing, the
        service does not raise.
        """
        h = "i" * 64
        blob = ContentBlob(content_hash=h, size_bytes=10)
        in_memory_session.add(blob)
        await in_memory_session.flush()

        # No disk file placed — should not crash
        result = await service.collect_garbage()
        assert result["blobs_removed"] == 1
