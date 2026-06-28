# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for ``check_py_typed`` — PEP 561 marker file checker."""

from __future__ import annotations

from pathlib import Path

from anvil.services.vault.check_py_typed import (
    check_package_data_configured,
    check_py_typed_empty,
    check_py_typed_exists,
)


class TestCheckPyTyped:
    """Tests for py.typed marker file checks."""

    def test_py_typed_exists_and_empty(self, tmp_path: Path) -> None:
        """``check_py_typed_exists`` and ``check_py_typed_empty`` pass when
        ``anvil/py.typed`` exists and is zero bytes.
        """
        anvil_dir = tmp_path / "anvil"
        anvil_dir.mkdir(parents=True)
        py_typed = anvil_dir / "py.typed"
        py_typed.write_text("", encoding="utf-8")

        assert check_py_typed_exists(tmp_path) is None
        assert check_py_typed_empty(tmp_path) is None

    def test_py_typed_missing(self, tmp_path: Path) -> None:
        """``check_py_typed_exists`` returns an error when ``anvil/py.typed``
        does not exist.
        """
        anvil_dir = tmp_path / "anvil"
        anvil_dir.mkdir(parents=True)

        result = check_py_typed_exists(tmp_path)
        assert result is not None
        assert "py.typed not found" in result

    def test_py_typed_not_empty(self, tmp_path: Path) -> None:
        """``check_py_typed_empty`` returns an error when ``anvil/py.typed``
        has content.
        """
        anvil_dir = tmp_path / "anvil"
        anvil_dir.mkdir(parents=True)
        py_typed = anvil_dir / "py.typed"
        py_typed.write_text("# marker file\n", encoding="utf-8")

        assert check_py_typed_exists(tmp_path) is None
        result = check_py_typed_empty(tmp_path)
        assert result is not None
        assert "not empty" in result

    def test_py_typed_in_package_data(self, tmp_path: Path) -> None:
        """``check_package_data_configured`` passes when
        ``[tool.setuptools.package-data]`` lists ``py.typed``.
        """
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            "[tool.setuptools.package-data]\nanvil = [\"py.typed\"]\n",
            encoding="utf-8",
        )

        assert check_package_data_configured(tmp_path) is None

    def test_py_typed_not_in_package_data(self, tmp_path: Path) -> None:
        """``check_package_data_configured`` returns an error when
        ``py.typed`` is not listed under ``[tool.setuptools.package-data]``.
        """
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            "[tool.setuptools.package-data]\nanvil = []\n",
            encoding="utf-8",
        )

        result = check_package_data_configured(tmp_path)
        assert result is not None
        assert "py.typed not listed" in result

    def test_pyproject_toml_missing(self, tmp_path: Path) -> None:
        """``check_package_data_configured`` returns an error when
        ``pyproject.toml`` does not exist.
        """
        result = check_package_data_configured(tmp_path)
        assert result is not None
        assert "pyproject.toml not found" in result

    def test_both_ok(self, tmp_path: Path) -> None:
        """All three checks pass when ``py.typed`` exists, is empty, and is
        listed in package-data.
        """
        anvil_dir = tmp_path / "anvil"
        anvil_dir.mkdir(parents=True)
        py_typed = anvil_dir / "py.typed"
        py_typed.write_text("", encoding="utf-8")

        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            "[tool.setuptools.package-data]\nanvil = [\"py.typed\"]\n",
            encoding="utf-8",
        )

        assert check_py_typed_exists(tmp_path) is None
        assert check_py_typed_empty(tmp_path) is None
        assert check_package_data_configured(tmp_path) is None
