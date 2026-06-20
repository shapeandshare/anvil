"""e2e setup test."""

import tomllib
from pathlib import Path


def test_import_anvil():
    import anvil

    _root = Path(__file__).resolve().parent.parent.parent
    _pyproject = _root / "pyproject.toml"
    with open(_pyproject, "rb") as _f:
        expected = tomllib.load(_f)["project"]["version"]

    assert anvil.__version__ == expected


def test_import_core():
    from anvil.core import engine

    assert engine is not None
