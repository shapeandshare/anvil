# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""anvil-backup CLI — full-deployment backup & restore commands.

Usage
-----
    anvil-backup create
    anvil-backup list [--include-safety] [--json]
    anvil-backup show <backup-id> [--json]
    anvil-backup verify <backup-id> [--json]
    anvil-backup restore <backup-id> [--force]
    anvil-backup delete <backup-id> [--confirm-last]
    anvil-backup status [--json]
    anvil-backup cleanup-safety [--yes]

Exit codes documented in ``contracts/cli-backup.md``.
"""

import argparse
import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path

from ...config import get_config


def build_parser() -> argparse.ArgumentParser:
    """Construct the argument parser for all subcommands."""
    parser = argparse.ArgumentParser(
        prog="anvil-backup",
        description="Full-deployment backup & restore",
    )
    sub = parser.add_subparsers(dest="command")

    # create
    sub.add_parser("create", help="Create a full deployment backup")

    # list
    list_p = sub.add_parser("list", help="List backups")
    list_p.add_argument(
        "--include-safety", action="store_true", help="Include safety snapshots"
    )
    list_p.add_argument("--json", action="store_true", help="JSON output")

    # show
    show_p = sub.add_parser("show", help="Show a single backup")
    show_p.add_argument("backup_id", help="Backup identifier")
    show_p.add_argument("--json", action="store_true", help="JSON output")

    # verify / restore / delete (stubs — implemented in later phases)
    sub.add_parser("verify", help="Verify backup integrity").add_argument("backup_id")
    sub.add_parser("restore", help="Restore from a backup").add_argument("backup_id")
    del_p = sub.add_parser("delete", help="Delete a backup")
    del_p.add_argument("backup_id")
    del_p.add_argument("--confirm-last", action="store_true")
    sub.add_parser("status", help="Show backup storage status")
    sub.add_parser("cleanup-safety", help="Remove safety snapshots").add_argument(
        "--yes", action="store_true"
    )

    return parser


def main(argv: list[str] | None = None) -> None:
    """Entry point for ``anvil-backup`` CLI."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    asyncio.run(_run(args))


async def _run(args: argparse.Namespace) -> None:
    """Execute the requested subcommand."""
    from ...db.session import AsyncSessionLocal
    from ...services.governance.audit_action import AuditAction
    from ...services.governance.audit_outcome import AuditOutcome
    from ...services.governance.audit_target_type import AuditTargetType
    from ...workbench import AnvilWorkbench

    async with AsyncSessionLocal() as session:
        wb = AnvilWorkbench(session)

        if args.command == "create":
            await _cmd_create(wb)
        elif args.command == "list":
            await _cmd_list(args, wb)
        elif args.command == "show":
            await _cmd_show(args, wb)
        elif args.command == "status":
            await _cmd_status(wb)
        elif args.command == "restore":
            await _cmd_restore(args, wb)
        else:
            print(f"Subcommand '{args.command}' not yet implemented in CLI")
            sys.exit(1)

        await session.commit()


async def _cmd_create(wb) -> None:
    """Create a backup and print result."""
    import os
    from datetime import datetime

    from ...db.models.backup_operation import BackupOperation
    from .archive_writer import ArchiveWriter
    from .snapshot_planner import SnapshotPlanner

    backup_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + os.urandom(3).hex()

    cfg = get_config()
    planner = SnapshotPlanner()
    plan = planner.plan(Path(cfg["backup_dir"]), cfg["backup_quota_bytes"])

    if not plan.sufficient_space or not plan.within_quota:
        print(f"Error: Insufficient space (need {plan.required_free_bytes} bytes)")
        sys.exit(4)

    op = BackupOperation(
        backup_id=backup_id,
        operation_type="backup",
        status="creating",
    )
    await wb.backup_repo.add(op)

    writer = ArchiveWriter(cfg["backup_dir"])
    result = await writer.write(
        backup_id=backup_id,
        roots=plan.roots,
        operation_type="backup",
    )

    await wb.backup_repo.update_fields(
        backup_id,
        status="completed",
        archive_filename=result["archive_filename"],
        archive_size_bytes=result["archive_size_bytes"],
        total_uncompressed_bytes=result["total_uncompressed_bytes"],
        manifest_sha256=result["manifest_sha256"],
        deployment_version=result["deployment_version"],
        schema_revision=result["schema_revision"],
        completed_at=datetime.now(UTC),
    )

    print(
        f"Backup created: {backup_id}  ({result['archive_size_bytes'] / 1048576:.0f} MB)"
    )

    # Audit
    try:
        await wb.audit.record(
            action_type=AuditAction.BACKUP_CREATE.value,
            target_type=AuditTargetType.BACKUP.value,
            target_id=backup_id,
            actor="system",
            outcome=AuditOutcome.SUCCESS.value,
        )
    except Exception:
        pass


