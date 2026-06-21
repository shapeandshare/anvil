"""Unit tests for AdvisoryService (T096).

Tests the three categories of post-acceptance advisory operations:

1. ``detect_near_duplicates`` — cross-version exact hash comparison
   within the same corpus (FR-015).
2. ``refresh_derived_state`` — no-op placeholder that records a DB
   note (FR-026a).
3. ``record_acceptance_stats`` — logs and persists version statistics
   (FR-026a).

All dependencies are mocked; this is a pure unit-level verification.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from anvil.db.repositories.content_blobs import ContentBlobRepository
from anvil.db.repositories.content_ingest_sessions import (
    ContentIngestSessionRepository,
)
from anvil.db.repositories.content_versions import ContentVersionRepository
from anvil.services.content.advisory_service import AdvisoryService


@pytest.fixture
def service() -> AdvisoryService:
    """Provide an ``AdvisoryService`` backed by fully mocked dependencies.

    Each test configures the mock repos as needed before exercising the
    method under test.
    """
    version_repo = MagicMock(spec=ContentVersionRepository)
    session_repo = MagicMock(spec=ContentIngestSessionRepository)
    blob_repo = MagicMock(spec=ContentBlobRepository)
    db_session = AsyncMock(spec=AsyncSession)
    return AdvisoryService(
        version_repo=version_repo,
        session_repo=session_repo,
        blob_repo=blob_repo,
        db_session=db_session,
    )


# ── detect_near_duplicates ───────────────────────────────────────────────


class TestDetectNearDuplicates:
    """Tests for ``AdvisoryService.detect_near_duplicates()``."""

    async def test_returns_empty_when_version_not_found(
        self,
        service: AdvisoryService,
    ) -> None:
        """Version does not exist — returns empty list."""
        service._version_repo.get = AsyncMock(return_value=None)
        result = await service.detect_near_duplicates(999)
        assert result == []

    async def test_returns_empty_when_no_entries(
        self,
        service: AdvisoryService,
    ) -> None:
        """Version exists but has no entries — returns empty list."""
        version = MagicMock()
        version.corpus_id = 1
        service._version_repo.get = AsyncMock(return_value=version)
        service._version_repo.get_entries = AsyncMock(return_value=[])
        result = await service.detect_near_duplicates(1)
        assert result == []

    async def test_no_duplicates_returns_empty(
        self,
        service: AdvisoryService,
    ) -> None:
        """No other version has matching hashes — returns empty list."""
        version = MagicMock()
        version.corpus_id = 1
        entry = MagicMock()
        entry.content_hash = "aa" * 32
        entry.path = "doc1.txt"

        service._version_repo.get = AsyncMock(return_value=version)
        service._version_repo.get_entries = AsyncMock(return_value=[entry])

        scalar_result = MagicMock()
        scalar_result.scalars.return_value.all = MagicMock(return_value=[])
        service._db_session.execute = AsyncMock(return_value=scalar_result)

        result = await service.detect_near_duplicates(1)
        assert result == []

    async def test_detects_cross_version_duplicates(
        self,
        service: AdvisoryService,
    ) -> None:
        """Finds duplicate entries across versions in the same corpus."""
        version = MagicMock()
        version.corpus_id = 1

        entry = MagicMock()
        entry.content_hash = "aa" * 32
        entry.path = "current/doc1.txt"

        dup_entry = MagicMock()
        dup_entry.content_hash = "aa" * 32
        dup_entry.path = "other/doc1.txt"
        dup_entry.version_id = 42

        service._version_repo.get = AsyncMock(return_value=version)
        service._version_repo.get_entries = AsyncMock(return_value=[entry])

        scalar_result = MagicMock()
        scalar_result.scalars.return_value.all = MagicMock(
            return_value=[dup_entry]
        )
        service._db_session.execute = AsyncMock(return_value=scalar_result)

        result = await service.detect_near_duplicates(1)
        assert result == [
            {
                "entry_path": "current/doc1.txt",
                "duplicate_path": "other/doc1.txt",
                "duplicate_version_id": 42,
            }
        ]

    async def test_reports_each_current_entry_once(
        self,
        service: AdvisoryService,
    ) -> None:
        """Each entry in current version gets one flag per hash match.

        If multiple entries in the current version have the same hash,
        each is flagged individually.  If multiple other versions contain
        the same hash, only the first match is reported per entry.
        """
        version = MagicMock()
        version.corpus_id = 1

        entry_a = MagicMock()
        entry_a.content_hash = "aa" * 32
        entry_a.path = "dup1.txt"
        entry_b = MagicMock()
        entry_b.content_hash = "bb" * 32
        entry_b.path = "unique.txt"
        entry_c = MagicMock()
        entry_c.content_hash = "aa" * 32
        entry_c.path = "dup2.txt"

        dup_entry = MagicMock()
        dup_entry.content_hash = "aa" * 32
        dup_entry.path = "original.txt"
        dup_entry.version_id = 42

        service._version_repo.get = AsyncMock(return_value=version)
        service._version_repo.get_entries = AsyncMock(
            return_value=[entry_a, entry_b, entry_c]
        )

        scalar_result = MagicMock()
        scalar_result.scalars.return_value.all = MagicMock(
            return_value=[dup_entry]
        )
        service._db_session.execute = AsyncMock(return_value=scalar_result)

        result = await service.detect_near_duplicates(1)
        assert len(result) == 2
        assert result[0]["entry_path"] == "dup1.txt"
        assert result[1]["entry_path"] == "dup2.txt"


# ── refresh_derived_state ────────────────────────────────────────────────


class TestRefreshDerivedState:
    """Tests for ``AdvisoryService.refresh_derived_state()``."""

    async def test_noop_when_version_not_found(
        self,
        service: AdvisoryService,
    ) -> None:
        """Version not found — warning logged, no crash."""
        service._version_repo.get = AsyncMock(return_value=None)
        await service.refresh_derived_state(999)
        service._db_session.flush.assert_not_called()

    async def test_records_note_on_version(
        self,
        service: AdvisoryService,
    ) -> None:
        """Records a refresh note on the version's ``note`` field."""
        version = MagicMock()
        version.note = None

        service._version_repo.get = AsyncMock(return_value=version)
        service._version_repo.get_entries = AsyncMock(return_value=[])

        await service.refresh_derived_state(1)

        assert version.note is not None
        assert "derived-state refresh requested" in version.note
        assert "FR-026a" in version.note
        service._db_session.flush.assert_awaited_once()

    async def test_appends_to_existing_note(
        self,
        service: AdvisoryService,
    ) -> None:
        """Appends refresh note when version already has a note."""
        version = MagicMock()
        version.note = "Original note."

        service._version_repo.get = AsyncMock(return_value=version)

        await service.refresh_derived_state(1)

        assert "Original note." in version.note
        assert "derived-state refresh requested" in version.note


