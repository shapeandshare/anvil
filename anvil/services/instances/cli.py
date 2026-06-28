# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""anvil-instance CLI — manage isolated anvil instances.

Usage
-----
    anvil-instance create <name> --workspace PATH [--web-port N] [--mlflow-port N]
    anvil-instance start <name>
    anvil-instance stop <name>
    anvil-instance restart <name>
    anvil-instance status <name>
    anvil-instance list [--json]
    anvil-instance destroy <name> --yes [--keep-data] [--force]

Exit codes
----------
0 — success
1 — general error / missing command
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...workbench import AnvilWorkbench


def build_parser() -> argparse.ArgumentParser:
    """Construct the argument parser for all subcommands."""
    parser = argparse.ArgumentParser(
        prog="anvil-instance",
        description="Manage isolated anvil instances",
    )
    sub = parser.add_subparsers(dest="command")

    # create
    create_p = sub.add_parser("create", help="Create a new isolated instance")
    create_p.add_argument("name", help="Instance name (alphanumeric, _, -)")
    create_p.add_argument(
        "--workspace",
        "-w",
        required=True,
        type=Path,
        help="Workspace root directory",
    )
    create_p.add_argument(
        "--web-port",
        type=int,
        default=None,
        help="Web/uvicorn port (auto-allocated if omitted)",
    )
    create_p.add_argument(
        "--mlflow-port",
        type=int,
        default=None,
        help="MLflow sidecar port (auto-allocated if omitted)",
    )

    # start
    sub.add_parser("start", help="Start an instance").add_argument("name")

    # stop
    sub.add_parser("stop", help="Stop an instance").add_argument("name")

    # restart
    sub.add_parser("restart", help="Restart an instance").add_argument("name")

    # status
    sub.add_parser("status", help="Show instance runtime status").add_argument("name")

    # list
    list_p = sub.add_parser("list", help="List all registered instances")
    list_p.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON array instead of a table",
    )

    # destroy
    destroy_p = sub.add_parser("destroy", help="Destroy a registered instance")
    destroy_p.add_argument("name", help="Instance name to destroy")
    destroy_p.add_argument(
        "--yes",
        action="store_true",
        help="Skip interactive confirmation",
    )
    destroy_p.add_argument(
        "--keep-data",
        action="store_true",
        help="Preserve workspace data on disk",
    )
    destroy_p.add_argument(
        "--force",
        action="store_true",
        help="Stop a running instance before destroying",
    )

    return parser


def main(argv: list[str] | None = None) -> None:
    """Entry point for ``anvil-instance`` CLI."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    asyncio.run(_run(args))


async def _run(args: argparse.Namespace) -> None:
    """Execute the requested subcommand."""
    from ...db.repositories.instance_registry import create_registry_session
    from ...db.session import AsyncSessionLocal
    from ...workbench import AnvilWorkbench

    registry_session = await create_registry_session()

    async with AsyncSessionLocal() as session:
        wb = AnvilWorkbench(session, registry_session=registry_session)

        if args.command == "create":
            await _cmd_create(args, wb)
        elif args.command == "start":
            await _cmd_start(args, wb)
        elif args.command == "stop":
            await _cmd_stop(args, wb)
        elif args.command == "restart":
            await _cmd_restart(args, wb)
        elif args.command == "status":
            await _cmd_status(args, wb)
        elif args.command == "list":
            await _cmd_list(args, wb)
        elif args.command == "destroy":
            await _cmd_destroy(args, wb)
        else:
            print(f"Subcommand '{args.command}' not yet implemented")
            sys.exit(1)

        await session.commit()


async def _cmd_create(args: argparse.Namespace, wb: AnvilWorkbench) -> None:
    """Create a new instance and print the result."""
    record = await wb.instances.create(
        name=args.name,
        workspace_root=args.workspace,
        web_port=args.web_port,
        mlflow_port=args.mlflow_port,
    )
    print(
        f"Instance '{record.name}' created (web={record.web_port}, "
        f"mlflow={record.mlflow_port}, "
        f"workspace={record.workspace_root})"
    )


async def _cmd_start(args: argparse.Namespace, wb: AnvilWorkbench) -> None:
    """Start an instance."""
    try:
        await wb.instances.start(args.name)
        print(f"Instance '{args.name}' started")
    except (ValueError, RuntimeError, FileNotFoundError) as exc:
        print(f"Error: {exc}")
        sys.exit(1)


async def _cmd_stop(args: argparse.Namespace, wb: AnvilWorkbench) -> None:
    """Stop an instance."""
    try:
        await wb.instances.stop(args.name)
        print(f"Instance '{args.name}' stopped")
    except (ValueError, FileNotFoundError) as exc:
        print(f"Error: {exc}")
        sys.exit(1)


async def _cmd_restart(args: argparse.Namespace, wb: AnvilWorkbench) -> None:
    """Restart an instance (stop then start)."""
    try:
        await wb.instances.restart(args.name)
        print(f"Instance '{args.name}' restarted")
    except (ValueError, RuntimeError, FileNotFoundError) as exc:
        print(f"Error: {exc}")
        sys.exit(1)


async def _cmd_status(args: argparse.Namespace, wb: AnvilWorkbench) -> None:
    """Show instance status."""
    status = await wb.instances.status(args.name)
    print(f"Instance '{args.name}': {status.value}")


async def _cmd_list(args: argparse.Namespace, wb: AnvilWorkbench) -> None:
    """List all registered instances with live status.

    Supports ``--json`` for machine-readable output.
    """
    instances = await wb.instances.list()
    if not instances:
        print("No instances registered")
        return

    if args.json:
        import json

        print(json.dumps(instances, indent=2, default=str))
        return

    header = (
        f"{'NAME':24s} {'WORKSPACE':48s} {'WEB':10s} " f"{'MLFLOW':12s} {'STATUS':10s}"
    )
    print(header)
    for inst in instances:
        ws = str(inst["workspace_root"])
        print(
            f"{inst['name']:24s} {ws:48s} "
            f"{inst['web_port']:<10d} {inst['mlflow_port']:<12d} "
            f"{inst['status']:10s}"
        )


async def _cmd_destroy(args: argparse.Namespace, wb: AnvilWorkbench) -> None:
    """Destroy a registered instance."""
    if not args.yes:
        print(
            f"Error: Destroy requires confirmation. "
            f"Use --yes to confirm destruction of '{args.name}'"
        )
        sys.exit(1)

    try:
        await wb.instances.destroy(
            args.name,
            keep_data=args.keep_data,
            force=args.force,
            confirmed=True,
        )
        data_note = "" if not args.keep_data else " (data preserved)"
        print(f"Instance '{args.name}' destroyed{data_note}")
    except (ValueError, RuntimeError, FileNotFoundError) as exc:
        print(f"Error: {exc}")
        sys.exit(1)
