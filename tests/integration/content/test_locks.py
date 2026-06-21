"""Integration tests for checkout lock lifecycle via the real repository.

Exercises ``ContentLockRepository`` directly against an in-memory SQLite
database.  Tests cover acquire/release lifecycle and active-lock listing.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from anvil.db.models.content_lock import CheckoutLock
from anvil.db.repositories.content_locks import ContentLockRepository
from anvil.services.content.lock_state import LockState


@pytest.mark.asyncio
async def test_acquire_release_board(content_db: AsyncSession) -> None:
    """Acquire a lock, verify it appears on the active list with holder
    and timestamp, then release and confirm it is cleared.

    Parameters
    ----------
    content_db : AsyncSession
        In-memory SQLite session with all tables created.
    """
    repo = ContentLockRepository(content_db)

    # Acquire
    lock = CheckoutLock(scope="corpus:42", holder="alice", state=LockState.HELD)
    saved = await repo.add(lock)

    assert saved.id is not None
    assert saved.scope == "corpus:42"
    assert saved.holder == "alice"
    assert saved.state == LockState.HELD
    assert saved.acquired_at is not None  # server default populated
    assert saved.released_at is None

    # Appears on active list
    active = await repo.list_active()
    assert len(active) == 1
    assert active[0].id == saved.id
    assert active[0].holder == "alice"

    # Release
    lock_id = saved.id  # capture before commit expires the instance
    await repo.release(lock_id)
    await content_db.commit()

    # Verify released lock is gone from active list
    active_after = await repo.list_active()
    assert len(active_after) == 0

    # Verify the lock record still exists with RELEASED state
    released = await repo.get(lock_id)
    assert released is not None
    assert released.state == LockState.RELEASED
    assert released.released_at is not None


@pytest.mark.asyncio
async def test_list_active(content_db: AsyncSession) -> None:
    """Acquire multiple locks and verify all appear in the active listing.

    Parameters
    ----------
    content_db : AsyncSession
        In-memory SQLite session with all tables created.
    """
    repo = ContentLockRepository(content_db)

    lock_a = CheckoutLock(scope="corpus:1", holder="alice", state=LockState.HELD)
    lock_b = CheckoutLock(scope="corpus:2", holder="bob", state=LockState.HELD)
    lock_c = CheckoutLock(scope="corpus:3", holder="charlie", state=LockState.HELD)

    await repo.add(lock_a)
    await repo.add(lock_b)
    await repo.add(lock_c)
    await content_db.commit()

    active = await repo.list_active()
    assert len(active) == 3

    scopes = {l.scope for l in active}
    assert scopes == {"corpus:1", "corpus:2", "corpus:3"}

    holders = {l.holder for l in active}
    assert holders == {"alice", "bob", "charlie"}

    # All active locks have HELD state
    for lock in active:
        assert lock.state == LockState.HELD
        assert lock.released_at is None
