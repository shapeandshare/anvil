# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Detect version increment from merge commit message.

Classifies a merge commit to decide whether a release should proceed.
Outputs ``INCREMENT_TYPE`` (AUTO/PATCH/SKIP/NONE) for the release workflow.
The actual version bump is delegated to ``cz bump`` (commitizen).

Classification rules:
- ``feat``, ``fix``, ``perf``, or ``BREAKING CHANGE`` (incl. ``!`` suffix
  or footer) → ``AUTO`` — commitizen determines the semver bump.
- Any other conventional commit type (``chore``, ``docs``, ``refactor``, ``revert``,
  ``test``, ``style``, ``ci``, ``build``) → ``PATCH`` — at least a
  revision bump for any intentional change.
- No conventional commit detected → ``NONE`` — no release.

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


# Commitizen bump types — cz bump automatically determines the semver
# increment for these (major for BREAKING CHANGE, minor for feat, patch
# for fix/perf).
_COMMITIZEN_BUMP_TYPES = frozenset({"feat", "fix", "perf"})

# Conventional commit types that are recognized but wouldn't trigger
# a bump via ``cz bump`` alone. We force a PATCH for these.
_OTHER_CONVENTIONAL_TYPES = frozenset(
    {"refactor", "chore", "docs", "ci", "test", "style", "build", "revert"}
)


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
    if msg:
        # BREAKING CHANGE anywhere in the message → AUTO (commitizen handles
        # the major bump from the footer or ! suffix).
        if "BREAKING CHANGE" in msg.upper():
            print("increment=AUTO")
            print("version_changed=true")
            return

        # Extract the conventional commit type prefix.
        m = re.match(r"^(\w+)", msg)
        if m:
            prefix = m.group(1).lower()
            rest = msg[len(m.group(0)) :]

            # feat! or fix! → BREAKING CHANGE indicator → AUTO
            if rest.startswith("!"):
                print("increment=AUTO")
                print("version_changed=true")
                return

            # Types that commitizen bumps automatically.
            if prefix in _COMMITIZEN_BUMP_TYPES:
                print("increment=AUTO")
                print("version_changed=true")
                return

            # Any other conventional commit → at least a patch.
            if prefix in _OTHER_CONVENTIONAL_TYPES:
                print("increment=PATCH")
                print("version_changed=true")
                return

    # No conventional commit detected, or unrecognized prefix.
    print("increment=NONE")
    print("version_changed=false")


if __name__ == "__main__":
    main()
