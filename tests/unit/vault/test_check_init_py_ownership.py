# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for the ``__init__.py`` ownership checker.

Tests ``_has_py_files``, ``_is_data_dir``, ``_init_py_is_bare``,
``scan_directory``, and the ``main`` CLI entry point.
"""

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


########################################################################
# _has_py_files tests
########################################################################


class TestHasPyFiles:
    """Tests for the _has_py_files helper."""

    def test_dir_with_py(self, tmp_path: Path) -> None:
        """Directory with a .py file returns True."""
        (tmp_path / "module.py").write_text("x = 1\n")
        assert _has_py_files(tmp_path) is True

    def test_dir_without_py(self, tmp_path: Path) -> None:
        """Directory without .py files returns False."""
        (tmp_path / "readme.md").write_text("# readme")
        assert _has_py_files(tmp_path) is False

    def test_empty_dir(self, tmp_path: Path) -> None:
        """Empty directory returns False."""
        assert _has_py_files(tmp_path) is False

    def test_non_recursive(self, tmp_path: Path) -> None:
        """Does not check subdirectories."""
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "module.py").write_text("x = 1\n")
        assert _has_py_files(tmp_path) is False


########################################################################
# _is_data_dir tests
########################################################################


class TestIsDataDir:
    """Tests for the _is_data_dir helper."""

    def test_known_data_dir(self, tmp_path: Path) -> None:
        """Known data directory name returns True."""
        d = tmp_path / "static"
        d.mkdir()
        assert _is_data_dir(d) is True

    def test_ancestor_data_dir(self, tmp_path: Path) -> None:
        """Child of a known data directory returns True."""
        d = tmp_path / "data" / "subdir"
        d.mkdir(parents=True)
        assert _is_data_dir(d) is True

    def test_normal_dir(self, tmp_path: Path) -> None:
        """Normal directory returns False."""
        d = tmp_path / "services"
        d.mkdir()
        assert _is_data_dir(d) is False

    def test_templates_is_data_dir(self, tmp_path: Path) -> None:
        """templates/ is a data directory."""
        d = tmp_path / "templates"
        d.mkdir()
        assert _is_data_dir(d) is True

    def test_multiple_levels(self, tmp_path: Path) -> None:
        """Deeply nested under data dir returns True."""
        d = tmp_path / "_resources" / "nested" / "deep"
        d.mkdir(parents=True)
        assert _is_data_dir(d) is True


########################################################################
# _init_py_is_bare tests
########################################################################


class TestInitPyIsBare:
    """Tests for the _init_py_is_bare helper."""

    def test_bare_docstring_only(self, tmp_path: Path) -> None:
        """File with only a docstring is bare."""
        p = tmp_path / "__init__.py"
        p.write_text('"""Package docstring."""\n')
        assert _init_py_is_bare(p) is True

    def test_bare_with_copyright(self, tmp_path: Path) -> None:
        """File with copyright header and docstring is bare."""
        p = tmp_path / "__init__.py"
        p.write_text(
            "# Copyright 2026\n"
            "# License MIT\n"
            '"""Package docstring."""\n'
        )
        assert _init_py_is_bare(p) is True

    def test_bare_empty(self, tmp_path: Path) -> None:
        """Empty file is bare."""
        p = tmp_path / "__init__.py"
        p.write_text("")
        assert _init_py_is_bare(p) is True

    def test_with_import_not_bare(self, tmp_path: Path) -> None:
        """File with import statement is not bare."""
        p = tmp_path / "__init__.py"
        p.write_text("import os\n")
        assert _init_py_is_bare(p) is False

    def test_with_from_import_not_bare(self, tmp_path: Path) -> None:
        """File with from-import is not bare."""
        p = tmp_path / "__init__.py"
        p.write_text("from .module import X\n")
        assert _init_py_is_bare(p) is False

    def test_with_class_not_bare(self, tmp_path: Path) -> None:
        """File with class definition is not bare."""
        p = tmp_path / "__init__.py"
        p.write_text("class MyClass:\n    pass\n")
        assert _init_py_is_bare(p) is False

    def test_with_function_not_bare(self, tmp_path: Path) -> None:
        """File with function definition is not bare."""
        p = tmp_path / "__init__.py"
        p.write_text("def foo() -> None:\n    pass\n")
        assert _init_py_is_bare(p) is False

    def test_with_assignment_not_bare(self, tmp_path: Path) -> None:
        """File with assignment is not bare."""
        p = tmp_path / "__init__.py"
        p.write_text("__version__ = '1.0'\n")
        assert _init_py_is_bare(p) is False

    def test_unreadable(self, tmp_path: Path) -> None:
        """Unreadable file returns not bare."""
        p = tmp_path / "__init__.py"
        p.write_text("x = 1\n")
        p.chmod(0o000)
        assert _init_py_is_bare(p) is False
        p.chmod(0o644)

    def test_syntax_error(self, tmp_path: Path) -> None:
        """File with syntax error returns not bare."""
        p = tmp_path / "__init__.py"
        p.write_text("if True:\n")
        assert _init_py_is_bare(p) is False

    def test_async_function_not_bare(self, tmp_path: Path) -> None:
        """File with async function is not bare."""
        p = tmp_path / "__init__.py"
        p.write_text("async def foo() -> None:\n    pass\n")
        assert _init_py_is_bare(p) is False


########################################################################
# scan_directory tests
########################################################################


class TestScanDirectory:
    """Tests for the scan_directory function."""

    def test_compliant_package(self, tmp_path: Path) -> None:
        """Package with bare __init__.py has no violations."""
        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text('"""My package."""\n')
        (pkg / "module.py").write_text("x = 1\n")
        scans = scan_directory(tmp_path)
        # No violations expected
        self._assert_no_violations(scans)

    def test_missing_init_py(self, tmp_path: Path) -> None:
        """Package with .py files but no __init__.py has a violation."""
        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        (pkg / "module.py").write_text("x = 1\n")
        scans = scan_directory(tmp_path)
        violations = self._count_violations(scans)
        assert violations == 1
        assert any("Missing __init__.py" in v.message for s in scans for v in s.violations)

    def test_data_dir_with_init_py(self, tmp_path: Path) -> None:
        """Data directory with __init__.py has a violation."""
        d = tmp_path / "static"
        d.mkdir()
        (d / "__init__.py").write_text('"""Should not be here."""\n')
        scans = scan_directory(tmp_path)
        violations = self._count_violations(scans)
        assert violations == 1
        assert any("must not contain" in v.message for s in scans for v in s.violations)

    def test_non_bare_init_py(self, tmp_path: Path) -> None:
        """Package with non-bare __init__.py has a violation."""
        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("import os\n")
        (pkg / "module.py").write_text("x = 1\n")
        scans = scan_directory(tmp_path)
        violations = self._count_violations(scans)
        assert violations == 1
        assert any("contains imports" in v.message for s in scans for v in s.violations)

    def test_empty_dir_no_violations(self, tmp_path: Path) -> None:
        """Empty directory has no violations."""
        scans = scan_directory(tmp_path)
        self._assert_no_violations(scans)

    def test_nested_packages(self, tmp_path: Path) -> None:
        """Nested packages are checked."""
        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text('"""Top."""\n')
        (pkg / "module.py").write_text("x = 1\n")
        sub = pkg / "subpkg"
        sub.mkdir()
        (sub / "module.py").write_text("y = 2\n")
        # subpkg missing __init__.py
        scans = scan_directory(tmp_path)
        violations = self._count_violations(scans)
        assert violations == 1

    @staticmethod
    def _count_violations(scans: list[PackageScan]) -> int:
        return sum(len(s.violations) for s in scans)

    @staticmethod
    def _assert_no_violations(scans: list[PackageScan]) -> None:
        for s in scans:
            assert len(s.violations) == 0, f"Unexpected violations in {s.dirpath}: {s.violations}"


########################################################################
# main CLI tests
########################################################################


class TestMain:
    """Tests for the CLI entry point."""

    def test_clean_exits_0(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Clean directory exits with code 0."""
        monkeypatch.setenv("ANVIL_ROOT", str(tmp_path))
        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text('"""My package."""\n')
        (pkg / "module.py").write_text("x = 1\n")
        from anvil.services.vault.check_init_py_ownership import main

        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 0

    def test_violation_exits_1(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Directory with violations exits with code 1."""
        monkeypatch.setenv("ANVIL_ROOT", str(tmp_path))
        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        (pkg / "module.py").write_text("x = 1\n")
        from anvil.services.vault.check_init_py_ownership import main

        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 1

    def test_nonexistent_root_exits_1(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Non-existent root directory exits with code 1."""
        monkeypatch.setenv("ANVIL_ROOT", str(tmp_path / "nonexistent"))
        monkeypatch.chdir(tmp_path)
        from anvil.services.vault.check_init_py_ownership import main

        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 1