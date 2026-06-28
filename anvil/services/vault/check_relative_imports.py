# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Relative-imports checker: flags absolute ``anvil.`` imports within the package.

Enforces AGENTS.md Principle 7 — every internal import must use relative
paths (``from .module import X``, ``from ..parent.module import Y``).
Absolute ``anvil.``-prefixed imports are only valid from outside the
package (``tests/``, ``examples/``).

Scans all ``.py`` files under ``anvil/``. Exits 0 if no violations,
1 if any absolute ``anvil.`` import is found.
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass  # noqa: dataclass
class AbsoluteImport:
    """A single absolute ``anvil.`` import statement found inside the package."""

    file: str
    line: int
    line_text: str


@dataclass  # noqa: dataclass
class ScanResult:
    """Aggregated scan result for a single file."""

    path: str
    violations: list[AbsoluteImport] = field(default_factory=list)


# Pattern matching ``from anvil.`` or ``import anvil.`` at the start
# of an import statement (after optional whitespace).
_ABSOLUTE_IMPORT_RE = re.compile(r"^\s*(?:from\s+anvil\.|import\s+anvil\.)")


def _in_triple_quoted(source: str, lineno: int) -> bool:
    """Check whether *lineno* (1-indexed) is inside a triple-quoted string.

    This is an approximate check — it counts ``\"\"\"`` and ``'''``
    delimiters (both single-line and multi-line) and determines whether
    the given line falls between an opening and closing delimiter.

    Parameters
    ----------
    source : str
        File source code.
    lineno : int
        1-indexed line number to check.

    Returns
    -------
    bool
    """
    in_docstring = False
    for i, line in enumerate(source.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith(('"""', "'''")):
            in_docstring = not in_docstring
        if i >= lineno:
            break
    return in_docstring


def scan_file(filepath: Path) -> ScanResult:
    """Scan a single Python file for absolute ``anvil.`` imports.

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
    except OSError:
        return result

    in_type_checking = False

    for i, line in enumerate(source.splitlines(), 1):
        stripped = line.strip()

        # Track ``if TYPE_CHECKING:`` blocks — absolute imports are
        # permitted inside these for cycle-breaking.
        if stripped.startswith("if TYPE_CHECKING:"):
            in_type_checking = True
            continue

        if in_type_checking:
            if stripped == "" or stripped.startswith("#"):
                continue
            if stripped and not stripped.startswith((" ", "\t")):
                in_type_checking = False
            else:
                continue  # Still inside the TYPE_CHECKING block

        # Skip comments
        if stripped.startswith("#"):
            continue

        # Skip lines inside docstrings (approximate)
        if _in_triple_quoted(source, i):
            continue

        # Suppression comment on the same line
        if "# relative-imports:allow" in line:
            continue

        # Check for absolute ``anvil.`` import
        if _ABSOLUTE_IMPORT_RE.match(stripped):
            result.violations.append(
                AbsoluteImport(str(filepath), i, stripped)
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
    total_violations = 0
    for r in results:
        for v in r.violations:
            print(f"ERROR: {v.file}:{v.line} Absolute 'anvil.' import found. "
                  f"Use relative import instead: {v.line_text}")
            total_violations += 1

    if total_violations:
        print(f"\n{total_violations} absolute import violation(s) found.")
        sys.exit(1)
    else:
        print("OK: No absolute anvil. imports found.")
        sys.exit(0)


if __name__ == "__main__":
    main()