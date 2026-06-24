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
    BumpType,
    _bump,
    _bump_patch,
    _prepend_changelog,
    _update_pyproject,
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
        import pytest

        with pytest.raises(ValueError):
            _bump("0.1.0", "INVALID")

    def test_invalid_format_raises(self) -> None:
        """Non-MAJOR.MINOR.PATCH strings raise ValueError."""
        import pytest

        with pytest.raises(ValueError):
            _bump("abc", BumpType.PATCH)
        with pytest.raises(ValueError):
            _bump("0.1", BumpType.PATCH)
        with pytest.raises(ValueError):
            _bump("0.1.0-beta", BumpType.PATCH)


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
            assert "### Features" in text
            assert "# Changelog" in text
        finally:
            os.unlink(path)

    def test_major_changelog_message(self) -> None:
        """Major increments get the correct label in the changelog."""
        import tempfile

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
        import tempfile

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
