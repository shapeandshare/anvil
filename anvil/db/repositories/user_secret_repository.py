# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Repository for ``UserSecret`` CRUD operations."""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.user_secret import UserSecret


class UserSecretRepository:
    """Async CRUD repository for ``UserSecret`` entries.

    Parameters
    ----------
    session : AsyncSession
        SQLAlchemy async session bound to the application database.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, user_id: str, key: str) -> UserSecret | None:
        """Retrieve a specific secret for a user.

        Parameters
        ----------
        user_id : str
            User identifier.
        key : str
            Secret key name.

        Returns
        -------
        UserSecret | None
            The matching secret, or ``None`` if not found.
        """
        stmt = select(UserSecret).where(
            UserSecret.user_id == user_id, UserSecret.key == key
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all_for_user(self, user_id: str) -> Sequence[UserSecret]:
        """Return all secrets for a user.

        Parameters
        ----------
        user_id : str
            User identifier.

        Returns
        -------
        Sequence[UserSecret]
            All secret rows for the user.
        """
        stmt = (
            select(UserSecret)
            .where(UserSecret.user_id == user_id)
            .order_by(UserSecret.key)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def count_by_key_id(self, key_id: str) -> int:
        """Count secrets encrypted with a given key.

        Parameters
        ----------
        key_id : str
            Encryption key identifier.

        Returns
        -------
        int
            Number of secrets using this key.
        """
        stmt = select(func.count()).where(UserSecret.key_id == key_id)
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def iterate_by_key_id(
        self, key_id: str, batch_size: int = 100
    ) -> AsyncIterator[UserSecret]:
        """Yield secrets matching ``key_id`` in cursor-based batches.

        Uses cursor-based pagination over ``id`` for efficient
        and consistent iteration during re-encryption sweeps.

        Parameters
        ----------
        key_id : str
            Encryption key identifier.
        batch_size : int, optional
            Rows per batch, by default 100.

        Yields
        ------
        UserSecret
            Each matching secret row.
        """
        cursor: int = 0
        while True:
            stmt = (
                select(UserSecret)
                .where(UserSecret.key_id == key_id, UserSecret.id > cursor)
                .order_by(UserSecret.id)
                .limit(batch_size)
            )
            result = await self._session.execute(stmt)
            batch = result.scalars().all()
            if not batch:
                break
            for row in batch:
                yield row
                cursor = row.id

    async def upsert(
        self, user_id: str, key: str, encrypted_value: str, key_id: str | None = None
    ) -> UserSecret:
        """Create or update a secret for a user.

        Parameters
        ----------
        user_id : str
            User identifier.
        key : str
            Secret key name.
        encrypted_value : str
            AES-256-GCM encrypted, base64-encoded value.
        key_id : str, optional
            Encryption key identifier to associate with this secret.

        Returns
        -------
        UserSecret
            The saved secret row.
        """
        existing = await self.get(user_id, key)
        if existing is not None:
            existing.encrypted_value = encrypted_value
            if key_id is not None:
                existing.key_id = key_id
            await self._session.flush()
            await self._session.refresh(existing)
            return existing
        secret = UserSecret(user_id=user_id, key=key, encrypted_value=encrypted_value)
        if key_id is not None:
            secret.key_id = key_id
        self._session.add(secret)
        await self._session.flush()
        await self._session.refresh(secret)
        return secret

    async def delete(self, user_id: str, key: str) -> None:
        """Remove a secret entry. Idempotent — no error if missing.

        Parameters
        ----------
        user_id : str
            User identifier.
        key : str
            Secret key name.
        """
        existing = await self.get(user_id, key)
        if existing is not None:
            await self._session.delete(existing)
            await self._session.flush()
