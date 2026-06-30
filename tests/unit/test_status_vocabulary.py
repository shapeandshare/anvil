# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Test that no legacy status vocabulary remains in Python source files."""

from pathlib import Path

# Allow-listed files that use "completed" / "pending" as part of the new
# ComputeStatus enum (see anvil/services/compute/result.py).
_ALLOWED_FILES: set[str] = {
    "result.py",
    "compute_status.py",
    "demo_model_provider.py",
    "model_asset.py",
    "backup_status.py",
    "cli.py",
}


def _iter_py_files(root: Path):
    for p in root.rglob("*.py"):
        rel = p.relative_to(root)
        parts = rel.parts
        if parts[0] in ("tests", "migrations"):
            continue
        if ".venv" in parts:
            continue
        if parts[-1] in _ALLOWED_FILES:
            continue
        yield p


def test_no_completed_status_in_py_source():
    root = Path(__file__).resolve().parent.parent.parent
    pkg_root = root / "anvil"
    hits = []
    for p in _iter_py_files(pkg_root):
        text = p.read_text()
        for i, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if '"completed"' in stripped or "'completed'" in stripped:
                hits.append((p, i, stripped))
    assert not hits, f"Found 'completed' status literals: {hits}"


def test_no_pending_status_in_py_source():
    root = Path(__file__).resolve().parent.parent.parent
    pkg_root = root / "anvil"
    hits = []
    for p in _iter_py_files(pkg_root):
        text = p.read_text()
        for i, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if '"pending"' in stripped or "'pending'" in stripped:
                hits.append((p, i, stripped))
    assert not hits, f"Found 'pending' status literals: {hits}"
