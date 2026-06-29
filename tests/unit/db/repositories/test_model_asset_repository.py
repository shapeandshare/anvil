"""Unit tests for the ModelAsset repository."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from anvil.db.models.model_asset import ModelAsset, ModelAssetStatus, ModelAssetType
from anvil.db.repositories.model_asset_repository import ModelAssetRepository


@pytest.fixture
def sample_asset() -> ModelAsset:
    return ModelAsset(
        external_model_id=1,
        asset_type=str(ModelAssetType.WEIGHTS),
        filename="model.safetensors",
        size_bytes=1000,
    )


@pytest.mark.asyncio
async def test_add_and_get_by_model(in_memory_session: AsyncSession) -> None:
    repo = ModelAssetRepository(in_memory_session)
    asset = ModelAsset(
        external_model_id=1,
        asset_type=str(ModelAssetType.CONFIG),
        filename="config.json",
        size_bytes=500,
    )
    saved = await repo.add(asset)
    assert saved.id is not None

    assets = await repo.get_by_model(1)
    assert len(assets) == 1
    assert assets[0].filename == "config.json"
    assert assets[0].status == str(ModelAssetStatus.PENDING)


@pytest.mark.asyncio
async def test_get_by_model_and_type(in_memory_session: AsyncSession) -> None:
    repo = ModelAssetRepository(in_memory_session)
    w1 = await repo.add(
        ModelAsset(
            external_model_id=1,
            asset_type=str(ModelAssetType.WEIGHTS),
            filename="model-00001-of-00002.safetensors",
            size_bytes=500,
        )
    )
    await repo.add(
        ModelAsset(
            external_model_id=1,
            asset_type=str(ModelAssetType.TOKENIZER),
            filename="tokenizer.json",
            size_bytes=100,
        )
    )

    weights = await repo.get_by_model_and_type(
        1, str(ModelAssetType.WEIGHTS)
    )
    assert len(weights) == 1
    assert weights[0].filename == "model-00001-of-00002.safetensors"


@pytest.mark.asyncio
async def test_update_status(in_memory_session: AsyncSession) -> None:
    repo = ModelAssetRepository(in_memory_session)
    asset = await repo.add(
        ModelAsset(
            external_model_id=1,
            asset_type=str(ModelAssetType.CONFIG),
            filename="config.json",
            size_bytes=500,
        )
    )
    updated = await repo.update_status(
        asset.id,
        str(ModelAssetStatus.AVAILABLE),
        sha256="abc123",
        storage_path="models/1/assets/abc123/config.json",
    )
    assert updated is not None
    assert updated.status == str(ModelAssetStatus.AVAILABLE)
    assert updated.sha256 == "abc123"
    assert updated.storage_path == "models/1/assets/abc123/config.json"


@pytest.mark.asyncio
async def test_update_progress(in_memory_session: AsyncSession) -> None:
    repo = ModelAssetRepository(in_memory_session)
    asset = await repo.add(
        ModelAsset(
            external_model_id=1,
            asset_type=str(ModelAssetType.WEIGHTS),
            filename="model.safetensors",
            size_bytes=1000,
        )
    )
    updated = await repo.update_progress(asset.id, 500)
    assert updated is not None
    assert updated.downloaded_bytes == 500


@pytest.mark.asyncio
async def test_update_status_nonexistent(in_memory_session: AsyncSession) -> None:
    repo = ModelAssetRepository(in_memory_session)
    result = await repo.update_status(99999, str(ModelAssetStatus.AVAILABLE))
    assert result is None