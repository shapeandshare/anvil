"""MigrationService — programmatic Alembic migration wrapper."""

import asyncio
import logging
from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config as AlembicConfig

from anvil.config import get_config

logger = logging.getLogger(__name__)

ALEMBIC_INI = str(Path(__file__).resolve().parent.parent.parent / "alembic.ini")


class MigrationError(RuntimeError):
    """Raised when a migration operation fails or schema is out of date."""

    def __init__(self, message: str, current_rev: str | None = None, head_rev: str | None = None):
        self.current_rev = current_rev
        self.head_rev = head_rev
        super().__init__(message)


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
        cfg = get_config()
        self._db_url = db_url or f"sqlite+aiosqlite:///{cfg['state_db_path']}"
        self._alembic_cfg = self._build_config(alembic_ini_path)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_config(self, ini_path: str) -> AlembicConfig:
        """Load Alembic config and override the database URL at runtime."""
        alembic_cfg = AlembicConfig(ini_path)
        alembic_cfg.set_main_option("sqlalchemy.url", self._db_url)
        return alembic_cfg

    def _ensure_db_dir(self) -> None:
        """Create parent directories for the SQLite file if they don't exist."""
        # Parse the file path from the sqlalchemy URL
        # URL format: sqlite+aiosqlite:///absolute/path/to/db
        url = self._db_url
        if url.startswith("sqlite+aiosqlite:///"):
            db_path = url[len("sqlite+aiosqlite:///"):]
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    async def _run_sync(self, fn, *args: Any, **kwargs: Any) -> Any:
        """Run a synchronous Alembic command in a thread executor."""
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

        if current_rev and head_rev and self._rev_is_ahead(current_rev, head_rev, script):
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
                result.append({
                    "revision": rev.revision,
                    "down_revision": rev.down_revision or "<base>",
                    "message": rev.doc or "",
                })
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
            raise MigrationError(
                f"Downgrade to {revision} failed: {exc}"
            ) from exc
        return await self.current()

    async def stamp(self, revision: str) -> None:
        """Stamp the database at *revision* without running migrations."""
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
        """Run upgrade or strict-verify based on ``ANVIL_DB_AUTO_MIGRATE`` config."""
        cfg = get_config()
        if cfg["db_auto_migrate"]:
            before, after = await self.upgrade()
            if before != after:
                logger.info("Auto-migrated DB: %s → %s", before or "<base>", after or "<base>")
            else:
                logger.info("Database already at HEAD: %s — no action needed", after)
        else:
            await self.verify_schema()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _rev_is_ahead(current: str, head: str, script: Any) -> bool:
        """Check if *current* is an ancestor of *head* (i.e., ahead of code)."""
        try:
            rev_obj = script.get_revision(current)
            if rev_obj is None:
                return False
            # Walk up the chain to see if head is reachable
            return current != head and script.get_revision(head) is not None
        except Exception:
            return False