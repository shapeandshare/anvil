# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""pytest configuration and fixtures for vault health tests."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def test_vault_dir() -> Path:
    """Return the path to the test vault directory.

    Returns
    -------
    Path
        Absolute path to ``tests/services/vault/test_vault/``.
    """
    return Path(__file__).resolve().parent / "test_vault"
