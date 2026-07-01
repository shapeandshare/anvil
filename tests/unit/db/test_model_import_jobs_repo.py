# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for ModelImportJobRepository."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from anvil.db.base import Base
from anvil.db.models.model_import_job import ModelImportJob
from anvil.db.repositories.model_import_jobs import ModelImportJobRepository
from anvil.db.session import AsyncSessionLocal, async_engine


@pytest.fixture
async def db_session():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as session:
        yield session
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.mark.asyncio
async def test_add_and_get(db_session):
    """Adding a ModelImportJob and retrieving it by ID returns the same entry."""
    repo = ModelImportJobRepository(db_session)

    job = ModelImportJob(
        source_type="huggingface",
        source_identifier="org/test-model",
        revision="main",
    )
    saved = await repo.add(job)
    assert saved.id is not None
    assert saved.source_identifier == "org/test-model"

    fetched = await repo.get(saved.id)
    assert fetched is not None
    assert fetched.status == "queued"


@pytest.mark.asyncio
async def test_add_and_update_status(db_session):
    """After update_status, the job status is changed."""
    repo = ModelImportJobRepository(db_session)

    job = ModelImportJob(
        source_type="huggingface",
        source_identifier="org/status-test",
    )
    saved = await repo.add(job)
    assert saved.status == "queued"

    updated = await repo.update_status(saved.id, status="complete")
    assert updated is not None
    assert updated.status == "complete"


@pytest.mark.asyncio
async def test_list_all_returns_newest_first(db_session):
    """list_all orders results by created_at descending."""
    repo = ModelImportJobRepository(db_session)

    j1 = ModelImportJob(
        source_type="huggingface",
        source_identifier="org/job-a",
        revision="main",
    )
    j2 = ModelImportJob(
        source_type="local",
        source_identifier="/test/job-b",
        revision="v2",
    )
    await repo.add(j1)
    await repo.add(j2)

    all_jobs = await repo.list_all()
    assert len(all_jobs) >= 2
    identifiers = {j.source_identifier for j in all_jobs}
    assert "org/job-a" in identifiers
    assert "/test/job-b" in identifiers
