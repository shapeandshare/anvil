# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Guarded-imports checker: flags TYPE_CHECKING-guarded symbols used in runtime code.

Enforces the constitutional exception discipline (FR-022):
Condition (c) — guarded symbols MUST be referenced only in annotations,
never in runtime code.

Scans all ``.py`` files under ``anvil/``. Exits 0 if no violations,
1 if any guarded symbol is used outside a type annotation context.
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class GuardedImport:
    """A single TYPE_CHECKING-guarded import statement."""

    symbol: str
    file: str
    line: int


@dataclass
class GuardedImportIssue:
    """A violation: guarded symbol used in runtime (non-annotation) code."""

    symbol: str
    file: str
    line: int
    message: str


@dataclass
class ScanResult:
    """Aggregated scan result for a single file."""

    path: str
    imports: list[GuardedImport] = field(default_factory=list)
    issues: list[GuardedImportIssue] = field(default_factory=list)
    has_future_annotations: bool = False


# Regex to extract symbol names from import-like lines within
# ``if TYPE_CHECKING:`` blocks.
_GUARDED_IMPORT_RE = re.compile(
    r"^\s*(?:from\s+(\.?\S+)\s+import\s+(.+)|import\s+(.+))"
)


def _extract_guarded_imports(source: str, filepath: str) -> list[GuardedImport]:
    """Extract ``TYPE_CHECKING``-guarded import symbols from source.

    Parameters
    ----------
    source : str
        File source code.
    filepath : str
        File path (for error attribution).

    Returns
    -------
    list of GuardedImport
    """
    imports: list[GuardedImport] = []
    in_guard = False

    for i, line in enumerate(source.splitlines(), 1):
        stripped = line.strip()

        if stripped.startswith("if TYPE_CHECKING:"):
            in_guard = True
            continue

        if not in_guard:
            continue

        # Skip blank and comment lines within the guard
        if stripped == "" or stripped.startswith("#"):
            continue

        # Exit guard on any non-indented line (back to module level)
        if stripped and not stripped.startswith((" ", "\t")):
            in_guard = False
            continue

        # Only process imports still inside the guard block
        m = _GUARDED_IMPORT_RE.match(stripped)
        if m:
            names_part = m.group(2) or m.group(3) or ""
            for name in names_part.split(","):
                name = name.strip()
                if " as " in name:
                    name = name.split(" as ")[-1].strip()
                if name:
                    imports.append(GuardedImport(name, filepath, i))

    return imports


def _find_runtime_usages(
    source: str, symbols: set[str], filepath: str
) -> list[GuardedImportIssue]:
    """Find usages of guarded symbols outside of annotations.

    A symbol is considered "annotation-only" if it only appears in:
    - Type annotations (function/attribute return/value types)
    - ``Mapped[...]``, ``list[...]``, ``Optional[...]``, etc.
    - ``cast(...)`` targets

    A symbol is "runtime" if it appears in:
    - Instantiation: ``SomeClass()``
    - Function calls: ``SomeClass.method()``
    - Value usage: ``x = SomeClass``
    - Any non-annotation expression that isn't inside a string annotation

    Parameters
    ----------
    source : str
        File source code.
    symbols : set of str
        Guarded symbol names to check.
    filepath : str
        File path for attribution.

    Returns
    -------
    list of GuardedImportIssue
    """
    issues: list[GuardedImportIssue] = []
    has_future_annotations = "from __future__ import annotations" in source

    for i, line in enumerate(source.splitlines(), 1):
        stripped = line.strip()

        for sym in symbols:
            if sym not in stripped:
                continue

            # Skip comment lines
            if stripped.startswith("#"):
                continue

            # Skip import lines
            if stripped.startswith("import ") or stripped.startswith("from "):
                continue

            # Skip lines that are purely annotation definitions
            # Pattern: "    x: SomeClass | None = None"
            # Pattern: "    def foo(bar: SomeClass) -> SomeClass:"
            in_annotation = re.search(
                rf":\s*[^=]*\b{re.escape(sym)}\b", stripped
            ) or re.search(rf"->\s*[^:]*\b{re.escape(sym)}\b", stripped)

            if in_annotation and has_future_annotations:
                continue  # Safe — annotations are deferred

            if not has_future_annotations and in_annotation:
                pass  # Without __future__, annotations ARE runtime — flag it

            # This is a real runtime usage
            if sym in stripped and not (in_annotation and has_future_annotations):
                issues.append(
                    GuardedImportIssue(
                        symbol=sym,
                        file=filepath,
                        line=i,
                        message=(
                            f"Guarded symbol '{sym}' used in runtime code "
                            f"on line {i} of {filepath}. "
                            f"Move to a normal top-level import or use "
                            f"only in annotations (requires "
                            f"``from __future__ import annotations``)."
                        ),
                    )
                )

    return issues


def scan_file(filepath: Path) -> ScanResult:
    """Scan a single Python file for guarded-import violations.

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
            GuardedImportIssue("", str(filepath), 0, f"Cannot read: {e}")
        )
        return result

    result.has_future_annotations = "from __future__ import annotations" in source
    result.imports = _extract_guarded_imports(source, str(filepath))

    if result.imports:
        guarded_symbols = {imp.symbol for imp in result.imports}
        result.issues = _find_runtime_usages(source, guarded_symbols, str(filepath))

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
                print(f"ERROR: {issue.message}")
                total_issues += 1
        if r.imports and not r.issues:
            # Annotation-only guarded imports — valid under the exception
            pass

    if total_issues:
        print(f"\n{total_issues} guarded-import violation(s) found.")
        sys.exit(1)
    else:
        print("OK: No guarded-import violations found.")
        sys.exit(0)


if __name__ == "__main__":
    main()
