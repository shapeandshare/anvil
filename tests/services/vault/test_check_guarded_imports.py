# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for :mod:`anvil.services.vault.check_guarded_imports` — guarded-
import checker.
"""

from __future__ import annotations

from pathlib import Path

from anvil.services.vault.check_guarded_imports import (
    _extract_guarded_imports,
    _find_runtime_usages,
    scan_directory,
    scan_file,
)


class TestExtractGuardedImports:
    """Tests for ``_extract_guarded_imports``."""

    def test_single_from_import(self) -> None:
        source = "if TYPE_CHECKING:\n" "    from .other_module import OtherClass\n"
        result = _extract_guarded_imports(source, "test.py")
        assert len(result) == 1
        assert result[0].symbol == "OtherClass"
        assert result[0].line == 2

    def test_multiple_from_imports(self) -> None:
        source = (
            "if TYPE_CHECKING:\n" "    from .foo import A\n" "    from .bar import B\n"
        )
        result = _extract_guarded_imports(source, "test.py")
        assert len(result) == 2
        assert result[0].symbol == "A"
        assert result[1].symbol == "B"

    def test_import_with_alias(self) -> None:
        source = "if TYPE_CHECKING:\n" "    from .module import X as Y\n"
        result = _extract_guarded_imports(source, "test.py")
        assert len(result) == 1
        assert result[0].symbol == "Y"

    def test_no_type_checking_block(self) -> None:
        source = "from .module import X\n"
        result = _extract_guarded_imports(source, "test.py")
        assert result == []

    def test_blank_lines_inside_guard_skipped(self) -> None:
        source = (
            "if TYPE_CHECKING:\n"
            "    from .foo import A\n"
            "\n"
            "    from .bar import B\n"
        )
        result = _extract_guarded_imports(source, "test.py")
        assert len(result) == 2

    def test_comment_lines_inside_guard_skipped(self) -> None:
        source = "if TYPE_CHECKING:\n" "    # comment\n" "    from .foo import A\n"
        result = _extract_guarded_imports(source, "test.py")
        assert len(result) == 1
        assert result[0].symbol == "A"

    def test_exit_guard_on_non_indented_line(self) -> None:
        source = "if TYPE_CHECKING:\n" "    from .foo import A\n" "x = 1\n"
        result = _extract_guarded_imports(source, "test.py")
        assert len(result) == 1


class TestFindRuntimeUsages:
    """Tests for ``_find_runtime_usages``."""

    def test_runtime_instantiation_flagged(self) -> None:
        source = "x = OtherClass()\n"
        symbols = {"OtherClass"}
        result = _find_runtime_usages(source, symbols, "test.py")
        assert len(result) == 1
        assert "OtherClass" in result[0].symbol

    def test_annotation_only_with_future_allowed(self) -> None:
        source = "from __future__ import annotations\n\ndef foo() -> OtherClass: ...\n"
        symbols = {"OtherClass"}
        result = _find_runtime_usages(source, symbols, "test.py")
        assert result == []

    def test_annotation_without_future_flagged(self) -> None:
        source = "def foo() -> OtherClass: ...\n"
        symbols = {"OtherClass"}
        result = _find_runtime_usages(source, symbols, "test.py")
        # Without __future__ annotations, annotations ARE runtime
        assert len(result) == 1

    def test_import_lines_skipped(self) -> None:
        source = "from .other_module import OtherClass\n"
        symbols = {"OtherClass"}
        result = _find_runtime_usages(source, symbols, "test.py")
        assert result == []

    def test_comment_lines_skipped(self) -> None:
        source = "# Uses OtherClass internally\n"
        symbols = {"OtherClass"}
        result = _find_runtime_usages(source, symbols, "test.py")
        assert result == []

    def test_no_matching_symbol(self) -> None:
        source = "x = SomethingElse()\n"
        symbols = {"OtherClass"}
        result = _find_runtime_usages(source, symbols, "test.py")
        assert result == []

    def test_empty_source(self) -> None:
        result = _find_runtime_usages("", {"Foo"}, "test.py")
        assert result == []

    def test_empty_symbols(self) -> None:
        result = _find_runtime_usages("x = Foo()\n", set(), "test.py")
        assert result == []


class TestScanFile:
    """Tests for ``scan_file`` with temp files."""

    def test_clean_file_no_issues(self, tmp_path: Path) -> None:
        p = tmp_path / "clean.py"
        p.write_text("from .module import X\nx = 1\n")
        result = scan_file(p)
        assert result.issues == []

    def test_guarded_import_annotation_only(self, tmp_path: Path) -> None:
        p = tmp_path / "guarded.py"
        p.write_text(
            "from __future__ import annotations\n"
            "from typing import TYPE_CHECKING\n"
            "\n"
            "if TYPE_CHECKING:\n"
            "    from .other import OtherClass\n"
            "\n"
            "def foo() -> OtherClass: ...\n"
        )
        result = scan_file(p)
        assert result.issues == []
        assert len(result.imports) == 1

    def test_guarded_import_runtime_usage(self, tmp_path: Path) -> None:
        p = tmp_path / "bad.py"
        p.write_text(
            "from typing import TYPE_CHECKING\n"
            "\n"
            "if TYPE_CHECKING:\n"
            "    from .other import OtherClass\n"
            "\n"
            "x = OtherClass()\n"
        )
        result = scan_file(p)
        assert len(result.issues) == 1

    def test_nonexistent_file_reports_error(self, tmp_path: Path) -> None:
        p = tmp_path / "nonexistent.py"
        result = scan_file(p)
        assert len(result.issues) == 1
        assert "Cannot read" in result.issues[0].message

    def test_no_guarded_imports_no_issues(self, tmp_path: Path) -> None:
        p = tmp_path / "normal.py"
        p.write_text("from __future__ import annotations\nx: int = 1\n")
        result = scan_file(p)
        assert result.imports == []
        assert result.issues == []


class TestScanDirectory:
    """Tests for ``scan_directory`` with temp directories."""

    def test_clean_directory(self, tmp_path: Path) -> None:
        (tmp_path / "good.py").write_text(
            "from __future__ import annotations\n"
            "from typing import TYPE_CHECKING\n"
            "\n"
            "if TYPE_CHECKING:\n"
            "    from .other import OtherClass\n"
            "\n"
            "def foo() -> OtherClass: ...\n"
        )
        results = scan_directory(tmp_path)
        assert len(results) == 1
        assert results[0].issues == []

    def test_directory_with_violations(self, tmp_path: Path) -> None:
        (tmp_path / "bad.py").write_text(
            "from typing import TYPE_CHECKING\n"
            "\n"
            "if TYPE_CHECKING:\n"
            "    from .other import OtherClass\n"
            "\n"
            "x = OtherClass()\n"
        )
        results = scan_directory(tmp_path)
        assert len(results) == 1
        assert len(results[0].issues) == 1

    def test_multiple_files(self, tmp_path: Path) -> None:
        (tmp_path / "clean.py").write_text("x = 1\n")
        (tmp_path / "guarded.py").write_text(
            "from __future__ import annotations\n"
            "from typing import TYPE_CHECKING\n"
            "\n"
            "if TYPE_CHECKING:\n"
            "    from .other import OtherClass\n"
        )
        results = scan_directory(tmp_path)
        assert len(results) == 2
        assert all(r.issues == [] for r in results)
