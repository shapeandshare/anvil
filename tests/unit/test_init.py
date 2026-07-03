# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for ``anvil/__init__.py``.

Tests cover:
- ``__version__`` is a non-empty string matching pyproject.toml
- Private module constants (``_ROOT``, ``_PYPROJECT_TOML``)
- Fallback path when ``pyproject.toml`` is absent (importlib.metadata)
"""

from __future__ import annotations

import importlib
import re
import tomllib
from pathlib import Path
from unittest.mock import patch

import pytest

# Regex matching PEP 440 / semver-like version strings.
_VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+(?:[ab]|rc\d+)?(?:\.dev\d+)?$")


def _pyproject_version() -> str:
    """Read ``__version__`` from ``pyproject.toml`` for comparison."""
    _root = Path(__file__).resolve().parent.parent.parent
    _pyproject = _root / "pyproject.toml"
    with open(_pyproject, "rb") as _f:
        return tomllib.load(_f)["project"]["version"]


####################################################################
# Happy path — pyproject.toml exists
####################################################################


def test_version_is_nonempty_string():
    """``__version__`` should be a non-empty string."""
    import anvil

    assert isinstance(anvil.__version__, str)
    assert len(anvil.__version__) > 0


def test_version_matches_pyproject():
    """``__version__`` should equal the value in ``pyproject.toml``."""
    import anvil

    expected = _pyproject_version()
    assert anvil.__version__ == expected


def test_version_format():
    """``__version__`` should match PEP 440 / semver format."""
    import anvil

    assert _VERSION_PATTERN.match(
        anvil.__version__
    ), f"__version__={anvil.__version__!r} does not match {_VERSION_PATTERN.pattern}"


def test_version_has_root_and_pyproject():
    """Private module constants should have correct types."""
    import anvil

    assert hasattr(anvil, "_ROOT")
    assert isinstance(anvil._ROOT, Path)
    assert anvil._ROOT.exists()
    assert anvil._ROOT.is_dir()

    assert hasattr(anvil, "_PYPROJECT_TOML")
    assert isinstance(anvil._PYPROJECT_TOML, Path)
    assert anvil._PYPROJECT_TOML.exists()
    assert anvil._PYPROJECT_TOML.is_file()
    assert anvil._PYPROJECT_TOML.name == "pyproject.toml"


####################################################################
# Fallback path — pyproject.toml absent
####################################################################


def test_version_fallback_uses_importlib_metadata():
    """When ``pyproject.toml`` is absent, ``__version__`` falls back to
    ``importlib.metadata.version("anvil")``."""
    import importlib.metadata

    expected = importlib.metadata.version("anvil")

    # Reload the module with all Path.exists() returning False to simulate
    # absence of pyproject.toml, triggering the importlib.metadata fallback.
    with patch("pathlib.Path.exists", return_value=False):
        import anvil  # noqa: F811 — reimport under the patch

        importlib.reload(anvil)

    try:
        assert isinstance(anvil.__version__, str)
        assert len(anvil.__version__) > 0
        assert anvil.__version__ == expected
    finally:
        importlib.reload(anvil)
