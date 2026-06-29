# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for the ADR uniqueness checker.

Tests ``_extract_adr_numbers``, ``_find_duplicates``,
``_validate_adrs``, and the ``main`` CLI entry point.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from anvil.services.vault.check_adr_unique import (
    ADRIssue,
    _extract_adr_numbers,
    _find_duplicates,
    _validate_adrs,
    main,
)

########################################################################
# _extract_adr_numbers tests
########################################################################


class TestExtractAdrNumbers:
    """Tests for the _extract_adr_numbers helper."""

    def test_single_adr(self, tmp_path: Path) -> None:
        """Single ADR-001 file is extracted."""
        (tmp_path / "ADR-001-first-decision.md").write_text("# ADR 1")
        files = set(tmp_path.iterdir())
        numbers, issues = _extract_adr_numbers(files)
        assert "ADR-001" in numbers
        assert len(numbers["ADR-001"]) == 1
        assert len(issues) == 0

    def test_multiple_adrs(self, tmp_path: Path) -> None:
        """Multiple unique ADR files are extracted."""
        (tmp_path / "ADR-001-first.md").write_text("# ADR 1")
        (tmp_path / "ADR-002-second.md").write_text("# ADR 2")
        (tmp_path / "ADR-010-tenth.md").write_text("# ADR 10")
        files = set(tmp_path.iterdir())
        numbers, issues = _extract_adr_numbers(files)
        assert "ADR-001" in numbers
        assert "ADR-002" in numbers
        assert "ADR-010" in numbers
        assert len(issues) == 0

    def test_skips_template_and_readme(self, tmp_path: Path) -> None:
        """ADR-template.md and README.md are skipped."""
        (tmp_path / "ADR-template.md").write_text("# Template")
        (tmp_path / "README.md").write_text("# Readme")
        (tmp_path / "ADR-001-real.md").write_text("# ADR 1")
        files = set(tmp_path.iterdir())
        numbers, issues = _extract_adr_numbers(files)
        assert "ADR-001" in numbers
        assert len(numbers) == 1
        assert len(issues) == 0

    def test_off_pattern_numeric_prefix(self, tmp_path: Path) -> None:
        """File with numeric prefix but missing ADR- is flagged."""
        (tmp_path / "001-decision.md").write_text("# decision")
        files = set(tmp_path.iterdir())
        numbers, issues = _extract_adr_numbers(files)
        assert len(numbers) == 0
        assert len(issues) == 1
        assert "001" in issues[0].message
        assert "ADR-001" in issues[0].message

    def test_off_pattern_and_valid(self, tmp_path: Path) -> None:
        """Valid ADR works alongside off-pattern file."""
        (tmp_path / "ADR-001-valid.md").write_text("# ADR 1")
        (tmp_path / "002-off.md").write_text("# off")
        files = set(tmp_path.iterdir())
        numbers, issues = _extract_adr_numbers(files)
        assert "ADR-001" in numbers
        assert len(issues) == 1
        assert "002" in issues[0].message

    def test_non_adr_file_skipped(self, tmp_path: Path) -> None:
        """Non-ADR .md files without numeric prefix are skipped."""
        (tmp_path / "index.md").write_text("# index")
        (tmp_path / "ADR-001-real.md").write_text("# ADR 1")
        files = set(tmp_path.iterdir())
        numbers, issues = _extract_adr_numbers(files)
        assert "ADR-001" in numbers
        assert len(issues) == 0


########################################################################
# _find_duplicates tests
########################################################################


