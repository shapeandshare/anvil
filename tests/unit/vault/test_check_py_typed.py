# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for the PEP 561 ``py.typed`` marker checker.

Tests ``_resolve_repo_root``, ``check_py_typed_exists``,
``check_py_typed_empty``, ``check_package_data_configured``, and
the ``main`` CLI entry point.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from anvil.services.vault.check_py_typed import (
    _resolve_repo_root,
    check_package_data_configured,
    check_py_typed_empty,
    check_py_typed_exists,
    main,
)


########################################################################
# _resolve_repo_root tests
########################################################################


class TestResolveRepoRoot:
    """Tests for the _resolve_repo_root helper."""

    def test_explicit_arg_used(self, tmp_path: Path) -> None:
        """Explicit path argument is used."""
        result = _resolve_repo_root(str(tmp_path))
        assert result == tmp_path.resolve()

    def test_env_var_used(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """ANVIL_REPO_ROOT env var is used when no argument."""
        monkeypatch.setenv("ANVIL_REPO_ROOT", str(tmp_path))
        result = _resolve_repo_root(None)
        assert result == tmp_path.resolve()

    def test_cwd_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """CWD is used when no argument or env var."""
        monkeypatch.delenv("ANVIL_REPO_ROOT", raising=False)
        result = _resolve_repo_root(None)
        assert result == Path.cwd().resolve()

    def test_explicit_overrides_env(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Explicit argument takes priority over env var."""
        monkeypatch.setenv("ANVIL_REPO_ROOT", "/nonexistent")
        result = _resolve_repo_root(str(tmp_path))
        assert result == tmp_path.resolve()


########################################################################
# check_py_typed_exists tests
########################################################################


class TestCheckPyTypedExists:
    """Tests for check_py_typed_exists."""

    def test_exists_returns_none(self, tmp_path: Path) -> None:
        """Returns None when py.typed exists."""
        anvil_dir = tmp_path / "anvil"
        anvil_dir.mkdir()
        (anvil_dir / "py.typed").write_text("")
        assert check_py_typed_exists(tmp_path) is None

    def test_missing_returns_error(self, tmp_path: Path) -> None:
        """Returns error when py.typed does not exist."""
        error = check_py_typed_exists(tmp_path)
        assert error is not None
        assert "not found" in error

    def test_missing_anvil_dir_returns_error(self, tmp_path: Path) -> None:
        """Returns error when anvil/ directory does not exist."""
        error = check_py_typed_exists(tmp_path)
        assert error is not None
        assert "not found" in error


########################################################################
# check_py_typed_empty tests
########################################################################


class TestCheckPyTypedEmpty:
    """Tests for check_py_typed_empty."""

    def test_empty_returns_none(self, tmp_path: Path) -> None:
        """Returns None when py.typed is zero bytes."""
        anvil_dir = tmp_path / "anvil"
        anvil_dir.mkdir()
        (anvil_dir / "py.typed").write_text("")
        assert check_py_typed_empty(tmp_path) is None

    def test_non_empty_returns_error(self, tmp_path: Path) -> None:
        """Returns error when py.typed has content."""
        anvil_dir = tmp_path / "anvil"
        anvil_dir.mkdir()
        (anvil_dir / "py.typed").write_text("# marker")
        error = check_py_typed_empty(tmp_path)
        assert error is not None
        assert "not empty" in error

    def test_larger_file_returns_error(self, tmp_path: Path) -> None:
        """Returns error when py.typed has multiple bytes."""
        anvil_dir = tmp_path / "anvil"
        anvil_dir.mkdir()
        (anvil_dir / "py.typed").write_text("marker file content")
        error = check_py_typed_empty(tmp_path)
        assert error is not None
        assert "size" in error


########################################################################
# check_package_data_configured tests
########################################################################


class TestCheckPackageDataConfigured:
    """Tests for check_package_data_configured."""

    def test_configured_returns_none(self, tmp_path: Path) -> None:
        """Returns None when py.typed is listed in pyproject.toml."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            "[tool.setuptools.package-data]\nanvil = [\"py.typed\"]\n"
        )
        assert check_package_data_configured(tmp_path) is None

    def test_missing_pyproject_returns_error(self, tmp_path: Path) -> None:
        """Returns error when pyproject.toml does not exist."""
        error = check_package_data_configured(tmp_path)
        assert error is not None
        assert "not found" in error

    def test_missing_section_returns_error(self, tmp_path: Path) -> None:
        """Returns error when tool.setuptools.package-data section missing."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[tool.ruff]\n")
        error = check_package_data_configured(tmp_path)
        assert error is not None
        assert "not found" in error

    def test_missing_entry_returns_error(self, tmp_path: Path) -> None:
        """Returns error when py.typed is not in the package-data list."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            "[tool.setuptools.package-data]\nanvil = [\"other_file\"]\n"
        )
        error = check_package_data_configured(tmp_path)
        assert error is not None
        assert "not listed" in error

    def test_invalid_toml_returns_error(self, tmp_path: Path) -> None:
        """Returns error when pyproject.toml is malformed."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("invalid [[ toml content")
        error = check_package_data_configured(tmp_path)
        assert error is not None
        assert "failed to parse" in error

    def test_anvil_section_missing(self, tmp_path: Path) -> None:
        """Returns error when anvil entry is absent from package-data."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            "[tool.setuptools.package-data]\nother_pkg = [\"py.typed\"]\n"
        )
        error = check_package_data_configured(tmp_path)
        assert error is not None
        assert "not listed" in error


########################################################################
# CLI main tests
########################################################################


class TestMain:
    """Tests for the CLI entry point."""

    def test_all_ok(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Exits 0 when all checks pass."""
        anvil_dir = tmp_path / "anvil"
        anvil_dir.mkdir()
        (anvil_dir / "py.typed").write_text("")
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            "[tool.setuptools.package-data]\nanvil = [\"py.typed\"]\n"
        )
        monkeypatch.setenv("ANVIL_REPO_ROOT", str(tmp_path))
        with pytest.raises(SystemExit) as exc:
            main([str(tmp_path)])
        assert exc.value.code == 0

    def test_missing_py_typed_exits_1(self, tmp_path: Path) -> None:
        """Exits 1 when py.typed does not exist."""
        anvil_dir = tmp_path / "anvil"
        anvil_dir.mkdir()
        with pytest.raises(SystemExit) as exc:
            main([str(tmp_path)])
        assert exc.value.code == 1

    def test_non_empty_py_typed_exits_1(self, tmp_path: Path) -> None:
        """Exits 1 when py.typed is not empty."""
        anvil_dir = tmp_path / "anvil"
        anvil_dir.mkdir()
        (anvil_dir / "py.typed").write_text("content")
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            "[tool.setuptools.package-data]\nanvil = [\"py.typed\"]\n"
        )
        with pytest.raises(SystemExit) as exc:
            main([str(tmp_path)])
        assert exc.value.code == 1

    def test_missing_config_exits_1(self, tmp_path: Path) -> None:
        """Exits 1 when pyproject.toml is missing."""
        anvil_dir = tmp_path / "anvil"
        anvil_dir.mkdir()
        (anvil_dir / "py.typed").write_text("")
        with pytest.raises(SystemExit) as exc:
            main([str(tmp_path)])
        assert exc.value.code == 1

    def test_no_args_uses_cwd(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """No args uses CWD (or env) as repo root."""
        monkeypatch.chdir(tmp_path)
        # No anvil dir in tmp_path - should fail
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 1