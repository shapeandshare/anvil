"""Tests for external model API endpoints.

Covers /v1/models/* routes against a mocked workbench.
"""

from __future__ import annotations

from datetime import UTC, datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from anvil.api.app import app
from anvil.api.deps import get_workbench
from anvil.services._shared.model_import_job_status import ModelImportJobStatus


@pytest.fixture
def mock_workbench():
    wb = MagicMock()
    wb.model_imports = MagicMock()
    return wb


@pytest.fixture
def override_dep(mock_workbench):
    app.dependency_overrides[get_workbench] = lambda: mock_workbench
    yield
    app.dependency_overrides.clear()


class TestImportModel:
    async def test_import_hf(self, client, mock_workbench, override_dep):
        mock_workbench.model_imports.submit_import = AsyncMock(return_value=42)
        resp = await client.post(
            "/v1/models/import",
            json={
                "source": "huggingface",
                "identifier": "org/model",
                "revision": "main",
            },
        )
        assert resp.status_code == 202
        assert resp.json()["job_id"] == 42
        assert resp.json()["status"] == "queued"

    async def test_import_invalid_source(self, client, mock_workbench, override_dep):
        mock_workbench.model_imports.submit_import = AsyncMock(
            side_effect=ValueError("Invalid source")
        )
        resp = await client.post(
            "/v1/models/import",
            json={"source": "invalid", "identifier": "x"},
        )
        assert resp.status_code == 422

    async def test_import_validates_fields(self, client, mock_workbench, override_dep):
        resp = await client.post("/v1/models/import", json={})
        assert resp.status_code == 422


class TestImportJobStatus:
    async def test_job_found(self, client, mock_workbench, override_dep):
        mock_job = MagicMock()
        mock_job.id = 1
        mock_job.status = ModelImportJobStatus.COMPLETE.value
        mock_job.started_at = None
        mock_job.finished_at = None
        mock_job.error_code = None
        mock_job.error_message = None
        mock_job.external_model_id = None
        mock_workbench.model_imports.get_job_status = AsyncMock(return_value=mock_job)

        resp = await client.get("/v1/models/import/1/status")
        assert resp.status_code == 200
        assert resp.json()["status"] == "complete"

    async def test_job_not_found(self, client, mock_workbench, override_dep):
        mock_workbench.model_imports.get_job_status = AsyncMock(return_value=None)
        resp = await client.get("/v1/models/import/999/status")
        assert resp.status_code == 404


class TestListExternalModels:
    async def test_list_models(self, client, mock_workbench, override_dep):
        m = MagicMock()
        m.id = 1
        m.display_name = "test-model"
        m.source_type = "huggingface"
        m.source_identifier = "org/model"
        m.architecture_family = "llama"
        m.parameter_count = 100_000_000
        m.license = "MIT"
        m.tokenizer_family = "bpe"
        m.revision_sha = "abc123"
        m.runnable_status = "runnable"
        m.asset_availability = "available"
        m.created_at = MagicMock()
        m.created_at.isoformat.return_value = "2026-06-01T00:00:00"
        mock_workbench.model_imports.list_external_models = AsyncMock(return_value=[m])

        resp = await client.get("/v1/models/external")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 1
        assert data[0]["display_name"] == "test-model"


class TestGetExternalModel:
    async def test_get_found(self, client, mock_workbench, override_dep):
        m = MagicMock()
        m.id = 1
        m.display_name = "test-model"
        m.source_type = "huggingface"
        m.source_identifier = "org/model"
        m.architecture_family = "llama"
        m.parameter_count = 100_000_000
        m.license = "MIT"
        m.tokenizer_family = "bpe"
        m.revision_sha = "abc123"
        m.runnable_status = "runnable"
        m.runnable_reason = None
        m.asset_availability = "available"
        m.config_json = "{}"
        m.created_at = MagicMock()
        m.created_at.isoformat.return_value = "2026-06-01T00:00:00"
        m.updated_at = MagicMock()
        m.updated_at.isoformat.return_value = "2026-06-01T00:00:00"
        mock_workbench.model_imports.get_external_model = AsyncMock(return_value=m)

        resp = await client.get("/v1/models/external/1")
        assert resp.status_code == 200
        assert resp.json()["display_name"] == "test-model"

    async def test_get_not_found(self, client, mock_workbench, override_dep):
        mock_workbench.model_imports.get_external_model = AsyncMock(return_value=None)
        resp = await client.get("/v1/models/external/999")
        assert resp.status_code == 404


