# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Core dependency checker — enforces Constitution Article I.

The ``anvil/core/`` package MUST have zero third-party Python
dependencies. Every top-level ``import`` and ``from ... import``
statement must resolve to either:

- A stdlib module (``sys.stdlib_module_names``)
- The compiler directive ``from __future__ import annotations``
- An intra-package import (relative or ``anvil.*``)

Imports inside ``if TYPE_CHECKING:`` guards are excluded from
the check (they are conditional, not runtime dependencies).
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Hardcoded fallback for Python < 3.10 where
# ``sys.stdlib_module_names`` is not available.
_STDLIB_FALLBACK: frozenset[str] = frozenset(
    {
        "__future__",
        "_thread",
        "abc",
        "aifc",
        "argparse",
        "array",
        "ast",
        "asynchat",
        "asyncio",
        "asyncore",
        "atexit",
        "audioop",
        "base64",
        "bdb",
        "binascii",
        "binhex",
        "bisect",
        "builtins",
        "bz2",
        "calendar",
        "cgi",
        "cgitb",
        "chunk",
        "cmath",
        "cmd",
        "code",
        "codecs",
        "codeop",
        "collections",
        "colorsys",
        "compileall",
        "concurrent",
        "configparser",
        "contextlib",
        "contextvars",
        "copy",
        "copyreg",
        "cProfile",
        "crypt",
        "csv",
        "ctypes",
        "curses",
        "dataclasses",
        "datetime",
        "dbm",
        "decimal",
        "difflib",
        "dis",
        "distutils",
        "doctest",
        "email",
        "encodings",
        "enum",
        "errno",
        "faulthandler",
        "fcntl",
        "filecmp",
        "fileinput",
        "fnmatch",
        "fractions",
        "ftplib",
        "functools",
        "gc",
        "getopt",
        "getpass",
        "gettext",
        "glob",
        "graphlib",
        "grp",
        "gzip",
        "hashlib",
        "heapq",
        "hmac",
        "html",
        "http",
        "idlelib",
        "imaplib",
        "imghdr",
        "imp",
        "importlib",
        "inspect",
        "io",
        "ipaddress",
        "itertools",
        "json",
        "keyword",
        "lib2to3",
        "linecache",
        "locale",
        "logging",
        "lzma",
        "mailbox",
        "mailcap",
        "marshal",
        "math",
        "mimetypes",
        "mmap",
        "modulefinder",
        "multiprocessing",
        "netrc",
        "nis",
        "nntplib",
        "numbers",
        "operator",
        "optparse",
        "os",
        "ossaudiodev",
        "parser",
        "pathlib",
        "pdb",
        "pickle",
        "pickletools",
        "pipes",
        "pkgutil",
        "platform",
        "plistlib",
        "poplib",
        "posix",
        "posixpath",
        "pprint",
        "profile",
        "pstats",
        "pty",
        "pwd",
        "py_compile",
        "pyclbr",
        "pydoc",
        "queue",
        "quopri",
        "random",
        "re",
        "readline",
        "reprlib",
        "resource",
        "rlcompleter",
        "runpy",
        "sched",
        "secrets",
        "select",
        "selectors",
        "shelve",
        "shlex",
        "shutil",
        "signal",
        "site",
        "smtpd",
        "smtplib",
        "sndhdr",
        "socket",
        "socketserver",
        "sqlite3",
        "ssl",
        "stat",
        "statistics",
        "string",
        "stringprep",
        "struct",
        "subprocess",
        "sunau",
        "symtable",
        "sys",
        "sysconfig",
        "syslog",
        "tabnanny",
        "tarfile",
        "telnetlib",
        "tempfile",
        "termios",
        "test",
        "textwrap",
        "threading",
        "time",
        "timeit",
        "tkinter",
        "token",
        "tokenize",
        "tomllib",
        "trace",
        "traceback",
        "tracemalloc",
        "tty",
        "turtle",
        "turtledemo",
        "types",
        "typing",
        "unicodedata",
        "unittest",
        "urllib",
        "uu",
        "uuid",
        "venv",
        "warnings",
        "wave",
        "weakref",
        "webbrowser",
        "winreg",
        "winsound",
        "wsgiref",
        "xdrlib",
        "xml",
        "xmlrpc",
        "zipapp",
        "zipfile",
        "zipimport",
        "zlib",
    }
)

# Regex matching ``import X`` and ``from X import Y``.
# Group 1 = the module part (everything between ``from`` / ``import``
# and ``import`` / end-of-line).
_IMPORT_RE = re.compile(r"^\s*(?:from\s+(\S+)\s+import\s|import\s+(\S+))")


