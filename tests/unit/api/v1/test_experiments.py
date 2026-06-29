# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for experiment tracking API endpoints.

Covers listing, comparing, retrieving, deleting experiments and
their associated MLflow data via /v1/experiments/* routes.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from anvil.api.v1.experiments import (
    _build_mlflow_url,
    _get_mlflow_experiment_id,
    _hyperparams_from_mlflow,
    _set_artifact_flag,
)
from anvil.services.tracking.tracking import TrackingService

####################################################################
# Helper: fake MLflow client
####################################################################


class _FakeMlflowClient:
    """Simulates MlflowClient for testing experiment endpoints."""

    def __init__(self, tracking_uri: str):
        self.tracking_uri = tracking_uri
        self._runs: dict[str, SimpleNamespace] = {}
        self._metric_histories: dict[str, list] = {}

    def get_experiment_by_name(self, name):
        return SimpleNamespace(experiment_id="exp_1")

    def create_experiment(self, name):
        return "exp_1"

    def create_run(self, experiment_id, run_name=None, tags=None):
        run_id = f"mlflow_{len(self._runs) + 1}"
        run = SimpleNamespace(
            info=SimpleNamespace(
                run_id=run_id,
                status="FINISHED",
                start_time=1717171200000,
                end_time=1717174800000,
            ),
            data=SimpleNamespace(
                params={
                    "n_embd": "16",
                    "n_head": "4",
                    "n_layer": "1",
                    "block_size": "16",
                    "num_steps": "100",
                    "learning_rate": "0.01",
                    "engine_backend": "stdlib",
                    "device": "cpu",
                },
                metrics={"final_loss": 0.5, "loss": 0.5},
                tags={
                    "mlflow.runName": "test-run",
                    "anvil.experiment_id": "42",
                    "anvil.status": "finished",
                    "architectures": "LlamaForCausalLM",
                },
            ),
        )
        self._runs[run_id] = run
        return run

    def get_run(self, run_id):
        run = self._runs.get(run_id)
        if run:
            return run
        raise MlflowException("Run not found")

    def search_runs(
        self, experiment_ids, order_by=None, filter_string=None, max_results=100
    ):
        return list(self._runs.values())

    def get_metric_history(self, run_id, metric_name):
        return self._metric_histories.get(run_id, [])

    def log_batch(self, run_id, params=None, metrics=None, tags=None):
        pass

    def log_metric(self, run_id, key, value, step=None):
        pass

    def set_terminated(self, run_id, status="FINISHED"):
        pass

    def log_artifact(self, run_id, local_path):
        pass

    def list_artifacts(self, run_id):
        return []

    def delete_run(self, run_id):
        self._runs.pop(run_id, None)

    def download_artifacts(self, run_id, path, dst_path=None):
        return "/tmp/downloaded_model.safetensors"


class MlflowException(Exception):
    """Local replacement for mlflow.exceptions.MlflowException."""


####################################################################
# Conftest-like fixtures
####################################################################


@pytest.fixture
def fake_client():
    """Return a fresh _FakeMlflowClient for each test."""
    return _FakeMlflowClient("http://127.0.0.1:5000")


@pytest.fixture
def fake_run_mlflow(fake_client):
    """Create a run in the fake client and return (run_id, fake_client)."""
    fake_client.create_run("exp_1")
    run_id = "mlflow_1"
    return run_id, fake_client


####################################################################
# Helper unit tests
####################################################################


class TestHyperparamsFromMlflow:
    """Tests for the _hyperparams_from_mlflow helper function."""

    def test_coerces_known_types(self):
        params = {
            "n_layer": "4",
            "n_embd": "128",
            "n_head": "8",
            "block_size": "256",
            "num_steps": "1000",
            "learning_rate": "0.01",
            "beta1": "0.85",
            "beta2": "0.99",
            "temperature": "0.5",
        }
        hp = _hyperparams_from_mlflow(params)
        assert hp["n_layer"] == 4
        assert isinstance(hp["n_layer"], int)
        assert hp["learning_rate"] == 0.01
        assert isinstance(hp["learning_rate"], float)
        assert hp["beta1"] == 0.85
        assert isinstance(hp["beta1"], float)

    def test_skips_missing_params(self):
        hp = _hyperparams_from_mlflow({"n_head": "4"})
        assert "n_layer" not in hp
        assert hp["n_head"] == 4

    def test_skips_unparseable_values(self):
        hp = _hyperparams_from_mlflow({"n_embd": "not-a-number", "n_head": "4"})
        assert "n_embd" not in hp
        assert hp["n_head"] == 4

    def test_returns_empty_dict_for_no_matches(self):
        hp = _hyperparams_from_mlflow({"irrelevant": "value"})
        assert hp == {}


class TestGetMlflowExperimentId:
    """Tests for _get_mlflow_experiment_id helper."""

    def test_returns_id_when_experiment_found(self, fake_client):
        with patch("anvil.api.v1.experiments.MlflowClient", return_value=fake_client):
            result = _get_mlflow_experiment_id()
        assert result == "exp_1"

    def test_returns_none_when_no_experiment(self, fake_client):
        fake_client.get_experiment_by_name = lambda name: None  # type: ignore[method-assign]
        with patch("anvil.api.v1.experiments.MlflowClient", return_value=fake_client):
            result = _get_mlflow_experiment_id()
        assert result is None

    def test_returns_none_on_mlflow_exception(self, fake_client):
        def _raise_error(name: str) -> None:
            raise MlflowException("MLflow error")

        fake_client.get_experiment_by_name = _raise_error  # type: ignore[method-assign]
        with (
            patch("anvil.api.v1.experiments.MlflowClient", return_value=fake_client),
            patch("anvil.api.v1.experiments.MlflowException", MlflowException),
        ):
            result = _get_mlflow_experiment_id()
        assert result is None


class TestBuildMlflowUrl:
    """Tests for _build_mlflow_url helper."""

    def test_builds_url_when_exp_id_provided(self):
        request = MagicMock()
        with patch(
            "anvil.api.v1.experiments.get_mlflow_browser_uri",
            return_value="http://localhost:5001",
        ):
            url = _build_mlflow_url(request, "exp_1")
        assert url == "http://localhost:5001/#/experiments/exp_1"

    def test_returns_none_when_no_exp_id(self):
        request = MagicMock()
        url = _build_mlflow_url(request, None)
        assert url is None


class TestSetArtifactFlag:
    """Tests for _set_artifact_flag helper."""

    def test_sets_true_when_file_exists(self):
        exp: dict = {"id": "42"}
        with patch("anvil.api.v1.experiments.Path.exists", return_value=True):
            _set_artifact_flag(exp)
        assert exp["artifact_available"] is True

    def test_sets_false_when_file_missing(self):
        exp: dict = {"id": "42"}
        with patch("anvil.api.v1.experiments.Path.exists", return_value=False):
            _set_artifact_flag(exp)
        assert exp["artifact_available"] is False

    def test_sets_false_when_no_id(self):
        exp: dict = {}
        _set_artifact_flag(exp)
        assert exp["artifact_available"] is False


####################################################################
# Experiments list endpoint
####################################################################


class TestListExperiments:
    """Tests for GET /v1/experiments."""

    async def test_lists_experiments_successfully(self, client, fake_client):
        """Happy path: returns experiments list with enrichment."""
        fake_client.create_run("exp_1")
        run = fake_client._runs["mlflow_1"]
        run.data.tags["anvil.experiment_id"] = "1"

        with (
            patch("anvil.api.v1.experiments.MlflowClient", return_value=fake_client),
            patch.object(
                TrackingService,
                "list_experiments",
                return_value=[
                    {
                        "id": 1,
                        "status": "finished",
                        "run_name": "test-run",
                        "final_loss": 0.5,
                        "mlflow_run_id": "mlflow_1",
                        "dataset_name": "test-ds",
                        "dataset_id": "1",
                        "corpus_id": None,
                        "input_digest": None,
                        "input_role": "training",
                        "engine_backend": "stdlib",
                        "device": "cpu",
                        "created_at": "1717171200000",
                        "config_id": None,
                        "artifact_available": False,
                    }
                ],
            ),
            patch("anvil.api.v1.experiments.Path.exists", return_value=False),
        ):
            resp = await client.get("/v1/experiments")
        assert resp.status_code == 200
        data = resp.json()
        assert "experiments" in data
        assert len(data["experiments"]) == 1
        assert data["experiments"][0]["id"] == 1
        assert "mlflow_experiment_id" in data
        assert "mlflow_url" in data

    async def test_returns_empty_list_when_no_experiments(self, client):
        """Returns empty list when no experiments exist."""
        with (
            patch.object(TrackingService, "list_experiments", return_value=[]),
            patch("anvil.api.v1.experiments.MlflowClient") as mock_client_cls,
            patch("anvil.api.v1.experiments.Path.exists", return_value=False),
        ):
            mock_client = MagicMock()
            mock_client_cls.return_value = mock_client
            mock_client.get_experiment_by_name.return_value = SimpleNamespace(
                experiment_id="exp_1"
            )
            resp = await client.get("/v1/experiments")
        assert resp.status_code == 200
        data = resp.json()
        assert data["experiments"] == []

    async def test_returns_mlflow_url_none_when_no_mlflow_experiment(self, client):
        """Returns None mlflow_url when MLflow experiment does not exist."""
        with (
            patch.object(TrackingService, "list_experiments", return_value=[]),
            patch("anvil.api.v1.experiments.MlflowClient") as mock_client_cls,
            patch("anvil.api.v1.experiments.Path.exists", return_value=False),
        ):
            mock_client = MagicMock()
            mock_client_cls.return_value = mock_client
            mock_client.get_experiment_by_name.return_value = None
            resp = await client.get("/v1/experiments")
        assert resp.status_code == 200
        data = resp.json()
        assert data["mlflow_experiment_id"] is None
        assert data["mlflow_url"] is None

    async def test_handles_mlflow_exception_in_list(self, client):
        """Returns None mlflow fields when MlflowException is raised."""
        with (
            patch.object(TrackingService, "list_experiments", return_value=[]),
            patch("anvil.api.v1.experiments.MlflowClient") as mock_client_cls,
            patch("anvil.api.v1.experiments.MlflowException", MlflowException),
            patch("anvil.api.v1.experiments.Path.exists", return_value=False),
        ):
            mock_client = MagicMock()
            mock_client_cls.return_value = mock_client
            mock_client.get_experiment_by_name.side_effect = MlflowException("fail")
            resp = await client.get("/v1/experiments")
        assert resp.status_code == 200
        data = resp.json()
        assert data["mlflow_experiment_id"] is None


####################################################################
# Experiments compare endpoint
####################################################################


class TestCompareExperiments:
    """Tests for GET /v1/experiments/compare."""

    async def test_compares_multiple_experiments(self, client):
        """Happy path: compares multiple experiments by IDs."""

        async def _fake_get_experiment(eid: int) -> dict | None:
            if eid == 1:
                return {
                    "id": 1,
                    "status": "finished",
                    "final_loss": 0.5,
                    "created_at": "1000",
                }
            if eid == 2:
                return {
                    "id": 2,
                    "status": "running",
                    "final_loss": None,
                    "created_at": "2000",
                }
            return None

        with patch.object(
            TrackingService,
            "get_experiment",
            side_effect=_fake_get_experiment,
        ):
            resp = await client.get(
                "/v1/experiments/compare?experiment_ids=1&experiment_ids=2&experiment_ids=999"
            )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["experiments"]) == 2
        assert data["experiments"][0]["id"] == 1
        assert data["experiments"][1]["id"] == 2

    async def test_compare_requires_at_least_one_id(self, client):
        """Returns 422 when no experiment IDs are provided."""
        resp = await client.get("/v1/experiments/compare")
        assert resp.status_code == 422

    async def test_compare_handles_all_missing(self, client):
        """Returns empty list when all IDs are missing."""
        with patch.object(TrackingService, "get_experiment", return_value=None):
            resp = await client.get(
                "/v1/experiments/compare?experiment_ids=999&experiment_ids=888"
            )
        assert resp.status_code == 200
        assert resp.json()["experiments"] == []


####################################################################
# Experiments detail endpoint
####################################################################


class TestGetExperiment:
    """Tests for GET /v1/experiments/{experiment_id}."""

    async def test_returns_experiment_detail(self, client):
        """Happy path: returns full experiment details."""
        exp_id = 42
        model_path = Path(f"data/models/experiment_{exp_id}.json")
        model_path.parent.mkdir(parents=True, exist_ok=True)
        model_path.write_text(
            json.dumps(
                {
                    "vocab_size": 100,
                    "n_embd": 16,
                    "n_head": 4,
                    "n_layer": 1,
                    "block_size": 16,
                    "state_dict": {},
                }
            )
        )

        async def _fake_get_experiment(eid: int) -> dict | None:
            if eid == exp_id:
                return {
                    "id": exp_id,
                    "mlflow_run_id": None,
                    "status": "FINISHED",
                    "run_name": "detail-test",
                    "final_loss": 0.5,
                    "params": {},
                    "metrics": {},
                    "tags": {},
                    "created_at": "",
                    "completed_at": None,
                    "input_digest": None,
                    "input_role": None,
                    "engine_backend": "stdlib",
                    "device": "cpu",
                }
            return None

        with patch.object(
            TrackingService, "get_experiment", side_effect=_fake_get_experiment
        ):
            try:
                resp = await client.get(f"/v1/experiments/{exp_id}")
                assert resp.status_code == 200
                data = resp.json()
                assert data["id"] == exp_id
                assert data["status"] == "FINISHED"
                assert "model_architecture" in data
                assert "memory_estimate" in data
                assert "hyperparameters" in data
            finally:
                model_path.unlink(missing_ok=True)

    async def test_returns_404_when_not_found(self, client):
        """Returns 404 when the experiment does not exist."""
        with patch.object(TrackingService, "get_experiment", return_value=None):
            resp = await client.get("/v1/experiments/999")
        assert resp.status_code == 404
        assert "Experiment not found" in resp.json()["detail"]

    async def test_includes_mlflow_data_when_run_id_present(self, client, fake_client):
        """Includes MLflow data when experiment has an mlflow_run_id."""
        exp_id = 43
        mlflow_run_id = "mlflow_gpu_1"
        fake_client.create_run("exp_1")
        fake_client._runs[mlflow_run_id] = SimpleNamespace(
            info=SimpleNamespace(
                run_id=mlflow_run_id,
                status="FINISHED",
                start_time=1717171200000,
                end_time=1717174800000,
            ),
            data=SimpleNamespace(
                params={"n_embd": "16"},
                metrics={"final_loss": 0.5, "system/gpu_memory_gb": 3.5},
                tags={"architectures": "LlamaForCausalLM"},
            ),
        )
        fake_client._metric_histories[mlflow_run_id] = [
            SimpleNamespace(step=0, value=2.0, timestamp=1),
            SimpleNamespace(step=1, value=3.5, timestamp=2),
        ]

        async def _fake_get_experiment(eid: int) -> dict | None:
            if eid == exp_id:
                return {
                    "id": exp_id,
                    "mlflow_run_id": mlflow_run_id,
                    "status": "FINISHED",
                    "run_name": "mlflow-test",
                    "final_loss": 0.5,
                    "params": {"n_embd": "16", "n_head": "4", "n_layer": "1"},
                    "metrics": {"final_loss": 0.5},
                    "tags": {"architectures": "LlamaForCausalLM"},
                    "created_at": "1717171200000",
                    "completed_at": "1717174800000",
                    "input_digest": None,
                    "input_role": None,
                    "engine_backend": "torch",
                    "device": "cuda:0",
                }
            return None

        with (
            patch("anvil.api.v1.experiments.MlflowClient", return_value=fake_client),
            patch.object(
                TrackingService, "get_experiment", side_effect=_fake_get_experiment
            ),
            patch.object(
                TrackingService,
                "get_safetensors_artifacts",
                return_value={"available": False, "files": [], "error": None},
            ),
            patch("anvil.api.v1.experiments.Path.exists", return_value=False),
        ):
            resp = await client.get(f"/v1/experiments/{exp_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["mlflow"] is not None
        assert "params" in data["mlflow"]
        assert data["gpu_memory_peak_gb"] == 3.5
        assert data["gpu_util_peak_pct"] is None

    async def test_computes_duration_from_timestamps(self, client):
        """Computes duration_seconds when created_at and completed_at are set."""

        async def _fake_get_experiment(eid: int) -> dict | None:
            if eid == 44:
                return {
                    "id": 44,
                    "mlflow_run_id": None,
                    "status": "FINISHED",
                    "run_name": "duration-test",
                    "final_loss": 0.5,
                    "params": {},
                    "metrics": {},
                    "tags": {},
                    "created_at": "1000",
                    "completed_at": "5000",
                    "input_digest": None,
                    "input_role": None,
                    "engine_backend": "stdlib",
                    "device": "cpu",
                }
            return None

        with patch.object(
            TrackingService, "get_experiment", side_effect=_fake_get_experiment
        ):
            resp = await client.get("/v1/experiments/44")
        assert resp.status_code == 200
        data = resp.json()
        assert data["duration_seconds"] == 4.0

    async def test_computes_duration_with_non_numeric_timestamps(self, client):
        """Returns None duration_seconds when timestamps are non-numeric."""

        async def _fake_get_experiment(eid: int) -> dict | None:
            if eid == 50:
                return {
                    "id": 50,
                    "mlflow_run_id": None,
                    "status": "FINISHED",
                    "run_name": "bad-ts",
                    "final_loss": None,
                    "params": {},
                    "metrics": {},
                    "tags": {},
                    "created_at": "not-a-number",
                    "completed_at": "also-not",
                    "input_digest": None,
                    "input_role": None,
                    "engine_backend": "stdlib",
                    "device": "cpu",
                }
            return None

        with patch.object(
            TrackingService, "get_experiment", side_effect=_fake_get_experiment
        ):
            resp = await client.get("/v1/experiments/50")
        assert resp.status_code == 200
        assert resp.json()["duration_seconds"] is None

    async def test_handles_mlflow_exception_in_detail(self, client):
        """Returns mlflow=None when MlflowException is raised."""
        exp_id = 46
        mlflow_run_id = "mlflow_err_1"

        async def _fake_get_experiment(eid: int) -> dict | None:
            if eid == exp_id:
                return {
                    "id": exp_id,
                    "mlflow_run_id": mlflow_run_id,
                    "status": "FINISHED",
                    "run_name": "mlflow-err",
                    "final_loss": None,
                    "params": {},
                    "metrics": {},
                    "tags": {},
                    "created_at": "",
                    "completed_at": None,
                    "input_digest": None,
                    "input_role": None,
                    "engine_backend": "stdlib",
                    "device": "cpu",
                }
            return None

        with (
            patch.object(
                TrackingService, "get_experiment", side_effect=_fake_get_experiment
            ),
            patch("anvil.api.v1.experiments.MlflowClient") as mock_client_cls,
            patch("anvil.api.v1.experiments.MlflowException", MlflowException),
            patch("anvil.api.v1.experiments.Path.exists", return_value=False),
        ):
            mock_client = MagicMock()
            mock_client_cls.return_value = mock_client
            mock_client.get_run.side_effect = MlflowException("run not found")
            resp = await client.get(f"/v1/experiments/{exp_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["mlflow"] is None

    async def test_handles_corrupted_model_file(self, client):
        """Returns model_architecture=None when JSON is corrupted."""
        exp_id = 47
        model_path = Path(f"data/models/experiment_{exp_id}.json")
        model_path.parent.mkdir(parents=True, exist_ok=True)
        model_path.write_text("not-valid-json")

        async def _fake_get_experiment(eid: int) -> dict | None:
            if eid == exp_id:
                return {
                    "id": exp_id,
                    "mlflow_run_id": None,
                    "status": "FINISHED",
                    "run_name": "corrupt",
                    "final_loss": None,
                    "params": {},
                    "metrics": {},
                    "tags": {},
                    "created_at": "",
                    "completed_at": None,
                    "input_digest": None,
                    "input_role": None,
                    "engine_backend": "stdlib",
                    "device": "cpu",
                }
            return None

        with patch.object(
            TrackingService, "get_experiment", side_effect=_fake_get_experiment
        ):
            try:
                resp = await client.get(f"/v1/experiments/{exp_id}")
                assert resp.status_code == 200
                data = resp.json()
                assert data["model_architecture"] is None
                assert data["memory_estimate"] is None
            finally:
                model_path.unlink(missing_ok=True)

    async def test_resolves_dataset_name_from_params(self, client, monkeypatch):
        """Resolves dataset_name from params dataset_id via AsyncSessionLocal."""
        exp_id = 45

        async def _fake_get_experiment(eid: int) -> dict | None:
            if eid == exp_id:
                return {
                    "id": exp_id,
                    "mlflow_run_id": None,
                    "status": "FINISHED",
                    "run_name": "ds-resolve",
                    "final_loss": None,
                    "params": {"dataset_id": "1"},
                    "metrics": {},
                    "tags": {},
                    "created_at": "",
                    "completed_at": None,
                    "input_digest": None,
                    "input_role": None,
                    "engine_backend": "stdlib",
                    "device": "cpu",
                }
            return None

        fake_ds = MagicMock()
        fake_ds.name = "resolved-dataset"

        fake_session = AsyncMock()
        fake_session.__aenter__.return_value = fake_session
        fake_session.__aexit__.return_value = None

        with (
            patch.object(
                TrackingService, "get_experiment", side_effect=_fake_get_experiment
            ),
            patch("anvil.api.v1.experiments.Path.exists", return_value=False),
            patch(
                "anvil.api.v1.experiments.AsyncSessionLocal", return_value=fake_session
            ),
        ):
            fake_repo = AsyncMock()
            fake_repo.get.return_value = fake_ds
            with patch(
                "anvil.api.v1.experiments.DatasetRepository", return_value=fake_repo
            ):
                resp = await client.get(f"/v1/experiments/{exp_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["dataset_name"] == "resolved-dataset"


####################################################################
# Experiments MLflow endpoint
####################################################################


class TestGetExperimentMlflow:
    """Tests for GET /v1/experiments/{experiment_id}/mlflow."""

    async def test_returns_mlflow_data(self, client, fake_client):
        """Happy path: returns MLflow data for an experiment."""
        exp_id = 42
        mlflow_run_id = "mlflow_detail_1"
        fake_client.create_run("exp_1")
        fake_client._runs[mlflow_run_id] = SimpleNamespace(
            info=SimpleNamespace(run_id=mlflow_run_id),
            data=SimpleNamespace(
                params={"n_embd": "16"},
                metrics={"loss": 0.5},
                tags={},
            ),
        )
        fake_client._metric_histories[mlflow_run_id] = [
            SimpleNamespace(step=0, value=1.0, timestamp=1),
        ]

        async def _fake_get_experiment(eid: int) -> dict | None:
            if eid == exp_id:
                return {"id": exp_id, "mlflow_run_id": mlflow_run_id}
            return None

        with (
            patch("anvil.api.v1.experiments.MlflowClient", return_value=fake_client),
            patch.object(
                TrackingService, "get_experiment", side_effect=_fake_get_experiment
            ),
            patch.object(
                TrackingService,
                "get_safetensors_artifacts",
                return_value={"available": False, "files": [], "error": None},
            ),
        ):
            resp = await client.get(f"/v1/experiments/{exp_id}/mlflow")
        assert resp.status_code == 200
        data = resp.json()
        assert data["mlflow_run_id"] == mlflow_run_id
        assert "params" in data
        assert "metrics" in data
        assert "metric_histories" in data

    async def test_returns_404_when_experiment_not_found(self, client):
        """Returns 404 when the experiment does not exist."""
        with patch.object(TrackingService, "get_experiment", return_value=None):
            resp = await client.get("/v1/experiments/999/mlflow")
        assert resp.status_code == 404

    async def test_returns_empty_when_no_mlflow_run_id(self, client):
        """Returns empty shapes when experiment has no mlflow_run_id."""

        async def _fake_get_experiment(eid: int) -> dict | None:
            if eid == 1:
                return {"id": 1, "mlflow_run_id": None}
            return None

        with patch.object(
            TrackingService, "get_experiment", side_effect=_fake_get_experiment
        ):
            resp = await client.get("/v1/experiments/1/mlflow")
        assert resp.status_code == 200
        data = resp.json()
        assert data["mlflow_run_id"] is None
        assert data["params"] == {}
        assert data["run_url"] is None

    async def test_returns_error_when_mlflow_exception(self, client, fake_client):
        """Returns error field when MlflowException is raised."""
        exp_id = 48
        mlflow_run_id = "mlflow_mlflow_err"

        async def _fake_get_experiment(eid: int) -> dict | None:
            if eid == exp_id:
                return {"id": exp_id, "mlflow_run_id": mlflow_run_id}
            return None

        with (
            patch.object(
                TrackingService, "get_experiment", side_effect=_fake_get_experiment
            ),
            patch("anvil.api.v1.experiments.MlflowClient") as mock_client_cls,
            patch("anvil.api.v1.experiments.MlflowException", MlflowException),
        ):
            mock_client = MagicMock()
            mock_client_cls.return_value = mock_client
            mock_client.get_run.side_effect = MlflowException("MLflow error detail")
            resp = await client.get(f"/v1/experiments/{exp_id}/mlflow")
        assert resp.status_code == 200
        data = resp.json()
        assert data["mlflow_run_id"] == mlflow_run_id
        assert "error" in data
        assert "MLflow error detail" in data["error"]


####################################################################
# Experiments metrics endpoint
####################################################################


class TestGetExperimentMetrics:
    """Tests for GET /v1/experiments/{experiment_id}/metrics."""

    async def test_returns_metrics(self, client, fake_client):
        """Happy path: returns loss metric history."""
        mlflow_run_id = "mlflow_metrics_1"

        async def _fake_get_experiment(eid: int) -> dict | None:
            if eid == 1:
                return {"id": 1, "mlflow_run_id": mlflow_run_id}
            return None

        fake_client._metric_histories[mlflow_run_id] = [
            SimpleNamespace(step=0, value=1.0, timestamp=1),
            SimpleNamespace(step=1, value=0.8, timestamp=2),
        ]

        with (
            patch("anvil.api.v1.experiments.MlflowClient", return_value=fake_client),
            patch.object(
                TrackingService, "get_experiment", side_effect=_fake_get_experiment
            ),
        ):
            resp = await client.get("/v1/experiments/1/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert "metrics" in data
        assert len(data["metrics"]) == 2
        assert data["metrics"][0]["step"] == 0
        assert data["metrics"][0]["loss"] == 1.0

    async def test_returns_404_when_experiment_not_found(self, client):
        with patch.object(TrackingService, "get_experiment", return_value=None):
            resp = await client.get("/v1/experiments/999/metrics")
        assert resp.status_code == 404

    async def test_returns_empty_when_no_mlflow_run_id(self, client):
        async def _fake_get_experiment(eid: int) -> dict | None:
            if eid == 1:
                return {"id": 1, "mlflow_run_id": None}
            return None

        with patch.object(
            TrackingService, "get_experiment", side_effect=_fake_get_experiment
        ):
            resp = await client.get("/v1/experiments/1/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["metrics"] == []
        assert data["mlflow_run_id"] is None

    async def test_returns_error_on_mlflow_exception(self, client, fake_client):
        """Returns error field when MlflowException is raised."""
        mlflow_run_id = "mlflow_metrics_err"

        async def _fake_get_experiment(eid: int) -> dict | None:
            if eid == 1:
                return {"id": 1, "mlflow_run_id": mlflow_run_id}
            return None

        def _raise_mlflow_error(run_id: str, name: str) -> None:
            raise MlflowException("metrics error")

        fake_client.get_metric_history = _raise_mlflow_error  # type: ignore[method-assign]

        with (
            patch("anvil.api.v1.experiments.MlflowClient", return_value=fake_client),
            patch("anvil.api.v1.experiments.MlflowException", MlflowException),
            patch.object(
                TrackingService, "get_experiment", side_effect=_fake_get_experiment
            ),
        ):
            resp = await client.get("/v1/experiments/1/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert "error" in data


####################################################################
# Delete experiment endpoint
####################################################################


class TestDeleteExperiment:
    """Tests for DELETE /v1/experiments/{experiment_id}."""

    async def test_deletes_experiment(self, client, fake_client):
        """Happy path: experiment deleted successfully."""

        async def _fake_get_experiment(eid: int) -> dict | None:
            if eid == 1:
                return {
                    "id": 1,
                    "mlflow_run_id": "mlflow_del_1",
                    "status": "FINISHED",
                }
            return None

        mock_client = MagicMock()
        mock_client.delete_run = MagicMock()

        with (
            patch.object(
                TrackingService, "get_experiment", side_effect=_fake_get_experiment
            ),
            patch.object(TrackingService, "_lazy_init", return_value=mock_client),
        ):
            resp = await client.delete("/v1/experiments/1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "deleted"

    async def test_returns_404_when_not_found(self, client):
        with patch.object(TrackingService, "get_experiment", return_value=None):
            resp = await client.delete("/v1/experiments/999")
        assert resp.status_code == 404

    async def test_deletes_experiment_without_mlflow_run(self, client):
        """Deletes experiment even without mlflow_run_id."""

        async def _fake_get_experiment(eid: int) -> dict | None:
            if eid == 1:
                return {"id": 1, "mlflow_run_id": None}
            return None

        with patch.object(
            TrackingService, "get_experiment", side_effect=_fake_get_experiment
        ):
            resp = await client.delete("/v1/experiments/1")
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

    async def test_handles_mlflow_error_on_delete(self, client, monkeypatch):
        """Handles MlflowException during MLflow delete gracefully."""

        async def _fake_get_experiment(eid: int) -> dict | None:
            if eid == 1:
                return {
                    "id": 1,
                    "mlflow_run_id": "mlflow_del_2",
                    "status": "FINISHED",
                }
            return None

        delete_mock = MagicMock()
        delete_mock.delete_run.side_effect = MlflowException("delete failed")

        with (
            patch.object(
                TrackingService, "get_experiment", side_effect=_fake_get_experiment
            ),
            patch.object(TrackingService, "_lazy_init", return_value=delete_mock),
            patch("anvil.api.v1.experiments.MlflowException", MlflowException),
        ):
            resp = await client.delete("/v1/experiments/1")
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"


####################################################################
# Artifacts listing endpoint
####################################################################


class TestListArtifacts:
    """Tests for GET /v1/experiments/{experiment_id}/runs/{run_id}/artifacts."""

    async def test_lists_artifacts(self, client):
        """Happy path: lists artifacts for a valid experiment and run."""
        exp_id = 42
        mlflow_run_id = "mlflow_art_1"

        async def _fake_get_experiment(eid: int) -> dict | None:
            if eid == exp_id:
                return {"id": exp_id, "mlflow_run_id": mlflow_run_id}
            return None

        with (
            patch.object(
                TrackingService, "get_experiment", side_effect=_fake_get_experiment
            ),
            patch.object(
                TrackingService,
                "get_safetensors_artifacts",
                return_value={
                    "available": True,
                    "files": [
                        {
                            "path": "model.safetensors",
                            "file_size": 100,
                            "is_safetensors": True,
                            "is_config": False,
                            "is_tokenizer": False,
                        },
                    ],
                    "error": None,
                },
            ),
        ):
            resp = await client.get(
                f"/v1/experiments/{exp_id}/runs/{mlflow_run_id}/artifacts"
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["available"] is True
        assert len(data["files"]) == 1

    async def test_returns_404_when_experiment_not_found(self, client):
        with patch.object(TrackingService, "get_experiment", return_value=None):
            resp = await client.get("/v1/experiments/999/runs/x/artifacts")
        assert resp.status_code == 404

    async def test_returns_404_when_no_mlflow_run(self, client):
        async def _fake_get_experiment(eid: int) -> dict | None:
            if eid == 1:
                return {"id": 1, "mlflow_run_id": None}
            return None

        with patch.object(
            TrackingService, "get_experiment", side_effect=_fake_get_experiment
        ):
            resp = await client.get("/v1/experiments/1/runs/x/artifacts")
        assert resp.status_code == 404

    async def test_returns_400_when_run_id_mismatch(self, client):
        exp_id = 42

        async def _fake_get_experiment(eid: int) -> dict | None:
            if eid == exp_id:
                return {"id": exp_id, "mlflow_run_id": "real_run_id"}
            return None

        with patch.object(
            TrackingService, "get_experiment", side_effect=_fake_get_experiment
        ):
            resp = await client.get(
                f"/v1/experiments/{exp_id}/runs/wrong_run_id/artifacts"
            )
        assert resp.status_code == 400
        assert "does not match" in resp.json()["detail"]


####################################################################
# Download artifact endpoint
####################################################################


class TestDownloadArtifact:
    """Tests for GET /v1/experiments/{experiment_id}/runs/{run_id}/download."""

    @pytest.fixture(autouse=True)
    def setup_temp_file(self, tmp_path):
        """Create a fake artifact file for download tests."""
        self.tmp_dir = tmp_path
        self.artifact_file = tmp_path / "model.safetensors"
        self.artifact_file.write_text("fake-artifact-content")
        return tmp_path

    async def test_downloads_artifact(self, client):
        """Happy path: downloads an artifact file."""
        exp_id = 42
        mlflow_run_id = "mlflow_dl_1"

        async def _fake_get_experiment(eid: int) -> dict | None:
            if eid == exp_id:
                return {"id": exp_id, "mlflow_run_id": mlflow_run_id}
            return None

        with (
            patch.object(
                TrackingService, "get_experiment", side_effect=_fake_get_experiment
            ),
            patch.object(
                TrackingService,
                "get_safetensors_artifacts",
                return_value={
                    "available": True,
                    "files": [
                        {
                            "path": "model.safetensors",
                            "file_size": 100,
                            "is_safetensors": True,
                            "is_config": False,
                            "is_tokenizer": False,
                        },
                    ],
                    "error": None,
                },
            ),
            patch("anvil.api.v1.experiments.MlflowClient") as mock_client_cls,
        ):
            mock_client = MagicMock()
            mock_client_cls.return_value = mock_client
            mock_client.download_artifacts.return_value = str(self.artifact_file)

            resp = await client.get(
                f"/v1/experiments/{exp_id}/runs/{mlflow_run_id}/download",
                params={"path": "model.safetensors"},
            )
        assert resp.status_code == 200
        assert resp.headers.get("content-type") == "application/octet-stream"

    async def test_returns_404_for_missing_path(self, client):
        """Returns 404 when the requested artifact path is not in the list."""
        exp_id = 42
        mlflow_run_id = "mlflow_dl_2"

        async def _fake_get_experiment(eid: int) -> dict | None:
            if eid == exp_id:
                return {"id": exp_id, "mlflow_run_id": mlflow_run_id}
            return None

        with (
            patch.object(
                TrackingService, "get_experiment", side_effect=_fake_get_experiment
            ),
            patch.object(
                TrackingService,
                "get_safetensors_artifacts",
                return_value={
                    "available": True,
                    "files": [
                        {
                            "path": "model.safetensors",
                            "file_size": 100,
                            "is_safetensors": True,
                            "is_config": False,
                            "is_tokenizer": False,
                        },
                    ],
                    "error": None,
                },
            ),
        ):
            resp = await client.get(
                f"/v1/experiments/{exp_id}/runs/{mlflow_run_id}/download",
                params={"path": "nonexistent.safetensors"},
            )
        assert resp.status_code == 404

    async def test_returns_404_when_no_safetensors_artifacts(self, client):
        """Returns 404 when no safetensors artifacts exist."""
        exp_id = 42
        mlflow_run_id = "mlflow_dl_3"

        async def _fake_get_experiment(eid: int) -> dict | None:
            if eid == exp_id:
                return {"id": exp_id, "mlflow_run_id": mlflow_run_id}
            return None

        with (
            patch.object(
                TrackingService, "get_experiment", side_effect=_fake_get_experiment
            ),
            patch.object(
                TrackingService,
                "get_safetensors_artifacts",
                return_value={"available": False, "files": [], "error": None},
            ),
        ):
            resp = await client.get(
                f"/v1/experiments/{exp_id}/runs/{mlflow_run_id}/download",
                params={"path": "model.safetensors"},
            )
        assert resp.status_code == 404
        assert "No safetensors artifacts" in resp.json()["detail"]

    async def test_returns_404_when_experiment_not_found(self, client):
        with patch.object(TrackingService, "get_experiment", return_value=None):
            resp = await client.get(
                "/v1/experiments/999/runs/x/download",
                params={"path": "model.safetensors"},
            )
        assert resp.status_code == 404

    async def test_returns_404_when_no_mlflow_run(self, client):
        async def _fake_get_experiment(eid: int) -> dict | None:
            if eid == 1:
                return {"id": 1, "mlflow_run_id": None}
            return None

        with patch.object(
            TrackingService, "get_experiment", side_effect=_fake_get_experiment
        ):
            resp = await client.get(
                "/v1/experiments/1/runs/x/download",
                params={"path": "model.safetensors"},
            )
        assert resp.status_code == 404

    async def test_returns_400_when_run_id_mismatch(self, client):
        exp_id = 42

        async def _fake_get_experiment(eid: int) -> dict | None:
            if eid == exp_id:
                return {"id": exp_id, "mlflow_run_id": "real_run_id"}
            return None

        with patch.object(
            TrackingService, "get_experiment", side_effect=_fake_get_experiment
        ):
            resp = await client.get(
                f"/v1/experiments/{exp_id}/runs/wrong_run_id/download",
                params={"path": "model.safetensors"},
            )
        assert resp.status_code == 400

    async def test_returns_500_when_not_a_file(self, client):
        """Returns 500 when downloaded artifact is not a file."""
        exp_id = 42
        mlflow_run_id = "mlflow_dl_4"

        async def _fake_get_experiment(eid: int) -> dict | None:
            if eid == exp_id:
                return {"id": exp_id, "mlflow_run_id": mlflow_run_id}
            return None

        with (
            patch.object(
                TrackingService, "get_experiment", side_effect=_fake_get_experiment
            ),
            patch.object(
                TrackingService,
                "get_safetensors_artifacts",
                return_value={
                    "available": True,
                    "files": [
                        {
                            "path": "model.safetensors",
                            "file_size": 100,
                            "is_safetensors": True,
                            "is_config": False,
                            "is_tokenizer": False,
                        },
                    ],
                    "error": None,
                },
            ),
            patch("anvil.api.v1.experiments.MlflowClient") as mock_client_cls,
        ):
            mock_client = MagicMock()
            mock_client_cls.return_value = mock_client
            mock_client.download_artifacts.return_value = "/tmp/nonexistent/path"
            resp = await client.get(
                f"/v1/experiments/{exp_id}/runs/{mlflow_run_id}/download",
                params={"path": "model.safetensors"},
            )
        assert resp.status_code == 500

    async def test_returns_500_on_mlflow_exception(self, client):
        """Returns 500 when MlflowException is raised during download."""
        exp_id = 42
        mlflow_run_id = "mlflow_dl_5"

        async def _fake_get_experiment(eid: int) -> dict | None:
            if eid == exp_id:
                return {"id": exp_id, "mlflow_run_id": mlflow_run_id}
            return None

        with (
            patch.object(
                TrackingService, "get_experiment", side_effect=_fake_get_experiment
            ),
            patch.object(
                TrackingService,
                "get_safetensors_artifacts",
                return_value={
                    "available": True,
                    "files": [
                        {
                            "path": "model.safetensors",
                            "file_size": 100,
                            "is_safetensors": True,
                            "is_config": False,
                            "is_tokenizer": False,
                        },
                    ],
                    "error": None,
                },
            ),
            patch("anvil.api.v1.experiments.MlflowClient") as mock_client_cls,
            patch("anvil.api.v1.experiments.MlflowException", MlflowException),
        ):
            mock_client = MagicMock()
            mock_client_cls.return_value = mock_client
            mock_client.download_artifacts.side_effect = MlflowException(
                "download failed"
            )
            resp = await client.get(
                f"/v1/experiments/{exp_id}/runs/{mlflow_run_id}/download",
                params={"path": "model.safetensors"},
            )
        assert resp.status_code == 500
        assert "Failed to download artifact" in resp.json()["detail"]

    async def test_returns_500_on_os_error(self, client):
        """Returns 500 when OSError is raised during download."""
        exp_id = 42
        mlflow_run_id = "mlflow_dl_6"

        async def _fake_get_experiment(eid: int) -> dict | None:
            if eid == exp_id:
                return {"id": exp_id, "mlflow_run_id": mlflow_run_id}
            return None

        with (
            patch.object(
                TrackingService, "get_experiment", side_effect=_fake_get_experiment
            ),
            patch.object(
                TrackingService,
                "get_safetensors_artifacts",
                return_value={
                    "available": True,
                    "files": [
                        {
                            "path": "model.safetensors",
                            "file_size": 100,
                            "is_safetensors": True,
                            "is_config": False,
                            "is_tokenizer": False,
                        },
                    ],
                    "error": None,
                },
            ),
            patch("anvil.api.v1.experiments.MlflowClient") as mock_client_cls,
        ):
            mock_client = MagicMock()
            mock_client_cls.return_value = mock_client
            mock_client.download_artifacts.side_effect = OSError("disk full")
            resp = await client.get(
                f"/v1/experiments/{exp_id}/runs/{mlflow_run_id}/download",
                params={"path": "model.safetensors"},
            )
        assert resp.status_code == 500
        assert "Failed to download artifact" in resp.json()["detail"]

    async def test_requires_path_query_param(self, client):
        """Returns 422 when path query param is missing."""
        exp_id = 42
        mlflow_run_id = "mlflow_dl_7"
        resp = await client.get(
            f"/v1/experiments/{exp_id}/runs/{mlflow_run_id}/download"
        )
        assert resp.status_code == 422


####################################################################
# Retry export endpoint
####################################################################


class TestRetryExport:
    """Tests for POST /v1/experiments/{experiment_id}/retry-export."""

    async def test_retry_export_successfully(self, client, tmp_path):
        """Happy path: retry export succeeds."""
        exp_id = 42
        mlflow_run_id = "mlflow_export_1"

        model_path = Path(f"data/models/experiment_{exp_id}.json")
        model_path.parent.mkdir(parents=True, exist_ok=True)
        model_path.write_text(
            json.dumps(
                {
                    "vocab_size": 100,
                    "n_embd": 16,
                    "n_head": 4,
                    "n_layer": 1,
                    "block_size": 16,
                    "state_dict": {},
                }
            )
        )

        async def _fake_get_experiment(eid: int) -> dict | None:
            if eid == exp_id:
                return {"id": exp_id, "mlflow_run_id": mlflow_run_id}
            return None

        with (
            patch.object(
                TrackingService, "get_experiment", side_effect=_fake_get_experiment
            ),
            patch(
                "anvil.services.training.export.SafetensorsExportService.retry_export"
            ) as mock_retry,
            patch.object(TrackingService, "log_artifacts"),
        ):
            mock_retry.return_value = {
                "error": None,
                "safetensors_path": "/tmp/model.safetensors",
                "config_path": "/tmp/config.json",
                "tokenizer_path": "/tmp/tokenizer.json",
                "mlmodel_path": None,
                "conda_path": None,
            }
            resp = await client.post(f"/v1/experiments/{exp_id}/retry-export")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "exported"
        assert data["safetensors_path"] is not None
        model_path.unlink(missing_ok=True)

    async def test_retry_export_returns_404_when_experiment_not_found(self, client):
        with patch.object(TrackingService, "get_experiment", return_value=None):
            resp = await client.post("/v1/experiments/999/retry-export")
        assert resp.status_code == 404

    async def test_retry_export_returns_404_when_model_missing(self, client):
        exp_id = 99

        async def _fake_get_experiment(eid: int) -> dict | None:
            if eid == exp_id:
                return {"id": exp_id, "mlflow_run_id": None}
            return None

        with patch.object(
            TrackingService, "get_experiment", side_effect=_fake_get_experiment
        ):
            resp = await client.post(f"/v1/experiments/{exp_id}/retry-export")
        assert resp.status_code == 404
        assert "No model artifact found" in resp.json()["detail"]

    async def test_retry_export_handles_export_error(self, client, tmp_path):
        """Returns 500 when the export itself fails."""
        exp_id = 43
        model_path = Path(f"data/models/experiment_{exp_id}.json")
        model_path.parent.mkdir(parents=True, exist_ok=True)
        model_path.write_text(
            json.dumps(
                {
                    "vocab_size": 100,
                    "n_embd": 16,
                    "n_head": 4,
                    "n_layer": 1,
                    "block_size": 16,
                }
            )
        )

        async def _fake_get_experiment(eid: int) -> dict | None:
            if eid == exp_id:
                return {"id": exp_id, "mlflow_run_id": "mlflow_export_2"}
            return None

        with (
            patch.object(
                TrackingService, "get_experiment", side_effect=_fake_get_experiment
            ),
            patch(
                "anvil.services.training.export.SafetensorsExportService.retry_export"
            ) as mock_retry,
        ):
            mock_retry.return_value = {
                "error": "Export failed: bad data",
                "safetensors_path": None,
                "config_path": None,
                "tokenizer_path": None,
                "mlmodel_path": None,
                "conda_path": None,
            }
            resp = await client.post(f"/v1/experiments/{exp_id}/retry-export")
        assert resp.status_code == 500
        assert "Export retry failed" in resp.json()["detail"]
        model_path.unlink(missing_ok=True)

    async def test_retry_export_without_mlflow_run_id(self, client, tmp_path):
        """Succeeds even without an mlflow_run_id."""
        exp_id = 44
        mlflow_run_id = None

        model_path = Path(f"data/models/experiment_{exp_id}.json")
        model_path.parent.mkdir(parents=True, exist_ok=True)
        model_path.write_text(
            json.dumps(
                {
                    "vocab_size": 100,
                    "n_embd": 16,
                    "n_head": 4,
                    "n_layer": 1,
                    "block_size": 16,
                }
            )
        )

        async def _fake_get_experiment(eid: int) -> dict | None:
            if eid == exp_id:
                return {"id": exp_id, "mlflow_run_id": mlflow_run_id}
            return None

        with (
            patch.object(
                TrackingService, "get_experiment", side_effect=_fake_get_experiment
            ),
            patch(
                "anvil.services.training.export.SafetensorsExportService.retry_export"
            ) as mock_retry,
        ):
            mock_retry.return_value = {
                "error": None,
                "safetensors_path": "/tmp/model.safetensors",
                "config_path": "/tmp/config.json",
                "tokenizer_path": "/tmp/tokenizer.json",
                "mlmodel_path": None,
                "conda_path": None,
            }
            resp = await client.post(f"/v1/experiments/{exp_id}/retry-export")
        assert resp.status_code == 200
        assert resp.json()["status"] == "exported"
        model_path.unlink(missing_ok=True)