class TestDeleteExternalModel:
    async def test_delete_found(self, client, mock_workbench, override_dep):
        mock_model = MagicMock()
        mock_model.id = 1
        mock_model.display_name = "test-model"
        mock_workbench.external_model_repo = MagicMock()
        mock_workbench.external_model_repo.get = AsyncMock(return_value=mock_model)
        mock_workbench.session = AsyncMock()
        mock_workbench.session.execute = AsyncMock()
        mock_workbench.session.commit = AsyncMock()
        mock_workbench.model_imports.delete_external_model = AsyncMock()
        mock_workbench.model_asset_repo = MagicMock()
        mock_workbench.model_store = MagicMock()

        resp = await client.delete("/v1/models/external/1")
        assert resp.status_code == 200
        assert "deleted" in resp.json()["message"]
        mock_workbench.external_model_repo.get.assert_awaited_once_with(1)
        mock_workbench.model_imports.delete_external_model.assert_awaited_once()
        mock_workbench.session.commit.assert_awaited_once()

    async def test_delete_not_found(self, client, mock_workbench, override_dep):
        mock_workbench.external_model_repo = MagicMock()
        mock_workbench.external_model_repo.get = AsyncMock(return_value=None)

        resp = await client.delete("/v1/models/external/999")
        assert resp.status_code == 404

    async def test_delete_with_assets(self, client, mock_workbench, override_dep):
        mock_model = MagicMock()
        mock_model.id = 1
        mock_model.display_name = "test-model"
        mock_workbench.external_model_repo = MagicMock()
        mock_workbench.external_model_repo.get = AsyncMock(return_value=mock_model)
        mock_workbench.session = AsyncMock()
        mock_workbench.session.execute = AsyncMock()
        mock_workbench.session.commit = AsyncMock()
        mock_workbench.model_imports.delete_external_model = AsyncMock()
        mock_workbench.model_asset_repo = MagicMock()
        mock_workbench.model_store = MagicMock()

        resp = await client.delete("/v1/models/external/1")
        assert resp.status_code == 200
        mock_workbench.session.execute.assert_awaited()
        mock_workbench.model_imports.delete_external_model.assert_awaited_with(
            1,
            model_asset_repo=mock_workbench.model_asset_repo,
            store=mock_workbench.model_store,
        )


########################################################################
# GET /v1/models/import/jobs
########################################################################


class TestListImportJobs:
    """Tests for GET /v1/models/import/jobs."""

    @staticmethod
    def _make_job(job_id: int, status: str = "complete") -> MagicMock:
        j = MagicMock()
        j.id = job_id
        j.status = status
        j.source_type = "huggingface"
        j.source_identifier = "org/model"
        j.revision = "main"
        j.started_at = datetime.now(UTC)
        j.finished_at = datetime.now(UTC)
        j.error_code = None
        j.error_message = None
        j.external_model_id = None
        j.created_at = datetime.now(UTC)
        return j

    async def test_list_jobs_empty(self, client, mock_workbench, override_dep):
        """Returns empty list when no jobs exist."""
        mock_workbench.model_imports.list_jobs = AsyncMock(return_value=[])

        resp = await client.get("/v1/models/import/jobs")

        assert resp.status_code == 200
        assert resp.json()["data"] == []

    async def test_list_jobs_with_external_model(
        self, client, mock_workbench, override_dep
    ):
        """Includes asset_availability when external_model_id is set."""
        job = self._make_job(job_id=1)
        job.external_model_id = 10
        mock_workbench.model_imports.list_jobs = AsyncMock(return_value=[job])
        mock_model = MagicMock()
        mock_model.asset_availability = "available"
        mock_workbench.external_model_repo = MagicMock()
        mock_workbench.external_model_repo.get = AsyncMock(return_value=mock_model)

        resp = await client.get("/v1/models/import/jobs")

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 1
        assert data[0]["asset_availability"] == "available"

    async def test_list_jobs_with_pending_assets(
        self, client, mock_workbench, override_dep
    ):
        """Includes download progress when assets are pending."""
        job = self._make_job(job_id=1)
        job.external_model_id = 10
        mock_workbench.model_imports.list_jobs = AsyncMock(return_value=[job])
        mock_model = MagicMock()
        mock_model.asset_availability = "assets_pending"
        mock_workbench.external_model_repo = MagicMock()
        mock_workbench.external_model_repo.get = AsyncMock(return_value=mock_model)
        mock_asset = MagicMock()
        mock_asset.downloaded_bytes = 50
        mock_asset.size_bytes = 100
        mock_workbench.model_asset_repo = MagicMock()
        mock_workbench.model_asset_repo.get_by_model = AsyncMock(
            return_value=[mock_asset]
        )

        resp = await client.get("/v1/models/import/jobs")

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data[0]["downloaded_bytes"] == 50
        assert data[0]["total_bytes"] == 100


########################################################################
# POST /v1/models/import/{job_id}/retry
########################################################################


class TestRetryImportJob:
    """Tests for POST /v1/models/import/{job_id}/retry."""

    async def test_retry_success(self, client, mock_workbench, override_dep):
        """Returns 202 with new job ID."""
        mock_workbench.model_imports.retry_import = AsyncMock(return_value=42)

        resp = await client.post("/v1/models/import/1/retry")

        assert resp.status_code == 202
        data = resp.json()
        assert data["job_id"] == 42
        assert data["status"] == "queued"
        mock_workbench.model_imports.retry_import.assert_awaited_with(1)

    async def test_retry_not_found(self, client, mock_workbench, override_dep):
        """Returns 404 when original job not found."""
        mock_workbench.model_imports.retry_import = AsyncMock(
            side_effect=ValueError("Job not found"),
        )

        resp = await client.post("/v1/models/import/999/retry")

        assert resp.status_code == 404


