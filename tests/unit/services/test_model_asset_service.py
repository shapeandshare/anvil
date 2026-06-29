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


def _safetensors_bytes() -> bytes:
    """Return a minimal valid safetensors byte payload for format detection."""
    import struct

    header = b'{"__metadata__":{}}'
    return struct.pack("<Q", len(header)) + header + b"\x00\x00"


def _wire_download_service(
    tmp_path,
    file_list: list[dict[str, str]],
    download_bytes: bytes,
):
    """Build a ModelAssetService with a real store + mocked HF source."""
    from anvil.storage.local import LocalFileStore

    store = LocalFileStore(str(tmp_path / "storage"))

    mock_model = MagicMock()
    mock_model.id = 1
    mock_model.source_identifier = "test/model"
    mock_model.revision_sha = "main"
    mock_model_repo = MagicMock()
    mock_model_repo.get = AsyncMock(return_value=mock_model)
    mock_model_repo.update_fields = AsyncMock()

    mock_job = MagicMock()
    mock_job.id = 42
    mock_job.external_model_id = 1
    mock_job_repo = MagicMock()
    mock_job_repo.get = AsyncMock(return_value=mock_job)
    mock_job_repo.update_status = AsyncMock(return_value=mock_job)

    created_assets: list[ModelAsset] = []

    def _add(
        asset: ModelAsset,
    ) -> ModelAsset:  # noqa: RUF100  # used as AsyncMock side_effect
        asset.id = len(created_assets) + 1
        asset.downloaded_bytes = 0
        asset.sha256 = None
        asset.storage_path = None
        created_assets.append(asset)
        return asset

    statuses: dict[int, str] = {}

    def _update_status(
        asset_id, status, **kwargs
    ):  # noqa: RUF100  # used as AsyncMock side_effect
        statuses[asset_id] = status
        return MagicMock()

    mock_asset_repo = MagicMock()
    mock_asset_repo.add = AsyncMock(side_effect=_add)
    mock_asset_repo.update_status = AsyncMock(side_effect=_update_status)
    mock_asset_repo.update_progress = AsyncMock()

    download_file = tmp_path / "downloaded.safetensors"
    download_file.write_bytes(download_bytes)

    mock_hf = MagicMock()
    mock_hf.list_asset_files = AsyncMock(return_value=file_list)
    mock_hf.download_asset_to_path = AsyncMock(return_value=str(download_file))

    svc = ModelAssetService(
        model_asset_repo=mock_asset_repo,
        asset_download_job_repo=mock_job_repo,
        external_model_repo=mock_model_repo,
        store=store,
        hf_source=mock_hf,
    )
    return svc, mock_job_repo, mock_model_repo, statuses


class TestRunDownload:
    """run_download() real download, hashing, storage, and state transitions."""

    @pytest.mark.asyncio
    async def test_run_download_success_stores_and_hashes(self, tmp_path) -> None:
        payload = _safetensors_bytes()
        svc, job_repo, model_repo, statuses = _wire_download_service(
            tmp_path,
            [{"asset_type": "weights", "filename": "model.safetensors"}],
            payload,
        )

        await svc.run_download(42)

        last = job_repo.update_status.call_args_list[-1]
        assert last[0][1] == str(AssetDownloadJobStatus.COMPLETE)
        assert statuses[1] == str(ModelAssetStatus.AVAILABLE)

        import hashlib

        expected_sha = hashlib.sha256(payload).hexdigest()
        stored = tmp_path / "storage" / "models" / "1" / "assets" / expected_sha
        assert (stored / "model.safetensors").exists()

        model_repo.update_fields.assert_any_call(
            1, asset_availability=str(AssetState.ASSETS_AVAILABLE)
        )

    @pytest.mark.asyncio
    async def test_run_download_rejects_bad_format(self, tmp_path) -> None:
        pickle_bytes = b"\x80\x04\x95abcdefgh"
        svc, job_repo, model_repo, statuses = _wire_download_service(
            tmp_path,
            [{"asset_type": "weights", "filename": "model.safetensors"}],
            pickle_bytes,
        )

        await svc.run_download(42)

        last = job_repo.update_status.call_args_list[-1]
        assert last[0][1] == str(AssetDownloadJobStatus.FAILED)
        assert statuses[1] == str(ModelAssetStatus.UNAVAILABLE)
        model_repo.update_fields.assert_any_call(
            1, asset_availability=str(AssetState.METADATA_ONLY)
        )

    @pytest.mark.asyncio
    async def test_run_download_job_not_found(self) -> None:
        svc = _make_service()
        svc._job_repo.get = AsyncMock(return_value=None)
        await svc.run_download(999)

    @pytest.mark.asyncio
    async def test_run_download_no_hf_source_fails(self) -> None:
        svc = _make_service()
        mock_job = MagicMock()
        mock_job.id = 42
        mock_job.external_model_id = 1
        svc._job_repo.get = AsyncMock(return_value=mock_job)
        svc._job_repo.update_status = AsyncMock(return_value=mock_job)
        mock_model = MagicMock()
        mock_model.id = 1
        svc._model_repo.get = AsyncMock(return_value=mock_model)

        await svc.run_download(42)

        last = svc._job_repo.update_status.call_args_list[-1]
        assert last[0][1] == str(AssetDownloadJobStatus.FAILED)
        assert last.kwargs["error_code"] == "missing_extra"

    @pytest.mark.asyncio
    async def test_run_download_empty_file_list_fails(self, tmp_path) -> None:
        svc, job_repo, _model_repo, _ = _wire_download_service(tmp_path, [], b"")

        await svc.run_download(42)

        last = job_repo.update_status.call_args_list[-1]
        assert last[0][1] == str(AssetDownloadJobStatus.FAILED)
        assert last.kwargs["error_code"] == "no_assets"
