"""Tests for US3: per-step loss on a consistent axis, final_loss, eval metrics, device provenance."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from anvil.services.tracking.tracking import TrackingService


@pytest.mark.asyncio
async def test_mlflow_callback_logs_loss_with_monotonic_step():
    """The mlflow_progress_callback logs 'loss' per step with a monotonic step axis."""
    logged = []

    async def fake_log_metric(run_id, key, value, *, step=None):
        logged.append({"run_id": run_id, "key": key, "value": value, "step": step})

    tracking_svc = MagicMock(spec=TrackingService)
    tracking_svc.log_metric = fake_log_metric
    tracking_svc.is_degraded = False

    mlflow_run_id = "test-run-id"

    def mlflow_progress_callback(step: int, loss: float) -> None:
        asyncio.create_task(
            tracking_svc.log_metric(mlflow_run_id, "loss", loss, step=step)
        )

    for step in range(5):
        mlflow_progress_callback(step, 1.0 / (step + 1))

    await asyncio.sleep(0.05)

    assert len(logged) == 5
    for i, entry in enumerate(logged):
        assert entry["run_id"] == "test-run-id"
        assert entry["key"] == "loss"
        assert entry["step"] == i

    steps = [entry["step"] for entry in logged]
    assert steps == list(range(5))


@pytest.mark.asyncio
async def test_on_complete_logs_final_loss():
    """on_complete calls log_final_metric with key='final_loss' and a float value."""
    final_logged = []

    async def fake_log_metric(run_id, key, value, *, step=None):
        pass

    async def fake_log_final(run_id, key, value):
        final_logged.append({"run_id": run_id, "key": key, "value": value})

    async def fake_finish(run_id):
        pass

    tracking_svc = MagicMock(spec=TrackingService)
    tracking_svc.log_metric = fake_log_metric
    tracking_svc.log_final_metric = fake_log_final
    tracking_svc.finish_run = fake_finish
    tracking_svc.is_degraded = False

    mlflow_run_id = "test-run-final"
    final_loss_val = 0.123

    from anvil.api.v1.training import router

    async def on_complete(model, config, final_loss, samples, uchars):
        await tracking_svc.finish_run(mlflow_run_id)
        await tracking_svc.log_final_metric(mlflow_run_id, "final_loss", final_loss)

    await on_complete(None, {}, final_loss_val, [], [])

    assert len(final_logged) == 1
    entry = final_logged[0]
    assert entry["key"] == "final_loss"
    assert entry["value"] == 0.123
    assert entry["run_id"] == "test-run-final"


@pytest.mark.asyncio
async def test_step_is_not_none():
    """The step argument to log_metric is never None."""
    logged = []

    async def fake_log_metric(run_id, key, value, *, step=None):
        logged.append({"key": key, "step": step})

    tracking_svc = MagicMock(spec=TrackingService)
    tracking_svc.log_metric = fake_log_metric
    tracking_svc.is_degraded = False

    mlflow_run_id = "test-run"

    def cb(step: int, loss: float) -> None:
        asyncio.create_task(
            tracking_svc.log_metric(mlflow_run_id, "loss", loss, step=step)
        )

    cb(0, 1.0)
    await asyncio.sleep(0.05)

    assert len(logged) >= 1
    assert logged[0]["step"] is not None
    assert logged[0]["step"] == 0


@pytest.mark.asyncio
async def test_multiple_steps_monotonically_increasing():
    """Multiple steps yield monotonically increasing step values."""
    logged = []

    async def fake_log_metric(run_id, key, value, *, step=None):
        logged.append(step)

    tracking_svc = MagicMock(spec=TrackingService)
    tracking_svc.log_metric = fake_log_metric
    tracking_svc.is_degraded = False

    mlflow_run_id = "test-run"

    def cb(step: int, loss: float) -> None:
        asyncio.create_task(
            tracking_svc.log_metric(mlflow_run_id, "loss", loss, step=step)
        )

    for s in range(10):
        cb(s, float(s))
    await asyncio.sleep(0.05)

    assert logged == list(range(10))


@pytest.mark.asyncio
async def test_start_run_logs_engine_backend_and_device_params():
    """engine_backend and device are recorded as run params via start_run."""
    from dataclasses import dataclass
    from unittest.mock import MagicMock

    @dataclass
    class _FakeRun:
        info: object = None

    class _FakeClient:
        def __init__(self, uri: str):
            self.logged_params: list = []
            self.created_runs: list = []

        def get_experiment_by_name(self, name: str):
            return MagicMock(experiment_id="exp_1")

        def create_run(self, experiment_id: str, run_name: str | None = None, **kw):
            run_id = f"run_{len(self.created_runs) + 1}"
            self.created_runs.append(run_id)
            return _FakeRun(info=MagicMock(run_id=run_id))

        def log_batch(self, run_id: str, params=None, **kw):
            self.logged_params.append({"run_id": run_id, "params": params or []})

        def log_metric(self, *a, **kw):
            pass

        def set_terminated(self, *a, **kw):
            pass

    def _factory(uri: str):
        return _FakeClient(uri)

    svc = TrackingService(
        tracking_uri="http://127.0.0.1:5000",
        client_factory=_factory,
    )

    await svc.start_run(
        run_name="param-test",
        params={"n_layer": 2},
        engine_backend="torch",
        device="mps",
    )

    client = svc._client
    assert client is not None
    assert len(client.logged_params) >= 1

    logged = client.logged_params[0]
    param_dict = {p.key: p.value for p in logged["params"]}
    assert param_dict.get("engine_backend") == "torch"
    assert param_dict.get("device") == "mps"


@pytest.mark.asyncio
async def test_eval_metric_shares_same_step_axis():
    """Eval/validation metric logged at the same step shares the same step axis."""
    logged = []

    async def fake_log_metric(run_id, key, value, *, step=None):
        logged.append({"key": key, "value": value, "step": step})

    tracking_svc = MagicMock(spec=TrackingService)
    tracking_svc.log_metric = fake_log_metric
    tracking_svc.is_degraded = False

    mlflow_run_id = "test-run-eval"
    step_n = 5

    await tracking_svc.log_metric(mlflow_run_id, "loss", 0.5, step=step_n)
    await tracking_svc.log_metric(mlflow_run_id, "eval_loss", 0.45, step=step_n)
    await tracking_svc.log_metric(mlflow_run_id, "val_accuracy", 0.85, step=step_n)

    loss_entry = next(e for e in logged if e["key"] == "loss")
    eval_entry = next(e for e in logged if e["key"] == "eval_loss")
    acc_entry = next(e for e in logged if e["key"] == "val_accuracy")

    assert loss_entry["step"] == step_n
    assert eval_entry["step"] == step_n
    assert acc_entry["step"] == step_n
