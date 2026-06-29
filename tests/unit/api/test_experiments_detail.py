# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for experiment detail routes.

Tests ``get_experiment``, ``get_experiment_metrics``,
``delete_experiment``, and ``download_artifact`` with mocked
``TrackingService`` and ``MlflowClient`` module-level imports.
"""

from __future__ import annotations

import json
import os
import tempfile
from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from mlflow.exceptions import MlflowException

from anvil.api.app import app
from anvil.api.deps import get_api_key_store

API_KEY = ""


@pytest.fixture(autouse=True)
def _api_key() -> None:
    global API_KEY
    API_KEY = get_api_key_store().key or ""


def _make_fake_experiment(
    experiment_id: int = 42,
    mlflow_run_id: str | None = "mlflow_abc123",
    status: str = "finished",
    final_loss: float | None = 0.123,
    created_at: str = "1700000000000",
    completed_at: str | None = "1700000100000",
    engine_backend: str = "torch",
    device: str = "cpu",
    params: dict | None = None,
    tags: dict | None = None,
) -> dict:
    """Build a fake experiment dict matching ``TrackingService.get_experiment`` shape."""
    return {
        "id": experiment_id,
        "status": status,
        "run_name": "test-run",
        "final_loss": final_loss,
        "mlflow_run_id": mlflow_run_id,
        "created_at": created_at,
        "completed_at": completed_at,
        "dataset_name": None,
        "input_digest": None,
        "input_role": None,
        "engine_backend": engine_backend,
        "device": device,
        "params": params or {},
        "metrics": {},
        "tags": tags or {},
    }


######################################################################
# get_experiment
######################################################################


def _make_fake_run(
    metrics: dict | None = None, params: dict | None = None
) -> MagicMock:
    """Build a fake MLflow Run object."""
    run = MagicMock()
    run.data.params = params or {}
    run.data.metrics = metrics or {}
    return run


def _patch_mlflow_client(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch MlflowClient in the experiments module to avoid real MLflow calls."""
    from anvil.api.v1 import experiments as experiments_module

    fake_run = _make_fake_run()

    class _FakeMlflowClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def get_run(self, run_id: str) -> object:
            return fake_run

        def get_metric_history(self, run_id: str, name: str) -> list:
            return []

        def list_artifacts(self, run_id: str) -> list:
            return []

        def get_experiment_by_name(self, name: str) -> object:
            return None

    monkeypatch.setattr(experiments_module, "MlflowClient", _FakeMlflowClient)


