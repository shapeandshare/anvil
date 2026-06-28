# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for package nesting depth checker."""

from __future__ import annotations

from pathlib import Path

from anvil.services.vault.check_nesting_depth import (
    NestingViolation,
    ScanResult,
    _get_package_depth,
    scan_directory,
)


class TestGetPackageDepth:
    """Tests for ``_get_package_depth``."""

    def test_root_depth_zero(self, tmp_path: Path) -> None:
        root = tmp_path / "anvil"
        root.mkdir()
        assert _get_package_depth(root, root) == 0

    def test_direct_child_with_init(self, tmp_path: Path) -> None:
        root = tmp_path / "anvil"
        root.mkdir()
        child = root / "core"
        child.mkdir()
        (child / "__init__.py").write_text("")
        assert _get_package_depth(root, child) == 1

    def test_child_without_init_not_counted(self) -> None:
        root = Path("/project/anvil")
        child = root / "core"

        original_exists = Path.exists

        def mock_exists(self: Path) -> bool:
            if self.name == "__init__.py":
                return self.parent.name == "anvil"
            return original_exists(self)

        Path.exists = mock_exists
        try:
            assert _get_package_depth(root, child) == 0
        finally:
            Path.exists = original_exists

    def test_two_levels_deep(self, tmp_path: Path) -> None:
        root = tmp_path / "anvil"
        root.mkdir()
        child = root / "services" / "vault"
        child.mkdir(parents=True)
        (root / "services" / "__init__.py").write_text("")
        (child / "__init__.py").write_text("")
        assert _get_package_depth(root, child) == 2

    def test_skip_non_package_parent(self, tmp_path: Path) -> None:
        root = tmp_path / "anvil"
        root.mkdir()
        svc = root / "services"
        svc.mkdir()
        vault = svc / "vault"
        vault.mkdir()
        (vault / "__init__.py").write_text("")
        assert _get_package_depth(root, vault) == 1

    def test_no_init_on_any_level(self) -> None:
        root = Path("/project/anvil")
        child = root / "a" / "b" / "c"

        def no_inits(self: Path) -> bool:
            return self.name != "__init__.py"

        original_exists = Path.exists
        Path.exists = no_inits
        try:
            assert _get_package_depth(root, child) == 0
        finally:
            Path.exists = original_exists

    def test_all_levels_have_init(self) -> None:
        root = Path("/project/anvil")
        child = root / "a" / "b" / "c"

        def all_inits(self: Path) -> bool:
            return True

        original_exists = Path.exists
        Path.exists = all_inits
        try:
            assert _get_package_depth(root, child) == 3
        finally:
            Path.exists = original_exists


class TestScanDirectory:
    """Tests for ``scan_directory``."""

    def test_depth_one_pass(self, tmp_path: Path) -> None:
        root = tmp_path / "anvil"
        root.mkdir()
        pkg1 = root / "pkg1"
        pkg1.mkdir()
        (pkg1 / "__init__.py").write_text("")
        result = scan_directory(root)
        assert result.violations == []

    def test_depth_two_pass(self, tmp_path: Path) -> None:
        root = tmp_path / "anvil"
        root.mkdir()
        pkg1 = root / "pkg1"
        pkg1.mkdir()
        (pkg1 / "__init__.py").write_text("")
        pkg2 = pkg1 / "pkg2"
        pkg2.mkdir()
        (pkg2 / "__init__.py").write_text("")
        result = scan_directory(root)
        assert result.violations == []

    def test_depth_three_fail(self, tmp_path: Path) -> None:
        root = tmp_path / "anvil"
        root.mkdir()
        pkg1 = root / "pkg1"
        pkg1.mkdir()
        (pkg1 / "__init__.py").write_text("")
        pkg2 = pkg1 / "pkg2"
        pkg2.mkdir()
        (pkg2 / "__init__.py").write_text("")
        pkg3 = pkg2 / "pkg3"
        pkg3.mkdir()
        (pkg3 / "__init__.py").write_text("")
        result = scan_directory(root)
        assert len(result.violations) == 1
        assert result.violations[0].depth == 3
        assert "pkg3" in result.violations[0].path

    def test_depth_four_fail(self, tmp_path: Path) -> None:
        root = tmp_path / "anvil"
        root.mkdir()
        p = root
        for part in ("a", "b", "c", "d"):
            p = p / part
            p.mkdir()
            (p / "__init__.py").write_text("")
        result = scan_directory(root)
        assert len(result.violations) == 2
        depths = {v.depth for v in result.violations}
        assert depths == {3, 4}

    def test_no_init_py_not_counted(self, tmp_path: Path) -> None:
        root = tmp_path / "anvil"
        root.mkdir()
        pkg1 = root / "pkg1"
        pkg1.mkdir()
        (pkg1 / "__init__.py").write_text("")
        non_pkg = pkg1 / "non_pkg"
        non_pkg.mkdir()
        pkg2 = non_pkg / "pkg2"
        pkg2.mkdir()
        (pkg2 / "__init__.py").write_text("")
        result = scan_directory(root)
        assert result.violations == []

    def test_skip_known_dirs(self, tmp_path: Path) -> None:
        root = tmp_path / "anvil"
        root.mkdir()
        pkg1 = root / "pkg1"
        pkg1.mkdir()
        (pkg1 / "__init__.py").write_text("")
        for skipped in ("__pycache__", ".git", "mlruns", "logs", "_meta",
                        ".obsidian", "addons"):
            d = root / skipped
            d.mkdir()
            (d / "__init__.py").write_text("")
        result = scan_directory(root)
        assert result.violations == []

    def test_mixed_depth(self, tmp_path: Path) -> None:
        root = tmp_path / "anvil"
        root.mkdir()
        a = root / "a"
        a.mkdir()
        (a / "__init__.py").write_text("")
        (a / "b").mkdir()
        (a / "b" / "__init__.py").write_text("")
        c = root / "c"
        c.mkdir()
        (c / "__init__.py").write_text("")
        d = c / "d"
        d.mkdir()
        (d / "__init__.py").write_text("")
        e = d / "e"
        e.mkdir()
        (e / "__init__.py").write_text("")
        f = root / "f"
        f.mkdir()
        (f / "__init__.py").write_text("")
        result = scan_directory(root)
        assert len(result.violations) == 1
        assert result.violations[0].depth == 3
        assert "e" in result.violations[0].path

    def test_empty_root_no_violations(self, tmp_path: Path) -> None:
        root = tmp_path / "anvil"
        root.mkdir()
        result = scan_directory(root)
        assert result.violations == []

    def test_nested_without_init_on_inner(self, tmp_path: Path) -> None:
        root = tmp_path / "anvil"
        root.mkdir()
        a = root / "a"
        a.mkdir()
        (a / "__init__.py").write_text("")
        b = a / "b"
        b.mkdir()
        result = scan_directory(root)
        assert result.violations == []

    def test_skip_dir_inside_package_does_not_affect_depth(
        self, tmp_path: Path
    ) -> None:
        root = tmp_path / "anvil"
        root.mkdir()
        a = root / "a"
        a.mkdir()
        (a / "__init__.py").write_text("")
        pycache = a / "__pycache__"
        pycache.mkdir()
        (pycache / "__init__.py").write_text("")
        b = a / "b"
        b.mkdir()
        (b / "__init__.py").write_text("")
        result = scan_directory(root)
        assert result.violations == []