# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for model registry API endpoints.

Covers all routes defined in ``anvil/api/v1/registry.py``:

- ``POST   /v1/registry/models`` — register model from experiment
- ``GET    /v1/registry/models`` — list registered models
- ``GET    /v1/registry/models/{model_id}`` — get model details
- ``GET    /v1/registry/models/{model_id}/versions/{version}`` — get version
- ``DELETE /v1/registry/models/{model_id}/versions/{version}`` — delete version
- ``DELETE /v1/registry/models/{model_id}`` — delete model
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

from anvil.api.app import app
from anvil.api.v1.registry import _fmt_ts

# ── Constants ───────────────────────────────────────────────────────

_MOCK_TS_MS = 1719000000000
_MOCK_TS_STR = "2024-06-21 20:00 UTC"


# ═════════════════════════════════════════════════════════════════════
# Fixtures
# ═════════════════════════════════════════════════════════════════════


@pytest.fixture(autouse=True)
def mock_tracking_service():
    """Mock ``TrackingService`` at module level.

    ``registry.py`` instantiates ``TrackingService()`` directly inside
    every endpoint — there is no dependency injection.  We patch the
    class reference so every call returns our mock instance.
    """
    with patch("anvil.api.v1.registry.TrackingService") as cls:
        inst = MagicMock()
        cls.return_value = inst
        yield inst


@pytest.fixture(autouse=True)
def mock_mlflow_client():
    """Mock ``MlflowClient`` at module level.

    ``get_model``, ``get_version``, ``delete_version``, and
    ``delete_model`` import ``MlflowClient`` at the top of the module
    and call it directly (not through ``TrackingService``).
    """
    with patch("anvil.api.v1.registry.MlflowClient") as cls:
        inst = MagicMock()
        cls.return_value = inst
        yield inst


@pytest.fixture(autouse=True)
def mock_mlflow_uri():
    """Mock ``get_mlflow_uri`` so no real MLflow process is contacted."""
    with patch("anvil.api.v1.registry.get_mlflow_uri", return_value="http://mock:5001"):
        yield


# ═════════════════════════════════════════════════════════════════════
# Helper factories
# ═════════════════════════════════════════════════════════════════════


def _make_version(version_num: int, run_id: str = "run-abc") -> MagicMock:
    """Build a fake MLflow model-version object."""
    v = MagicMock()
    v.version = version_num
    v.run_id = run_id
    v.creation_timestamp = _MOCK_TS_MS
    v.source = f"runs:/{run_id}/model.json"
    return v


def _make_run(
    params: dict | None = None,
    metrics: dict | None = None,
    tags: dict | None = None,
) -> MagicMock:
    """Build a fake MLflow run object with plain-dict data attributes."""
    run = MagicMock()
    data = MagicMock()
    data.params = dict(params or {})
    data.metrics = dict(metrics or {})
    data.tags = dict(tags or {})
    run.data = data
    return run


def _make_registered_model(name: str = "test-model") -> MagicMock:
    """Build a fake MLflow ``RegisteredModel`` object."""
    rm = MagicMock()
    rm.name = name
    rm.description = "A test model"
    rm.creation_timestamp = _MOCK_TS_MS
    return rm


# ═════════════════════════════════════════════════════════════════════
# Unit: _fmt_ts
# ═════════════════════════════════════════════════════════════════════


class TestFmtTs:
    """``_fmt_ts`` helper."""

    def test_formats_timestamp(self) -> None:
        assert _fmt_ts(_MOCK_TS_MS) == _MOCK_TS_STR

    def test_none_returns_none(self) -> None:
        assert _fmt_ts(None) is None

    def test_invalid_returns_str(self) -> None:
        assert _fmt_ts(10**18) == str(10**18)  # beyond year 9999 → OverflowError


# ═════════════════════════════════════════════════════════════════════
# POST /v1/registry/models
# ═════════════════════════════════════════════════════════════════════