########################################################################
# POST /v1/models/{model_id}/download
########################################################################


class TestDownloadModelAssets:
    """Tests for POST /v1/models/{model_id}/download."""

    async def test_download_success(self, client, mock_workbench, override_dep):
        """Returns 202 with job_id."""
        mock_workbench.model_assets = MagicMock()
        mock_workbench.model_assets.submit_download = AsyncMock(return_value=42)

        resp = await client.post("/v1/models/1/download")

        assert resp.status_code == 202
        data = resp.json()
        assert data["job_id"] == 42
        assert data["status"] == "queued"

    async def test_download_model_not_found(self, client, mock_workbench, override_dep):
        """Returns 404 when model not found."""
        from anvil.services.model_import.model_asset_service import ModelNotFoundError

        mock_workbench.model_assets = MagicMock()
        mock_workbench.model_assets.submit_download = AsyncMock(
            side_effect=ModelNotFoundError("Model 999 not found"),
        )

        resp = await client.post("/v1/models/999/download")

        assert resp.status_code == 404

    async def test_download_already_available(
        self, client, mock_workbench, override_dep
    ):
        """Returns 409 when assets already available."""
        from anvil.services.model_import.model_asset_service import (
            ModelAssetAlreadyAvailableError,
        )

        mock_workbench.model_assets = MagicMock()
        mock_workbench.model_assets.submit_download = AsyncMock(
            side_effect=ModelAssetAlreadyAvailableError("Assets already available"),
        )

        resp = await client.post("/v1/models/1/download")

        assert resp.status_code == 409

    async def test_download_duplicate(self, client, mock_workbench, override_dep):
        """Returns 409 when download already in progress."""
        from anvil.services.model_import.model_asset_service import (
            DuplicateDownloadError,
        )

        mock_workbench.model_assets = MagicMock()
        mock_workbench.model_assets.submit_download = AsyncMock(
            side_effect=DuplicateDownloadError("Download already in progress"),
        )

        resp = await client.post("/v1/models/1/download")

        assert resp.status_code == 409


########################################################################
# GET /v1/models/{model_id}/download/{job_id}/status
########################################################################


class TestAssetDownloadStatus:
    """Tests for GET /v1/models/{model_id}/download/{job_id}/status."""

    async def test_status_found(self, client, mock_workbench, override_dep):
        """Returns download job status."""
        mock_workbench.model_assets = MagicMock()
        mock_workbench.model_assets.get_job_status = AsyncMock(
            return_value={"job_id": 1, "status": "downloading"},
        )

        resp = await client.get("/v1/models/1/download/1/status")

        assert resp.status_code == 200
        data = resp.json()
        assert data["job_id"] == 1
        assert data["status"] == "downloading"

    async def test_status_not_found(self, client, mock_workbench, override_dep):
        """Returns 404 when download job not found."""
        mock_workbench.model_assets = MagicMock()
        mock_workbench.model_assets.get_job_status = AsyncMock(return_value=None)

        resp = await client.get("/v1/models/1/download/999/status")

        assert resp.status_code == 404
        assert "Download job not found" in resp.json()["detail"]


########################################################################
# GET /v1/models/{model_id}/assets
########################################################################


class TestListModelAssets:
    """Tests for GET /v1/models/{model_id}/assets."""

    async def test_list_assets(self, client, mock_workbench, override_dep):
        """Returns model assets list."""
        mock_asset = MagicMock()
        mock_asset.id = 1
        mock_asset.asset_type = "model"
        mock_asset.filename = "model.safetensors"
        mock_asset.status = "downloaded"
        mock_asset.size_bytes = 1000
        mock_asset.downloaded_bytes = 1000
        mock_asset.sha256 = "abc123"
        mock_asset.format = "safetensors"
        mock_asset.created_at = datetime.now(UTC)

        mock_workbench.model_assets = MagicMock()
        mock_workbench.model_assets.get_assets_for_model = AsyncMock(
            return_value=[mock_asset],
        )

        resp = await client.get("/v1/models/1/assets")

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 1
        assert data[0]["asset_type"] == "model"
        assert data[0]["filename"] == "model.safetensors"

    async def test_list_assets_empty(self, client, mock_workbench, override_dep):
        """Returns empty list when no assets exist."""
        mock_workbench.model_assets = MagicMock()
        mock_workbench.model_assets.get_assets_for_model = AsyncMock(return_value=[])

        resp = await client.get("/v1/models/1/assets")

        assert resp.status_code == 200
        assert resp.json()["data"] == []
