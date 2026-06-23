# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for the auto-bump version logic.

Tests that ``bump_version.py`` correctly increments patch versions,
modifies ``pyproject.toml`` in-place, and prepends changelog entries.
"""

import os
import tempfile

from anvil.services.vault.bump_version import (
    _bump_patch,
    _prepend_changelog,
    _update_pyproject,
)


class TestBumpPatch:
    """Tests for the version-string increment helper."""

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

    def test_invalid_format_raises(self) -> None:
        """Non-MAJOR.MINOR.PATCH strings raise ValueError."""
        import pytest

        with pytest.raises(ValueError):
            _bump_patch("abc")
        with pytest.raises(ValueError):
            _bump_patch("0.1")
        with pytest.raises(ValueError):
            _bump_patch("0.1.0-beta")


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
        import pytest

        content = 'version = "0.2.0"\n'
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write(content)
            path = f.name
        try:
            with pytest.raises(RuntimeError):
                _update_pyproject(path, "0.2.1", "0.1.0")
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
            assert "# Changelog" in text
        finally:
            os.unlink(path)