class TestRegisterModel:
    """``POST /v1/registry/models`` — register a trained model."""

    _PAYLOAD: dict = {"experiment_id": 1}

    async def test_register_success(self, client, mock_tracking_service) -> None:
        """Happy path — experiment is ``FINISHED`` with an MLflow run ID."""
        mock_tracking_service.get_experiment = AsyncMock(
            return_value={
                "id": 1,
                "status": "FINISHED",
                "mlflow_run_id": "run-abc-123",
                "params": {},
            }
        )
        mock_tracking_service.register_source_model = AsyncMock(
            return_value={
                "name": "dataset-1",
                "version": "1",
                "run_id": "run-abc-123",
                "source": "runs:/run-abc-123/model.json",
            }
        )

        resp = await client.post("/v1/registry/models", json=self._PAYLOAD)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "dataset-1"
        assert data["version"] == "1"

    async def test_experiment_not_found(self, client, mock_tracking_service) -> None:
        """Experiment does not exist → 400."""
        mock_tracking_service.get_experiment = AsyncMock(return_value=None)

        resp = await client.post("/v1/registry/models", json=self._PAYLOAD)
        assert resp.status_code == 400
        assert "Experiment not found" in resp.json()["detail"]

    async def test_experiment_not_finished(self, client, mock_tracking_service) -> None:
        """Experiment is ``RUNNING`` → 400."""
        mock_tracking_service.get_experiment = AsyncMock(
            return_value={
                "id": 1,
                "status": "RUNNING",
                "mlflow_run_id": "run-abc",
            }
        )

        resp = await client.post("/v1/registry/models", json=self._PAYLOAD)
        assert resp.status_code == 400
        assert "must be FINISHED" in resp.json()["detail"]

    async def test_experiment_no_mlflow_run(
        self, client, mock_tracking_service
    ) -> None:
        """Experiment lacks an MLflow run ID → 400."""
        mock_tracking_service.get_experiment = AsyncMock(
            return_value={
                "id": 1,
                "status": "FINISHED",
                "mlflow_run_id": None,
                "params": {},
            }
        )

        resp = await client.post("/v1/registry/models", json=self._PAYLOAD)
        assert resp.status_code == 400
        assert "MLflow run ID" in resp.json()["detail"]


# ═════════════════════════════════════════════════════════════════════
# GET /v1/registry/models
# ═════════════════════════════════════════════════════════════════════


class TestListRegisteredModels:
    """``GET /v1/registry/models`` — list registered models."""

    async def test_returns_models(self, client, mock_tracking_service) -> None:
        """Two registered models returned."""
        mock_tracking_service.list_registered_models = AsyncMock(
            return_value=[
                {"name": "model-a", "version": 1, "run_id": "r1"},
                {"name": "model-b", "version": 2, "run_id": "r2"},
            ]
        )

        resp = await client.get("/v1/registry/models")
        assert resp.status_code == 200
        data = resp.json()
        assert "models" in data
        assert len(data["models"]) == 2
        assert data["models"][0]["name"] == "model-a"

    async def test_empty_list(self, client, mock_tracking_service) -> None:
        """No models registered → empty list."""
        mock_tracking_service.list_registered_models = AsyncMock(return_value=[])

        resp = await client.get("/v1/registry/models")
        assert resp.status_code == 200
        assert resp.json() == {"models": []}

    async def test_search_param_passthrough(
        self, client, mock_tracking_service
    ) -> None:
        """``search`` query parameter forwarded to service."""
        mock_tracking_service.list_registered_models = AsyncMock(return_value=[])

        await client.get("/v1/registry/models", params={"search": "demo"})
        mock_tracking_service.list_registered_models.assert_awaited_with(search="demo")


# ═════════════════════════════════════════════════════════════════════
# GET /v1/registry/models/{model_id}
# ═════════════════════════════════════════════════════════════════════


