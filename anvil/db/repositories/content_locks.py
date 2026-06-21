# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""ContentLockRepository — data access for advisory checkout locks.

Provides CRUD operations and active-lock queries for the ``CheckoutLock``
entity via the async SQLAlchemy repository pattern.
"""

from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ...services.content.lock_state import LockState
from ..models.content_lock import CheckoutLock


class ContentLockRepository:
    """Repository for ``CheckoutLock`` entity CRUD and lifecycle
    management.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository with a database session.

        Parameters
        ----------
        session : AsyncSession
            SQLAlchemy async session used for all database operations.
        """
        self._session = session

    async def get(self, id: int) -> CheckoutLock | None:
        """Retrieve a checkout lock by its primary key.

        Parameters
        ----------
        id : int
            The primary key of the lock to retrieve.

        Returns
        -------
        CheckoutLock | None
            The matching ``CheckoutLock`` instance, or ``None`` if no
            record exists with the given ``id``.
        """
        return await self._session.get(CheckoutLock, id)

    async def add(self, lock: CheckoutLock) -> CheckoutLock:
        """Persist a new checkout lock and return it with a generated
        primary key.

        Parameters
        ----------
        lock : CheckoutLock
            The unsaved ``CheckoutLock`` instance to add to the database.

        Returns
        -------
        CheckoutLock
            The same instance after flush and refresh, with its ``id``
            and server-side defaults populated.
        """
        self._session.add(lock)
        await self._session.flush()
        await self._session.refresh(lock)
        return lock

    async def release(self, id: int) -> None:
        """Release a checkout lock by marking it as released.

        Sets the lock state to ``RELEASED`` and records the release
        timestamp.

        Parameters
        ----------
        id : int
            Primary key of the lock to release.

        Returns
        -------
        None
        """
        await self._session.execute(
            update(CheckoutLock)
            .where(CheckoutLock.id == id)
            .values(
                state=LockState.RELEASED,
                released_at=datetime.now(UTC),
            )
        )

    async def list_active(self) -> Sequence[CheckoutLock]:
        """List all currently held checkout locks.

        Returns
        -------
        Sequence[CheckoutLock]
            All ``CheckoutLock`` records with state ``HELD``, ordered
            by acquisition time ascending.
        """
        result = await self._session.execute(
            select(CheckoutLock)
            .where(CheckoutLock.state == LockState.HELD)
            .order_by(CheckoutLock.acquired_at.asc())
        )
        return result.scalars().all()
