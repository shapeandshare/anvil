"""e2e tests for model asset download endpoints (spec 042)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from anvil.db.models.external_model import ExternalModel
from anvil.db.models.model_asset import ModelAsset, ModelAssetType
from anvil.db.repositories.external_models import ExternalModelRepository
from anvil.db.repositories.model_asset_repository import ModelAssetRepository
from anvil.services._shared.asset_state import AssetState
from anvil.services._shared.runnable_status import RunnableStatus
from anvil.services._shared.source_type import SourceType


@pytest.fixture
async def seeded_model(session: AsyncSession) -> int:
    """Create a metadata-only ExternalModel and return its ID."""
    repo = ExternalModelRepository(session)
    model = ExternalModel(
        display_name="Test Model",
        source_type=str(SourceType.HUGGINGFACE),
        source_identifier="test/test-model",
        architecture_family="LlamaForCausalLM",
        parameter_count=100_000,
        license="mit",
        tokenizer_family="sentencepiece",
        revision_sha="abc123",
        runnable_status=str(RunnableStatus.RUNNABLE),
        asset_availability=str(AssetState.METADATA_ONLY),
        config_json='{"architectures":["LlamaForCausalLM"]}',
    )
    saved = await repo.add(model)
    await session.commit()
    return saved.id


class TestDownloadEndpoint:
    """POST /v1/models/{model_id}/download and related endpoints."""

    @pytest.mark.asyncio
    async def test_download_submit_returns_202(
        self, client: AsyncClient, seeded_model: int
    ) -> None:
        r = await client.post(f"/v1/models/{seeded_model}/download")
        assert r.status_code == 202
        data = r.json()
        assert "job_id" in data
        assert data["status"] == "queued"

    @pytest.mark.asyncio
    async def test_download_submit_nonexistent_model(self, client: AsyncClient) -> None:
        r = await client.post("/v1/models/99999/download")
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_download_status_polling(
        self, client: AsyncClient, seeded_model: int
    ) -> None:
        r = await client.post(f"/v1/models/{seeded_model}/download")
        assert r.status_code == 202
        job_id = r.json()["job_id"]

        r = await client.get(f"/v1/models/{seeded_model}/download/{job_id}/status")
        assert r.status_code == 200
        data = r.json()
        assert data["job_id"] == job_id
        assert "status" in data

    @pytest.mark.asyncio
    async def test_download_status_not_found(
        self, client: AsyncClient, seeded_model: int
    ) -> None:
        r = await client.get(f"/v1/models/{seeded_model}/download/99999/status")
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_assets_list(
        self, client: AsyncClient, seeded_model: int, session: AsyncSession
    ) -> None:
        repo = ModelAssetRepository(session)
        await repo.add(
            ModelAsset(
                external_model_id=seeded_model,
                asset_type=str(ModelAssetType.CONFIG),
                filename="config.json",
                size_bytes=500,
            )
        )
        await session.commit()

        r = await client.get(f"/v1/models/{seeded_model}/assets")
        assert r.status_code == 200
        data = r.json()
        assert "data" in data
        assert len(data["data"]) >= 1
        assert data["data"][0]["filename"] == "config.json"

    @pytest.mark.asyncio
    async def test_download_submit_twice(
        self, client: AsyncClient, seeded_model: int
    ) -> None:
        r1 = await client.post(f"/v1/models/{seeded_model}/download")
        assert r1.status_code == 202

        r2 = await client.post(f"/v1/models/{seeded_model}/download")
        assert r2.status_code == 409