async def _cmd_list(args: argparse.Namespace, wb) -> None:
    """List backups."""
    raw = await wb.backup_repo.get_all()
    if args.json:
        import json

        items = []
        now = datetime.now(UTC)
        for op in raw:
            created = op.created_at
            age = 0
            if created:
                if created.tzinfo is None:
                    created = created.replace(tzinfo=UTC)
                age = int((now - created).total_seconds())
            items.append(
                {
                    "backup_id": op.backup_id,
                    "operation_type": op.operation_type,
                    "status": op.status,
                    "created_at": op.created_at.isoformat() if op.created_at else None,
                    "archive_size_bytes": op.archive_size_bytes or 0,
                    "age_seconds": max(age, 0),
                }
            )
        print(json.dumps(items, indent=2, default=str))
    else:
        print(f"{'BACKUP ID':32s} {'TYPE':20s} {'STATUS':12s} {'SIZE':8s}  AGE")
        for op in raw:
            now = datetime.now(UTC)
            created = op.created_at
            age = ""
            if created:
                if created.tzinfo is None:
                    created = created.replace(tzinfo=UTC)
                delta = now - created
                if delta.total_seconds() < 3600:
                    age = f"{int(delta.total_seconds() // 60)}m"
                elif delta.total_seconds() < 86400:
                    age = f"{int(delta.total_seconds() // 3600)}h"
                else:
                    age = f"{int(delta.total_seconds() // 86400)}d"
            size_mb = (op.archive_size_bytes or 0) / 1048576
            print(
                f"{op.backup_id:32s} {op.operation_type:20s} {op.status:12s} "
                f"{size_mb:>6.0f}MB  {age}"
            )


async def _cmd_show(args: argparse.Namespace, wb) -> None:
    """Show a single backup."""
    op = await wb.backup_repo.get_by_backup_id(args.backup_id)
    if op is None:
        print(f"Backup not found: {args.backup_id}")
        sys.exit(5)
    print(f"Backup ID:       {op.backup_id}")
    print(f"Type:            {op.operation_type}")
    print(f"Status:          {op.status}")
    print(f"Size:            {op.archive_size_bytes or 0} bytes")
    print(f"Version:         {op.deployment_version or 'N/A'}")
    print(f"Schema rev:      {op.schema_revision or 'N/A'}")
    print(f"Created:         {op.created_at}")


async def _cmd_status(wb) -> None:
    """Show backup storage status."""
    raw = await wb.backup_repo.get_all()
    total = sum(op.archive_size_bytes or 0 for op in raw)
    count = len(raw)
    cfg = get_config()
    quota = cfg["backup_quota_bytes"]
    frac = total / quota if quota else 0
    print(f"Backups:         {count}")
    print(f"Total size:      {total / 1048576:.0f} MB")
    print(f"Quota:           {quota / 1048576:.0f} MB")
    print(f"Usage:           {frac * 100:.0f}%")
    if raw:
        print(f"Latest:          {raw[0].backup_id}")
        print(f"Oldest:          {raw[-1].backup_id}")


async def _cmd_restore(args: argparse.Namespace, wb) -> None:
    """Restore from a backup."""
    print("Creating pre-restore safety snapshot...", end=" ", flush=True)
    try:
        result = await wb._session.bind._backup_service.restore(
            backup_id=args.backup_id,
            confirm="RESTORE",
            repo=wb.backup_repo,
        )
    except Exception as exc:
        print(f"FAILED: {exc}")
        sys.exit(7)
    print(f"done ({result.get('safety_snapshot_id', '?')})")
    print(
        f"Restore complete. Pre-restore safety snapshot: "
        f"{result.get('safety_snapshot_id', '?')}"
    )
    print("Restart the application to load restored state.")


from datetime import datetime
from pathlib import Path
