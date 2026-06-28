# one-class:allow — ScanResult/result types are tightly coupled to the checker
# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""``__init__.py`` ownership checker: validates Python package packaging.

Enforces the ``__init__.py`` Ownership Policy (Constitution Article VI,
AGENTS.md Principle 6):

1. Every authoritative Python package level (a directory containing
   ``.py`` modules under ``anvil/``) MUST have a bare, docstring-only
   ``__init__.py`` — no re-exports, no imports (except docstring).
2. Data-only directories (``static/``, ``templates/``, etc.) MUST NOT
   have ``__init__.py``.
3. All ``__init__.py`` files with imports or re-exports are violations.
4. Directories under ``anvil/`` that contain ``.py`` files but lack
   ``__init__.py`` are violations.

Exits 0 if no violations, 1 if any are found.
"""

from __future__ import annotations

import ast
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Directories that are data-only and MUST NOT contain ``__init__.py``.
_DATA_DIRS: frozenset[str] = frozenset(
    {
        "static",
        "templates",
        "data",
        "_resources",
        "_meta",
        ".obsidian",
        "addons",
        "__pycache__",
        "mlruns",
        "logs",
        "backups",
        "migrations",
    }
)


@dataclass  # noqa: dataclass
class InitPyViolation:
    """A single ``__init__.py`` ownership violation."""

    path: str
    message: str


@dataclass  # noqa: dataclass
class PackageScan:
    """Scan result for a single directory under ``anvil/``."""

    dirpath: str
    violations: list[InitPyViolation] = field(default_factory=list)


def _has_py_files(dirpath: Path) -> bool:
    """Check if *dirpath* contains any ``.py`` files (non-recursive).

    Parameters
    ----------
    dirpath : pathlib.Path
        Directory to inspect.

    Returns
    -------
    bool
        ``True`` if at least one ``.py`` file exists directly inside.
    """
    try:
        for entry in dirpath.iterdir():
            if entry.is_file() and entry.suffix == ".py":
                return True
        return False
    except PermissionError:
        return False


def _is_data_dir(dirpath: Path) -> bool:
    """Check if *dirpath* or any ancestor is a known data-only directory.

    A directory is considered data-only if its own name or the name of any
    ancestor directory is in the ``_DATA_DIRS`` set.  This prevents false
    positives for nested directories under ``data/``, ``_resources/``, etc.
    that contain ``.py`` files as demo samples rather than importable code.

    Parameters
    ----------
    dirpath : pathlib.Path
        Directory path to check (basename and ancestors are examined).

    Returns
    -------
    bool
    """
    return any(
        parent.name in _DATA_DIRS for parent in [dirpath, *list(dirpath.parents)]
    )


def _init_py_is_bare(init_path: Path) -> bool:
    """Check if an ``__init__.py`` file is bare (docstring-only, no imports).

    A bare ``__init__.py`` may contain:
    - A copyright header (comment lines)
    - A single module docstring (triple-quoted string)
    - Blank lines

    It MUST NOT contain:
    - Any ``import`` or ``from ... import`` statement
    - Any assignment, function, or class definitions

    Parameters
    ----------
    init_path : pathlib.Path
        Path to the ``__init__.py`` file.

    Returns
    -------
    bool
        ``True`` if the file is bare, ``False`` if it contains
        imports or re-exports.
    """
    try:
        source = init_path.read_text()
    except OSError:
        return False

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False

    for node in tree.body:
        # Allow docstrings (module-level Expr with a constant string value)
        if isinstance(node, ast.Expr) and isinstance(
            getattr(node, "value", None), ast.Constant
        ):
            continue
        # Allow comment lines are stripped by the parser — nothing to skip
        # Blank lines are also stripped — nothing to skip

        # Anything else (import, from-import, assign, def, class) is non-bare
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            return False
        if isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Assign),
        ):
            return False

    return True


def scan_directory(root: Path) -> list[PackageScan]:
    """Recursively scan all subdirectories under *root* for violations.

    Parameters
    ----------
    root : pathlib.Path
        Root directory to scan (typically ``anvil/``).

    Returns
    -------
    list of PackageScan
        One entry per visited subdirectory, containing any violations found.
    """
    results: list[PackageScan] = []

    for dirpath in sorted(root.rglob("*")):
        if not dirpath.is_dir():
            continue

        dirname = dirpath.name
        init_path = dirpath / "__init__.py"
        has_py = _has_py_files(dirpath)
        is_data = _is_data_dir(dirpath)

        scan = PackageScan(str(dirpath))

        if is_data:
            # Data directories MUST NOT have __init__.py
            if init_path.exists():
                scan.violations.append(
                    InitPyViolation(
                        str(dirpath),
                        f"Data-only directory '{dirname}' must not contain "
                        f"__init__.py",
                    )
                )
        elif has_py:
            # Authoritative package level: MUST have bare __init__.py
            if not init_path.exists():
                scan.violations.append(
                    InitPyViolation(
                        str(dirpath),
                        f"Missing __init__.py in package directory " f"'{dirpath}'",
                    )
                )
            elif not _init_py_is_bare(init_path):
                scan.violations.append(
                    InitPyViolation(
                        str(dirpath),
                        f"__init__.py in '{dirpath}' contains imports or "
                        f"re-exports; must be docstring-only",
                    )
                )

        if scan.violations:
            results.append(scan)

    return results


def main() -> None:
    """CLI entry point.

    Reads ``ANVIL_ROOT`` (defaults to ``anvil``) and scans for
    ``__init__.py`` ownership violations. Exits 0 if clean, 1 otherwise.
    """
    root = Path(os.environ.get("ANVIL_ROOT", "anvil"))
    if not root.exists():
        root = Path("anvil")
    if not root.exists():
        print(f"ERROR: source directory {root} not found")
        sys.exit(1)

    scans = scan_directory(root)
    total_violations = 0

    for scan in scans:
        for violation in scan.violations:
            print(f"ERROR: {violation.path}: {violation.message}")
            total_violations += 1

    if total_violations:
        print(f"\n{total_violations} __init__.py ownership violation(s) found.")
        sys.exit(1)
    else:
        print("OK: All packages have valid __init__.py files.")
        sys.exit(0)


if __name__ == "__main__":
    main()
