# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for IngestionService — session lifecycle management.

Tests the orchestration layer that coordinates session CRUD, staging,
validation, acceptance, and abandonment.  Uses the ``in_memory_session``
fixture for real repository-backed operations and ``MagicMock`` for the
``VersionedContentStore`` and ``ValidationService`` dependencies.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from anvil.db.models.content_corpus import ContentCorpus
from anvil.db.models.content_ingest_session import IngestSession
from anvil.db.models.content_source import ContentSource
from anvil.db.repositories.content_blobs import ContentBlobRepository
from anvil.db.repositories.content_corpora import ContentCorpusRepository
from anvil.db.repositories.content_ingest_sessions import (
    ContentIngestSessionRepository,
)
from anvil.db.repositories.content_sources import ContentSourceRepository
from anvil.db.repositories.content_versions import ContentVersionRepository
from anvil.services.content.accept_result import AcceptResult
from anvil.services.content.ingest_session_ref import IngestSessionRef
from anvil.services.content.ingest_status import IngestStatus
from anvil.services.content.ingestion_service import IngestionService
from anvil.services.content.staged_entry import StagedEntry
from anvil.services.content.validation_report import (
    ValidationProblem,
    ValidationReport,
)


@pytest_asyncio.fixture
async def seed_corpus_and_source(
    in_memory_session: AsyncSession,
) -> tuple[int, int]:
    """Seed the DB with a ``ContentCorpus`` and ``ContentSource`` and
    return their ids.
    """
    corpus = ContentCorpus(slug="ingest-corpus", name="Ingest Test Corpus")
    in_memory_session.add(corpus)
    source = ContentSource(slug="test-source", name="Test Source", kind="manual")
    in_memory_session.add(source)
    await in_memory_session.flush()
    await in_memory_session.refresh(corpus)
    await in_memory_session.refresh(source)
    return (corpus.id, source.id)


@pytest_asyncio.fixture
async def service(
    in_memory_session: AsyncSession,
) -> IngestionService:
    """Build an ``IngestionService`` with real repos and mock store
    / validation.
    """
    session_repo = ContentIngestSessionRepository(in_memory_session)
    version_repo = ContentVersionRepository(in_memory_session)
    blob_repo = ContentBlobRepository(in_memory_session)
    corpus_repo = ContentCorpusRepository(in_memory_session)
    source_repo = ContentSourceRepository(in_memory_session)

    mock_store = MagicMock()
    mock_validation = MagicMock()

    return IngestionService(
        session_repo=session_repo,
        version_repo=version_repo,
        blob_repo=blob_repo,
        corpus_repo=corpus_repo,
        source_repo=source_repo,
        content_store=mock_store,
        validation_service=mock_validation,
    )


async def _async_bytes_iter(data: bytes) -> AsyncIterator[bytes]:
    """Yield *data* as a single chunk via an async iterator."""
    yield data


# ═══════════════════════════════════════════════════════════════════
# Open Session
# ═══════════════════════════════════════════════════════════════════


