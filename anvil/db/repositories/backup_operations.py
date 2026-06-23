# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Repository for BackupOperation persistence."""

from collections.abc import Sequence

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.backup_operation import BackupOperation


class BackupOperationRepository:
    """Repository for persisting and querying backup operations.

    Parameters
    ----------
    session : AsyncSession
        The SQLAlchemy async session bound to this repository.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, id: int) -> BackupOperation | None:
        """Fetch a backup operation by its primary key."""
        return await self._session.get(BackupOperation, id)

    async def get_by_backup_id(self, backup_id: str) -> BackupOperation | None:
        """Fetch a backup operation by its unique ``backup_id``."""
        result = await self._session.execute(
            select(BackupOperation).where(BackupOperation.backup_id == backup_id)
        )
        return result.scalar_one_or_none()

    async def get_all(self) -> Sequence[BackupOperation]:
        """Return all backup operations, newest first."""
        result = await self._session.execute(
            select(BackupOperation).order_by(BackupOperation.created_at.desc())
        )
        return result.scalars().all()

    async def get_all_restorable(self) -> Sequence[BackupOperation]:
        """Return all non-safety operations (safety snapshots excluded)."""
        result = await self._session.execute(
            select(BackupOperation)
            .where(BackupOperation.operation_type != "pre_restore_safety")
            .order_by(BackupOperation.created_at.desc())
        )
        return result.scalars().all()

    async def add(self, operation: BackupOperation) -> BackupOperation:
        """Persist a new backup operation and return it."""
        self._session.add(operation)
        await self._session.flush()
        await self._session.refresh(operation)
        return operation

    async def update_fields(
        self, backup_id: str, **kwargs: object
    ) -> BackupOperation | None:
        """Update one or more fields on an operation identified by
        ``backup_id`` and return the refreshed row.
        """
        await self._session.execute(
            update(BackupOperation)
            .where(BackupOperation.backup_id == backup_id)
            .values(**kwargs)
        )
        await self._session.flush()
        return await self.get_by_backup_id(backup_id)

    async def delete(self, backup_id: str) -> None:
        """Delete a backup operation (idempotent)."""
        await self._session.execute(
            delete(BackupOperation).where(BackupOperation.backup_id == backup_id)
        )
