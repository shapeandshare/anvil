# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for the import-placement checker.

Tests ``_scan_source_for_imports``, ``scan_file``, ``scan_directory``,
and the ``main`` CLI entry point.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from anvil.services.vault.check_import_placement import (
    LazyImport,
    ScanResult,
    _scan_source_for_imports,
    scan_directory,
    scan_file,
)

########################################################################
# _scan_source_for_imports tests
########################################################################


class TestScanSourceForImports:
    """Tests for the _scan_source_for_imports helper."""

    def test_all_imports_at_top(self) -> None:
        """All imports before first definition - no violations."""
        source = """import os
from pathlib import Path

def foo() -> None:
    pass
"""
        violations = _scan_source_for_imports(source, "test.py")
        assert len(violations) == 0

    def test_lazy_import_flagged(self) -> None:
        """Import after first function definition is flagged."""
        source = """import os

def foo() -> None:
    pass

import sys
"""
        violations = _scan_source_for_imports(source, "test.py")
        assert len(violations) == 1
        assert violations[0].statement == "import sys"
        assert violations[0].line == 6

    def test_lazy_import_in_function_body(self) -> None:
        """Import inside a function body is flagged."""
        source = """def foo() -> None:
    import os
    pass
"""
        violations = _scan_source_for_imports(source, "test.py")
        assert len(violations) == 1
        assert "import os" in violations[0].statement

    def test_try_except_import_allowed(self) -> None:
        """Import inside try/except ImportError is allowed."""
        source = """def foo() -> None:
    try:
        import optional_dep
    except ImportError:
        pass
"""
        violations = _scan_source_for_imports(source, "test.py")
        assert len(violations) == 0

    def test_try_except_rexported(self) -> None:
        """Import inside try/except ImportError block is allowed."""
        source = """def foo() -> None:
    try:
        from optional import dep
    except ImportError:
        pass
"""
        violations = _scan_source_for_imports(source, "test.py")
        assert len(violations) == 0

    def test_type_checking_block_allowed(self) -> None:
        """Import inside if TYPE_CHECKING block is allowed."""
        source = """from __future__ import annotations
from typing import TYPE_CHECKING

def foo() -> None:
    if TYPE_CHECKING:
        from .module import MyClass
    pass
"""
        violations = _scan_source_for_imports(source, "test.py")
        assert len(violations) == 0

    def test_suppression_comment_allowed(self) -> None:
        """Import after # import-placement:allow comment is allowed."""
        source = """def foo() -> None:
    pass

# import-placement:allow
import sys
"""
        violations = _scan_source_for_imports(source, "test.py")
        assert len(violations) == 0

    def test_no_definitions_no_violations(self) -> None:
        """File without definitions has no violations."""
        source = "import os\nimport sys\n"
        violations = _scan_source_for_imports(source, "test.py")
        assert len(violations) == 0

    def test_async_function_triggers_boundary(self) -> None:
        """Async def starts the boundary."""
        source = """import os

async def foo() -> None:
    pass

import sys
"""
        violations = _scan_source_for_imports(source, "test.py")
        assert len(violations) == 1

    def test_decorator_triggers_boundary(self) -> None:
        """Decorator starts the boundary."""
        source = """import os

@decorator
def foo() -> None:
    pass

import sys
"""
        violations = _scan_source_for_imports(source, "test.py")
        assert len(violations) == 1

    def test_class_definition_triggers_boundary(self) -> None:
        """Class definition starts the boundary."""
        source = """import os

class MyClass:
    pass

import sys
"""
        violations = _scan_source_for_imports(source, "test.py")
        assert len(violations) == 1

    def test_allow_comment_does_not_suppress_multiple_lines(self) -> None:
        """Suppression only applies to the next import."""
        source = """def foo():
    pass

# import-placement:allow
import os
import sys
"""
        violations = _scan_source_for_imports(source, "test.py")
        assert len(violations) == 1

    def test_generic_except_closes_context(self) -> None:
        """Generic except closes the import-error context."""
        source = """def foo():
    try:
        pass
    except:
        import os
"""
        violations = _scan_source_for_imports(source, "test.py")
        assert len(violations) == 1

    def test_multiple_violations(self) -> None:
        """Multiple lazy imports are all flagged."""
        source = """def foo():
    pass

import os
import sys
"""
        violations = _scan_source_for_imports(source, "test.py")
        assert len(violations) == 2


########################################################################
# scan_file tests
########################################################################


class TestScanFile:
    """Tests for the scan_file function."""

    def test_clean_file(self, tmp_path: Path) -> None:
        """Clean file returns result with no violations."""
        p = tmp_path / "test.py"
        p.write_text("import os\n\ndef foo() -> None:\n    pass\n")
        result = scan_file(p)
        assert isinstance(result, ScanResult)
        assert len(result.violations) == 0

    def test_violation_detected(self, tmp_path: Path) -> None:
        """File with lazy import returns violation."""
        p = tmp_path / "test.py"
        p.write_text("def foo() -> None:\n    pass\n\nimport os\n")
        result = scan_file(p)
        assert len(result.violations) == 1

    def test_unreadable_file(self, tmp_path: Path) -> None:
        """Unreadable file returns violation for the read error."""
        p = tmp_path / "test.py"
        p.write_text("x = 1")
        p.chmod(0o000)
        result = scan_file(p)
        assert len(result.violations) == 1
        assert "cannot read" in result.violations[0].statement.lower()
        p.chmod(0o644)


########################################################################
# scan_directory tests
########################################################################


class TestScanDirectory:
    """Tests for the scan_directory function."""

    def test_empty_directory(self, tmp_path: Path) -> None:
        """Empty directory returns empty results."""
        results = scan_directory(tmp_path)
        assert len(results) == 0

    def test_multiple_files(self, tmp_path: Path) -> None:
        """Multiple files are scanned."""
        (tmp_path / "a.py").write_text("import os\n\ndef foo(): pass\n")
        (tmp_path / "b.py").write_text("import sys\n\ndef bar(): pass\n")
        results = scan_directory(tmp_path)
        assert len(results) == 2

    def test_recursive_scan(self, tmp_path: Path) -> None:
        """Files in subdirectories are scanned."""
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "deep.py").write_text("import os\n\ndef foo(): pass\n")
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
        p.write_text("import os\n\ndef foo() -> None:\n    pass\n")
        from anvil.services.vault.check_import_placement import main

        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 0

    def test_violation_exits_1(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Directory with violations exits with code 1."""
        monkeypatch.setenv("ANVIL_ROOT", str(tmp_path))
        p = tmp_path / "test.py"
        p.write_text("def foo() -> None:\n    pass\n\nimport os\n")
        from anvil.services.vault.check_import_placement import main

        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 1

    def test_nonexistent_root_exits_1(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Non-existent root directory exits with code 1."""
        monkeypatch.setenv("ANVIL_ROOT", str(tmp_path / "nonexistent"))
        monkeypatch.chdir(tmp_path)
        from anvil.services.vault.check_import_placement import main

        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 1
