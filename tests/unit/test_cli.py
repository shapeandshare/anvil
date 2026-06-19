"""Unit tests for CLI functions, including db_main subcommands."""


from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from anvil.cli import db_main


# ======================================================================
# db_main argument parsing (T014, T015, T018)
# ======================================================================


@pytest.fixture
def mock_migration_service():
    """Patch MigrationService so CLI tests don't touch real DB.

    Since db_main() imports MigrationService inside _run(), we
    patch at the source (anvil.db.migration.MigrationService).
    """
    with patch("anvil.db.migration.MigrationService") as mock_cls:
        instance = MagicMock()
        instance.upgrade = AsyncMock(return_value=(None, "abc123"))
        instance.downgrade = AsyncMock(return_value="def456")
        instance.current = AsyncMock(return_value="abc123")
        instance.history = AsyncMock(return_value=[
            {"revision": "abc123", "down_revision": "<base>", "message": "Initial"},
        ])
        instance.create_revision = AsyncMock(return_value="new456rev")
        instance.stamp = AsyncMock()
        mock_cls.return_value = instance
        yield instance


class TestDbMain:
    """Verify db_main CLI argument parsing and delegation."""

    def test_upgrade_calls_service(self, mock_migration_service):
        db_main(["upgrade"])
        mock_migration_service.upgrade.assert_awaited_once()

    def test_downgrade_default(self, mock_migration_service):
        db_main(["downgrade"])
        mock_migration_service.downgrade.assert_awaited_once_with("-1")

    def test_downgrade_specific_revision(self, mock_migration_service):
        db_main(["downgrade", "xyz789"])
        mock_migration_service.downgrade.assert_awaited_once_with("xyz789")

    def test_current_calls_service(self, mock_migration_service):
        db_main(["current"])
        mock_migration_service.current.assert_awaited_once()

    def test_history_calls_service(self, mock_migration_service):
        db_main(["history"])
        mock_migration_service.history.assert_awaited_once()

    def test_revision_calls_service(self, mock_migration_service):
        db_main(["revision", "-m", "add table"])
        mock_migration_service.create_revision.assert_awaited_once_with("add table")

    def test_stamp_calls_service(self, mock_migration_service):
        db_main(["stamp", "abc123"])
        mock_migration_service.stamp.assert_awaited_once_with("abc123")

    def test_revision_requires_message(self):
        with pytest.raises(SystemExit):
            db_main(["revision"])

    @patch("anvil.db.migration.MigrationService")
    def test_migration_error_exits_with_code_1(self, mock_cls: MagicMock):
        from anvil.db.migration_error import MigrationError
        instance = MagicMock()
        instance.upgrade = AsyncMock(side_effect=MigrationError("fail"))
        mock_cls.return_value = instance
        with pytest.raises(SystemExit):
            db_main(["upgrade"])