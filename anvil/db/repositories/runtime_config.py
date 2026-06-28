# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Repository for RuntimeConfig persistence.

Each row is a single key/value override with an ``apply_class``
describing how it takes effect.  Boot-critical values (workspace root,
web port, MLflow port, DB path) live in the workspace ``instance.json``
boot file — this repository does NOT store them.
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.runtime_config import RuntimeConfig


class RuntimeConfigRepository:
    """Repository for persisting and querying runtime config overrides.

    Parameters
    ----------
    session : AsyncSession
        The SQLAlchemy async session bound to this repository.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, key: str) -> RuntimeConfig | None:
        """Fetch a runtime config override by its key.

        Parameters
        ----------
        key : str
            The setting key (e.g. ``device``, ``mlflow_uri``).

        Returns
        -------
        RuntimeConfig | None
            The persisted row, or ``None`` if no override exists.
        """
        result = await self._session.execute(
            select(RuntimeConfig).where(RuntimeConfig.key == key)
        )
        return result.scalar_one_or_none()

    async def get_all(self) -> Sequence[RuntimeConfig]:
        """Return all persisted runtime config overrides.

        Returns
        -------
        Sequence[RuntimeConfig]
            All rows, ordered by key.
        """
        result = await self._session.execute(
            select(RuntimeConfig).order_by(RuntimeConfig.key)
        )
        return result.scalars().all()

    async def upsert(self, key: str, value: str, apply_class: str) -> RuntimeConfig:
        """Create or update a runtime config override.

        Uses INSERT … ON CONFLICT (key) DO UPDATE so that the
        same key never duplicates.

        Parameters
        ----------
        key : str
            The setting key.
        value : str
            The stringified override value.
        apply_class : str
            The ``ApplyClass`` value indicating how the change takes
            effect (e.g. ``boot_critical``, ``mlflow_restart``,
            ``applies_live``).

        Returns
        -------
        RuntimeConfig
            The persisted (and flushed/refreshed) row.
        """
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert

        stmt = sqlite_insert(RuntimeConfig).values(
            key=key, value=value, apply_class=apply_class
        )
        upsert_stmt = stmt.on_conflict_do_update(
            index_elements=["key"],
            set_={
                "value": stmt.excluded.value,
                "apply_class": stmt.excluded.apply_class,
            },
        )
        await self._session.execute(upsert_stmt)
        await self._session.flush()
        result = await self._session.execute(
            select(RuntimeConfig).where(RuntimeConfig.key == key)
        )
        row = result.scalar_one_or_none()
        assert row is not None  # Freshly upserted row must exist.
        return row

    async def delete(self, key: str) -> None:
        """Delete a runtime config override (idempotent).

        Parameters
        ----------
        key : str
            The setting key to remove.
        """
        await self._session.execute(
            delete(RuntimeConfig).where(RuntimeConfig.key == key)
        )
        await self._session.flush()
