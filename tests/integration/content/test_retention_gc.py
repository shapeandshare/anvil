"""Integration tests for retention-garbage-collection (T097).

Tests that unreferenced content blobs and aged-out ingestion sessions
are correctly removed, while retention-protected versions (those with
``VersionRunRef`` or a ``ContentTag`` where ``gc_protected=True``)
have their blobs preserved.

See ``anvil/services/content/retention_service.py`` for the GC
implementation and ``specs/016-lakefs-content-repo/`` for T097.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from anvil.db.models.content_blob import ContentBlob
from anvil.db.models.content_corpus import ContentCorpus
from anvil.db.models.content_source import ContentSource
from anvil.db.models.content_tag import ContentTag
from anvil.db.models.content_version_run_ref import VersionRunRef
from anvil.db.repositories.content_blobs import ContentBlobRepository
from anvil.db.repositories.content_corpora import ContentCorpusRepository
from anvil.db.repositories.content_ingest_sessions import ContentIngestSessionRepository
from anvil.db.repositories.content_sources import ContentSourceRepository
from anvil.db.repositories.content_versions import ContentVersionRepository
from anvil.services.content.ingest_status import IngestStatus
from anvil.services.content.ingestion_service import IngestionService
from anvil.services.content.local_versioned_content_store import (
    LocalVersionedContentStore,
)
from anvil.services.content.retention_service import RetentionService
from anvil.services.content.validation_service import ValidationService


async def _stream(data: bytes) -> AsyncIterator[bytes]:
    """Yield *data* as a single-chunk async byte stream."""
    yield data


async def _build_ingestion(session: AsyncSession, content_dir: Path) -> tuple[
    IngestionService,
    LocalVersionedContentStore,
    ContentCorpusRepository,
    ContentVersionRepository,
    ContentBlobRepository,
    ContentIngestSessionRepository,
    ContentCorpus,
    ContentSource,
]:
    """Construct ingestion service, repositories, store, and
    seed a corpus/source.

    Parameters
    ----------
    session : AsyncSession
        SQLAlchemy async session.
    content_dir : Path
        Temporary content directory.

    Returns
    -------
    tuple
        (ingestion_service, store, corpus_repo, version_repo,
         blob_repo, session_repo, corpus, source)
    """
    store = LocalVersionedContentStore(content_dir=str(content_dir), db_session=session)
    corpus_repo = ContentCorpusRepository(session)
    source_repo = ContentSourceRepository(session)
    version_repo = ContentVersionRepository(session)
    session_repo = ContentIngestSessionRepository(session)
    blob_repo = ContentBlobRepository(session)

    corpus = await corpus_repo.add(ContentCorpus(slug="gc-test", name="GC Test"))
    source = await source_repo.add(
        ContentSource(slug="test-source", name="Test Source", kind="manual")
    )
    await store.ensure_corpus(corpus.slug)

    ingestion = IngestionService(
        session_repo,
        version_repo,
        blob_repo,
        corpus_repo,
        source_repo,
        store,
        ValidationService(),
    )
    return (
        ingestion,
        store,
        corpus_repo,
        version_repo,
        blob_repo,
        session_repo,
        corpus,
        source,
    )


def _build_gc(
    session: AsyncSession,
    content_dir: Path,
    corpus_repo: ContentCorpusRepository,
    version_repo: ContentVersionRepository,
    blob_repo: ContentBlobRepository,
    session_repo: ContentIngestSessionRepository,
) -> RetentionService:
    """Construct a ``RetentionService`` wired to the provided
    repositories.

    Parameters
    ----------
    session : AsyncSession
        SQLAlchemy async session.
    content_dir : Path
        Content directory path.
    corpus_repo : ContentCorpusRepository
        Corpus repository.
    version_repo : ContentVersionRepository
        Version repository.
    blob_repo : ContentBlobRepository
        Blob repository.
    session_repo : ContentIngestSessionRepository
        Session repository.

    Returns
    -------
    RetentionService
        A configured retention service instance.
    """
    return RetentionService(
        corpus_repo=corpus_repo,
        version_repo=version_repo,
        blob_repo=blob_repo,
        session_repo=session_repo,
        db_session=session,
        content_dir=str(content_dir),
    )


class TestRunReferencedVersionSurvivesGC:
    """Versions linked by ``VersionRunRef`` are retention-protected and
    their blobs survive garbage collection.
    """

    @pytest.mark.asyncio
    async def test_run_referenced_version_survives_gc(
        self, content_db: AsyncSession, content_dir: Path
    ) -> None:
        """Ingest content, accept, freeze, record a ``VersionRunRef``,
        then run GC.  The version's blobs must still be present.
        """
        (
            ingestion,
            store,
            corpus_repo,
            version_repo,
            blob_repo,
            session_repo,
            corpus,
            source,
        ) = await _build_ingestion(content_db, content_dir)
        corpus_slug = corpus.slug

        ref = await ingestion.open_session(corpus.id, source.id)
        await ingestion.stage(
            ref.session_id, "protected.txt", _stream(b"protected data")
        )
        assert (await ingestion.validate(ref.session_id)).ok
        await ingestion.accept(ref.session_id)

        version_ref = await store.freeze_version(corpus_slug)

        run_ref = VersionRunRef(
            version_id=version_ref.version_id,
            mlflow_run_id="test-run-001",
            corpus_ref=f"corpus:{corpus_slug}",
        )
        await version_repo.add_run_ref(run_ref)
        await content_db.commit()

        entries = await version_repo.get_entries(version_ref.version_id)
        protected_hash = entries[0].content_hash

        orphan_hash = "aa" + "bb" * 31
        await blob_repo.upsert(ContentBlob(content_hash=orphan_hash, size_bytes=4))
        orphan_dir = content_dir / "blobs" / orphan_hash[:2]
        orphan_dir.mkdir(parents=True, exist_ok=True)
        (orphan_dir / orphan_hash).write_bytes(b"zzzz")
        await content_db.commit()

        gc = _build_gc(
            content_db,
            content_dir,
            corpus_repo,
            version_repo,
            blob_repo,
            session_repo,
        )
        stats = await gc.collect_garbage()

        assert stats["versions_protected"] >= 1
        assert stats["blobs_removed"] >= 1
        assert await blob_repo.exists(protected_hash)

        protected_path = content_dir / "blobs" / protected_hash[:2] / protected_hash
        assert protected_path.exists()
        assert not await blob_repo.exists(orphan_hash)

        orphan_path = content_dir / "blobs" / orphan_hash[:2] / orphan_hash
        assert not orphan_path.exists()


class TestTagProtectedVersionSurvivesGC:
    """Versions with a ``ContentTag`` where ``gc_protected=True`` are
    retention-protected and their blobs survive garbage collection.
    """

    @pytest.mark.asyncio
    async def test_tag_protected_version_survives_gc(
        self, content_db: AsyncSession, content_dir: Path
    ) -> None:
        """Ingest content, accept, freeze, tag with ``gc_protected=True``,
        then run GC.  The version's blobs must still be present.
        """
        (
            ingestion,
            store,
            corpus_repo,
            version_repo,
            blob_repo,
            session_repo,
            corpus,
            source,
        ) = await _build_ingestion(content_db, content_dir)
        corpus_slug = corpus.slug

        ref = await ingestion.open_session(corpus.id, source.id)
        await ingestion.stage(ref.session_id, "tagged.txt", _stream(b"tagged data"))
        assert (await ingestion.validate(ref.session_id)).ok
        await ingestion.accept(ref.session_id)
        version_ref = await store.freeze_version(corpus_slug)

        tag = ContentTag(
            version_id=version_ref.version_id,
            name="golden",
            gc_protected=True,
        )
        content_db.add(tag)
        await content_db.commit()

        entries = await version_repo.get_entries(version_ref.version_id)
        protected_hash = entries[0].content_hash

        gc = _build_gc(
            content_db,
            content_dir,
            corpus_repo,
            version_repo,
            blob_repo,
            session_repo,
        )
        stats = await gc.collect_garbage()

        assert stats["versions_protected"] >= 1
        assert await blob_repo.exists(protected_hash)

        protected_path = content_dir / "blobs" / protected_hash[:2] / protected_hash
        assert protected_path.exists()


class TestUnreferencedBlobsAreCollected:
    """Orphan blobs with no referencing entries are removed by GC."""

    @pytest.mark.asyncio
    async def test_unreferenced_blobs_are_collected(
        self, content_db: AsyncSession, content_dir: Path
    ) -> None:
        """Create a blob that is not referenced by any version entry.
        Run GC and verify it is deleted from both DB and disk.
        """
        (
            _ingestion,
            _store,
            corpus_repo,
            version_repo,
            blob_repo,
            session_repo,
            _corpus,
            _source,
        ) = await _build_ingestion(content_db, content_dir)

        orphan_hash = "cc" + "dd" * 31
        blob = ContentBlob(content_hash=orphan_hash, size_bytes=7)
        await blob_repo.upsert(blob)

        orphan_dir = content_dir / "blobs" / orphan_hash[:2]
        orphan_dir.mkdir(parents=True, exist_ok=True)
        (orphan_dir / orphan_hash).write_bytes(b"orphaned")

        await content_db.commit()

        assert await blob_repo.exists(orphan_hash)

        gc = _build_gc(
            content_db,
            content_dir,
            corpus_repo,
            version_repo,
            blob_repo,
            session_repo,
        )
        stats = await gc.collect_garbage()

        assert stats["blobs_removed"] >= 1
        assert not await blob_repo.exists(orphan_hash)

        orphan_path = content_dir / "blobs" / orphan_hash[:2] / orphan_hash
        assert not orphan_path.exists()


class TestFailedSessionStagingCleaned:
    """Failed ingestion sessions older than 30 days have their staging
    directories removed by GC.
    """

    @pytest.mark.asyncio
    async def test_old_failed_session_staging_cleaned(
        self, content_db: AsyncSession, content_dir: Path
    ) -> None:
        """Create a failed session with a ``closed_at`` older than 30
        days.  Run GC and verify the staging directory is removed.
        """
        (
            _ingestion,
            _store,
            corpus_repo,
            version_repo,
            blob_repo,
            session_repo,
            corpus,
            _source,
        ) = await _build_ingestion(content_db, content_dir)

        from anvil.db.models.content_ingest_session import IngestSession

        old_staging_key = f"{corpus.slug}/old-session"
        session = IngestSession(
            corpus_id=corpus.id,
            source_id=1,
            staging_key=old_staging_key,
            status=IngestStatus.FAILED,
            closed_at=datetime.now() - timedelta(days=31),
        )
        await session_repo.add(session)

        staging_area = content_dir / "staging" / old_staging_key
        staging_area.mkdir(parents=True, exist_ok=True)
        (staging_area / "ref.json").write_text("{}")

        assert staging_area.exists()

        gc = _build_gc(
            content_db,
            content_dir,
            corpus_repo,
            version_repo,
            blob_repo,
            session_repo,
        )
        stats = await gc.collect_garbage()

        assert stats["sessions_cleaned"] >= 1
        assert not staging_area.exists()

    @pytest.mark.asyncio
    async def test_recent_failed_session_not_cleaned(
        self, content_db: AsyncSession, content_dir: Path
    ) -> None:
        """A failed session with a recent ``closed_at`` is NOT cleaned
        by GC.
        """
        (
            _ingestion,
            _store,
            corpus_repo,
            version_repo,
            blob_repo,
            session_repo,
            corpus,
            _source,
        ) = await _build_ingestion(content_db, content_dir)

        from anvil.db.models.content_ingest_session import IngestSession

        recent_staging_key = f"{corpus.slug}/recent-session"
        session = IngestSession(
            corpus_id=corpus.id,
            source_id=1,
            staging_key=recent_staging_key,
            status=IngestStatus.FAILED,
            closed_at=datetime.now() - timedelta(days=1),
        )
        await session_repo.add(session)

        staging_area = content_dir / "staging" / recent_staging_key
        staging_area.mkdir(parents=True, exist_ok=True)
        (staging_area / "ref.json").write_text("{}")

        gc = _build_gc(
            content_db,
            content_dir,
            corpus_repo,
            version_repo,
            blob_repo,
            session_repo,
        )
        stats = await gc.collect_garbage()

        assert stats["sessions_cleaned"] == 0
        assert staging_area.exists()
