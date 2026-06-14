"""Tests for Experiment model lifecycle fields."""

from datetime import UTC, datetime, timezone

import pytest
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.ext.asyncio import AsyncSession

from anvil.db.base import Base
from anvil.db.models.training_config import Experiment
from anvil.db.repositories.experiments import ExperimentRepository
from anvil.db.session import AsyncSessionLocal, async_engine


@pytest.fixture
async def db_session():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as session:
        yield session
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def repo(db_session: AsyncSession):
    return ExperimentRepository(db_session)


@pytest.mark.asyncio
async def test_experiment_has_new_fields():
    mapper = sa_inspect(Experiment)
    columns = {c.key: c for c in mapper.columns}

    assert "run_name" in columns
    assert columns["run_name"].nullable is True

    assert "corpus_id" in columns
    assert columns["corpus_id"].nullable is True

    assert "input_digest" in columns
    assert columns["input_digest"].nullable is True

    assert "input_role" in columns
    assert columns["input_role"].nullable is True

    assert "engine_backend" in columns
    assert columns["engine_backend"].nullable is True

    assert "device" in columns
    assert columns["device"].nullable is True


@pytest.mark.asyncio
async def test_experiment_status_defaults_to_running(db_session: AsyncSession):
    exp = Experiment(config_id=1)
    db_session.add(exp)
    await db_session.flush()
    await db_session.refresh(exp)
    assert exp.status == "running"


@pytest.mark.asyncio
async def test_create_running(repo: ExperimentRepository):
    exp = await repo.create_running(
        config_id=1,
        run_name="test-run",
        mlflow_run_id="mlflow_123",
        dataset_id=5,
        corpus_id=None,
        engine_backend="stdlib",
        device="cpu",
    )
    assert exp.status == "running"
    assert exp.run_name == "test-run"
    assert exp.mlflow_run_id == "mlflow_123"
    assert exp.dataset_id == 5
    assert exp.engine_backend == "stdlib"
    assert exp.device == "cpu"
    assert exp.started_at is not None


@pytest.mark.asyncio
async def test_mark_finished(repo: ExperimentRepository):
    exp = await repo.create_running(
        config_id=1, run_name="finish-test", mlflow_run_id="mf1"
    )
    now = datetime.now(UTC)
    finished = await repo.mark_finished(
        experiment_id=exp.id,
        final_loss=0.123,
        generated_samples="sample1\nsample2",
        completed_at=now,
    )
    assert finished.status == "finished"
    assert finished.final_loss == 0.123
    assert finished.completed_at is not None


@pytest.mark.asyncio
async def test_mark_failed(repo: ExperimentRepository):
    exp = await repo.create_running(
        config_id=1, run_name="fail-test", mlflow_run_id="mf2"
    )
    now = datetime.now(UTC)
    failed = await repo.mark_failed(
        experiment_id=exp.id,
        error_message="something broke",
        completed_at=now,
    )
    assert failed.status == "failed"
    assert failed.error_message == "something broke"
    assert failed.completed_at is not None


@pytest.mark.asyncio
async def test_find_orphaned(repo: ExperimentRepository):
    await repo.create_running(config_id=1, run_name="orphan1", mlflow_run_id="o1")
    await repo.create_running(config_id=1, run_name="orphan2", mlflow_run_id="o2")
    finished = await repo.create_running(
        config_id=1, run_name="done", mlflow_run_id="o3"
    )
    now = datetime.now(UTC)
    await repo.mark_finished(
        finished.id, final_loss=0.5, generated_samples="", completed_at=now
    )

    orphans = await repo.find_orphaned()
    assert len(orphans) == 2
    for o in orphans:
        assert o.status == "running"
