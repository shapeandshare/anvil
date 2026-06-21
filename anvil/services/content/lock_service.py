"""LockService — advisory checkout lock lifecycle management.

Provides ``acquire``, ``release``, and ``list_active`` operations
for content checkout locks, delegating persistence to the
``ContentLockRepository``.
"""

from __future__ import annotations

from collections.abc import Sequence

from ...db.models.content_lock import CheckoutLock
from ...db.repositories.content_locks import ContentLockRepository


class LockService:
    """Manages the lifecycle of advisory content checkout locks.

    Wraps a ``ContentLockRepository`` to provide a higher-level API
    for acquiring, releasing, and listing active locks.  Each lock
    is scoped to a content entity (e.g. ``"corpus:42"``) and held
    by a named holder.

    Parameters
    ----------
    lock_repo : ContentLockRepository
        Repository backing lock persistence.
    """

    def __init__(self, lock_repo: ContentLockRepository) -> None:
        """Initialise the service with a lock repository.

        Parameters
        ----------
        lock_repo : ContentLockRepository
            Repository backing lock persistence.
        """
        self._repo = lock_repo

    async def acquire(self, scope: str, holder: str) -> CheckoutLock:
        """Acquire an advisory checkout lock.

        Creates a new ``CheckoutLock`` in the ``HELD`` state.
        Does **not** check for existing locks — the caller is
        responsible for conflict detection.

        Parameters
        ----------
        scope : str
            Lock scope identifier (e.g. ``"corpus:42"``).
        holder : str
            Lock holder identifier.

        Returns
        -------
        CheckoutLock
            The persisted lock with generated ``id`` and
            server-side ``acquired_at`` populated.
        """
        from .lock_state import LockState

        lock = CheckoutLock(scope=scope, holder=holder, state=LockState.HELD)
        return await self._repo.add(lock)

    async def release(self, lock_id: int) -> None:
        """Release an advisory checkout lock.

        Marks the lock as ``RELEASED`` and records the release
        timestamp.  A no-op if the lock does not exist.

        Parameters
        ----------
        lock_id : int
            Primary key of the lock to release.
        """
        await self._repo.release(lock_id)

    async def list_active(self) -> Sequence[CheckoutLock]:
        """Return all currently-held checkout locks.

        Returns
        -------
        Sequence[CheckoutLock]
            All ``CheckoutLock`` records with ``state == HELD``,
            ordered by acquisition time.
        """
        return await self._repo.list_active()
