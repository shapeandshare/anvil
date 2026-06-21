# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

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
