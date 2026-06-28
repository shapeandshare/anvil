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
import asyncio
import os as _os
import sys

from .build_notes import main as build_notes_main
from .bump_version import bump_main
from .bump_version import main as bump_version_main
from .check_adr_unique import main as check_adr_unique_main
from .check_bump_scope import main as check_bump_scope_main
from .check_core_deps import main as check_core_deps_main
from .check_guarded_imports import main as check_guarded_imports_main
from .check_import_placement import main as check_import_placement_main
from .check_init_py_ownership import main as check_init_py_ownership_main
from .check_layer_boundaries import main as check_layer_boundaries_main
from .check_nesting_depth import main as check_nesting_depth_main
from .check_one_class import main as check_one_class_main
from .check_py_typed import main as check_py_typed_main
from .check_relative_imports import main as check_relative_imports_main
from .check_version import main as check_version_main
from .detect_increment import main as detect_increment_main
from .migrate_specs import run as migrate_specs_run
from .vault_health_service import VaultHealthService


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level argument parser with subcommands.

    Returns
    -------
    argparse.ArgumentParser
        Configured parser with all vault subcommands including audits,
        ADR checks, guarded-import checks, and constitution checks.
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

    # --- bump ---
    bump_p = sub.add_parser(
        "bump",
        help="Bump version by type (MAJOR/MINOR/PATCH) and prepend CHANGELOG entry",
    )
    bump_p.add_argument(
        "--increment",
        required=True,
        choices=["MAJOR", "MINOR", "PATCH"],
        help="Version increment type",
    )

    # --- bump-patch ---
    sub.add_parser(
        "bump-patch",
        help="[deprecated] Bump patch version — use 'bump --increment PATCH' instead",
    )

    # --- detect-increment ---
    sub.add_parser(
        "detect-increment",
        help="Classify merge commit for version increment type",
    )

    # --- check-version ---
    sub.add_parser(
        "check-version",
        help="Detect whether version changed since parent commit",
    )

    # --- build-notes ---
    sub.add_parser(
        "build-notes",
        help="Build release-notes.md from CHANGELOG and PR_BODY",
    )

    # --- migrate-specs ---
    ms_p = sub.add_parser(
        "migrate-specs",
        help="Migrate specs/ artifacts into docs/vault/Specs/",
    )
    ms_group = ms_p.add_mutually_exclusive_group(required=True)
    ms_group.add_argument(
        "--dry-run",
        action="store_true",
        help="Print migration plan without making changes",
    )
    ms_group.add_argument(
        "--verify-only",
        action="store_true",
        help="Check all specs are represented in vault (exit 0/1)",
    )
    ms_group.add_argument(
        "--apply",
        action="store_true",
        help="Execute the migration",
    )
    ms_p.add_argument(
        "--vault-dir",
        default="docs/vault",
        help="Path to Obsidian vault directory (default: docs/vault)",
    )
    ms_p.add_argument(
        "--specs-dir",
        default="specs",
        help="Path to specs directory (default: specs)",
    )

    # --- check-init-py ---
    sub.add_parser(
        "check-init-py",
        help="Validate __init__.py ownership policy in source tree",
    )

    # --- check-relative-imports ---
    sub.add_parser(
        "check-relative-imports",
        help="Check for absolute anvil. imports inside the anvil/ package",
    )

    # --- check-one-class ---
    sub.add_parser(
        "check-one-class",
        help="Verify one class per Python source file",
    )

    # --- check-import-placement ---
    sub.add_parser(
        "check-import-placement",
        help="Verify imports are at top of file (no lazy imports)",
    )

    # --- check-nesting ---
    sub.add_parser(
        "check-nesting",
        help="Verify max 2 levels of package nesting from anvil/ root",
    )

    # --- check-py-typed ---
    sub.add_parser(
        "check-py-typed",
        help="Verify py.typed marker exists and is configured in pyproject.toml",
    )

    # --- check-core-deps ---
    core_p = sub.add_parser(
        "check-core-deps",
        help="Verify anvil/core/ has zero third-party dependencies",
    )
    core_p.add_argument(
        "--source-dir",
        default="anvil/core",
        help="Directory to scan for third-party imports (default: anvil/core)",
    )

    # --- check-layers ---
    sub.add_parser(
        "check-layers",
        help="Verify layer boundaries in the codebase architecture",
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
    elif args.command == "bump-patch":
        _cmd_bump_patch(args)
    elif args.command == "bump":
        _cmd_bump(args)
    elif args.command == "detect-increment":
        _cmd_detect_increment(args)
    elif args.command == "check-version":
        _cmd_check_version(args)
    elif args.command == "build-notes":
        _cmd_build_notes(args)
    elif args.command == "migrate-specs":
        _cmd_migrate_specs(args)
    elif args.command == "check-init-py":
        _cmd_check_init_py(args)
    elif args.command == "check-relative-imports":
        _cmd_check_relative_imports(args)
    elif args.command == "check-one-class":
        _cmd_check_one_class(args)
    elif args.command == "check-import-placement":
        _cmd_check_import_placement(args)
    elif args.command == "check-nesting":
        _cmd_check_nesting(args)
    elif args.command == "check-py-typed":
        _cmd_check_py_typed(args)
    elif args.command == "check-core-deps":
        _cmd_check_core_deps(args)
    elif args.command == "check-layers":
        _cmd_check_layers(args)
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
    _os.environ.setdefault("ANVIL_DECISIONS_DIR", args.decisions_dir)
    check_adr_unique_main()


def _cmd_check_guarded_imports(args: argparse.Namespace) -> None:
    """Handle the ``check-guarded-imports`` subcommand.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed CLI arguments.
    """
    _os.environ["ANVIL_ROOT"] = args.source_dir
    check_guarded_imports_main()


def _cmd_check_bump_scope(args: argparse.Namespace) -> None:
    """Handle the ``check-bump-scope`` subcommand.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed CLI arguments.
    """
    _os.environ["GITHUB_WORKSPACE"] = args.repo_root
    check_bump_scope_main()


def _cmd_bump_patch(args: argparse.Namespace) -> None:
    """Handle the ``bump-patch`` subcommand.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed CLI arguments.
    """
    bump_version_main()


def _cmd_bump(args: argparse.Namespace) -> None:
    """Handle the ``bump`` subcommand.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed CLI arguments.
    """
    bump_main(increment=args.increment)


def _cmd_detect_increment(args: argparse.Namespace) -> None:
    """Handle the ``detect-increment`` subcommand."""
    detect_increment_main()


def _cmd_check_version(args: argparse.Namespace) -> None:
    """Handle the ``check-version`` subcommand."""
    check_version_main()


def _cmd_build_notes(args: argparse.Namespace) -> None:
    """Handle the ``build-notes`` subcommand."""
    build_notes_main()


def _cmd_migrate_specs(args: argparse.Namespace) -> None:
    """Handle the ``migrate-specs`` subcommand.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed CLI arguments.
    """
    sys.exit(
        migrate_specs_run(
            vault_dir=args.vault_dir,
            specs_dir=args.specs_dir,
            dry_run=args.dry_run,
            verify_only=args.verify_only,
            apply=args.apply,
        )
    )


def _cmd_check_init_py(args: argparse.Namespace) -> None:
    """Handle the ``check-init-py`` subcommand."""
    check_init_py_ownership_main()


def _cmd_check_relative_imports(args: argparse.Namespace) -> None:
    """Handle the ``check-relative-imports`` subcommand."""
    check_relative_imports_main()


def _cmd_check_one_class(args: argparse.Namespace) -> None:
    """Handle the ``check-one-class`` subcommand."""
    _os.environ["ANVIL_ROOT"] = getattr(args, "source_dir", "anvil")
    check_one_class_main()


def _cmd_check_import_placement(args: argparse.Namespace) -> None:
    """Handle the ``check-import-placement`` subcommand."""
    check_import_placement_main()


def _cmd_check_nesting(args: argparse.Namespace) -> None:
    """Handle the ``check-nesting`` subcommand."""
    check_nesting_depth_main()


def _cmd_check_py_typed(args: argparse.Namespace) -> None:
    """Handle the ``check-py-typed`` subcommand."""
    check_py_typed_main()


def _cmd_check_core_deps(args: argparse.Namespace) -> None:
    """Handle the ``check-core-deps`` subcommand."""
    _os.environ["ANVIL_ROOT"] = getattr(args, "source_dir", "anvil/core")
    check_core_deps_main()


def _cmd_check_layers(args: argparse.Namespace) -> None:
    """Handle the ``check-layers`` subcommand."""
    check_layer_boundaries_main()


if __name__ == "__main__":
    main()
