# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Detect version increment from merge commit message.

Classifies a merge commit to decide whether a release should proceed.
Outputs ``INCREMENT_TYPE`` (AUTO/PATCH/SKIP/NONE) for the release workflow.
The actual version bump is delegated to ``cz bump`` (commitizen).

Used by the ``anvil-vault detect-increment`` CLI subcommand from
``.github/workflows/release.yml``.
"""

from __future__ import annotations

import os
import re
import subprocess


def _read_version(filepath: str = "pyproject.toml") -> str | None:
    """Extract the version string from a PEP 621 ``pyproject.toml``.

    Parameters
    ----------
    filepath : str
        Path to ``pyproject.toml`` (default: ``"pyproject.toml"``).

    Returns
    -------
    str or None
        The version string (e.g. ``"0.5.0"``), or ``None`` if not found.
    """
    try:
        with open(filepath) as f:
            for line in f:
                m = re.match(r'^version = "(.+)"', line)
                if m:
                    return m.group(1)
    except FileNotFoundError:
        return None
    return None


def _parent_version() -> str | None:
    """Read version from ``pyproject.toml`` at the parent git commit.

    Returns
    -------
    str or None
        Version string from ``HEAD^:pyproject.toml``, or ``None`` if
        the parent commit does not exist or lacks a version field.
    """
    result = subprocess.run(
        ["git", "show", "HEAD^:pyproject.toml"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    for line in result.stdout.splitlines():
        m = re.match(r'^version = "(.+)"', line)
        if m:
            return m.group(1)
    return None


def _merge_message() -> str:
    """Return the most recent commit's full message."""
    result = subprocess.run(
        ["git", "log", "-1", "--format=%B"],
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def main() -> None:
    """Print ``key=value`` lines to stdout for ``$GITHUB_OUTPUT``."""
    current = _read_version() or "unknown"
    prev = _parent_version()

    print(f"version={current}")
    print(f"version_current={current}")
    print(f"version_prev={prev or 'none'}")

    if os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch":
        print("increment=PATCH")
        print("version_changed=true")
        return

    if prev is not None and current != prev:
        print("increment=SKIP")
        print("version_changed=true")
        return

    msg = _merge_message()
    if msg and re.match(
        r"^(BREAKING CHANGE|feat|fix|perf|refactor|chore|docs|ci|test|style|build)",
        msg,
        re.IGNORECASE,
    ):
        print("increment=AUTO")
        print("version_changed=true")
    else:
        print("increment=NONE")
        print("version_changed=false")


if __name__ == "__main__":
    main()
