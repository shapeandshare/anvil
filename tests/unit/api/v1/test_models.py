"""Tests for external model API endpoints.

Covers /v1/models/* routes against a mocked workbench.
"""

from __future__ import annotations

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
