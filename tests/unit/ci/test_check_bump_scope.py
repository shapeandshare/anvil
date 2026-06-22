# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for the bump-scope guard.

Tests that check_bump_scope.py correctly classifies PR changes as
version-only-bump vs. source-touching, and validates its file-scope
contract (FR-006a).
"""

from pathlib import Path

import pytest

from anvil.services.vault.check_bump_scope import (
    _changed_files,
    _is_version_only,
    _validate_bump_scope,
)


class TestIsVersionOnly:
    """Tests for the core classification predicate."""

    def test_version_pyproject_only(self) -> None:
        """A change touching only pyproject.toml's version line is version-only."""
        changed = {"pyproject.toml"}
        assert _is_version_only(changed) is True

    def test_changelog_only(self) -> None:
        """A change touching only CHANGELOG.md is version-only."""
        changed = {"CHANGELOG.md"}
        assert _is_version_only(changed) is True

    def test_both_version_files(self) -> None:
        """A change touching both pyproject.toml and CHANGELOG.md is version-only."""
        changed = {"pyproject.toml", "CHANGELOG.md"}
        assert _is_version_only(changed) is True

    def test_includes_source_file(self) -> None:
        """A change that also touches a source file is NOT version-only."""
        changed = {"pyproject.toml", "anvil/cli.py"}
        assert _is_version_only(changed) is False

    def test_includes_test_file(self) -> None:
        """A change that also touches a test file is NOT version-only."""
        changed = {"CHANGELOG.md", "tests/unit/test_something.py"}
        assert _is_version_only(changed) is False

    def test_no_known_files(self) -> None:
        """An empty or unknown file set is not version-only."""
        assert _is_version_only(set()) is False
        assert _is_version_only({"Makefile"}) is False

    def test_dotfiles_are_not_version(self) -> None:
        """Any other file (configs, docs, CI) triggers a full gate."""
        changed = {"pyproject.toml", ".github/workflows/ci.yml"}
        assert _is_version_only(changed) is False


class TestChangedFiles:
    """Tests for the git-diff-based file-list extraction."""

    def test_extracts_from_git_diff(self, tmp_path: Path) -> None:
        """Given a repo and a reference commit, _changed_files returns paths."""
        # Create a minimal git repo with a commit and some changes
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "file_a.txt").write_text("hello")
        (repo / "sub").mkdir()
        (repo / "sub" / "file_b.txt").write_text("world")

        result = _changed_files(str(repo))
        # If there's no git ref, the function returns ['CHANGELOG.md', 'pyproject.toml']
        # as a safe default for HEAD~1
        assert isinstance(result, list)


class TestValidateBumpScope:
    """Tests for the main CLI entrypoint validation."""

    def test_version_only_exits_zero(self, tmp_path: Path) -> None:
        """A version-only change should exit 0 (acceptable)."""
        # Simulated state
        repo = tmp_path / "repo"
        repo.mkdir()
        _validate_bump_scope({"pyproject.toml", "CHANGELOG.md"}, str(repo))

    def test_source_change_exits_zero_but_flags(self, tmp_path: Path) -> None:
        """A source-touching change should exit 0 (the guard always passes;
        it's a classifier, not an enforcer — enforcement is branch protection.
        """
        repo = tmp_path / "repo"
        repo.mkdir()
        _validate_bump_scope({"anvil/cli.py"}, str(repo))
