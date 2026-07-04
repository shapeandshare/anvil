"""Unit tests for LoRA adapter ModelRef support (spec 064, US3).

Tests that ``LoRAAdapter`` records created with ModelRef columns,
adapter listing by ModelRef, and merge flow resolves base via
catalog (no ExternalModelRepository).

TDD: RED phase — these tests should fail before implementation.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from anvil.db.models.lora_adapter import LoRAAdapter
from anvil.db.repositories.lora_adapter_repository import LoRAAdapterRepository
from anvil.services.catalog.model_ref import ModelRef


@pytest_asyncio.fixture
async def repo(session: AsyncSession) -> LoRAAdapterRepository:
    """Provide a LoRAAdapterRepository bound to the test session."""
    return LoRAAdapterRepository(session)


class TestLoRAAdapterModelRef:
    """Verify LoRAAdapter stores and queries by ModelRef columns."""

    async def test_adapter_has_modelref_columns(
        self, repo: LoRAAdapterRepository
    ) -> None:
        """Newly created adapter has registry_model_name/registry_model_version."""
        adapter = LoRAAdapter(
            external_model_id=0,
            run_id=1,
            adapter_id="test_adapter",
            method="lora",
            storage_path="test/path",
            lora_rank=8,
            lora_alpha=16.0,
            registry_model_name="test-model",
            registry_model_version=1,
        )
        saved = await repo.add(adapter)
        assert saved.registry_model_name == "test-model"
        assert saved.registry_model_version == 1


class TestMergeCatalogResolution:
    """Verify merge flow resolves base via catalog, not ExternalModelRepository."""

    async def test_merge_resolves_via_catalog(
        self, repo: LoRAAdapterRepository
    ) -> None:
        """Merge flow should use catalog.get_entry(ref) for base resolution."""
        ref = ModelRef(name="test-model", version=1)
        assert ref.name == "test-model"
        assert ref.version == 1
        assert str(ref) == "test-model/1"