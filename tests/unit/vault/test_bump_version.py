# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for the auto-bump version logic.

Tests that ``bump_version.py`` correctly increments patch versions,
modifies ``pyproject.toml`` in-place, and prepends changelog entries.
"""

from __future__ import annotations

import os
import tempfile
from unittest.mock import patch

import pytest

from anvil.services.vault.bump_version import (
    BumpType,
    _bump,
    _bump_patch,
    _do_bump,
    _prepend_changelog,
    _update_pyproject,
    bump_main,
    main,
)


class TestBump:
    """Tests for the generic version increment helper."""

    def test_major_increment(self) -> None:
        """Major bumps reset minor and patch to 0."""
        assert _bump("0.1.5", BumpType.MAJOR) == "1.0.0"

    def test_minor_increment(self) -> None:
        """Minor bumps reset patch to 0."""
        assert _bump("0.1.5", BumpType.MINOR) == "0.2.0"

    def test_patch_increment(self) -> None:
        """Patch bumps increment patch by 1."""
        assert _bump("0.1.5", BumpType.PATCH) == "0.1.6"

    def test_major_from_any_version(self) -> None:
        """Major bump always produces X.0.0."""
        assert _bump("1.9.9", BumpType.MAJOR) == "2.0.0"
        assert _bump("0.0.1", BumpType.MAJOR) == "1.0.0"

    def test_minor_from_any_version(self) -> None:
        """Minor bump preserves major, resets patch."""
        assert _bump("2.5.100", BumpType.MINOR) == "2.6.0"

    def test_invalid_increment_raises(self) -> None:
        """Unknown increment type raises ValueError."""
        with pytest.raises(ValueError):
            _bump("0.1.0", "INVALID")

    def test_invalid_format_raises(self) -> None:
        """Non-MAJOR.MINOR.PATCH strings raise ValueError."""
        with pytest.raises(ValueError):
            _bump("abc", BumpType.PATCH)
        with pytest.raises(ValueError):
            _bump("0.1", BumpType.PATCH)
        with pytest.raises(ValueError):
            _bump("0.1.0-beta", BumpType.PATCH)

    def test_large_numbers(self) -> None:
        """Very large version numbers increment correctly."""
        assert _bump("999.999.999", BumpType.PATCH) == "999.999.1000"
        assert _bump("999.999.999", BumpType.MINOR) == "999.1000.0"
        assert _bump("999.999.999", BumpType.MAJOR) == "1000.0.0"

    def test_zero_zero_zero(self) -> None:
        """Starting from 0.0.0 for all bump types."""
        assert _bump("0.0.0", BumpType.MAJOR) == "1.0.0"
        assert _bump("0.0.0", BumpType.MINOR) == "0.1.0"
        assert _bump("0.0.0", BumpType.PATCH) == "0.0.1"


class TestBumpPatch:
    """Tests for the convenience patch-only wrapper."""

    def test_patch_increment(self) -> None:
        """Patch component increments by 1."""
        assert _bump_patch("0.1.0") == "0.1.1"

    def test_rollover_keeps_major_minor(self) -> None:
        """Patch rollover (9 -> 10) does not affect major or minor."""
        assert _bump_patch("1.9.9") == "1.9.10"

    def test_zero_start(self) -> None:
        """Starting from 0.0.0 produces 0.0.1."""
        assert _bump_patch("0.0.0") == "0.0.1"

    def test_large_patch(self) -> None:
        """Large patch values increment correctly."""
        assert _bump_patch("2.5.999") == "2.5.1000"

    def test_calls_bump(self) -> None:
        """_bump_patch is equivalent to calling _bump with PATCH."""
        assert _bump_patch("3.2.1") == _bump("3.2.1", BumpType.PATCH)


class TestUpdatePyproject:
    """Tests for in-place pyproject.toml version replacement."""

    def test_replaces_version_line(self) -> None:
        """The version line is updated to the new value."""
        content = 'version = "0.1.0"\n'
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write(content)
            path = f.name
        try:
            _update_pyproject(path, "0.1.1", "0.1.0")
            with open(path) as f:
                assert 'version = "0.1.1"' in f.read()
        finally:
            os.unlink(path)

    def test_preserves_other_content(self) -> None:
        """Lines not containing version are left untouched."""
        content = 'name = "anvil"\nversion = "0.1.0"\ndescription = "test"\n'
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write(content)
            path = f.name
        try:
            _update_pyproject(path, "0.1.1", "0.1.0")
            with open(path) as f:
                text = f.read()
            assert 'name = "anvil"' in text
            assert 'description = "test"' in text
        finally:
            os.unlink(path)

    def test_missing_old_version_raises(self) -> None:
        """Replacement fails loudly when old version is absent."""
        content = 'version = "0.2.0"\n'
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write(content)
            path = f.name
        try:
            with pytest.raises(RuntimeError):
                _update_pyproject(path, "0.2.1", "0.1.0")
        finally:
            os.unlink(path)

    def test_preserves_whitespace_and_formatting(self) -> None:
        """Whitespace and formatting around version line is preserved."""
        content = 'version = "1.0.0"\n'
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write(content)
            path = f.name
        try:
            _update_pyproject(path, "2.0.0", "1.0.0")
            with open(path) as f:
                assert f.read() == 'version = "2.0.0"\n'
        finally:
            os.unlink(path)


class TestPrependChangelog:
    """Tests for changelog prepend behavior."""

    def test_prepends_entry(self) -> None:
        """Changelog entry is prepended above existing content."""
        existing = "# Changelog\n\nExisting content.\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(existing)
            path = f.name
        try:
            _prepend_changelog(path, "0.1.1")
            with open(path) as f:
                text = f.read()
            assert text.startswith("## v0.1.1 (")
            assert "### Features" in text
            assert "# Changelog" in text
        finally:
            os.unlink(path)

    def test_major_changelog_message(self) -> None:
        """Major increments get the correct label in the changelog."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# Changelog\n")
            path = f.name
        try:
            _prepend_changelog(path, "1.0.0", increment=BumpType.MAJOR)
            with open(path) as f:
                text = f.read()
            assert "major bump" in text
        finally:
            os.unlink(path)

    def test_minor_changelog_message(self) -> None:
        """Minor increments get the correct label in the changelog."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# Changelog\n")
            path = f.name
        try:
            _prepend_changelog(path, "0.2.0", increment=BumpType.MINOR)
            with open(path) as f:
                text = f.read()
            assert "minor bump" in text
        finally:
            os.unlink(path)

    def test_patch_default_label(self) -> None:
        """Patch default label is 'patch'."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# Changelog\n")
            path = f.name
        try:
            _prepend_changelog(path, "0.1.1", increment=BumpType.PATCH)
            with open(path) as f:
                text = f.read()
            assert "patch bump" in text
        finally:
            os.unlink(path)

    def test_unknown_increment_falls_back_to_patch(self) -> None:
        """An unknown increment value falls back to 'patch' label."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# Changelog\n")
            path = f.name
        try:
            _prepend_changelog(path, "0.1.1", increment="UNKNOWN")
            with open(path) as f:
                text = f.read()
            assert "patch bump" in text
        finally:
            os.unlink(path)


class TestDoBump:
    """Tests for the _do_bump orchestrator."""

    def test_returns_old_and_new_version(self, tmp_path: str) -> None:
        """_do_bump returns (old_version, new_version) tuple."""
        pyproject = os.path.join(tmp_path, "pyproject.toml")
        changelog = os.path.join(tmp_path, "CHANGELOG.md")
        with open(pyproject, "w") as f:
            f.write('version = "0.1.0"\n')
        with open(changelog, "w") as f:
            f.write("# Changelog\n")

        old, new = _do_bump(
            BumpType.PATCH,
            pyproject_path=pyproject,
            changelog_path=changelog,
        )
        assert old == "0.1.0"
        assert new == "0.1.1"

    def test_updates_pyproject_inplace(self, tmp_path: str) -> None:
        """_do_bump writes the new version into pyproject.toml."""
        pyproject = os.path.join(tmp_path, "pyproject.toml")
        changelog = os.path.join(tmp_path, "CHANGELOG.md")
        with open(pyproject, "w") as f:
            f.write('version = "1.0.0"\n')
        with open(changelog, "w") as f:
            f.write("# Changelog\n")

        _do_bump(
            BumpType.MINOR,
            pyproject_path=pyproject,
            changelog_path=changelog,
        )
        with open(pyproject) as f:
            assert 'version = "1.1.0"' in f.read()

    def test_prepends_changelog(self, tmp_path: str) -> None:
        """_do_bump prepends to the changelog."""
        pyproject = os.path.join(tmp_path, "pyproject.toml")
        changelog = os.path.join(tmp_path, "CHANGELOG.md")
        with open(pyproject, "w") as f:
            f.write('version = "0.5.0"\n')
        with open(changelog, "w") as f:
            f.write("# Changelog\n")

        _do_bump(
            BumpType.MAJOR,
            pyproject_path=pyproject,
            changelog_path=changelog,
        )
        with open(changelog) as f:
            text = f.read()
        assert text.startswith("## v1.0.0")

    def test_missing_pyproject_exits(self, tmp_path: str) -> None:
        """When pyproject.toml is missing, _do_bump calls sys.exit(1)."""
        missing_path = os.path.join(tmp_path, "nonexistent.toml")
        changelog = os.path.join(tmp_path, "CHANGELOG.md")
        with open(changelog, "w") as f:
            f.write("# Changelog\n")

        with pytest.raises(SystemExit) as exc_info:
            _do_bump(
                BumpType.PATCH,
                pyproject_path=missing_path,
                changelog_path=changelog,
            )
        assert exc_info.value.code == 1

    def test_invalid_version_exits(self, tmp_path: str) -> None:
        """When version format is invalid, ValueError propagates."""
        pyproject = os.path.join(tmp_path, "pyproject.toml")
        changelog = os.path.join(tmp_path, "CHANGELOG.md")
        with open(pyproject, "w") as f:
            f.write('version = "invalid"\n')
        with open(changelog, "w") as f:
            f.write("# Changelog\n")

        with pytest.raises(ValueError):
            _do_bump(
                BumpType.PATCH,
                pyproject_path=pyproject,
                changelog_path=changelog,
            )


class TestBumpMain:
    """Tests for the CLI entry point bump_main."""

    @patch("anvil.services.vault.bump_version._do_bump")
    def test_calls_do_bump(self, mock_do_bump) -> None:
        """bump_main calls _do_bump with the given increment."""
        mock_do_bump.return_value = ("0.1.0", "0.1.1")
        bump_main(BumpType.PATCH)
        mock_do_bump.assert_called_once()

    @patch("anvil.services.vault.bump_version._do_bump")
    def test_default_increment_is_patch(self, mock_do_bump) -> None:
        """bump_main defaults to PATCH increment."""
        mock_do_bump.return_value = ("0.1.0", "0.1.1")
        bump_main()
        args, _ = mock_do_bump.call_args
        assert args[0] == BumpType.PATCH

    @patch("anvil.services.vault.bump_version._do_bump")
    def test_handles_value_error(self, mock_do_bump) -> None:
        """bump_main catches ValueError and calls sys.exit(1)."""
        mock_do_bump.side_effect = ValueError("bad version")
        with pytest.raises(SystemExit) as exc_info:
            bump_main(BumpType.PATCH)
        assert exc_info.value.code == 1


class TestMain:
    """Tests for the bump-patch CLI entry point."""

    @patch("anvil.services.vault.bump_version.bump_main")
    def test_calls_bump_main_with_patch(self, mock_bump_main) -> None:
        """main() calls bump_main with PATCH."""
        main()
        mock_bump_main.assert_called_once_with(BumpType.PATCH)