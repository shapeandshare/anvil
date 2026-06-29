# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for the one-class-per-file checker.

Tests ``_has_suppression``, ``_is_enum_class``, ``_is_exception_class``,
``scan_file``, ``scan_directory``, and the ``main`` CLI entry point.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from anvil.services.vault.check_one_class import (
    OneClassIssue,
    ScanResult,
    _has_suppression,
    _is_enum_class,
    _is_exception_class,
    scan_directory,
    scan_file,
)

########################################################################
# _has_suppression tests
########################################################################


class TestHasSuppression:
    """Tests for the _has_suppression helper."""

    def test_suppression_in_first_line(self) -> None:
        """Suppression comment in first line returns True."""
        source = "# one-class:allow\nx = 1\n"
        assert _has_suppression(source) is True

    def test_suppression_in_fifth_line(self) -> None:
        """Suppression comment in 5th line returns True."""
        source = "# line1\n# line2\n# line3\n# line4\n# one-class:allow\n"
        assert _has_suppression(source) is True

    def test_no_suppression(self) -> None:
        """No suppression comment returns False."""
        source = "# regular comment\nx = 1\n"
        assert _has_suppression(source) is False

    def test_suppression_after_fifth_line(self) -> None:
        """Suppression after 5th line is not detected."""
        source = "# line1\n# line2\n# line3\n# line4\n# line5\n# one-class:allow\n"
        assert _has_suppression(source) is False

    def test_empty_file(self) -> None:
        """Empty file returns False."""
        assert _has_suppression("") is False


########################################################################
# _is_enum_class tests
########################################################################


class TestIsEnumClass:
    """Tests for the _is_enum_class helper."""

    def test_direct_enum_inheritance(self) -> None:
        """Class inheriting from Enum is detected."""
        import ast

        node = ast.parse("class Color(Enum):\n    RED = 1\n").body[0]
        assert isinstance(node, ast.ClassDef)
        assert _is_enum_class(node) is True

    def test_enum_attribute_inheritance(self) -> None:
        """Class inheriting from enum.Enum is detected."""
        import ast

        node = ast.parse("class Color(enum.Enum):\n    RED = 1\n").body[0]
        assert isinstance(node, ast.ClassDef)
        assert _is_enum_class(node) is True

    def test_regular_class(self) -> None:
        """Regular class returns False."""
        import ast

        node = ast.parse("class MyClass:\n    pass\n").body[0]
        assert isinstance(node, ast.ClassDef)
        assert _is_enum_class(node) is False

    def test_other_inheritance(self) -> None:
        """Class inheriting from something else returns False."""
        import ast

        node = ast.parse("class MyClass(Base):\n    pass\n").body[0]
        assert isinstance(node, ast.ClassDef)
        assert _is_enum_class(node) is False


########################################################################
# _is_exception_class tests
########################################################################


class TestIsExceptionClass:
    """Tests for the _is_exception_class helper."""

    def test_direct_exception_inheritance(self) -> None:
        """Class inheriting from Exception is detected."""
        import ast

        node = ast.parse("class MyError(Exception):\n    pass\n").body[0]
        assert isinstance(node, ast.ClassDef)
        assert _is_exception_class(node) is True

    def test_exception_attribute_inheritance(self) -> None:
        """Class inheriting from exceptions.Exception is detected."""
        import ast

        node = ast.parse("class MyError(exceptions.Exception):\n    pass\n").body[0]
        assert isinstance(node, ast.ClassDef)
        assert _is_exception_class(node) is True

    def test_regular_class(self) -> None:
        """Regular class returns False."""
        import ast

        node = ast.parse("class MyClass:\n    pass\n").body[0]
        assert isinstance(node, ast.ClassDef)
        assert _is_exception_class(node) is False


########################################################################
# scan_file tests
########################################################################