class TestGetModel:
    """``GET /v1/registry/models/{model_id}`` — model details."""

    async def test_string_model_id(
        self, client, mock_tracking_service, mock_mlflow_client
    ) -> None:
        """String ``model_id`` used directly as the MLflow model name."""
        mock_tracking_service.list_registered_models = AsyncMock(return_value=[])
        mock_mlflow_client.get_registered_model.return_value = _make_registered_model(
            "my-model"
        )
        mock_mlflow_client.search_model_versions.return_value = []

        resp = await client.get("/v1/registry/models/my-model")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "my-model"
        assert data["versions"] == []

    async def test_integer_model_id_by_convention(
        self, client, mock_tracking_service, mock_mlflow_client
    ) -> None:
        """Integer ``model_id`` resolved via ``dataset-{id}`` / ``corpus-{id}`` convention."""
        mock_tracking_service.list_registered_models = AsyncMock(
            return_value=[
                {"name": "dataset-1", "id": 1},
                {"name": "other-model", "id": 2},
            ]
        )
        mock_mlflow_client.get_registered_model.return_value = _make_registered_model(
            "dataset-1"
        )
        mock_mlflow_client.search_model_versions.return_value = []

        resp = await client.get("/v1/registry/models/1")
        assert resp.status_code == 200
        assert resp.json()["name"] == "dataset-1"

    async def test_not_found(self, client, mock_tracking_service) -> None:
        """Integer ID that does not resolve → 404."""
        mock_tracking_service.list_registered_models = AsyncMock(return_value=[])

        resp = await client.get("/v1/registry/models/999")
        assert resp.status_code == 404
        assert "Model not found" in resp.json()["detail"]

    async def test_with_versions(
        self, client, mock_tracking_service, mock_mlflow_client
    ) -> None:
        """Versions enriched with run metadata."""
        mock_tracking_service.list_registered_models = AsyncMock(return_value=[])
        mock_mlflow_client.get_registered_model.return_value = _make_registered_model(
            "mymodel"
        )

        v1 = _make_version(1, "run-1")
        v2 = _make_version(2, "run-2")
        mock_mlflow_client.search_model_versions.return_value = [v1, v2]

        run1 = _make_run(
            params={"dataset_id": "5", "n_embd": "16"},
            metrics={"final_loss": 0.123},
            tags={
                "anvil.experiment_id": "42",
                "anvil.warm_start": "true",
                "anvil.base_model_ref": "gpt2",
            },
        )
        run2 = _make_run(
            params={"corpus_id": "3", "n_layer": "2"},
            metrics={"final_loss": 0.456},
            tags={"anvil.experiment_id": "43"},
        )

        def _get_run_side_effect(run_id: str) -> MagicMock:
            return {"run-1": run1, "run-2": run2}.get(run_id, _make_run())

        mock_mlflow_client.get_run.side_effect = _get_run_side_effect

        resp = await client.get("/v1/registry/models/mymodel")
        assert resp.status_code == 200
        data = resp.json()

        assert len(data["versions"]) == 2
        v1r = data["versions"][0]
        assert v1r["version"] == 1
        assert v1r["final_loss"] == 0.123
        assert v1r["experiment_id"] == 42
        assert v1r["lineage"] == {
            "warm_start": "true",
            "base_model_ref": "gpt2",
        }

        v2r = data["versions"][1]
        assert v2r["version"] == 2
        assert v2r["final_loss"] == 0.456
        assert v2r["experiment_id"] == 43
        assert v2r["lineage"] is None

    async def test_mlflow_client_raises(
        self, client, mock_tracking_service, mock_mlflow_client
    ) -> None:
        """MlflowClient raises → 404."""
        from mlflow.exceptions import MlflowException

        mock_tracking_service.list_registered_models = AsyncMock(return_value=[])
        mock_mlflow_client.get_registered_model.side_effect = MlflowException("nope")

        resp = await client.get("/v1/registry/models/my-model")
        assert resp.status_code == 404
        assert "Model not found" in resp.json()["detail"]


