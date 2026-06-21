# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""CLI entry points for vault health subcommands.

Provides the ``anvil-vault`` console script with subcommands for vault
auditing, ADR validation, guarded-import checking, and bump-scope
classification.
"""

from __future__ import annotations

import argparse
import sys


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level argument parser with subcommands.

    Returns
    -------
    argparse.ArgumentParser
        Configured parser with ``audit``, ``check-adrs``,
        ``check-guarded-imports``, and ``check-bump-scope`` subcommands.
    """
    parser = argparse.ArgumentParser(
        prog="anvil-vault",
        description="Vault health tools — audit, validate, and analyze vault integrity.",
    )
    sub = parser.add_subparsers(dest="command")

    # --- audit ---
    audit_p = sub.add_parser(
        "audit", help="Run full vault audit (mechanical + graph health)"
    )
    audit_p.add_argument(
        "--vault-dir",
        default="docs/vault",
        help="Path to Obsidian vault directory (default: docs/vault)",
    )
    audit_p.add_argument(
        "--apply",
        action="store_true",
        help="Apply safe auto-fixes in-place",
    )
    audit_p.add_argument(
        "--diff",
        action="store_true",
        help="Show proposed fixes without making changes",
    )
    audit_p.add_argument(
        "--skip-graph-health",
        action="store_true",
        help="Skip networkx graph health analysis",
    )

    # --- check-adrs ---
    adr_p = sub.add_parser("check-adrs", help="Validate ADR uniqueness and naming")
    adr_p.add_argument(
        "--decisions-dir",
        default="docs/vault/Decisions",
        help="Path to ADR decisions directory (default: docs/vault/Decisions)",
    )

    # --- check-guarded-imports ---
    guard_p = sub.add_parser(
        "check-guarded-imports",
        help="Validate TYPE_CHECKING guarded imports are annotation-only",
    )
    guard_p.add_argument(
        "--source-dir",
        default="anvil",
        help="Root directory of Python source to scan (default: anvil)",
    )

    # --- check-bump-scope ---
    bump_p = sub.add_parser(
        "check-bump-scope",
        help="Classify PR changes as version-only or full",
    )
    bump_p.add_argument(
        "--repo-root",
        default=".",
        help="Git repository root path (default: .)",
    )

    # --- detect-increment ---
    inc_p = sub.add_parser(
        "detect-increment",
        help="Classify merge commit for version increment type",
    )

    # --- check-version ---
    cv_p = sub.add_parser(
        "check-version",
        help="Detect whether version changed since parent commit",
    )

    # --- build-notes ---
    bn_p = sub.add_parser(
        "build-notes",
        help="Build release-notes.md from CHANGELOG and PR_BODY",
    )

    return parser


def main(argv: list[str] | None = None) -> None:
    """CLI entry point — parse args and dispatch to the appropriate handler.

    Parameters
    ----------
    argv : list of str or None
        Command-line arguments (defaults to ``sys.argv[1:]``).
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "audit":
        _cmd_audit(args)
    elif args.command == "check-adrs":
        _cmd_check_adrs(args)
    elif args.command == "check-guarded-imports":
        _cmd_check_guarded_imports(args)
    elif args.command == "check-bump-scope":
        _cmd_check_bump_scope(args)
    elif args.command == "detect-increment":
        _cmd_detect_increment(args)
    elif args.command == "check-version":
        _cmd_check_version(args)
    elif args.command == "build-notes":
        _cmd_build_notes(args)
    else:
        parser.print_help()
        sys.exit(1)


def _cmd_audit(args: argparse.Namespace) -> None:
    """Handle the ``audit`` subcommand.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed CLI arguments.
    """
    import asyncio

    from .vault_health_service import VaultHealthService

    async def _run() -> None:
        svc = VaultHealthService(vault_dir=args.vault_dir)
        mech, gh = await svc.run_full_audit(
            skip_graph_health=args.skip_graph_health,
        )

        error_count = len(mech.errors)
        warning_count = len(mech.warnings)

        if args.diff:
            print("Diff mode — proposed fixes:")
            for f in mech.errors:
                if f.fixable:
                    print(f"  {f.note_path}: {f.message}")
            for f in mech.warnings:
                if f.fixable:
                    print(f"  {f.note_path}: {f.message}")
            if not any(f.fixable for f in mech.errors + mech.warnings):
                print("  No fixable issues found.")
        elif args.apply:
            print("Apply mode — auto-fixes applied:")
            for f in mech.errors:
                if f.fixable:
                    print(f"  Fixed: {f.note_path}: {f.message}")
            for f in mech.warnings:
                if f.fixable:
                    print(f"  Fixed: {f.note_path}: {f.message}")
            if not any(f.fixable for f in mech.errors + mech.warnings):
                print("  No fixable issues found.")
        else:
            print(f"Vault audit: {error_count} errors, {warning_count} warnings")
            for f in mech.errors:
                sev = "ERROR"
                print(f"  [{sev}] {f.note_path}: {f.message}")
            for f in mech.warnings:
                sev = "WARN"
                print(f"  [{sev}] {f.note_path}: {f.message}")

        if gh is not None:
            print(f"\nGraph health: {gh.notes_scanned} notes scanned")
            if gh.health_score.overall > 0:
                print(f"Health score: {gh.health_score.overall:.1f}/100")

        if error_count > 0:
            sys.exit(1)

    asyncio.run(_run())


def _cmd_check_adrs(args: argparse.Namespace) -> None:
    """Handle the ``check-adrs`` subcommand.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed CLI arguments.
    """
    import os as _os

    _os.environ.setdefault("ANVIL_DECISIONS_DIR", args.decisions_dir)
    from .check_adr_unique import main as adr_main

    adr_main()


def _cmd_check_guarded_imports(args: argparse.Namespace) -> None:
    """Handle the ``check-guarded-imports`` subcommand.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed CLI arguments.
    """
    import os as _os

    _os.environ["ANVIL_ROOT"] = args.source_dir
    from .check_guarded_imports import main as guarded_main

    guarded_main()


def _cmd_check_bump_scope(args: argparse.Namespace) -> None:
    """Handle the ``check-bump-scope`` subcommand.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed CLI arguments.
    """
    import os as _os

    _os.environ["GITHUB_WORKSPACE"] = args.repo_root
    from .check_bump_scope import main as bump_main

    bump_main()


def _cmd_detect_increment(args: argparse.Namespace) -> None:
    """Handle the ``detect-increment`` subcommand."""
    from .detect_increment import main

    main()


def _cmd_check_version(args: argparse.Namespace) -> None:
    """Handle the ``check-version`` subcommand."""
    from .check_version import main

    main()


def _cmd_build_notes(args: argparse.Namespace) -> None:
    """Handle the ``build-notes`` subcommand."""
    from .build_notes import main

    main()


if __name__ == "__main__":
    main()
