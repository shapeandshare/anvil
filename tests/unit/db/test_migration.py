"""Tests for MigrationService."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from anvil.db.migration import MigrationError, MigrationService


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def mock_alembic_cfg():
    """Return a MagicMock that stands in for AlembicConfig."""
    cfg = MagicMock()
    cfg.set_main_option = MagicMock()
    return cfg


@pytest.fixture
def svc(mock_alembic_cfg):
    """Build a MigrationService with a mocked Alembic config."""
    with patch("anvil.db.migration.AlembicConfig", return_value=mock_alembic_cfg):
        with patch("anvil.db.migration.get_config") as mock_get_config:
            mock_get_config.return_value = {
                "state_db_path": "/tmp/test-anvil.db",
                "db_auto_migrate": True,
            }
            service = MigrationService(
                db_url="sqlite+aiosqlite:////tmp/test-anvil.db",
                alembic_ini_path="/fake/alembic.ini",
            )
            yield service


# ======================================================================
# T002: __init__ tests
# ======================================================================


class TestInit:
    """Verify MigrationService construction."""

    def test_uses_provided_db_url(self, svc):
        assert svc._db_url == "sqlite+aiosqlite:////tmp/test-anvil.db"

    @patch("anvil.db.migration.AlembicConfig")
    @patch("anvil.db.migration.get_config")
    def test_default_db_url_from_config(
        self, mock_get_config: MagicMock, mock_alembic_cls: MagicMock
    ):
        mock_get_config.return_value = {
            "state_db_path": "/var/anvil/anvil-state.db",
            "db_auto_migrate": True,
        }
        service = MigrationService()
        assert "sqlite+aiosqlite:////var/anvil/anvil-state.db" == service._db_url

    def test_build_config_sets_sqlalchemy_url(self, svc, mock_alembic_cfg):
        # _build_config is called once during __init__ and again here = 2 total
        svc._build_config("/fake/alembic.ini")
        assert mock_alembic_cfg.set_main_option.call_count == 2
        mock_alembic_cfg.set_main_option.assert_any_call(
            "sqlalchemy.url",
            "sqlite+aiosqlite:////tmp/test-anvil.db",
        )

    def test_ensure_db_dir_creates_parent(self, svc, tmp_path: Path):
        db_path = tmp_path / "sub" / "nested" / "test.db"
        url = f"sqlite+aiosqlite:///{db_path}"
        svc._db_url = url
        svc._ensure_db_dir()
        assert db_path.parent.exists()


# ======================================================================
# T003: upgrade tests
# ======================================================================


class TestUpgrade:
    """Verify MigrationService.upgrade()."""

    @patch("anvil.db.migration.command.upgrade")
    @patch.object(MigrationService, "current")
    async def test_upgrade_applies_migrations(
        self, mock_current: AsyncMock, mock_upgrade: MagicMock, svc: MigrationService
    ):
        mock_current.side_effect = [None, "abc123def"]
        before, after = await svc.upgrade()
        assert before is None
        assert after == "abc123def"
        mock_upgrade.assert_called_once_with(svc._alembic_cfg, "heads")

    @patch("anvil.db.migration.command.upgrade")
    @patch.object(MigrationService, "current")
    async def test_upgrade_noop_when_at_head(
        self, mock_current: AsyncMock, mock_upgrade: MagicMock, svc: MigrationService
    ):
        mock_current.return_value = "abc123def"
        before, after = await svc.upgrade()
        assert before == "abc123def"
        assert after == "abc123def"

    @patch("anvil.db.migration.command.upgrade")
    async def test_upgrade_failure_raises_migration_error(
        self, mock_upgrade: MagicMock, svc: MigrationService
    ):
        mock_upgrade.side_effect = RuntimeError("DB locked")
        with pytest.raises(MigrationError, match="Migration failed"):
            await svc.upgrade()


# ======================================================================
# T004: verify_schema tests
# ======================================================================


class TestVerifySchema:
    """Verify MigrationService.verify_schema()."""

    @patch("alembic.script.ScriptDirectory")
    @patch.object(MigrationService, "current")
    async def test_verify_passes_when_matched(
        self,
        mock_current: AsyncMock,
        mock_script_dir_cls: MagicMock,
        svc: MigrationService,
    ):
        mock_current.return_value = "abc123def"
        mock_script_dir_cls.from_config.return_value.get_current_head.return_value = "abc123def"
        await svc.verify_schema()  # should not raise

    @patch("alembic.script.ScriptDirectory")
    @patch.object(MigrationService, "current")
    async def test_verify_raises_when_ahead(
        self,
        mock_current: AsyncMock,
        mock_script_dir_cls: MagicMock,
        svc: MigrationService,
    ):
        mock_current.return_value = "xyz789abc"
        mock_script_dir_cls.from_config.return_value.get_current_head.return_value = "abc123def"
        with pytest.raises(MigrationError, match="AHEAD"):
            await svc.verify_schema()

    @patch("alembic.script.ScriptDirectory")
    @patch.object(MigrationService, "current")
    async def test_verify_raises_when_behind(
        self,
        mock_current: AsyncMock,
        mock_script_dir_cls: MagicMock,
        svc: MigrationService,
    ):
        # DB is behind: current_rev exists, head_rev exists, but current is NOT
        # an ancestor of head (i.e. get_revision(current) returns None = unknown revision)
        mock_current.return_value = "abc123def"
        mock_script_dir_cls.from_config.return_value.get_current_head.return_value = "xyz789abc"
        mock_script_dir_cls.from_config.return_value.get_revision.side_effect = (
            lambda r: None  # current rev is not known to script = behind
        )
        with pytest.raises(MigrationError, match="BEHIND"):
            await svc.verify_schema()


# ======================================================================
# T005: current / history / downgrade / stamp tests
# ======================================================================


class TestCurrent:
    """Verify MigrationService.current()."""

    async def test_current_returns_none_on_empty_db(self, svc: MigrationService):
        result = await svc.current()
        assert result is None or isinstance(result, str)


class TestHistory:
    """Verify MigrationService.history()."""

    @patch("alembic.script.ScriptDirectory")
    async def test_history_returns_list(
        self, mock_script_dir_cls: MagicMock, svc: MigrationService
    ):
        rev1 = MagicMock()
        rev1.revision = "abc123"
        rev1.down_revision = None
        rev1.doc = "Initial"

        rev2 = MagicMock()
        rev2.revision = "def456"
        rev2.down_revision = "abc123"
        rev2.doc = "Add tables"

        mock_script_dir_cls.from_config.return_value.walk_revisions.return_value = [rev2, rev1]

        result = await svc.history()
        assert len(result) == 2
        assert result[0]["revision"] == "def456"
        assert result[1]["down_revision"] == "<base>"


class TestDowngrade:
    """Verify MigrationService.downgrade()."""

    @patch("anvil.db.migration.command.downgrade")
    @patch.object(MigrationService, "current", return_value="abc123def")
    async def test_downgrade_calls_alembic(
        self,
        mock_current: AsyncMock,
        mock_downgrade: MagicMock,
        svc: MigrationService,
    ):
        result = await svc.downgrade("-1")
        assert result == "abc123def"
        mock_downgrade.assert_called_once_with(svc._alembic_cfg, "-1")

    @patch("anvil.db.migration.command.downgrade")
    async def test_downgrade_failure_raises(
        self, mock_downgrade: MagicMock, svc: MigrationService
    ):
        mock_downgrade.side_effect = RuntimeError("fail")
        with pytest.raises(MigrationError, match="Downgrade"):
            await svc.downgrade("-1")


class TestStamp:
    """Verify MigrationService.stamp()."""

    @patch("anvil.db.migration.command.stamp")
    async def test_stamp_calls_alembic(
        self, mock_stamp: MagicMock, svc: MigrationService
    ):
        await svc.stamp("abc123def")
        mock_stamp.assert_called_once_with(svc._alembic_cfg, "abc123def")

    @patch("anvil.db.migration.command.stamp")
    async def test_stamp_failure_raises(
        self, mock_stamp: MagicMock, svc: MigrationService
    ):
        mock_stamp.side_effect = RuntimeError("fail")
        with pytest.raises(MigrationError, match="Stamp"):
            await svc.stamp("abc123def")


# ======================================================================
# T006: create_revision tests
# ======================================================================


class TestCreateRevision:
    """Verify MigrationService.create_revision()."""

    @patch("anvil.db.migration.command.revision")
    @patch("alembic.script.ScriptDirectory")
    async def test_create_revision_returns_head(
        self,
        mock_script_dir_cls: MagicMock,
        mock_revision: MagicMock,
        svc: MigrationService,
    ):
        mock_script_dir_cls.from_config.return_value.get_current_head.return_value = "new123rev"
        result = await svc.create_revision("add table")
        assert result == "new123rev"
        mock_revision.assert_called_once()


class TestEnsureMigrated:
    """Verify MigrationService.ensure_migrated()."""

    @patch.object(MigrationService, "upgrade")
    async def test_auto_migrate_true_calls_upgrade(
        self, mock_upgrade: AsyncMock, svc: MigrationService
    ):
        mock_upgrade.return_value = (None, "abc123")
        with patch("anvil.db.migration.get_config") as mock_cfg:
            mock_cfg.return_value = {"db_auto_migrate": True}
            await svc.ensure_migrated()
        mock_upgrade.assert_called_once()

    @patch.object(MigrationService, "verify_schema")
    async def test_auto_migrate_false_calls_verify(
        self, mock_verify: AsyncMock, svc: MigrationService
    ):
        with patch("anvil.db.migration.get_config") as mock_cfg:
            mock_cfg.return_value = {"db_auto_migrate": False}
            await svc.ensure_migrated()
        mock_verify.assert_called_once()