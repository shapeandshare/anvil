"""Tests for TeachingSessionRepository.

Uses in-memory SQLite with ``Base.metadata.create_all`` for an isolated
test database per session.  Follows the same pattern as
``test_corpus_repository.py``.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from anvil.db.base import Base
from anvil.db.models.teaching_session import TeachingSession
from anvil.db.models.teaching_session_status import TeachingSessionStatus
from anvil.db.repositories.teaching_session_repository import (
    TeachingSessionRepository,
)
from anvil.db.session import AsyncSessionLocal, async_engine


@pytest.fixture
async def db_session():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as session:
        yield session


@pytest.mark.asyncio
async def test_add_and_get(db_session: AsyncSession):
    repo = TeachingSessionRepository(db_session)
    ts = TeachingSession(
        name="test-session",
        description="A test session",
        status=TeachingSessionStatus.DRAFT,
    )
    saved = await repo.add(ts)
    assert saved.id is not None
    assert saved.name == "test-session"
    assert saved.status == TeachingSessionStatus.DRAFT

    fetched = await repo.get(saved.id)
    assert fetched is not None
    assert fetched.name == "test-session"
    assert fetched.status == TeachingSessionStatus.DRAFT


@pytest.mark.asyncio
async def test_add_with_seed_experiment(db_session: AsyncSession):
    repo = TeachingSessionRepository(db_session)
    ts = TeachingSession(
        name="seeded-session",
        seed_experiment_id=42,
        current_base_experiment_id=42,
        status=TeachingSessionStatus.DRAFT,
    )
    saved = await repo.add(ts)
    assert saved.seed_experiment_id == 42
    assert saved.current_base_experiment_id == 42


@pytest.mark.asyncio
async def test_list_status_filter(db_session: AsyncSession):
    repo = TeachingSessionRepository(db_session)
    ts1 = TeachingSession(name="draft-1", status=TeachingSessionStatus.DRAFT)
    ts2 = TeachingSession(name="draft-2", status=TeachingSessionStatus.DRAFT)
    ts3 = TeachingSession(name="active-1", status=TeachingSessionStatus.ACTIVE)
    await repo.add(ts1)
    await repo.add(ts2)
    await repo.add(ts3)

    drafts, total = await repo.list(status=TeachingSessionStatus.DRAFT)
    assert total == 2
    names = [s.name for s in drafts]
    assert "draft-1" in names
    assert "draft-2" in names

    active, total_active = await repo.list(status=TeachingSessionStatus.ACTIVE)
    assert total_active >= 1
    assert any(s.name == "active-1" for s in active)


@pytest.mark.asyncio
async def test_list_pagination(db_session: AsyncSession):
    repo = TeachingSessionRepository(db_session)
    for i in range(5):
        await repo.add(
            TeachingSession(name=f"session-{i}", status=TeachingSessionStatus.DRAFT)
        )

    page1, total = await repo.list(limit=2, offset=0)
    assert len(page1) == 2
    assert total == 5

    page2, _ = await repo.list(limit=2, offset=2)
    assert len(page2) == 2

    page3, _ = await repo.list(limit=2, offset=4)
    assert len(page3) == 1


@pytest.mark.asyncio
async def test_update_status(db_session: AsyncSession):
    repo = TeachingSessionRepository(db_session)
    ts = TeachingSession(name="status-test", status=TeachingSessionStatus.DRAFT)
    saved = await repo.add(ts)

    updated = await repo.update_status(saved.id, TeachingSessionStatus.ACTIVE)
    assert updated is not None
    assert updated.status == TeachingSessionStatus.ACTIVE

    fetched = await repo.get(saved.id)
    assert fetched is not None
    assert fetched.status == TeachingSessionStatus.ACTIVE


@pytest.mark.asyncio
async def test_update_status_unknown_id(db_session: AsyncSession):
    repo = TeachingSessionRepository(db_session)
    result = await repo.update_status(99999, TeachingSessionStatus.ACTIVE)
    assert result is None


@pytest.mark.asyncio
async def test_update_current_base_experiment_id(db_session: AsyncSession):
    repo = TeachingSessionRepository(db_session)
    ts = TeachingSession(
        name="chain-test",
        current_base_experiment_id=1,
        status=TeachingSessionStatus.ACTIVE,
    )
    saved = await repo.add(ts)

    updated = await repo.update_current_base_experiment_id(saved.id, 2)
    assert updated is not None
    assert updated.current_base_experiment_id == 2

    fetched = await repo.get(saved.id)
    assert fetched is not None
    assert fetched.current_base_experiment_id == 2


@pytest.mark.asyncio
async def test_delete(db_session: AsyncSession):
    repo = TeachingSessionRepository(db_session)
    ts = TeachingSession(name="delete-test", status=TeachingSessionStatus.DRAFT)
    saved = await repo.add(ts)
    cid = saved.id

    deleted = await repo.delete(cid)
    assert deleted is True

    assert await repo.get(cid) is None


@pytest.mark.asyncio
async def test_delete_unknown(db_session: AsyncSession):
    repo = TeachingSessionRepository(db_session)
    result = await repo.delete(99999)
    assert result is False