# ── record_acceptance_stats ──────────────────────────────────────────────


class TestRecordAcceptanceStats:
    """Tests for ``AdvisoryService.record_acceptance_stats()``."""

    async def test_noop_when_version_not_found(
        self,
        service: AdvisoryService,
    ) -> None:
        """Version not found — warning logged, no crash."""
        service._version_repo.get = AsyncMock(return_value=None)
        await service.record_acceptance_stats(999)
        service._db_session.flush.assert_not_called()

    @patch(
        "anvil.services.content.advisory_service.get_config",
        create=True,
    )
    @patch("anvil.services.content.advisory_service.Path", create=True)
    async def test_records_stats_on_version(
        self,
        mock_path: MagicMock,
        mock_get_config: MagicMock,
        service: AdvisoryService,
    ) -> None:
        """Records entry count and total bytes on the version."""
        mock_get_config.return_value = {"content_dir": "/tmp/content"}

        version = MagicMock()
        version.corpus_id = 1
        version.version_number = 3

        entry1 = MagicMock()
        entry1.size_bytes = 100
        entry2 = MagicMock()
        entry2.size_bytes = 200

        service._version_repo.get = AsyncMock(return_value=version)
        service._version_repo.get_entries = AsyncMock(
            return_value=[entry1, entry2]
        )

        # Prevent actual filesystem writes.
        mock_path_instance = MagicMock()
        mock_path.return_value = mock_path_instance
        mock_advisory = MagicMock()
        mock_path_instance.__truediv__.return_value = mock_advisory
        mock_stats_file = MagicMock()
        mock_advisory.__truediv__.return_value = mock_stats_file

        await service.record_acceptance_stats(1)

        assert version.entry_count == 2
        assert version.total_bytes == 300
        service._db_session.flush.assert_awaited_once()
        mock_stats_file.write_text.assert_called_once()