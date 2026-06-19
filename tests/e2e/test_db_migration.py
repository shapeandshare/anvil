"""End-to-end tests for auto database schema management.

Tests use a real SQLite file in a temporary directory and actual Alembic
migrations to verify auto-migration behavior on startup.
"""


from pathlib import Path

import pytest

from anvil.db.migration import MigrationService
from anvil.db.migration_error import MigrationError


@pytest.fixture
def tmp_db(tmp_path: Path) -> str:
    """Return a sqlite URL pointing at a temp directory."""
    return f"sqlite+aiosqlite:///{tmp_path / 'test-anvil.db'}"


@pytest.mark.asyncio
async def test_auto_create_creates_db_and_migrates(tmp_db: str):
    """US1: Fresh DB gets auto-created and all migrations applied."""
    svc = MigrationService(db_url=tmp_db)
    before, after = await svc.upgrade()
    assert before is None  # no revision before first migration
    assert after is not None  # HEAD revision after migration
    # Verify we can read back the current revision
    current = await svc.current()
    assert current == after


@pytest.mark.asyncio
async def test_auto_create_is_idempotent(tmp_db: str):
    """US1: Running upgrade on an already-migrated DB is a no-op."""
    svc = MigrationService(db_url=tmp_db)
    await svc.upgrade()  # first run
    before2, after2 = await svc.upgrade()  # second run
    assert before2 == after2  # no change on second run


@pytest.mark.asyncio
async def test_ensure_migrated_auto_migrates(tmp_db: str):
    """US1: ensure_migrated with default config calls upgrade."""
    svc = MigrationService(db_url=tmp_db)
    # ensure_migrated reads db_auto_migrate from config — we patch it
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("ANVIL_DB_AUTO_MIGRATE", "true")
        # Rebuild service to pick up new config
        svc2 = MigrationService(db_url=tmp_db)
        await svc2.ensure_migrated()  # should not raise
        current = await svc2.current()
        assert current is not None


@pytest.mark.asyncio
async def test_strict_mode_raises_when_db_empty(tmp_db: str):
    """US2: Strict mode (ANVIL_DB_AUTO_MIGRATE=false) fails if DB untouched."""
    svc = MigrationService(db_url=tmp_db)
    with pytest.raises(MigrationError, match="BEHIND"):
        await svc.verify_schema()


@pytest.mark.asyncio
async def test_strict_mode_passes_when_db_uptodate(tmp_db: str):
    """US2: Strict mode passes when DB schema matches HEAD."""
    svc = MigrationService(db_url=tmp_db)
    await svc.upgrade()  # migrate first
    await svc.verify_schema()  # should not raise


@pytest.mark.asyncio
async def test_strict_ensure_migrated_raises_without_migration(tmp_db: str):
    """US2: ensure_migrated with ANVIL_DB_AUTO_MIGRATE=false fails if not migrated."""
    # Clear get_config() lru_cache so MonkeyPatch env var takes effect
    from anvil.config import get_config
    get_config.cache_clear()

    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("ANVIL_DB_AUTO_MIGRATE", "false")
        svc = MigrationService(db_url=tmp_db)
        with pytest.raises(MigrationError, match="BEHIND"):
            await svc.ensure_migrated()


@pytest.mark.asyncio
async def test_history_returns_migrations(tmp_db: str):
    """US3: History returns list of migrations."""
    svc = MigrationService(db_url=tmp_db)
    await svc.upgrade()
    history = await svc.history()
    assert len(history) > 0
    for entry in history:
        assert "revision" in entry
        assert "down_revision" in entry


@pytest.mark.asyncio
async def test_current_returns_revision_after_upgrade(tmp_db: str):
    """US3: Current returns revision after upgrade."""
    svc = MigrationService(db_url=tmp_db)
    await svc.upgrade()
    current = await svc.current()
    assert current is not None
    assert len(current) > 0


@pytest.mark.asyncio
async def test_downgrade_and_upgrade_roundtrip(tmp_db: str):
    """US3: Downgrade then upgrade restores HEAD."""
    svc = MigrationService(db_url=tmp_db)
    await svc.upgrade()
    head = await svc.current()

    # Downgrade one step
    await svc.downgrade("-1")
    after_downgrade = await svc.current()
    assert after_downgrade != head

    # Upgrade back
    await svc.upgrade()
    after_upgrade = await svc.current()
    assert after_upgrade == head


@pytest.mark.asyncio
async def test_stamp_sets_revision(tmp_db: str):
    """US3: Stamp sets a revision without running migrations."""
    svc = MigrationService(db_url=tmp_db)
    await svc.upgrade()
    head = await svc.current()
    assert head is not None

    # Stamp to base (re-stamping head is a no-op, but shouldn't error)
    await svc.stamp(head)
    current = await svc.current()
    assert current == head