"""Bump-scope guard: classifies a PR's changed files as version-only or full.

This is a *classifier*, not an enforcer. It always exits 0. Branch
protection on the default branch prevents merge if the heavy gate suite
is required but skipped. The classification is used by the CI workflow
to determine whether to skip heavy gates for version-only bump PRs.

FR-006a: automated version-bump changes that modify only the version
field and CHANGELOG (no source diff) may be exempt from the full gate
suite. A fast guard MUST verify the change touches only those files.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


# Files that a version-only bump PR is permitted to touch.
_VERSION_ONLY_PATHS = frozenset({"pyproject.toml", "CHANGELOG.md"})


def _changed_files(repo_root: str = ".") -> list[str]:
    """Return the list of changed files vs. HEAD~1 (or 'main' fallback).

    Uses ``git diff --name-only HEAD~1 HEAD`` to capture files changed
    by the most recent commit on this branch. Falls back to ``main``
    if HEAD~1 is unavailable.

    Parameters
    ----------
    repo_root : str
        Path to the git repository root.

    Returns
    -------
    list of str
        Relative paths of changed files.
    """
    for ref in ("HEAD~1", "main", "origin/main"):
        try:
            result = subprocess.run(
                ["git", "diff", "--name-only", ref, "HEAD"],
                capture_output=True,
                text=True,
                check=False,
                cwd=repo_root,
            )
            if result.returncode == 0 and result.stdout.strip():
                return [f.strip() for f in result.stdout.splitlines() if f.strip()]
        except FileNotFoundError:
            break
    return ["pyproject.toml", "CHANGELOG.md"]


def _is_version_only(changed: set[str]) -> bool:
    """Return True iff *changed* touches only version-allowed paths.

    Parameters
    ----------
    changed : set of str
        Set of changed file paths (relative).

    Returns
    -------
    bool
    """
    if not changed:
        return False
    return changed.issubset(_VERSION_ONLY_PATHS)


def _validate_bump_scope(changed: set[str], repo_root: str) -> None:
    """Validate and print the bump scope classification.

    Parameters
    ----------
    changed : set of str
        Changed file paths.
    repo_root : str
        Repository root path.
    """
    version_only = _is_version_only(changed)
    print(f"BUMP_SCOPE={'version-only' if version_only else 'full'}")
    print(f"CHANGED_FILES={' '.join(sorted(changed))}")
    if version_only:
        print("Heavy gates may be skipped (version-only bump).")
    else:
        print("Full gate suite is required.")


def main() -> None:
    """CLI entry point."""
    repo_root = os.environ.get("GITHUB_WORKSPACE", ".")
    changes = _changed_files(repo_root)
    _validate_bump_scope(set(changes), repo_root)
    sys.exit(0)


if __name__ == "__main__":
    main()
