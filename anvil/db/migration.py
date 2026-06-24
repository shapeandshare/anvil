# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""MigrationService — programmatic Alembic migration wrapper."""

from __future__ import annotations

import asyncio
import importlib.resources as _resources
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

from alembic import command
from alembic.config import Config as AlembicConfig
from alembic.script import ScriptDirectory

from ..config import get_config
from .migration_error import MigrationError
from .schema_version import SCHEMA_VERSION

logger = logging.getLogger(__name__)

# Resolve alembic.ini and migrations dir from the installed package
# (not CWD / not repo-root) via importlib.resources — see ADR-017.
_PACKAGE_RES = _resources.files("anvil")
_RESOURCE_DIR = _PACKAGE_RES / "_resources"
ALEMBIC_INI = str(_RESOURCE_DIR / "alembic.ini")
"""Path to the Alembic configuration file inside the installed package."""
_MIGRATIONS_DIR = str(_RESOURCE_DIR / "migrations")
"""Path to the Alembic migration scripts directory inside the installed package."""

F = TypeVar("F", bound=Callable[..., Any])
R = TypeVar("R")


class MigrationService:
    """Wraps Alembic programmatic API for application startup and CLI usage.

    All public methods are async-safe — sync Alembic calls are dispatched via
    ``run_in_executor`` so they don't block the event loop.
    """

    def __init__(
        self,
        db_url: str | None = None,
        alembic_ini_path: str = ALEMBIC_INI,
    ) -> None:
        """Initialise the migration service.

        Parameters
        ----------
        db_url : str, optional
            SQLAlchemy database URL. Defaults to the value from
            ``get_config()["state_db_path"]``.
        alembic_ini_path : str, optional
            Path to the Alembic configuration file. Defaults to the
            package-bundled ``alembic.ini``.
        """
        cfg = get_config()
        self._db_url = db_url or f"sqlite+aiosqlite:///{cfg['state_db_path']}"
        self._alembic_cfg = self._build_config(alembic_ini_path)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_config(self, ini_path: str) -> AlembicConfig:
        """Load Alembic config and override DB URL and script location.

        Parameters
        ----------
        ini_path : str
            Path to the ``alembic.ini`` configuration file.

        Returns
        -------
        AlembicConfig
            Configured Alembic config object with the runtime database
            URL and migration script directory set.
        """
        alembic_cfg = AlembicConfig(ini_path)
        alembic_cfg.set_main_option("sqlalchemy.url", self._db_url)
        alembic_cfg.set_main_option("script_location", _MIGRATIONS_DIR)
        return alembic_cfg

    def _ensure_db_dir(self) -> None:
        """Create parent directories for the SQLite file if they don't exist.

        Parses the filesystem path from the ``sqlite+aiosqlite:///``
        URL and ensures all parent directories exist.
        """
        # Parse the file path from the sqlalchemy URL
        # URL format: sqlite+aiosqlite:///absolute/path/to/db
        url = self._db_url
        if url.startswith("sqlite+aiosqlite:///"):
            db_path = url[len("sqlite+aiosqlite:///") :]
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    async def _run_sync(self, fn: Callable[..., R], *args: Any, **kwargs: Any) -> R:
        """Run a synchronous Alembic command in a thread executor.

        Parameters
        ----------
        fn : callable
            A synchronous callable (typically an Alembic ``command``
            module function).
        *args : Any
            Positional arguments forwarded to *fn*.
        **kwargs : Any
            Keyword arguments forwarded to *fn*.

        Returns
        -------
        Any
            The return value of *fn*.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, fn, *args, **kwargs)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def upgrade(self) -> tuple[str | None, str | None]:
        """Apply all pending migrations to HEAD.

        Returns ``(before_revision, after_revision)``.

        If the database file does not exist, it is created (along with
        parent directories) before running migrations.
        """
        self._ensure_db_dir()
        before = await self.current()
        try:
            await self._run_sync(command.upgrade, self._alembic_cfg, "heads")
        except Exception as exc:
            logger.exception("Migration upgrade failed")
            raise MigrationError(
                f"Migration failed: {exc}. "
                f"Run 'anvil db upgrade' manually for details."
            ) from exc
        after = await self.current()
        logger.info("Migrated DB: %s → %s", before or "<base>", after or "<base>")
        if before != after:
            await self.set_schema_version()
            logger.info("Set DB schema version to v%d", SCHEMA_VERSION)
        return before, after

    async def verify_schema(self) -> None:
        """Verify the database schema matches the expected HEAD revision.

        Raises ``MigrationError`` if:
        - The DB revision is **ahead** of the code revision (possible downgrade scenario).
        - The DB revision is **behind** the code revision (pending migrations).
        """
        from alembic.script import ScriptDirectory

        script = ScriptDirectory.from_config(self._alembic_cfg)
        head_rev = script.get_current_head()

        current_rev = await self.current()

        if current_rev == head_rev:
            logger.info("Database schema matches HEAD (%s)", head_rev)
            return

        if (
            current_rev
            and head_rev
            and self._rev_is_ahead(current_rev, head_rev, script)
        ):
            raise MigrationError(
                f"Database schema (revision {current_rev}) is AHEAD of "
                f"application code (HEAD = {head_rev}). "
                "This may indicate a downgrade. Ensure you are running "
                "a compatible version of anvil.",
                current_rev=current_rev,
                head_rev=head_rev,
            )

        # DB is behind
        raise MigrationError(
            f"Database schema (revision {current_rev or '<base>'}) is BEHIND "
            f"expected HEAD ({head_rev}). "
            f"Run 'anvil db upgrade' to apply pending migrations.",
            current_rev=current_rev,
            head_rev=head_rev,
        )

    async def current(self) -> str | None:
        """Return the current database revision hash, or ``None`` if unstamped."""
        # We need to capture the output of `alembic current` — unfortunately
        # alembic.command.current() prints to stdout rather than returning a value.
        # We read the alembic_version table directly instead.
        from sqlalchemy import create_engine

        # Use a sync engine for this simple query (run in executor)
        def _get_current() -> str | None:
            sync_url = self._db_url.replace("+aiosqlite", "")
            engine = create_engine(sync_url)
            try:
                from sqlalchemy import text

                with engine.connect() as conn:
                    row = conn.execute(
                        text("SELECT version_num FROM alembic_version")
                    ).fetchone()
                    return str(row[0]) if row else None
            except Exception:
                return None
            finally:
                engine.dispose()

        return await self._run_sync(_get_current)

    async def history(self) -> list[dict[str, str]]:
        """Return migration history as a list of ``{revision, down_revision, message}``."""

        def _get_history() -> list[dict[str, str]]:
            from alembic.script import ScriptDirectory

            script = ScriptDirectory.from_config(self._alembic_cfg)
            result: list[dict[str, str]] = []
            for rev in script.walk_revisions("base", "heads"):
                # Each rev is a Revision object with revision, down_revision, doc
                down_rev = rev.down_revision
                down: str
                if down_rev is None:
                    down = "<base>"
                elif isinstance(down_rev, str):
                    down = down_rev
                else:
                    down = ",".join(down_rev)
                result.append(
                    {
                        "revision": rev.revision,
                        "down_revision": down,
                        "message": rev.doc or "",
                    }
                )
            return result

        return await self._run_sync(_get_history)

    async def downgrade(self, revision: str = "-1") -> str | None:
        """Roll back to *revision* (default: ``-1`` = one migration).

        Returns the final revision after the downgrade.
        """
        try:
            await self._run_sync(command.downgrade, self._alembic_cfg, revision)
        except Exception as exc:
            logger.exception("Migration downgrade failed")
            raise MigrationError(f"Downgrade to {revision} failed: {exc}") from exc
        return await self.current()

    async def stamp(self, revision: str) -> None:
        """Stamp the database at *revision* without running migrations.

        Parameters
        ----------
        revision : str
            Revision hash (or ``"base"``) to stamp the database at.

        Raises
        ------
        MigrationError
            If the Alembic stamp operation fails.
        """
        try:
            await self._run_sync(command.stamp, self._alembic_cfg, revision)
        except Exception as exc:
            logger.exception("Stamp failed")
            raise MigrationError(f"Stamp at {revision} failed: {exc}") from exc

    async def create_revision(self, message: str) -> str:
        """Auto-generate a new migration from ORM model changes.

        Returns the revision hash of the generated migration.
        """

        def _create() -> str:
            from alembic.script import ScriptDirectory

            script = ScriptDirectory.from_config(self._alembic_cfg)
            command.revision(self._alembic_cfg, autogenerate=True, message=message)
            # The newly created file is at the HEAD
            head = script.get_current_head()
            if head is None:
                raise RuntimeError("No HEAD revision found after generating migration")
            return head

        return await self._run_sync(_create)

    async def ensure_migrated(self) -> None:
        """Run upgrade or strict-verify based on ``ANVIL_DB_AUTO_MIGRATE`` config.

        When ``db_auto_migrate`` is ``True`` (the default) this calls
        :meth:`upgrade` to apply pending migrations. Otherwise it
        calls :meth:`verify_schema` and raises ``MigrationError`` if
        the schema is not at HEAD.
        """
        cfg = get_config()
        if cfg["db_auto_migrate"]:
            before, after = await self.upgrade()
            if before != after:
                logger.info(
                    "Auto-migrated DB: %s → %s", before or "<base>", after or "<base>"
                )
            else:
                logger.info("Database already at HEAD: %s — no action needed", after)
        else:
            await self.verify_schema()

    # ------------------------------------------------------------------
    # Schema version (PRAGMA user_version) support
    # ------------------------------------------------------------------

    async def get_schema_version(self) -> int:
        """Read ``PRAGMA user_version`` from the SQLite database.

        Returns
        -------
        int
            The stored schema version, or ``0`` if the database is
            fresh/unstamped (no file, no table, or unreadable).
        """

        def _get() -> int:
            from sqlalchemy import create_engine

            sync_url = self._db_url.replace("+aiosqlite", "")
            engine = create_engine(sync_url)
            try:
                with engine.connect() as conn:
                    row = conn.exec_driver_sql("PRAGMA user_version").fetchone()
                    return int(row[0]) if row else 0
            except Exception:
                return 0
            finally:
                engine.dispose()

        return await self._run_sync(_get)

    async def set_schema_version(self) -> None:
        """Write ``SCHEMA_VERSION`` to ``PRAGMA user_version``.

        Called after a successful migration upgrade so that subsequent
        startup checks can verify the DB matches the code.
        """

        def _set() -> None:
            from sqlalchemy import create_engine

            sync_url = self._db_url.replace("+aiosqlite", "")
            engine = create_engine(sync_url)
            try:
                with engine.connect() as conn:
                    conn.exec_driver_sql(f"PRAGMA user_version = {SCHEMA_VERSION}")
                    conn.commit()
            finally:
                engine.dispose()

        await self._run_sync(_set)

    async def ensure_schema_version(self) -> None:
        """Verify the DB schema version matches ``SCHEMA_VERSION``.

        Raises ``MigrationError`` if the database has a non-zero
        *user_version* that does not match the code constant.  A
        *user_version* of ``0`` (fresh DB) is always allowed — the
        version will be set after the first migration run.

        Raises
        ------
        MigrationError
            If a version mismatch is detected — likely caused by a
            squashed migration that this database predates.
        """
        db_version = await self.get_schema_version()
        if db_version == 0:
            return
        if db_version != SCHEMA_VERSION:
            raise MigrationError(
                f"Database schema version mismatch: DB has v{db_version}, "
                f"code expects v{SCHEMA_VERSION}. "
                "This usually means Alembic migrations were squashed "
                "after this database was created.\n"
                "Fix: rm data/anvil-state.db && make run"
            )

    # ------------------------------------------------------------------
    # Table integrity check
    # ------------------------------------------------------------------

    @staticmethod
    async def verify_table_integrity(
        db_url: str | None = None,
    ) -> list[str]:
        """Compare ORM-model tables against the actual database schema.

        Returns a list of missing table names (empty = all present).

        Parameters
        ----------
        db_url : str, optional
            SQLAlchemy database URL. Defaults to config.
        """
        from sqlalchemy import create_engine, text

        if db_url is None:
            db_url = f"sqlite+aiosqlite:///{get_config()['state_db_path']}"

        from ..db.registry import get_expected_tables

        expected = get_expected_tables()

        def _check() -> list[str]:
            sync_url = db_url.replace("+aiosqlite", "")
            engine = create_engine(sync_url)
            try:
                with engine.connect() as conn:
                    rows = conn.execute(
                        text("SELECT name FROM sqlite_master " "WHERE type='table'")
                    ).fetchall()
                    actual = {row[0] for row in rows}
                return sorted(expected - actual)
            finally:
                engine.dispose()

        import asyncio

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _check)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _rev_is_ahead(current: str, head: str, script: ScriptDirectory) -> bool:
        """Check if *current* is an ancestor of *head* (i.e., ahead of code)."""
        try:
            rev_obj = script.get_revision(current)
            if rev_obj is None:
                return False
            # Walk up the chain to see if head is reachable
            return current != head and script.get_revision(head) is not None
        except Exception:
            return False
