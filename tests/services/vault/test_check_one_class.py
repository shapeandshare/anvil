# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for :mod:`anvil.services.vault.check_one_class` — one-class-per-file
checker."""

from __future__ import annotations

from pathlib import Path

from anvil.services.vault.check_one_class import scan_file


class TestScanFile:
    """Tests for ``scan_file``.

    The checker uses AST to count class definitions per file. Files with
    1 class pass. Files with 2+ classes are violations UNLESS the extra
    classes are enums or exceptions.
    """

    def test_one_class_pass(self, tmp_path: Path) -> None:
        filepath = tmp_path / "foo.py"
        filepath.write_text("class MyClass:\n    pass\n")
        result = scan_file(filepath)
        assert result.issues == []

    def test_two_classes_fail(self, tmp_path: Path) -> None:
        filepath = tmp_path / "foo.py"
        filepath.write_text("class Alpha:\n    pass\n\nclass Beta:\n    pass\n")
        result = scan_file(filepath)
        assert len(result.issues) == 1
        assert "Alpha" in result.issues[0].classes
        assert "Beta" in result.issues[0].classes

    def test_class_and_enum_pass(self, tmp_path: Path) -> None:
        filepath = tmp_path / "foo.py"
        filepath.write_text(
            "from enum import Enum\n\nclass Color(Enum):\n    RED = 1\n\nclass MyClass:\n    pass\n"
        )
        result = scan_file(filepath)
        assert result.issues == []

    def test_class_and_exception_pass(self, tmp_path: Path) -> None:
        filepath = tmp_path / "foo.py"
        filepath.write_text(
            "class MyError(Exception):\n    pass\n\nclass MyClass:\n    pass\n"
        )
        result = scan_file(filepath)
        assert result.issues == []

    def test_no_classes_pass(self, tmp_path: Path) -> None:
        filepath = tmp_path / "foo.py"
        filepath.write_text("def helper():\n    return 42\n\nCONSTANT = 'hello'\n")
        result = scan_file(filepath)
        assert result.issues == []

    def test_three_classes_fail(self, tmp_path: Path) -> None:
        filepath = tmp_path / "foo.py"
        filepath.write_text(
            "class A:\n    pass\n\nclass B:\n    pass\n\nclass C:\n    pass\n"
        )
        result = scan_file(filepath)
        assert len(result.issues) == 1
        assert result.issues[0].classes == ["A", "B", "C"]

    def test_suppression_comment(self, tmp_path: Path) -> None:
        filepath = tmp_path / "foo.py"
        filepath.write_text(
            "# one-class:allow\n\nclass Alpha:\n    pass\n\nclass Beta:\n    pass\n"
        )
        result = scan_file(filepath)
        assert result.issues == []

    def test_two_classes_both_exceptions_fail(self, tmp_path: Path) -> None:
        filepath = tmp_path / "foo.py"
        filepath.write_text(
            "class MyError(Exception):\n    pass\n\nclass AnotherError(Exception):\n    pass\n"
        )
        result = scan_file(filepath)
        assert len(result.issues) == 1
        assert "MyError" in result.issues[0].classes
        assert "AnotherError" in result.issues[0].classes