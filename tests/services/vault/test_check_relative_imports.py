# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for ``check_relative_imports`` — absolute import scanner."""

from __future__ import annotations

from pathlib import Path

from anvil.services.vault.check_relative_imports import scan_file


class TestRelativeImportPass:
    """Tests that relative imports are accepted."""

    def test_relative_import_from(self) -> None:
        source = "from .module import X\n"
        p = Path(_write_tmp(source))
        result = scan_file(p)
        assert result.violations == []

    def test_relative_import_from_parent(self) -> None:
        source = "from ..parent.module import Y\n"
        p = Path(_write_tmp(source))
        result = scan_file(p)
        assert result.violations == []

    def test_relative_import_blank_file(self) -> None:
        source = ""
        p = Path(_write_tmp(source))
        result = scan_file(p)
        assert result.violations == []

    def test_standard_library_import(self) -> None:
        source = "import os\nfrom pathlib import Path\n"
        p = Path(_write_tmp(source))
        result = scan_file(p)
        assert result.violations == []

    def test_third_party_import(self) -> None:
        source = "import pytest\nfrom fastapi import APIRouter\n"
        p = Path(_write_tmp(source))
        result = scan_file(p)
        assert result.violations == []

    def test_relative_import_pass(self) -> None:
        source = "from .module import X\nfrom ..parent import Y\n"
        p = Path(_write_tmp(source))
        result = scan_file(p)
        assert result.violations == []


class TestAbsoluteImportFail:
    """Tests that absolute ``from anvil.`` imports are flagged."""

    def test_from_anvil_import(self) -> None:
        source = "from anvil.module import X\n"
        p = Path(_write_tmp(source))
        result = scan_file(p)
        assert len(result.violations) == 1
        assert result.violations[0].line == 1
        assert result.violations[0].line_text == "from anvil.module import X"

    def test_from_anvil_deep_import(self) -> None:
        source = "from anvil.services.vault.check_relative_imports import scan_file\n"
        p = Path(_write_tmp(source))
        result = scan_file(p)
        assert len(result.violations) == 1
        assert result.violations[0].line == 1

    def test_absolute_import_fail(self) -> None:
        source = "from anvil.module import X\n"
        p = Path(_write_tmp(source))
        result = scan_file(p)
        assert len(result.violations) == 1

    def test_multiple_absolute_imports(self) -> None:
        source = (
            "from anvil.foo import A\n"
            "from .bar import B\n"
            "from anvil.baz import C\n"
        )
        p = Path(_write_tmp(source))
        result = scan_file(p)
        assert len(result.violations) == 2

    def test_indented_absolute_import(self) -> None:
        source = "    from anvil.module import X\n"
        p = Path(_write_tmp(source))
        result = scan_file(p)
        assert len(result.violations) == 1


class TestImportAnvilFail:
    """Tests that ``import anvil.`` statements are flagged."""

    def test_import_anvil_module(self) -> None:
        source = "import anvil.module\n"
        p = Path(_write_tmp(source))
        result = scan_file(p)
        assert len(result.violations) == 1
        assert result.violations[0].line_text == "import anvil.module"

    def test_import_anvil_fail(self) -> None:
        source = "import anvil.module\n"
        p = Path(_write_tmp(source))
        result = scan_file(p)
        assert len(result.violations) == 1

    def test_import_anvil_deep(self) -> None:
        source = "import anvil.services.vault\n"
        p = Path(_write_tmp(source))
        result = scan_file(p)
        assert len(result.violations) == 1


class TestTypeCheckingImportAllowed:
    """Tests that absolute imports inside ``if TYPE_CHECKING:`` are allowed."""

    def test_type_checking_from_import(self) -> None:
        source = (
            "from __future__ import annotations\n"
            "from typing import TYPE_CHECKING\n"
            "\n"
            "if TYPE_CHECKING:\n"
            "    from anvil.module import X\n"
        )
        p = Path(_write_tmp(source))
        result = scan_file(p)
        assert result.violations == []

    def test_type_checking_multi_line(self) -> None:
        source = (
            "if TYPE_CHECKING:\n"
            "    from anvil.foo import A\n"
            "    from anvil.bar import B\n"
            "\n"
            "from .real import C\n"
        )
        p = Path(_write_tmp(source))
        result = scan_file(p)
        assert result.violations == []

    def test_type_checking_import_allowed(self) -> None:
        source = (
            "from __future__ import annotations\n"
            "from typing import TYPE_CHECKING\n"
            "\n"
            "if TYPE_CHECKING:\n"
            "    from anvil.module import X\n"
            "    from anvil.other import Y\n"
        )
        p = Path(_write_tmp(source))
        result = scan_file(p)
        assert result.violations == []

    def test_type_checking_exited_before_absolute(self) -> None:
        source = (
            "if TYPE_CHECKING:\n"
            "    from anvil.foo import A\n"
            "\n"
            "from anvil.bar import B\n"
        )
        p = Path(_write_tmp(source))
        result = scan_file(p)
        assert len(result.violations) == 1
        assert "anvil.bar" in result.violations[0].line_text


