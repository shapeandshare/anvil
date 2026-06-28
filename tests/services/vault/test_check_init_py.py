# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for ``check_init_py_ownership`` — ``__init__.py`` ownership checker."""

from __future__ import annotations

from pathlib import Path

import pytest

from anvil.services.vault.check_init_py_ownership import (
    InitPyViolation,
    PackageScan,
    _has_py_files,
    _init_py_is_bare,
    _is_data_dir,
    scan_directory,
)


class TestHasPyFiles:
    """Tests for ``_has_py_files``."""

    def test_dir_with_py_files(self, tmp_path: Path) -> None:
        d = tmp_path / "mypkg"
        d.mkdir()
        (d / "module.py").write_text("x = 1\n")
        assert _has_py_files(d) is True

    def test_dir_without_py_files(self, tmp_path: Path) -> None:
        d = tmp_path / "mypkg"
        d.mkdir()
        (d / "data.txt").write_text("hello\n")
        assert _has_py_files(d) is False

    def test_empty_dir(self, tmp_path: Path) -> None:
        d = tmp_path / "emptydir"
        d.mkdir()
        assert _has_py_files(d) is False

    def test_nested_py_files_not_counted(self, tmp_path: Path) -> None:
        d = tmp_path / "mypkg"
        sub = d / "subpkg"
        sub.mkdir(parents=True)
        (sub / "deep.py").write_text("x = 1\n")
        assert _has_py_files(d) is False


class TestIsDataDir:
    """Tests for ``_is_data_dir``."""

    def test_known_data_dirs(self) -> None:
        for name in ("static", "templates", "data", "_resources", "_meta"):
            assert _is_data_dir(name) is True

    def test_non_data_dir(self) -> None:
        assert _is_data_dir("services") is False
        assert _is_data_dir("core") is False
        assert _is_data_dir("mypackage") is False


class TestInitPyIsBare:
    """Tests for ``_init_py_is_bare``."""

    def test_docstring_only(self, tmp_path: Path) -> None:
        p = tmp_path / "__init__.py"
        p.write_text('"""My package docstring."""\n')
        assert _init_py_is_bare(p) is True

    def test_copyright_and_docstring(self, tmp_path: Path) -> None:
        p = tmp_path / "__init__.py"
        p.write_text(
            "# Copyright notice\n" "# License header\n" '"""My package docstring."""\n'
        )
        assert _init_py_is_bare(p) is True

    def test_with_import(self, tmp_path: Path) -> None:
        p = tmp_path / "__init__.py"
        p.write_text('"""My package."""\nfrom .module import X\n')
        assert _init_py_is_bare(p) is False

    def test_with_from_import(self, tmp_path: Path) -> None:
        p = tmp_path / "__init__.py"
        p.write_text('"""My package."""\nimport os\n')
        assert _init_py_is_bare(p) is False

    def test_with_function_def(self, tmp_path: Path) -> None:
        p = tmp_path / "__init__.py"
        p.write_text('"""My package."""\ndef foo() -> None:\n    pass\n')
        assert _init_py_is_bare(p) is False

    def test_with_class_def(self, tmp_path: Path) -> None:
        p = tmp_path / "__init__.py"
        p.write_text('"""My package."""\nclass Foo:\n    pass\n')
        assert _init_py_is_bare(p) is False

    def test_with_assignment(self, tmp_path: Path) -> None:
        p = tmp_path / "__init__.py"
        p.write_text('"""My package."""\n__version__ = "1.0"\n')
        assert _init_py_is_bare(p) is False

    def test_empty_file(self, tmp_path: Path) -> None:
        p = tmp_path / "__init__.py"
        p.write_text("")
        assert _init_py_is_bare(p) is True

    def test_only_blank_lines(self, tmp_path: Path) -> None:
        p = tmp_path / "__init__.py"
        p.write_text("\n\n\n")
        assert _init_py_is_bare(p) is True


class TestScanDirectory:
    """Tests for ``scan_directory`` — the main entry point."""

    def test_valid_package_with_init_py(self, tmp_path: Path) -> None:
        pkg = tmp_path / "mypackage"
        pkg.mkdir()
        (pkg / "module.py").write_text("x = 1\n")
        init = pkg / "__init__.py"
        init.write_text('"""My package."""\n')
        results = scan_directory(tmp_path)
        assert len(results) == 0

    def test_missing_init_py(self, tmp_path: Path) -> None:
        pkg = tmp_path / "mypackage"
        pkg.mkdir()
        (pkg / "module.py").write_text("x = 1\n")
        results = scan_directory(tmp_path)
        assert len(results) == 1
        scan = results[0]
        assert len(scan.violations) == 1
        v = scan.violations[0]
        assert "Missing __init__.py" in v.message

    def test_data_dir_with_init_py(self, tmp_path: Path) -> None:
        data_dir = tmp_path / "static"
        data_dir.mkdir()
        init = data_dir / "__init__.py"
        init.write_text('"""Data?""")')
        results = scan_directory(tmp_path)
        assert len(results) == 1
        v = results[0].violations[0]
        assert "must not contain __init__.py" in v.message

    def test_init_py_with_imports(self, tmp_path: Path) -> None:
        pkg = tmp_path / "mypackage"
        pkg.mkdir()
        (pkg / "module.py").write_text("x = 1\n")
        init = pkg / "__init__.py"
        init.write_text('"""My package."""\nfrom .module import x\n')
        results = scan_directory(tmp_path)
        assert len(results) == 1
        v = results[0].violations[0]
        assert "contains imports or re-exports" in v.message

    def test_init_py_with_only_docstring(self, tmp_path: Path) -> None:
        pkg = tmp_path / "mypackage"
        pkg.mkdir()
        (pkg / "module.py").write_text("x = 1\n")
        init = pkg / "__init__.py"
        init.write_text('"""My package."""\n')
        results = scan_directory(tmp_path)
        assert len(results) == 0

    def test_skip_known_data_dirs(self, tmp_path: Path) -> None:
        for name in ("static", "templates", "data", "_resources"):
            d = tmp_path / name
            d.mkdir()
            (d / "file.txt").write_text("content\n")
            # No __init__.py — should not produce violations
        results = scan_directory(tmp_path)
        data_results = [
            r
            for r in results
            if any(
                name in r.dirpath
                for name in ("static", "templates", "data", "_resources")
            )
        ]
        assert len(data_results) == 0

    def test_known_data_dirs_spurious_init_py(self, tmp_path: Path) -> None:
        for name in ("static", "templates", "data", "_resources"):
            d = tmp_path / name
            d.mkdir()
            (d / "__init__.py").write_text('"""oops"""\n')
        results = scan_directory(tmp_path)
        assert len(results) == 4
        for scan in results:
            assert any(
                "must not contain __init__.py" in v.message for v in scan.violations
            )

    def test_non_package_dir_no_issue(self, tmp_path: Path) -> None:
        d = tmp_path / "assets"
        d.mkdir()
        (d / "icon.svg").write_text("<svg></svg>\n")
        results = scan_directory(tmp_path)
        assert len(results) == 0

    def test_deeply_nested_violations(self, tmp_path: Path) -> None:
        sub = tmp_path / "subpkg"
        sub.mkdir()
        (sub / "mod.py").write_text("y = 2\n")
        results = scan_directory(tmp_path)
        assert len(results) == 1
        v = results[0].violations[0]
        assert "Missing __init__.py" in v.message
