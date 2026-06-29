"""Unit tests for ModelAssetService — submit, run, and status polling."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from anvil.db.models.asset_download_job import AssetDownloadJob
from anvil.db.models.model_asset import ModelAsset, ModelAssetStatus
from anvil.services._shared.asset_download_job_status import AssetDownloadJobStatus
from anvil.services._shared.asset_state import AssetState
from anvil.services.model_import.model_asset_service import (
    DuplicateDownloadError,
    ModelAssetAlreadyAvailableError,
    ModelAssetService,
    ModelNotFoundError,
)


def _make_service(
    model_exists: bool = True,
    asset_availability: str = AssetState.METADATA_ONLY,
    has_active_job: bool = False,
) -> ModelAssetService:
    """Create a ModelAssetService with mocked dependencies."""
    mock_model_repo = MagicMock()
    mock_model = MagicMock()
    mock_model.id = 1
    mock_model.asset_availability = asset_availability
    if model_exists:
        mock_model_repo.get = AsyncMock(return_value=mock_model)
    else:
        mock_model_repo.get = AsyncMock(return_value=None)
    mock_model_repo.update_fields = AsyncMock()

    mock_job_repo = MagicMock()
    mock_job_repo.get_active_for_model = AsyncMock(return_value=has_active_job)

    mock_asset_repo = MagicMock()
    mock_store = AsyncMock()

    svc = ModelAssetService(
        model_asset_repo=mock_asset_repo,
        asset_download_job_repo=mock_job_repo,
        external_model_repo=mock_model_repo,
        store=mock_store,
    )
    mock_job = AssetDownloadJob(
        external_model_id=1,
        status=str(AssetDownloadJobStatus.QUEUED),
    )
    mock_job.id = 42
    mock_job_repo.add = AsyncMock(return_value=mock_job)

    return svc


class TestSubmitDownload:
    """submit_download() gating logic."""

    @pytest.mark.asyncio
    async def test_submit_happy_path(self) -> None:
        svc = _make_service()
        job_id = await svc.submit_download(1)
        assert job_id == 42

    @pytest.mark.asyncio
    async def test_submit_model_not_found(self) -> None:
        svc = _make_service(model_exists=False)
        with pytest.raises(ModelNotFoundError):
            await svc.submit_download(1)

    @pytest.mark.asyncio
    async def test_submit_already_available(self) -> None:
        svc = _make_service(asset_availability=AssetState.ASSETS_AVAILABLE)
        with pytest.raises(ModelAssetAlreadyAvailableError):
            await svc.submit_download(1)

    @pytest.mark.asyncio
    async def test_submit_duplicate_job(self) -> None:
        svc = _make_service(has_active_job=True)
        with pytest.raises(DuplicateDownloadError):
            await svc.submit_download(1)


class TestGetJobStatus:
    """get_job_status() aggregate and per-asset progress."""

    @pytest.mark.asyncio
    async def test_status_job_not_found(self) -> None:
        svc = _make_service()
        svc._job_repo.get = AsyncMock(return_value=None)
        result = await svc.get_job_status(99)
        assert result is None

    @pytest.mark.asyncio
    async def test_status_with_assets(self) -> None:
        svc = _make_service()

        mock_job = MagicMock()
        mock_job.id = 42
        mock_job.status = str(AssetDownloadJobStatus.COMPLETE)
        mock_job.external_model_id = 1
        mock_job.started_at = datetime(2026, 6, 28, 12, 0, 0, tzinfo=UTC)
        mock_job.finished_at = datetime(2026, 6, 28, 12, 1, 0, tzinfo=UTC)
        mock_job.error_code = None
        mock_job.error_message = None
        svc._job_repo.get = AsyncMock(return_value=mock_job)

        asset1 = MagicMock(spec=ModelAsset)
        asset1.id = 10
        asset1.asset_type = "weights"
        asset1.filename = "model.safetensors"
        asset1.status = "available"
        asset1.size_bytes = 1000
        asset1.downloaded_bytes = 1000
        asset1.sha256 = "abc"

        asset2 = MagicMock(spec=ModelAsset)
        asset2.id = 11
        asset2.asset_type = "config"
        asset2.filename = "config.json"
        asset2.status = "available"
        asset2.size_bytes = 500
        asset2.downloaded_bytes = 500
        asset2.sha256 = "def"

        svc._asset_repo.get_by_model = AsyncMock(return_value=[asset1, asset2])

        result = await svc.get_job_status(42)
        assert result is not None
        assert result["job_id"] == 42
        assert result["total_assets"] == 2
        assert result["completed_assets"] == 2
        assert len(result["assets"]) == 2

    @pytest.mark.asyncio
    async def test_status_partial_progress(self) -> None:
        svc = _make_service()

        mock_job = MagicMock()
        mock_job.id = 43
        mock_job.status = str(AssetDownloadJobStatus.DOWNLOADING)
        mock_job.external_model_id = 1
        mock_job.started_at = datetime(2026, 6, 28, 12, 0, 0, tzinfo=UTC)
        mock_job.finished_at = None
        mock_job.error_code = None
        mock_job.error_message = None
        svc._job_repo.get = AsyncMock(return_value=mock_job)

        asset1 = MagicMock(spec=ModelAsset)
        asset1.id = 10
        asset1.asset_type = "weights"
        asset1.filename = "model-00001-of-00002.safetensors"
        asset1.status = "available"
        asset1.size_bytes = 1000
        asset1.downloaded_bytes = 1000
        asset1.sha256 = "abc"

        asset2 = MagicMock(spec=ModelAsset)
        asset2.id = 11
        asset2.asset_type = "weights"
        asset2.filename = "model-00002-of-00002.safetensors"
        asset2.status = "downloading"
        asset2.size_bytes = 2000
        asset2.downloaded_bytes = 500
        asset2.sha256 = None

        svc._asset_repo.get_by_model = AsyncMock(return_value=[asset1, asset2])

        result = await svc.get_job_status(43)
        assert result["total_assets"] == 2
        assert result["completed_assets"] == 1
        assert result["assets"][1]["downloaded_bytes"] == 500
        assert result["assets"][1]["sha256"] is None


class TestRunDownload:
    """run_download() state transitions."""

    @pytest.mark.asyncio
    async def test_run_download_success(self) -> None:
        svc = _make_service()

        mock_job = MagicMock()
        mock_job.id = 42
        mock_job.external_model_id = 1
        mock_job.status = str(AssetDownloadJobStatus.QUEUED)

        svc._job_repo.get = AsyncMock(return_value=mock_job)
        svc._job_repo.update_status = AsyncMock(return_value=mock_job)

        mock_model = MagicMock()
        mock_model.id = 1
        svc._model_repo.get = AsyncMock(return_value=mock_model)

        asset = MagicMock(spec=ModelAsset)
        asset.id = 10
        asset.filename = "model.safetensors"
        asset.size_bytes = 1000
        svc._asset_repo.get_by_model = AsyncMock(return_value=[asset])
        svc._asset_repo.update_status = AsyncMock(return_value=asset)
        svc._asset_repo.update_progress = AsyncMock()

        await svc.run_download(42)

        update_calls = svc._job_repo.update_status.call_args_list
        last_args = update_calls[-1]
        assert last_args[0][1] == str(AssetDownloadJobStatus.COMPLETE)

    @pytest.mark.asyncio
    async def test_run_download_job_not_found(self) -> None:
        svc = _make_service()
        svc._job_repo.get = AsyncMock(return_value=None)
        await svc.run_download(999)

    @pytest.mark.asyncio
    async def test_run_download_asset_skipped(self) -> None:
        svc = _make_service()

        mock_job = MagicMock()
        mock_job.id = 42
        mock_job.external_model_id = 1
        mock_job.status = str(AssetDownloadJobStatus.QUEUED)

        svc._job_repo.get = AsyncMock(return_value=mock_job)
        svc._job_repo.update_status = AsyncMock(return_value=mock_job)

        mock_model = MagicMock()
        mock_model.id = 1
        svc._model_repo.get = AsyncMock(return_value=mock_model)

        # Create a fresh mock repo with explicit AsyncMocks for asset methods
        asset_mock = MagicMock()
        asset_mock.id = 10
        asset_mock.filename = "model.safetensors"
        asset_mock.size_bytes = 1000
        asset_mock.status = None

        mock_asset_repo = MagicMock()
        mock_asset_repo.get_by_model = AsyncMock(return_value=[asset_mock])
        mock_asset_repo.update_status = AsyncMock(return_value=None)
        mock_asset_repo.update_progress = AsyncMock()
        svc._asset_repo = mock_asset_repo

        await svc.run_download(42)

        update_calls = svc._job_repo.update_status.call_args_list
        last_args = update_calls[-1]
        assert last_args[0][1] == str(AssetDownloadJobStatus.COMPLETE)
