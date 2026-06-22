# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for ValidationService — content ingestion validation gates.

Tests each gate independently by mocking the ``aiofiles.open`` and
``content_db_session.execute`` dependencies so no real filesystem or
database is needed.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from anvil.services.content.staged_entry import StagedEntry
from anvil.services.content.validation_report import ValidationProblem
from anvil.services.content.validation_service import ValidationService


@pytest_asyncio.fixture
async def service() -> ValidationService:
    """Provide a fresh ``ValidationService`` for each test."""
    return ValidationService()


@pytest_asyncio.fixture
def mock_db_session() -> MagicMock:
    """Provide a mock ``AsyncSession`` for DB-backed validation gates."""
    return MagicMock(spec=AsyncSession)


def _entry(
    path: str = "doc.txt",
    content_hash: str = "aa" * 32,
    size_bytes: int = 100,
) -> StagedEntry:
    """Convenience factory for ``StagedEntry`` instances."""
    return StagedEntry(path=path, content_hash=content_hash, size_bytes=size_bytes)


# ═══════════════════════════════════════════════════════════════════
# Full validate pass
# ═══════════════════════════════════════════════════════════════════


class TestValidatePass:
    """The top-level validate() method passes for valid entries."""

    async def test_valid_entry_passes_all_gates(
        self, service: ValidationService, mock_db_session: MagicMock
    ) -> None:
        """A valid entry with no problems produces ``ok=True``."""
        entry = _entry()

        with patch("anvil.services.content.validation_service.async_open") as mock_open:
            mock_file = AsyncMock()
            mock_file.__aenter__.return_value.read = AsyncMock(
                return_value=b"Hello, World!"
            )
            mock_open.return_value = mock_file

            # Mock cross-corpus dedup query to return no duplicates.
            mock_result = MagicMock()
            mock_result.fetchall.return_value = []
            mock_db_session.execute = AsyncMock(return_value=mock_result)

            report = await service.validate(
                [entry],
                content_db_session=mock_db_session,
                content_dir="/tmp/content",
                corpus_slug="test-corpus",
            )

        assert report.ok is True
        assert len(report.problems) == 0


# ═══════════════════════════════════════════════════════════════════
# UTF-8 readability gate
# ═══════════════════════════════════════════════════════════════════


class TestUTF8Gate:
    """Gate 1 — each blob must decode cleanly as UTF-8 text."""

    async def test_utf8_valid_passes(
        self, service: ValidationService, mock_db_session: MagicMock
    ) -> None:
        """Valid UTF-8 content passes the gate."""
        entry = _entry()

        with patch("anvil.services.content.validation_service.async_open") as mock_open:
            mock_file = AsyncMock()
            mock_file.__aenter__.return_value.read = AsyncMock(
                return_value="café".encode("utf-8")
            )
            mock_open.return_value = mock_file

            mock_result = MagicMock()
            mock_result.fetchall.return_value = []
            mock_db_session.execute = AsyncMock(return_value=mock_result)

            report = await service.validate(
                [entry],
                content_db_session=mock_db_session,
                content_dir="/tmp/content",
                corpus_slug="test-corpus",
            )

        assert report.ok is True

    async def test_utf8_invalid_fails(
        self, service: ValidationService, mock_db_session: MagicMock
    ) -> None:
        """Invalid UTF-8 content produces a problem."""
        entry = _entry()

        with patch("anvil.services.content.validation_service.async_open") as mock_open:
            mock_file = AsyncMock()
            mock_file.__aenter__.return_value.read = AsyncMock(
                return_value=b"\xff\xfe\x00\x01"
            )
            mock_open.return_value = mock_file

            mock_result = MagicMock()
            mock_result.fetchall.return_value = []
            mock_db_session.execute = AsyncMock(return_value=mock_result)

            report = await service.validate(
                [entry],
                content_db_session=mock_db_session,
                content_dir="/tmp/content",
                corpus_slug="test-corpus",
            )

        assert report.ok is False
        problem = report.problems[0]
        assert problem.gate_name == "utf8_readability"
        assert problem.entry_path == "doc.txt"

    async def test_utf8_file_not_found(
        self, service: ValidationService, mock_db_session: MagicMock
    ) -> None:
        """A missing blob file produces a problem."""
        entry = _entry()

        with patch("anvil.services.content.validation_service.async_open") as mock_open:
            mock_open.side_effect = FileNotFoundError("No such file")

            mock_result = MagicMock()
            mock_result.fetchall.return_value = []
            mock_db_session.execute = AsyncMock(return_value=mock_result)

            report = await service.validate(
                [entry],
                content_db_session=mock_db_session,
                content_dir="/tmp/content",
                corpus_slug="test-corpus",
            )

        assert report.ok is False
        problem = report.problems[0]
        assert problem.gate_name == "utf8_readability"
        assert "Blob file not found" in problem.reason


