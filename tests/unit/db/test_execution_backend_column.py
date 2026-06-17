"""Tests for execution_backend and remote_job_id columns on Experiment."""

import pytest
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.ext.asyncio import AsyncSession

from anvil.db.models.training_config import Experiment
from anvil.db.repositories.experiments import ExperimentRepository


@pytest.fixture
async def repo(session: AsyncSession):
    return ExperimentRepository(session)


@pytest.mark.asyncio
async def test_experiment_has_execution_backend_column():
    """Verify execution_backend column exists and is nullable."""
    mapper = sa_inspect(Experiment)
    columns = {c.key: c for c in mapper.columns}

    assert "execution_backend" in columns
    col = columns["execution_backend"]
    assert col.nullable is True
    assert col.type.length == 32


@pytest.mark.asyncio
async def test_experiment_has_remote_job_id_column():
    """Verify remote_job_id column exists and is nullable."""
    mapper = sa_inspect(Experiment)
    columns = {c.key: c for c in mapper.columns}

    assert "remote_job_id" in columns
    col = columns["remote_job_id"]
    assert col.nullable is True
    assert col.type.length == 128


@pytest.mark.asyncio
async def test_new_columns_default_to_null(session: AsyncSession):
    """New columns should default to NULL on creation."""
    exp = Experiment(config_id=1, run_name="defaults-test")
    session.add(exp)
    await session.flush()
    await session.refresh(exp)

    assert exp.execution_backend is None
    assert exp.remote_job_id is None


@pytest.mark.asyncio
async def test_write_and_read_execution_backend(session: AsyncSession):
    """Execution backend can be written and read back."""
    exp = Experiment(
        config_id=1,
        run_name="backend-test",
        execution_backend="remote-ssh",
    )
    session.add(exp)
    await session.flush()
    await session.refresh(exp)

    assert exp.execution_backend == "remote-ssh"


@pytest.mark.asyncio
async def test_write_and_read_remote_job_id(session: AsyncSession):
    """Remote job ID can be written and read back."""
    exp = Experiment(
        config_id=1,
        run_name="job-id-test",
        remote_job_id="slurm-12345",
    )
    session.add(exp)
    await session.flush()
    await session.refresh(exp)

    assert exp.remote_job_id == "slurm-12345"


@pytest.mark.asyncio
async def test_set_remote_job_id_repository_method(repo: ExperimentRepository):
    """set_remote_job_id updates and returns the experiment."""
    exp = await repo.create_running(config_id=1, run_name="remote-test")

    updated = await repo.set_remote_job_id(
        experiment_id=exp.id,
        job_id="aws-batch-abc-456",
    )

    assert updated.remote_job_id == "aws-batch-abc-456"
    assert updated.id == exp.id

    # Verify persistence — re-fetch and check
    refetched = await repo.get(exp.id)
    assert refetched is not None
    assert refetched.remote_job_id == "aws-batch-abc-456"


@pytest.mark.asyncio
async def test_set_remote_job_id_raises_on_missing(repo: ExperimentRepository):
    """set_remote_job_id raises ValueError for nonexistent experiment."""
    with pytest.raises(ValueError, match="not found"):
        await repo.set_remote_job_id(experiment_id=9999, job_id="missing-job")


@pytest.mark.asyncio
async def test_execution_backend_length_constraint(session: AsyncSession):
    """Verify execution_backend max length via column metadata."""
    mapper = sa_inspect(Experiment)
    col = mapper.columns["execution_backend"]
    assert col.type.length == 32


@pytest.mark.asyncio
async def test_remote_job_id_length_constraint(session: AsyncSession):
    """Verify remote_job_id max length via column metadata."""
    mapper = sa_inspect(Experiment)
    col = mapper.columns["remote_job_id"]
    assert col.type.length == 128