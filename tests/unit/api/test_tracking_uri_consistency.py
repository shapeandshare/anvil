# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for tracking URI consistency across API modules.

Phase 4 User Story 2 — Consistent tracking destination + CLI parity.
T025: No hardcoded MLflow URIs in API modules.
T027: Degraded-mode response contracts.
"""

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from anvil.api.app import app
from anvil.api.deps import get_api_key_store
from anvil.db.base import Base
from anvil.db.session import AsyncSessionLocal, async_engine
from anvil.services.tracking.tracking import TrackingService

API_DIR = Path("anvil/api/v1")


@pytest.fixture(autouse=True)
async def setup_db():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


def test_experiments_py_no_hardcoded_sqlite_uri():
    src = (API_DIR / "experiments.py").read_text()
    assert "sqlite:///./mlruns" not in src


def test_experiments_py_no_hardcoded_http_uri():
    src = (API_DIR / "experiments.py").read_text()
    assert '"http://127.0.0.1:5000"' not in src


def test_registry_py_no_hardcoded_sqlite_uri():
    src = (API_DIR / "registry.py").read_text()
    assert "sqlite:///./mlruns" not in src


def test_registry_py_no_hardcoded_http_uri():
    src = (API_DIR / "registry.py").read_text()
    assert '"http://127.0.0.1:5000"' not in src


def test_experiments_py_no_mlflow_uri_constant():
    src = (API_DIR / "experiments.py").read_text()
    assert "MLFLOW_TRACKING_URI" not in src and "MLFLOW_UI_URI" not in src


def test_registry_py_no_mlflow_uri_constant():
    src = (API_DIR / "registry.py").read_text()
    assert "MLFLOW_TRACKING_URI" not in src


class _DegradingClient:
    def __init__(self, tracking_uri: str):
        self.tracking_uri = tracking_uri

    def get_experiment_by_name(self, name):
        return None

    def create_experiment(self, name):
        return "exp_degraded"

    def create_run(self, experiment_id, run_name=None, tags=None):
        raise ConnectionError("MLflow not available")

    def log_batch(self, run_id, params=None, metrics=None, tags=None):
        pass

    def log_metric(self, run_id, key, value, step=None):
        pass

    def set_terminated(self, run_id, status="FINISHED"):
        pass

    def log_artifact(self, run_id, local_path):
        pass


class _FakeClientForDegradedTest:
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


@pytest.mark.asyncio
async def test_training_start_degraded_mode_returns_200():
    svc = TrackingService(
        tracking_uri="http://127.0.0.1:5000",
        client_factory=lambda uri: _DegradingClient(uri),
    )
    transport = ASGITransport(app=app)
    from anvil.api.v1 import training as training_module

    orig_svc = training_module.tracking_svc
    training_module.tracking_svc = svc
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
                "num_steps": 1,
            }
            response = await client.post("/v1/training/start", json=config)
            assert response.status_code == 200
            data = response.json()
            assert data.get("tracking") == "degraded"
            assert data.get("mlflow_run_id") is None
            assert "run_id" in data
    finally:
        training_module.tracking_svc = orig_svc


@pytest.mark.asyncio
async def test_training_start_active_mode_returns_mlflow_run_id():
    svc = TrackingService(
        tracking_uri="http://127.0.0.1:5000",
        client_factory=lambda uri: _FakeClientForDegradedTest(uri),
    )
    from anvil.api.v1 import training as training_module

    orig_svc = training_module.tracking_svc
    training_module.tracking_svc = svc
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
                "num_steps": 1,
            }
            response = await client.post("/v1/training/start", json=config)
            assert response.status_code == 200
            data = response.json()
            assert data.get("tracking") == "active"
            assert data.get("mlflow_run_id") is not None
            assert "run_id" in data
    finally:
        training_module.tracking_svc = orig_svc
