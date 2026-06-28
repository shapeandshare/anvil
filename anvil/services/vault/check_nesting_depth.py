# one-class:allow — ScanResult/result types are tightly coupled to the checker
# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Package nesting depth checker: enforces max 2 levels of sub-packaging.

Scans all directories under ``anvil/`` and flags any package (directory with
``__init__.py``) whose depth exceeds 2 levels from the ``anvil/`` root.
Follows Constitution Article X §10.5.

Known non-package directories (``__pycache__``, ``.git``, ``mlruns``,
``logs``, ``_meta``, ``.obsidian``, ``addons``) are skipped during the scan.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

#: Directories to skip during walk (not counted as package levels).
_SKIP_DIRS: set[str] = {
    "__pycache__",
    ".git",
    "mlruns",
    "logs",
    "_meta",
    ".obsidian",
    "addons",
}


@dataclass  # noqa: dataclass
class NestingViolation:
    """A package that exceeds the maximum allowed nesting depth."""

    path: str
    depth: int


@dataclass  # noqa: dataclass
class ScanResult:
    """Aggregated scan result for the entire tree."""

    violations: list[NestingViolation] = field(default_factory=list)


def _get_package_depth(root: Path, dirpath: Path) -> int:
    """Compute package nesting depth of *dirpath* relative to *root*.

    Depth is the count of directories (including *dirpath*) on the path
    from *root* to *dirpath* that contain an ``__init__.py``.  The root
    directory itself is not counted.

    Parameters
    ----------
    root : pathlib.Path
        Top-level source directory (``anvil/``).
    dirpath : pathlib.Path
        Directory whose depth to compute.

    Returns
    -------
    int
        Package nesting depth.
    """
    depth = 0
    current = dirpath
    while current != root:
        if current.joinpath("__init__.py").exists():
            depth += 1
        current = current.parent
    return depth


def scan_directory(root: Path) -> ScanResult:
    """Walk *root* and find packages exceeding max nesting depth.

    Parameters
    ----------
    root : pathlib.Path
        Directory to scan (typically ``anvil/``).

    Returns
    -------
    ScanResult
    """
    result = ScanResult()
    max_depth = 2

    for dirpath_str, dirnames, _ in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]

        current = Path(dirpath_str)

        if not current.joinpath("__init__.py").exists():
            continue

        if current == root:
            continue

        depth = _get_package_depth(root, current)
        if depth > max_depth:
            result.violations.append(NestingViolation(str(current), depth))

    return result


def main() -> None:
    """CLI entry point.

    Exits with code 0 if all packages respect the max nesting depth of 2,
    or code 1 if violations are found.
    """
    root = Path(os.environ.get("ANVIL_ROOT", "anvil"))
    if not root.exists():
        root = Path("anvil")
    if not root.exists():
        print(f"ERROR: source directory {root} not found")
        sys.exit(1)

    result = scan_directory(root)
    if result.violations:
        for v in result.violations:
            print(f"ERROR: {v.path} is at depth {v.depth} (max 2 allowed)")
        sys.exit(1)
    else:
        print("OK: All packages respect max nesting depth of 2.")
        sys.exit(0)


if __name__ == "__main__":
    main()
