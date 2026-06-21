# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Utilities for reading and comparing PEP 621 version strings.

Shared helper used by CI-oriented subcommands (``detect-increment``,
``check-version``, ``build-notes``) to avoid duplicating version
extraction logic across modules.
"""

from __future__ import annotations

import re
import subprocess


def read_version(filepath: str = "pyproject.toml") -> str | None:
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


def parent_version() -> str | None:
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


def classify_increment(merge_msg: str) -> str:
    """Classify a conventional-commit message into a version increment type.

    Parameters
    ----------
    merge_msg : str
        The full commit message to classify.

    Returns
    -------
    str
        One of ``"MAJOR"``, ``"MINOR"``, ``"PATCH"``, or ``"NONE"``.
    """
    if re.search(r"BREAKING CHANGE", merge_msg, re.IGNORECASE):
        return "MAJOR"
    if merge_msg.startswith("feat"):
        return "MINOR"
    if merge_msg.startswith("fix"):
        return "PATCH"
    if re.match(r"^(perf|refactor|chore|docs|ci|test|style|build)", merge_msg):
        return "NONE"
    return "NONE"
