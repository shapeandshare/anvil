# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Global instance registry repository.

Manages the host-level global registry SQLite database at
``~/.anvil/registry.db`` — a separate database from the per-instance
app DB.  The registry tracks running instances for cross-instance
collision detection (port conflicts, workspace-root conflicts).

DDL bootstrap
-------------
The ``instance_records`` table is created lazily on first registry
access via raw SQL (``CREATE TABLE IF NOT EXISTS``).  This sidesteps
Alembic for the global registry — one table that is never migrated
independently of the anvil package itself.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy import delete, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

if TYPE_CHECKING:
    from ..models.instance_record import InstanceRecord

logger = logging.getLogger(__name__)

# ── DDL bootstrap ────────────────────────────────────────────────────────
# Must match anvil/db/models/instance_record.py exactly.
# Using raw SQL to avoid coupling the global registry to Alembic migrations.
_INSTANCE_RECORDS_DDL: str = """\
CREATE TABLE IF NOT EXISTS instance_records (
    id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL,
    workspace_root VARCHAR(500) NOT NULL,
    web_port INTEGER NOT NULL,
    mlflow_port INTEGER NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (name),
    UNIQUE (workspace_root),
    UNIQUE (web_port),
    UNIQUE (mlflow_port)
)
"""

# ── Module-level lazy registry engine ───────────────────────────────────
#
# The registry DB lives at ~/.anvil/registry.db — a separate SQLite
# file from the per-instance app DB.  The engine is created lazily:
# first-call-wins (race-safe for the MVP because calls are serialised
# by the FastAPI event loop).

_registry_engine: AsyncEngine | None = None
_DEFAULT_REGISTRY_PATH: str = str(Path.home() / ".anvil" / "registry.db")


def get_registry_engine(db_url: str | None = None) -> AsyncEngine:
    """Return the lazily-initialised async engine for the registry DB.

    Parameters
    ----------
    db_url : str, optional
        SQLAlchemy database URL.  Defaults to
        ``sqlite+aiosqlite:///{home}/.anvil/registry.db``.  Override
        for testing with an in-memory database.

    Returns
    -------
    AsyncEngine
        The singleton async engine bound to the registry SQLite file.
    """
    global _registry_engine
    if _registry_engine is None:
        if db_url is None:
            db_path = _DEFAULT_REGISTRY_PATH
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
            db_url = f"sqlite+aiosqlite:///{db_path}"
        _registry_engine = create_async_engine(
            db_url,
            echo=False,
            connect_args={"check_same_thread": False},
        )
    return _registry_engine


async def ensure_registry_tables(engine: AsyncEngine | None = None) -> None:
    """Create the ``instance_records`` table if it does not exist.

    Idempotent — safe to call on every repository access.

    Parameters
    ----------
    engine : AsyncEngine, optional
        Registry DB engine.  Defaults to the module-level singleton.
    """
    if engine is None:
        engine = get_registry_engine()
    async with engine.begin() as conn:
        await conn.execute(text(_INSTANCE_RECORDS_DDL))
        await conn.commit()


async def create_registry_session(
    engine: AsyncEngine | None = None,
) -> AsyncSession:
    """Create an ``AsyncSession`` bound to the registry DB.

    Bootstraps the registry table on first use.

    Parameters
    ----------
    engine : AsyncEngine, optional
        Registry DB engine.  Defaults to the module-level singleton.

    Returns
    -------
    AsyncSession
        A new async session bound to the registry engine.
    """
    engine = engine or get_registry_engine()
    await ensure_registry_tables(engine)
    return AsyncSession(bind=engine)


def dispose_registry_engine() -> None:
    """Dispose the module-level registry engine (for testing teardown)."""
    global _registry_engine
    if _registry_engine is not None:
        import asyncio

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            # No running loop — sync dispose is fine.
            _registry_engine.sync_engine.dispose()
        _registry_engine = None


# ── Repository ───────────────────────────────────────────────────────────


