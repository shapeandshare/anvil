import asyncio
from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from anvil.api.app import app
from anvil.db.repositories.experiments import ExperimentRepository
from anvil.services.tracking import TrackingService


class _FakeClientForFailure:
    def __init__(self, tracking_uri: str):
        self.tracking_uri = tracking_uri
        self.created_runs = []
        self.terminated = {}

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
        pass

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
    session: AsyncSession, _fake_tracking
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
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            config = {
                "n_layer": 1,
                "n_embd": 16,
                "n_head": 4,
                "block_size": 16,
                "num_steps": 1,
                "learning_rate": 0.01,
                "beta1": 0.85,
                "beta2": 0.99,
                "temperature": 0.5,
                "use_gpu": False,
            }
            response = await client.post("/v1/training/start", json=config)
            assert response.status_code == 200
            data = response.json()
            experiment_id = data["experiment_id"]

            await asyncio.sleep(1)

            assert len(_fake_tracking._fail_run_calls) == 1
            _, call_reason = _fake_tracking._fail_run_calls[0]
            assert call_reason == "training failed!"
            assert len(_fake_tracking._finish_run_calls) == 0

            repo = ExperimentRepository(session)
            exp = await repo.get(experiment_id)
            assert exp is not None
            assert exp.status == "failed"
            assert exp.error_message == "training failed!"
            assert exp.completed_at is not None
    finally:
        training_module.tracking_svc = orig_tracking_svc
        training_module.svc.start_training = orig_start_training


@pytest.mark.asyncio
async def test_successful_training_marks_finished(session: AsyncSession):
    repo = ExperimentRepository(session)
    exp = await repo.create_running(
        config_id=0,
        run_name="happy-path-test",
        mlflow_run_id="mlflow_42",
        engine_backend="stdlib",
        device="cpu",
    )
    await session.commit()
    experiment_id = exp.id

    from datetime import UTC, datetime

    await repo.mark_finished(
        experiment_id=experiment_id,
        final_loss=0.123,
        completed_at=datetime.now(UTC),
    )
    await session.commit()

    updated = await repo.get(experiment_id)
    assert updated is not None
    assert updated.status == "finished"
    assert updated.final_loss == 0.123


@pytest.mark.asyncio
async def test_list_artifacts_no_mlflow_run(session: AsyncSession, client: AsyncClient):
    """GET /experiments/{id}/runs/{run_id}/artifacts returns 404 when experiment has no MLflow run."""
    repo = ExperimentRepository(session)
    exp = await repo.create_running(
        config_id=0,
        run_name="no-mlflow",
        mlflow_run_id=None,
        engine_backend="stdlib",
        device="cpu",
    )
    await session.commit()

    response = await client.get(f"/v1/experiments/{exp.id}/runs/nonexistent/artifacts")
    assert response.status_code == 404
    assert "No MLflow run associated" in response.json()["detail"]


@pytest.mark.asyncio
async def test_download_artifact_no_mlflow_run(session: AsyncSession, client: AsyncClient):
    """GET /experiments/{id}/runs/{run_id}/download returns 404 when experiment has no MLflow run."""
    repo = ExperimentRepository(session)
    exp = await repo.create_running(
        config_id=0,
        run_name="no-mlflow-dl",
        mlflow_run_id=None,
        engine_backend="stdlib",
        device="cpu",
    )
    await session.commit()

    response = await client.get(
        f"/v1/experiments/{exp.id}/runs/nonexistent/download",
        params={"path": "model.safetensors"},
    )
    assert response.status_code == 404
    assert "No MLflow run associated" in response.json()["detail"]


@pytest.mark.asyncio
async def test_download_artifact_not_found(session: AsyncSession, client: AsyncClient):
    """GET /experiments/{id}/runs/{run_id}/download returns 404 when no artifacts exist for the run."""
    from anvil.services.tracking import TrackingService

    repo = ExperimentRepository(session)
    exp = await repo.create_running(
        config_id=0,
        run_name="artifact-test",
        mlflow_run_id="mlflow_artifact_test",
        engine_backend="stdlib",
        device="cpu",
    )
    await session.commit()

    with patch.object(
        TrackingService, "get_safetensors_artifacts", return_value={
            "available": False, "files": [], "error": None,
        }
    ):
        response = await client.get(
            f"/v1/experiments/{exp.id}/runs/mlflow_artifact_test/download",
            params={"path": "nonexistent.safetensors"},
        )
    assert response.status_code == 404
    assert "No safetensors artifacts found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_list_artifacts_run_id_mismatch(session: AsyncSession, client: AsyncClient):
    """GET /experiments/{id}/runs/{run_id}/artifacts returns 400 when run_id doesn't match."""
    repo = ExperimentRepository(session)
    exp = await repo.create_running(
        config_id=0,
        run_name="mismatch-test",
        mlflow_run_id="real_run_id",
        engine_backend="stdlib",
        device="cpu",
    )
    await session.commit()

    response = await client.get(
        f"/v1/experiments/{exp.id}/runs/wrong_run_id/artifacts"
    )
    assert response.status_code == 400
    assert "does not match" in response.json()["detail"]
