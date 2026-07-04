"""Tests for anvil-backup CLI argument parser, command dispatch, and
``_cmd_*`` implementation functions.

Covers the full CLI surface: argument parsing, ``main()`` entry point,
``_run()`` dispatch, and individual command handlers.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

from anvil.services.backup.cli import (
    _cmd_create,
    _cmd_list,
    _cmd_restore,
    _cmd_show,
    _cmd_status,
    _run,
    build_parser,
    main,
)

########################################################################
# Parser tests
########################################################################


class TestCLIParser:
    """Parser structure and argument validation."""

    def test_parser_accepts_create(self):
        parser = build_parser()
        args = parser.parse_args(["create"])
        assert args.command == "create"

    def test_parser_accepts_list(self):
        parser = build_parser()
        args = parser.parse_args(["list"])
        assert args.command == "list"

    def test_parser_accepts_list_with_flags(self):
        parser = build_parser()
        args = parser.parse_args(["list", "--include-safety", "--json"])
        assert args.command == "list"
        assert args.include_safety is True
        assert args.json is True

    def test_parser_accepts_show(self):
        parser = build_parser()
        args = parser.parse_args(["show", "some-backup-id"])
        assert args.command == "show"
        assert args.backup_id == "some-backup-id"

    def test_parser_accepts_restore(self):
        parser = build_parser()
        args = parser.parse_args(["restore", "backup-123"])
        assert args.command == "restore"
        assert args.backup_id == "backup-123"

    def test_parser_accepts_delete(self):
        parser = build_parser()
        args = parser.parse_args(["delete", "backup-123"])
        assert args.command == "delete"
        assert args.backup_id == "backup-123"

    def test_parser_accepts_verify(self):
        parser = build_parser()
        args = parser.parse_args(["verify", "backup-123"])
        assert args.command == "verify"
        assert args.backup_id == "backup-123"

    def test_parser_no_args_exits(self):
        """Running the CLI with no args should call sys.exit(1)."""
        import sys

        try:
            main([])
        except SystemExit as e:
            assert e.code == 1

    def test_parser_accepts_status(self):
        parser = build_parser()
        args = parser.parse_args(["status"])
        assert args.command == "status"

    def test_parser_accepts_cleanup_safety(self):
        """``cleanup-safety`` subcommand accepts optional ``--yes``."""
        parser = build_parser()
        args = parser.parse_args(["cleanup-safety", "--yes"])
        assert args.command == "cleanup-safety"
        assert args.yes is True

    def test_parser_show_json_flag(self):
        """``show`` subcommand accepts ``--json`` flag."""
        parser = build_parser()
        args = parser.parse_args(["show", "bid", "--json"])
        assert args.json is True

    def test_parser_delete_with_confirm(self):
        """``delete`` subcommand accepts ``--confirm-last``."""
        parser = build_parser()
        args = parser.parse_args(["delete", "bid", "--confirm-last"])
        assert args.confirm_last is True


########################################################################
# _cmd_* tests
########################################################################


@pytest.fixture
def mock_backup_op() -> MagicMock:
    """Create a mock BackupOperation with basic fields set."""
    op = MagicMock()
    op.backup_id = "test-backup-001"
    op.operation_type = "backup"
    op.status = "completed"
    op.archive_size_bytes = 5_242_880  # 5 MB
    op.deployment_version = "1.0.0"
    op.schema_revision = "abc123"
    op.created_at = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)
    return op


@pytest.fixture
def mock_wb(mock_backup_op: MagicMock) -> MagicMock:
    """Create a MagicMock workbench."""
    wb = MagicMock()
    wb.backup_repo = AsyncMock()
    wb.backup_repo.get_all.return_value = [mock_backup_op]
    wb.backup_repo.get_by_backup_id.return_value = mock_backup_op
    wb.backup_repo.add = AsyncMock()
    wb.backup_repo.update_fields = AsyncMock()
    wb.audit = AsyncMock()
    wb.audit.record = AsyncMock()
    return wb


class TestCmdCreate:
    """``_cmd_create`` — backup creation flow."""

    @patch("anvil.services.backup.cli.get_config")
    @patch("anvil.services.backup.cli.SnapshotPlanner")
    @patch("anvil.services.backup.cli.ArchiveWriter")
    async def test_create_success(
        self,
        mock_writer_cls: MagicMock,
        mock_planner_cls: MagicMock,
        mock_get_config: MagicMock,
        mock_wb: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Successful backup prints the backup ID and size."""
        mock_get_config.return_value = {
            "backup_dir": "/tmp/backups",
            "backup_quota_bytes": 1_000_000_000,
        }

        plan = MagicMock()
        plan.sufficient_space = True
        plan.within_quota = True
        plan.required_free_bytes = 0
        plan.roots = ["/data", "/logs"]
        mock_planner_cls.return_value.plan.return_value = plan

        result = {
            "archive_filename": "backup-001.tar.gz",
            "archive_size_bytes": 5_242_880,
            "total_uncompressed_bytes": 10_485_760,
            "manifest_sha256": "abcd",
            "deployment_version": "1.0.0",
            "schema_revision": "abc123",
        }
        mock_writer_cls.return_value.write = AsyncMock(return_value=result)

        await _cmd_create(mock_wb)

        mock_planner_cls.return_value.plan.assert_called_once()
        mock_writer_cls.return_value.write.assert_called_once()
        mock_wb.backup_repo.add.assert_awaited_once()
        mock_wb.backup_repo.update_fields.assert_awaited_once()
        mock_wb.audit.record.assert_awaited_once()

        captured = capsys.readouterr()
        assert "Backup created" in captured.out

    @patch("anvil.services.backup.cli.get_config")
    @patch("anvil.services.backup.cli.SnapshotPlanner")
    @patch("anvil.services.backup.cli.ArchiveWriter")
    async def test_create_audit_fails(
        self,
        mock_writer_cls: MagicMock,
        mock_planner_cls: MagicMock,
        mock_get_config: MagicMock,
        mock_wb: MagicMock,
    ) -> None:
        """Audit failure does not prevent backup completion."""
        mock_get_config.return_value = {
            "backup_dir": "/tmp/backups",
            "backup_quota_bytes": 1_000_000_000,
        }

        plan = MagicMock()
        plan.sufficient_space = True
        plan.within_quota = True
        plan.required_free_bytes = 0
        plan.roots = ["/data"]
        mock_planner_cls.return_value.plan.return_value = plan

        result = {
            "archive_filename": "backup-002.tar.gz",
            "archive_size_bytes": 1024,
            "total_uncompressed_bytes": 2048,
            "manifest_sha256": "abcd",
            "deployment_version": "1.0",
            "schema_revision": "r2",
        }
        mock_writer_cls.return_value.write = AsyncMock(return_value=result)

        # Make audit.record raise OSError to test the except block
        mock_wb.audit.record = AsyncMock(side_effect=OSError("db locked"))

        await _cmd_create(mock_wb)
        mock_wb.audit.record.assert_awaited_once()

    @patch("anvil.services.backup.cli.get_config")
    @patch("anvil.services.backup.cli.SnapshotPlanner")
    @patch("anvil.services.backup.cli.ArchiveWriter")
    async def test_create_insufficient_space(
        self,
        mock_writer_cls: MagicMock,
        mock_planner_cls: MagicMock,
        mock_get_config: MagicMock,
        mock_wb: MagicMock,
    ) -> None:
        """Insufficient space exits with code 4."""
        mock_get_config.return_value = {
            "backup_dir": "/tmp/backups",
            "backup_quota_bytes": 1_000_000_000,
        }

        plan = MagicMock()
        plan.sufficient_space = False
        plan.within_quota = False
        plan.required_free_bytes = 500_000_000
        mock_planner_cls.return_value.plan.return_value = plan

        with pytest.raises(SystemExit) as exc_info:
            await _cmd_create(mock_wb)
        assert exc_info.value.code == 4