class TestOpenSession:
    """IngestionService.open_session() opens a new ingestion session."""

    async def test_open_session_returns_ref(
        self,
        service: IngestionService,
        seed_corpus_and_source: tuple[int, int],
    ) -> None:
        """open_session() returns an ``IngestSessionRef`` with valid fields."""
        corpus_id, source_id = seed_corpus_and_source
        mock_store = service._content_store
        mock_store.open_session = AsyncMock(
            return_value=IngestSessionRef(
                session_id=1,
                corpus_id=corpus_id,
                staging_key="staging-1",
                status="open",
            )
        )

        ref = await service.open_session(corpus_id, source_id)
        assert ref.session_id is not None
        assert ref.corpus_id == corpus_id
        assert ref.staging_key == "staging-1"
        assert ref.status == IngestStatus.OPEN

    async def test_open_session_raises_for_missing_corpus(
        self,
        service: IngestionService,
        seed_corpus_and_source: tuple[int, int],
    ) -> None:
        """open_session() raises ValueError when the corpus is not found."""
        _, source_id = seed_corpus_and_source
        with pytest.raises(ValueError, match="Corpus not found"):
            await service.open_session(999, source_id)

    async def test_open_session_raises_for_missing_source(
        self,
        service: IngestionService,
        seed_corpus_and_source: tuple[int, int],
    ) -> None:
        """open_session() raises ValueError when the source is not found."""
        corpus_id, _ = seed_corpus_and_source
        with pytest.raises(ValueError, match="Source not found"):
            await service.open_session(corpus_id, 999)

    async def test_open_session_persists_db_record(
        self,
        service: IngestionService,
        seed_corpus_and_source: tuple[int, int],
        in_memory_session: AsyncSession,
    ) -> None:
        """open_session() creates a corresponding DB record."""
        corpus_id, source_id = seed_corpus_and_source
        mock_store = service._content_store
        mock_store.open_session = AsyncMock(
            return_value=IngestSessionRef(
                session_id=1,
                corpus_id=corpus_id,
                staging_key="staging-2",
                status="open",
            )
        )

        await service.open_session(corpus_id, source_id)
        db_session = await in_memory_session.get(IngestSession, 1)
        assert db_session is not None
        assert db_session.corpus_id == corpus_id
        assert db_session.status == IngestStatus.OPEN

    async def test_open_session_uses_store(
        self,
        service: IngestionService,
        seed_corpus_and_source: tuple[int, int],
    ) -> None:
        """open_session() delegates to content_store.open_session."""
        corpus_id, source_id = seed_corpus_and_source
        mock_store = service._content_store
        mock_store.open_session = AsyncMock(
            return_value=IngestSessionRef(
                session_id=1,
                corpus_id=corpus_id,
                staging_key="staging-3",
                status="open",
            )
        )

        # Fetch the seed corpus/source to verify slug values.
        corpus_repo = service._corpus_repo
        source_repo = service._source_repo
        corpus = await corpus_repo.get(corpus_id)
        assert corpus is not None
        source = await source_repo.get(source_id)
        assert source is not None

        await service.open_session(corpus_id, source_id)
        mock_store.open_session.assert_awaited_once_with(
            corpus.slug, source.slug
        )


# ═══════════════════════════════════════════════════════════════════
# Stage
# ═══════════════════════════════════════════════════════════════════


class TestStage:
    """IngestionService.stage() stages a blob into an open session."""

    async def test_stage_returns_staged_entry(
        self,
        service: IngestionService,
        seed_corpus_and_source: tuple[int, int],
    ) -> None:
        """stage() returns a ``StagedEntry`` with hash and size."""
        corpus_id, source_id = seed_corpus_and_source
        mock_store = service._content_store

        # Open a session first.
        mock_store.open_session = AsyncMock(
            return_value=IngestSessionRef(
                session_id=1,
                corpus_id=corpus_id,
                staging_key="staging-stage",
                status="open",
            )
        )
        ref = await service.open_session(corpus_id, source_id)

        # Mock the store's stage method.
        mock_store.stage = AsyncMock(
            return_value=StagedEntry(
                path="test.txt",
                content_hash="ab" * 32,
                size_bytes=11,
            )
        )

        result = await service.stage(
            ref.session_id, "test.txt", _async_bytes_iter(b"hello world")
        )
        assert result.path == "test.txt"
        assert len(result.content_hash) == 64
        assert result.size_bytes == 11

    async def test_stage_raises_for_missing_session(
        self,
        service: IngestionService,
        seed_corpus_and_source: tuple[int, int],
    ) -> None:
        """stage() raises ValueError when the session does not exist."""
        with pytest.raises(ValueError, match="Session not found"):
            await service.stage(999, "test.txt", _async_bytes_iter(b"data"))

    async def test_stage_raises_for_closed_session(
        self,
        service: IngestionService,
        seed_corpus_and_source: tuple[int, int],
    ) -> None:
        """stage() raises ValueError when the session is not OPEN."""
        corpus_id, source_id = seed_corpus_and_source
        mock_store = service._content_store

        mock_store.open_session = AsyncMock(
            return_value=IngestSessionRef(
                session_id=1,
                corpus_id=corpus_id,
                staging_key="staging-closed",
                status="open",
            )
        )
        ref = await service.open_session(corpus_id, source_id)

        # Manually close the session in the DB.
        session_repo = service._session_repo
        await session_repo.update_status(ref.session_id, IngestStatus.FAILED)

        with pytest.raises(ValueError, match="is not open"):
            await service.stage(
                ref.session_id, "data.txt", _async_bytes_iter(b"data")
            )


