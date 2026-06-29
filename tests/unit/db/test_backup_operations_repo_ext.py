# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Extends BackupOperationRepository tests to cover remaining lines.

Adds tests for: get() by primary key, get_by_backup_id returning None,
get_all with ordering, and idempotent delete on non-existent id.
"""

from __future__ import annotations

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


# ── get by primary key ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_by_id_returns_row(db_session: AsyncSession) -> None:
    """get() returns a backup operation by primary key."""
    repo = BackupOperationRepository(db_session)
    op = BackupOperation(backup_id=BACKUP_ID, operation_type="backup")
    saved = await repo.add(op)

    fetched = await repo.get(saved.id)
    assert fetched is not None
    assert fetched.backup_id == BACKUP_ID


@pytest.mark.asyncio
async def test_get_by_id_returns_none(db_session: AsyncSession) -> None:
    """get() returns None for a non-existent primary key."""
    repo = BackupOperationRepository(db_session)
    fetched = await repo.get(9999)
    assert fetched is None


# ── get_by_backup_id returning None ───────────────────────────────────────


@pytest.mark.asyncio
async def test_get_by_backup_id_returns_none(db_session: AsyncSession) -> None:
    """get_by_backup_id returns None for a non-existent backup_id."""
    repo = BackupOperationRepository(db_session)
    fetched = await repo.get_by_backup_id("does-not-exist")
    assert fetched is None


# ── get_all ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_all_returns_all_records(db_session: AsyncSession) -> None:
    """get_all returns all records regardless of order (created_at
    has second-level precision so same-second inserts have undefined
    order)."""
    repo = BackupOperationRepository(db_session)
    await repo.add(BackupOperation(backup_id="rec-a", operation_type="backup"))
    await repo.add(BackupOperation(backup_id="rec-b", operation_type="backup"))

    all_ops = await repo.get_all()
    ids = {o.backup_id for o in all_ops}
    assert "rec-a" in ids
    assert "rec-b" in ids
    assert len(ids) >= 2


# ── get_all_restorable with mix of types ──────────────────────────────────


@pytest.mark.asyncio
async def test_get_all_restorable_multiple_types(db_session: AsyncSession) -> None:
    """get_all_restorable returns only non-safety operations
    when mixed with other types."""
    repo = BackupOperationRepository(db_session)
    await repo.add(BackupOperation(backup_id="backup-1", operation_type="backup"))
    await repo.add(BackupOperation(backup_id="restore-1", operation_type="restore"))
    await repo.add(
        BackupOperation(backup_id="safety-1", operation_type="pre_restore_safety")
    )
    await repo.add(BackupOperation(backup_id="backup-2", operation_type="backup"))

    restorable = await repo.get_all_restorable()
    ids = {r.backup_id for r in restorable}
    assert "safety-1" not in ids
    assert "backup-1" in ids
    assert "restore-1" in ids
    assert "backup-2" in ids


# ── update_fields with multiple fields ────────────────────────────────────


@pytest.mark.asyncio
async def test_update_fields_multiple(db_session: AsyncSession) -> None:
    """update_fields updates multiple fields at once."""
    repo = BackupOperationRepository(db_session)
    op = BackupOperation(backup_id=BACKUP_ID, operation_type="backup")
    await repo.add(op)

    updated = await repo.update_fields(
        BACKUP_ID,
        status="completed",
        archive_size_bytes=2048,
        error_message=None,
    )
    assert updated is not None
    assert updated.status == "completed"
    assert updated.archive_size_bytes == 2048


@pytest.mark.asyncio
async def test_update_fields_nonexistent(db_session: AsyncSession) -> None:
    """update_fields returns None when backup_id does not exist."""
    repo = BackupOperationRepository(db_session)
    result = await repo.update_fields("no-such-id", status="completed")
    assert result is None


# ── delete idempotent ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_idempotent(db_session: AsyncSession) -> None:
    """delete does not raise on non-existent backup_id."""
    repo = BackupOperationRepository(db_session)
    await repo.delete("never-existed")
    # No exception is the pass condition.