# ═══════════════════════════════════════════════════════════════════
# Size bounds gate
# ═══════════════════════════════════════════════════════════════════


class TestSizeGate:
    """Gate 2 — no single entry may exceed 100 MiB."""

    async def test_small_entry_passes(
        self, service: ValidationService, mock_db_session: MagicMock
    ) -> None:
        """A small entry passes the size gate."""
        entry = _entry(size_bytes=1024)

        with patch("anvil.services.content.validation_service.async_open") as mock_open:
            mock_file = AsyncMock()
            mock_file.__aenter__.return_value.read = AsyncMock(
                return_value=b"small"
            )
            mock_open.return_value = mock_file

            mock_result = MagicMock()
            mock_result.fetchall.return_value = []
            mock_db_session.execute = AsyncMock(return_value=mock_result)

            report = await service.validate(
                [entry],
                content_db_session=mock_db_session,
                content_dir="/tmp/content",
                corpus_slug="test-corpus",
            )

        assert report.ok is True

    async def test_oversized_entry_fails(
        self, service: ValidationService, mock_db_session: MagicMock
    ) -> None:
        """An entry larger than 100 MiB fails the size gate."""
        hundred_mib = 100 * 1024 * 1024
        entry = _entry(size_bytes=hundred_mib + 1)

        with patch("anvil.services.content.validation_service.async_open") as mock_open:
            mock_file = AsyncMock()
            mock_file.__aenter__.return_value.read = AsyncMock(return_value=b"big")
            mock_open.return_value = mock_file

            mock_result = MagicMock()
            mock_result.fetchall.return_value = []
            mock_db_session.execute = AsyncMock(return_value=mock_result)

            report = await service.validate(
                [entry],
                content_db_session=mock_db_session,
                content_dir="/tmp/content",
                corpus_slug="test-corpus",
            )

        assert report.ok is False
        assert report.problems[0].gate_name == "size_limit"


# ═══════════════════════════════════════════════════════════════════
# Provenance metadata gate
# ═══════════════════════════════════════════════════════════════════


class TestProvenanceGate:
    """Gate 3 — each entry must have non-empty path and content_hash."""

    async def test_empty_path_fails(
        self, service: ValidationService, mock_db_session: MagicMock
    ) -> None:
        """An entry with an empty path fails provenance check."""
        entry = _entry(path="  ", content_hash="aa" * 32)

        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        with patch("anvil.services.content.validation_service.async_open") as mock_open:
            mock_file = AsyncMock()
            mock_file.__aenter__.return_value.read = AsyncMock(return_value=b"data")
            mock_open.return_value = mock_file

            report = await service.validate(
                [entry],
                content_db_session=mock_db_session,
                content_dir="/tmp/content",
                corpus_slug="test-corpus",
            )

        problem = next(p for p in report.problems if p.gate_name == "provenance_metadata")
        assert "path" in problem.reason

    async def test_empty_hash_fails(
        self, service: ValidationService, mock_db_session: MagicMock
    ) -> None:
        """An entry with an empty content_hash fails provenance check."""
        entry = _entry(path="doc.txt", content_hash="  ")

        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        with patch("anvil.services.content.validation_service.async_open") as mock_open:
            mock_file = AsyncMock()
            mock_file.__aenter__.return_value.read = AsyncMock(return_value=b"data")
            mock_open.return_value = mock_file

            report = await service.validate(
                [entry],
                content_db_session=mock_db_session,
                content_dir="/tmp/content",
                corpus_slug="test-corpus",
            )

        problem = next(
            p for p in report.problems if p.gate_name == "provenance_metadata"
        )
        assert "content_hash" in problem.reason


# ═══════════════════════════════════════════════════════════════════
# Intra-batch dedup gate
# ═══════════════════════════════════════════════════════════════════


