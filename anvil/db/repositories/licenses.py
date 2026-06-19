"""Repository for the approved-license catalog (``license_catalog`` table).

Provides lookup by identifier (for the acceptable-use gate and
provenance assignment) and bulk/idempotent seeding.
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.license_entry import LicenseEntry


class LicenseRepository:
    """Data access for :class:`LicenseEntry` records.

    Parameters
    ----------
    session : AsyncSession
        An active async SQLAlchemy session.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, id: int) -> LicenseEntry | None:
        """Return a single entry by primary key."""
        return await self._session.get(LicenseEntry, id)

    async def get_by_identifier(self, identifier: str) -> LicenseEntry | None:
        """Return a single entry by its unique ``identifier``."""
        result = await self._session.execute(
            select(LicenseEntry).where(LicenseEntry.identifier == identifier)
        )
        return result.scalar_one_or_none()

    async def all(self) -> Sequence[LicenseEntry]:
        """Return all license catalog entries."""
        result = await self._session.execute(
            select(LicenseEntry).order_by(LicenseEntry.identifier)
        )
        return result.scalars().all()

    async def add(self, entry: LicenseEntry) -> LicenseEntry:
        """Persist a new license entry.

        Parameters
        ----------
        entry : LicenseEntry
            The unsaved entry.

        Returns
        -------
        LicenseEntry
            The entry after flush and refresh.
        """
        self._session.add(entry)
        await self._session.flush()
        await self._session.refresh(entry)
        return entry