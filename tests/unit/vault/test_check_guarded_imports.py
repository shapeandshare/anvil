# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for the guarded-imports checker.

Tests ``_extract_guarded_imports``, ``_find_runtime_usages``,
``scan_file``, ``scan_directory``, and the ``main`` CLI entry point.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from anvil.services.vault.check_guarded_imports import (
    ScanResult,
    _extract_guarded_imports,
    _find_runtime_usages,
    scan_directory,
    scan_file,
)


########################################################################
# _extract_guarded_imports tests
########################################################################


class TestExtractGuardedImports:
    """Tests for the _extract_guarded_imports helper."""

    def test_no_guarded_imports(self) -> None:
        """File without TYPE_CHECKING block returns empty list."""
        source = "import os\nfrom pathlib import Path\n"
        imports = _extract_guarded_imports(source, "test.py")
        assert len(imports) == 0

    def test_with_guarded_import(self) -> None:
        """Single TYPE_CHECKING-guarded import is extracted."""
        source = """from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .other import OtherClass
"""
        imports = _extract_guarded_imports(source, "test.py")
        assert len(imports) == 1
        assert imports[0].symbol == "OtherClass"
        assert imports[0].file == "test.py"

    def test_multiple_guarded_imports(self) -> None:
        """Multiple symbols in TYPE_CHECKING block are extracted."""
        source = """from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .module import ClassA, ClassB
    from .other import ClassC
"""
        imports = _extract_guarded_imports(source, "test.py")
        assert len(imports) == 3
        symbols = {i.symbol for i in imports}
        assert symbols == {"ClassA", "ClassB", "ClassC"}

    def test_guarded_import_with_alias(self) -> None:
        """Import with 'as' alias extracts the alias name."""
        source = """from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .module import LongName as LN
"""
        imports = _extract_guarded_imports(source, "test.py")
        assert len(imports) == 1
        assert imports[0].symbol == "LN"

    def test_guarded_import_statement(self) -> None:
        """Direct import within TYPE_CHECKING is extracted."""
        source = """from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import something
"""
        imports = _extract_guarded_imports(source, "test.py")
        assert len(imports) == 1
        assert imports[0].symbol == "something"

    def test_guard_exits_on_non_indented(self) -> None:
        """Guard block exits on non-indented, non-import line."""
        source = """from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .module import MyClass

x = 1
"""
        imports = _extract_guarded_imports(source, "test.py")
        assert len(imports) == 1


########################################################################
# _find_runtime_usages tests
########################################################################


class TestFindRuntimeUsages:
    """Tests for the _find_runtime_usages helper."""

    def test_no_runtime_usage_with_future(self) -> None:
        """Annotation-only usage with __future__ is safe."""
        source = """from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .module import MyClass

def foo(x: MyClass) -> None:
    pass
"""
        issues = _find_runtime_usages(source, {"MyClass"}, "test.py")
        assert len(issues) == 0

    def test_runtime_usage_detected(self) -> None:
        """Actual runtime usage of a guarded symbol is flagged."""
        source = """from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .module import MyClass

obj = MyClass()
"""
        issues = _find_runtime_usages(source, {"MyClass"}, "test.py")
        assert len(issues) == 1
        assert "MyClass" in issues[0].message
        assert issues[0].line == 6

    def test_import_line_skipped(self) -> None:
        """Import lines are not flagged as runtime usage."""
        source = """from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .module import MyClass

from .other import MyClass
"""
        issues = _find_runtime_usages(source, {"MyClass"}, "test.py")
        assert len(issues) == 0

    def test_comment_line_skipped(self) -> None:
        """Comment lines are not flagged."""
        source = """from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .module import MyClass

# MyClass is cool
"""
        issues = _find_runtime_usages(source, {"MyClass"}, "test.py")
        assert len(issues) == 0

    def test_multiple_usages_all_flagged(self) -> None:
        """Multiple runtime usages are all flagged."""
        source = """from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .module import MyClass

x = MyClass()
y = MyClass()
"""
        issues = _find_runtime_usages(source, {"MyClass"}, "test.py")
        assert len(issues) == 2

    def test_no_matching_symbol(self) -> None:
        """Symbols not in source are not flagged."""
        source = "x = 1\n"
        issues = _find_runtime_usages(source, {"NonExistent"}, "test.py")
        assert len(issues) == 0

    def test_annotation_without_future_is_runtime(self) -> None:
        """Without __future__, annotations are runtime and should be flagged."""
        source = """from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .module import MyClass

def foo(x: MyClass) -> None:
    pass
"""
        issues = _find_runtime_usages(source, {"MyClass"}, "test.py")
        assert len(issues) == 1


########################################################################
# scan_file tests
########################################################################