# ═════════════════════════════════════════════════════════════════════
# GET /v1/registry/models/{model_id}/versions/{version}
# ═════════════════════════════════════════════════════════════════════


class TestGetVersion:
    """``GET /v1/registry/models/{model_id}/versions/{version}``."""

    async def test_success(
        self, client, mock_tracking_service, mock_mlflow_client
    ) -> None:
        """Returns version detail with run metadata."""
        mock_tracking_service.list_registered_models = AsyncMock(return_value=[])
        v1 = _make_version(1, "run-1")
        mock_mlflow_client.search_model_versions.return_value = [v1]
        mock_mlflow_client.get_run.return_value = _make_run(
            params={"dataset_id": "5"},
            metrics={"final_loss": 0.123},
            tags={"anvil.experiment_id": "42"},
        )

        resp = await client.get("/v1/registry/models/mymodel/versions/1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["version"] == 1
        assert data["final_loss"] == 0.123
        assert data["experiment_id"] == 42

    async def test_model_not_found(self, client, mock_tracking_service) -> None:
        """Integer ID that does not resolve → 404."""
        mock_tracking_service.list_registered_models = AsyncMock(return_value=[])

        resp = await client.get("/v1/registry/models/999/versions/1")
        assert resp.status_code == 404

    async def test_version_not_found(
        self, client, mock_tracking_service, mock_mlflow_client
    ) -> None:
        """Existing model, non-existent version → 404."""
        mock_tracking_service.list_registered_models = AsyncMock(return_value=[])
        mock_mlflow_client.search_model_versions.return_value = [_make_version(1)]

        resp = await client.get("/v1/registry/models/mymodel/versions/99")
        assert resp.status_code == 404
        assert "Version not found" in resp.json()["detail"]


# ═════════════════════════════════════════════════════════════════════
# DELETE /v1/registry/models/{model_id}/versions/{version}
# ═════════════════════════════════════════════════════════════════════


class TestDeleteVersion:
    """``DELETE /v1/registry/models/{model_id}/versions/{version}``."""

    async def test_success(
        self, client, mock_tracking_service, mock_mlflow_client
    ) -> None:
        """Version deleted successfully."""
        mock_tracking_service.list_registered_models = AsyncMock(
            return_value=[{"name": "mymodel", "id": 1}]
        )

        resp = await client.delete("/v1/registry/models/mymodel/versions/1")
        assert resp.status_code == 200
        assert "deleted" in resp.json()["message"]

    async def test_model_not_found(self, client, mock_tracking_service) -> None:
        """Integer ID that does not resolve → 404."""
        mock_tracking_service.list_registered_models = AsyncMock(return_value=[])

        resp = await client.delete("/v1/registry/models/999/versions/1")
        assert resp.status_code == 404
        assert "Model not found" in resp.json()["detail"]


# ═════════════════════════════════════════════════════════════════════
# DELETE /v1/registry/models/{model_id}
# ═════════════════════════════════════════════════════════════════════


class TestDeleteModel:
    """``DELETE /v1/registry/models/{model_id}``."""

    async def test_success(
        self, client, mock_tracking_service, mock_mlflow_client
    ) -> None:
        """Model and all versions deleted."""
        mock_tracking_service.list_registered_models = AsyncMock(
            return_value=[{"name": "mymodel", "id": 1}]
        )

        resp = await client.delete("/v1/registry/models/mymodel")
        assert resp.status_code == 200
        assert "deleted" in resp.json()["message"]

    async def test_model_not_found(self, client, mock_tracking_service) -> None:
        """Integer ID that does not resolve → 404."""
        mock_tracking_service.list_registered_models = AsyncMock(return_value=[])

        resp = await client.delete("/v1/registry/models/999")
        assert resp.status_code == 404
        assert "Model not found" in resp.json()["detail"]
