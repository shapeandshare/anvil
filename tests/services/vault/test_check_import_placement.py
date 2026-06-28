# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for ``check_import_placement`` — lazy import detection."""

from __future__ import annotations

from pathlib import Path

from anvil.services.vault.check_import_placement import (
    _scan_source_for_imports,
    scan_file,
)


class TestScanSourceForImports:
    """Tests for ``_scan_source_for_imports``."""

    def test_top_of_file_imports_pass(self) -> None:
        source = (
            "import os\n"
            "import sys\n"
            "from pathlib import Path\n"
            "\n"
            "def foo() -> None:\n"
            "    pass\n"
        )
        violations = _scan_source_for_imports(source, "test.py")
        assert violations == []

    def test_lazy_import_after_def_fail(self) -> None:
        source = (
            "import os\n"
            "\n"
            "def foo() -> None:\n"
            "    pass\n"
            "\n"
            "import sys\n"
        )
        violations = _scan_source_for_imports(source, "test.py")
        assert len(violations) == 1
        assert violations[0].line == 6
        assert violations[0].statement == "import sys"

    def test_try_import_error_allowed(self) -> None:
        source = (
            "import os\n"
            "\n"
            "def foo() -> None:\n"
            "    pass\n"
            "\n"
            "try:\n"
            "    import sys\n"
            "except ImportError:\n"
            "    pass\n"
        )
        violations = _scan_source_for_imports(source, "test.py")
        assert violations == []

    def test_type_checking_import_allowed(self) -> None:
        source = (
            "from __future__ import annotations\n"
            "from typing import TYPE_CHECKING\n"
            "\n"
            "def foo() -> None:\n"
            "    pass\n"
            "\n"
            "if TYPE_CHECKING:\n"
            "    from pathlib import Path\n"
        )
        violations = _scan_source_for_imports(source, "test.py")
        assert violations == []

    def test_suppression_comment_allowed(self) -> None:
        source = (
            "import os\n"
            "\n"
            "def foo() -> None:\n"
            "    pass\n"
            "\n"
            "# import-placement:allow\n"
            "import sys\n"
        )
        violations = _scan_source_for_imports(source, "test.py")
        assert violations == []

    def test_multiple_defs_lazy_import(self) -> None:
        source = (
            "import os\n"
            "\n"
            "def foo() -> None:\n"
            "    pass\n"
            "\n"
            "def bar() -> None:\n"
            "    pass\n"
            "\n"
            "import sys\n"
        )
        violations = _scan_source_for_imports(source, "test.py")
        assert len(violations) == 1
        assert violations[0].line == 9
        assert violations[0].statement == "import sys"

    def test_class_definition_triggers(self) -> None:
        source = (
            "import os\n"
            "\n"
            "class MyClass:\n"
            "    pass\n"
            "\n"
            "import sys\n"
        )
        violations = _scan_source_for_imports(source, "test.py")
        assert len(violations) == 1
        assert violations[0].line == 6
        assert violations[0].statement == "import sys"


class TestScanFile:
    """Tests for ``scan_file``."""

    def clean_file(self) -> str:
        return "import os\nimport sys\n\n\ndef foo() -> None:\n    pass\n"

    def lazy_file(self) -> str:
        return (
            "import os\n"
            "\n"
            "def foo() -> None:\n"
            "    pass\n"
            "\n"
            "import sys\n"
        )

    def test_clean_file_no_violations(self, tmp_path: Path) -> None:
        p = tmp_path / "clean.py"
        p.write_text(self.clean_file())
        result = scan_file(p)
        assert result.violations == []

    def test_lazy_file_reports_violations(self, tmp_path: Path) -> None:
        p = tmp_path / "lazy.py"
        p.write_text(self.lazy_file())
        result = scan_file(p)
        assert len(result.violations) == 1
        assert result.violations[0].line == 6

    def test_nonexistent_file_reports_error(self, tmp_path: Path) -> None:
        p = tmp_path / "nonexistent.py"
        result = scan_file(p)
        assert len(result.violations) == 1
        assert "cannot read" in result.violations[0].statement

    def test_empty_file_no_violations(self, tmp_path: Path) -> None:
        p = tmp_path / "empty.py"
        p.write_text("")
        result = scan_file(p)
        assert result.violations == []

    def test_no_definitions_no_violations(self, tmp_path: Path) -> None:
        p = tmp_path / "module.py"
        p.write_text("import os\nimport sys\n")
        result = scan_file(p)
        assert result.violations == []