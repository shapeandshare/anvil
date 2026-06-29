# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for the ``anvil-instance`` CLI — argument parsing and
command dispatch.

Tests the public functions ``build_parser`` and ``main``, plus the
internal ``_cmd_*`` dispatch functions.  The ``main`` function is
tested with its ``asyncio.run`` and ``sys.exit`` mocked to isolate
the CLI logic.

The internal ``_cmd_*`` functions are tested by constructing
``argparse.Namespace`` objects directly, allowing clean unit tests
without invoking the parser.
"""

from __future__ import annotations

import argparse
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

from anvil.services.instances.cli import (
    _cmd_create,
    _cmd_destroy,
    _cmd_list,
    _cmd_restart,
    _cmd_start,
    _cmd_status,
    _cmd_stop,
    build_parser,
    main,
)
from anvil.services.instances.instance_status import InstanceStatus


########################################################################
# build_parser tests
########################################################################


class TestBuildParser:
    """Argument-parser construction and validation."""

    def test_no_args_sets_command_none(self) -> None:
        """Parser without args sets command to None (handled by main)."""
        parser = build_parser()
        args = parser.parse_args([])
        assert args.command is None

    def test_create_subcommand(self) -> None:
        """``create`` subcommand requires ``name`` and ``--workspace``."""
        parser = build_parser()
        args = parser.parse_args(
            ["create", "my-instance", "--workspace", "/tmp/ws"]
        )
        assert args.command == "create"
        assert args.name == "my-instance"
        assert args.workspace == Path("/tmp/ws")
        assert args.web_port is None
        assert args.mlflow_port is None

    def test_create_with_ports(self) -> None:
        """``create`` accepts optional ``--web-port`` and
        ``--mlflow-port``.
        """
        parser = build_parser()
        args = parser.parse_args(
            [
                "create",
                "my-instance",
                "--workspace",
                "/tmp/ws",
                "--web-port",
                "9090",
                "--mlflow-port",
                "6000",
            ]
        )
        assert args.web_port == 9090
        assert args.mlflow_port == 6000

    def test_create_short_workspace_flag(self) -> None:
        """``-w`` is a valid short form for ``--workspace``."""
        parser = build_parser()
        args = parser.parse_args(["create", "x", "-w", "/tmp/x"])
        assert args.workspace == Path("/tmp/x")

    def test_start_subcommand(self) -> None:
        """``start`` accepts a name argument."""
        parser = build_parser()
        args = parser.parse_args(["start", "my-instance"])
        assert args.command == "start"
        assert args.name == "my-instance"

    def test_stop_subcommand(self) -> None:
        """``stop`` accepts a name argument."""
        parser = build_parser()
        args = parser.parse_args(["stop", "my-instance"])
        assert args.command == "stop"
        assert args.name == "my-instance"

    def test_restart_subcommand(self) -> None:
        """``restart`` accepts a name argument."""
        parser = build_parser()
        args = parser.parse_args(["restart", "my-instance"])
        assert args.command == "restart"
        assert args.name == "my-instance"

    def test_status_subcommand(self) -> None:
        """``status`` accepts a name argument."""
        parser = build_parser()
        args = parser.parse_args(["status", "my-instance"])
        assert args.command == "status"
        assert args.name == "my-instance"

    def test_list_subcommand(self) -> None:
        """``list`` subcommand parses and defaults to text output."""
        parser = build_parser()
        args = parser.parse_args(["list"])
        assert args.command == "list"
        assert args.json is False

    def test_list_json_flag(self) -> None:
        """``list --json`` sets the json flag."""
        parser = build_parser()
        args = parser.parse_args(["list", "--json"])
        assert args.command == "list"
        assert args.json is True

    def test_destroy_subcommand(self) -> None:
        """``destroy`` requires ``name`` and ``--yes``."""
        parser = build_parser()
        args = parser.parse_args(
            ["destroy", "my-instance", "--yes"]
        )
        assert args.command == "destroy"
        assert args.name == "my-instance"
        assert args.yes is True
        assert args.keep_data is False
        assert args.force is False

    def test_destroy_with_flags(self) -> None:
        """``destroy`` accepts ``--keep-data`` and ``--force``."""
        parser = build_parser()
        args = parser.parse_args(
            ["destroy", "my-instance", "--yes", "--keep-data", "--force"]
        )
        assert args.keep_data is True
        assert args.force is True


########################################################################
# _cmd_* function tests
########################################################################


@pytest.fixture
def mock_wb() -> MagicMock:
    """Create a MagicMock workbench with async instances service."""
    wb = MagicMock()
    wb.instances = AsyncMock()
    return wb


@pytest.fixture
def args_for_factory() -> type:
    """Helper to build Namespace objects."""

    def _build(**kwargs: object) -> argparse.Namespace:
        return argparse.Namespace(**kwargs)

    return _build


class TestCmdCreate:
    """``_cmd_create`` dispatches to ``wb.instances.create``."""

    async def test_create_prints_summary(
        self, mock_wb: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Creation prints the instance summary."""
        record = MagicMock()
        record.name = "new-instance"
        record.web_port = 8080
        record.mlflow_port = 5001
        record.workspace_root = "/tmp/ws"
        mock_wb.instances.create.return_value = record

        args = argparse.Namespace(
            name="new-instance",
            workspace=Path("/tmp/ws"),
            web_port=8080,
            mlflow_port=5001,
        )
        await _cmd_create(args, mock_wb)

        mock_wb.instances.create.assert_awaited_once_with(
            name="new-instance",
            workspace_root=Path("/tmp/ws"),
            web_port=8080,
            mlflow_port=5001,
        )
        captured = capsys.readouterr()
        assert "new-instance" in captured.out
        assert "8080" in captured.out


