"""Tests for model registry API routes.

Covers POST /v1/registry/models (register_model) which is not covered
in tests/unit/api/test_registry_detail.py (which covers GET/DELETE routes).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from anvil.api.app import app
from anvil.api.deps import get_workbench


@pytest.fixture
def mock_workbench():
    wb = MagicMock()
    wb.dataset_repo = MagicMock()
    wb.corpus_repo = MagicMock()
    return wb


@pytest.fixture
def override_dep(mock_workbench):
    app.dependency_overrides[get_workbench] = lambda: mock_workbench
    yield
    app.dependency_overrides.clear()


class TestRegisterModel:
    """Tests for POST /v1/registry/models."""

    async def test_register_success_with_dataset_name(self, client, monkeypatch):
        """Register a model from a finished experiment with dataset name."""
        from anvil.api.v1 import registry as registry_module

        mock_tracking = AsyncMock()
        mock_tracking.get_experiment.return_value = {
            "id": 42,
            "status": "FINISHED",
            "mlflow_run_id": "mlflow_run_1",
            "params": {"dataset_id": "1"},
        }
        mock_tracking.register_source_model.return_value = {
            "name": "dataset-test-data",
            "version": 1,
        }
        monkeypatch.setattr(registry_module, "TrackingService", lambda: mock_tracking)

        # Mock database session + repo to return a dataset with name
        fake_ds = MagicMock()
        fake_ds.name = "dataset-test-data"
        fake_session = AsyncMock()
        fake_session.__aenter__.return_value = fake_session
        fake_session.__aexit__.return_value = None

        mock_ds_repo = AsyncMock()
        mock_ds_repo.get.return_value = fake_ds

        with (
            patch(
                "anvil.api.v1.registry.AsyncSessionLocal",
                return_value=fake_session,
            ),
            patch(
                "anvil.api.v1.registry.DatasetRepository",
                return_value=mock_ds_repo,
            ),
        ):
            resp = await client.post(
                "/v1/registry/models",
                json={"experiment_id": 42},
            )

        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "dataset-test-data"
        assert data["version"] == 1
        mock_tracking.register_source_model.assert_called_once_with(
            run_id="mlflow_run_1",
            name="dataset-test-data",
            dataset_id=1,
            corpus_id=None,
        )

    async def test_register_success_with_corpus_name(self, client, monkeypatch):
        """Register a model from a finished experiment with corpus name."""
        from anvil.api.v1 import registry as registry_module

        mock_tracking = AsyncMock()
        mock_tracking.get_experiment.return_value = {
            "id": 43,
            "status": "FINISHED",
            "mlflow_run_id": "mlflow_run_2",
            "params": {"corpus_id": "5"},
        }
        mock_tracking.register_source_model.return_value = {
            "name": "corpus-test-corpus",
            "version": 1,
        }
        monkeypatch.setattr(registry_module, "TrackingService", lambda: mock_tracking)

        fake_corp = MagicMock()
        fake_corp.name = "corpus-test-corpus"
        fake_session = AsyncMock()
        fake_session.__aenter__.return_value = fake_session
        fake_session.__aexit__.return_value = None

        mock_corp_repo = AsyncMock()
        mock_corp_repo.get.return_value = fake_corp

        with (
            patch(
                "anvil.api.v1.registry.AsyncSessionLocal",
                return_value=fake_session,
            ),
            patch(
                "anvil.api.v1.registry.CorpusRepository",
                return_value=mock_corp_repo,
            ),
        ):
            resp = await client.post(
                "/v1/registry/models",
                json={"experiment_id": 43},
            )

        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "corpus-test-corpus"

    async def test_register_experiment_not_found(self, client, monkeypatch):
        """Returns 400 when experiment does not exist."""
        from anvil.api.v1 import registry as registry_module

        mock_tracking = AsyncMock()
        mock_tracking.get_experiment.return_value = None
        monkeypatch.setattr(registry_module, "TrackingService", lambda: mock_tracking)

        resp = await client.post(
            "/v1/registry/models",
            json={"experiment_id": 999},
        )

        assert resp.status_code == 400
        assert "Experiment not found" in resp.json()["detail"]

    async def test_register_not_finished(self, client, monkeypatch):
        """Returns 400 when experiment is not FINISHED."""
        from anvil.api.v1 import registry as registry_module

        mock_tracking = AsyncMock()
        mock_tracking.get_experiment.return_value = {
            "id": 42,
            "status": "RUNNING",
            "mlflow_run_id": "mlflow_run_1",
            "params": {},
        }
        monkeypatch.setattr(registry_module, "TrackingService", lambda: mock_tracking)

        resp = await client.post(
            "/v1/registry/models",
            json={"experiment_id": 42},
        )

        assert resp.status_code == 400
        assert "must be FINISHED" in resp.json()["detail"]

    async def test_register_no_mlflow_run_id(self, client, monkeypatch):
        """Returns 400 when experiment has no MLflow run ID."""
        from anvil.api.v1 import registry as registry_module

        mock_tracking = AsyncMock()
        mock_tracking.get_experiment.return_value = {
            "id": 42,
            "status": "FINISHED",
            "mlflow_run_id": None,
            "params": {},
        }
        monkeypatch.setattr(registry_module, "TrackingService", lambda: mock_tracking)

        resp = await client.post(
            "/v1/registry/models",
            json={"experiment_id": 42},
        )

        assert resp.status_code == 400
        assert "no MLflow run ID" in resp.json()["detail"]

    async def test_register_validates_required_fields(self, client):
        """Pydantic validation: missing experiment_id returns 422."""
        resp = await client.post(
            "/v1/registry/models",
            json={},
        )
        assert resp.status_code == 422
