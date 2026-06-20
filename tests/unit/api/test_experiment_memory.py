"""Tests for per-run memory enrichment on the experiment detail endpoint."""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from anvil.api.v1.experiments import _hyperparams_from_mlflow
from anvil.services.tracking.tracking import TrackingService


class _FakeMetric:
    def __init__(self, value):
        self.value = value


class _FakeMlflowClient:
    def __init__(self, *a, **kw):
        self._metrics = {
            "loss": 0.5,
            "system/gpu_memory_gb": 3.5,
            "system/gpu_util_pct": 80.0,
        }
        self._params = {
            "n_embd": "64",
            "n_head": "4",
            "n_layer": "2",
            "block_size": "32",
            "num_steps": "100",
            "learning_rate": "0.01",
        }

    def get_experiment_by_name(self, name):
        return SimpleNamespace(experiment_id="exp_1")

    def get_run(self, run_id):
        return SimpleNamespace(
            data=SimpleNamespace(
                params=self._params,
                metrics=self._metrics,
                tags={"architectures": "LlamaForCausalLM"},
            )
        )

    def get_metric_history(self, run_id, metric_name):
        if metric_name == "system/gpu_memory_gb":
            return [_FakeMetric(2.0), _FakeMetric(3.5), _FakeMetric(3.0)]
        if metric_name == "system/gpu_util_pct":
            return [_FakeMetric(50.0), _FakeMetric(80.0), _FakeMetric(60.0)]
        return [_FakeMetric(0.5)]


class TestHyperparamsFromMlflow:
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

    def test_skips_missing_and_unparseable(self):
        hp = _hyperparams_from_mlflow({"n_embd": "not-a-number", "n_head": "4"})
        assert "n_embd" not in hp
        assert hp["n_head"] == 4


@pytest.mark.asyncio
async def test_experiment_detail_includes_memory_estimate(client):
    exp_id = 42

    model_path = Path(f"data/models/experiment_{exp_id}.json")
    model_path.parent.mkdir(parents=True, exist_ok=True)
    model_path.write_text(
        json.dumps(
            {
                "vocab_size": 100,
                "n_embd": 64,
                "n_head": 4,
                "n_layer": 2,
                "block_size": 32,
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
                "run_name": "mem-test",
                "final_loss": 0.5,
                "params": {},
                "metrics": {},
                "tags": {},
                "created_at": "",
                "completed_at": None,
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

            assert data["model_architecture"]["num_params"] > 0
            mem = data["memory_estimate"]
            assert mem is not None
            assert mem["param_count"] == data["model_architecture"]["num_params"]
            assert mem["peak_mb"] > 0
            assert mem["weights_mb"] > 0
            assert mem["optimizer_mb"] == pytest.approx(mem["weights_mb"] * 2, rel=0.01)
            assert data["gpu_memory_peak_gb"] is None
            assert data["gpu_util_peak_pct"] is None
        finally:
            model_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_experiment_detail_no_artifact_has_null_memory(client):
    exp_id = 43

    async def _fake_get_experiment(eid: int) -> dict | None:
        if eid == exp_id:
            return {
                "id": exp_id,
                "mlflow_run_id": None,
                "status": "FINISHED",
                "run_name": "no-artifact",
                "final_loss": None,
                "params": {},
                "metrics": {},
                "tags": {},
                "created_at": "",
                "completed_at": None,
                "engine_backend": "stdlib",
                "device": "cpu",
            }
        return None

    with patch.object(
        TrackingService, "get_experiment", side_effect=_fake_get_experiment
    ):
        resp = await client.get(f"/v1/experiments/{exp_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["memory_estimate"] is None
    assert data["model_architecture"] is None


@pytest.mark.asyncio
async def test_experiment_detail_surfaces_gpu_peaks_and_param_fallback(client):
    exp_id = 44
    mlflow_run_id = "mlflow_gpu_1"

    async def _fake_get_experiment(eid: int) -> dict | None:
        if eid == exp_id:
            return {
                "id": exp_id,
                "mlflow_run_id": mlflow_run_id,
                "status": "FINISHED",
                "run_name": "gpu-run",
                "final_loss": 0.5,
                "params": {
                    "n_embd": "64",
                    "n_head": "4",
                    "n_layer": "2",
                    "block_size": "32",
                    "num_steps": "100",
                    "learning_rate": "0.01",
                },
                "metrics": {},
                "tags": {},
                "created_at": "",
                "completed_at": None,
                "engine_backend": "torch",
                "device": "cuda:0",
            }
        return None

    async def _fake_artifacts(self, run_id):
        return {"available": False, "files": [], "error": None}

    with (
        patch("anvil.api.v1.experiments.MlflowClient", _FakeMlflowClient),
        patch.object(TrackingService, "get_experiment", side_effect=_fake_get_experiment),
        patch.object(TrackingService, "get_safetensors_artifacts", _fake_artifacts),
    ):
        resp = await client.get(f"/v1/experiments/{exp_id}")

    assert resp.status_code == 200
    data = resp.json()
    assert data["gpu_memory_peak_gb"] == 3.5
    assert data["gpu_util_peak_pct"] == 80.0
    assert data["hyperparameters"]["n_embd"] == 64