class TestIntraBatchDedupGate:
    """Gate 4 — no two entries may share the same content_hash."""

    async def test_duplicate_hash_fails(
        self, service: ValidationService, mock_db_session: MagicMock
    ) -> None:
        """Two entries with the same hash in the same batch fail dedup."""
        entries = [
            _entry(path="a.txt", content_hash="dd" * 32),
            _entry(path="b.txt", content_hash="dd" * 32),
        ]

        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        with patch("anvil.services.content.validation_service.async_open") as mock_open:
            mock_file = AsyncMock()
            mock_file.__aenter__.return_value.read = AsyncMock(return_value=b"data")
            mock_open.return_value = mock_file

            report = await service.validate(
                entries,
                content_db_session=mock_db_session,
                content_dir="/tmp/content",
                corpus_slug="test-corpus",
            )

        dedup_problems = [p for p in report.problems if p.gate_name == "intra_batch_dedup"]
        assert len(dedup_problems) == 1
        assert dedup_problems[0].entry_path == "b.txt"

    async def test_unique_hashes_pass(
        self, service: ValidationService, mock_db_session: MagicMock
    ) -> None:
        """Entries with unique hashes pass the dedup gate."""
        entries = [
            _entry(path="a.txt", content_hash="e1" * 32),
            _entry(path="b.txt", content_hash="e2" * 32),
        ]

        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        with patch("anvil.services.content.validation_service.async_open") as mock_open:
            mock_file = AsyncMock()
            mock_file.__aenter__.return_value.read = AsyncMock(return_value=b"data")
            mock_open.return_value = mock_file

            report = await service.validate(
                entries,
                content_db_session=mock_db_session,
                content_dir="/tmp/content",
                corpus_slug="test-corpus",
            )

        dedup_problems = [p for p in report.problems if p.gate_name == "intra_batch_dedup"]
        assert len(dedup_problems) == 0


# ═══════════════════════════════════════════════════════════════════
# Cross-corpus dedup gate
# ═══════════════════════════════════════════════════════════════════


class TestCrossCorpusDedupGate:
    """Gate 5 — cross-corpus exact dedup produces warnings."""

    async def test_existing_hash_produces_warning(
        self, service: ValidationService, mock_db_session: MagicMock
    ) -> None:
        """An existing content hash produces a warning-level problem."""
        entry = _entry(content_hash="ff" * 32)

        # Mock the DB query to return the hash as already existing.
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [("ff" * 32,)]
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        with patch("anvil.services.content.validation_service.async_open") as mock_open:
            mock_file = AsyncMock()
            mock_file.__aenter__.return_value.read = AsyncMock(return_value=b"data")
            mock_open.return_value = mock_file

            report = await service.validate(
                [entry],
                content_db_session=mock_db_session,
                content_dir="/tmp/content",
                corpus_slug="test-corpus",
            )

        dedup_problems = [
            p for p in report.problems if p.gate_name == "cross_corpus_dedup"
        ]
        assert len(dedup_problems) == 1
        assert dedup_problems[0].severity == "warning"

    async def test_new_hash_no_warning(
        self, service: ValidationService, mock_db_session: MagicMock
    ) -> None:
        """A new content hash does not produce a warning."""
        entry = _entry(content_hash="00" * 32)

        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        with patch("anvil.services.content.validation_service.async_open") as mock_open:
            mock_file = AsyncMock()
            mock_file.__aenter__.return_value.read = AsyncMock(return_value=b"data")
            mock_open.return_value = mock_file

            report = await service.validate(
                [entry],
                content_db_session=mock_db_session,
                content_dir="/tmp/content",
                corpus_slug="test-corpus",
            )

        dedup_problems = [
            p for p in report.problems if p.gate_name == "cross_corpus_dedup"
        ]
        assert len(dedup_problems) == 0


# ═══════════════════════════════════════════════════════════════════
# Language allowlist gate
# ═══════════════════════════════════════════════════════════════════


