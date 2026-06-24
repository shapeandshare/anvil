#!/usr/bin/env python3
"""CI gate: verify SCHEMA_VERSION is bumped when migrations change.

Detects if any migration file was modified without a corresponding
bump to ``SCHEMA_VERSION`` in ``anvil/db/schema_version.py``.  This
prevents the squashed-migration bug from landing.

Usage (CI):
    git fetch origin main
    python3 scripts/ci/check_migration_integrity.py \\
        --base-ref origin/main --head-ref HEAD

Exit codes:
    0 — migration changes are accompanied by a SCHEMA_VERSION bump
    1 — migration files changed but SCHEMA_VERSION was not bumped
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_MIGRATIONS_DIR = _REPO_ROOT / "anvil" / "_resources" / "migrations" / "versions"
_SCHEMA_VERSION_FILE = _REPO_ROOT / "anvil" / "db" / "schema_version.py"


def _git_diff_files(ref_a: str, ref_b: str) -> list[str]:
    """Return file paths changed between two git refs."""
    result = subprocess.run(
        ["git", "diff", "--name-only", ref_a, ref_b],
        capture_output=True,
        text=True,
        check=True,
        cwd=_REPO_ROOT,
    )
    return [f.strip() for f in result.stdout.splitlines() if f.strip()]


def _files_under(paths: list[str], directory: Path) -> bool:
    """Check if any path is under *directory*."""
    dir_str = str(directory.resolve())
    for p in paths:
        if (_REPO_ROOT / p).resolve().as_posix().startswith(dir_str):
            return True
    return False


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Verify SCHEMA_VERSION is bumped when migrations change."
    )
    parser.add_argument(
        "--base-ref",
        default="origin/main",
        help="Base git ref to compare against (default: origin/main)",
    )
    parser.add_argument(
        "--head-ref",
        default="HEAD",
        help="Head git ref (default: HEAD)",
    )
    args = parser.parse_args(argv)

    changed = _git_diff_files(args.base_ref, args.head_ref)
    migrations_changed = _files_under(changed, _MIGRATIONS_DIR)

    if not migrations_changed:
        sys.exit(0)

    schema_version_changed = _files_under(changed, _SCHEMA_VERSION_FILE)

    if schema_version_changed:
        sys.exit(0)

    print(
        "FAIL: Migration files changed but SCHEMA_VERSION was not bumped.",
        file=sys.stderr,
    )
    print(file=sys.stderr)
    print(
        f"  Files changed under {_MIGRATIONS_DIR.relative_to(_REPO_ROOT)}/",
        file=sys.stderr,
    )
    for p in sorted(changed):
        if _files_under([p], _MIGRATIONS_DIR):
            print(f"    {p}", file=sys.stderr)
    print(file=sys.stderr)
    print(
        "  When migrations are squashed/rewritten, bump SCHEMA_VERSION in",
        file=sys.stderr,
    )
    print(
        f"  {_SCHEMA_VERSION_FILE.relative_to(_REPO_ROOT)}.",
        file=sys.stderr,
    )
    print(
        "  This ensures existing databases are rejected at startup with",
        file=sys.stderr,
    )
    print("  a clear error message instead of serving a 500.", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