class TestCmdList:
    """``_cmd_list`` — listing backups."""

    async def test_list_json(
        self,
        mock_wb: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """With --json, output is a JSON array."""
        args = argparse.Namespace(json=True, include_safety=False)
        await _cmd_list(args, mock_wb)
        captured = capsys.readouterr()
        import json

        data = json.loads(captured.out)
        assert len(data) == 1
        assert data[0]["backup_id"] == "test-backup-001"

    async def test_list_text(
        self,
        mock_wb: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Without --json, output is a text table."""
        args = argparse.Namespace(json=False, include_safety=False)
        await _cmd_list(args, mock_wb)
        captured = capsys.readouterr()
        assert "BACKUP ID" in captured.out
        assert "test-backup-001" in captured.out

    async def test_list_empty(
        self,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """No backups produces an empty table."""
        wb = MagicMock()
        wb.backup_repo = AsyncMock()
        wb.backup_repo.get_all.return_value = []

        args = argparse.Namespace(json=False, include_safety=False)
        await _cmd_list(args, wb)
        captured = capsys.readouterr()
        assert "BACKUP ID" in captured.out  # header always prints

    async def test_list_json_naive_datetime(
        self,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """JSON output handles naive datetime (no tzinfo)."""
        from datetime import datetime

        op = MagicMock()
        op.backup_id = "naive-op"
        op.operation_type = "backup"
        op.status = "completed"
        op.archive_size_bytes = 1024
        op.created_at = datetime(2026, 6, 1, 12, 0, 0)  # no tzinfo

        wb = MagicMock()
        wb.backup_repo = AsyncMock()
        wb.backup_repo.get_all.return_value = [op]

        args = argparse.Namespace(json=True, include_safety=False)
        await _cmd_list(args, wb)
        captured = capsys.readouterr()
        import json

        data = json.loads(captured.out)
        assert len(data) == 1
        assert data[0]["backup_id"] == "naive-op"

    async def test_list_text_young_backup(
        self,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Text output formats age as minutes for very recent backups."""
        from datetime import datetime, timedelta

        op = MagicMock()
        op.backup_id = "young-op"
        op.operation_type = "backup"
        op.status = "completed"
        op.archive_size_bytes = 2048
        op.created_at = datetime.now(UTC) - timedelta(minutes=5)

        wb = MagicMock()
        wb.backup_repo = AsyncMock()
        wb.backup_repo.get_all.return_value = [op]

        args = argparse.Namespace(json=False, include_safety=False)
        await _cmd_list(args, wb)
        captured = capsys.readouterr()
        assert "young-op" in captured.out

    async def test_list_text_hour_old_backup(
        self,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Text output formats age as hours for hour-old backups."""
        from datetime import datetime, timedelta

        op = MagicMock()
        op.backup_id = "hour-op"
        op.operation_type = "backup"
        op.status = "completed"
        op.archive_size_bytes = 4096
        op.created_at = datetime.now(UTC) - timedelta(hours=2)

        wb = MagicMock()
        wb.backup_repo = AsyncMock()
        wb.backup_repo.get_all.return_value = [op]

        args = argparse.Namespace(json=False, include_safety=False)
        await _cmd_list(args, wb)
        captured = capsys.readouterr()
        assert "hour-op" in captured.out

    async def test_list_text_naive_datetime(
        self,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Text output handles naive datetime (no tzinfo)."""
        from datetime import datetime

        op = MagicMock()
        op.backup_id = "naive-text-op"
        op.operation_type = "backup"
        op.status = "completed"
        op.archive_size_bytes = 512
        op.created_at = datetime(2026, 6, 1, 12, 0, 0)  # no tzinfo

        wb = MagicMock()
        wb.backup_repo = AsyncMock()
        wb.backup_repo.get_all.return_value = [op]

        args = argparse.Namespace(json=False, include_safety=False)
        await _cmd_list(args, wb)
        captured = capsys.readouterr()
        assert "naive-text-op" in captured.out


class TestCmdShow:
    """``_cmd_show`` — displaying a single backup."""

    async def test_show_found(
        self,
        mock_wb: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Existing backup prints its details."""
        args = argparse.Namespace(backup_id="test-backup-001", json=False)
        await _cmd_show(args, mock_wb)
        captured = capsys.readouterr()
        assert "test-backup-001" in captured.out
        assert "completed" in captured.out
        assert "5 MB" in captured.out or "5242880" in captured.out

    async def test_show_not_found(
        self,
        mock_wb: MagicMock,
    ) -> None:
        """Non-existent backup exits with code 5."""
        mock_wb.backup_repo.get_by_backup_id.return_value = None
        args = argparse.Namespace(backup_id="missing", json=False)
        with pytest.raises(SystemExit) as exc_info:
            await _cmd_show(args, mock_wb)
        assert exc_info.value.code == 5


class TestCmdStatus:
    """``_cmd_status`` — storage status display."""

    @patch("anvil.services.backup.cli.get_config")
    async def test_status_with_backups(
        self,
        mock_get_config: MagicMock,
        mock_wb: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Status prints count, size, quota, usage percent."""
        mock_get_config.return_value = {
            "backup_dir": "/tmp/backups",
            "backup_quota_bytes": 100_000_000,
        }
        await _cmd_status(mock_wb)
        captured = capsys.readouterr()
        assert "Backups:" in captured.out
        assert "Quota:" in captured.out
        assert "Usage:" in captured.out

    @patch("anvil.services.backup.cli.get_config")
    async def test_status_empty(
        self,
        mock_get_config: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Status with no backups still prints quota info."""
        mock_get_config.return_value = {
            "backup_dir": "/tmp/backups",
            "backup_quota_bytes": 100_000_000,
        }
        wb = MagicMock()
        wb.backup_repo = AsyncMock()
        wb.backup_repo.get_all.return_value = []

        await _cmd_status(wb)
        captured = capsys.readouterr()
        assert "Backups:" in captured.out


class TestCmdRestore:
    """``_cmd_restore`` — restore from backup."""

    async def test_restore_success(
        self,
        mock_wb: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Successful restore prints safety snapshot ID."""
        mock_restore = AsyncMock(
            return_value={
                "safety_snapshot_id": "snap-001",
            }
        )
        mock_wb._session.bind._backup_service.restore = mock_restore
        args = argparse.Namespace(backup_id="test-backup-001")
        await _cmd_restore(args, mock_wb)
        captured = capsys.readouterr()
        assert "Restore complete" in captured.out
        assert "snap-001" in captured.out

    async def test_restore_failure(
        self,
        mock_wb: MagicMock,
    ) -> None:
        """Restore failure exits with code 7."""
        mock_wb._session.bind._backup_service.restore = AsyncMock(
            side_effect=OSError("permission denied")
        )
        args = argparse.Namespace(backup_id="test-backup-001")
        with pytest.raises(SystemExit) as exc_info:
            await _cmd_restore(args, mock_wb)
        assert exc_info.value.code == 7


########################################################################
# _run() dispatch tests
########################################################################


class TestRun:
    """``_run()`` dispatches to the correct ``_cmd_*``."""

    @patch("anvil.services.backup.cli.AnvilWorkbench")
    @patch("anvil.services.backup.cli.AsyncSessionLocal")
    async def test_run_create(
        self,
        mock_session_factory: MagicMock,
        mock_wb_cls: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """``create`` dispatches to ``_cmd_create``."""
        wb = MagicMock()
        wb.backup_repo = AsyncMock()
        wb.backup_repo.add = AsyncMock()
        wb.backup_repo.update_fields = AsyncMock()
        wb.audit = AsyncMock()
        wb.audit.record = AsyncMock()
        mock_wb_cls.return_value = wb
        mock_session = AsyncMock()
        mock_session_factory.return_value.__aenter__.return_value = mock_session

        # Patch the helpers that _cmd_create needs
        with (
            patch("anvil.services.backup.cli.get_config") as mock_cfg,
            patch("anvil.services.backup.cli.SnapshotPlanner") as mock_planner_cls,
            patch("anvil.services.backup.cli.ArchiveWriter") as mock_writer_cls,
        ):
            mock_cfg.return_value = {
                "backup_dir": "/tmp/backups",
                "backup_quota_bytes": 1_000_000_000,
            }
            plan = MagicMock()
            plan.sufficient_space = True
            plan.within_quota = True
            plan.required_free_bytes = 0
            plan.roots = ["/data"]
            mock_planner_cls.return_value.plan.return_value = plan

            result = {
                "archive_filename": "test.tar.gz",
                "archive_size_bytes": 1024,
                "total_uncompressed_bytes": 2048,
                "manifest_sha256": "abcd",
                "deployment_version": "1.0",
                "schema_revision": "r1",
            }
            mock_writer_cls.return_value.write = AsyncMock(return_value=result)

            args = argparse.Namespace(command="create")
            await _run(args)

        mock_session.commit.assert_awaited_once()

    @patch("anvil.services.backup.cli.AnvilWorkbench")
    @patch("anvil.services.backup.cli.AsyncSessionLocal")
    async def test_run_list(
        self,
        mock_session_factory: MagicMock,
        mock_wb_cls: MagicMock,
    ) -> None:
        """``list`` dispatches to ``_cmd_list``."""
        wb = MagicMock()
        wb.backup_repo = AsyncMock()
        wb.backup_repo.get_all.return_value = []
        mock_wb_cls.return_value = wb
        mock_session = AsyncMock()
        mock_session_factory.return_value.__aenter__.return_value = mock_session

        args = argparse.Namespace(command="list", json=False, include_safety=False)
        await _run(args)
        mock_session.commit.assert_awaited_once()

    @patch("anvil.services.backup.cli.AnvilWorkbench")
    @patch("anvil.services.backup.cli.AsyncSessionLocal")
    async def test_run_show(
        self,
        mock_session_factory: MagicMock,
        mock_wb_cls: MagicMock,
    ) -> None:
        """``show`` dispatches to ``_cmd_show``."""
        wb = MagicMock()
        wb.backup_repo = AsyncMock()
        wb.backup_repo.get_by_backup_id.return_value = MagicMock()
        mock_wb_cls.return_value = wb
        mock_session = AsyncMock()
        mock_session_factory.return_value.__aenter__.return_value = mock_session

        args = argparse.Namespace(command="show", backup_id="bid", json=False)
        await _run(args)
        mock_session.commit.assert_awaited_once()

    @patch("anvil.services.backup.cli.AnvilWorkbench")
    @patch("anvil.services.backup.cli.AsyncSessionLocal")
    async def test_run_status(
        self,
        mock_session_factory: MagicMock,
        mock_wb_cls: MagicMock,
    ) -> None:
        """``status`` dispatches to ``_cmd_status``."""
        wb = MagicMock()
        wb.backup_repo = AsyncMock()
        wb.backup_repo.get_all.return_value = []
        mock_wb_cls.return_value = wb
        mock_session = AsyncMock()
        mock_session_factory.return_value.__aenter__.return_value = mock_session

        with patch("anvil.services.backup.cli.get_config") as mock_cfg:
            mock_cfg.return_value = {
                "backup_dir": "/tmp/backups",
                "backup_quota_bytes": 100_000_000,
            }
            args = argparse.Namespace(command="status")
            await _run(args)

        mock_session.commit.assert_awaited_once()

    @patch("anvil.services.backup.cli.AnvilWorkbench")
    @patch("anvil.services.backup.cli.AsyncSessionLocal")
    async def test_run_restore(
        self,
        mock_session_factory: MagicMock,
        mock_wb_cls: MagicMock,
    ) -> None:
        """``restore`` dispatches to ``_cmd_restore``."""
        wb = MagicMock()
        wb.backup_repo = AsyncMock()
        wb._session.bind._backup_service.restore = AsyncMock(
            return_value={
                "safety_snapshot_id": "snap-x",
            }
        )
        mock_wb_cls.return_value = wb
        mock_session = AsyncMock()
        mock_session_factory.return_value.__aenter__.return_value = mock_session

        args = argparse.Namespace(command="restore", backup_id="bid")
        await _run(args)
        mock_session.commit.assert_awaited_once()

    @patch("anvil.services.backup.cli.AnvilWorkbench")
    @patch("anvil.services.backup.cli.AsyncSessionLocal")
    async def test_run_unknown_command(
        self,
        mock_session_factory: MagicMock,
        mock_wb_cls: MagicMock,
    ) -> None:
        """Unknown command prints an error and exits."""
        wb = MagicMock()
        mock_wb_cls.return_value = wb
        mock_session = AsyncMock()
        mock_session_factory.return_value.__aenter__.return_value = mock_session

        args = argparse.Namespace(command="unknown")
        with pytest.raises(SystemExit) as exc_info:
            await _run(args)
        assert exc_info.value.code == 1


########################################################################
# main() integration tests
########################################################################


class TestMain:
    """``main()`` entry point with mocked asyncio.run."""

    @patch("anvil.services.backup.cli.asyncio.run")
    def test_main_create(self, mock_run: MagicMock) -> None:
        """``main()`` dispatches ``create``."""
        main(["create"])
        mock_run.assert_called_once()

    @patch("anvil.services.backup.cli.asyncio.run")
    def test_main_list(self, mock_run: MagicMock) -> None:
        """``main()`` dispatches ``list``."""
        main(["list"])
        mock_run.assert_called_once()

    @patch("anvil.services.backup.cli.asyncio.run")
    def test_main_show(self, mock_run: MagicMock) -> None:
        """``main()`` dispatches ``show``."""
        main(["show", "bid"])
        mock_run.assert_called_once()

    @patch("anvil.services.backup.cli.asyncio.run")
    def test_main_restore(self, mock_run: MagicMock) -> None:
        """``main()`` dispatches ``restore``."""
        main(["restore", "bid"])
        mock_run.assert_called_once()

    @patch("anvil.services.backup.cli.asyncio.run")
    def test_main_status(self, mock_run: MagicMock) -> None:
        """``main()`` dispatches ``status``."""
        main(["status"])
        mock_run.assert_called_once()

    @patch("anvil.services.backup.cli.asyncio.run")
    def test_main_delete(self, mock_run: MagicMock) -> None:
        """``main()`` dispatches ``delete``."""
        main(["delete", "bid"])
        mock_run.assert_called_once()

    @patch("anvil.services.backup.cli.asyncio.run")
    def test_main_verify(self, mock_run: MagicMock) -> None:
        """``main()`` dispatches ``verify``."""
        main(["verify", "bid"])
        mock_run.assert_called_once()

    @patch("anvil.services.backup.cli.asyncio.run")
    def test_main_cleanup_safety(self, mock_run: MagicMock) -> None:
        """``main()`` dispatches ``cleanup-safety``."""
        main(["cleanup-safety"])
        mock_run.assert_called_once()