class TestScanFile:
    """Tests for the scan_file function."""

    def test_clean_file(self, tmp_path: Path) -> None:
        """File with no guarded imports returns clean result."""
        p = tmp_path / "test.py"
        p.write_text("import os\nx = 1\n")
        result = scan_file(p)
        assert isinstance(result, ScanResult)
        assert len(result.issues) == 0
        assert len(result.imports) == 0

    def test_annotation_only_guarded(self, tmp_path: Path) -> None:
        """File with annotation-only guarded imports passes."""
        p = tmp_path / "test.py"
        p.write_text(
            "from __future__ import annotations\n"
            "from typing import TYPE_CHECKING\n"
            "\n"
            "if TYPE_CHECKING:\n"
            "    from .module import MyClass\n"
            "\n"
            "def foo(x: MyClass) -> None:\n"
            "    pass\n"
        )
        result = scan_file(p)
        assert len(result.issues) == 0
        assert len(result.imports) == 1
        assert result.has_future_annotations is True

    def test_runtime_guarded_fails(self, tmp_path: Path) -> None:
        """File with runtime usage of guarded symbol fails."""
        p = tmp_path / "test.py"
        p.write_text(
            "from typing import TYPE_CHECKING\n"
            "\n"
            "if TYPE_CHECKING:\n"
            "    from .module import MyClass\n"
            "\n"
            "obj = MyClass()\n"
        )
        result = scan_file(p)
        assert len(result.issues) == 1
        assert "MyClass" in result.issues[0].message

    def test_unreadable_file(self, tmp_path: Path) -> None:
        """Unreadable file returns a scan issue."""
        p = tmp_path / "test.py"
        p.write_text("x = 1\n")
        p.chmod(0o000)
        result = scan_file(p)
        assert len(result.issues) == 1
        assert "Cannot read" in result.issues[0].message
        p.chmod(0o644)

    def test_no_future_annotation_usage_flagged(self, tmp_path: Path) -> None:
        """Without __future__, annotation usage is also flagged."""
        p = tmp_path / "test.py"
        p.write_text(
            "from typing import TYPE_CHECKING\n"
            "\n"
            "if TYPE_CHECKING:\n"
            "    from .module import MyClass\n"
            "\n"
            "def foo(x: MyClass) -> None:\n"
            "    pass\n"
        )
        result = scan_file(p)
        assert len(result.issues) == 1


########################################################################
# scan_directory tests
########################################################################


class TestScanDirectory:
    """Tests for the scan_directory function."""

    def test_empty_directory(self, tmp_path: Path) -> None:
        """Empty directory returns empty results list."""
        results = scan_directory(tmp_path)
        assert len(results) == 0

    def test_single_clean_file(self, tmp_path: Path) -> None:
        """Single clean file in directory returns one result."""
        p = tmp_path / "test.py"
        p.write_text("import os\n")
        results = scan_directory(tmp_path)
        assert len(results) == 1
        assert len(results[0].issues) == 0

    def test_recursive_scan(self, tmp_path: Path) -> None:
        """Files in subdirectories are scanned recursively."""
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "deep.py").write_text("import sys\n")
        p = tmp_path / "test.py"
        p.write_text("import os\n")
        results = scan_directory(tmp_path)
        assert len(results) == 2

    def test_skips_non_py_files(self, tmp_path: Path) -> None:
        """Non-.py files are not scanned."""
        (tmp_path / "readme.md").write_text("# readme")
        (tmp_path / "test.py").write_text("import os\n")
        results = scan_directory(tmp_path)
        assert len(results) == 1


########################################################################
# main CLI tests
########################################################################


class TestMain:
    """Tests for the CLI entry point."""

    def test_clean_exits_0(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Clean directory exits with code 0."""
        monkeypatch.setenv("ANVIL_ROOT", str(tmp_path))
        p = tmp_path / "test.py"
        p.write_text("import os\nx = 1\n")
        from anvil.services.vault.check_guarded_imports import main

        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 0

    def test_violation_exits_1(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Directory with violations exits with code 1."""
        monkeypatch.setenv("ANVIL_ROOT", str(tmp_path))
        p = tmp_path / "test.py"
        p.write_text(
            "from typing import TYPE_CHECKING\n"
            "\n"
            "if TYPE_CHECKING:\n"
            "    from .module import MyClass\n"
            "\n"
            "obj = MyClass()\n"
        )
        from anvil.services.vault.check_guarded_imports import main

        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 1

    def test_nonexistent_root_fallback(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """When ANVIL_ROOT points to non-existent dir, falls back to 'anvil'."""
        monkeypatch.setenv("ANVIL_ROOT", str(tmp_path / "nonexistent"))
        monkeypatch.chdir(tmp_path)
        from anvil.services.vault.check_guarded_imports import main

        with pytest.raises(SystemExit) as exc:
            main()
        # Falls back to 'anvil' which doesn't exist in tmp_path
        assert exc.value.code == 1

    def test_violation_with_future_not_flagged(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Annotation-only with __future__ is not flagged."""
        monkeypatch.setenv("ANVIL_ROOT", str(tmp_path))
        p = tmp_path / "test.py"
        p.write_text(
            "from __future__ import annotations\n"
            "from typing import TYPE_CHECKING\n"
            "\n"
            "if TYPE_CHECKING:\n"
            "    from .module import MyClass\n"
            "\n"
            "def foo(x: MyClass) -> None:\n"
            "    pass\n"
        )
        from anvil.services.vault.check_guarded_imports import main

        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 0