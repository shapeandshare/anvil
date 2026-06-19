"""Unit tests for the ADR uniqueness checker.

Tests that check_adr_unique.py correctly detects duplicate ADR-0NN
identifiers, passes unique sets, and handles off-pattern filenames.
Follows TDD per the constitution mandate.
"""

from pathlib import Path

from scripts.ci.check_adr_unique import (
    ADRIssue,
    _extract_adr_numbers,
    _find_duplicates,
    _validate_adrs,
)


class TestExtractADRNumbers:
    """Tests for extracting ADR identifiers from filenames."""

    def test_standard_adr_pattern(self, tmp_path: Path) -> None:
        """A file named ADR-0NN-*.md extracts 'ADR-0NN'."""
        files = {tmp_path / "ADR-001-architecture-decisions.md"}
        result = _extract_adr_numbers(files)
        assert result == {"ADR-001"}

    def test_off_pattern_is_rejected(self, tmp_path: Path) -> None:
        """A file that doesn't match ADR-0NN-*.md raises an issue."""
        files = {tmp_path / "010-numpy-docstring-enforcement.md"}
        numbers, issues = _extract_adr_numbers(files)
        assert len(issues) == 1
        assert "does not match ADR-0NN" in issues[0].message

    def test_mixed_patterns(self, tmp_path: Path) -> None:
        """Mixed ADR and non-ADR files return only valid ADRs plus issues."""
        files = {
            tmp_path / "ADR-001-arch.md",
            tmp_path / "ADR-002-bridge.md",
            tmp_path / "just-a-note.md",
            tmp_path / "README.md",
        }
        numbers, issues = _extract_adr_numbers(files)
        assert "ADR-001" in numbers
        assert "ADR-002" in numbers
        assert len(numbers) == 2

    def test_case_sensitive_pattern(self, tmp_path: Path) -> None:
        """ADR- should be uppercase per convention."""
        files = {tmp_path / "adr-003-lowercase.md"}
        numbers, issues = _extract_adr_numbers(files)
        assert len(numbers) == 0
        if issues:
            assert "adr-003" in issues[0].message or "ADR" in issues[0].message


class TestFindDuplicates:
    """Tests for duplicate ADR number detection."""

    def test_no_duplicates(self) -> None:
        """Unique ADR numbers return empty issue list."""
        numbers = {"ADR-001", "ADR-002", "ADR-003"}
        issues = _find_duplicates(numbers)
        assert len(issues) == 0

    def test_detects_duplicates(self) -> None:
        """Duplicate ADR numbers generate issues."""
        numbers = {"ADR-001", "ADR-001"}
        issues = _find_duplicates(numbers)
        assert len(issues) == 1
        assert "ADR-001" in issues[0].message

    def test_multiple_collisions(self) -> None:
        """Multiple collisions are each reported."""
        numbers = {"ADR-001", "ADR-001", "ADR-008", "ADR-008", "ADR-016", "ADR-016"}
        issues = _find_duplicates(numbers)
        assert len(issues) == 3


class TestValidateADRs:
    """Integration-level tests for the full validation."""

    def test_clean_adr_directory(self, tmp_path: Path) -> None:
        """A directory of unique, correctly-named ADRs passes."""
        (tmp_path / "ADR-001-first.md").write_text("")
        (tmp_path / "ADR-002-second.md").write_text("")
        (tmp_path / "README.md").write_text("")
        issues = _validate_adrs(tmp_path)
        assert len(issues) == 0

    def test_directory_with_collisions(self, tmp_path: Path) -> None:
        """A directory with duplicate ADR numbers fails."""
        (tmp_path / "ADR-008-release.md").write_text("")
        (tmp_path / "ADR-008-tabbed-layout.md").write_text("")
        issues = _validate_adrs(tmp_path)
        assert len(issues) == 1
        assert "ADR-008" in issues[0].message

    def test_directory_with_off_pattern(self, tmp_path: Path) -> None:
        """Off-pattern ADR files generate issues."""
        (tmp_path / "010-missing-adr-prefix.md").write_text("")
        issues = _validate_adrs(tmp_path)
        assert len(issues) == 1
