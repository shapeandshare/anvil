# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Repository for ``UserSecret`` CRUD operations."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
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

    async def upsert(
        self, user_id: str, key: str, encrypted_value: str
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

        Returns
        -------
        UserSecret
            The saved secret row.
        """
        existing = await self.get(user_id, key)
        if existing is not None:
            existing.encrypted_value = encrypted_value
            await self._session.flush()
            await self._session.refresh(existing)
            return existing
        secret = UserSecret(
            user_id=user_id, key=key, encrypted_value=encrypted_value
        )
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