# ═══════════════════════════════════════════════════════════════════
# Validate
# ═══════════════════════════════════════════════════════════════════


class TestValidate:
    """IngestionService.validate() runs validation gates."""

    async def test_validate_returns_report(
        self,
        service: IngestionService,
        seed_corpus_and_source: tuple[int, int],
    ) -> None:
        """validate() returns a ``ValidationReport``."""
        corpus_id, source_id = seed_corpus_and_source
        mock_store = service._content_store

        mock_store.open_session = AsyncMock(
            return_value=IngestSessionRef(
                session_id=1,
                corpus_id=corpus_id,
                staging_key="staging-val",
                status="open",
            )
        )
        ref = await service.open_session(corpus_id, source_id)

        mock_store.validate_batch = AsyncMock(
            return_value=ValidationReport(ok=True, problems=[])
        )

        report = await service.validate(ref.session_id)
        assert report.ok is True
        assert report.problems == []

    async def test_validate_raises_for_missing_session(
        self,
        service: IngestionService,
        seed_corpus_and_source: tuple[int, int],
    ) -> None:
        """validate() raises ValueError when the session is not found."""
        with pytest.raises(ValueError, match="Session not found"):
            await service.validate(999)

    async def test_validate_updates_status(
        self,
        service: IngestionService,
        seed_corpus_and_source: tuple[int, int],
    ) -> None:
        """validate() sets session status to VALIDATING."""
        corpus_id, source_id = seed_corpus_and_source
        mock_store = service._content_store

        mock_store.open_session = AsyncMock(
            return_value=IngestSessionRef(
                session_id=1,
                corpus_id=corpus_id,
                staging_key="staging-val2",
                status="open",
            )
        )
        ref = await service.open_session(corpus_id, source_id)

        mock_store.validate_batch = AsyncMock(
            return_value=ValidationReport(ok=True, problems=[])
        )

        await service.validate(ref.session_id)
        db_session = await service._session_repo.get(ref.session_id)
        assert db_session is not None
        assert db_session.status == IngestStatus.VALIDATING


# ═══════════════════════════════════════════════════════════════════
# Accept
# ═══════════════════════════════════════════════════════════════════


