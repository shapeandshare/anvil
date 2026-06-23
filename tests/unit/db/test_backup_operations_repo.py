# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for BackupOperationRepository CRUD."""

from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from anvil.db.base import Base
from anvil.db.models.backup_operation import BackupOperation
from anvil.db.repositories.backup_operations import BackupOperationRepository
from anvil.db.session import AsyncSessionLocal, async_engine


@pytest.fixture
async def db_session():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as session:
        yield session


BACKUP_ID = "20260621T143000Z-a1b2c3"
NOW = datetime(2026, 6, 21, 14, 30, 0, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_add_and_get_by_backup_id(db_session: AsyncSession):
    repo = BackupOperationRepository(db_session)
    op = BackupOperation(
        backup_id=BACKUP_ID,
        operation_type="backup",
        status="completed",
        archive_size_bytes=1024,
        total_uncompressed_bytes=4096,
        deployment_version="1.7.0",
        schema_revision="002",
    )
    saved = await repo.add(op)
    assert saved.id is not None
    assert saved.backup_id == BACKUP_ID

    fetched = await repo.get_by_backup_id(BACKUP_ID)
    assert fetched is not None
    assert fetched.status == "completed"


@pytest.mark.asyncio
async def test_get_all_returns_all(db_session: AsyncSession):
    repo = BackupOperationRepository(db_session)
    op_a = BackupOperation(backup_id="001-a", operation_type="backup")
    op_b = BackupOperation(backup_id="002-b", operation_type="backup")
    await repo.add(op_a)
    await repo.add(op_b)

    all_ops = await repo.get_all()
    ids = [o.backup_id for o in all_ops]
    assert "001-a" in ids
    assert "002-b" in ids
    assert len(ids) >= 2


@pytest.mark.asyncio
async def test_get_all_restorable_excludes_safety(db_session: AsyncSession):
    repo = BackupOperationRepository(db_session)
    await repo.add(BackupOperation(backup_id="manual-1", operation_type="backup"))
    await repo.add(
        BackupOperation(
            backup_id="safety-1", operation_type="pre_restore_safety"
        )
    )
    restorable = await repo.get_all_restorable()
    ids = [r.backup_id for r in restorable]
    assert "manual-1" in ids
    assert "safety-1" not in ids


@pytest.mark.asyncio
async def test_update_fields(db_session: AsyncSession):
    repo = BackupOperationRepository(db_session)
    await repo.add(BackupOperation(backup_id=BACKUP_ID, operation_type="backup"))

    updated = await repo.update_fields(BACKUP_ID, status="corrupted")
    assert updated is not None
    assert updated.status == "corrupted"


@pytest.mark.asyncio
async def test_delete(db_session: AsyncSession):
    repo = BackupOperationRepository(db_session)
    await repo.add(BackupOperation(backup_id=BACKUP_ID, operation_type="backup"))

    await repo.delete(BACKUP_ID)
    fetched = await repo.get_by_backup_id(BACKUP_ID)
    assert fetched is None