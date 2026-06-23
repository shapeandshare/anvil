# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Patch-version bump for CI auto-bump workflow.

Replaces the fragile ``sed``-based version bump in ``.github/workflows/auto-bump.yml``
with a Python implementation using ``tomllib`` (stdlib, Python 3.11+). Also prepends
a changelog entry to ``CHANGELOG.md``.

Used exclusively by the ``anvil-vault bump-patch`` CLI subcommand.
"""

from __future__ import annotations

import datetime
import re
import sys

from .._shared.version_utils import read_version


def _bump_patch(version: str) -> str:
    """Increment the patch component of a ``MAJOR.MINOR.PATCH`` version string.

    Parameters
    ----------
    version : str
        Current version (e.g. ``"0.1.0"``).

    Returns
    -------
    str
        Bumped version (e.g. ``"0.1.1"``).

    Raises
    ------
    ValueError
        If ``version`` does not match ``MAJOR.MINOR.PATCH``.
    """
    m = re.match(r"^(\d+)\.(\d+)\.(\d+)$", version)
    if not m:
        raise ValueError(f"Version '{version}' does not match MAJOR.MINOR.PATCH format")
    major, minor, patch = int(m.group(1)), int(m.group(2)), int(m.group(3))
    return f"{major}.{minor}.{patch + 1}"


def _update_pyproject(pyproject_path: str, new_version: str, old_version: str) -> None:
    """Replace the version string in ``pyproject.toml`` in-place.

    Parameters
    ----------
    pyproject_path : str
        Path to ``pyproject.toml``.
    new_version : str
        New version to write.
    old_version : str
        Old version to replace (for safety — only replaces exact match).
    """
    with open(pyproject_path) as f:
        content = f.read()

    pattern = f'version = "{old_version}"'
    replacement = f'version = "{new_version}"'

    if pattern not in content:
        raise RuntimeError(
            f"Could not find '{pattern}' in {pyproject_path} — "
            f"expected version {old_version} but cannot locate it."
        )

    updated = content.replace(pattern, replacement, 1)

    with open(pyproject_path, "w") as f:
        f.write(updated)


def _prepend_changelog(changelog_path: str, new_version: str) -> None:
    """Prepend an auto-bump changelog entry to ``CHANGELOG.md``.

    Parameters
    ----------
    changelog_path : str
        Path to ``CHANGELOG.md``.
    new_version : str
        The new version to reference in the entry.
    """
    today = datetime.date.today().isoformat()
    entry = (
        f"## v{new_version} ({today})\n"
        "\n"
        "### Fix\n"
        "- Automated patch bump: source code merged to main without a version bump\n"
        "\n"
        "---\n"
        "\n"
    )

    with open(changelog_path) as f:
        original = f.read()

    with open(changelog_path, "w") as f:
        f.write(entry + original)


def main() -> None:
    """CLI entry point for ``anvil-vault bump-patch``.

    Reads the current version from ``pyproject.toml``, bumps the patch component,
    rewrites the version in-place, and prepends a ``CHANGELOG.md`` entry.
    """
    pyproject_path = "pyproject.toml"
    changelog_path = "CHANGELOG.md"

    old_version = read_version(pyproject_path)
    if old_version is None:
        print("Error: could not read version from pyproject.toml", file=sys.stderr)
        sys.exit(1)

    try:
        new_version = _bump_patch(old_version)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    _update_pyproject(pyproject_path, new_version, old_version)
    _prepend_changelog(changelog_path, new_version)

    print(f"version_current={old_version}")
    print(f"version_new={new_version}")
    print(f"Bumped {pyproject_path}: {old_version} -> {new_version}")
    print(f"Updated {changelog_path}")


if __name__ == "__main__":
    main()