class TestCmdStart:
    """``_cmd_start`` dispatches to ``wb.instances.start``."""

    async def test_start_success(
        self, mock_wb: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Successful start prints confirmation."""
        args = argparse.Namespace(name="my-instance")
        await _cmd_start(args, mock_wb)
        mock_wb.instances.start.assert_awaited_once_with("my-instance")
        captured = capsys.readouterr()
        assert "my-instance" in captured.out
        assert "started" in captured.out

    async def test_start_value_error(
        self, mock_wb: MagicMock
    ) -> None:
        """ValueError from start prints error and exits."""
        mock_wb.instances.start.side_effect = ValueError("bad name")
        args = argparse.Namespace(name="bad-name")
        with pytest.raises(SystemExit):
            await _cmd_start(args, mock_wb)


class TestCmdStop:
    """``_cmd_stop`` dispatches to ``wb.instances.stop``."""

    async def test_stop_success(
        self, mock_wb: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Successful stop prints confirmation."""
        args = argparse.Namespace(name="my-instance")
        await _cmd_stop(args, mock_wb)
        mock_wb.instances.stop.assert_awaited_once_with("my-instance")
        captured = capsys.readouterr()
        assert "stopped" in captured.out

    async def test_stop_not_found(
        self, mock_wb: MagicMock
    ) -> None:
        """FileNotFoundError from stop exits."""
        mock_wb.instances.stop.side_effect = FileNotFoundError("no pid")
        args = argparse.Namespace(name="ghost")
        with pytest.raises(SystemExit):
            await _cmd_stop(args, mock_wb)


class TestCmdRestart:
    """``_cmd_restart`` dispatches to ``wb.instances.restart``."""

    async def test_restart_success(
        self, mock_wb: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Successful restart prints confirmation."""
        args = argparse.Namespace(name="my-instance")
        await _cmd_restart(args, mock_wb)
        mock_wb.instances.restart.assert_awaited_once_with("my-instance")
        captured = capsys.readouterr()
        assert "restarted" in captured.out

    async def test_restart_error(
        self, mock_wb: MagicMock
    ) -> None:
        """RuntimeError from restart exits."""
        mock_wb.instances.restart.side_effect = RuntimeError("timeout")
        args = argparse.Namespace(name="broken")
        with pytest.raises(SystemExit):
            await _cmd_restart(args, mock_wb)


class TestCmdStatus:
    """``_cmd_status`` dispatches to ``wb.instances.status``."""

    async def test_status_running(
        self, mock_wb: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Status prints the instance status value."""
        mock_wb.instances.status.return_value = InstanceStatus.RUNNING
        args = argparse.Namespace(name="my-instance")
        await _cmd_status(args, mock_wb)
        mock_wb.instances.status.assert_awaited_once_with("my-instance")
        captured = capsys.readouterr()
        assert "running" in captured.out


class TestCmdList:
    """``_cmd_list`` dispatches to ``wb.instances.list``."""

    async def test_list_empty(
        self, mock_wb: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Empty list prints a message."""
        mock_wb.instances.list.return_value = []
        args = argparse.Namespace(json=False)
        await _cmd_list(args, mock_wb)
        captured = capsys.readouterr()
        assert "No instances" in captured.out

    async def test_list_text_table(
        self, mock_wb: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Non-empty list prints a header and rows."""
        mock_wb.instances.list.return_value = [
            {
                "name": "a",
                "workspace_root": "/ws/a",
                "web_port": 8080,
                "mlflow_port": 5001,
                "status": "running",
            }
        ]
        args = argparse.Namespace(json=False)
        await _cmd_list(args, mock_wb)
        captured = capsys.readouterr()
        assert "NAME" in captured.out
        assert "a" in captured.out

    async def test_list_json(
        self, mock_wb: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """With ``--json`` flag, output is JSON."""
        mock_wb.instances.list.return_value = [
            {
                "name": "b",
                "workspace_root": "/ws/b",
                "web_port": 8081,
                "mlflow_port": 5002,
                "status": "stopped",
            }
        ]
        args = argparse.Namespace(json=True)
        await _cmd_list(args, mock_wb)
        captured = capsys.readouterr()
        import json as j

        data = j.loads(captured.out)
        assert data[0]["name"] == "b"


class TestCmdDestroy:
    """``_cmd_destroy`` checks --yes and dispatches."""

    async def test_destroy_missing_confirmation(
        self, mock_wb: MagicMock
    ) -> None:
        """Without --yes, destroy prints error and exits."""
        args = argparse.Namespace(name="my-instance", yes=False, keep_data=False, force=False)
        with pytest.raises(SystemExit):
            await _cmd_destroy(args, mock_wb)

    async def test_destroy_success(
        self, mock_wb: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """With --yes, destroy dispatches and prints confirmation."""
        args = argparse.Namespace(
            name="my-instance", yes=True, keep_data=False, force=False
        )
        await _cmd_destroy(args, mock_wb)
        mock_wb.instances.destroy.assert_awaited_once_with(
            "my-instance",
            keep_data=False,
            force=False,
            confirmed=True,
        )
        captured = capsys.readouterr()
        assert "destroyed" in captured.out

    async def test_destroy_keep_data(
        self, mock_wb: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """With --keep-data, confirmation message notes data preserved."""
        args = argparse.Namespace(
            name="my-instance", yes=True, keep_data=True, force=False
        )
        await _cmd_destroy(args, mock_wb)
        captured = capsys.readouterr()
        assert "data preserved" in captured.out

    async def test_destroy_error(
        self, mock_wb: MagicMock
    ) -> None:
        """RuntimeError from destroy exits."""
        mock_wb.instances.destroy.side_effect = RuntimeError("stale lock")
        args = argparse.Namespace(
            name="my-instance", yes=True, keep_data=False, force=False
        )
        with pytest.raises(SystemExit):
            await _cmd_destroy(args, mock_wb)


########################################################################
# _run() dispatch tests (mocked session wiring)
########################################################################


class TestRun:
    """``_run()`` wires services and dispatches to the correct ``_cmd_*``."""

    @patch("anvil.services.instances.cli.AnvilWorkbench")
    @patch("anvil.services.instances.cli.AsyncSessionLocal")
    @patch("anvil.services.instances.cli.create_registry_session")
    async def test_run_create(
        self,
        mock_reg: MagicMock,
        mock_session: MagicMock,
        mock_wb_cls: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """``_run`` dispatches ``create`` through the workbench."""
        wb = MagicMock()
        wb.instances = AsyncMock()
        record = MagicMock()
        record.name = "test-i"
        record.web_port = 8080
        record.mlflow_port = 5001
        record.workspace_root = "/tmp/ws"
        wb.instances.create.return_value = record
        mock_wb_cls.return_value = wb

        mock_session.return_value.__aenter__.return_value = AsyncMock()

        args = argparse.Namespace(
            command="create",
            name="test-i",
            workspace=Path("/tmp/ws"),
            web_port=8080,
            mlflow_port=5001,
        )
        from anvil.services.instances.cli import _run as run_fn

        await run_fn(args)
        wb.instances.create.assert_awaited_once()

    @patch("anvil.services.instances.cli.AnvilWorkbench")
    @patch("anvil.services.instances.cli.AsyncSessionLocal")
    @patch("anvil.services.instances.cli.create_registry_session")
    async def test_run_unknown_command(
        self,
        mock_reg: MagicMock,
        mock_session: MagicMock,
        mock_wb_cls: MagicMock,
    ) -> None:
        """An unknown command prints an error and exits."""
        mock_wb_cls.return_value = MagicMock()
        mock_session.return_value.__aenter__.return_value = AsyncMock()

        args = argparse.Namespace(command="unknown-command")
        from anvil.services.instances.cli import _run as run_fn

        with pytest.raises(SystemExit):
            await run_fn(args)


########################################################################
# main() integration tests (mocked asyncio.run)
########################################################################


class TestMain:
    """``main()`` entry point with mocked async dispatch."""

    @patch("anvil.services.instances.cli.asyncio.run")
    def test_main_no_command_exits(
        self, mock_run: MagicMock
    ) -> None:
        """``main()`` with no command prints help and exits."""
        with pytest.raises(SystemExit) as exc_info:
            main([])
        assert exc_info.value.code == 1
        mock_run.assert_not_called()

    @patch("anvil.services.instances.cli.asyncio.run")
    def test_main_create(
        self, mock_run: MagicMock
    ) -> None:
        """``main()`` dispatches ``create``."""
        main(["create", "my-instance", "--workspace", "/tmp/ws"])
        mock_run.assert_called_once()

    @patch("anvil.services.instances.cli.asyncio.run")
    def test_main_start(self, mock_run: MagicMock) -> None:
        """``main()`` dispatches ``start``."""
        main(["start", "my-instance"])
        mock_run.assert_called_once()

    @patch("anvil.services.instances.cli.asyncio.run")
    def test_main_stop(self, mock_run: MagicMock) -> None:
        """``main()`` dispatches ``stop``."""
        main(["stop", "my-instance"])
        mock_run.assert_called_once()

    @patch("anvil.services.instances.cli.asyncio.run")
    def test_main_restart(self, mock_run: MagicMock) -> None:
        """``main()`` dispatches ``restart``."""
        main(["restart", "my-instance"])
        mock_run.assert_called_once()

    @patch("anvil.services.instances.cli.asyncio.run")
    def test_main_status(self, mock_run: MagicMock) -> None:
        """``main()`` dispatches ``status``."""
        main(["status", "my-instance"])
        mock_run.assert_called_once()

    @patch("anvil.services.instances.cli.asyncio.run")
    def test_main_list(self, mock_run: MagicMock) -> None:
        """``main()`` dispatches ``list``."""
        main(["list"])
        mock_run.assert_called_once()

    @patch("anvil.services.instances.cli.asyncio.run")
    def test_main_destroy(self, mock_run: MagicMock) -> None:
        """``main()`` dispatches ``destroy``."""
        main(["destroy", "my-instance", "--yes"])
        mock_run.assert_called_once()
