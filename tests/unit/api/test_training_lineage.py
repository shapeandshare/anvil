"""Tests for training start lineage (dataset/corpus input logging)."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from anvil.api.app import app
from anvil.db.base import Base
from anvil.db.session import AsyncSessionLocal, async_engine


class FakeLineageClient:
    def __init__(self, tracking_uri: str):
        self.tracking_uri = tracking_uri
        self.created_runs = []
        self.logged_inputs = []
        self.tags: dict[str, dict[str, str]] = {}

    def get_experiment_by_name(self, name):
        from unittest.mock import MagicMock

        return MagicMock(experiment_id="exp_1")

    def create_experiment(self, name):
        return "exp_1"

    def create_run(self, experiment_id, run_name=None, tags=None):
        from unittest.mock import MagicMock

        run_id = f"mlflow_{len(self.created_runs) + 1}"
        self.created_runs.append(run_id)
        self.tags[run_id] = {}
        return MagicMock(info=MagicMock(run_id=run_id))

    def log_batch(self, run_id, params=None, metrics=None, tags=None):
        pass

    def log_metric(self, run_id, key, value, step=None):
        pass

    def set_terminated(self, run_id, status="FINISHED"):
        pass

    def log_artifact(self, run_id, local_path):
        pass

    def log_input(self, run_id, dataset, context=None):
        self.logged_inputs.append(
            {"run_id": run_id, "dataset": dataset, "context": context}
        )

    def set_tag(self, run_id, key, value):
        if run_id not in self.tags:
            self.tags[run_id] = {}
        self.tags[run_id][key] = value


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
    from anvil.services.tracking import TrackingService

    svc = TrackingService(
        tracking_uri="http://127.0.0.1:5000",
        client_factory=lambda uri: FakeLineageClient(uri),
    )
    return svc


BASE_CONFIG = {
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


@pytest.mark.asyncio
async def test_start_with_dataset_id_calls_log_dataset_input(db_session, fake_tracking):
    from anvil.api.v1 import training as training_module

    orig_svc = training_module.tracking_svc
    training_module.tracking_svc = fake_tracking

    with patch.object(
        fake_tracking, "log_dataset_input", new=AsyncMock(return_value="abc123")
    ):
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                config = {**BASE_CONFIG, "dataset_id": 1}
                response = await client.post("/v1/training/start", json=config)
                assert response.status_code == 200

            fake_tracking.log_dataset_input.assert_called_once()
            _, kwargs = fake_tracking.log_dataset_input.call_args
            assert kwargs.get("dataset_id") == 1
            assert kwargs.get("role") == "training"

        finally:
            training_module.tracking_svc = orig_svc


@pytest.mark.asyncio
async def test_start_with_corpus_id_calls_log_corpus_input(db_session, fake_tracking):
    from anvil.api.v1 import training as training_module

    orig_svc = training_module.tracking_svc
    training_module.tracking_svc = fake_tracking

    with patch.object(
        fake_tracking, "log_corpus_input", new=AsyncMock(return_value="def456")
    ):
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                config = {**BASE_CONFIG, "corpus_id": 1}
                response = await client.post("/v1/training/start", json=config)
                assert response.status_code == 200

            fake_tracking.log_corpus_input.assert_called_once()
            _, kwargs = fake_tracking.log_corpus_input.call_args
            assert kwargs.get("corpus_id") == 1

        finally:
            training_module.tracking_svc = orig_svc


@pytest.mark.asyncio
async def test_no_dataset_or_corpus_no_phantom_input(db_session, fake_tracking):
    from anvil.api.v1 import training as training_module

    orig_svc = training_module.tracking_svc
    training_module.tracking_svc = fake_tracking

    with (
        patch.object(
            fake_tracking, "log_dataset_input", new=AsyncMock(return_value="abc123")
        ),
        patch.object(
            fake_tracking, "log_corpus_input", new=AsyncMock(return_value="def456")
        ),
    ):
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                config = {**BASE_CONFIG}
                response = await client.post("/v1/training/start", json=config)
                assert response.status_code == 200

            fake_tracking.log_dataset_input.assert_not_called()
            fake_tracking.log_corpus_input.assert_not_called()

        finally:
            training_module.tracking_svc = orig_svc


@pytest.mark.asyncio
async def test_start_with_dataset_id_persists_input_digest(db_session, fake_tracking):
    from anvil.api.v1 import training as training_module

    orig_svc = training_module.tracking_svc
    training_module.tracking_svc = fake_tracking

    with patch.object(
        fake_tracking, "log_dataset_input", new=AsyncMock(return_value="abc123digest")
    ):
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                config = {**BASE_CONFIG, "dataset_id": 1}
                response = await client.post("/v1/training/start", json=config)
                assert response.status_code == 200
                data = response.json()

            mlflow_run_id = data.get("mlflow_run_id")
            assert mlflow_run_id is not None

            # input_digest is now stored as MLflow tags, not in ExperimentRepository
            client = fake_tracking._client
            assert client is not None
            run_tags = client.tags.get(mlflow_run_id, {})
            assert run_tags.get("anvil.input_digest") == "abc123digest"
            assert run_tags.get("anvil.input_role") == "training"

        finally:
            training_module.tracking_svc = orig_svc


@pytest.mark.asyncio
async def test_no_input_id_no_digest(db_session, fake_tracking):
    from anvil.api.v1 import training as training_module

    orig_svc = training_module.tracking_svc
    training_module.tracking_svc = fake_tracking

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            config = {**BASE_CONFIG}
            response = await client.post("/v1/training/start", json=config)
            assert response.status_code == 200
            data = response.json()

        mlflow_run_id = data.get("mlflow_run_id")
        assert mlflow_run_id is not None

        # input_digest is now stored as MLflow tags; no dataset/corpus means no tag set
        client = fake_tracking._client
        assert client is not None
        run_tags = client.tags.get(mlflow_run_id, {})
        assert run_tags.get("anvil.input_digest") is None
        assert run_tags.get("anvil.input_role") is None

    finally:
        training_module.tracking_svc = orig_svc