def _get_stdlib() -> frozenset[str]:
    """Return the set of known stdlib top-level module names.

    Prefers ``sys.stdlib_module_names`` (Python 3.10+), falling
    back to a hardcoded list.

    Returns
    -------
    frozenset of str
    """
    if hasattr(sys, "stdlib_module_names"):
        return frozenset(sys.stdlib_module_names)
    return _STDLIB_FALLBACK


def _is_intra_package(module: str) -> bool:
    """Check if *module* is an intra-package import.

    Intra-package imports are either relative (starting with ``.``)
    or reference the ``anvil`` namespace.

    Parameters
    ----------
    module : str
        The module string from an import statement (e.g. ``os.path``
        or ``.autograd``).

    Returns
    -------
    bool
    """
    return module.startswith(".") or module.split(".")[0] in ("anvil",)


def _top_level_module(module: str) -> str:
    """Extract the top-level package name from a dotted module path.

    Parameters
    ----------
    module : str
        Dotted module path, e.g. ``os.path`` or ``collections.abc``.

    Returns
    -------
    str
    """
    return module.split(".")[0]


@dataclass  # noqa: dataclass
class ImportStatement:
    """A single import statement found in source code."""

    module: str
    file: str
    line: int
    raw: str


@dataclass  # noqa: dataclass
class DepViolation:
    """A third-party dependency violation found in a file."""

    file: str
    line: int
    raw: str
    module: str


@dataclass  # noqa: dataclass
class FileCheckResult:
    """Aggregated check result for a single file."""

    path: str
    violations: list[DepViolation] = field(default_factory=list)


def _extract_imports(source: str, filepath: str) -> list[ImportStatement]:
    """Extract all top-level imports from *source*, excluding TYPE_CHECKING blocks.

    Parameters
    ----------
    source : str
        File source code.
    filepath : str
        File path for attribution.

    Returns
    -------
    list of ImportStatement
    """
    imports: list[ImportStatement] = []
    in_type_checking = False

    for i, line in enumerate(source.splitlines(), 1):
        stripped = line.strip()

        if stripped.startswith("if TYPE_CHECKING:"):
            in_type_checking = True
            continue

        if in_type_checking:
            # A non-indented line at module level exits the guard.
            # Use the raw (unstripped) line to detect indentation.
            if line and not line.startswith((" ", "\t")):
                in_type_checking = False
            else:
                continue

        m = _IMPORT_RE.match(stripped)
        if not m:
            continue

        module = (m.group(1) or m.group(2) or "").strip()
        if not module:
            continue

        imports.append(ImportStatement(module, filepath, i, stripped))

    return imports


def check_file(filepath: Path) -> FileCheckResult:
    """Check a single Python file for non-stdlib imports.

    Parameters
    ----------
    filepath : pathlib.Path
        Path to the Python file.

    Returns
    -------
    FileCheckResult
    """
    result = FileCheckResult(str(filepath))
    stdlib = _get_stdlib()

    try:
        source = filepath.read_text()
    except OSError as e:
        print(f"ERROR: cannot read {filepath}: {e}")
        return result

    imports = _extract_imports(source, str(filepath))

    for imp in imports:
        module = imp.module

        # Allow ``from __future__ import ...``
        if module == "__future__":
            continue

        # Allow intra-package imports (relative or anvil.*)
        if _is_intra_package(module):
            continue

        # Check against stdlib
        top = _top_level_module(module)
        if top not in stdlib:
            result.violations.append(
                DepViolation(
                    file=imp.file,
                    line=imp.line,
                    raw=imp.raw,
                    module=module,
                )
            )

    return result


def check_directory(root: Path) -> list[FileCheckResult]:
    """Recursively check all ``.py`` files under *root*.

    Parameters
    ----------
    root : pathlib.Path
        Directory to scan.

    Returns
    -------
    list of FileCheckResult
    """
    results: list[FileCheckResult] = []
    for pyfile in sorted(root.rglob("*.py")):
        results.append(check_file(pyfile))
    return results


def main() -> None:
    """CLI entry point.

    Scans ``anvil/core/`` (or ``ANVIL_ROOT``) for non-stdlib imports
    and reports violations. Exits 0 if clean, 1 otherwise.
    """
    root = Path(os.environ.get("ANVIL_ROOT", "anvil/core"))
    if not root.exists():
        root = Path("anvil/core")
    if not root.exists():
        print(f"ERROR: source directory {root} not found")
        sys.exit(1)

    results = check_directory(root)
    total_violations = 0

    for r in results:
        for v in r.violations:
            print(f"ERROR: {v.file}:{v.line} non-stdlib import: {v.raw}")
            total_violations += 1

    if total_violations:
        print(f"\n{total_violations} non-stdlib import(s) found in " f"anvil/core/.")
        sys.exit(1)
    else:
        print("OK: anvil/core/ has no third-party dependencies.")
        sys.exit(0)


if __name__ == "__main__":
    main()
