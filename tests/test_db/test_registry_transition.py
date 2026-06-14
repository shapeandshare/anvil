"""Tests for local-to-MLflow registry migration."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from microgpt.db.models.registry import ModelVersion, RegisteredModel
from microgpt.db.models.training_config import Experiment, TrainingConfig
from microgpt.db.repositories.experiments import ExperimentRepository
from microgpt.db.repositories.models import ModelRepository
from microgpt.services.models import ModelRegistryService
from microgpt.services.tracking import TrackingService


class FakeMlflowClient:
    def __init__(self, tracking_uri: str | None = None):
        self.tracking_uri = tracking_uri
        self.registered_models: dict[str, list[str]] = {}
        self.version_counters: dict[str, int] = {}
        self.calls: list[tuple] = []

    def get_experiment_by_name(self, name: str) -> None:
        return None

    def create_experiment(self, name: str) -> str:
        return "0"

    def create_registered_model(self, name: str):
        self.calls.append(("create_registered_model", name))
        if name not in self.registered_models:
            self.registered_models[name] = []
        return type("FakeRM", (), {"name": name})()

    def create_model_version(self, name: str, source: str, run_id: str):
        self.calls.append(("create_model_version", name, source, run_id))
        if name not in self.version_counters:
            self.version_counters[name] = 0
        self.version_counters[name] += 1
        self.registered_models.setdefault(name, []).append(
            str(self.version_counters[name])
        )
        return type(
            "FakeMV", (), {"version": str(self.version_counters[name]), "name": name}
        )()


@pytest.fixture
def tracking_svc():
    ts = TrackingService(
        tracking_uri="http://fake:5000",
        client_factory=lambda uri: FakeMlflowClient(uri),
    )
    ts._lazy_init()
    return ts


@pytest.mark.asyncio
async def test_migration_migrates_existing_row(session: AsyncSession, tracking_svc):
    config = TrainingConfig()
    session.add(config)
    await session.flush()
    await session.refresh(config)

    exp = Experiment(
        config_id=config.id,
        status="finished",
        mlflow_run_id="exp-run-id",
        dataset_id=42,
    )
    session.add(exp)
    await session.flush()
    await session.refresh(exp)

    model = RegisteredModel(name="legacy-model")
    session.add(model)
    await session.flush()
    await session.refresh(model)

    version = ModelVersion(
        model_id=model.id,
        version=1,
        experiment_id=exp.id,
        artifact_path="data/models/registry/legacy-model/v1/model.json",
    )
    session.add(version)
    await session.commit()

    repo = ModelRepository(session)
    svc = ModelRegistryService(repo)
    result = await svc.migrate_local_registry_to_mlflow(tracking_svc)
    assert result["migrated"] >= 1

    fake_client = tracking_svc._client
    version_calls = [c for c in fake_client.calls if c[0] == "create_model_version"]
    assert len(version_calls) == 1
    assert version_calls[0][1] == "dataset-42"


@pytest.mark.asyncio
async def test_migration_best_effort_no_crash(session: AsyncSession):
    repo = ModelRepository(session)
    svc = ModelRegistryService(repo)
    broken_tracking = TrackingService(
        tracking_uri="http://localhost:99999",
    )
    result = await svc.migrate_local_registry_to_mlflow(broken_tracking)
    assert "migrated" in result
    assert "skipped" in result
    assert result["failed"] == 0


@pytest.mark.asyncio
async def test_migration_idempotent_no_crash(session: AsyncSession, tracking_svc):
    config = TrainingConfig()
    session.add(config)
    await session.flush()
    await session.refresh(config)

    exp = Experiment(
        config_id=config.id,
        status="finished",
        mlflow_run_id="dup-run-id",
        dataset_id=99,
    )
    session.add(exp)
    await session.flush()
    await session.refresh(exp)

    model = RegisteredModel(name="dup-model")
    session.add(model)
    await session.flush()
    await session.refresh(model)

    version = ModelVersion(
        model_id=model.id,
        version=1,
        experiment_id=exp.id,
        artifact_path="data/models/registry/dup-model/v1/model.json",
    )
    session.add(version)
    await session.commit()

    repo = ModelRepository(session)
    svc = ModelRegistryService(repo)

    r1 = await svc.migrate_local_registry_to_mlflow(tracking_svc)
    assert r1["migrated"] >= 1

    r2 = await svc.migrate_local_registry_to_mlflow(tracking_svc)
    assert r2["failed"] == 0