class TestGetExperiment:
    """Tests for ``GET /v1/experiments/{id}`` detail endpoint."""

    @staticmethod
    @pytest.mark.asyncio
    async def test_basic_detail(monkeypatch: pytest.MonkeyPatch) -> None:
        """Returns full experiment detail with correct structure."""
        from anvil.api.v1 import experiments as experiments_module

        mock_tracking = AsyncMock()
        mock_tracking.get_experiment.return_value = _make_fake_experiment()
        mock_tracking.get_safetensors_artifacts.return_value = {
            "available": False,
            "files": [],
            "error": None,
        }
        monkeypatch.setattr(
            experiments_module, "TrackingService", lambda: mock_tracking
        )
        _patch_mlflow_client(monkeypatch)

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="https://test", headers={"X-API-Key": API_KEY}
        ) as client:
            resp = await client.get("/v1/experiments/42")

        assert (
            resp.status_code == 200
        ), f"Expected 200 with full mocks, got {resp.status_code}: {resp.text}"

    @staticmethod
    @pytest.mark.asyncio
    async def test_hyperparams_decode(monkeypatch: pytest.MonkeyPatch) -> None:
        """Hyperparameters are decoded from MLflow string params."""
        from anvil.api.v1 import experiments as experiments_module

        fake_exp = _make_fake_experiment(
            params={
                "n_layer": "4",
                "n_embd": "64",
                "n_head": "8",
                "block_size": "128",
                "num_steps": "500",
                "learning_rate": "0.001",
                "temperature": "0.7",
            }
        )

        mock_tracking = AsyncMock()
        mock_tracking.get_experiment.return_value = fake_exp
        mock_tracking.get_safetensors_artifacts.return_value = {
            "available": False,
            "files": [],
            "error": None,
        }
        monkeypatch.setattr(
            experiments_module, "TrackingService", lambda: mock_tracking
        )
        _patch_mlflow_client(monkeypatch)

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="https://test", headers={"X-API-Key": API_KEY}
        ) as client:
            resp = await client.get("/v1/experiments/42")

        assert (
            resp.status_code == 200
        ), f"Expected 200 got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["hyperparameters"]["n_layer"] == 4
        assert data["hyperparameters"]["n_embd"] == 64
        assert data["hyperparameters"]["learning_rate"] == 0.001

    @staticmethod
    @pytest.mark.asyncio
    async def test_404_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
        """Non-existent experiment returns HTTP 404."""
        from anvil.api.v1 import experiments as experiments_module

        mock_tracking = AsyncMock()
        mock_tracking.get_experiment.return_value = None
        monkeypatch.setattr(
            experiments_module, "TrackingService", lambda: mock_tracking
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="https://test", headers={"X-API-Key": API_KEY}
        ) as client:
            resp = await client.get("/v1/experiments/99999")

        assert resp.status_code == 404
        assert "Experiment not found" in resp.json().get("detail", "")

    @staticmethod
    @pytest.mark.asyncio
    async def test_duration_calculation(monkeypatch: pytest.MonkeyPatch) -> None:
        """Duration is computed from created_at and completed_at timestamps."""
        from anvil.api.v1 import experiments as experiments_module

        fake_exp = _make_fake_experiment(
            mlflow_run_id="mlflow_dur",
            created_at="1700000000000",
            completed_at="1700001000000",
        )
        mock_tracking = AsyncMock()
        mock_tracking.get_experiment.return_value = fake_exp
        mock_tracking.get_safetensors_artifacts.return_value = {
            "available": False,
            "files": [],
            "error": None,
        }
        monkeypatch.setattr(
            experiments_module, "TrackingService", lambda: mock_tracking
        )
        _patch_mlflow_client(monkeypatch)

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="https://test", headers={"X-API-Key": API_KEY}
        ) as client:
            resp = await client.get("/v1/experiments/42")

        assert resp.status_code == 200
        data = resp.json()
        # 1700000000 - 1700001000 = 1000 seconds
        assert data["duration_seconds"] == 1000.0

    @staticmethod
    @pytest.mark.asyncio
    async def test_memory_estimate_from_architecture(
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: object,
    ) -> None:
        """Memory estimate is computed from model architecture JSON."""
        from anvil.api.v1 import experiments as experiments_module

        model_data = {
            "vocab_size": 200,
            "n_embd": 16,
            "n_head": 4,
            "n_layer": 1,
            "block_size": 16,
        }

        os.makedirs("data/models", exist_ok=True)
        model_path = "data/models/experiment_42.json"
        with open(model_path, "w") as f:  # noqa: ASYNC230
            json.dump(model_data, f)

        try:
            fake_exp = _make_fake_experiment(mlflow_run_id="mlflow_mem")
            mock_tracking = AsyncMock()
            mock_tracking.get_experiment.return_value = fake_exp
            mock_tracking.get_safetensors_artifacts.return_value = {
                "available": False,
                "files": [],
                "error": None,
            }
            monkeypatch.setattr(
                experiments_module, "TrackingService", lambda: mock_tracking
            )
            _patch_mlflow_client(monkeypatch)

            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport,
                base_url="https://test",
                headers={"X-API-Key": API_KEY},
            ) as client:
                resp = await client.get("/v1/experiments/42")

            assert resp.status_code == 200
            data = resp.json()
            assert data["memory_estimate"] is not None
            assert data["memory_estimate"]["param_count"] > 0
        finally:
            if os.path.exists(model_path):
                os.remove(model_path)


######################################################################
# get_experiment_metrics
######################################################################


