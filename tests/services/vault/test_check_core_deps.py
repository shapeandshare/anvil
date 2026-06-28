# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for check_core_deps.py — stdlib-only import enforcement."""

from __future__ import annotations

from pathlib import Path

from anvil.services.vault.check_core_deps import (
    DepViolation,
    FileCheckResult,
    ImportStatement,
    _extract_imports,
    _is_intra_package,
    _top_level_module,
    check_directory,
    check_file,
)


class TestTopLevelModule:
    """Tests for ``_top_level_module``."""

    def test_simple_name(self) -> None:
        assert _top_level_module("os") == "os"

    def test_dotted_path(self) -> None:
        assert _top_level_module("os.path") == "os"

    def test_deep_dotted(self) -> None:
        assert _top_level_module("collections.abc.def") == "collections"


class TestIsIntraPackage:
    """Tests for ``_is_intra_package``."""

    def test_relative_import(self) -> None:
        assert _is_intra_package(".sibling") is True

    def test_relative_deep_import(self) -> None:
        assert _is_intra_package("..parent.module") is True

    def test_anvil_namespace(self) -> None:
        assert _is_intra_package("anvil.core.engine") is True

    def test_anvil_root(self) -> None:
        assert _is_intra_package("anvil") is True

    def test_stdlib_not_intra(self) -> None:
        assert _is_intra_package("os") is False

    def test_third_party_not_intra(self) -> None:
        assert _is_intra_package("torch") is False


class TestExtractImports:
    """Tests for ``_extract_imports``."""

    def test_import_x(self) -> None:
        source = "import os\nimport math\n"
        imports = _extract_imports(source, "test.py")
        assert len(imports) == 2
        assert imports[0].module == "os"
        assert imports[1].module == "math"

    def test_from_import(self) -> None:
        source = "from typing import List\n"
        imports = _extract_imports(source, "test.py")
        assert len(imports) == 1
        assert imports[0].module == "typing"

    def test_type_checking_guard_excluded(self) -> None:
        source = (
            "import os\n"
            "if TYPE_CHECKING:\n"
            "    from torch import Tensor\n"
            "import math\n"
        )
        imports = _extract_imports(source, "test.py")
        modules = [i.module for i in imports]
        assert "torch" not in modules
        assert modules == ["os", "math"]

    def test_empty_source(self) -> None:
        assert _extract_imports("", "test.py") == []

    def test_no_imports(self) -> None:
        source = "x = 1\ndef foo(): pass\n"
        assert _extract_imports(source, "test.py") == []


class TestCheckFile:
    """Tests for ``check_file``."""

    def test_stdlib_import_pass(self, tmp_path: Path) -> None:
        p = tmp_path / "mod.py"
        p.write_text("import os\nimport math\nfrom typing import List\n")
        result = check_file(p)
        assert result.violations == []

    def test_third_party_import_fail(self, tmp_path: Path) -> None:
        p = tmp_path / "mod.py"
        p.write_text("import torch\n")
        result = check_file(p)
        assert len(result.violations) == 1
        v = result.violations[0]
        assert v.module == "torch"
        assert "torch" in v.raw

    def test_from_third_party_fail(self, tmp_path: Path) -> None:
        p = tmp_path / "mod.py"
        p.write_text("from numpy import array\n")
        result = check_file(p)
        assert len(result.violations) == 1
        v = result.violations[0]
        assert v.module == "numpy"

    def test_future_annotations_skipped(self, tmp_path: Path) -> None:
        p = tmp_path / "mod.py"
        p.write_text("from __future__ import annotations\nimport os\n")
        result = check_file(p)
        assert result.violations == []

    def test_relative_import_skipped(self, tmp_path: Path) -> None:
        p = tmp_path / "mod.py"
        p.write_text("from .sibling import helper\nimport os\n")
        result = check_file(p)
        assert result.violations == []

    def test_intra_package_import_skipped(self, tmp_path: Path) -> None:
        p = tmp_path / "mod.py"
        p.write_text("from anvil.core.engine import LlamaModel\nimport math\n")
        result = check_file(p)
        assert result.violations == []

    def test_type_checking_import_skipped(self, tmp_path: Path) -> None:
        p = tmp_path / "mod.py"
        p.write_text(
            "import os\n"
            "if TYPE_CHECKING:\n"
            "    from torch import Tensor\n"
            "import math\n"
        )
        result = check_file(p)
        assert result.violations == []

    def test_mixed_imports(self, tmp_path: Path) -> None:
        p = tmp_path / "mod.py"
        p.write_text(
            "import os\n"
            "import torch\n"
            "import math\n"
            "from numpy import array\n"
            "import sys\n"
        )
        result = check_file(p)
        assert len(result.violations) == 2
        modules = {v.module for v in result.violations}
        assert modules == {"torch", "numpy"}

    def test_unreadable_file(self, tmp_path: Path) -> None:
        p = tmp_path / "nonexistent.py"
        result = check_file(p)
        assert result.violations == []


class TestCheckDirectory:
    """Tests for ``check_directory``."""

    def test_clean_directory(self, tmp_path: Path) -> None:
        d = tmp_path / "core"
        d.mkdir()
        (d / "a.py").write_text("import os\n")
        (d / "sub").mkdir()
        (d / "sub" / "b.py").write_text("from typing import Optional\n")
        results = check_directory(d)
        assert all(len(r.violations) == 0 for r in results)

    def test_directory_with_violations(self, tmp_path: Path) -> None:
        d = tmp_path / "core"
        d.mkdir()
        (d / "a.py").write_text("import os\n")
        (d / "b.py").write_text("import torch\n")
        results = check_directory(d)
        violations = [(r.path, len(r.violations)) for r in results]
        assert sum(count for _, count in violations) == 1

    def test_non_py_files_skipped(self, tmp_path: Path) -> None:
        d = tmp_path / "core"
        d.mkdir()
        (d / "a.py").write_text("import os\n")
        (d / "data.txt").write_text("not python\n")
        results = check_directory(d)
        assert len(results) == 1
        assert results[0].violations == []