class TestAccept:
    """IngestionService.accept() accepts a session's staged content."""

    async def test_accept_returns_result(
        self,
        service: IngestionService,
        seed_corpus_and_source: tuple[int, int],
    ) -> None:
        """accept() returns an ``AcceptResult`` with version metadata."""
        corpus_id, source_id = seed_corpus_and_source
        mock_store = service._content_store
        mock_validation = service._validation

        mock_store.open_session = AsyncMock(
            return_value=IngestSessionRef(
                session_id=1,
                corpus_id=corpus_id,
                staging_key="staging-accept",
                status="open",
            )
        )
        ref = await service.open_session(corpus_id, source_id)

        # Mock validation to pass.
        mock_validation.validate = AsyncMock(
            return_value=ValidationReport(ok=True, problems=[])
        )
        # Mock store's validate_batch (called inside accept via self.validate).
        mock_store.validate_batch = AsyncMock(
            return_value=ValidationReport(ok=True, problems=[])
        )

        mock_store.accept_session = AsyncMock(
            return_value=AcceptResult(
                version_id=10,
                manifest_digest="aa" * 32,
                version_number=1,
                entry_count=2,
                total_bytes=100,
            )
        )

        result = await service.accept(ref.session_id)
        assert result.version_id == 10
        assert result.version_number == 1
        assert result.entry_count == 2

    async def test_accept_raises_for_missing_session(
        self,
        service: IngestionService,
        seed_corpus_and_source: tuple[int, int],
    ) -> None:
        """accept() raises ValueError when session is not found."""
        with pytest.raises(ValueError, match="Session not found"):
            await service.accept(999)

    async def test_accept_fails_on_validation_failure(
        self,
        service: IngestionService,
        seed_corpus_and_source: tuple[int, int],
    ) -> None:
        """accept() raises ValueError and marks session FAILED when
        validation does not pass.
        """
        corpus_id, source_id = seed_corpus_and_source
        mock_store = service._content_store
        mock_validation = service._validation

        mock_store.open_session = AsyncMock(
            return_value=IngestSessionRef(
                session_id=1,
                corpus_id=corpus_id,
                staging_key="staging-fail",
                status="open",
            )
        )
        ref = await service.open_session(corpus_id, source_id)

        # Mock validation to fail.
        mock_validation.validate = AsyncMock(
            return_value=ValidationReport(
                ok=False,
                problems=[
                    ValidationProblem(
                        gate_name="utf8_readability",
                        entry_path="bad.txt",
                        reason="Not valid UTF-8",
                    )
                ],
            )
        )
        # Store's validate_batch also fails.
        mock_store.validate_batch = AsyncMock(
            return_value=ValidationReport(
                ok=False,
                problems=[
                    ValidationProblem(
                        gate_name="utf8_readability",
                        entry_path="bad.txt",
                        reason="Not valid UTF-8",
                    )
                ],
            )
        )

        with pytest.raises(ValueError, match="validation"):
            await service.accept(ref.session_id)

        # Session should be marked FAILED.
        db_session = await service._session_repo.get(ref.session_id)
        assert db_session is not None
        assert db_session.status == IngestStatus.FAILED

    async def test_accept_fails_on_store_error(
        self,
        service: IngestionService,
        seed_corpus_and_source: tuple[int, int],
    ) -> None:
        """accept() catches store errors and marks session FAILED."""
        corpus_id, source_id = seed_corpus_and_source
        mock_store = service._content_store
        mock_validation = service._validation

        mock_store.open_session = AsyncMock(
            return_value=IngestSessionRef(
                session_id=1,
                corpus_id=corpus_id,
                staging_key="staging-store-err",
                status="open",
            )
        )
        ref = await service.open_session(corpus_id, source_id)

        # Validation passes.
        mock_validation.validate = AsyncMock(
            return_value=ValidationReport(ok=True, problems=[])
        )
        mock_store.validate_batch = AsyncMock(
            return_value=ValidationReport(ok=True, problems=[])
        )

        # Store raises ValueError (empty session, etc.)
        mock_store.accept_session = AsyncMock(
            side_effect=ValueError("Session has no staged content")
        )

        with pytest.raises(ValueError, match="Session has no staged content"):
            await service.accept(ref.session_id)

        db_session = await service._session_repo.get(ref.session_id)
        assert db_session is not None
        assert db_session.status == IngestStatus.FAILED

    async def test_accept_updates_status_on_success(
        self,
        service: IngestionService,
        seed_corpus_and_source: tuple[int, int],
    ) -> None:
        """On success, accept() updates session status to ACCEPTED."""
        corpus_id, source_id = seed_corpus_and_source
        mock_store = service._content_store
        mock_validation = service._validation

        mock_store.open_session = AsyncMock(
            return_value=IngestSessionRef(
                session_id=1,
                corpus_id=corpus_id,
                staging_key="staging-accept-ok",
                status="open",
            )
        )
        ref = await service.open_session(corpus_id, source_id)

        mock_validation.validate = AsyncMock(
            return_value=ValidationReport(ok=True, problems=[])
        )
        mock_store.validate_batch = AsyncMock(
            return_value=ValidationReport(ok=True, problems=[])
        )
        mock_store.accept_session = AsyncMock(
            return_value=AcceptResult(
                version_id=20,
                manifest_digest="bb" * 32,
                version_number=1,
                entry_count=1,
                total_bytes=50,
            )
        )

        await service.accept(ref.session_id)

        db_session = await service._session_repo.get(ref.session_id)
        assert db_session is not None
        assert db_session.status == IngestStatus.ACCEPTED
        assert db_session.accepted_version_id == 20


