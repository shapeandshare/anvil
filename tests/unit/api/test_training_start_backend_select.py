"""Tests for training start with compute_backend selection."""

from typing import Optional
from unittest.mock import ANY, patch

import pytest
from httpx import ASGITransport, AsyncClient

from anvil.api.app import app
from anvil.db.base import Base
from anvil.db.session import async_engine
from anvil.services.compute.compute_backend_unavailable import ComputeBackendUnavailable


class FakeMlflowClient:
    def __init__(self, tracking_uri: str):
        self.tracking_uri = tracking_uri
        self.created_runs = []

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
        pass

    def log_artifact(self, run_id, local_path):
        pass


@pytest.fixture(autouse=True)
async def setup_db():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
def fake_tracking():
    from anvil.services.tracking import TrackingService
    svc = TrackingService(
        tracking_uri="http://127.0.0.1:5000",
        client_factory=lambda uri: FakeMlflowClient(uri),
    )
    return svc


def _make_config(overrides: dict | None = None) -> dict:
    base = {
        "n_layer": 1,
        "n_embd": 16,
        "n_head": 4,
        "block_size": 16,
        "num_steps": 1,
        "learning_rate": 0.01,
        "beta1": 0.85,
        "beta2": 0.99,
        "temperature": 0.5,
    }
    if overrides:
        base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_compute_backend_auto_accepts(fake_tracking):
    """compute_backend='auto' is accepted and produces a successful run."""
    from anvil.api.v1 import training as training_module
    orig_svc = training_module.tracking_svc
    training_module.tracking_svc = fake_tracking

    config = _make_config({"compute_backend": "auto"})
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/v1/training/start", json=config)
            assert response.status_code == 200
            data = response.json()
            assert "run_id" in data
            assert data["status"] == "running"
    finally:
        training_module.tracking_svc = orig_svc


@pytest.mark.asyncio
async def test_compute_backend_local_cpu_accepts(fake_tracking):
    """compute_backend='local-cpu' is accepted and forces stdlib engine."""
    from anvil.api.v1 import training as training_module
    orig_svc = training_module.tracking_svc
    training_module.tracking_svc = fake_tracking

    config = _make_config({"compute_backend": "local-cpu"})
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/v1/training/start", json=config)
            assert response.status_code == 200
            data = response.json()
            assert "run_id" in data
    finally:
        training_module.tracking_svc = orig_svc


@pytest.mark.asyncio
async def test_compute_backend_local_gpu_falls_back_to_cpu(fake_tracking):
    """compute_backend='local-gpu' silently falls back to CPU if no GPU."""
    from anvil.api.v1 import training as training_module
    orig_svc = training_module.tracking_svc
    training_module.tracking_svc = fake_tracking

    config = _make_config({"compute_backend": "local-gpu"})
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/v1/training/start", json=config)
            assert response.status_code == 200
            data = response.json()
            assert "run_id" in data
    finally:
        training_module.tracking_svc = orig_svc


@pytest.mark.asyncio
async def test_compute_backend_modal_unavailable_returns_error(fake_tracking):
    """compute_backend='modal' returns 422 error when Modal is not available."""
    from anvil.api.v1 import training as training_module
    orig_svc = training_module.tracking_svc
    training_module.tracking_svc = fake_tracking

    config = _make_config({"compute_backend": "modal"})
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/v1/training/start", json=config)
            assert response.status_code == 422
            data = response.json()
            assert "detail" in data
            assert "Modal" in data["detail"] or "modal" in data["detail"].lower()
    finally:
        training_module.tracking_svc = orig_svc


@pytest.mark.asyncio
async def test_compute_backend_unknown_returns_error(fake_tracking):
    """An unknown compute_backend value returns a 422 error."""
    from anvil.api.v1 import training as training_module
    orig_svc = training_module.tracking_svc
    training_module.tracking_svc = fake_tracking

    config = _make_config({"compute_backend": "nonexistent-backend"})
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/v1/training/start", json=config)
            assert response.status_code == 422
            data = response.json()
            assert "detail" in data
    finally:
        training_module.tracking_svc = orig_svc


@pytest.mark.asyncio
async def test_compute_backend_defaults_to_auto(fake_tracking):
    """Omitting compute_backend defaults to 'auto' (backward compatible)."""
    from anvil.api.v1 import training as training_module
    orig_svc = training_module.tracking_svc
    training_module.tracking_svc = fake_tracking

    config = _make_config({})  # no compute_backend, no use_gpu
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/v1/training/start", json=config)
            assert response.status_code == 200
            data = response.json()
            assert "run_id" in data
    finally:
        training_module.tracking_svc = orig_svc