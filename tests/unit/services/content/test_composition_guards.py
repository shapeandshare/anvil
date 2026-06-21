"""Unit tests for CompositionService composition guards (T070).

Tests that ``CompositionService`` raises ``ValueError`` for:
- Empty composition spec (no entries)
- All-zero-weight composition spec (sum of weights ≤ 0)

Uses mocked dependencies since this is a unit-level verification of
the guard logic (which runs before any DB or store interaction in
:meth:`CompositionService.freeze` and :meth:`CompositionService.validate_spec`).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from anvil.db.repositories.content_corpora import ContentCorpusRepository
from anvil.db.repositories.content_versions import ContentVersionRepository
from anvil.services.content.composition_service import CompositionService
from anvil.services.content.versioned_content_store import VersionedContentStore


@pytest.fixture
def service() -> CompositionService:
    """Provide a ``CompositionService`` backed by fully mocked dependencies.

    The guards in ``validate_spec()`` and ``freeze()`` operate on the
    ``spec`` parameter before any async store/DB interaction, so the
    mock details do not affect these tests.
    """
    store = MagicMock(spec=VersionedContentStore)
    version_repo = MagicMock(spec=ContentVersionRepository)
    corpus_repo = MagicMock(spec=ContentCorpusRepository)
    db_session = AsyncMock(spec=AsyncSession)
    return CompositionService(
        store=store,
        version_repo=version_repo,
        corpus_repo=corpus_repo,
        db_session=db_session,
    )


class TestCompositionValidateSpec:
    """Tests for ``CompositionService.validate_spec()``."""

    def test_rejects_empty_spec(self, service: CompositionService) -> None:
        """Empty spec raises ``ValueError``."""
        with pytest.raises(ValueError, match="must not be empty"):
            service.validate_spec([])

    def test_rejects_all_zero_weights(self, service: CompositionService) -> None:
        """All entries with ``weight=0.0`` raises ``ValueError``."""
        spec = [
            {"content_hash": "aa" * 32, "weight": 0.0},
            {"content_hash": "bb" * 32, "weight": 0.0},
        ]
        with pytest.raises(ValueError, match=r"weights.*sum.*positive"):
            service.validate_spec(spec)

    def test_accepts_valid_spec(self, service: CompositionService) -> None:
        """A valid spec (non-empty, positive total weight) passes."""
        spec = [
            {"content_hash": "aa" * 32, "weight": 0.7},
            {"content_hash": "bb" * 32, "weight": 0.3},
        ]
        # Should not raise.
        service.validate_spec(spec)

    def test_accepts_single_entry(self, service: CompositionService) -> None:
        """A single entry with non-zero weight is valid."""
        spec = [
            {"content_hash": "cc" * 32, "weight": 1.0},
        ]
        service.validate_spec(spec)

    def test_mixed_zero_and_nonzero_weights_ok(
        self,
        service: CompositionService,
    ) -> None:
        """Mixed weights (some zero, some non-zero) are valid."""
        spec = [
            {"content_hash": "dd" * 32, "weight": 0.0},
            {"content_hash": "ee" * 32, "weight": 1.0},
        ]
        service.validate_spec(spec)

    def test_negative_sum_raises(self, service: CompositionService) -> None:
        """Negative total weight raises ``ValueError``."""
        spec = [
            {"content_hash": "ff" * 32, "weight": -0.5},
            {"content_hash": "gg" * 32, "weight": -0.5},
        ]
        with pytest.raises(ValueError, match=r"weights.*sum.*positive"):
            service.validate_spec(spec)


class TestCompositionFreezeGuards:
    """Tests that ``CompositionService.freeze()`` rejects invalid specs
    before any DB or store interaction.
    """

    async def test_freeze_rejects_empty_spec(
        self,
        service: CompositionService,
    ) -> None:
        """Freeze with empty spec raises ``ValueError`` (guard runs first)."""
        with pytest.raises(ValueError, match="must not be empty"):
            await service.freeze(1, [])

    async def test_freeze_rejects_all_zero_weights(
        self,
        service: CompositionService,
    ) -> None:
        """Freeze with all-zero-weight spec raises ``ValueError``."""
        spec = [
            {"content_hash": "aa" * 32, "weight": 0.0},
            {"content_hash": "bb" * 32, "weight": 0.0},
        ]
        with pytest.raises(ValueError, match=r"weights.*sum.*positive"):
            await service.freeze(1, spec)

    async def test_freeze_rejects_negative_sum(
        self,
        service: CompositionService,
    ) -> None:
        """Freeze with negative total weight raises ``ValueError``."""
        spec = [
            {"content_hash": "cc" * 32, "weight": -1.0},
            {"content_hash": "dd" * 32, "weight": -1.0},
        ]
        with pytest.raises(ValueError, match=r"weights.*sum.*positive"):
            await service.freeze(1, spec)
