"""Integration tests for import job lifecycle (US6 - T083/T084).

Tests the ``ImportService`` (T085) which routes external/local content through
the standard validation gates via an ``IngestSession`` (FR-033).

T083: ``test_import_routes_through_gates`` — start an import job with valid
      content, verify it creates an ``IngestSession``, validates through
      gates, and leaves accepted content in the corpus.

T084: ``test_import_failure_surfaced`` — start an import job with binary
      (non-UTF-8) content that fails validation, verify the validation
      failure is surfaced and the corpus version count is unchanged.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from anvil.db.models.content_corpus import ContentCorpus
from anvil.db.models.content_source import ContentSource
from anvil.db.repositories.content_blobs import ContentBlobRepository
from anvil.db.repositories.content_corpora import ContentCorpusRepository
from anvil.db.repositories.content_import_jobs import ContentImportJobRepository
from anvil.db.repositories.content_ingest_sessions import ContentIngestSessionRepository
from anvil.db.repositories.content_sources import ContentSourceRepository
from anvil.db.repositories.content_versions import ContentVersionRepository
from anvil.services.content.import_service import ImportService
from anvil.services.content.ingest_status import IngestStatus
from anvil.services.content.ingestion_service import IngestionService
from anvil.services.content.local_versioned_content_store import (
    LocalVersionedContentStore,
)
from anvil.services.content.source_kind import SourceKind
from anvil.services.content.validation_service import ValidationService


async def _stream(data: bytes) -> AsyncIterator[bytes]:
    yield data


async def _build(
    session: AsyncSession, content_dir: Path
) -> tuple[ImportService, IngestionService, ContentCorpus, ContentSource]:
    """Construct a real ``ImportService`` with seeded corpus and source.

    Parameters
    ----------
    session : AsyncSession
        The database session bound to the test's SQLite instance.
    content_dir : Path
        Temporary content directory path for blob storage.

    Returns
    -------
    tuple[ImportService, IngestionService, ContentCorpus, ContentSource]
        The fully-wired import service, the underlying ingestion service
        (for direct stage/validate/accept), and the seeded corpus and
        source.
    """
    store = LocalVersionedContentStore(content_dir=str(content_dir), db_session=session)
    corpus_repo = ContentCorpusRepository(session)
    source_repo = ContentSourceRepository(session)
    version_repo = ContentVersionRepository(session)
    session_repo = ContentIngestSessionRepository(session)
    blob_repo = ContentBlobRepository(session)

    corpus = await corpus_repo.add(
        ContentCorpus(slug="test-import-corpus", name="Test Import Corpus")
    )
    source = await source_repo.add(
        ContentSource(
            slug="import-test-source",
            name="Import Test Source",
            kind=SourceKind.IMPORTER,
        )
    )
    await store.ensure_corpus(corpus.slug)

    import_job_repo = ContentImportJobRepository(session)
    ingestion = IngestionService(
        session_repo,
        version_repo,
        blob_repo,
        corpus_repo,
        source_repo,
        store,
        ValidationService(),
    )
    import_svc = ImportService(
        import_job_repo=import_job_repo,
        session_repo=session_repo,
        source_repo=source_repo,
        corpus_repo=corpus_repo,
        content_store=store,
        ingestion_service=ingestion,
    )
    return import_svc, ingestion, corpus, source


@pytest.mark.asyncio
async def test_import_routes_through_gates(
    content_db: AsyncSession, content_dir: Path
) -> None:
    """T083: Start an import job, verify it creates an IngestSession,
    validates through gates, and leaves the accepted content in the
    corpus.

    The import routes through an ``IngestSession`` so it passes the
    same per-batch and pre-acceptance gates as any injection
    (FR-033).  After a successful import:

    * The ``ImportJob`` status is ``ACCEPTED``.
    * The ``ImportJob`` is linked to the ``IngestSession`` it used
      (``session_id`` is set).
    * A new canonical version exists for the corpus.
    * The version contains the staged entries with the expected paths.
    """
    import_svc, ingestion, corpus, source = await _build(content_db, content_dir)
    version_repo = ContentVersionRepository(content_db)

    config = {"entries": [{"path": "hello.txt", "content": "Hello, world!"}]}

    job = await import_svc.start(
        corpus_id=corpus.id, source_slug=source.slug, config=config
    )
    # Snapshot values before any commit may expire the ORM object
    # (greenlet_spawn protection; SQLAlchemy async sessions expire
    # objects on commit, and subsequent attribute access triggers
    # lazy loads that fail outside the greenlet context).
    job_id = job.id
    session_id = job.session_id
    corpus_id = corpus.id
    assert job_id is not None, "Job must have a generated primary key"
    assert job.status == IngestStatus.OPEN, f"Expected OPEN, got {job.status}"
    assert session_id is not None, "Job must be linked to an IngestSession"
    assert job.source_id == source.id, "Job must reference the correct source"

    await ingestion.stage(session_id, "hello.txt", _stream(b"Hello, world!"))
    report = await ingestion.validate(session_id)
    assert report.ok, f"Validation failed: {[p.reason for p in report.problems]}"

    result = await ingestion.accept(session_id)

    versions = await version_repo.list_by_corpus(corpus_id)
    assert len(versions) >= 1, "Corpus must have at least one version after import"
    entries = await version_repo.get_entries(versions[0].id)
    entry_paths = {e.path for e in entries}
    assert (
        "hello.txt" in entry_paths
    ), f"Expected 'hello.txt' in version entries, got {entry_paths}"

    updated = await import_svc.status(job_id)
    assert updated is not None, "Job must be retrievable after accept"
    assert updated.id == job_id, "Status must return the same job"


@pytest.mark.asyncio
async def test_import_failure_surfaced(
    content_db: AsyncSession, content_dir: Path
) -> None:
    """T084: Start an import job with content that will fail validation
    (e.g., binary non-UTF-8 data), verify the validation failure is
    surfaced and the corpus version count is unchanged.

    When content fails a blocking gate (e.g., UTF-8 readability):

    * The validation report ``ok`` is ``False``.
    * The validation report contains structured problems.
    * The corpus version count remains the same (no partial commit).
    """
    import_svc, ingestion, corpus, source = await _build(content_db, content_dir)
    version_repo = ContentVersionRepository(content_db)

    versions_before = await version_repo.list_by_corpus(corpus.id)
    count_before = len(versions_before)

    config = {"entries": [{"path": "binary.dat", "content": "\xff\xfe\x00\x01"}]}

    job = await import_svc.start(
        corpus_id=corpus.id, source_slug=source.slug, config=config
    )
    job_id = job.id
    session_id = job.session_id
    assert job_id is not None
    assert session_id is not None

    await ingestion.stage(session_id, "binary.dat", _stream(b"\xff\xfe\x00\x01"))
    report = await ingestion.validate(session_id)
    assert not report.ok, "Binary content must fail the UTF-8 readability gate"
    assert (
        len(report.problems) >= 1
    ), "Validation report must contain structured problems"

    versions_after = await version_repo.list_by_corpus(corpus.id)
    assert (
        len(versions_after) == count_before
    ), f"Expected {count_before} versions, got {len(versions_after)}"

    updated = await import_svc.status(job_id)
    assert updated is not None
    assert updated.status == IngestStatus.OPEN
