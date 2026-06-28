# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""One-class-per-file checker: flags files with multiple top-level classes.

Enforces the constitutional constraint (Article X): every ``.py`` file under
``anvil/`` MUST contain exactly one class definition, unless the additional
classes are allowed companions (enums, exceptions, or suppressed via
inline comment).

Scans all ``.py`` files under ``anvil/``. Exits 0 if no violations,
1 if any file has multiple non-companion classes.
"""

from __future__ import annotations

import ast
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass  # noqa: dataclass
class OneClassIssue:
    """A violation: file contains multiple non-companion classes."""

    file: str
    classes: list[str]
    message: str


@dataclass  # noqa: dataclass
class ScanResult:
    """Aggregated scan result for a single file."""

    path: str
    issues: list[OneClassIssue] = field(default_factory=list)


def _has_suppression(source: str) -> bool:
    """Check if the source file has a ``# one-class:allow`` suppression.

    Parameters
    ----------
    source : str
        File source code.

    Returns
    -------
    bool
        True if suppression comment found in the first 5 lines.
    """
    for line in source.splitlines()[:5]:
        stripped = line.strip()
        if stripped.startswith("#") and "one-class:allow" in stripped:
            return True
    return False


def _is_enum_class(node: ast.ClassDef) -> bool:
    """Check if a class definition inherits from ``enum.Enum``.

    Parameters
    ----------
    node : ast.ClassDef
        The class definition node.

    Returns
    -------
    bool
        True if the class inherits from ``Enum``.
    """
    for base in node.bases:
        if isinstance(base, ast.Name) and base.id == "Enum":
            return True
        if isinstance(base, ast.Attribute) and base.attr == "Enum":
            return True
    return False


def _is_exception_class(node: ast.ClassDef) -> bool:
    """Check if a class definition inherits from ``Exception``.

    Parameters
    ----------
    node : ast.ClassDef
        The class definition node.

    Returns
    -------
    bool
        True if the class inherits from ``Exception``.
    """
    for base in node.bases:
        if isinstance(base, ast.Name) and base.id == "Exception":
            return True
        if isinstance(base, ast.Attribute) and base.attr == "Exception":
            return True
    return False


def scan_file(filepath: Path) -> ScanResult:
    """Scan a single Python file for one-class-per-file violations.

    Parameters
    ----------
    filepath : pathlib.Path
        Path to the Python file.

    Returns
    -------
    ScanResult
    """
    result = ScanResult(str(filepath))

    try:
        source = filepath.read_text()
    except OSError as e:
        result.issues.append(
            OneClassIssue(str(filepath), [], f"Cannot read: {e}")
        )
        return result

    if _has_suppression(source):
        return result

    try:
        tree = ast.parse(source, filename=str(filepath))
    except SyntaxError as e:
        result.issues.append(
            OneClassIssue(str(filepath), [], f"Cannot parse: {e}")
        )
        return result

    top_level_classes: list[ast.ClassDef] = [
        node for node in tree.body if isinstance(node, ast.ClassDef)
    ]

    if len(top_level_classes) <= 1:
        return result

    companion_names: list[str] = []
    primary_names: list[str] = []

    for node in top_level_classes:
        if _is_enum_class(node) or _is_exception_class(node):
            companion_names.append(node.name)
        else:
            primary_names.append(node.name)

    if len(primary_names) <= 1:
        return result

    all_names = [c.name for c in top_level_classes]
    result.issues.append(
        OneClassIssue(
            str(filepath),
            all_names,
            f"has {len(all_names)} classes: {all_names}",
        )
    )

    return result


def scan_directory(root: Path) -> list[ScanResult]:
    """Recursively scan all ``.py`` files under *root*.

    Parameters
    ----------
    root : pathlib.Path
        Directory to scan.

    Returns
    -------
    list of ScanResult
    """
    results: list[ScanResult] = []
    for pyfile in sorted(root.rglob("*.py")):
        results.append(scan_file(pyfile))
    return results


def main() -> None:
    """CLI entry point."""
    root = Path(os.environ.get("ANVIL_ROOT", "anvil"))
    if not root.exists():
        root = Path("anvil")
    if not root.exists():
        print(f"ERROR: source directory {root} not found")
        sys.exit(1)

    results = scan_directory(root)
    total_issues = 0
    for r in results:
        if r.issues:
            for issue in r.issues:
                print(f"ERROR: {issue.file} {issue.message}")
                total_issues += 1

    if total_issues:
        print(f"\n{total_issues} one-class-per-file violation(s) found.")
        sys.exit(1)
    else:
        print("OK: All files have one class per file.")
        sys.exit(0)


if __name__ == "__main__":
    main()