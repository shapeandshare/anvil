"""Unit tests for CompositionService.preview() (T068).

Tests the per-source token/byte contribution analysis provided by
``CompositionService.preview()``.  The repository and DB session
dependencies are mocked since this is a unit-level verification of
the preview aggregation logic.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from anvil.db.models.content_blob import ContentBlob
from anvil.db.repositories.content_corpora import ContentCorpusRepository
from anvil.db.repositories.content_versions import ContentVersionRepository
from anvil.services.content.composition_service import CompositionService
from anvil.services.content.versioned_content_store import VersionedContentStore


@pytest.fixture
def mock_corpus() -> MagicMock:
    """Provide a mock corpus model with a known slug and id."""
    corpus = MagicMock()
    corpus.id = 1
    corpus.slug = "test-corpus"
    corpus.name = "Test Corpus"
    return corpus


@pytest.fixture
def mock_corpus_repo(mock_corpus: MagicMock) -> MagicMock:
    """Provide a mock ``ContentCorpusRepository`` that returns the fixture corpus."""
    repo = MagicMock(spec=ContentCorpusRepository)
    repo.get = AsyncMock(return_value=mock_corpus)
    return repo


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Provide a mock async DB session for blob-size lookups.

    Returns ``None`` for every ``scalar_one_or_none()`` call by default
    (blob not found → size_bytes=0).  Tests that need non-zero sizes
    can override the mock.
    """
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None

    session = AsyncMock(spec=AsyncSession)
    session.execute = AsyncMock(return_value=mock_result)
    return session


@pytest.fixture
def mock_store() -> MagicMock:
    """Provide a mocked ``VersionedContentStore``."""
    store = MagicMock(spec=VersionedContentStore)
    store.open_session = AsyncMock()
    store.stage = AsyncMock()
    store.validate_batch = AsyncMock()
    store.accept_session = AsyncMock()
    store.freeze_version = AsyncMock()
    store.resolve = AsyncMock()
    store.open_blob = AsyncMock()
    store.revert = AsyncMock()
    store.ensure_corpus = AsyncMock()
    store.abandon_session = AsyncMock()
    store.tag_version = AsyncMock()
    store.resolve_by_tag = AsyncMock()
    return store


@pytest.fixture
def service(
    mock_store: MagicMock,
    mock_corpus_repo: MagicMock,
    mock_db_session: AsyncMock,
) -> CompositionService:
    """Provide a ``CompositionService`` backed by fully mocked dependencies."""
    version_repo = MagicMock(spec=ContentVersionRepository)
    return CompositionService(
        store=mock_store,
        version_repo=version_repo,
        corpus_repo=mock_corpus_repo,
        db_session=mock_db_session,
    )


class TestCompositionPreview:
    """Tests for ``CompositionService.preview()``."""

    async def test_preview_returns_per_entry_stats(
        self,
        service: CompositionService,
        mock_db_session: AsyncMock,
    ) -> None:
        """Preview returns a ``sources`` list with one entry per spec item."""
        # Mock: all blobs return 100 bytes.
        mock_result = MagicMock()
        blob = MagicMock(spec=ContentBlob)
        blob.size_bytes = 100
        mock_result.scalar_one_or_none.return_value = blob
        mock_db_session.execute.return_value = mock_result

        spec = [
            {"content_hash": "aa" * 32, "weight": 0.7},
            {"content_hash": "bb" * 32, "weight": 0.3},
        ]
        preview = await service.preview(1, spec)

        assert "sources" in preview
        assert len(preview["sources"]) == 2
        assert preview["sources"][0]["weight"] == 0.7
        assert preview["sources"][1]["weight"] == 0.3
        # Both blobs have the same size (100 bytes).
        assert preview["sources"][0]["bytes"] == 100
        assert preview["sources"][1]["bytes"] == 100
        assert preview["total_bytes"] == 200

    async def test_preview_computes_total_bytes(
        self,
        service: CompositionService,
        mock_db_session: AsyncMock,
    ) -> None:
        """``total_bytes`` sums per-entry blob sizes."""
        # Mock: each blob returns 100 bytes.
        mock_result = MagicMock()
        blob = MagicMock(spec=ContentBlob)
        blob.size_bytes = 100
        mock_result.scalar_one_or_none.return_value = blob
        mock_db_session.execute.return_value = mock_result

        spec = [
            {"content_hash": "cc" * 32, "weight": 0.5},
            {"content_hash": "dd" * 32, "weight": 0.5},
            {"content_hash": "ee" * 32, "weight": 0.5},
        ]
        preview = await service.preview(1, spec)

        assert preview["total_bytes"] == 300

    async def test_preview_computes_total_tokens(
        self,
        service: CompositionService,
        mock_db_session: AsyncMock,
    ) -> None:
        """``total_tokens`` equals ``total_bytes // 4``."""
        mock_result = MagicMock()
        blob = MagicMock(spec=ContentBlob)
        blob.size_bytes = 100
        mock_result.scalar_one_or_none.return_value = blob
        mock_db_session.execute.return_value = mock_result

        spec = [
            {"content_hash": "ff" * 32, "weight": 1.0},
            {"content_hash": "gg" * 32, "weight": 1.0},
        ]
        preview = await service.preview(1, spec)

        assert preview["total_tokens"] == 50  # 200 // 4

    async def test_preview_missing_blob_returns_zero_bytes(
        self,
        service: CompositionService,
        mock_db_session: AsyncMock,
    ) -> None:
        """When a blob hash does not exist in the DB, its size is 0."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        spec = [
            {"content_hash": "zz" * 32, "weight": 1.0},
        ]
        preview = await service.preview(1, spec)

        assert preview["sources"][0]["bytes"] == 0
        assert preview["total_bytes"] == 0
        assert preview["total_tokens"] == 0

    async def test_preview_raises_on_missing_corpus(
        self,
        mock_store: MagicMock,
        mock_db_session: AsyncMock,
    ) -> None:
        """Preview raises ``ValueError`` when the corpus is not found."""
        missing_repo = MagicMock(spec=ContentCorpusRepository)
        missing_repo.get = AsyncMock(return_value=None)
        version_repo = MagicMock(spec=ContentVersionRepository)

        svc = CompositionService(
            store=mock_store,
            version_repo=version_repo,
            corpus_repo=missing_repo,
            db_session=mock_db_session,
        )

        with pytest.raises(ValueError, match="Corpus not found"):
            await svc.preview(999, [{"content_hash": "aa" * 32, "weight": 1.0}])

    async def test_preview_structure_contains_expected_keys(
        self,
        service: CompositionService,
        mock_db_session: AsyncMock,
    ) -> None:
        """Preview dict has the expected top-level keys."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        preview = await service.preview(
            1,
            [{"content_hash": "aa" * 32, "weight": 0.5}],
        )

        assert set(preview.keys()) == {"sources", "total_bytes", "total_tokens"}