class TestLanguageGate:
    """Gate 6 — rejects content with characters beyond U+00FF."""

    async def test_latin_only_passes(
        self, service: ValidationService, mock_db_session: MagicMock
    ) -> None:
        """Content within the Latin-1 range passes the language gate."""
        entry = _entry()

        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        with patch.object(service, "_read_blob_content") as mock_read:
            mock_read.return_value = b"Hello, World! cafe"

            report = await service.validate(
                [entry],
                content_db_session=mock_db_session,
                content_dir="/tmp/content",
                corpus_slug="test-corpus",
            )

        lang_problems = [
            p for p in report.problems if p.gate_name == "language_allowlist"
        ]
        assert len(lang_problems) == 0

    async def test_non_latin_fails(
        self, service: ValidationService, mock_db_session: MagicMock
    ) -> None:
        """Content with non-Latin characters fails the language gate."""
        entry = _entry()
        non_latin = "Hello \u4e2d\u6587 world".encode("utf-8")

        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        with patch.object(service, "_read_blob_content") as mock_read:
            mock_read.return_value = non_latin

            report = await service.validate(
                [entry],
                content_db_session=mock_db_session,
                content_dir="/tmp/content",
                corpus_slug="test-corpus",
            )

        lang_problems = [
            p for p in report.problems if p.gate_name == "language_allowlist"
        ]
        assert len(lang_problems) == 1

    async def test_missing_blob_skips_language_check(
        self, service: ValidationService, mock_db_session: MagicMock
    ) -> None:
        """When a blob file is missing, the language check is skipped."""
        entry = _entry()

        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        with patch.object(service, "_read_blob_content") as mock_read:
            mock_read.return_value = None

            report = await service.validate(
                [entry],
                content_db_session=mock_db_session,
                content_dir="/tmp/content",
                corpus_slug="test-corpus",
            )

        lang_problems = [
            p for p in report.problems if p.gate_name == "language_allowlist"
        ]
        assert len(lang_problems) == 0


# ═══════════════════════════════════════════════════════════════════
# Sensitive-info scan gate
# ═══════════════════════════════════════════════════════════════════


class TestSensitiveInfoGate:
    """Gate 7 — scans for credit card, email, and SSN patterns."""

    async def test_clean_content_passes(
        self, service: ValidationService, mock_db_session: MagicMock
    ) -> None:
        """Content with no sensitive patterns passes the gate."""
        entry = _entry()

        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        with patch.object(service, "_read_blob_content") as mock_read:
            mock_read.return_value = b"This is clean content with no secrets."

            report = await service.validate(
                [entry],
                content_db_session=mock_db_session,
                content_dir="/tmp/content",
                corpus_slug="test-corpus",
            )

        sensitive_problems = [
            p for p in report.problems if p.gate_name == "sensitive_info"
        ]
        assert len(sensitive_problems) == 0

    async def test_credit_card_detected(
        self, service: ValidationService, mock_db_session: MagicMock
    ) -> None:
        """Content with a credit card number is flagged."""
        entry = _entry()

        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        with patch.object(service, "_read_blob_content") as mock_read:
            mock_read.return_value = b"Card: 4111-1111-1111-1111"

            report = await service.validate(
                [entry],
                content_db_session=mock_db_session,
                content_dir="/tmp/content",
                corpus_slug="test-corpus",
            )

        sensitive_problems = [
            p for p in report.problems if p.gate_name == "sensitive_info"
        ]
        assert len(sensitive_problems) >= 1
        assert "credit_card" in sensitive_problems[0].reason

    async def test_email_detected(
        self, service: ValidationService, mock_db_session: MagicMock
    ) -> None:
        """Content with an email address is flagged."""
        entry = _entry()

        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        with patch.object(service, "_read_blob_content") as mock_read:
            mock_read.return_value = b"Contact: user@example.com"

            report = await service.validate(
                [entry],
                content_db_session=mock_db_session,
                content_dir="/tmp/content",
                corpus_slug="test-corpus",
            )

        sensitive_problems = [
            p for p in report.problems if p.gate_name == "sensitive_info"
        ]
        assert len(sensitive_problems) >= 1
        assert "email" in sensitive_problems[0].reason

    async def test_ssn_detected(
        self, service: ValidationService, mock_db_session: MagicMock
    ) -> None:
        """Content with a US SSN is flagged."""
        entry = _entry()

        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        with patch.object(service, "_read_blob_content") as mock_read:
            mock_read.return_value = b"SSN: 123-45-6789"

            report = await service.validate(
                [entry],
                content_db_session=mock_db_session,
                content_dir="/tmp/content",
                corpus_slug="test-corpus",
            )

        sensitive_problems = [
            p for p in report.problems if p.gate_name == "sensitive_info"
        ]
        assert len(sensitive_problems) >= 1
        assert "ssn" in sensitive_problems[0].reason

    async def test_missing_blob_skips_sensitive_scan(
        self, service: ValidationService, mock_db_session: MagicMock
    ) -> None:
        """When a blob file is missing, the sensitive-info scan is skipped."""
        entry = _entry()

        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        with patch.object(service, "_read_blob_content") as mock_read:
            mock_read.return_value = None

            report = await service.validate(
                [entry],
                content_db_session=mock_db_session,
                content_dir="/tmp/content",
                corpus_slug="test-corpus",
            )

        sensitive_problems = [
            p for p in report.problems if p.gate_name == "sensitive_info"
        ]
        assert len(sensitive_problems) == 0