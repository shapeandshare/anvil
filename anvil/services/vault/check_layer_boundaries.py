# one-class:allow — ScanResult/result types are tightly coupled to the checker
# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Layer-boundary checker: flags cross-layer import violations.

Enforces Constitution Article VII and AGENTS.md Principle 5 (Layer
Discipline). The architecture layers are:

- Repositories (``anvil/db/repositories/``) → DB access only
- ORM Models (``anvil/db/models/``) → DB models only
- Services (``anvil/services/``) → consume repositories, business logic
- God Class (``AnvilWorkbench``) → exposes all services
- Routes (``anvil/api/v1/``) → call god class only
- Core (``anvil/core/``) → zero deps, stdlib only

Forbidden imports:
- Routes importing repositories, models, or services directly
- Services importing from ``anvil.api``
- Repositories importing from services or api
- Core importing any ``anvil.`` subpackage
- Models importing from services, api, or repositories

Scans all ``.py`` files under ``anvil/``. Exits 0 if no violations,
1 if any layer boundary is crossed.
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass  # noqa: dataclass
class LayerViolation:
    """A single layer boundary violation.

    Attributes
    ----------
    file : str
        File path where the violation was found.
    line : int
        Line number of the violating import.
    layer : str
        Layer name of the source file.
    target : str
        Forbidden import target that was matched.
    message : str
        Human-readable violation description.
    """

    file: str
    line: int
    layer: str
    target: str
    message: str


@dataclass  # noqa: dataclass
class ScanResult:
    """Aggregated scan result for a single file.

    Attributes
    ----------
    path : str
        File path.
    layer : str or None
        Detected layer name, or None if the file is outside known layers.
    issues : list of LayerViolation
        Any violations found in this file.
    """

    path: str
    layer: str | None = None
    issues: list[LayerViolation] = field(default_factory=list)


# Layer definitions: path prefix → layer name.
# Order matters: more specific prefixes must come first.
_LAYER_PREFIXES: list[tuple[str, str]] = [
    ("anvil/api/v1/", "routes"),
    ("anvil/db/repositories/", "repositories"),
    ("anvil/db/models/", "models"),
    ("anvil/services/", "services"),
    ("anvil/core/", "core"),
]

# Forbidden import targets per layer (dotted module prefixes).
# An import that starts with or equals a listed prefix is a violation.
_FORBIDDEN_TARGETS: dict[str, list[str]] = {
    "routes": [
        "anvil.db.repositories",
        "anvil.db.models",
        "anvil.services",
    ],
    "services": [
        "anvil.api",
    ],
    "repositories": [
        "anvil.services",
        "anvil.api",
    ],
    "core": [
        "anvil.",
    ],
    "models": [
        "anvil.services",
        "anvil.api",
        "anvil.db.repositories",
    ],
}

# Regex to extract the imported module from ``import X`` or ``from X import Y``.
_IMPORT_RE = re.compile(r"^\s*(?:import\s+(\S+)|from\s+(\S+)\s+import\s+)")


def _classify_file(filepath: str) -> str | None:
    """Determine the layer of a file based on its path.

    Parameters
    ----------
    filepath : str
        Relative file path (e.g. ``anvil/api/v1/routes.py``).

    Returns
    -------
    str or None
        Layer name or None if the file is not in a recognised layer.
    """
    for prefix, layer in _LAYER_PREFIXES:
        if filepath.startswith(prefix):
            return layer
    return None


def _check_imports(source: str, filepath: str, layer: str) -> list[LayerViolation]:
    """Check all import lines against forbidden targets for the layer.

    Parameters
    ----------
    source : str
        File source code.
    filepath : str
        File path (for violation attribution).
    layer : str
        Layer name of the source file.

    Returns
    -------
    list of LayerViolation
    """
    issues: list[LayerViolation] = []
    forbidden = _FORBIDDEN_TARGETS.get(layer, [])

    if not forbidden:
        return issues

    for i, line in enumerate(source.splitlines(), 1):
        m = _IMPORT_RE.match(line)
        if not m:
            continue

        module = m.group(1) or m.group(2) or ""
        if not module:
            continue

        for target in forbidden:
            if module == target or module.startswith(target):
                issues.append(
                    LayerViolation(
                        file=filepath,
                        line=i,
                        layer=layer,
                        target=target,
                        message=(
                            f"ERROR: {filepath}:{i} layer violation: "
                            f"{layer} should not import {target}"
                        ),
                    )
                )

    return issues


def scan_file(filepath: Path) -> ScanResult:
    """Scan a single Python file for layer boundary violations.

    Parameters
    ----------
    filepath : pathlib.Path
        Path to the Python file.

    Returns
    -------
    ScanResult
    """
    result = ScanResult(str(filepath))
    result.layer = _classify_file(str(filepath))

    if result.layer is None:
        return result  # Not in a known layer — skip

    try:
        source = filepath.read_text()
    except OSError as e:
        result.issues.append(
            LayerViolation(str(filepath), 0, result.layer, "", f"Cannot read: {e}")
        )
        return result

    result.issues = _check_imports(source, str(filepath), result.layer)
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
                print(issue.message)
                total_issues += 1

    if total_issues:
        print(f"\n{total_issues} layer boundary violation(s) found.")
        sys.exit(1)
    else:
        print("OK: All layer boundaries are respected.")
        sys.exit(0)


if __name__ == "__main__":
    main()
