# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Import-placement checker: flags imports that appear after module-level
class/function definitions.

Enforces the architecture rule that imports must be at the top of the
file. Lazy/conditional imports inside function/method bodies are allowed
ONLY for runtime capability detection (e.g., platform-specific GPU
support, optional dependency probing).

Scans all ``.py`` files under ``anvil/``. Exits 0 if no violations,
1 if any lazy import is found outside an allowlisted context.
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass  # noqa: dataclass
class LazyImport:
    """A lazy import found after the first module-level definition."""

    statement: str
    file: str
    line: int


@dataclass  # noqa: dataclass
class ScanResult:
    """Aggregated scan result for a single file."""

    path: str
    violations: list[LazyImport] = field(default_factory=list)


# Regex for import statements
_IMPORT_RE = re.compile(r"^\s*(import\s+|from\s+\S+\s+import\s+)")

# Regex patterns that open allowlisted blocks at module level
_TRY_RE = re.compile(r"^\s*try\s*:")
_EXCEPT_IMPORT_ERROR_RE = re.compile(r"^\s*except\s+ImportError\b")
_EXCEPT_RE = re.compile(r"^\s*except\b")
_TYPE_CHECKING_RE = re.compile(r"^\s*if\s+TYPE_CHECKING\s*:")
_PLATFORM_COND_RE = re.compile(
    r"^\s*if\s+.*\b(?:sys\.platform|platform\.system|platform\.machine"
    r"|importlib\.util\.find_spec)\b.*:"
)


def _calc_indent(line: str) -> int:
    """Return the indent level (number of leading spaces) of *line*."""
    return len(line) - len(line.lstrip())


def _scan_source_for_imports(source: str, filepath: str) -> list[LazyImport]:
    """Scan *source* for lazy imports after the first module-level definition.

    Parameters
    ----------
    source : str
        File source code.
    filepath : str
        File path (for error attribution).

    Returns
    -------
    list of LazyImport
    """
    violations: list[LazyImport] = []
    lines = source.splitlines()

    # Find the first module-level class/function definition (indent 0,
    # excluding imports, comments, and blank lines).
    first_def_lineno: int | None = None
    for i, raw in enumerate(lines):
        line = raw.strip()
        indent = _calc_indent(raw)

        # Skip blank, comment, and import lines
        if not line or line.startswith("#") or _IMPORT_RE.match(raw):
            continue

        if indent == 0 and (
            line.startswith("def ")
            or line.startswith("class ")
            or line.startswith("async def ")
            or line.startswith("@")
        ):
            first_def_lineno = i + 1
            break

    if first_def_lineno is None:
        return violations  # No definitions — all imports are top-of-file

    # Stateful scan from the definition line onward to find lazy imports
    # and determine whether they sit inside an allowlisted block.
    #
    # We maintain a stack of block contexts keyed by indent level.
    # Each entry: (indent_of_opener, kind)
    # where kind is: "try", "import_error", "type_checking", "platform"
    context_stack: list[tuple[int, str]] = []
    suppress = False

    for lineno, raw in enumerate(lines, 1):
        if lineno < first_def_lineno:
            continue

        line = raw.strip()
        indent = _calc_indent(raw)

        # --- Suppression check ---
        # If the *previous* line had a suppression comment, allow the next
        # import regardless of context.
        if suppress:
            if _IMPORT_RE.match(raw):
                suppress = False
                continue
            suppress = False

        if "# import-placement:allow" in raw:
            suppress = True
            continue

        # --- Pop contexts that no longer apply (indent returned to or
        #     below the opener's indent) ---
        while context_stack and indent <= context_stack[-1][0]:
            context_stack.pop()

        # --- Open new contexts (only at the sub-indent level that
        #     follows the opener, or at indent 0 for top-level blocks) ---
        if _TRY_RE.match(raw):
            context_stack.append((indent, "try"))
        elif _EXCEPT_IMPORT_ERROR_RE.match(raw):
            # This replaces the current try context (same indent level)
            # with an import_error context.  Pop any try at the same indent.
            while context_stack and context_stack[-1][0] >= indent:
                context_stack.pop()
            context_stack.append((indent, "import_error"))
        elif _EXCEPT_RE.match(raw):
            # A generic except closes the try/import-error context at this
            # indent level.
            while context_stack and context_stack[-1][0] >= indent:
                context_stack.pop()
        elif _TYPE_CHECKING_RE.match(raw):
            context_stack.append((indent, "type_checking"))
        elif _PLATFORM_COND_RE.match(raw):
            context_stack.append((indent, "platform"))

        # --- Check import lines ---
        if _IMPORT_RE.match(raw):
            # Determine if we are inside an allowlisted context
            allowed = any(
                kind in ("try", "import_error", "type_checking", "platform")
                for _, kind in context_stack
            )
            if not allowed:
                violations.append(LazyImport(line.strip(), filepath, lineno))

    return violations


def scan_file(filepath: Path) -> ScanResult:
    """Scan a single Python file for import-placement violations.

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
        # Treat unreadable as a violation to surface the issue
        result.violations.append(LazyImport(f"(cannot read: {e})", str(filepath), 0))
        return result

    result.violations = _scan_source_for_imports(source, str(filepath))
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
            print(f"ERROR: {v.file}:{v.line} lazy import: {v.statement}")
            total_violations += 1

    if total_violations:
        print(f"\n{total_violations} lazy import(s) found.")
        sys.exit(1)
    else:
        print("OK: All imports are at top of file.")
        sys.exit(0)


if __name__ == "__main__":
    main()