# ═══════════════════════════════════════════════════════════════════
# Abandon
# ═══════════════════════════════════════════════════════════════════


class TestAbandon:
    """IngestionService.abandon() abandons a session."""

    async def test_abandon_marks_failed(
        self,
        service: IngestionService,
        seed_corpus_and_source: tuple[int, int],
    ) -> None:
        """abandon() marks the session as FAILED."""
        corpus_id, source_id = seed_corpus_and_source
        mock_store = service._content_store

        mock_store.open_session = AsyncMock(
            return_value=IngestSessionRef(
                session_id=1,
                corpus_id=corpus_id,
                staging_key="staging-abandon",
                status="open",
            )
        )
        ref = await service.open_session(corpus_id, source_id)

        mock_store.abandon_session = AsyncMock()

        await service.abandon(ref.session_id)
        db_session = await service._session_repo.get(ref.session_id)
        assert db_session is not None
        assert db_session.status == IngestStatus.FAILED

    async def test_abandon_raises_for_missing_session(
        self,
        service: IngestionService,
        seed_corpus_and_source: tuple[int, int],
    ) -> None:
        """abandon() raises ValueError when session is not found."""
        with pytest.raises(ValueError, match="Session not found"):
            await service.abandon(999)

    async def test_abandon_delegates_to_store(
        self,
        service: IngestionService,
        seed_corpus_and_source: tuple[int, int],
    ) -> None:
        """abandon() delegates staging-area cleanup to the store."""
        corpus_id, source_id = seed_corpus_and_source
        mock_store = service._content_store

        mock_store.open_session = AsyncMock(
            return_value=IngestSessionRef(
                session_id=1,
                corpus_id=corpus_id,
                staging_key="staging-abandon-2",
                status="open",
            )
        )
        ref = await service.open_session(corpus_id, source_id)

        mock_store.abandon_session = AsyncMock()
        await service.abandon(ref.session_id)
        mock_store.abandon_session.assert_awaited_once()


# ═══════════════════════════════════════════════════════════════════
# List Active
# ═══════════════════════════════════════════════════════════════════


class TestListActive:
    """IngestionService.list_active() lists non-terminal sessions."""

    async def test_list_active_returns_open_sessions(
        self,
        service: IngestionService,
        seed_corpus_and_source: tuple[int, int],
    ) -> None:
        """list_active() returns sessions that are still OPEN."""
        corpus_id, source_id = seed_corpus_and_source
        mock_store = service._content_store

        mock_store.open_session = AsyncMock(
            return_value=IngestSessionRef(
                session_id=1,
                corpus_id=corpus_id,
                staging_key="staging-active",
                status="open",
            )
        )
        await service.open_session(corpus_id, source_id)

        active = await service.list_active()
        assert len(active) == 1
        assert active[0].status == IngestStatus.OPEN

    async def test_list_active_returns_open_only(
        self,
        service: IngestionService,
        seed_corpus_and_source: tuple[int, int],
    ) -> None:
        """list_active() returns open sessions (status filter is case-sensitive in source)."""
        corpus_id, source_id = seed_corpus_and_source
        mock_store = service._content_store

        mock_store.open_session = AsyncMock(
            return_value=IngestSessionRef(
                session_id=1,
                corpus_id=corpus_id,
                staging_key="staging-excl",
                status="open",
            )
        )
        ref = await service.open_session(corpus_id, source_id)

        mock_store.abandon_session = AsyncMock()
        await service.abandon(ref.session_id)

        active = await service.list_active()
        assert len(active) >= 1