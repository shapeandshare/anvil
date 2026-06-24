# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Semantic version bump for CI release workflow.

Replaces the fragile ``sed``-based version bump in the CI release workflow
with a Python implementation. Supports MAJOR, MINOR, and PATCH increments.
Also prepends a changelog entry to ``CHANGELOG.md``.

Used by the ``anvil-vault bump`` and ``anvil-vault bump-patch`` CLI subcommands
from ``.github/workflows/release.yml``.
"""

from __future__ import annotations

import datetime
import re
import sys

from .._shared.version_utils import read_version


class BumpType:
    """Supported version increment types."""

    MAJOR = "MAJOR"
    MINOR = "MINOR"
    PATCH = "PATCH"


def _bump(version: str, increment: str) -> str:
    """Increment a ``MAJOR.MINOR.PATCH`` version string by the given type.

    Parameters
    ----------
    version : str
        Current version (e.g. ``"0.1.0"``).
    increment : str
        One of ``"MAJOR"``, ``"MINOR"``, or ``"PATCH"``.

    Returns
    -------
    str
        Bumped version.

    Raises
    ------
    ValueError
        If ``version`` does not match ``MAJOR.MINOR.PATCH``, or
        ``increment`` is not a recognized type.
    """
    m = re.match(r"^(\d+)\.(\d+)\.(\d+)$", version)
    if not m:
        raise ValueError(f"Version '{version}' does not match MAJOR.MINOR.PATCH format")
    major, minor, patch = int(m.group(1)), int(m.group(2)), int(m.group(3))

    if increment == BumpType.MAJOR:
        return f"{major + 1}.0.0"
    if increment == BumpType.MINOR:
        return f"{major}.{minor + 1}.0"
    if increment == BumpType.PATCH:
        return f"{major}.{minor}.{patch + 1}"
    raise ValueError(
        f"Unknown increment '{increment}'. Must be MAJOR, MINOR, or PATCH."
    )


def _bump_patch(version: str) -> str:
    """Increment the patch component of a ``MAJOR.MINOR.PATCH`` version string.

    Convenience wrapper around :func:`_bump` with ``increment="PATCH"``.

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
    return _bump(version, BumpType.PATCH)


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


def _prepend_changelog(
    changelog_path: str,
    new_version: str,
    increment: str = BumpType.PATCH,
) -> None:
    """Prepend a version-bump changelog entry to ``CHANGELOG.md``.

    Parameters
    ----------
    changelog_path : str
        Path to ``CHANGELOG.md``.
    new_version : str
        The new version to reference in the entry.
    increment : str
        One of ``"MAJOR"``, ``"MINOR"``, or ``"PATCH"`` (default: PATCH).
    """
    bump_label = {
        BumpType.MAJOR: "major",
        BumpType.MINOR: "minor",
        BumpType.PATCH: "patch",
    }.get(increment, "patch")

    today = datetime.date.today().isoformat()
    entry = (
        f"## v{new_version} ({today})\n"
        "\n"
        "### Features\n"
        f"- Automated {bump_label} bump: release workflow\n"
        "\n"
        "---\n"
        "\n"
    )

    with open(changelog_path) as f:
        original = f.read()

    with open(changelog_path, "w") as f:
        f.write(entry + original)


def _do_bump(
    increment: str,
    pyproject_path: str = "pyproject.toml",
    changelog_path: str = "CHANGELOG.md",
) -> tuple[str, str]:
    """Read version, bump it, write files, return (old, new).

    Parameters
    ----------
    increment : str
        One of ``"MAJOR"``, ``"MINOR"``, or ``"PATCH"``.
    pyproject_path : str
        Path to ``pyproject.toml`` (default: ``"pyproject.toml"``).
    changelog_path : str
        Path to ``CHANGELOG.md`` (default: ``"CHANGELOG.md"``).

    Returns
    -------
    tuple of str
        ``(old_version, new_version)``.

    Raises
    ------
    SystemExit
        If the current version cannot be read.
    ValueError
        If the version format is invalid.
    """
    old_version = read_version(pyproject_path)
    if old_version is None:
        print("Error: could not read version from pyproject.toml", file=sys.stderr)
        sys.exit(1)

    new_version = _bump(old_version, increment)
    _update_pyproject(pyproject_path, new_version, old_version)
    _prepend_changelog(changelog_path, new_version, increment=increment)
    return old_version, new_version


def bump_main(increment: str = BumpType.PATCH) -> None:
    """CLI entry point for ``anvil-vault bump``.

    Reads the current version from ``pyproject.toml``, bumps it by the
    given increment type, rewrites the version in-place, and prepends
    a ``CHANGELOG.md`` entry.

    Parameters
    ----------
    increment : str
        One of ``"MAJOR"``, ``"MINOR"``, or ``"PATCH"``.
    """
    pyproject_path = "pyproject.toml"
    changelog_path = "CHANGELOG.md"
    try:
        old_version, new_version = _do_bump(increment, pyproject_path, changelog_path)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"version_current={old_version}")
    print(f"version_new={new_version}")
    print(f"Bumped {pyproject_path}: {old_version} -> {new_version}")
    print(f"Updated {changelog_path}")


def main() -> None:
    """CLI entry point for ``anvil-vault bump-patch``.

    Reads the current version from ``pyproject.toml``, bumps the patch component,
    rewrites the version in-place, and prepends a ``CHANGELOG.md`` entry.
    """
    bump_main(BumpType.PATCH)


if __name__ == "__main__":
    main()
