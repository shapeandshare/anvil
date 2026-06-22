# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for ImportService — declarative import job orchestration.

Tests the job lifecycle: starting a new import job, querying status,
and error handling for missing sources or corpora.  Uses the
``in_memory_session`` fixture for real repository-backed operations
and ``MagicMock`` for the ``VersionedContentStore`` and
``IngestionService`` dependencies.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from anvil.db.models.content_corpus import ContentCorpus
from anvil.db.models.content_import_job import ImportJob
from anvil.db.models.content_source import ContentSource
from anvil.db.repositories.content_corpora import ContentCorpusRepository
from anvil.db.repositories.content_import_jobs import ContentImportJobRepository
from anvil.db.repositories.content_ingest_sessions import ContentIngestSessionRepository
from anvil.db.repositories.content_sources import ContentSourceRepository
from anvil.services.content.import_service import ImportService
from anvil.services.content.ingest_session_ref import IngestSessionRef


@pytest_asyncio.fixture
async def seed_corpus_and_source(
    in_memory_session: AsyncSession,
) -> tuple[int, str]:
    """Seed the DB with a ``ContentCorpus`` and ``ContentSource`` and
    return the corpus id and source slug.
    """
    corpus = ContentCorpus(slug="import-corpus", name="Import Test Corpus")
    in_memory_session.add(corpus)
    source = ContentSource(slug="import-source", name="Import Source", kind="importer")
    in_memory_session.add(source)
    await in_memory_session.flush()
    await in_memory_session.refresh(corpus)
    await in_memory_session.refresh(source)
    return (corpus.id, source.slug)


@pytest_asyncio.fixture
async def service(
    in_memory_session: AsyncSession,
) -> ImportService:
    """Build an ``ImportService`` with real repos and mock store /
    ingestion service.
    """
    import_repo = ContentImportJobRepository(in_memory_session)
    session_repo = ContentIngestSessionRepository(in_memory_session)
    source_repo = ContentSourceRepository(in_memory_session)
    corpus_repo = ContentCorpusRepository(in_memory_session)

    mock_store = MagicMock()
    mock_ingestion = MagicMock()

    return ImportService(
        import_job_repo=import_repo,
        session_repo=session_repo,
        source_repo=source_repo,
        corpus_repo=corpus_repo,
        content_store=mock_store,
        ingestion_service=mock_ingestion,
    )


# ═══════════════════════════════════════════════════════════════════
# Start
# ═══════════════════════════════════════════════════════════════════


class TestStart:
    """ImportService.start() starts a new declarative import job."""

    async def test_start_returns_job(
        self,
        service: ImportService,
        seed_corpus_and_source: tuple[int, str],
    ) -> None:
        """start() returns an ``ImportJob`` with a generated id."""
        corpus_id, source_slug = seed_corpus_and_source
        mock_ingestion = service._ingestion

        mock_ingestion.open_session = AsyncMock(
            return_value=IngestSessionRef(
                session_id=10,
                corpus_id=corpus_id,
                staging_key="import-staging-1",
                status="open",
            )
        )

        job = await service.start(
            corpus_id=corpus_id,
            source_slug=source_slug,
            config={"filter": "*.txt"},
        )
        assert job.id is not None
        assert job.corpus_id == corpus_id
        assert job.session_id == 10

    async def test_start_persists_job(
        self,
        service: ImportService,
        seed_corpus_and_source: tuple[int, str],
    ) -> None:
        """start() creates a DB record for the import job."""
        corpus_id, source_slug = seed_corpus_and_source
        mock_ingestion = service._ingestion

        mock_ingestion.open_session = AsyncMock(
            return_value=IngestSessionRef(
                session_id=11,
                corpus_id=corpus_id,
                staging_key="import-staging-2",
                status="open",
            )
        )

        job = await service.start(
            corpus_id=corpus_id,
            source_slug=source_slug,
            config={"pattern": "data/**/*.csv"},
        )
        fetched = await service._import_repo.get(job.id)
        assert fetched is not None
        assert fetched.id == job.id
        assert "pattern" in fetched.config_json

    async def test_start_opens_ingestion_session(
        self,
        service: ImportService,
        seed_corpus_and_source: tuple[int, str],
    ) -> None:
        """start() delegates session creation to the ingestion service."""
        corpus_id, source_slug = seed_corpus_and_source
        mock_ingestion = service._ingestion

        mock_ingestion.open_session = AsyncMock(
            return_value=IngestSessionRef(
                session_id=12,
                corpus_id=corpus_id,
                staging_key="import-staging-3",
                status="open",
            )
        )

        await service.start(corpus_id=corpus_id, source_slug=source_slug, config={})
        mock_ingestion.open_session.assert_awaited_once()

    async def test_start_raises_for_missing_source(
        self,
        service: ImportService,
        seed_corpus_and_source: tuple[int, str],
    ) -> None:
        """start() raises ValueError when the source slug is unknown."""
        corpus_id, _ = seed_corpus_and_source
        with pytest.raises(ValueError, match="Content source not found"):
            await service.start(
                corpus_id=corpus_id,
                source_slug="no-such-source",
                config={},
            )

    async def test_start_raises_for_missing_corpus(
        self,
        service: ImportService,
        seed_corpus_and_source: tuple[int, str],
    ) -> None:
        """start() raises ValueError when the corpus is not found."""
        _, source_slug = seed_corpus_and_source
        with pytest.raises(ValueError, match="Corpus not found"):
            await service.start(
                corpus_id=999,
                source_slug=source_slug,
                config={},
            )


# ═══════════════════════════════════════════════════════════════════
# Status
# ═══════════════════════════════════════════════════════════════════


class TestStatus:
    """ImportService.status() retrieves job status."""

    async def test_status_returns_job(
        self,
        service: ImportService,
        seed_corpus_and_source: tuple[int, str],
    ) -> None:
        """status() returns the ``ImportJob`` when it exists."""
        corpus_id, source_slug = seed_corpus_and_source
        mock_ingestion = service._ingestion

        mock_ingestion.open_session = AsyncMock(
            return_value=IngestSessionRef(
                session_id=20,
                corpus_id=corpus_id,
                staging_key="import-staging-status",
                status="open",
            )
        )

        job = await service.start(
            corpus_id=corpus_id, source_slug=source_slug, config={}
        )
        fetched = await service.status(job.id)
        assert fetched is not None
        assert fetched.id == job.id

    async def test_status_returns_none_for_missing(
        self,
        service: ImportService,
        seed_corpus_and_source: tuple[int, str],
    ) -> None:
        """status() returns None when the job does not exist."""
        fetched = await service.status(999)
        assert fetched is None
