"""Unit tests for anvil/services/vault/build_notes.py.

Tests changelog entry extraction (_extract_changelog_entry) using
temporary files to simulate CHANGELOG.md content.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from anvil.services.vault.build_notes import _extract_changelog_entry

##############################################################################
# _extract_changelog_entry
##############################################################################


def test_extract_basic_entry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A standard changelog entry is extracted correctly."""
    monkeypatch.chdir(tmp_path)
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(
        "# Changelog\n\n"
        "## v0.5.0\n\n"
        "- Feature A\n"
        "- Feature B\n\n"
        "## v0.4.0\n\n"
        "- Fix C\n"
    )

    entry = _extract_changelog_entry("0.5.0")
    assert entry is not None
    assert "- Feature A" in entry
    assert "- Feature B" in entry
    assert "- Fix C" not in entry


def test_extract_last_entry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The last changelog entry (no following ##) is extracted."""
    monkeypatch.chdir(tmp_path)
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text("# Changelog\n\n" "## v1.0.0\n\n" "Initial release.\n")

    entry = _extract_changelog_entry("1.0.0")
    assert entry is not None
    assert entry == "Initial release."


def test_extract_entry_with_dashes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Horizontal rules (---) inside entries are stripped."""
    monkeypatch.chdir(tmp_path)
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(
        "# Changelog\n\n"
        "## v0.5.0\n\n"
        "- Feature A\n"
        "---\n"
        "- Feature B\n\n"
        "## v0.4.0\n\n"
        "- Fix C\n"
    )

    entry = _extract_changelog_entry("0.5.0")
    assert entry is not None
    assert "---" not in entry
    assert "- Feature A" in entry
    assert "- Feature B" in entry


def test_extract_entry_not_found(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A version not in the changelog returns None."""
    monkeypatch.chdir(tmp_path)
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text("# Changelog\n\n## v0.4.0\n\nOld stuff.\n")

    entry = _extract_changelog_entry("9.9.9")
    assert entry is None


def test_extract_missing_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Missing CHANGELOG.md returns None (no crash)."""
    monkeypatch.chdir(tmp_path)
    entry = _extract_changelog_entry("0.5.0")
    assert entry is None


def test_extract_empty_entry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An empty entry (only version header) returns None."""
    monkeypatch.chdir(tmp_path)
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text("# Changelog\n\n## v0.5.0\n\n## v0.4.0\n\nOld.\n")

    entry = _extract_changelog_entry("0.5.0")
    assert entry is None


def test_extract_multiline_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Multi-line entries are preserved."""
    monkeypatch.chdir(tmp_path)
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(
        "## v0.5.0\n\n" "- Line one\n" "- Line two\n" "\n" "More details.\n"
    )

    entry = _extract_changelog_entry("0.5.0")
    assert entry is not None
    assert "- Line one" in entry
    assert "- Line two" in entry
    assert "More details." in entry


def test_extract_version_with_v_prefix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The version passed to the function does not include 'v' prefix."""
    monkeypatch.chdir(tmp_path)
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text("## v0.5.0\n\nContent.\n")

    entry = _extract_changelog_entry("0.5.0")
    assert entry is not None
    assert entry == "Content."


def test_extract_respects_version_boundary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Extraction stops at the next ## v line."""
    monkeypatch.chdir(tmp_path)
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(
        "## v0.5.0\n\n"
        "Content A\n\n"
        "## v0.4.0\n\n"
        "Content B\n\n"
        "## v0.3.0\n\n"
        "Content C\n"
    )

    entry = _extract_changelog_entry("0.4.0")
    assert entry is not None
    assert "Content B" in entry
    assert "Content A" not in entry
    assert "Content C" not in entry


def test_extract_strips_leading_trailing_whitespace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Leading/trailing whitespace is stripped from entries."""
    monkeypatch.chdir(tmp_path)
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text("## v0.5.0\n\n\n  \nContent.\n  \n\n")

    entry = _extract_changelog_entry("0.5.0")
    assert entry is not None
    assert entry == "Content."