class TestCommentLineSkipped:
    """Tests that comment lines are not scanned."""

    def test_comment_with_absolute_import(self) -> None:
        source = "# from anvil.module import X\n"
        p = Path(_write_tmp(source))
        result = scan_file(p)
        assert result.violations == []

    def test_inline_comment_after_code(self) -> None:
        source = "from .module import X  # from anvil.module import X\n"
        p = Path(_write_tmp(source))
        result = scan_file(p)
        assert result.violations == []

    def test_comment_line_skipped(self) -> None:
        source = "# from anvil.module import X\n"
        p = Path(_write_tmp(source))
        result = scan_file(p)
        assert result.violations == []

    def test_comment_block_with_imports(self) -> None:
        source = (
            "# TODO: change to: from anvil.foo import A\n"
            "#  from anvil.bar import B\n"
            "from .real import C\n"
        )
        p = Path(_write_tmp(source))
        result = scan_file(p)
        assert result.violations == []


class TestSuppressionComment:
    """Tests that ``# relative-imports:allow`` suppresses violations."""

    def test_suppressed_from_import(self) -> None:
        source = "from anvil.module import X  # relative-imports:allow\n"
        p = Path(_write_tmp(source))
        result = scan_file(p)
        assert result.violations == []

    def test_suppressed_import(self) -> None:
        source = "import anvil.module  # relative-imports:allow\n"
        p = Path(_write_tmp(source))
        result = scan_file(p)
        assert result.violations == []

    def test_suppression_comment(self) -> None:
        source = "from anvil.module import X  # relative-imports:allow\n"
        p = Path(_write_tmp(source))
        result = scan_file(p)
        assert result.violations == []

    def test_unsuppressed_import_still_fails(self) -> None:
        source = (
            "from anvil.allowable import X  # relative-imports:allow\n"
            "from anvil.not_allowable import Y\n"
        )
        p = Path(_write_tmp(source))
        result = scan_file(p)
        assert len(result.violations) == 1
        assert "not_allowable" in result.violations[0].line_text


class TestImportInDocstringSkipped:
    """Tests that imports mentioned in docstrings are not flagged."""

    def test_module_docstring(self) -> None:
        source = (
            '\"\"\"Module docstring mentioning from anvil.module import X.\"\"\"\n'
            "from .real import X\n"
        )
        p = Path(_write_tmp(source))
        result = scan_file(p)
        assert result.violations == []

    def test_function_docstring(self) -> None:
        source = (
            "def foo():\n"
            '    """This uses ``from anvil.utils import helper`` internally."""\n'
            "    pass\n"
        )
        p = Path(_write_tmp(source))
        result = scan_file(p)
        assert result.violations == []

    def test_class_docstring(self) -> None:
        source = (
            "class MyClass:\n"
            '    """Accepts ``from anvil.models import Base`` as an example."""\n'
            "    pass\n"
        )
        p = Path(_write_tmp(source))
        result = scan_file(p)
        assert result.violations == []

    def test_multi_line_docstring(self) -> None:
        source = (
            '"""\n'
            "Multi-line docstring.\n"
            "\n"
            "Example::\n"
            "\n"
            "    from anvil.module import X\n"
            '"""\n'
            "from .real import X\n"
        )
        p = Path(_write_tmp(source))
        result = scan_file(p)
        assert result.violations == []

    def test_import_in_docstring_skipped(self) -> None:
        source = (
            '"""\n'
            "This module provides X.\n"
            "\n"
            "Usage::\n"
            "\n"
            "    from anvil.module import X\n"
            '"""\n'
        )
        p = Path(_write_tmp(source))
        result = scan_file(p)
        assert result.violations == []

    def test_docstring_then_real_absolute_still_fails(self) -> None:
        source = (
            '"""Docstring with from anvil.module import X."""\n'
            "from anvil.real_module import Y\n"
        )
        p = Path(_write_tmp(source))
        result = scan_file(p)
        assert len(result.violations) == 1
        assert "real_module" in result.violations[0].line_text


def _write_tmp(content: str) -> str:
    """Write *content* to a temporary ``.py`` file and return its path."""
    import tempfile

    with tempfile.NamedTemporaryFile(
        suffix=".py", mode="w", delete=False, encoding="utf-8"
    ) as f:
        f.write(content)
        return f.name