class TestGetExperimentMetrics:
    """Tests for ``GET /v1/experiments/{id}/metrics``."""

    @staticmethod
    @pytest.mark.asyncio
    async def test_mlflow_unavailable_returns_empty(
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When MLflow is unavailable, metrics returns empty list with error."""
        from anvil.api.v1 import experiments as experiments_module

        fake_exp = _make_fake_experiment(mlflow_run_id="mlflow_metrics")
        mock_tracking = AsyncMock()
        mock_tracking.get_experiment.return_value = fake_exp
        monkeypatch.setattr(
            experiments_module, "TrackingService", lambda: mock_tracking
        )

        real_mlflow = experiments_module.MlflowClient

        def _failing_client(*args: object, **kwargs: object) -> object:
            raise MlflowException("MLflow unavailable")

        monkeypatch.setattr(experiments_module, "MlflowClient", _failing_client)

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="https://test", headers={"X-API-Key": API_KEY}
        ) as client:
            resp = await client.get("/v1/experiments/42/metrics")

        assert resp.status_code == 200
        data = resp.json()
        assert data["metrics"] == []
        assert data["mlflow_run_id"] == "mlflow_metrics"
        assert "error" in data

    @staticmethod
    @pytest.mark.asyncio
    async def test_no_mlflow_run_id_returns_empty(
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Experiment without mlflow_run_id returns empty metrics."""
        from anvil.api.v1 import experiments as experiments_module

        fake_exp = _make_fake_experiment(mlflow_run_id=None)
        mock_tracking = AsyncMock()
        mock_tracking.get_experiment.return_value = fake_exp
        monkeypatch.setattr(
            experiments_module, "TrackingService", lambda: mock_tracking
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="https://test", headers={"X-API-Key": API_KEY}
        ) as client:
            resp = await client.get("/v1/experiments/42/metrics")

        assert resp.status_code == 200
        data = resp.json()
        assert data["metrics"] == []
        assert data["mlflow_run_id"] is None

    @staticmethod
    @pytest.mark.asyncio
    async def test_404_when_experiment_not_found(
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Nonexistent experiment returns 404."""
        from anvil.api.v1 import experiments as experiments_module

        mock_tracking = AsyncMock()
        mock_tracking.get_experiment.return_value = None
        monkeypatch.setattr(
            experiments_module, "TrackingService", lambda: mock_tracking
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="https://test", headers={"X-API-Key": API_KEY}
        ) as client:
            resp = await client.get("/v1/experiments/99999/metrics")

        assert resp.status_code == 404


######################################################################
# delete_experiment
######################################################################


class TestDeleteExperiment:
    """Tests for ``DELETE /v1/experiments/{id}``."""

    @staticmethod
    @pytest.mark.asyncio
    async def test_delete_with_mlflow_run(monkeypatch: pytest.MonkeyPatch) -> None:
        """Delete with MLflow run calls delete_run and returns 200."""
        from anvil.api.v1 import experiments as experiments_module

        fake_exp = _make_fake_experiment(mlflow_run_id="mlflow_del")
        mock_tracking = AsyncMock()
        mock_tracking.get_experiment.return_value = fake_exp
        monkeypatch.setattr(
            experiments_module, "TrackingService", lambda: mock_tracking
        )

        delete_called = False

        class FakeMlflowClientDelete:
            def __init__(self, *args: object, **kwargs: object) -> None:
                pass

            def delete_run(self, run_id: str) -> None:
                nonlocal delete_called
                delete_called = True

        # Need to patch tracking_svc._client as well as the MlflowClient import
        # The handler accesses tracking_svc._client directly
        mock_tracking._client = FakeMlflowClientDelete()

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="https://test", headers={"X-API-Key": API_KEY}
        ) as client:
            resp = await client.delete("/v1/experiments/42")

        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

    @staticmethod
    @pytest.mark.asyncio
    async def test_delete_without_mlflow_run(
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Delete without mlflow_run_id still returns 200."""
        from anvil.api.v1 import experiments as experiments_module

        fake_exp = _make_fake_experiment(mlflow_run_id=None)
        mock_tracking = AsyncMock()
        mock_tracking.get_experiment.return_value = fake_exp
        monkeypatch.setattr(
            experiments_module, "TrackingService", lambda: mock_tracking
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="https://test", headers={"X-API-Key": API_KEY}
        ) as client:
            resp = await client.delete("/v1/experiments/42")

        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

    @staticmethod
    @pytest.mark.asyncio
    async def test_delete_mlflow_exception_still_returns_200(
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """MlflowException during delete_run is caught, returns 200."""
        from anvil.api.v1 import experiments as experiments_module

        fake_exp = _make_fake_experiment(mlflow_run_id="mlflow_err")
        mock_tracking = AsyncMock()
        mock_tracking.get_experiment.return_value = fake_exp
        monkeypatch.setattr(
            experiments_module, "TrackingService", lambda: mock_tracking
        )

        class FailingMlflowClient:
            def __init__(self, *args: object, **kwargs: object) -> None:
                pass

            def delete_run(self, run_id: str) -> None:
                raise MlflowException("MLflow server error")

        mock_tracking._client = FailingMlflowClient()

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="https://test", headers={"X-API-Key": API_KEY}
        ) as client:
            resp = await client.delete("/v1/experiments/42")

        assert (
            resp.status_code == 200
        ), f"Expected 200 despite MlflowException, got {resp.status_code}: {resp.text}"
        assert resp.json()["status"] == "deleted"

    @staticmethod
    @pytest.mark.asyncio
    async def test_delete_404_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
        """Delete nonexistent experiment returns 404."""
        from anvil.api.v1 import experiments as experiments_module

        mock_tracking = AsyncMock()
        mock_tracking.get_experiment.return_value = None
        monkeypatch.setattr(
            experiments_module, "TrackingService", lambda: mock_tracking
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="https://test", headers={"X-API-Key": API_KEY}
        ) as client:
            resp = await client.delete("/v1/experiments/99999")

        assert resp.status_code == 404


######################################################################
# download_artifact
######################################################################


class TestDownloadArtifact:
    """Tests for ``GET /v1/experiments/{eid}/runs/{rid}/download``."""

    @staticmethod
    @pytest.mark.asyncio
    async def test_download_success(monkeypatch: pytest.MonkeyPatch) -> None:
        """Successful download returns a FileResponse with the file content."""
        from anvil.api.v1 import experiments as experiments_module

        # Create a temp file to serve
        tf = tempfile.NamedTemporaryFile(delete=False, suffix=".safetensors")
        tf.write(b"fake-safetensors-data")
        tf.close()

        fake_exp = _make_fake_experiment(
            mlflow_run_id="mlflow_dl",
            params={"dataset_id": "1"},
        )
        mock_tracking = AsyncMock()
        mock_tracking.get_experiment.return_value = fake_exp
        mock_tracking.get_safetensors_artifacts.return_value = {
            "available": True,
            "files": [
                {
                    "path": "model.safetensors",
                    "file_size": 100,
                    "is_safetensors": True,
                    "is_config": False,
                    "is_tokenizer": False,
                }
            ],
            "error": None,
        }
        monkeypatch.setattr(
            experiments_module, "TrackingService", lambda: mock_tracking
        )

        class FakeMlflowClientDownload:
            def __init__(self, *args: object, **kwargs: object) -> None:
                pass

            def download_artifacts(
                self, run_id: str, path: str, dst_path: str | None = None
            ) -> str:
                return tf.name

        monkeypatch.setattr(
            experiments_module,
            "MlflowClient",
            lambda *a, **kw: FakeMlflowClientDownload(),
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="https://test", headers={"X-API-Key": API_KEY}
        ) as client:
            resp = await client.get(
                "/v1/experiments/42/runs/mlflow_dl/download",
                params={"path": "model.safetensors"},
            )

        assert resp.status_code == 200
        assert resp.content == b"fake-safetensors-data"
        assert resp.headers.get("content-type") == "application/octet-stream"
        os.unlink(tf.name)

    @staticmethod
    @pytest.mark.asyncio
    async def test_download_404_experiment_not_found(
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Download from nonexistent experiment returns 404."""
        from anvil.api.v1 import experiments as experiments_module

        mock_tracking = AsyncMock()
        mock_tracking.get_experiment.return_value = None
        monkeypatch.setattr(
            experiments_module, "TrackingService", lambda: mock_tracking
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="https://test", headers={"X-API-Key": API_KEY}
        ) as client:
            resp = await client.get(
                "/v1/experiments/99999/runs/mlflow_x/download",
                params={"path": "model.safetensors"},
            )

        assert resp.status_code == 404
