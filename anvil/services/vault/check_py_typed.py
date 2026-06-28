# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""PEP 561 ``py.typed`` marker checker.

Verifies that the ``anvil/py.typed`` marker file (PEP 561) exists, is zero
bytes, and is correctly listed in ``[tool.setuptools.package-data]`` in
``pyproject.toml``.

Exits 0 if all checks pass, 1 if any violation is found.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

try:
    import tomllib
except ImportError:  # pragma: no cover (Python <3.11)
    import tomli as tomllib  # type: ignore[no-redef]


_REPO_ROOT_HINT = "Set ANVIL_REPO_ROOT or run from the repo root."


def _resolve_repo_root(arg_root: str | None) -> Path:
    """Resolve the repository root directory.

    Priority: explicit argument > ``ANVIL_REPO_ROOT`` env var > CWD.

    Parameters
    ----------
    arg_root : str or None
        Explicit path passed via CLI.

    Returns
    -------
    pathlib.Path
        Resolved absolute repository root.

    Raises
    ------
    SystemExit
        If no root can be determined.
    """
    if arg_root:
        return Path(arg_root).resolve(strict=True)

    env_root = os.environ.get("ANVIL_REPO_ROOT")
    if env_root:
        return Path(env_root).resolve(strict=True)

    return Path.cwd().resolve()


def check_py_typed_exists(repo_root: Path) -> str | None:
    """Check that ``anvil/py.typed`` exists.

    Parameters
    ----------
    repo_root : pathlib.Path
        Repository root directory.

    Returns
    -------
    str or None
        Error message if missing, ``None`` if OK.
    """
    py_typed = repo_root / "anvil" / "py.typed"
    if not py_typed.exists():
        return f"ERROR: anvil/py.typed not found ({_REPO_ROOT_HINT})"
    return None


def check_py_typed_empty(repo_root: Path) -> str | None:
    """Check that ``anvil/py.typed`` is zero bytes.

    Parameters
    ----------
    repo_root : pathlib.Path
        Repository root directory.

    Returns
    -------
    str or None
        Error message if non-empty, ``None`` if OK.
    """
    py_typed = repo_root / "anvil" / "py.typed"
    size = py_typed.stat().st_size
    if size != 0:
        return f"ERROR: anvil/py.typed is not empty (size: {size} bytes)"
    return None


def check_package_data_configured(repo_root: Path) -> str | None:
    """Check that ``py.typed`` is listed in ``[tool.setuptools.package-data]``.

    Parameters
    ----------
    repo_root : pathlib.Path
        Repository root directory.

    Returns
    -------
    str or None
        Error message if not configured, ``None`` if OK.
    """
    pyproject = repo_root / "pyproject.toml"
    if not pyproject.exists():
        return f"ERROR: pyproject.toml not found at {pyproject}"

    try:
        data = tomllib.loads(pyproject.read_text())
    except Exception as exc:  # noqa: BLE001
        return f"ERROR: failed to parse pyproject.toml: {exc}"

    try:
        package_data = data["tool"]["setuptools"]["package-data"]
    except KeyError:
        return "ERROR: [tool.setuptools.package-data] not found in pyproject.toml"

    anvil_entry = package_data.get("anvil", [])
    if "py.typed" not in anvil_entry:
        return "ERROR: py.typed not listed in [tool.setuptools.package-data] in pyproject.toml"

    return None


def main(argv: list[str] | None = None) -> None:
    """CLI entry point for the py.typed marker checker.

    Parameters
    ----------
    argv : list of str or None
        Command-line arguments. First positional arg is the repo root path.
        Defaults to ``None`` (reads from current directory).
    """
    args = argv or []
    repo_root = _resolve_repo_root(args[0] if args else None)

    errors: list[str] = []

    exists_error = check_py_typed_exists(repo_root)
    if exists_error:
        errors.append(exists_error)
    else:
        empty_error = check_py_typed_empty(repo_root)
        if empty_error:
            errors.append(empty_error)

    config_error = check_package_data_configured(repo_root)
    if config_error:
        errors.append(config_error)

    for err in errors:
        print(err)

    if errors:
        sys.exit(1)

    print("OK: py.typed marker is present and configured.")
    sys.exit(0)


if __name__ == "__main__":
    main()
