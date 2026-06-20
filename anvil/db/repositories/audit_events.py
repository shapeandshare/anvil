"""Repository for the hash-chained audit trail (``audit_events`` table).

Provides append-only operations — ``get_tail`` (for chaining),
``append`` (insert a new entry), and read-only queries.  Intentionally
exposes **no** update or delete methods (VR-A3) so the chain's
tamper-evidence guarantee is enforced at the data-access layer.
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.audit_event import AuditEvent


class AuditEventRepository:
    """Data access for :class:`AuditEvent` records.

    Parameters
    ----------
    session : AsyncSession
        An active async SQLAlchemy session.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_tail(self) -> AuditEvent | None:
        """Return the most recent audit entry (highest sequence).

        Returns ``None`` when the chain is empty.
        """
        result = await self._session.execute(
            select(AuditEvent).order_by(AuditEvent.sequence.desc()).limit(1)
        )
        return result.scalar_one_or_none()

    async def append(self, event: AuditEvent) -> AuditEvent:
        """Insert a new entry into the chain.

        Parameters
        ----------
        event : AuditEvent
            The entry to insert.  Its ``prev_hash`` and ``entry_hash``
            must have been computed before calling this method.

        Returns
        -------
        AuditEvent
            The entry after flush and refresh.
        """
        self._session.add(event)
        await self._session.flush()
        await self._session.refresh(event)
        return event

    async def all_ordered(self) -> Sequence[AuditEvent]:
        """Return all entries in chain order (ascending sequence)."""
        result = await self._session.execute(
            select(AuditEvent).order_by(AuditEvent.sequence.asc())
        )
        return result.scalars().all()

    async def query(
        self,
        *,
        target_type: str | None = None,
        target_id: str | None = None,
        action_type: str | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> Sequence[AuditEvent]:
        """Return filtered entries in chain order.

        All filter parameters are optional; when omitted the
        corresponding criterion is not applied.

        Parameters
        ----------
        target_type : str, optional
            Filter by target entity type.
        target_id : str, optional
            Filter by target entity identifier.
        action_type : str, optional
            Filter by action type.
        limit : int
            Maximum entries to return (default ``200``).
        offset : int
            Number of entries to skip (default ``0``).
        """
        stmt = select(AuditEvent).order_by(AuditEvent.sequence.asc())
        if target_type is not None:
            stmt = stmt.where(AuditEvent.target_type == target_type)
        if target_id is not None:
            stmt = stmt.where(AuditEvent.target_id == target_id)
        if action_type is not None:
            stmt = stmt.where(AuditEvent.action_type == action_type)
        result = await self._session.execute(stmt.offset(offset).limit(limit))
        return result.scalars().all()