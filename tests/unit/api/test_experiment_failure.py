# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from anvil.api.app import app
from anvil.api.deps import get_api_key_store
from anvil.services.tracking.tracking import TrackingService


class _FakeClientForFailure:
    def __init__(self, tracking_uri: str):
        self.tracking_uri = tracking_uri
        self.created_runs = []
        self.terminated = {}
        self.logged_metrics: dict[str, dict[str, float]] = {}

    def get_experiment_by_name(self, name):
        from unittest.mock import MagicMock

        return MagicMock(experiment_id="exp_1")

    def create_experiment(self, name):
        return "exp_1"

    def create_run(self, experiment_id, run_name=None, tags=None):
        from unittest.mock import MagicMock

        run_id = f"mlflow_{len(self.created_runs) + 1}"
        self.created_runs.append(run_id)
        return MagicMock(info=MagicMock(run_id=run_id))

    def log_batch(self, run_id, params=None, metrics=None, tags=None):
        pass

    def log_metric(self, run_id, key, value, step=None):
        if run_id not in self.logged_metrics:
            self.logged_metrics[run_id] = {}
        self.logged_metrics[run_id][key] = value

    def set_terminated(self, run_id, status="FINISHED"):
        self.terminated[run_id] = status

    def log_artifact(self, run_id, local_path):
        pass

    def search_runs(self, experiment_ids, filter_string):
        return []


@pytest.fixture
def _fake_tracking():
    svc = TrackingService(
        tracking_uri="http://127.0.0.1:5000",
        client_factory=lambda uri: _FakeClientForFailure(uri),
    )
    svc._fail_run_calls = []
    orig_fail_run = svc.fail_run

    async def fail_run_spy(run_id: str, *, reason: str | None = None):
        svc._fail_run_calls.append((run_id, reason))
        await orig_fail_run(run_id, reason=reason)

    svc.fail_run = fail_run_spy
    svc._finish_run_calls = []
    orig_finish_run = svc.finish_run

    async def finish_run_spy(run_id: str):
        svc._finish_run_calls.append(run_id)
        await orig_finish_run(run_id)

    svc.finish_run = finish_run_spy
    return svc


@pytest.mark.asyncio
async def test_training_exception_triggers_fail_run(
    _fake_tracking,
):
    from anvil.api.v1 import training as training_module

    orig_tracking_svc = training_module.tracking_svc
    orig_start_training = training_module.svc.start_training

    training_module.tracking_svc = _fake_tracking

    async def broken_start_training(
        config, run_id=None, on_complete=None, progress_callback_override=None
    ):
        raise ValueError("training failed!")

    training_module.svc.start_training = broken_start_training

    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(
            transport=transport,
            base_url="https://test",
            headers={"X-API-Key": get_api_key_store().key or ""},
        ) as client:
            config = {
                "n_layer": 1,
                "n_embd": 16,
                "n_head": 4,
                "block_size": 16,
                "num_steps": 10,
            }
            response = await client.post("/v1/training/start", json=config)
            assert response.status_code == 200
            data = response.json()

            await asyncio.sleep(1)

            assert len(_fake_tracking._fail_run_calls) == 1
            _, call_reason = _fake_tracking._fail_run_calls[0]
            assert call_reason == "training failed!"
            assert len(_fake_tracking._finish_run_calls) == 0

            assert _fake_tracking._client is not None
            assert (
                _fake_tracking._client.terminated.get(data["mlflow_run_id"]) == "FAILED"
            )
    finally:
        training_module.tracking_svc = orig_tracking_svc
        training_module.svc.start_training = orig_start_training


@pytest.mark.asyncio
async def test_successful_training_marks_finished():
    """Successful training finishes the MLflow run and logs final_loss."""
    client = _FakeClientForFailure("http://127.0.0.1:5000")
    client.create_experiment("anvil")
    client.create_run("exp_1")
    run_id = client.created_runs[0]

    svc = TrackingService(
        tracking_uri="http://127.0.0.1:5000",
        client_factory=lambda uri: client,
    )
    svc._lazy_init()

    await svc.finish_run(run_id)
    await svc.log_final_metric(run_id, "final_loss", 0.123)

    assert client.terminated.get(run_id) == "FINISHED"
    assert client.logged_metrics.get(run_id, {}).get("final_loss") == 0.123


@pytest.mark.asyncio
async def test_list_artifacts_no_mlflow_run(client: AsyncClient):
    response = await client.get("/v1/experiments/999/runs/nonexistent/artifacts")
    assert response.status_code == 404
    assert "Experiment not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_download_artifact_no_mlflow_run(client: AsyncClient):
    response = await client.get(
        "/v1/experiments/999/runs/nonexistent/download",
        params={"path": "model.safetensors"},
    )
    assert response.status_code == 404
    assert "Experiment not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_download_artifact_not_found(client: AsyncClient):
    """GET /experiments/{id}/runs/{run_id}/download returns 404 when no artifacts exist for the run."""
    exp_id = 42
    mlflow_run_id = "mlflow_artifact_test"

    async def _fake_get_experiment(eid: int) -> dict | None:
        if eid == exp_id:
            return {
                "id": exp_id,
                "mlflow_run_id": mlflow_run_id,
                "status": "running",
                "run_name": "artifact-test",
                "final_loss": None,
                "params": {},
                "metrics": {},
                "tags": {},
            }
        return None

    with (
        patch.object(
            TrackingService, "get_experiment", side_effect=_fake_get_experiment
        ),
        patch.object(
            TrackingService,
            "get_safetensors_artifacts",
            return_value={
                "available": False,
                "files": [],
                "error": None,
            },
        ),
    ):
        response = await client.get(
            f"/v1/experiments/{exp_id}/runs/{mlflow_run_id}/download",
            params={"path": "nonexistent.safetensors"},
        )
    assert response.status_code == 404
    assert "No safetensors artifacts found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_list_artifacts_run_id_mismatch(client: AsyncClient):
    """GET /experiments/{id}/runs/{run_id}/artifacts returns 400 when run_id doesn't match."""
    exp_id = 42

    async def _fake_get_experiment(eid: int) -> dict | None:
        if eid == exp_id:
            return {
                "id": exp_id,
                "mlflow_run_id": "real_run_id",
                "status": "running",
                "run_name": "mismatch-test",
                "final_loss": None,
                "params": {},
                "metrics": {},
                "tags": {},
            }
        return None

    with patch.object(
        TrackingService, "get_experiment", side_effect=_fake_get_experiment
    ):
        response = await client.get(
            f"/v1/experiments/{exp_id}/runs/wrong_run_id/artifacts"
        )
    assert response.status_code == 400
    assert "does not match" in response.json()["detail"]