class TestScanFile:
    """Tests for the scan_file function."""

    def test_single_class(self, tmp_path: Path) -> None:
        """File with one class has no issues."""
        p = tmp_path / "test.py"
        p.write_text("class MyClass:\n    pass\n")
        result = scan_file(p)
        assert isinstance(result, ScanResult)
        assert len(result.issues) == 0

    def test_no_classes(self, tmp_path: Path) -> None:
        """File with no classes has no issues."""
        p = tmp_path / "test.py"
        p.write_text("x = 1\n")
        result = scan_file(p)
        assert len(result.issues) == 0

    def test_multiple_primary_classes_flagged(self, tmp_path: Path) -> None:
        """File with multiple non-companion classes is flagged."""
        p = tmp_path / "test.py"
        p.write_text("class ClassA:\n    pass\n\nclass ClassB:\n    pass\n")
        result = scan_file(p)
        assert len(result.issues) == 1
        assert "ClassA" in result.issues[0].message
        assert "ClassB" in result.issues[0].message

    def test_enum_companion_allowed(self, tmp_path: Path) -> None:
        """File with one class and one Enum companion passes."""
        p = tmp_path / "test.py"
        p.write_text(
            "from enum import Enum\n"
            "\n"
            "class Color(Enum):\n"
            "    RED = 1\n"
            "\n"
            "class MainClass:\n"
            "    pass\n"
        )
        result = scan_file(p)
        assert len(result.issues) == 0

    def test_exception_companion_allowed(self, tmp_path: Path) -> None:
        """File with one class and one Exception companion passes."""
        p = tmp_path / "test.py"
        p.write_text(
            "class MyError(Exception):\n"
            "    pass\n"
            "\n"
            "class MainClass:\n"
            "    pass\n"
        )
        result = scan_file(p)
        assert len(result.issues) == 0

    def test_suppression_comment_allowed(self, tmp_path: Path) -> None:
        """File with suppression comment passes."""
        p = tmp_path / "test.py"
        p.write_text(
            "# one-class:allow\n"
            "class ClassA:\n"
            "    pass\n"
            "\n"
            "class ClassB:\n"
            "    pass\n"
        )
        result = scan_file(p)
        assert len(result.issues) == 0

    def test_two_exceptions_allowed(self, tmp_path: Path) -> None:
        """File with two exception classes and one primary passes."""
        p = tmp_path / "test.py"
        p.write_text(
            "class ErrorA(Exception):\n"
            "    pass\n"
            "\n"
            "class ErrorB(Exception):\n"
            "    pass\n"
            "\n"
            "class MainClass:\n"
            "    pass\n"
        )
        result = scan_file(p)
        assert len(result.issues) == 0

    def test_two_primary_and_exception_flagged(self, tmp_path: Path) -> None:
        """File with two primary + exception is flagged (2 primaries)."""
        p = tmp_path / "test.py"
        p.write_text(
            "class ErrorA(Exception):\n"
            "    pass\n"
            "\n"
            "class ClassA:\n"
            "    pass\n"
            "\n"
            "class ClassB:\n"
            "    pass\n"
        )
        result = scan_file(p)
        assert len(result.issues) == 1
        assert "ErrorA" in result.issues[0].classes
        assert "ClassA" in result.issues[0].classes
        assert "ClassB" in result.issues[0].classes

    def test_three_primary_classes_flagged(self, tmp_path: Path) -> None:
        """File with three primary classes is flagged."""
        p = tmp_path / "test.py"
        p.write_text(
            "class ClassA:\n"
            "    pass\n"
            "\n"
            "class ClassB:\n"
            "    pass\n"
            "\n"
            "class ClassC:\n"
            "    pass\n"
        )
        result = scan_file(p)
        assert len(result.issues) == 1
        assert len(result.issues[0].classes) == 3

    def test_unreadable_file(self, tmp_path: Path) -> None:
        """Unreadable file returns read error as issue."""
        p = tmp_path / "test.py"
        p.write_text("x = 1")
        p.chmod(0o000)
        result = scan_file(p)
        assert len(result.issues) == 1
        assert "Cannot read" in result.issues[0].message
        p.chmod(0o644)

    def test_syntax_error(self, tmp_path: Path) -> None:
        """File with syntax error returns parse error."""
        p = tmp_path / "test.py"
        p.write_text("class MyClass\n    pass\n")
        result = scan_file(p)
        assert len(result.issues) == 1
        assert "Cannot parse" in result.issues[0].message


########################################################################
# scan_directory tests
########################################################################


class TestScanDirectory:
    """Tests for the scan_directory function."""

    def test_empty_directory(self, tmp_path: Path) -> None:
        """Empty directory returns empty results."""
        results = scan_directory(tmp_path)
        assert len(results) == 0

    def test_multiple_files_with_violations(self, tmp_path: Path) -> None:
        """Multiple files with violations are detected."""
        (tmp_path / "good.py").write_text("class MyClass:\n    pass\n")
        (tmp_path / "bad.py").write_text("class A:\n    pass\n\nclass B:\n    pass\n")
        results = scan_directory(tmp_path)
        assert len(results) == 2
        total_issues = sum(len(r.issues) for r in results)
        assert total_issues == 1

    def test_recursive_scan(self, tmp_path: Path) -> None:
        """Files in subdirectories are scanned."""
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "deep.py").write_text("class MyClass:\n    pass\n")
        (tmp_path / "good.py").write_text("class MyClass:\n    pass\n")
        results = scan_directory(tmp_path)
        assert len(results) == 2

    def test_skips_non_py_files(self, tmp_path: Path) -> None:
        """Non-.py files are skipped."""
        (tmp_path / "test.md").write_text("# readme")
        (tmp_path / "good.py").write_text("class MyClass:\n    pass\n")
        results = scan_directory(tmp_path)
        assert len(results) == 1


########################################################################
# main CLI tests
########################################################################


class TestMain:
    """Tests for the CLI entry point."""

    def test_clean_exits_0(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Clean directory exits with code 0."""
        monkeypatch.setenv("ANVIL_ROOT", str(tmp_path))
        p = tmp_path / "test.py"
        p.write_text("class MyClass:\n    pass\n")
        from anvil.services.vault.check_one_class import main

        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 0

    def test_violation_exits_1(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Directory with violations exits with code 1."""
        monkeypatch.setenv("ANVIL_ROOT", str(tmp_path))
        p = tmp_path / "test.py"
        p.write_text("class A:\n    pass\n\nclass B:\n    pass\n")
        from anvil.services.vault.check_one_class import main

        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 1

    def test_nonexistent_root_exits_1(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Non-existent root directory exits with code 1."""
        monkeypatch.setenv("ANVIL_ROOT", str(tmp_path / "nonexistent"))
        monkeypatch.chdir(tmp_path)
        from anvil.services.vault.check_one_class import main

        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 1
