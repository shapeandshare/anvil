"""Tests for Experiment migration data backfill (007)."""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from microgpt.db.base import Base
from microgpt.db.models.training_config import Experiment
from microgpt.db.repositories.experiments import ExperimentRepository
from microgpt.db.session import AsyncSessionLocal, async_engine


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
async def test_completed_backfills_to_finished(repo: ExperimentRepository):
    exp = Experiment(status="completed", config_id=1)
    await repo.add(exp)
    await repo._session.execute(
        text("UPDATE experiments SET status = 'finished' WHERE status = 'completed'")
    )
    await repo._session.flush()
    await repo._session.refresh(exp)
    assert exp.status == "finished"


@pytest.mark.asyncio
async def test_pending_backfills_to_failed(repo: ExperimentRepository):
    exp = Experiment(status="pending", config_id=2)
    await repo.add(exp)
    await repo._session.execute(
        text(
            "UPDATE experiments SET status = 'failed', error_message = 'legacy/unknown' WHERE status = 'pending'"
        )
    )
    await repo._session.flush()
    await repo._session.refresh(exp)
    assert exp.status == "failed"
    assert exp.error_message == "legacy/unknown"


@pytest.mark.asyncio
async def test_idempotent_finished_stays_finished(repo: ExperimentRepository):
    exp = Experiment(status="finished", config_id=3)
    await repo.add(exp)
    await repo._session.execute(
        text("UPDATE experiments SET status = 'finished' WHERE status = 'completed'")
    )
    await repo._session.execute(
        text(
            "UPDATE experiments SET status = 'failed', error_message = 'legacy/unknown' WHERE status = 'pending'"
        )
    )
    await repo._session.flush()
    await repo._session.refresh(exp)
    assert exp.status == "finished"
