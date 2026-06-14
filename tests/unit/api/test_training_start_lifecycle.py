"""Tests for training start lifecycle (Experiment created at start)."""

import json
from unittest.mock import ANY

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from anvil.api.app import app
from anvil.db.base import Base
from anvil.db.repositories.experiments import ExperimentRepository
from anvil.db.session import AsyncSessionLocal, async_engine
from anvil.services.tracking import TrackingService


class FakeClientForTraining:
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


@pytest.fixture
async def db_session():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as session:
        yield session
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
def fake_tracking():
    svc = TrackingService(
        tracking_uri="http://127.0.0.1:5000",
        client_factory=lambda uri: FakeClientForTraining(uri),
    )
    return svc


@pytest.mark.asyncio
async def test_training_start_creates_experiment(
    db_session: AsyncSession, fake_tracking
):
    from anvil.api.v1 import training as training_module
    from anvil.api.v1.training import router

    orig_svc = training_module.tracking_svc
    training_module.tracking_svc = fake_tracking

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
            assert "run_id" in data
            assert "mlflow_run_id" in data
            assert "experiment_id" in data or "status" in data
    finally:
        training_module.tracking_svc = orig_svc
