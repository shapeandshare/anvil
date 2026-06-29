# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for the relative-imports checker.

Tests ``_in_triple_quoted``, ``scan_file``, ``scan_directory``,
and the ``main`` CLI entry point.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from anvil.services.vault.check_relative_imports import (
    AbsoluteImport,
    ScanResult,
    _in_triple_quoted,
    scan_directory,
    scan_file,
)

########################################################################
# _in_triple_quoted tests
########################################################################


class TestInTripleQuoted:
    """Tests for the _in_triple_quoted helper."""

    def test_not_in_docstring(self) -> None:
        """Line outside a docstring returns False."""
        source = "import os\nx = 1\n"
        assert _in_triple_quoted(source, 1) is False

    def test_inside_docstring(self) -> None:
        """Line inside a triple-quoted docstring returns True."""
        source = '"""\ninside\ndocstring\n"""\nx = 1\n'
        assert _in_triple_quoted(source, 2) is True

    def test_after_docstring(self) -> None:
        """Line after the docstring ends returns False."""
        source = '"""\ndocstring\n"""\nx = 1\n'
        assert _in_triple_quoted(source, 4) is False

    def test_single_line_docstring(self) -> None:
        """Line on a single-line docstring returns True."""
        source = '"""docstring"""\nx = 1\n'
        assert _in_triple_quoted(source, 1) is True

    def test_approximate_docstring_tracking(self) -> None:
        """Approximately tracks multiple docstrings (single-line not closed)."""
        source = '"""first"""\nx = 1\n"""second"""\ny = 2\n'
        # For lineno=1: stripped starts with """ -> in_docstring = True, i >= 1 -> True
        assert _in_triple_quoted(source, 1) is True
        # For lineno=2: still inside the open """first""" (single-line not closed) -> True
        assert _in_triple_quoted(source, 2) is True
        # For lineno=3: stripped starts with """ -> toggles in_docstring = False, i >= 3 -> False
        assert _in_triple_quoted(source, 3) is False
        # For lineno=4: in_docstring already False -> False
        assert _in_triple_quoted(source, 4) is False

    def test_single_quotes_docstring(self) -> None:
        """Triple-single-quoted docstrings are tracked."""
        source = "'''\ninside\n'''\nx = 1\n"
        assert _in_triple_quoted(source, 2) is True
        assert _in_triple_quoted(source, 4) is False


########################################################################
# scan_file tests
########################################################################


class TestScanFile:
    """Tests for the scan_file function."""

    def test_relative_import_pass(self, tmp_path: Path) -> None:
        """Relative imports are not flagged."""
        p = tmp_path / "test.py"
        p.write_text("from .module import X\nfrom ..parent import Y\n")
        result = scan_file(p)
        assert isinstance(result, ScanResult)
        assert len(result.violations) == 0

    def test_absolute_anvil_import_flagged(self, tmp_path: Path) -> None:
        """Absolute anvil. import inside package is flagged."""
        p = tmp_path / "test.py"
        p.write_text("from anvil.core import engine\n")
        result = scan_file(p)
        assert len(result.violations) == 1
        assert "from anvil.core" in result.violations[0].line_text

    def test_import_anvil_dot_flagged(self, tmp_path: Path) -> None:
        """import anvil.X is flagged."""
        p = tmp_path / "test.py"
        p.write_text("import anvil.core\n")
        result = scan_file(p)
        assert len(result.violations) == 1
        assert "import anvil.core" in result.violations[0].line_text

    def test_type_checking_allowed(self, tmp_path: Path) -> None:
        """Absolute import inside TYPE_CHECKING block is allowed."""
        p = tmp_path / "test.py"
        p.write_text(
            "from __future__ import annotations\n"
            "from typing import TYPE_CHECKING\n"
            "\n"
            "if TYPE_CHECKING:\n"
            "    from anvil.services import MyClass\n"
            "\n"
            "def foo() -> None:\n"
            "    pass\n"
        )
        result = scan_file(p)
        assert len(result.violations) == 0

    def test_docstring_not_flagged(self, tmp_path: Path) -> None:
        """Absolute import inside docstring is not flagged."""
        p = tmp_path / "test.py"
        p.write_text('"""\n' "from anvil.core import engine\n" '"""\n' "x = 1\n")
        result = scan_file(p)
        assert len(result.violations) == 0

    def test_suppression_comment_allowed(self, tmp_path: Path) -> None:
        """Absolute import with suppression comment is allowed."""
        p = tmp_path / "test.py"
        p.write_text("from anvil.core import engine  # relative-imports:allow\n")
        result = scan_file(p)
        assert len(result.violations) == 0

    def test_comment_line_not_flagged(self, tmp_path: Path) -> None:
        """Absolute import in a comment is not flagged."""
        p = tmp_path / "test.py"
        p.write_text("# from anvil.core import engine\nx = 1\n")
        result = scan_file(p)
        assert len(result.violations) == 0

    def test_standard_lib_not_flagged(self, tmp_path: Path) -> None:
        """Non-anvil absolute imports are not flagged."""
        p = tmp_path / "test.py"
        p.write_text("import os\nfrom pathlib import Path\n")
        result = scan_file(p)
        assert len(result.violations) == 0

    def test_multiple_violations(self, tmp_path: Path) -> None:
        """Multiple absolute imports are all flagged."""
        p = tmp_path / "test.py"
        p.write_text(
            "from anvil.core import engine\n" "from anvil.services import training\n"
        )
        result = scan_file(p)
        assert len(result.violations) == 2

    def test_unreadable_file(self, tmp_path: Path) -> None:
        """Unreadable file returns empty result."""
        p = tmp_path / "test.py"
        p.write_text("x = 1")
        p.chmod(0o000)
        result = scan_file(p)
        assert len(result.violations) == 0
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
        (tmp_path / "a.py").write_text("from .module import X\n")
        (tmp_path / "b.py").write_text("from anvil.core import engine\n")
        results = scan_directory(tmp_path)
        assert len(results) == 2
        violations = sum(len(r.violations) for r in results)
        assert violations == 1

    def test_only_py_files(self, tmp_path: Path) -> None:
        """Non-.py files are skipped."""
        (tmp_path / "readme.md").write_text("# hello")
        (tmp_path / "main.py").write_text("from .module import X\n")
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
        p.write_text("from .module import X\n")
        from anvil.services.vault.check_relative_imports import main

        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 0

    def test_violation_exits_1(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Directory with violations exits with code 1."""
        monkeypatch.setenv("ANVIL_ROOT", str(tmp_path))
        p = tmp_path / "test.py"
        p.write_text("from anvil.core import engine\n")
        from anvil.services.vault.check_relative_imports import main

        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 1

    def test_nonexistent_root_exits_1(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Non-existent root directory exits with code 1."""
        monkeypatch.setenv("ANVIL_ROOT", str(tmp_path / "nonexistent"))
        monkeypatch.chdir(tmp_path)
        from anvil.services.vault.check_relative_imports import main

        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 1