class TestFindDuplicates:
    """Tests for the _find_duplicates helper."""

    def test_no_duplicates(self) -> None:
        """Returns empty list when no duplicates exist."""
        numbers = {
            "ADR-001": [Path("ADR-001-first.md")],
            "ADR-002": [Path("ADR-002-second.md")],
        }
        issues = _find_duplicates(numbers)
        assert len(issues) == 0

    def test_duplicate_detected(self) -> None:
        """Returns issue when duplicate ADR numbers exist."""
        numbers = {
            "ADR-001": [
                Path("docs/vault/Decisions/ADR-001-first.md"),
                Path("docs/vault/Decisions/ADR-001-second.md"),
            ],
        }
        issues = _find_duplicates(numbers)
        assert len(issues) == 1
        assert "Duplicate ADR identifier" in issues[0].message
        assert "ADR-001" in issues[0].message

    def test_multiple_duplicate_groups(self) -> None:
        """Reports duplicate issues for each duplicated ADR number."""
        numbers = {
            "ADR-001": [
                Path("docs/vault/Decisions/ADR-001-a.md"),
                Path("docs/vault/Decisions/ADR-001-b.md"),
            ],
            "ADR-002": [
                Path("docs/vault/Decisions/ADR-002-a.md"),
                Path("docs/vault/Decisions/ADR-002-b.md"),
            ],
        }
        issues = _find_duplicates(numbers)
        assert len(issues) == 2

    def test_triplicate_detected(self) -> None:
        """Three files with same ADR number are detected."""
        numbers = {
            "ADR-001": [
                Path("docs/vault/Decisions/ADR-001-a.md"),
                Path("docs/vault/Decisions/ADR-001-b.md"),
                Path("docs/vault/Decisions/ADR-001-c.md"),
            ],
        }
        issues = _find_duplicates(numbers)
        assert len(issues) == 1
        assert "3 files" in issues[0].message


########################################################################
# _validate_adrs tests
########################################################################


class TestValidateAdrs:
    """Tests for the _validate_adrs function."""

    def test_valid_directory(self, tmp_path: Path) -> None:
        """Valid directory with unique ADRs returns no issues."""
        (tmp_path / "ADR-001-first.md").write_text("# ADR 1")
        (tmp_path / "ADR-002-second.md").write_text("# ADR 2")
        issues = _validate_adrs(tmp_path)
        assert len(issues) == 0

    def test_duplicate_adrs(self, tmp_path: Path) -> None:
        """Duplicate ADR numbers are detected."""
        (tmp_path / "ADR-001-first.md").write_text("# ADR 1")
        (tmp_path / "ADR-001-second.md").write_text("# ADR 1 again")
        issues = _validate_adrs(tmp_path)
        assert len(issues) == 1
        assert "Duplicate ADR identifier" in issues[0].message

    def test_off_pattern_file(self, tmp_path: Path) -> None:
        """Off-pattern numeric file is flagged."""
        (tmp_path / "001-decision.md").write_text("# decision")
        issues = _validate_adrs(tmp_path)
        assert len(issues) == 1
        assert "001" in issues[0].message

    def test_directory_not_found(self, tmp_path: Path) -> None:
        """Non-existent directory returns an issue."""
        missing = tmp_path / "nonexistent"
        issues = _validate_adrs(missing)
        assert len(issues) == 1
        assert "not found" in issues[0].message

    def test_empty_directory(self, tmp_path: Path) -> None:
        """Empty directory returns no issues."""
        issues = _validate_adrs(tmp_path)
        assert len(issues) == 0

    def test_duplicate_and_off_pattern(self, tmp_path: Path) -> None:
        """Both duplicates and off-pattern files are reported."""
        (tmp_path / "ADR-001-first.md").write_text("# ADR 1")
        (tmp_path / "ADR-001-second.md").write_text("# ADR 1 again")
        (tmp_path / "002-decision.md").write_text("# decision")
        issues = _validate_adrs(tmp_path)
        assert len(issues) == 2


########################################################################
# CLI main tests
########################################################################


class TestMain:
    """Tests for the CLI entry point."""

    def test_valid_exits_0(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Valid ADRs exit with code 0."""
        (tmp_path / "ADR-001-first.md").write_text("# ADR 1")
        monkeypatch.setenv("ANVIL_DECISIONS_DIR", str(tmp_path))
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 0

    def test_duplicate_exits_1(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Duplicate ADRs exit with code 1."""
        (tmp_path / "ADR-001-first.md").write_text("# ADR 1")
        (tmp_path / "ADR-001-second.md").write_text("# ADR 1 again")
        monkeypatch.setenv("ANVIL_DECISIONS_DIR", str(tmp_path))
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 1

    def test_off_pattern_exits_1(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Off-pattern files exit with code 1."""
        (tmp_path / "001-decision.md").write_text("# decision")
        monkeypatch.setenv("ANVIL_DECISIONS_DIR", str(tmp_path))
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 1
