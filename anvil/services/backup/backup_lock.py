# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Process-scoped single-operation lock for backup/restore concurrency."""

import asyncio


class BackupLock:
    """Ensures only one backup or restore operation runs at a time.

    The lock is process-scoped and lives on the long-lived
    ``BackupService`` instance (``app.state.backup_service``).  API
    routes return HTTP 409 (Conflict) when an operation is already in
    flight.

    Parameters
    ----------
    operation_type : str or None
        Type of the currently running operation (``backup``,
        ``restore``), or ``None`` when idle.
    backup_id : str or None
        Identifier of the in-flight operation, or ``None`` when idle.
    """

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._operation_type: str | None = None
        self._backup_id: str | None = None

    @property
    def is_busy(self) -> bool:
        """Return ``True`` if a backup or restore is in progress."""
        return self._lock.locked()

    @property
    def current(self) -> tuple[str, str] | None:
        """Return ``(operation_type, backup_id)`` of the in-flight
        operation, or ``None`` if idle.
        """
        if self._operation_type:
            return (self._operation_type, self._backup_id or "")
        return None

    async def try_acquire(self, operation_type: str, backup_id: str) -> bool:
        """Attempt to acquire the lock.

        Parameters
        ----------
        operation_type : str
            ``backup`` or ``restore``.
        backup_id : str
            Unique identifier for this operation.

        Returns
        -------
        bool
            ``True`` if the lock was acquired, ``False`` if busy.
        """
        acquired = self._lock.locked() is False
        if acquired:
            await self._lock.acquire()
            self._operation_type = operation_type
            self._backup_id = backup_id
        return acquired

    def release(self) -> None:
        """Release the lock and reset state."""
        if self._lock.locked():
            self._operation_type = None
            self._backup_id = None
            self._lock.release()
