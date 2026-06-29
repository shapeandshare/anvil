# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for :mod:`anvil.services.vault.build_notes` — release notes
builder.
"""

from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

import pytest


class TestExtractChangelogEntry:
    """Tests for ``_extract_changelog_entry``."""

    @pytest.fixture(autouse=True)
    def _chdir_tmp(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)

    def test_exact_version_found(self, tmp_path: Path) -> None:
        changelog = (
            "# Changelog\n\n"
            "## v0.5.0\n\n"
            "- Added training dashboard\n"
            "- Fixed model loading\n\n"
            "## v0.4.0\n\n"
            "- Initial release\n"
        )
        (tmp_path / "CHANGELOG.md").write_text(changelog)
        from anvil.services.vault.build_notes import _extract_changelog_entry

        entry = _extract_changelog_entry("0.5.0")
        assert entry is not None
        assert "Added training dashboard" in entry
        assert "Fixed model loading" in entry
        assert "Initial release" not in entry

    def test_version_not_found(self, tmp_path: Path) -> None:
        changelog = "# Changelog\n\n## v0.4.0\n\n- Initial release\n"
        (tmp_path / "CHANGELOG.md").write_text(changelog)
        from anvil.services.vault.build_notes import _extract_changelog_entry

        entry = _extract_changelog_entry("0.5.0")
        assert entry is None

    def test_no_changelog_file(self) -> None:
        from anvil.services.vault.build_notes import _extract_changelog_entry

        entry = _extract_changelog_entry("0.5.0")
        assert entry is None

    def test_last_version_in_file(self, tmp_path: Path) -> None:
        changelog = "# Changelog\n\n## v0.5.0\n\n- Last release\n"
        (tmp_path / "CHANGELOG.md").write_text(changelog)
        from anvil.services.vault.build_notes import _extract_changelog_entry

        entry = _extract_changelog_entry("0.5.0")
        assert entry is not None
        assert "Last release" in entry

    def test_entry_with_dashes_removed(self, tmp_path: Path) -> None:
        changelog = (
            "# Changelog\n\n"
            "## v0.5.0\n\n"
            "- Feature one\n"
            "---\n"
            "- Feature two\n"
        )
        (tmp_path / "CHANGELOG.md").write_text(changelog)
        from anvil.services.vault.build_notes import _extract_changelog_entry

        entry = _extract_changelog_entry("0.5.0")
        assert entry is not None
        assert "---" not in entry
        assert "Feature one" in entry
        assert "Feature two" in entry

    def test_entry_is_just_dashes_returns_none(self, tmp_path: Path) -> None:
        changelog = "# Changelog\n\n## v0.5.0\n\n---\n"
        (tmp_path / "CHANGELOG.md").write_text(changelog)
        from anvil.services.vault.build_notes import _extract_changelog_entry

        entry = _extract_changelog_entry("0.5.0")
        assert entry is None


class TestMain:
    """Tests for ``main()`` — the CLI entry point."""

    @pytest.fixture(autouse=True)
    def _chdir_tmp(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)

    @pytest.fixture
    def _write_changelog(self, tmp_path: Path) -> Generator[None, None, None]:
        changelog = (
            "# Changelog\n\n"
            "## v0.5.0\n\n"
            "- Added training dashboard\n"
            "- Fixed model loading\n\n"
            "## v0.4.0\n\n"
            "- Initial release\n"
        )
        (tmp_path / "CHANGELOG.md").write_text(changelog)
        yield

    def test_writes_release_notes_with_changelog(
        self,
        capsys: pytest.CaptureFixture[str],
        _write_changelog: None,
    ) -> None:
        with patch(
            "anvil.services.vault.build_notes.read_version",
            return_value="0.5.0",
        ):
            from anvil.services.vault.build_notes import main

            with pytest.raises(SystemExit) as exc:
                main()
            assert exc.value.code == 0
        captured = capsys.readouterr()
        assert "release-notes.md written (v0.5.0)" in captured.out

    def test_writes_release_notes_without_changelog(
        self,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        with patch(
            "anvil.services.vault.build_notes.read_version",
            return_value="0.5.0",
        ):
            from anvil.services.vault.build_notes import main

            with pytest.raises(SystemExit) as exc:
                main()
            assert exc.value.code == 0

    def test_writes_pr_body_when_set(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        _write_changelog: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("PR_BODY", "This PR adds a new training dashboard.")
        with patch(
            "anvil.services.vault.build_notes.read_version",
            return_value="0.5.0",
        ):
            from anvil.services.vault.build_notes import main

            with pytest.raises(SystemExit) as exc:
                main()
            assert exc.value.code == 0
        notes = (tmp_path / "release-notes.md").read_text()
        assert "### Release Notes" in notes
        assert "This PR adds a new training dashboard." in notes

    def test_exits_with_error_on_missing_version(
        self,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        with patch(
            "anvil.services.vault.build_notes.read_version",
            return_value=None,
        ):
            from anvil.services.vault.build_notes import main

            with pytest.raises(SystemExit) as exc:
                main()
            assert exc.value.code == 1