class InstanceRegistryRepository:
    """Repository for the global ``instance_records`` table.

    Writes and queries the separate registry DB.  All mutating methods
    require the caller to commit the session.

    Parameters
    ----------
    session : AsyncSession
        An async session **bound to the registry DB engine** — *not*
        the per-instance app DB session.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def register(self, record: InstanceRecord) -> InstanceRecord:
        """Insert a new instance record into the global registry.

        Parameters
        ----------
        record : InstanceRecord
            Unsaved ORM instance with ``name``, ``workspace_root``,
            ``web_port``, and ``mlflow_port`` set.

        Returns
        -------
        InstanceRecord
            The saved record with ``id`` populated.

        Raises
        ------
        ValueError
            If a unique constraint is violated (duplicate name,
            workspace root, or port) — surfaced as a human-readable
            collision message.
        """
        try:
            self._session.add(record)
            await self._session.flush()
            await self._session.refresh(record)
            return record
        except SQLAlchemyError as exc:
            await self._session.rollback()
            err_msg = str(exc).lower()
            if "unique" in err_msg or "integrity" in err_msg:
                if record.name in err_msg or "name" in err_msg:
                    raise ValueError(
                        f"Instance name '{record.name}' already exists "
                        f"in the global registry"
                    ) from exc
                if "workspace_root" in err_msg:
                    raise ValueError(
                        f"Workspace root '{record.workspace_root}' "
                        f"is already registered"
                    ) from exc
                if "web_port" in err_msg:
                    raise ValueError(
                        f"Web port {record.web_port} is already in use "
                        f"by another instance"
                    ) from exc
                if "mlflow_port" in err_msg:
                    raise ValueError(
                        f"MLflow port {record.mlflow_port} is already "
                        f"in use by another instance"
                    ) from exc
            # Re-raise unrecognised exceptions.
            raise

    async def get_by_name(self, name: str) -> InstanceRecord | None:
        """Look up an instance by its unique name.

        Parameters
        ----------
        name : str
            Instance name to search for.

        Returns
        -------
        InstanceRecord | None
            The matching record, or ``None`` if not found.
        """
        model_cls = _get_instance_model()
        result = await self._session.execute(
            select(model_cls).where(model_cls.name == name)
        )
        return result.scalar_one_or_none()

    async def list_all(self) -> Sequence[InstanceRecord]:
        """Return every registered instance, newest first.

        Returns
        -------
        Sequence[InstanceRecord]
            All records in descending ``created_at`` order.
        """
        model_cls = _get_instance_model()
        result = await self._session.execute(
            select(model_cls).order_by(model_cls.created_at.desc())
        )
        return result.scalars().all()

    async def deregister(self, name: str) -> None:
        """Remove an instance from the global registry by name.

        Idempotent — succeeds even if the name does not exist.

        Parameters
        ----------
        name : str
            Instance name to deregister.
        """
        model_cls = _get_instance_model()
        await self._session.execute(delete(model_cls).where(model_cls.name == name))
        await self._session.flush()

    async def find_port_conflict(
        self, web_port: int, mlflow_port: int
    ) -> InstanceRecord | None:
        """Find an existing instance that uses either of the given ports.

        Parameters
        ----------
        web_port : int
            Web/uvicorn port to check.
        mlflow_port : int
            MLflow sidecar port to check.

        Returns
        -------
        InstanceRecord | None
            The first conflicting record, or ``None`` if neither port
            is taken.
        """
        model_cls = _get_instance_model()
        result = await self._session.execute(
            select(model_cls).where(
                (model_cls.web_port == web_port)
                | (model_cls.mlflow_port == mlflow_port)
            )
        )
        return result.scalar_one_or_none()

    async def find_workspace_conflict(self, root: str) -> InstanceRecord | None:
        """Find an existing instance using the given workspace root.

        Parameters
        ----------
        root : str
            Absolute workspace root path to check.

        Returns
        -------
        InstanceRecord | None
            The matching record, or ``None`` if the root is free.
        """
        model_cls = _get_instance_model()
        result = await self._session.execute(
            select(model_cls).where(model_cls.workspace_root == root)
        )
        return result.scalar_one_or_none()

    async def find_workspace_overlap(self, root: str) -> InstanceRecord | None:
        """Find an existing instance whose workspace overlaps with *root*.

        Overlap means *root* is a subdirectory **of** a registered
        workspace, **or** a registered workspace is a subdirectory
        **of** *root*.  Uses resolved absolute paths for comparison.

        Parameters
        ----------
        root : str
            Absolute workspace root path to check.

        Returns
        -------
        InstanceRecord | None
            The first overlapping record, or ``None`` if no overlap.
        """
        model_cls = _get_instance_model()
        result = await self._session.execute(
            select(model_cls).order_by(model_cls.workspace_root)
        )
        all_records: Sequence[InstanceRecord] = result.scalars().all()

        resolved = str(Path(root).resolve())
        resolved_trailing = resolved.rstrip("/") + "/"

        for rec in all_records:
            rec_root = str(Path(rec.workspace_root).resolve())
            rec_trailing = rec_root.rstrip("/") + "/"
            # Check if resolved is a subdirectory of rec_root OR
            # rec_root is a subdirectory of resolved.
            if resolved_trailing.startswith(rec_trailing) or rec_trailing.startswith(
                resolved_trailing
            ):
                return rec
        return None


# ── Internal helpers ─────────────────────────────────────────────────────

_INSTANCE_MODEL: type | None = None


def _get_instance_model() -> type:
    """Lazily import and return the ``InstanceRecord`` ORM class.

    Uses a lazy import to avoid circular dependencies at module level.
    """
    global _INSTANCE_MODEL
    if _INSTANCE_MODEL is None:
        from ..models.instance_record import InstanceRecord

        _INSTANCE_MODEL = InstanceRecord
    return _INSTANCE_MODEL  # type: ignore[return-value]
